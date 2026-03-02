from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import torch

from liquidity.nowcasting.regime.hmm_classifier import RegimeProbabilities, RegimeState
from liquidity.nowcasting.regime.lstm_forecaster import LSTMRegimeForecaster


@pytest.fixture
def mock_lstm_model():
    """Mock a trained PyTorch model to return specific probabilities."""
    model = MagicMock()
    # Mock forward pass to return constant logits: [10, -10, -10] (high probability for class 0)
    model.return_value = torch.tensor([[10.0, -10.0, -10.0]])
    model.eval = MagicMock()
    return model


@pytest.fixture
def forecaster(mock_lstm_model):
    """Return a mocked forecaster."""
    forecaster = LSTMRegimeForecaster(sequence_length=5)
    forecaster._is_fitted = True
    forecaster._input_size = 2
    forecaster._scalers = {"feat1": (0.0, 1.0), "feat2": (0.0, 1.0)}
    
    # Pre-populate with mock models for horizons
    forecaster._models = {
        7: mock_lstm_model,
        14: mock_lstm_model,
        30: mock_lstm_model
    }
    return forecaster


def test_init_device_selection():
    """Test device selection logic."""
    with patch("torch.cuda.is_available", return_value=False):
        f1 = LSTMRegimeForecaster()
        assert f1.device.type == "cpu"
        
    f2 = LSTMRegimeForecaster(device="cpu")
    assert f2.device.type == "cpu"


def test_fit_insufficient_data():
    """Test fit raises error with insufficient data."""
    f = LSTMRegimeForecaster(sequence_length=10)
    
    # Need at least sequence_length + max(HORIZONS) + 100 = 10 + 30 + 100 = 140
    df = pd.DataFrame({"feat1": np.random.randn(50)})
    labels = pd.Series([RegimeState.EXPANSION] * 50)
    
    with pytest.raises(ValueError, match="Insufficient data: need at least 140 samples"):
        f.fit(df, labels)


@patch("liquidity.nowcasting.regime.lstm_forecaster.LSTMRegimeForecaster._train_model")
def test_fit_mocked_training(mock_train_model):
    """Test fit method with mocked internal training."""
    f = LSTMRegimeForecaster(sequence_length=10, epochs=1, batch_size=2)
    f.HORIZONS = [7]  # Override for faster test
    
    # Create minimum viable data (10 + 7 + 100 = 117 rows)
    n_samples = 120
    df = pd.DataFrame({
        "feat1": np.random.randn(n_samples),
        "feat2": np.random.randn(n_samples)
    })
    labels = pd.Series([RegimeState.EXPANSION] * n_samples)
    
    # Mock _train_model to return a dummy model and diagnostics
    mock_model = MagicMock()
    mock_diag = MagicMock()
    mock_train_model.return_value = (mock_model, mock_diag)
    
    f.fit(df, labels)
    
    assert f.is_fitted
    assert 7 in f._models
    assert "feat1" in f._scalers
    mock_train_model.assert_called_once()


def test_forecast_not_fitted():
    """Test forecast raises error if not fitted."""
    f = LSTMRegimeForecaster()
    with pytest.raises(ValueError, match="Model not fitted"):
        f.forecast(pd.DataFrame())


def test_forecast_insufficient_sequence(forecaster):
    """Test forecast raises error if sequence length is too short."""
    # Sequence length is 5
    df = pd.DataFrame({"feat1": [1, 2, 3], "feat2": [1, 2, 3]})
    with pytest.raises(ValueError, match="Need at least 5 rows"):
        forecaster.forecast(df)


def test_forecast_success(forecaster):
    """Test successful forecast generation."""
    # Provide 5 rows of data
    df = pd.DataFrame({
        "feat1": [1, 2, 3, 4, 5],
        "feat2": [1, 2, 3, 4, 5]
    })
    
    forecasts = forecaster.forecast(df)
    
    # Models are available for 7, 14, 30
    assert len(forecasts) == 3
    
    f7 = forecasts[0]
    assert f7.horizon == 7
    # Based on the mock model logits [10, -10, -10], class 0 should have ~1.0 prob
    assert f7.predicted_regime == RegimeState.EXPANSION
    assert f7.confidence > 0.99


def test_get_regime_probabilities(forecaster):
    """Test regime probabilities generation for ensemble compatibility."""
    df = pd.DataFrame({
        "feat1": [1, 2, 3, 4, 5, 6],
        "feat2": [1, 2, 3, 4, 5, 6]
    }, index=pd.date_range("2026-01-01", periods=6))
    
    # Sequence length is 5, total 6 rows. Expect 1 result (for the last row)
    # Actually, the loop goes from i=sequence_length to len(features)
    # range(5, 6) -> 1 iteration
    probs = forecaster.get_regime_probabilities(df, horizon=7)
    
    assert len(probs) == 1
    assert isinstance(probs[0], RegimeProbabilities)
    assert probs[0].current_regime == RegimeState.EXPANSION
    assert probs[0].expansion > 0.99
