from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from liquidity.nowcasting.regime.ensemble import RegimeEnsemble
from liquidity.nowcasting.regime.hmm_classifier import RegimeProbabilities, RegimeState


@pytest.fixture
def mock_probs():
    """Create a list of mock regime probabilities."""
    return [
        RegimeProbabilities(
            timestamp=pd.Timestamp("2026-01-01"),
            expansion=0.7,
            neutral=0.2,
            contraction=0.1,
            current_regime=RegimeState.EXPANSION,
            confidence=0.7
        )
    ]


@pytest.fixture
def mock_hmm():
    hmm = MagicMock()
    return hmm


@pytest.fixture
def mock_markov():
    markov = MagicMock()
    return markov


@pytest.fixture
def mock_lstm():
    lstm = MagicMock()
    return lstm


def test_init_weights_validation():
    """Test weights must sum to 1."""
    with pytest.raises(ValueError, match="Weights must sum to 1"):
        RegimeEnsemble(weights={"hmm": 0.5, "markov": 0.2})

    # Should work
    ens = RegimeEnsemble(weights={"hmm": 0.5, "markov": 0.5})
    assert ens.weights["hmm"] == 0.5


@patch("liquidity.nowcasting.regime.ensemble.HMMRegimeClassifier")
@patch("liquidity.nowcasting.regime.ensemble.MarkovSwitchingClassifier")
@patch("liquidity.nowcasting.regime.ensemble.LSTMRegimeForecaster")
def test_fit_all_success(mock_lstm_cls, mock_markov_cls, mock_hmm_cls):
    """Test fit when all models succeed."""
    ens = RegimeEnsemble()

    # Mock data
    features = pd.DataFrame({"A": [1, 2, 3]})
    returns = pd.Series([0.1, 0.2, 0.3])
    labels = pd.Series([RegimeState.EXPANSION] * 3)

    ens.fit(features, returns, labels)

    assert ens.is_fitted
    assert "hmm" in ens._effective_weights
    assert "markov" in ens._effective_weights
    assert "lstm" in ens._effective_weights

    # Original weights should be maintained since all fitted
    assert ens._effective_weights["hmm"] == ens.DEFAULT_WEIGHTS["hmm"]


@patch("liquidity.nowcasting.regime.ensemble.HMMRegimeClassifier")
@patch("liquidity.nowcasting.regime.ensemble.MarkovSwitchingClassifier")
@patch("liquidity.nowcasting.regime.ensemble.LSTMRegimeForecaster")
def test_fit_partial_failure(mock_lstm_cls, mock_markov_cls, mock_hmm_cls):
    """Test weight redistribution when a model fails to fit."""
    ens = RegimeEnsemble()

    # Make LSTM fail
    mock_lstm_cls.return_value.fit.side_effect = Exception("LSTM failed")

    features = pd.DataFrame({"A": [1, 2, 3]})
    returns = pd.Series([0.1, 0.2, 0.3])
    labels = pd.Series([RegimeState.EXPANSION] * 3)

    ens.fit(features, returns, labels)

    assert ens.is_fitted
    assert ens._lstm is None
    assert "lstm" not in ens._effective_weights

    # HMM (0.4) and Markov (0.3) remaining -> total = 0.7
    # New HMM weight = 0.4 / 0.7 = 0.571
    # New Markov weight = 0.3 / 0.7 = 0.428
    assert np.isclose(ens._effective_weights["hmm"], 0.4 / 0.7)
    assert np.isclose(ens._effective_weights["markov"], 0.3 / 0.7)


@patch("liquidity.nowcasting.regime.ensemble.HMMRegimeClassifier")
@patch("liquidity.nowcasting.regime.ensemble.MarkovSwitchingClassifier")
@patch("liquidity.nowcasting.regime.ensemble.LSTMRegimeForecaster")
def test_fit_all_failures(mock_lstm_cls, mock_markov_cls, mock_hmm_cls):
    """Test fit raises error if all models fail."""
    ens = RegimeEnsemble()

    mock_hmm_cls.side_effect = Exception("HMM failed")
    mock_markov_cls.side_effect = Exception("Markov failed")
    mock_lstm_cls.side_effect = Exception("LSTM failed")

    features = pd.DataFrame({"A": [1, 2, 3]})
    returns = pd.Series([0.1, 0.2, 0.3])

    with pytest.raises(ValueError, match="All models failed to fit"):
        ens.fit(features, returns)


def test_get_regime_probabilities(mock_hmm, mock_markov, mock_lstm, mock_probs):
    """Test combined probability calculation."""
    ens = RegimeEnsemble()
    ens._is_fitted = True
    ens._hmm = mock_hmm
    ens._markov = mock_markov
    ens._lstm = mock_lstm
    ens._effective_weights = {"hmm": 0.5, "markov": 0.5}  # Ignore LSTM for this test

    # Set up mock returns
    mock_hmm.get_regime_probabilities.return_value = [
        RegimeProbabilities(
            timestamp=pd.Timestamp("2026-01-01"),
            expansion=0.8, neutral=0.1, contraction=0.1,
            current_regime=RegimeState.EXPANSION, confidence=0.8
        )
    ]

    mock_markov.get_regime_probabilities.return_value = [
        RegimeProbabilities(
            timestamp=pd.Timestamp("2026-01-01"),
            expansion=0.2, neutral=0.7, contraction=0.1,
            current_regime=RegimeState.NEUTRAL, confidence=0.7
        )
    ]

    # Exclude LSTM
    ens._lstm = None

    probs = ens.get_regime_probabilities(pd.DataFrame(), pd.Series())

    assert len(probs) == 1
    # Combined expected: 0.5 * 0.8 + 0.5 * 0.2 = 0.5 expansion
    # 0.5 * 0.1 + 0.5 * 0.7 = 0.4 neutral
    # 0.5 * 0.1 + 0.5 * 0.1 = 0.1 contraction
    assert np.isclose(probs[0].expansion, 0.5)
    assert np.isclose(probs[0].neutral, 0.4)
    assert np.isclose(probs[0].contraction, 0.1)

    # Max is 0.5 -> EXPANSION
    assert probs[0].current_regime == RegimeState.EXPANSION


def test_forecast_delegation():
    """Test forecast delegates to LSTM."""
    ens = RegimeEnsemble()
    ens._is_fitted = True
    ens._lstm = MagicMock()

    mock_forecast = MagicMock()
    mock_forecast.horizon = 7
    mock_forecast.probabilities = np.array([0.5, 0.3, 0.2])

    ens._lstm.forecast.return_value = [mock_forecast]

    result = ens.forecast(pd.DataFrame())

    assert 7 in result
    np.testing.assert_array_equal(result[7], np.array([0.5, 0.3, 0.2]))
