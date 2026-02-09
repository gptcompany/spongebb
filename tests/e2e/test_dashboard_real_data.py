"""E2E tests verifying real data availability for the dashboard.

These tests ensure all data sources are accessible and return valid data.
No mock data should be used — if a source is unavailable, the test fails.

Run with: uv run pytest tests/e2e/ -v
"""

import os

import pytest

# Skip all e2e tests if FRED API key not configured
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not os.environ.get("LIQUIDITY_FRED_API_KEY"),
        reason="LIQUIDITY_FRED_API_KEY not set",
    ),
]


class TestNetLiquidityRealData:
    """Verify Net Liquidity calculator returns real data with all deltas."""

    @pytest.mark.asyncio
    async def test_net_liquidity_calculates(self) -> None:
        """Net Liquidity calculator runs and returns all fields."""
        from liquidity.calculators.net_liquidity import NetLiquidityCalculator
        from liquidity.config import configure_openbb_credentials

        assert configure_openbb_credentials(), "OpenBB credentials must be configured"

        calc = NetLiquidityCalculator()
        result = await calc.get_current()

        # Must have all delta fields
        assert hasattr(result, "net_liquidity")
        assert hasattr(result, "weekly_delta")
        assert hasattr(result, "monthly_delta")
        assert hasattr(result, "delta_60d")
        assert hasattr(result, "delta_90d")

        # Net liquidity should be in plausible range (trillions USD)
        assert 3_000 < result.net_liquidity < 10_000, (
            f"Net liquidity {result.net_liquidity}B out of plausible range"
        )

    @pytest.mark.asyncio
    async def test_net_liquidity_time_series(self) -> None:
        """Net Liquidity calculator returns time series DataFrame."""
        from liquidity.calculators.net_liquidity import NetLiquidityCalculator
        from liquidity.config import configure_openbb_credentials

        configure_openbb_credentials()

        calc = NetLiquidityCalculator()
        df = await calc.calculate()

        assert not df.empty, "Time series should not be empty"
        assert "net_liquidity" in df.columns
        assert len(df) >= 30, "Need at least 30 days of data"


class TestGlobalLiquidityRealData:
    """Verify Global Liquidity calculator returns real data."""

    @pytest.mark.asyncio
    async def test_global_liquidity_calculates(self) -> None:
        """Global Liquidity calculator runs and returns all fields."""
        from liquidity.calculators.global_liquidity import GlobalLiquidityCalculator
        from liquidity.config import configure_openbb_credentials

        assert configure_openbb_credentials(), "OpenBB credentials must be configured"

        calc = GlobalLiquidityCalculator()
        result = await calc.get_current()

        assert hasattr(result, "total_usd")
        assert hasattr(result, "weekly_delta")
        assert hasattr(result, "delta_30d")
        assert hasattr(result, "delta_60d")
        assert hasattr(result, "delta_90d")

        # Global liquidity should be > $15 trillion
        assert result.total_usd > 15_000, (
            f"Global liquidity {result.total_usd}B unexpectedly low"
        )


class TestFXCollectorRealData:
    """Verify FX data source works."""

    @pytest.mark.asyncio
    async def test_dxy_data(self) -> None:
        """DXY index data is available."""
        from liquidity.collectors.fx import FXCollector

        collector = FXCollector()
        df = await collector.collect_dxy(period="7d")

        assert not df.empty, "DXY data should not be empty"
        assert "value" in df.columns

        latest = df["value"].iloc[-1]
        assert 80 < latest < 130, f"DXY {latest} out of plausible range"

    @pytest.mark.asyncio
    async def test_fx_pairs(self) -> None:
        """Major FX pairs data is available."""
        from liquidity.collectors.fx import FXCollector

        collector = FXCollector()
        df = await collector.collect_pairs(period="5d")

        assert not df.empty, "FX pairs data should not be empty"
        expected_pairs = {"EURUSD=X", "USDJPY=X", "USDCNY=X"}
        actual_pairs = set(df["series_id"].unique())
        assert expected_pairs.issubset(actual_pairs), (
            f"Missing pairs: {expected_pairs - actual_pairs}"
        )


