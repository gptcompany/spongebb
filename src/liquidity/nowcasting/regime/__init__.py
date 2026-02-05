"""Regime classification module using probabilistic models.

This module provides regime detection using Hidden Markov Models (HMM) and other
probabilistic approaches for classifying liquidity regimes.

Key components:
- HMMRegimeClassifier: GaussianHMM-based regime classifier with 3 states
- RegimeState: Enum for regime states (EXPANSION, NEUTRAL, CONTRACTION)
- RegimeProbabilities: Dataclass for regime probability outputs
- HMMDiagnostics: Dataclass for model diagnostics

Example:
    from liquidity.nowcasting.regime import HMMRegimeClassifier, RegimeState

    # Fit model on historical features
    classifier = HMMRegimeClassifier(n_states=3)
    classifier.fit(features_df)

    # Get current regime
    current = classifier.classify_current(features_df)
    print(f"Regime: {current.current_regime.name}")
    print(f"Confidence: {current.confidence:.1%}")

    # Get full probability sequence
    probs = classifier.get_regime_probabilities(features_df)
"""

from liquidity.nowcasting.regime.ensemble import (
    EnsembleDiagnostics,
    EnsembleMode,
    RegimeEnsemble,
)
from liquidity.nowcasting.regime.hmm_classifier import (
    HMMDiagnostics,
    HMMRegimeClassifier,
    RegimeProbabilities,
    RegimeState,
)
from liquidity.nowcasting.regime.lstm_forecaster import (
    LSTMDiagnostics,
    LSTMForecast,
    LSTMRegimeForecaster,
)
from liquidity.nowcasting.regime.markov_switching import (
    MarkovSwitchingClassifier,
    MarkovSwitchingDiagnostics,
)

__all__ = [
    # Ensemble
    "EnsembleDiagnostics",
    "EnsembleMode",
    "RegimeEnsemble",
    # HMM
    "HMMDiagnostics",
    "HMMRegimeClassifier",
    # LSTM
    "LSTMDiagnostics",
    "LSTMForecast",
    "LSTMRegimeForecaster",
    # Markov Switching
    "MarkovSwitchingClassifier",
    "MarkovSwitchingDiagnostics",
    # Common
    "RegimeProbabilities",
    "RegimeState",
]
