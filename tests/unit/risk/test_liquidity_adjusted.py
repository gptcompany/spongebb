"""Tests for Liquidity-Adjusted Risk Metrics."""

import numpy as np
import pandas as pd
import pytest

from liquidity.risk.liquidity_adjusted import (
    DEFAULT_LIQUIDITY_PARAMS,
    LAVaRResult,
    LiquidityAdjustedRisk,
    LiquidityParams,
)


class TestLiquidityParams:
    """Test LiquidityParams dataclass."""

    def test_default_values(self) -> None:
        """Default values should be reasonable."""
        params = LiquidityParams()
        assert params.spread_bps == 10.0
        assert params.avg_daily_volume == 1e6
        assert params.position_size == 10000
        assert params.liquidation_days == 1

    def test_custom_values(self) -> None:
        """Custom values should be set correctly."""
        params = LiquidityParams(
            spread_bps=20,
            avg_daily_volume=5e6,
            position_size=50000,
            liquidation_days=3,
        )
        assert params.spread_bps == 20
        assert params.liquidation_days == 3


class TestLiquidityAdjustedRisk:
    """Test LAVaR calculations."""

    @pytest.fixture
    def sample_returns(self) -> pd.Series:
        """Generate sample returns."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        return pd.Series(
            np.random.normal(0.0005, 0.02, 500),
            index=dates,
        )

    @pytest.fixture
    def default_params(self) -> LiquidityParams:
        """Default liquidity parameters."""
        return LiquidityParams(
            spread_bps=10,
            avg_daily_volume=1e6,
            position_size=10000,
            liquidation_days=1,
        )

    def test_lavar_greater_than_var(
        self, sample_returns: pd.Series, default_params: LiquidityParams
    ) -> None:
        """LAVaR should always be >= base VaR."""
        calc = LiquidityAdjustedRisk()
        result = calc.calculate(sample_returns, default_params)

        assert result.lavar_95 >= result.base_var_95
        assert result.lavar_99 >= result.base_var_99

    def test_spread_cost_calculation(self) -> None:
        """Spread cost should be half the spread."""
        calc = LiquidityAdjustedRisk()
        params = LiquidityParams(spread_bps=20)

        cost = calc.estimate_spread_cost(params)
        assert abs(cost - 0.001) < 0.0001  # 20 bps / 2 = 10 bps = 0.001

    def test_market_impact_increases_with_position(self, sample_returns: pd.Series) -> None:
        """Larger position should have higher market impact."""
        calc = LiquidityAdjustedRisk()

        small_params = LiquidityParams(position_size=1000, avg_daily_volume=1e6)
        large_params = LiquidityParams(position_size=100000, avg_daily_volume=1e6)

        small_result = calc.calculate(sample_returns, small_params)
        large_result = calc.calculate(sample_returns, large_params)

        assert large_result.market_impact > small_result.market_impact

    def test_market_impact_zero_volume(self, sample_returns: pd.Series) -> None:
        """Zero volume should not cause division error."""
        calc = LiquidityAdjustedRisk()
        params = LiquidityParams(avg_daily_volume=0)

        result = calc.calculate(sample_returns, params)
        assert result.market_impact == 0.0

    def test_liquidation_time_adjustment(self, sample_returns: pd.Series) -> None:
        """Longer liquidation should increase LAVaR."""
        calc = LiquidityAdjustedRisk()

        short_params = LiquidityParams(liquidation_days=1)
        long_params = LiquidityParams(liquidation_days=5)

        short_result = calc.calculate(sample_returns, short_params)
        long_result = calc.calculate(sample_returns, long_params)

        assert long_result.lavar_95 > short_result.lavar_95

    def test_no_liquidation_adjustment_for_one_day(
        self, sample_returns: pd.Series, default_params: LiquidityParams
    ) -> None:
        """No adjustment for single day liquidation."""
        calc = LiquidityAdjustedRisk()
        result = calc.calculate(sample_returns, default_params)

        assert result.liquidation_adjustment == 0.0

    def test_stress_scenarios(
        self, sample_returns: pd.Series, default_params: LiquidityParams
    ) -> None:
        """Stress scenarios should show increasing LAVaR."""
        calc = LiquidityAdjustedRisk()
        scenarios = calc.calculate_stress(sample_returns, default_params)

        assert "normal" in scenarios
        assert "moderate_stress" in scenarios
        assert "severe_stress" in scenarios
        assert "crisis" in scenarios

        # LAVaR should increase with stress level
        assert scenarios["crisis"].lavar_95 > scenarios["severe_stress"].lavar_95
        assert scenarios["severe_stress"].lavar_95 > scenarios["moderate_stress"].lavar_95
        assert scenarios["moderate_stress"].lavar_95 > scenarios["normal"].lavar_95

    def test_multi_asset(self) -> None:
        """Multi-asset LAVaR should work."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=300, freq="B")
        returns_df = pd.DataFrame(
            {
                "BTC": np.random.normal(0.001, 0.03, 300),
                "SPY": np.random.normal(0.0005, 0.012, 300),
            },
            index=dates,
        )

        calc = LiquidityAdjustedRisk()
        results = calc.calculate_multi_asset(returns_df, DEFAULT_LIQUIDITY_PARAMS)

        assert "BTC" in results
        assert "SPY" in results

    def test_multi_asset_missing_params(self) -> None:
        """Assets without params should use defaults."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=300, freq="B")
        returns_df = pd.DataFrame(
            {
                "UNKNOWN_ASSET": np.random.normal(0.0005, 0.015, 300),
            },
            index=dates,
        )

        calc = LiquidityAdjustedRisk()
        results = calc.calculate_multi_asset(returns_df, {})

        assert "UNKNOWN_ASSET" in results

    def test_default_params_exist(self) -> None:
        """Default params should be defined for common assets."""
        assert "BTC" in DEFAULT_LIQUIDITY_PARAMS
        assert "SPY" in DEFAULT_LIQUIDITY_PARAMS
        assert "GLD" in DEFAULT_LIQUIDITY_PARAMS
        assert "TLT" in DEFAULT_LIQUIDITY_PARAMS
        assert "HYG" in DEFAULT_LIQUIDITY_PARAMS

    def test_result_contains_params(
        self, sample_returns: pd.Series, default_params: LiquidityParams
    ) -> None:
        """Result should contain the params used."""
        calc = LiquidityAdjustedRisk()
        result = calc.calculate(sample_returns, default_params)

        assert result.params.spread_bps == default_params.spread_bps
