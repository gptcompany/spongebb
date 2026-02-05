"""LSTM-based regime forecaster using PyTorch.

Provides probabilistic regime forecasting for 7/14/30 day horizons.

The LSTM approach differs from HMM/Markov Switching in that:
- Captures long-term dependencies (memory cells)
- Learns non-linear patterns automatically
- Better suited for forecasting future regimes
- Requires more data for training
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from .hmm_classifier import RegimeProbabilities, RegimeState

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class LSTMForecast:
    """Forecast result for a single horizon.

    Attributes:
        horizon: Days ahead for forecast.
        probabilities: Array of probabilities [expansion, neutral, contraction].
        predicted_regime: Most likely regime.
        confidence: Maximum probability.
    """

    horizon: int
    probabilities: NDArray[np.float64]
    predicted_regime: RegimeState
    confidence: float


@dataclass
class LSTMDiagnostics:
    """Diagnostics for LSTM model.

    Attributes:
        train_loss: Final training loss.
        val_loss: Final validation loss (if available).
        epochs_trained: Number of epochs trained.
        best_epoch: Epoch with best validation loss.
        sequence_length: Input sequence length used.
        hidden_size: LSTM hidden size.
    """

    train_loss: float
    val_loss: float | None
    epochs_trained: int
    best_epoch: int
    sequence_length: int
    hidden_size: int


class RegimeLSTM(nn.Module):
    """LSTM network for regime classification.

    Architecture:
        Input -> LSTM layers -> Dropout -> Linear -> Softmax
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        num_classes: int = 3,
        dropout: float = 0.2,
    ):
        """Initialize LSTM network.

        Args:
            input_size: Number of input features.
            hidden_size: LSTM hidden layer size.
            num_layers: Number of stacked LSTM layers.
            num_classes: Number of output classes (regimes).
            dropout: Dropout probability.
        """
        super().__init__()

        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True,
        )

        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len, features).

        Returns:
            Logits tensor of shape (batch, num_classes).
        """
        # LSTM forward
        lstm_out, (h_n, _) = self.lstm(x)

        # Use last hidden state
        last_hidden = h_n[-1]  # (batch, hidden_size)

        # Fully connected layers
        logits = self.fc(last_hidden)

        return logits


class LSTMRegimeForecaster:
    """LSTM-based regime forecaster for multi-horizon prediction.

    Trains separate models for each forecast horizon (7, 14, 30 days).
    Uses walk-forward validation to prevent lookahead bias.

    Example:
        forecaster = LSTMRegimeForecaster(sequence_length=30)
        forecaster.fit(features_df, labels_series)
        forecasts = forecaster.forecast(latest_features)
    """

    HORIZONS = [7, 14, 30]

    def __init__(
        self,
        sequence_length: int = 30,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        learning_rate: float = 0.001,
        epochs: int = 50,
        batch_size: int = 32,
        early_stopping_patience: int = 10,
        device: str | None = None,
    ):
        """Initialize LSTM forecaster.

        Args:
            sequence_length: Number of time steps to look back.
            hidden_size: LSTM hidden layer size.
            num_layers: Number of stacked LSTM layers.
            dropout: Dropout probability for regularization.
            learning_rate: Adam optimizer learning rate.
            epochs: Maximum training epochs.
            batch_size: Training batch size.
            early_stopping_patience: Epochs without improvement before stopping.
            device: Device to use ('cpu', 'cuda', or None for auto).
        """
        self.sequence_length = sequence_length
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.early_stopping_patience = early_stopping_patience

        # Auto-detect device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self._models: dict[int, RegimeLSTM] = {}
        self._scalers: dict[str, tuple[float, float]] = {}  # (mean, std) per feature
        self._is_fitted = False
        self._input_size: int = 0
        self._diagnostics: dict[int, LSTMDiagnostics] = {}

    @property
    def is_fitted(self) -> bool:
        """Return whether model has been fitted."""
        return self._is_fitted

    def fit(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
        val_split: float = 0.2,
    ) -> "LSTMRegimeForecaster":
        """Fit LSTM models for all horizons.

        Args:
            features: DataFrame with feature columns (e.g., net_liq_pct, global_liq_pct).
            labels: Series with RegimeState labels for each timestamp.
            val_split: Fraction of data to use for validation.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If insufficient data for training.
        """
        min_samples = self.sequence_length + max(self.HORIZONS) + 100
        if len(features) < min_samples:
            raise ValueError(
                f"Insufficient data: need at least {min_samples} samples, got {len(features)}"
            )

        # Store feature names and compute normalization stats
        self._input_size = len(features.columns)
        for col in features.columns:
            self._scalers[col] = (float(features[col].mean()), float(features[col].std()))

        # Normalize features
        X_normalized = self._normalize(features)

        # Convert labels to integers
        label_to_int = {
            RegimeState.EXPANSION: 0,
            RegimeState.NEUTRAL: 1,
            RegimeState.CONTRACTION: 2,
        }
        y_int = np.asarray(labels.map(lambda x: label_to_int.get(x, 1)).values)

        # Train model for each horizon
        for horizon in self.HORIZONS:
            logger.info(f"Training LSTM for horizon={horizon} days")

            # Create sequences
            X_seq, y_seq = self._create_sequences(X_normalized, y_int, horizon)

            if len(X_seq) < 100:
                logger.warning(f"Insufficient sequences for horizon={horizon}, skipping")
                continue

            # Train/val split (time-based, not random)
            split_idx = int(len(X_seq) * (1 - val_split))
            X_train, X_val = X_seq[:split_idx], X_seq[split_idx:]
            y_train, y_val = y_seq[:split_idx], y_seq[split_idx:]

            # Create DataLoaders
            train_dataset = TensorDataset(
                torch.FloatTensor(X_train),
                torch.LongTensor(y_train),
            )
            train_loader = DataLoader(
                train_dataset,
                batch_size=self.batch_size,
                shuffle=True,
            )

            val_dataset = TensorDataset(
                torch.FloatTensor(X_val),
                torch.LongTensor(y_val),
            )
            val_loader = DataLoader(val_dataset, batch_size=self.batch_size)

            # Train model
            model, diag = self._train_model(train_loader, val_loader, horizon)
            self._models[horizon] = model
            self._diagnostics[horizon] = diag

        self._is_fitted = True
        return self

    def forecast(
        self,
        features: pd.DataFrame,
    ) -> list[LSTMForecast]:
        """Generate forecasts for all horizons.

        Args:
            features: DataFrame with recent feature values.
                      Must have at least sequence_length rows.

        Returns:
            List of LSTMForecast for each horizon.

        Raises:
            ValueError: If model not fitted or insufficient data.
        """
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        if len(features) < self.sequence_length:
            raise ValueError(
                f"Need at least {self.sequence_length} rows, got {len(features)}"
            )

        # Use latest sequence
        latest = features.iloc[-self.sequence_length :]
        X_normalized = self._normalize(latest)
        X_tensor = torch.FloatTensor(X_normalized).unsqueeze(0).to(self.device)

        forecasts = []
        for horizon in self.HORIZONS:
            if horizon not in self._models:
                continue

            model = self._models[horizon]
            model.eval()

            with torch.no_grad():
                logits = model(X_tensor)
                probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

            predicted_regime = RegimeState(int(np.argmax(probs)))
            confidence = float(np.max(probs))

            forecasts.append(
                LSTMForecast(
                    horizon=horizon,
                    probabilities=probs.astype(np.float64),
                    predicted_regime=predicted_regime,
                    confidence=confidence,
                )
            )

        return forecasts

    def get_regime_probabilities(
        self,
        features: pd.DataFrame,
        horizon: int = 7,
    ) -> list[RegimeProbabilities]:
        """Get regime probabilities for ensemble compatibility.

        Args:
            features: DataFrame with feature columns.
            horizon: Forecast horizon to use.

        Returns:
            List of RegimeProbabilities for each timestamp.
        """
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        if horizon not in self._models:
            raise ValueError(f"No model for horizon={horizon}")

        model = self._models[horizon]
        model.eval()

        # Normalize features
        X_normalized = self._normalize(features)

        # Create sequences for all timestamps
        results = []
        for i in range(self.sequence_length, len(features)):
            seq = X_normalized[i - self.sequence_length : i]
            X_tensor = torch.FloatTensor(seq).unsqueeze(0).to(self.device)

            with torch.no_grad():
                logits = model(X_tensor)
                probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

            predicted_regime = RegimeState(int(np.argmax(probs)))
            confidence = float(np.max(probs))
            timestamp = features.index[i]

            results.append(
                RegimeProbabilities(
                    timestamp=pd.Timestamp(timestamp),  # type: ignore[arg-type]
                    expansion=float(probs[0]),
                    neutral=float(probs[1]),
                    contraction=float(probs[2]),
                    current_regime=predicted_regime,
                    confidence=confidence,
                )
            )

        return results

    def get_diagnostics(self, horizon: int = 7) -> LSTMDiagnostics:
        """Get model diagnostics for a specific horizon.

        Args:
            horizon: Forecast horizon.

        Returns:
            LSTMDiagnostics for the specified horizon.
        """
        if horizon not in self._diagnostics:
            raise ValueError(f"No diagnostics for horizon={horizon}")

        return self._diagnostics[horizon]

    def _normalize(self, features: pd.DataFrame) -> NDArray[np.float64]:
        """Normalize features using stored statistics."""
        result = np.zeros((len(features), len(features.columns)), dtype=np.float64)

        for i, col in enumerate(features.columns):
            mean, std = self._scalers.get(col, (0.0, 1.0))
            if std < 1e-8:
                std = 1.0
            col_values = np.asarray(features[col].values, dtype=np.float64)
            result[:, i] = (col_values - mean) / std

        return result

    def _create_sequences(
        self,
        X: NDArray[np.float64],
        y: NDArray[Any],
        horizon: int,
    ) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
        """Create sequences for training.

        Args:
            X: Normalized feature array.
            y: Label array.
            horizon: Forecast horizon.

        Returns:
            Tuple of (sequences, targets).
        """
        sequences = []
        targets = []

        # For each position, use past sequence_length values to predict
        # the label horizon days ahead
        for i in range(self.sequence_length, len(X) - horizon):
            seq = X[i - self.sequence_length : i]
            target = y[i + horizon]

            sequences.append(seq)
            targets.append(target)

        return np.array(sequences, dtype=np.float64), np.array(targets, dtype=np.int64)

    def _train_model(
        self,
        train_loader: DataLoader[tuple[torch.Tensor, ...]],
        val_loader: DataLoader[tuple[torch.Tensor, ...]],
        horizon: int,
    ) -> tuple[RegimeLSTM, LSTMDiagnostics]:
        """Train a single LSTM model.

        Args:
            train_loader: Training data loader.
            val_loader: Validation data loader.
            horizon: Forecast horizon (for diagnostics).

        Returns:
            Tuple of (trained model, diagnostics).
        """
        model = RegimeLSTM(
            input_size=self._input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            num_classes=3,
            dropout=self.dropout,
        ).to(self.device)

        optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)
        criterion = nn.CrossEntropyLoss()

        best_val_loss = float("inf")
        best_epoch = 0
        patience_counter = 0
        best_state: dict[str, Any] = {}

        train_losses = []
        val_losses = []

        for epoch in range(self.epochs):
            # Training
            model.train()
            epoch_loss = 0.0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                optimizer.zero_grad()
                logits = model(X_batch)
                loss = criterion(logits, y_batch)
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()

            train_loss = epoch_loss / len(train_loader)
            train_losses.append(train_loss)

            # Validation
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(self.device)
                    y_batch = y_batch.to(self.device)

                    logits = model(X_batch)
                    loss = criterion(logits, y_batch)
                    val_loss += loss.item()

            val_loss = val_loss / len(val_loader)
            val_losses.append(val_loss)

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_epoch = epoch
                patience_counter = 0
                best_state = model.state_dict().copy()
            else:
                patience_counter += 1

            if patience_counter >= self.early_stopping_patience:
                logger.info(f"Early stopping at epoch {epoch + 1}")
                break

        # Restore best model
        if best_state:
            model.load_state_dict(best_state)

        diagnostics = LSTMDiagnostics(
            train_loss=train_losses[-1] if train_losses else 0.0,
            val_loss=val_losses[-1] if val_losses else None,
            epochs_trained=len(train_losses),
            best_epoch=best_epoch,
            sequence_length=self.sequence_length,
            hidden_size=self.hidden_size,
        )

        return model, diagnostics
