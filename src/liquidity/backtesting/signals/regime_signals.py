"""Regime-based signal generator."""
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from liquidity.nowcasting.regime.hmm_classifier import HMMRegimeClassifier, RegimeState


class SignalType(Enum):
    """Signal type enumeration."""
    LONG = 1
    SHORT = -1
    FLAT = 0


@dataclass
class Signal:
    """Trading signal with metadata."""
    date: pd.Timestamp
    signal_type: SignalType
    strength: float  # 0-1, confidence in signal
    regime: RegimeState
    holding_period: int | None = None  # Suggested days to hold


class RegimeSignalGenerator:
    """Generate trading signals based on liquidity regime.

    Signal Logic:
    - EXPANSION regime → LONG (risk-on)
    - CONTRACTION regime → SHORT (risk-off)
    - NEUTRAL → FLAT (no position)

    Strength is based on:
    - HMM state probability
    - Regime duration (longer = stronger)
    - Liquidity trend direction
    """

    def __init__(
        self,
        long_regime: RegimeState = RegimeState.EXPANSION,
        short_regime: RegimeState = RegimeState.CONTRACTION,
        neutral_regime: RegimeState = RegimeState.NEUTRAL,
        min_confidence: float = 0.6,
    ):
        """Initialize generator.

        Args:
            long_regime: Regime that triggers long signal
            short_regime: Regime that triggers short signal
            neutral_regime: Regime that triggers flat signal
            min_confidence: Minimum HMM probability to generate signal
        """
        self.long_regime = long_regime
        self.short_regime = short_regime
        self.neutral_regime = neutral_regime
        self.min_confidence = min_confidence
        self._classifier: HMMRegimeClassifier | None = None

    @property
    def classifier(self) -> HMMRegimeClassifier:
        """Lazy-load classifier."""
        if self._classifier is None:
            self._classifier = HMMRegimeClassifier()
        return self._classifier

    def generate_signals(
        self,
        liquidity_data: pd.DataFrame,
        use_smoothed: bool = True,  # noqa: ARG002
    ) -> pd.DataFrame:
        """Generate signals from liquidity data.

        Args:
            liquidity_data: DataFrame with net_liquidity column
            use_smoothed: If True, use smoothed HMM states (reduces noise)

        Returns:
            DataFrame with signal, strength, regime columns
        """
        # Fit classifier if needed
        if not self.classifier.is_fitted:
            self.classifier.fit(liquidity_data[['net_liquidity']])

        # Get regime probabilities for each timestamp
        regime_probs = self.classifier.get_regime_probabilities(
            liquidity_data[['net_liquidity']]
        )

        # Generate signals
        signals = []
        strengths = []
        regimes = []

        for prob in regime_probs:
            max_prob = prob.confidence

            if max_prob < self.min_confidence:
                signal = SignalType.FLAT
                strength = 0.0
            elif prob.current_regime == self.long_regime:
                signal = SignalType.LONG
                strength = max_prob
            elif prob.current_regime == self.short_regime:
                signal = SignalType.SHORT
                strength = max_prob
            else:
                signal = SignalType.FLAT
                strength = 0.0

            signals.append(signal.value)
            strengths.append(strength)
            regimes.append(prob.current_regime.value)

        result = pd.DataFrame({
            'signal': signals,
            'strength': strengths,
            'regime': regimes,
        }, index=liquidity_data.index)

        return result

    def generate_momentum_signals(
        self,
        liquidity_data: pd.DataFrame,
        lookback: int = 20,
    ) -> pd.DataFrame:
        """Generate momentum-based signals.

        Long when liquidity trending up, short when trending down.

        Args:
            liquidity_data: DataFrame with net_liquidity column
            lookback: Days for momentum calculation

        Returns:
            DataFrame with signal, strength columns
        """
        liq = liquidity_data['net_liquidity']

        # Calculate momentum (% change over lookback)
        momentum = liq.pct_change(lookback)

        # Normalize to [-1, 1] for signal strength
        momentum_norm = momentum / momentum.abs().rolling(252).max()

        signals = np.where(momentum > 0, SignalType.LONG.value,
                   np.where(momentum < 0, SignalType.SHORT.value, SignalType.FLAT.value))

        result = pd.DataFrame({
            'signal': signals,
            'strength': momentum_norm.abs().fillna(0),
            'momentum': momentum,
        }, index=liquidity_data.index)

        return result

    def combine_signals(
        self,
        regime_signals: pd.DataFrame,
        momentum_signals: pd.DataFrame,
        regime_weight: float = 0.7,
    ) -> pd.DataFrame:
        """Combine regime and momentum signals.

        Args:
            regime_signals: Output of generate_signals()
            momentum_signals: Output of generate_momentum_signals()
            regime_weight: Weight for regime signal (0-1)

        Returns:
            Combined signal DataFrame
        """
        mom_weight = 1 - regime_weight

        # Weighted combination
        combined = (
            regime_signals['signal'] * regime_signals['strength'] * regime_weight +
            momentum_signals['signal'] * momentum_signals['strength'] * mom_weight
        )

        # Discretize to -1, 0, 1
        final_signal = np.sign(combined)
        final_strength = combined.abs()

        return pd.DataFrame({
            'signal': final_signal,
            'strength': final_strength,
            'regime_component': regime_signals['signal'],
            'momentum_component': momentum_signals['signal'],
        }, index=regime_signals.index)

    def detect_regime_transitions(
        self,
        signals: pd.DataFrame,
    ) -> pd.DataFrame:
        """Detect regime transition points.

        Useful for transition analysis.

        Args:
            signals: DataFrame with regime column

        Returns:
            DataFrame with transition dates and types
        """
        regime = signals['regime'] if 'regime' in signals.columns else signals['signal']

        transitions = regime != regime.shift(1)
        transition_dates = signals.index[transitions]

        transitions_df = pd.DataFrame({
            'date': transition_dates,
            'from_regime': regime.shift(1)[transitions].values,
            'to_regime': regime[transitions].values,
        })

        return transitions_df
