"""Integration tests for ETF flows collector.

Tests ETFFlowCollector functionality:
- Current shares outstanding fetch
- Historical price fetch
- Batch download for prices
- Precious metal ETF convenience methods

Run with: uv run pytest tests/integration/test_etf_flows.py -v
"""

import asyncio

import pandas as pd
import pytest

from liquidity.collectors.etf_flows import (
    ETF_TICKERS,
    ETF_UNDERLYING,
    ETFFlowCollector,
)


@pytest.fixture
def etf_collector() -> ETFFlowCollector:
    """Create an ETF flow collector instance."""
    return ETFFlowCollector()


class TestETFSymbols:
    """Tests for ETF symbols mapping."""

    def test_etf_tickers_defined(self) -> None:
        """Test all 5 ETFs are mapped."""
        assert len(ETF_TICKERS) == 5
        assert "gld" in ETF_TICKERS
        assert "slv" in ETF_TICKERS
        assert "uso" in ETF_TICKERS
        assert "cper" in ETF_TICKERS
        assert "dba" in ETF_TICKERS

    def test_etf_ticker_values(self) -> None:
        """Test ETF ticker values are correct."""
        assert ETF_TICKERS["gld"] == "GLD"
        assert ETF_TICKERS["slv"] == "SLV"
        assert ETF_TICKERS["uso"] == "USO"
        assert ETF_TICKERS["cper"] == "CPER"
        assert ETF_TICKERS["dba"] == "DBA"

    def test_etf_underlying_mapping(self) -> None:
        """Test all ETFs have underlying commodity mapping."""
        for ticker in ETF_TICKERS.values():
            assert ticker in ETF_UNDERLYING, f"Missing underlying for {ticker}"

    def test_etf_underlying_values(self) -> None:
        """Test underlying values are correct."""
        assert ETF_UNDERLYING["GLD"] == "gold"
        assert ETF_UNDERLYING["SLV"] == "silver"
        assert ETF_UNDERLYING["USO"] == "oil"
        assert ETF_UNDERLYING["CPER"] == "copper"
        assert ETF_UNDERLYING["DBA"] == "agriculture"


class TestETFFlowCollector:
    """Tests for ETFFlowCollector instantiation and basic methods."""

    def test_collector_instantiation(self) -> None:
        """Test ETFFlowCollector can be instantiated."""
        collector = ETFFlowCollector()
        assert collector.name == "etf_flows"

    def test_collector_class_attributes(self) -> None:
        """Test class attributes are accessible."""
        assert ETFFlowCollector.ETF_TICKERS == ETF_TICKERS
        assert ETFFlowCollector.ETF_UNDERLYING == ETF_UNDERLYING


class TestETFFlowCollectorIntegration:
    """Integration tests with real Yahoo Finance data."""

    @pytest.mark.asyncio
    async def test_collect_current_shares(
        self, etf_collector: ETFFlowCollector
    ) -> None:
        """Test fetching current shares outstanding."""
        df = await etf_collector.collect_current_shares()

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        expected_cols = {
            "timestamp",
            "etf",
            "underlying",
            "shares_outstanding",
            "total_assets",
            "nav_price",
            "market_price",
            "source",
        }
        assert set(df.columns) == expected_cols

        # Verify all 5 ETFs present
        etfs = df["etf"].unique().tolist()
        print(f"\nETFs fetched: {etfs}")

        for ticker in ETF_TICKERS.values():
            assert ticker in etfs, f"Missing {ticker}"

        # Verify source
        assert (df["source"] == "yahoo").all()

        # Verify GLD has reasonable shares outstanding (hundreds of millions)
        gld_row = df[df["etf"] == "GLD"]
        if not gld_row.empty:
            shares = gld_row["shares_outstanding"].values[0]
            if shares is not None:
                assert shares > 1e6, f"GLD shares too low: {shares}"
                assert shares < 1e10, f"GLD shares too high: {shares}"
                print(f"GLD shares outstanding: {shares:,.0f}")

    @pytest.mark.asyncio
    async def test_collect_historical_prices(
        self, etf_collector: ETFFlowCollector
    ) -> None:
        """Test fetching historical prices."""
        df = await etf_collector.collect_historical_prices(period="5d")

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        expected_cols = {
            "timestamp",
            "etf",
            "underlying",
            "source",
            "close",
            "volume",
        }
        assert set(df.columns) == expected_cols

        # Verify all 5 ETFs present
        etfs = df["etf"].unique().tolist()
        print(f"\nETFs with price history: {etfs}")

        for ticker in ETF_TICKERS.values():
            assert ticker in etfs, f"Missing {ticker}"

        # Verify data types
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
        assert pd.api.types.is_numeric_dtype(df["close"])
        assert pd.api.types.is_numeric_dtype(df["volume"])

    @pytest.mark.asyncio
    async def test_collect_precious_metal_etfs(
        self, etf_collector: ETFFlowCollector
    ) -> None:
        """Test collecting precious metal ETFs only."""
        df = await etf_collector.collect_precious_metal_etfs(period="5d")

        # Verify only GLD and SLV
        etfs = df["etf"].unique().tolist()
        assert "GLD" in etfs, "GLD should be present"
        assert "SLV" in etfs, "SLV should be present"
        assert len(etfs) == 2, "Should only have 2 ETFs"

        # Verify underlying
        assert set(df["underlying"].unique()) == {"gold", "silver"}

        # Verify price ranges
        gld = df[df["etf"] == "GLD"]["close"]
        assert gld.min() > 100, f"GLD too low: {gld.min()}"
        assert gld.max() < 500, f"GLD too high: {gld.max()}"
        print(f"\nGLD (latest): ${gld.iloc[-1]:.2f}")

        slv = df[df["etf"] == "SLV"]["close"]
        assert slv.min() > 10, f"SLV too low: {slv.min()}"
        assert slv.max() < 100, f"SLV too high: {slv.max()}"
        print(f"SLV (latest): ${slv.iloc[-1]:.2f}")

    @pytest.mark.asyncio
    async def test_historical_prices_output_format(
        self, etf_collector: ETFFlowCollector
    ) -> None:
        """Test historical prices DataFrame has correct format."""
        df = await etf_collector.collect_historical_prices(period="5d")

        # Verify column types
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
        assert pd.api.types.is_string_dtype(df["etf"])
        assert pd.api.types.is_string_dtype(df["underlying"])
        assert pd.api.types.is_string_dtype(df["source"])
        assert pd.api.types.is_numeric_dtype(df["close"])
        assert pd.api.types.is_numeric_dtype(df["volume"])

        # Verify no NaN close prices (ffill should handle gaps)
        assert df["close"].isna().sum() == 0

    @pytest.mark.asyncio
    async def test_current_shares_output_format(
        self, etf_collector: ETFFlowCollector
    ) -> None:
        """Test current shares DataFrame has correct format."""
        df = await etf_collector.collect_current_shares()

        # Verify column types
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
        assert pd.api.types.is_string_dtype(df["etf"])
        assert pd.api.types.is_string_dtype(df["underlying"])
        assert pd.api.types.is_string_dtype(df["source"])