class TestCommodityCollectorRealData:
    """Verify commodity data source works."""

    @pytest.mark.asyncio
    async def test_commodities_data(self) -> None:
        """Gold, copper, and oil data are available."""
        from liquidity.collectors.commodities import CommodityCollector

        collector = CommodityCollector()
        df = await collector.collect_all(period="7d")

        assert not df.empty, "Commodity data should not be empty"

        # Verify key series exist
        series_ids = set(df["series_id"].unique())
        assert "GC=F" in series_ids, "Gold (GC=F) data missing"
        assert "HG=F" in series_ids, "Copper (HG=F) data missing"
        assert "CL=F" in series_ids, "WTI Oil (CL=F) data missing"

        # Sanity check gold price
        gold_df = df[df["series_id"] == "GC=F"]
        gold_price = gold_df["value"].iloc[-1]
        assert 1000 < gold_price < 10000, f"Gold price ${gold_price} implausible"


class TestRegimeClassifierRealData:
    """Verify regime classifier works with real data."""

    @pytest.mark.asyncio
    async def test_regime_classification(self) -> None:
        """Regime classifier runs and returns valid result."""
        from liquidity.analyzers.regime_classifier import RegimeClassifier
        from liquidity.config import configure_openbb_credentials

        assert configure_openbb_credentials(), "OpenBB credentials must be configured"

        classifier = RegimeClassifier()
        result = await classifier.classify()

        assert result.direction is not None
        assert 0 <= result.intensity <= 100
        assert result.confidence in {"LOW", "MEDIUM", "HIGH"}


class TestCorrelationEngineRealData:
    """Verify correlation engine works with real data."""

    @pytest.mark.asyncio
    async def test_asset_correlations(self) -> None:
        """Correlation engine computes real correlations."""
        from liquidity.analyzers.correlation_engine import CorrelationEngine

        engine = CorrelationEngine()
        prices = await engine._fetch_asset_prices()

        assert not prices.empty, "Asset prices should not be empty"

        returns = engine._calculate_returns(prices)
        matrix = engine.calculate_correlation_matrix(returns)

        assert matrix.correlations is not None
        assert not matrix.correlations.empty
        # Diagonal should be 1.0 (self-correlation)
        for asset in matrix.correlations.columns:
            assert abs(matrix.correlations.loc[asset, asset] - 1.0) < 0.01


class TestDashboardDataPipelineE2E:
    """End-to-end test: full dashboard data fetch returns real data."""

    @pytest.mark.asyncio
    async def test_main_dashboard_data(self) -> None:
        """Full dashboard data pipeline returns real data (no mock)."""
        from liquidity.config import configure_openbb_credentials
        from liquidity.dashboard.callbacks_main import _fetch_data_async

        assert configure_openbb_credentials(), "OpenBB credentials must be configured"

        data = await _fetch_data_async()

        # Verify structure
        assert "net_liquidity_df" in data
        assert "global_liquidity_df" in data
        assert "regime" in data
        assert "net_metrics" in data
        assert "global_metrics" in data

        # Verify net metrics have all deltas
        net = data["net_metrics"]
        assert "current" in net
        assert "weekly_delta" in net
        assert "monthly_delta" in net
        assert "delta_60d" in net
        assert "delta_90d" in net

        # Verify global metrics have all deltas
        glb = data["global_metrics"]
        assert "current" in glb
        assert "weekly_delta" in glb
        assert "monthly_delta" in glb
        assert "delta_60d" in glb
        assert "delta_90d" in glb

        # Verify DataFrames are non-empty
        assert not data["net_liquidity_df"].empty
        assert not data["global_liquidity_df"].empty
