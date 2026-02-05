"""Tests for historical VaR calculator."""

import numpy as np
import pandas as pd
import pytest

from liquidity.risk.var.historical import HistoricalVaR, VaRResult


class TestHistoricalVaR:
    """Test historical VaR calculations."""

    @pytest.fixture
    def sample_returns(self) -> pd.Series:
        """Generate sample returns."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        returns = pd.Series(
            np.random.normal(0.0005, 0.015, 500),
            index=dates,
            name="returns",
        )
        return returns

    def test_var_result_dataclass(self) -> None:
        """VaRResult should be a proper dataclass."""
        result = VaRResult(
            var_95=0.025,
            var_99=0.035,
            observation_count=252,
            window_days=252,
            as_of_date=pd.Timestamp("2024-01-01"),
        )
        assert result.var_95 == 0.025
        assert result.var_99 == 0.035

    def test_var_95_within_bounds(self, sample_returns: pd.Series) -> None:
        """VaR 95% should be reasonable for normal returns."""
        calculator = HistoricalVaR(window=252)
        result = calculator.calculate(sample_returns)

        # VaR 95% typically 1.5-4% for daily returns with std=1.5%
        assert 0.01 < result.var_95 < 0.05

    def test_var_99_greater_than_var_95(self, sample_returns: pd.Series) -> None:
        """VaR 99% should be >= VaR 95%."""
        calculator = HistoricalVaR(window=252)
        result = calculator.calculate(sample_returns)

        assert result.var_99 >= result.var_95

    def test_window_respected(self, sample_returns: pd.Series) -> None:
        """Window should limit observations."""
        calculator = HistoricalVaR(window=100)
        result = calculator.calculate(sample_returns)

        assert result.observation_count == 100
        assert result.window_days == 100

    def test_short_series(self) -> None:
        """Short series should use all available data."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=50, freq="B")
        returns = pd.Series(np.random.normal(0, 0.01, 50), index=dates)

        calculator = HistoricalVaR(window=252)
        result = calculator.calculate(returns)

        assert result.observation_count == 50

    def test_empty_series(self) -> None:
        """Empty series should return zeros."""
        returns = pd.Series([], dtype=float)
        calculator = HistoricalVaR(window=252)
        result = calculator.calculate(returns)

        assert result.var_95 == 0.0
        assert result.var_99 == 0.0
        assert result.observation_count == 0

    def test_as_of_date(self, sample_returns: pd.Series) -> None:
        """as_of should limit data to that date."""
        calculator = HistoricalVaR(window=252)
        as_of = pd.Timestamp("2020-06-01")
        result = calculator.calculate(sample_returns, as_of=as_of)

        # Should use data up to June 1, 2020
        assert result.as_of_date is not None
        assert result.as_of_date <= as_of

    def test_rolling_var(self, sample_returns: pd.Series) -> None:
        """Rolling VaR should produce time series."""
        calculator = HistoricalVaR(window=100)
        rolling = calculator.calculate_rolling(sample_returns)

        assert len(rolling) == len(sample_returns) - 100 + 1
        assert "var_95" in rolling.columns
        assert "var_99" in rolling.columns

    def test_rolling_var_monotonic_index(self, sample_returns: pd.Series) -> None:
        """Rolling VaR index should be sorted."""
        calculator = HistoricalVaR(window=100)
        rolling = calculator.calculate_rolling(sample_returns)

        assert rolling.index.is_monotonic_increasing

    def test_multi_asset(self) -> None:
        """Multi-asset VaR should work for all columns."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=300, freq="B")
        returns_df = pd.DataFrame(
            {
                "BTC": np.random.normal(0.001, 0.03, 300),
                "SPX": np.random.normal(0.0005, 0.012, 300),
                "GOLD": np.random.normal(0.0003, 0.008, 300),
            },
            index=dates,
        )

        calculator = HistoricalVaR(window=252)
        results = calculator.calculate_multi_asset(returns_df)

        assert "BTC" in results
        assert "SPX" in results
        assert "GOLD" in results

        # BTC should have higher VaR due to higher volatility
        assert results["BTC"].var_95 > results["SPX"].var_95
        assert results["SPX"].var_95 > results["GOLD"].var_95

    def test_nan_handling(self) -> None:
        """NaN values should be dropped."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=100, freq="B")
        returns = pd.Series(np.random.normal(0, 0.01, 100), index=dates)
        returns.iloc[10:20] = np.nan  # Add some NaNs

        calculator = HistoricalVaR(window=252)
        result = calculator.calculate(returns)

        assert result.observation_count == 90  # 100 - 10 NaNs

    def test_theoretical_var(self) -> None:
        """For known distribution, VaR should match theory."""
        # Generate large sample from known distribution
        np.random.seed(42)
        n = 50000
        sigma = 0.02
        dates = pd.date_range("2000-01-01", periods=n, freq="B")
        returns = pd.Series(np.random.normal(0, sigma, n), index=dates)

        calculator = HistoricalVaR(window=n)
        result = calculator.calculate(returns)

        # Theoretical VaR(95%) = sigma * 1.645 ≈ 0.0329
        expected_var_95 = sigma * 1.645
        assert abs(result.var_95 - expected_var_95) < 0.002
