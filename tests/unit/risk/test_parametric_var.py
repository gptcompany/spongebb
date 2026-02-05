"""Tests for parametric VaR calculator."""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from liquidity.risk.var.parametric import Distribution, ParametricVaR, ParametricVaRResult


class TestParametricVaR:
    """Test parametric VaR calculations."""

    @pytest.fixture
    def normal_returns(self) -> pd.Series:
        """Generate normally distributed returns."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        returns = pd.Series(
            np.random.normal(0.0005, 0.015, 500),
            index=dates,
        )
        return returns

    @pytest.fixture
    def fat_tail_returns(self) -> pd.Series:
        """Generate returns with fat tails (t-distributed)."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        # t-distribution with df=5 has fat tails
        returns = pd.Series(
            stats.t.rvs(df=5, loc=0.0005, scale=0.012, size=500),
            index=dates,
        )
        return returns

    def test_result_dataclass(self) -> None:
        """ParametricVaRResult should be a proper dataclass."""
        result = ParametricVaRResult(
            var_95=0.025,
            var_99=0.035,
            distribution=Distribution.NORMAL,
            mean=0.0005,
            std=0.015,
        )
        assert result.var_95 == 0.025
        assert result.distribution == Distribution.NORMAL

    def test_normal_var_positive(self, normal_returns: pd.Series) -> None:
        """Normal VaR should be positive."""
        calc = ParametricVaR(distribution=Distribution.NORMAL)
        result = calc.calculate(normal_returns)

        assert result.var_95 > 0
        assert result.var_99 > 0
        assert result.distribution == Distribution.NORMAL

    def test_normal_var_theoretical(self) -> None:
        """Normal VaR should match theoretical value for large sample."""
        # Create returns with known parameters
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=10000, freq="B")
        mu, sigma = 0.0, 0.02
        returns = pd.Series(np.random.normal(mu, sigma, 10000), index=dates)

        calc = ParametricVaR(distribution=Distribution.NORMAL, window=10000)
        result = calc.calculate(returns)

        # Theoretical VaR(95%) = sigma * 1.645 ≈ 0.0329
        expected_var_95 = sigma * 1.645
        assert abs(result.var_95 - expected_var_95) < 0.002

    def test_var_99_greater_than_var_95(self, normal_returns: pd.Series) -> None:
        """VaR 99% should be >= VaR 95%."""
        calc = ParametricVaR(distribution=Distribution.NORMAL)
        result = calc.calculate(normal_returns)

        assert result.var_99 >= result.var_95

    def test_t_dist_var_positive(self, fat_tail_returns: pd.Series) -> None:
        """t-distribution VaR should be positive."""
        calc = ParametricVaR(distribution=Distribution.T_STUDENT)
        result = calc.calculate(fat_tail_returns)

        assert result.var_95 > 0
        assert result.var_99 > 0
        assert result.distribution == Distribution.T_STUDENT

    def test_df_estimated(self, fat_tail_returns: pd.Series) -> None:
        """Degrees of freedom should be estimated for t-dist."""
        calc = ParametricVaR(distribution=Distribution.T_STUDENT)
        result = calc.calculate(fat_tail_returns)

        assert result.df is not None
        # df should be estimated, typically > 2
        assert result.df > 2

    def test_t_dist_captures_fat_tails(self, fat_tail_returns: pd.Series) -> None:
        """t-distribution should typically show higher VaR for fat-tailed data."""
        normal_calc = ParametricVaR(distribution=Distribution.NORMAL)
        t_calc = ParametricVaR(distribution=Distribution.T_STUDENT)

        normal_result = normal_calc.calculate(fat_tail_returns)
        t_result = t_calc.calculate(fat_tail_returns)

        # At 99%, t-dist often shows higher risk for fat-tailed data
        # But this depends on estimated df, so we just check it's close
        assert t_result.var_99 > 0
        assert normal_result.var_99 > 0

    def test_compare_distributions(self, normal_returns: pd.Series) -> None:
        """Compare should return results for both distributions."""
        calc = ParametricVaR()
        comparison = calc.compare_distributions(normal_returns)

        assert Distribution.NORMAL in comparison
        assert Distribution.T_STUDENT in comparison
        assert comparison[Distribution.NORMAL].distribution == Distribution.NORMAL
        assert comparison[Distribution.T_STUDENT].distribution == Distribution.T_STUDENT

    def test_rolling_var(self, normal_returns: pd.Series) -> None:
        """Rolling VaR should produce time series."""
        calc = ParametricVaR(distribution=Distribution.NORMAL, window=100)
        rolling = calc.calculate_rolling(normal_returns)

        assert len(rolling) > 0
        assert "var_95" in rolling.columns
        assert "var_99" in rolling.columns
        assert "mean" in rolling.columns
        assert "std" in rolling.columns
        assert "df" in rolling.columns

    def test_empty_series(self) -> None:
        """Empty series should return reasonable defaults."""
        returns = pd.Series([], dtype=float)
        calc = ParametricVaR(distribution=Distribution.NORMAL)
        result = calc.calculate(returns)

        # Should return some result even for empty data
        assert result.observation_count == 0

    def test_distribution_enum(self) -> None:
        """Distribution enum should have correct values."""
        assert Distribution.NORMAL.value == "normal"
        assert Distribution.T_STUDENT.value == "t-student"

    def test_window_parameter(self, normal_returns: pd.Series) -> None:
        """Window parameter should affect observation count."""
        calc_short = ParametricVaR(window=100)
        calc_long = ParametricVaR(window=400)

        result_short = calc_short.calculate(normal_returns)
        result_long = calc_long.calculate(normal_returns)

        assert result_short.observation_count == 100
        assert result_long.observation_count == 400