class TestETFFlowCollectorConvenience:
    """Tests for convenience methods."""

    @pytest.mark.asyncio
    async def test_get_gld_holdings(self, etf_collector: ETFFlowCollector) -> None:
        """Test getting GLD holdings."""
        holdings = await etf_collector.get_gld_holdings()

        if holdings is None:
            pytest.skip("Could not fetch GLD holdings")

        assert holdings["etf"] == "GLD"
        assert "shares_outstanding" in holdings
        assert "total_assets" in holdings
        assert "nav_price" in holdings
        assert "market_price" in holdings

        print("\nGLD Holdings:")
        for key, value in holdings.items():
            print(f"  {key}: {value}")

    @pytest.mark.asyncio
    async def test_collect_all(self, etf_collector: ETFFlowCollector) -> None:
        """Test collect_all method."""
        df = await etf_collector.collect_all(period="5d")

        # Should return historical prices
        expected_cols = {
            "timestamp",
            "etf",
            "underlying",
            "source",
            "close",
            "volume",
        }
        assert set(df.columns) == expected_cols

        # All 5 ETFs should be present
        assert len(df["etf"].unique()) == 5


class TestFlowEstimation:
    """Tests for flow estimation methods."""

    def test_estimate_daily_flows_single_timestamp(self) -> None:
        """Test flow estimation with single timestamp returns unchanged."""
        mock_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01")],
                "etf": ["GLD"],
                "shares_outstanding": [100_000_000],
            }
        )

        result = ETFFlowCollector.estimate_daily_flows(mock_data)

        # Should return unchanged (no historical data to compare)
        assert len(result) == 1
        assert (
            "shares_change" not in result.columns
            or result["shares_change"].isna().all()
        )

    def test_estimate_daily_flows_multiple_timestamps(self) -> None:
        """Test flow estimation with multiple timestamps."""
        mock_data = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3),
                "etf": ["GLD", "GLD", "GLD"],
                "shares_outstanding": [100_000_000, 101_000_000, 100_500_000],
            }
        )

        result = ETFFlowCollector.estimate_daily_flows(mock_data)

        # Should have shares_change column
        assert "shares_change" in result.columns

        # First value should be NaN (no previous to compare)
        assert pd.isna(result["shares_change"].iloc[0])

        # Second value: 101M - 100M = 1M
        assert result["shares_change"].iloc[1] == 1_000_000

        # Third value: 100.5M - 101M = -0.5M
        assert result["shares_change"].iloc[2] == -500_000


class TestETFFlowCollectorRegistry:
    """Tests for ETF flow collector registry."""

    @pytest.mark.asyncio
    async def test_collector_registered(self) -> None:
        """Test that ETF flow collector is registered."""
        from liquidity.collectors import registry

        assert "etf_flows" in registry.list_collectors()
        collector_cls = registry.get("etf_flows")
        assert collector_cls is ETFFlowCollector


if __name__ == "__main__":
    # Run a quick sanity check
    async def main() -> None:
        collector = ETFFlowCollector()

        print("Fetching current shares outstanding...")
        shares_df = await collector.collect_current_shares()
        print(shares_df.to_string())

        print("\n\nFetching historical prices (5d)...")
        prices_df = await collector.collect_historical_prices(period="5d")
        print(f"Total data points: {len(prices_df)}")

        for etf in prices_df["etf"].unique():
            etf_data = prices_df[prices_df["etf"] == etf]
            latest = etf_data["close"].iloc[-1]
            print(f"{etf}: ${latest:.2f}")

        print("\n\nFetching GLD holdings...")
        gld = await collector.get_gld_holdings()
        if gld:
            print(f"GLD shares outstanding: {gld['shares_outstanding']:,.0f}")

    asyncio.run(main())
