"""Tests for Regime-Conditional VaR."""

import numpy as np
import pandas as pd
import pytest

from liquidity.risk.regime_var import (
    REGIME_RISK_MULTIPLIERS,
    RegimeConditionalVaR,
    RegimeType,
    RegimeVaRResult,
    WeightedVaRResult,
)


class TestRegimeType:
    """Test RegimeType enum."""

    def test_enum_values(self) -> None:
        """Enum should have correct values."""
        assert RegimeType.EXPANSION.value == "EXPANSION"
        assert RegimeType.NEUTRAL.value == "NEUTRAL"
        assert RegimeType.CONTRACTION.value == "CONTRACTION"

    def test_risk_multipliers_exist(self) -> None:
        """Risk multipliers should exist for all regimes."""
        for regime in RegimeType:
            assert regime in REGIME_RISK_MULTIPLIERS


class TestRegimeConditionalVaR:
    """Test regime-conditional VaR."""

    @pytest.fixture
    def sample_data(self) -> tuple[pd.Series, pd.Series]:
        """Generate sample returns with regime labels."""
        np.random.seed(42)
        n = 500
        dates = pd.date_range("2020-01-01", periods=n, freq="B")

        # Assign regimes with different probabilities
        regimes = np.random.choice(
            ["EXPANSION", "NEUTRAL", "CONTRACTION"],
            size=n,
            p=[0.4, 0.35, 0.25],
        )

        # Different volatility by regime
        returns = []
        for regime in regimes:
            if regime == "EXPANSION":
                returns.append(np.random.normal(0.001, 0.01))  # Low vol
            elif regime == "NEUTRAL":
                returns.append(np.random.normal(0.0005, 0.015))
            else:
                returns.append(np.random.normal(-0.0005, 0.025))  # High vol

        return (
            pd.Series(returns, index=dates),
            pd.Series(regimes, index=dates),
        )

    def test_segment_by_regime(self, sample_data: tuple[pd.Series, pd.Series]) -> None:
        """Should segment returns correctly."""
        returns, regimes = sample_data
        calc = RegimeConditionalVaR()
        segments = calc.segment_by_regime(returns, regimes)

        assert len(segments) > 0
        for regime, regime_returns in segments.items():
            assert len(regime_returns) >= 30  # min_observations

    def test_calculate_by_regime(self, sample_data: tuple[pd.Series, pd.Series]) -> None:
        """Should calculate VaR for each regime."""
        returns, regimes = sample_data
        calc = RegimeConditionalVaR()
        results = calc.calculate_by_regime(returns, regimes)

        assert len(results) > 0
        for regime, result in results.items():
            assert isinstance(result, RegimeVaRResult)
            assert result.var_95 > 0
            assert result.cvar_95 >= result.var_95

    def test_contraction_higher_var(self, sample_data: tuple[pd.Series, pd.Series]) -> None:
        """Contraction should have higher VaR due to higher volatility."""
        returns, regimes = sample_data
        calc = RegimeConditionalVaR()
        results = calc.calculate_by_regime(returns, regimes)

        if RegimeType.EXPANSION in results and RegimeType.CONTRACTION in results:
            assert (
                results[RegimeType.CONTRACTION].var_95 > results[RegimeType.EXPANSION].var_95
            )

    def test_weighted_var(self, sample_data: tuple[pd.Series, pd.Series]) -> None:
        """Weighted VaR should combine regimes."""
        returns, regimes = sample_data
        calc = RegimeConditionalVaR()
        result = calc.calculate_weighted(returns, regimes)

        assert isinstance(result, WeightedVaRResult)
        assert result.weighted_var_95 > 0
        assert result.weighted_cvar_95 >= result.weighted_var_95

    def test_weighted_var_with_custom_probs(
        self, sample_data: tuple[pd.Series, pd.Series]
    ) -> None:
        """Should use custom probabilities when provided."""
        returns, regimes = sample_data
        calc = RegimeConditionalVaR()

        custom_probs = {
            RegimeType.EXPANSION: 0.1,
            RegimeType.NEUTRAL: 0.1,
            RegimeType.CONTRACTION: 0.8,
        }

        result = calc.calculate_weighted(
            returns, regimes, regime_probabilities=custom_probs
        )

        # With high contraction probability, weighted VaR should be higher
        assert result.weighted_var_95 > 0

    def test_regime_probabilities_sum_to_one(
        self, sample_data: tuple[pd.Series, pd.Series]
    ) -> None:
        """Regime probabilities should be normalized."""
        returns, regimes = sample_data
        calc = RegimeConditionalVaR()
        results = calc.calculate_by_regime(returns, regimes)

        total_prob = sum(r.regime_probability for r in results.values())
        assert abs(total_prob - 1.0) < 0.01

    def test_min_observations_filter(self) -> None:
        """Regimes with few observations should be filtered out."""
        np.random.seed(42)
        n = 100
        dates = pd.date_range("2020-01-01", periods=n, freq="B")

        # Most observations in EXPANSION, few in CONTRACTION
        regimes = ["EXPANSION"] * 90 + ["CONTRACTION"] * 10
        np.random.shuffle(regimes)

        returns = pd.Series(np.random.normal(0, 0.01, n), index=dates)
        regime_series = pd.Series(regimes, index=dates)

        calc = RegimeConditionalVaR(min_observations=30)
        segments = calc.segment_by_regime(returns, regime_series)

        # CONTRACTION should be filtered out (only 10 obs < 30 min)
        assert RegimeType.EXPANSION in segments
        assert RegimeType.CONTRACTION not in segments

    def test_current_regime_detection(
        self, sample_data: tuple[pd.Series, pd.Series]
    ) -> None:
        """Should detect current regime from max probability."""
        returns, regimes = sample_data
        calc = RegimeConditionalVaR()

        result = calc.calculate_weighted(returns, regimes)

        assert result.current_regime in RegimeType
        assert 0 <= result.current_probability <= 1


class TestRegimeRiskMultipliers:
    """Test regime risk multipliers."""

    def test_expansion_lowest(self) -> None:
        """Expansion should have lowest multiplier."""
        assert REGIME_RISK_MULTIPLIERS[RegimeType.EXPANSION] < 1.0

    def test_contraction_highest(self) -> None:
        """Contraction should have highest multiplier."""
        assert REGIME_RISK_MULTIPLIERS[RegimeType.CONTRACTION] > 1.0

    def test_neutral_is_one(self) -> None:
        """Neutral should be exactly 1.0."""
        assert REGIME_RISK_MULTIPLIERS[RegimeType.NEUTRAL] == 1.0
