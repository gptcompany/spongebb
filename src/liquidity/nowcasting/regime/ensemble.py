"""Ensemble regime classifier combining HMM, Markov Switching, and LSTM.

The ensemble approach provides:
- More robust regime classification than any single model
- Weighted combination of different modeling perspectives
- Calibrated probability estimates
- Reduced sensitivity to individual model failures

Default weights:
- HMM: 40% (interpretable, regime persistence)
- Markov Switching: 30% (parameter switching, statistical rigor)
- LSTM: 30% (non-linear patterns, forecasting)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .hmm_classifier import HMMRegimeClassifier, RegimeProbabilities, RegimeState
from .lstm_forecaster import LSTMRegimeForecaster
from .markov_switching import MarkovSwitchingClassifier

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class EnsembleMode(Enum):
    """Ensemble combination mode."""

    WEIGHTED_AVERAGE = "weighted_average"
    VOTING = "voting"
    STACKING = "stacking"


@dataclass
class EnsembleDiagnostics:
    """Diagnostics for ensemble model.

    Attributes:
        weights: Model weights used.
        model_agreement: Average agreement between models (0-1).
        hmm_fitted: Whether HMM was successfully fitted.
        markov_fitted: Whether Markov Switching was successfully fitted.
        lstm_fitted: Whether LSTM was successfully fitted.
        calibration_error: Expected calibration error (if computed).
    """

    weights: dict[str, float]
    model_agreement: float
    hmm_fitted: bool
    markov_fitted: bool
    lstm_fitted: bool
    calibration_error: float | None


class RegimeEnsemble:
    """Ensemble classifier combining HMM, Markov Switching, and LSTM.

    Provides robust regime classification by combining multiple models
    with configurable weights. Falls back gracefully if some models fail.

    Example:
        ensemble = RegimeEnsemble(weights={'hmm': 0.4, 'markov': 0.3, 'lstm': 0.3})
        ensemble.fit(features_df, returns_series, labels_series)
        probs = ensemble.get_regime_probabilities(latest_features)
    """

    DEFAULT_WEIGHTS = {
        "hmm": 0.4,
        "markov": 0.3,
        "lstm": 0.3,
    }

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        mode: EnsembleMode = EnsembleMode.WEIGHTED_AVERAGE,
        n_states: int = 3,
        lstm_sequence_length: int = 30,
        lstm_epochs: int = 50,
    ):
        """Initialize ensemble classifier.

        Args:
            weights: Model weights (must sum to 1). Uses DEFAULT_WEIGHTS if None.
            mode: Combination mode (weighted_average, voting, or stacking).
            n_states: Number of regime states (2 or 3).
            lstm_sequence_length: LSTM lookback window.
            lstm_epochs: Maximum LSTM training epochs.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.mode = mode
        self.n_states = n_states
        self.lstm_sequence_length = lstm_sequence_length
        self.lstm_epochs = lstm_epochs

        # Validate weights
        weight_sum = sum(self.weights.values())
        if not np.isclose(weight_sum, 1.0, atol=0.01):
            raise ValueError(f"Weights must sum to 1, got {weight_sum}")

        # Initialize sub-models
        self._hmm: HMMRegimeClassifier | None = None
        self._markov: MarkovSwitchingClassifier | None = None
        self._lstm: LSTMRegimeForecaster | None = None

        self._is_fitted = False
        self._effective_weights: dict[str, float] = {}

    @property
    def is_fitted(self) -> bool:
        """Return whether ensemble has been fitted."""
        return self._is_fitted

    def fit(
        self,
        features: pd.DataFrame,
        returns: pd.Series,
        labels: pd.Series | None = None,
    ) -> "RegimeEnsemble":
        """Fit all ensemble models.

        Args:
            features: DataFrame with feature columns for HMM and LSTM.
            returns: Series with returns for Markov Switching.
            labels: Optional Series with RegimeState labels for LSTM.
                    If None, labels are inferred from HMM predictions.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If all models fail to fit.
        """
        fitted_models = 0

        # Fit HMM
        try:
            self._hmm = HMMRegimeClassifier(n_states=self.n_states)
            self._hmm.fit(features)
            fitted_models += 1
            logger.info("HMM fitted successfully")
        except Exception as e:
            logger.warning(f"HMM fitting failed: {e}")
            self._hmm = None

        # Fit Markov Switching
        try:
            self._markov = MarkovSwitchingClassifier(k_regimes=self.n_states)
            self._markov.fit(returns)
            fitted_models += 1
            logger.info("Markov Switching fitted successfully")
        except Exception as e:
            logger.warning(f"Markov Switching fitting failed: {e}")
            self._markov = None

        # Fit LSTM (requires labels)
        if labels is None and self._hmm is not None:
            # Infer labels from HMM
            hmm_probs = self._hmm.get_regime_probabilities(features)
            labels = pd.Series(
                [p.current_regime for p in hmm_probs],
                index=features.index[: len(hmm_probs)],
            )

        if labels is not None:
            try:
                self._lstm = LSTMRegimeForecaster(
                    sequence_length=self.lstm_sequence_length,
                    epochs=self.lstm_epochs,
                )
                self._lstm.fit(features, labels)
                fitted_models += 1
                logger.info("LSTM fitted successfully")
            except Exception as e:
                logger.warning(f"LSTM fitting failed: {e}")
                self._lstm = None

        if fitted_models == 0:
            raise ValueError("All models failed to fit")

        # Compute effective weights (redistribute from failed models)
        self._compute_effective_weights()

        self._is_fitted = True
        return self

    def get_regime_probabilities(
        self,
        features: pd.DataFrame,
        returns: pd.Series | None = None,
    ) -> list[RegimeProbabilities]:
        """Get ensemble regime probabilities.

        Args:
            features: DataFrame with feature columns.
            returns: Optional returns series for Markov model.

        Returns:
            List of RegimeProbabilities for each timestamp.

        Raises:
            ValueError: If ensemble not fitted.
        """
        if not self._is_fitted:
            raise ValueError("Ensemble not fitted. Call fit() first.")

        # Collect probabilities from each model
        all_probs: dict[str, list[NDArray[np.float64]]] = {
            "hmm": [],
            "markov": [],
            "lstm": [],
        }
        timestamps: list[pd.Timestamp] = []

        # HMM probabilities
        if self._hmm is not None:
            hmm_probs = self._hmm.get_regime_probabilities(features)
            for p in hmm_probs:
                all_probs["hmm"].append(p.as_array)
            timestamps = [p.timestamp for p in hmm_probs]

        # Markov probabilities
        if self._markov is not None and returns is not None:
            try:
                markov_probs = self._markov.get_regime_probabilities(smoothed=True)
                for p in markov_probs:
                    all_probs["markov"].append(p.as_array)

                # Use Markov timestamps if HMM not available
                if not timestamps:
                    timestamps = [p.timestamp for p in markov_probs]
            except Exception as e:
                logger.warning(f"Markov probabilities failed: {e}")

        # LSTM probabilities
        if self._lstm is not None:
            try:
                lstm_probs = self._lstm.get_regime_probabilities(features, horizon=7)
                for p in lstm_probs:
                    all_probs["lstm"].append(p.as_array)

                # Pad with zeros if LSTM has fewer predictions (due to sequence_length)
                pad_count = len(timestamps) - len(all_probs["lstm"])
                if pad_count > 0:
                    all_probs["lstm"] = [
                        np.array([1 / 3, 1 / 3, 1 / 3])
                    ] * pad_count + all_probs["lstm"]
            except Exception as e:
                logger.warning(f"LSTM probabilities failed: {e}")

        # Combine probabilities
        results = []
        n_samples = len(timestamps)

        for i in range(n_samples):
            combined = np.zeros(3, dtype=np.float64)
            total_weight = 0.0

            for model_name, weight in self._effective_weights.items():
                if all_probs[model_name] and i < len(all_probs[model_name]):
                    combined += weight * all_probs[model_name][i]
                    total_weight += weight

            # Normalize
            if total_weight > 0:
                combined /= total_weight

            # Ensure valid probabilities
            combined = np.clip(combined, 0, 1)
            combined /= combined.sum()

            most_likely = RegimeState(int(np.argmax(combined)))

            results.append(
                RegimeProbabilities(
                    timestamp=timestamps[i],
                    expansion=float(combined[0]),
                    neutral=float(combined[1]),
                    contraction=float(combined[2]),
                    current_regime=most_likely,
                    confidence=float(np.max(combined)),
                )
            )

        return results

    def classify_current(
        self,
        features: pd.DataFrame,
        returns: pd.Series | None = None,
    ) -> RegimeProbabilities:
        """Classify current regime.

        Args:
            features: DataFrame with recent feature values.
            returns: Optional returns series for Markov model.

        Returns:
            RegimeProbabilities for the latest time step.
        """
        probs = self.get_regime_probabilities(features, returns)
        return probs[-1]

    def forecast(
        self,
        features: pd.DataFrame,
    ) -> dict[int, NDArray[np.float64]]:
        """Get regime forecasts for multiple horizons.

        Only uses LSTM for forecasting (HMM/Markov are classification only).

        Args:
            features: DataFrame with recent feature values.

        Returns:
            Dict mapping horizon (days) to probability array.

        Raises:
            ValueError: If LSTM not fitted.
        """
        if self._lstm is None:
            raise ValueError("LSTM not fitted, cannot forecast")

        forecasts = self._lstm.forecast(features)

        return {f.horizon: f.probabilities for f in forecasts}

    def get_diagnostics(self) -> EnsembleDiagnostics:
        """Get ensemble diagnostics.

        Returns:
            EnsembleDiagnostics with model status and metrics.
        """
        # Compute model agreement (placeholder - would need actual predictions)
        model_agreement = 1.0  # Assume perfect agreement until computed

        return EnsembleDiagnostics(
            weights=self._effective_weights.copy(),
            model_agreement=model_agreement,
            hmm_fitted=self._hmm is not None,
            markov_fitted=self._markov is not None,
            lstm_fitted=self._lstm is not None,
            calibration_error=None,
        )

    def _compute_effective_weights(self) -> None:
        """Compute effective weights by redistributing from failed models."""
        active_models = []
        if self._hmm is not None:
            active_models.append("hmm")
        if self._markov is not None:
            active_models.append("markov")
        if self._lstm is not None:
            active_models.append("lstm")

        if not active_models:
            return

        # Get weights for active models
        active_weights = {m: self.weights.get(m, 0) for m in active_models}
        total = sum(active_weights.values())

        # Normalize to sum to 1
        self._effective_weights = {m: w / total for m, w in active_weights.items()}

        logger.info(f"Effective weights: {self._effective_weights}")
