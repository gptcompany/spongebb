"""Tests for CVaR / Expected Shortfall."""

import numpy as np
import pandas as pd
import pytest

from liquidity.risk.cvar import CVaRResult, ExpectedShortfall
from liquidity.risk.var.parametric import Distribution


class TestExpectedShortfall:
    """Test Expected Shortfall calculations."""

    @pytest.fixture
    def sample_returns(self) -> pd.Series:
        """Generate sample returns."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        return pd.Series(
            np.random.normal(0.0005, 0.015, 500),
            index=dates,
        )

    @pytest.fixture
    def fat_tail_returns(self) -> pd.Series:
        """Generate returns with more extreme tails."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        # Mix of normal and occasional large losses
        returns = np.random.normal(0.0005, 0.015, 500)
        # Add some extreme losses
        returns[np.random.choice(500, 20, replace=False)] = np.random.uniform(-0.08, -0.04, 20)
        return pd.Series(returns, index=dates)

    def test_result_dataclass(self) -> None:
        """CVaRResult should be a proper dataclass."""
        result = CVaRResult(
            cvar_95=0.035,
            cvar_99=0.050,
            var_95=0.025,
            var_99=0.040,
            tail_observations=25,
            method="historical",
        )
        assert result.cvar_95 == 0.035
        assert result.method == "historical"

    def test_cvar_greater_than_var(self, sample_returns: pd.Series) -> None:
        """CVaR should always be >= VaR."""
        es = ExpectedShortfall(window=252)
        result = es.calculate_historical(sample_returns)

        assert result.cvar_95 >= result.var_95
        assert result.cvar_99 >= result.var_99

    def test_cvar_99_greater_than_cvar_95(self, sample_returns: pd.Series) -> None:
        """CVaR 99% should be >= CVaR 95%."""
        es = ExpectedShortfall(window=252)
        result = es.calculate_historical(sample_returns)

        assert result.cvar_99 >= result.cvar_95

    def test_historical_cvar_positive(self, sample_returns: pd.Series) -> None:
        """Historical CVaR should be positive for normal returns."""
        es = ExpectedShortfall(window=252)
        result = es.calculate_historical(sample_returns)

        assert result.cvar_95 > 0
        assert result.cvar_99 > 0
        assert result.method == "historical"

    def test_parametric_normal_cvar(self, sample_returns: pd.Series) -> None:
        """Parametric normal CVaR should work."""
        es = ExpectedShortfall(window=252)
        result = es.calculate_parametric(sample_returns, Distribution.NORMAL)

        assert result.cvar_95 > 0
        assert result.cvar_99 > 0
        assert result.method == "parametric-normal"

    def test_parametric_t_cvar(self, sample_returns: pd.Series) -> None:
        """Parametric t-dist CVaR should work."""
        es = ExpectedShortfall(window=252)
        result = es.calculate_parametric(sample_returns, Distribution.T_STUDENT)

        assert result.cvar_95 > 0
        assert result.cvar_99 > 0
        assert result.method == "parametric-t-student"

    def test_cvar_var_ratio_reasonable(self, sample_returns: pd.Series) -> None:
        """CVaR/VaR ratio should be reasonable (typically 1.1-1.5)."""
        es = ExpectedShortfall(window=252)
        result = es.calculate_historical(sample_returns)

        if result.var_95 > 0:
            ratio_95 = result.cvar_95 / result.var_95
            assert 1.0 <= ratio_95 <= 2.0

        if result.var_99 > 0:
            ratio_99 = result.cvar_99 / result.var_99
            assert 1.0 <= ratio_99 <= 2.0

    def test_rolling_cvar(self, sample_returns: pd.Series) -> None:
        """Rolling CVaR should produce time series."""
        es = ExpectedShortfall(window=100)
        rolling = es.calculate_rolling(sample_returns)

        assert len(rolling) > 0
        assert "cvar_95" in rolling.columns
        assert "cvar_99" in rolling.columns
        assert "var_95" in rolling.columns
        assert "var_99" in rolling.columns

    def test_rolling_parametric(self, sample_returns: pd.Series) -> None:
        """Rolling parametric CVaR should work."""
        es = ExpectedShortfall(window=100)
        rolling = es.calculate_rolling(sample_returns, method="parametric")

        assert len(rolling) > 0
        assert "cvar_95" in rolling.columns

    def test_comparison_table(self, sample_returns: pd.Series) -> None:
        """Comparison table should have all methods."""
        es = ExpectedShortfall(window=252)
        comparison = es.compare_var_cvar(sample_returns)

        assert len(comparison) == 3
        assert "Historical" in comparison.index
        assert "Parametric-Normal" in comparison.index
        assert "Parametric-t" in comparison.index
        assert "VaR_95" in comparison.columns
        assert "CVaR_95" in comparison.columns
        assert "CVaR/VaR_99" in comparison.columns

    def test_comparison_cvar_var_ratios(self, sample_returns: pd.Series) -> None:
        """CVaR/VaR ratios should be >= 1."""
        es = ExpectedShortfall(window=252)
        comparison = es.compare_var_cvar(sample_returns)

        for ratio in comparison["CVaR/VaR_99"]:
            assert ratio >= 1.0

    def test_empty_series(self) -> None:
        """Empty series should return zeros."""
        returns = pd.Series([], dtype=float)
        es = ExpectedShortfall(window=252)
        result = es.calculate_historical(returns)

        assert result.cvar_95 == 0.0
        assert result.cvar_99 == 0.0
        assert result.tail_observations == 0

    def test_tail_observations(self, sample_returns: pd.Series) -> None:
        """Tail observations should be approximately 5% of window."""
        es = ExpectedShortfall(window=252)
        result = es.calculate_historical(sample_returns)

        # For 252 observations, tail at 95% should be ~12-13
        expected_tail = int(252 * 0.05)
        assert abs(result.tail_observations - expected_tail) <= 2

    def test_fat_tails_higher_cvar(self, fat_tail_returns: pd.Series) -> None:
        """Fat-tailed data should have higher CVaR/VaR ratio."""
        es = ExpectedShortfall(window=252)
        result = es.calculate_historical(fat_tail_returns)

        # With extreme losses, CVaR should be notably higher than VaR
        if result.var_99 > 0:
            ratio = result.cvar_99 / result.var_99
            # Ratio should be > 1 for fat tails
            assert ratio >= 1.0

    def test_theoretical_cvar_ratio(self) -> None:
        """For normal data, CVaR/VaR ratio should be ~1.22 at 95%."""
        np.random.seed(42)
        n = 50000
        dates = pd.date_range("2000-01-01", periods=n, freq="B")
        returns = pd.Series(np.random.normal(0, 0.02, n), index=dates)

        es = ExpectedShortfall(window=n)
        result = es.calculate_parametric(returns, Distribution.NORMAL)

        if result.var_95 > 0:
            ratio = result.cvar_95 / result.var_95
            # Theoretical ratio for normal at 95% is ~1.22
            assert 1.1 < ratio < 1.4
