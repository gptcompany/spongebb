"""Integration tests for FX collector.

Tests FXCollector functionality:
- DXY fetch via Yahoo Finance
- Major FX pairs fetch
- Weekend gap handling for DXY
- FRED fallback for DXY
- Batch download (single yf.download for multiple symbols)

Run with: uv run pytest tests/integration/test_fx_collector.py -v
"""

import asyncio
import os
from unittest.mock import patch

import pytest

from liquidity.collectors.fx import FX_SYMBOLS, FXCollector


@pytest.fixture
def fx_collector() -> FXCollector:
    """Create an FX collector instance."""
    return FXCollector()


class TestFXCollectorDXY:
    """Integration tests for DXY fetching."""

    @pytest.mark.asyncio
    async def test_fx_collector_dxy(self, fx_collector: FXCollector) -> None:
        """Test DXY fetch via Yahoo Finance."""
        # Fetch last 30 days of DXY data
        df = await fx_collector.collect_dxy(period="30d")

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}

        # Verify series_id is DXY ticker
        assert df["series_id"].unique().tolist() == ["DX-Y.NYB"]

        # Verify source is 'yahoo'
        assert df["source"].unique().tolist() == ["yahoo"]

        # Verify unit is 'index'
        assert df["unit"].unique().tolist() == ["index"]

        # Verify DXY value in typical range (80-120)
        dxy_values = df["value"]
        assert dxy_values.min() > 80, f"DXY too low: {dxy_values.min()}"
        assert dxy_values.max() < 130, f"DXY too high: {dxy_values.max()}"

        # Verify we have multiple data points
        assert len(df) > 10, f"Expected >10 data points, got {len(df)}"

        print(f"\nDXY (latest): {dxy_values.iloc[-1]:.2f}")
        print(f"DXY range: {dxy_values.min():.2f} - {dxy_values.max():.2f}")

    @pytest.mark.asyncio
    async def test_fx_collector_dxy_weekend_handling(
        self, fx_collector: FXCollector
    ) -> None:
        """Test that DXY weekend gaps are handled with ffill."""
        # Fetch enough data to include weekends
        df = await fx_collector.collect_dxy(period="30d")

        if df.empty:
            pytest.skip("No DXY data returned")

        # There should be no NaN values after processing
        assert df["value"].isna().sum() == 0, (
            "DXY should have no NaN values after ffill"
        )

        # Verify data is sorted by timestamp
        timestamps = df["timestamp"].values
        assert all(
            timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1)
        ), "Data should be sorted by timestamp"


class TestFXCollectorPairs:
    """Integration tests for FX pair fetching."""

    @pytest.mark.asyncio
    async def test_fx_collector_major_pairs(self, fx_collector: FXCollector) -> None:
        """Test major FX pairs fetch."""
        # Fetch last 30 days of major pairs
        df = await fx_collector.collect_pairs(period="30d")

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}

        # Verify source is 'yahoo'
        assert (df["source"] == "yahoo").all()

        # Verify unit is 'rate' for pairs
        assert (df["unit"] == "rate").all()

        # Get unique pairs
        pairs = df["series_id"].unique().tolist()
        print(f"\nPairs fetched: {pairs}")

        # Verify at least some major pairs are present
        expected_pairs = ["EURUSD=X", "USDJPY=X", "GBPUSD=X"]
        for pair in expected_pairs:
            assert pair in pairs, f"Expected {pair} in results"

        # Verify FX pair values in reasonable ranges
        eurusd = df[df["series_id"] == "EURUSD=X"]["value"]
        if not eurusd.empty:
            assert eurusd.min() > 0.5, f"EUR/USD too low: {eurusd.min()}"
            assert eurusd.max() < 2.0, f"EUR/USD too high: {eurusd.max()}"
            print(f"EUR/USD (latest): {eurusd.iloc[-1]:.4f}")

        usdjpy = df[df["series_id"] == "USDJPY=X"]["value"]
        if not usdjpy.empty:
            assert usdjpy.min() > 80, f"USD/JPY too low: {usdjpy.min()}"
            assert usdjpy.max() < 200, f"USD/JPY too high: {usdjpy.max()}"
            print(f"USD/JPY (latest): {usdjpy.iloc[-1]:.2f}")

    @pytest.mark.asyncio
    async def test_fx_collector_batch_download(self, fx_collector: FXCollector) -> None:
        """Test that batch download works for multiple symbols."""
        # Fetch multiple pairs at once
        symbols = ["EURUSD=X", "USDJPY=X", "GBPUSD=X"]
        df = await fx_collector.collect(symbols=symbols, period="30d")

        # Verify all requested symbols are present
        fetched_symbols = df["series_id"].unique().tolist()
        for symbol in symbols:
            assert symbol in fetched_symbols, f"Symbol {symbol} not in results"

        # Verify we have data for each symbol
        for symbol in symbols:
            symbol_data = df[df["series_id"] == symbol]
            assert len(symbol_data) > 0, f"No data for {symbol}"


