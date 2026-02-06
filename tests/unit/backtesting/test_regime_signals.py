"""Tests for regime signal generator."""
from unittest.mock import Mock, PropertyMock, patch

import numpy as np
import pandas as pd
import pytest

from liquidity.backtesting.signals.regime_signals import (
    RegimeSignalGenerator,
    Signal,
    SignalType,
)
from liquidity.nowcasting.regime.hmm_classifier import RegimeProbabilities, RegimeState


class TestSignalType:
    """Test SignalType enum."""

    def test_signal_values(self):
        """Verify signal values."""
        assert SignalType.LONG.value == 1
        assert SignalType.SHORT.value == -1
        assert SignalType.FLAT.value == 0


class TestRegimeSignalGenerator:
    """Test regime signal generator."""

    @pytest.fixture
    def sample_liquidity(self) -> pd.DataFrame:
        """Create sample liquidity data."""
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100, freq='B')
        return pd.DataFrame({
            'net_liquidity': np.cumsum(np.random.normal(0, 0.01, 100)) + 100
        }, index=dates)

    def test_init_default_regimes(self):
        """Verify default regime mapping."""
        gen = RegimeSignalGenerator()
        assert gen.long_regime == RegimeState.EXPANSION
        assert gen.short_regime == RegimeState.CONTRACTION

    @patch.object(RegimeSignalGenerator, 'classifier', new_callable=PropertyMock)
    def test_generate_signals_returns_dataframe(self, mock_classifier_prop, sample_liquidity):
        """Generate signals should return DataFrame."""
        # Mock classifier
        mock_classifier = Mock()
        mock_classifier.is_fitted = True

        # Create mock RegimeProbabilities for each timestamp
        mock_probs = [
            RegimeProbabilities(
                timestamp=ts,
                expansion=0.8,
                neutral=0.1,
                contraction=0.1,
                current_regime=RegimeState.EXPANSION,
                confidence=0.8,
            )
            for ts in sample_liquidity.index
        ]
        mock_classifier.get_regime_probabilities.return_value = mock_probs
        mock_classifier_prop.return_value = mock_classifier

        gen = RegimeSignalGenerator()
        result = gen.generate_signals(sample_liquidity)

        assert isinstance(result, pd.DataFrame)
        assert 'signal' in result.columns
        assert 'strength' in result.columns
        assert len(result) == 100

    @patch.object(RegimeSignalGenerator, 'classifier', new_callable=PropertyMock)
    def test_expansion_generates_long(self, mock_classifier_prop, sample_liquidity):
        """EXPANSION regime should generate LONG signal."""
        mock_classifier = Mock()
        mock_classifier.is_fitted = True
        mock_probs = [
            RegimeProbabilities(
                timestamp=ts,
                expansion=0.8,
                neutral=0.1,
                contraction=0.1,
                current_regime=RegimeState.EXPANSION,
                confidence=0.8,
            )
            for ts in sample_liquidity.index
        ]
        mock_classifier.get_regime_probabilities.return_value = mock_probs
        mock_classifier_prop.return_value = mock_classifier

        gen = RegimeSignalGenerator()
        result = gen.generate_signals(sample_liquidity)

        assert all(result['signal'] == SignalType.LONG.value)

    @patch.object(RegimeSignalGenerator, 'classifier', new_callable=PropertyMock)
    def test_contraction_generates_short(self, mock_classifier_prop, sample_liquidity):
        """CONTRACTION regime should generate SHORT signal."""
        mock_classifier = Mock()
        mock_classifier.is_fitted = True
        mock_probs = [
            RegimeProbabilities(
                timestamp=ts,
                expansion=0.1,
                neutral=0.1,
                contraction=0.8,
                current_regime=RegimeState.CONTRACTION,
                confidence=0.8,
            )
            for ts in sample_liquidity.index
        ]
        mock_classifier.get_regime_probabilities.return_value = mock_probs
        mock_classifier_prop.return_value = mock_classifier

        gen = RegimeSignalGenerator()
        result = gen.generate_signals(sample_liquidity)

        assert all(result['signal'] == SignalType.SHORT.value)

    @patch.object(RegimeSignalGenerator, 'classifier', new_callable=PropertyMock)
    def test_low_confidence_generates_flat(self, mock_classifier_prop, sample_liquidity):
        """Low confidence should generate FLAT signal."""
        mock_classifier = Mock()
        mock_classifier.is_fitted = True
        mock_probs = [
            RegimeProbabilities(
                timestamp=ts,
                expansion=0.4,
                neutral=0.3,
                contraction=0.3,
                current_regime=RegimeState.EXPANSION,
                confidence=0.4,  # Low confidence
            )
            for ts in sample_liquidity.index
        ]
        mock_classifier.get_regime_probabilities.return_value = mock_probs
        mock_classifier_prop.return_value = mock_classifier

        gen = RegimeSignalGenerator(min_confidence=0.6)
        result = gen.generate_signals(sample_liquidity)

        assert all(result['signal'] == SignalType.FLAT.value)

    def test_momentum_signals_positive_trend(self, sample_liquidity):
        """Positive momentum should generate LONG."""
        # Create strong uptrend
        sample_liquidity['net_liquidity'] = np.linspace(100, 150, 100)

        gen = RegimeSignalGenerator()
        result = gen.generate_momentum_signals(sample_liquidity, lookback=10)

        # After lookback period, all signals should be LONG
        assert all(result['signal'].iloc[20:] == SignalType.LONG.value)

    def test_detect_regime_transitions(self):
        """Transition detection should find regime changes."""
        dates = pd.date_range('2024-01-01', periods=10, freq='B')
        signals = pd.DataFrame({
            'regime': [1, 1, 1, -1, -1, -1, 0, 0, 1, 1],
        }, index=dates)

        gen = RegimeSignalGenerator()
        transitions = gen.detect_regime_transitions(signals)

        # Should find 4 transitions: start, 1→-1, -1→0, 0→1
        assert len(transitions) == 4


class TestSignal:
    """Test Signal dataclass."""

    def test_signal_creation(self):
        """Verify signal creation."""
        signal = Signal(
            date=pd.Timestamp('2024-01-15'),
            signal_type=SignalType.LONG,
            strength=0.85,
            regime=RegimeState.EXPANSION,
        )
        assert signal.strength == 0.85
        assert signal.signal_type == SignalType.LONG