class TestFXCollectorFallback:
    """Integration tests for FRED fallback."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.environ.get("LIQUIDITY_FRED_API_KEY"),
        reason="LIQUIDITY_FRED_API_KEY not set - skipping FRED fallback test",
    )
    async def test_fx_collector_dxy_fred_fallback(
        self, fx_collector: FXCollector
    ) -> None:
        """Test FRED fallback for DXY when Yahoo fails."""
        # Mock Yahoo fetch to fail
        with patch.object(
            fx_collector, "_fetch_sync", side_effect=Exception("Yahoo failed")
        ):
            # Collect DXY - should fallback to FRED
            df = await fx_collector.collect_dxy(period="30d", use_fred_fallback=True)

            # Verify FRED fallback worked
            assert not df.empty, "FRED fallback should return data"
            assert df["source"].unique().tolist() == ["fred"]
            assert df["series_id"].unique().tolist() == ["DXY"]  # Normalized name

            # Verify DXY value in typical range
            dxy_values = df["value"]
            assert dxy_values.min() > 80, f"DXY too low: {dxy_values.min()}"
            assert dxy_values.max() < 130, f"DXY too high: {dxy_values.max()}"

            print(f"\nDXY from FRED (latest): {dxy_values.iloc[-1]:.2f}")


class TestFXCollectorAll:
    """Integration tests for collecting all FX data."""

    @pytest.mark.asyncio
    async def test_fx_collector_collect_all(self, fx_collector: FXCollector) -> None:
        """Test collecting all FX data (DXY + pairs)."""
        df = await fx_collector.collect_all(period="30d")

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}

        # Get unique series
        series = df["series_id"].unique().tolist()
        print(f"\nAll FX series fetched: {series}")

        # Verify at least DXY and some pairs are present
        assert "DX-Y.NYB" in series, "DXY should be in results"
        assert any("USD" in s for s in series), "Should have USD pairs"

        # Verify units are correct
        dxy_unit = df[df["series_id"] == "DX-Y.NYB"]["unit"].unique()
        if len(dxy_unit) > 0:
            assert dxy_unit[0] == "index", "DXY should have unit 'index'"

        pair_units = df[df["series_id"] != "DX-Y.NYB"]["unit"].unique()
        if len(pair_units) > 0:
            assert "rate" in pair_units, "Pairs should have unit 'rate'"

    @pytest.mark.asyncio
    async def test_fx_collector_get_current_dxy(
        self, fx_collector: FXCollector
    ) -> None:
        """Test getting current DXY value."""
        dxy = await fx_collector.get_current_dxy()

        if dxy is None:
            pytest.skip("Could not fetch current DXY")

        # Verify DXY value in typical range
        assert 80 < dxy < 130, f"DXY out of range: {dxy}"
        print(f"\nCurrent DXY: {dxy:.2f}")


class TestFXCollectorRegistry:
    """Tests for FX collector registry."""

    @pytest.mark.asyncio
    async def test_collector_registered(self) -> None:
        """Test that FX collector is registered in the registry."""
        from liquidity.collectors import registry

        assert "fx" in registry.list_collectors()
        collector_cls = registry.get("fx")
        assert collector_cls is FXCollector


class TestFXCollectorSymbols:
    """Tests for FX symbols mapping."""

    def test_fx_symbols_mapping(self) -> None:
        """Test FX symbols mapping is correct."""
        # Verify expected symbols are defined
        assert "dxy" in FX_SYMBOLS
        assert "eurusd" in FX_SYMBOLS
        assert "usdjpy" in FX_SYMBOLS
        assert "gbpusd" in FX_SYMBOLS
        assert "usdchf" in FX_SYMBOLS
        assert "usdcad" in FX_SYMBOLS
        assert "usdcny" in FX_SYMBOLS
        assert "audusd" in FX_SYMBOLS

        # Verify Yahoo Finance ticker format
        assert FX_SYMBOLS["dxy"] == "DX-Y.NYB"
        assert FX_SYMBOLS["eurusd"] == "EURUSD=X"
        assert FX_SYMBOLS["usdjpy"] == "USDJPY=X"


if __name__ == "__main__":
    # Run a quick sanity check
    async def main() -> None:
        collector = FXCollector()

        print("Fetching DXY...")
        dxy_df = await collector.collect_dxy(period="30d")
        if not dxy_df.empty:
            print(f"DXY (latest): {dxy_df['value'].iloc[-1]:.2f}")
        else:
            print("No DXY data returned")

        print("\nFetching major pairs...")
        pairs_df = await collector.collect_pairs(period="30d")
        if not pairs_df.empty:
            for series in pairs_df["series_id"].unique():
                latest = pairs_df[pairs_df["series_id"] == series]["value"].iloc[-1]
                print(f"{series}: {latest:.4f}")
        else:
            print("No pairs data returned")

        print("\nFetching all FX data...")
        all_df = await collector.collect_all(period="30d")
        print(f"Total data points: {len(all_df)}")
        print(f"Series: {all_df['series_id'].unique().tolist()}")

    asyncio.run(main())
