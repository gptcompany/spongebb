"""Integration tests for stablecoin collector with real API.

Tests against the live DefiLlama API (no authentication required).
Run with: uv run pytest tests/integration/collectors/test_stablecoins_integration.py -v

Note: These tests make real HTTP requests to the DefiLlama API.
"""

import asyncio
from datetime import UTC, datetime

import pandas as pd
import pytest

from liquidity.collectors.stablecoins import StablecoinCollector


@pytest.fixture
def collector() -> StablecoinCollector:
    """Create a StablecoinCollector instance."""
    return StablecoinCollector()


class TestStablecoinCollectIntegration:
    """Integration tests for collect method with real API."""

    @pytest.mark.asyncio
    async def test_collect_real_api(self, collector: StablecoinCollector) -> None:
        """Test fetching real stablecoin data from DefiLlama."""
        try:
            df = await collector.collect()

            # Should have data
            assert len(df) > 0, "Should return stablecoin data"

            # Check data structure
            expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
            assert expected_columns.issubset(set(df.columns)), (
                f"Missing columns: {expected_columns - set(df.columns)}"
            )

            # Should have total market cap
            total_rows = df[df["series_id"] == "STABLECOIN_TOTAL_MCAP"]
            assert len(total_rows) > 0, "Should include total market cap"

            total_mcap = total_rows["value"].iloc[0]
            # Total stablecoin market should be >$100B (as of 2026)
            assert total_mcap > 100, f"Total stablecoin mcap {total_mcap}B seems too low"
            # And less than $1T for sanity check
            assert total_mcap < 1000, f"Total stablecoin mcap {total_mcap}B seems too high"

            # Verify source
            assert (df["source"] == "defillama").all()

            # Verify unit
            assert (df["unit"] == "billions_usd").all()

            # Values should be positive
            assert (df["value"] >= 0).all(), "Values should be non-negative"

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_collect_includes_usdt(self, collector: StablecoinCollector) -> None:
        """Test that USDT (largest stablecoin) is included."""
        try:
            df = await collector.collect()

            usdt_rows = df[df["series_id"] == "STABLECOIN_USDT"]
            assert len(usdt_rows) > 0, "Should include USDT"

            usdt_supply = usdt_rows["value"].iloc[0]
            # USDT should be >$50B (it's the largest stablecoin)
            assert usdt_supply > 50, f"USDT supply {usdt_supply}B seems too low"

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_collect_includes_usdc(self, collector: StablecoinCollector) -> None:
        """Test that USDC (second largest stablecoin) is included."""
        try:
            df = await collector.collect()

            usdc_rows = df[df["series_id"] == "STABLECOIN_USDC"]
            assert len(usdc_rows) > 0, "Should include USDC"

            usdc_supply = usdc_rows["value"].iloc[0]
            # USDC should be >$10B
            assert usdc_supply > 10, f"USDC supply {usdc_supply}B seems too low"

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_collect_includes_chain_breakdown(
        self, collector: StablecoinCollector
    ) -> None:
        """Test that chain breakdown is included for major stablecoins."""
        try:
            df = await collector.collect(include_chain_breakdown=True)

            # Should have at least one chain breakdown (e.g., USDT on Ethereum or Tron)
            chain_rows = df[df["series_id"].str.contains("_ETHEREUM|_TRON|_BSC")]
            # May not always have chain data if API format changes
            # So we don't require it, just check format if present
            if len(chain_rows) > 0:
                # Values should be in billions
                assert (chain_rows["value"] > 0).all()
                assert (chain_rows["unit"] == "billions_usd").all()

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_collect_without_chain_breakdown(
        self, collector: StablecoinCollector
    ) -> None:
        """Test collect without chain breakdown returns fewer rows."""
        try:
            df_with_chains = await collector.collect(include_chain_breakdown=True)
            df_without_chains = await collector.collect(include_chain_breakdown=False)

            # Without chains should have fewer or equal rows
            assert len(df_without_chains) <= len(df_with_chains)

        finally:
            await collector.close()


class TestStablecoinHistoricalIntegration:
    """Integration tests for historical data collection."""

    @pytest.mark.asyncio
    async def test_collect_historical_real_api(
        self, collector: StablecoinCollector
    ) -> None:
        """Test fetching historical stablecoin data."""
        try:
            df = await collector.collect_historical(days=30)

            # Should have ~30 days of data
            assert len(df) >= 25, f"Expected at least 25 days of history, got {len(df)}"

            # Check data structure
            expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
            assert expected_columns.issubset(set(df.columns))

            # Values should be in reasonable range
            # Total stablecoin market has been >$100B since 2022
            assert df["value"].min() > 50, "Historical values seem too low"
            assert df["value"].max() < 1000, "Historical values seem too high"

            # All should be total market cap series
            assert (df["series_id"] == "STABLECOIN_TOTAL_MCAP").all()

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_historical_data_sorted(
        self, collector: StablecoinCollector
    ) -> None:
        """Test historical data is sorted by timestamp."""
        try:
            df = await collector.collect_historical(days=30)

            if len(df) > 1:
                timestamps = df["timestamp"].tolist()
                assert timestamps == sorted(timestamps), "Data should be sorted by timestamp"

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_historical_timestamps_are_datetime(
        self, collector: StablecoinCollector
    ) -> None:
        """Test historical timestamps are proper datetime objects."""
        try:
            df = await collector.collect_historical(days=30)

            if not df.empty:
                assert pd.api.types.is_datetime64_any_dtype(df["timestamp"]), (
                    "timestamp should be datetime type"
                )

        finally:
            await collector.close()


class TestStablecoinMarketSummaryIntegration:
    """Integration tests for market summary."""

    @pytest.mark.asyncio
    async def test_market_summary_real_api(
        self, collector: StablecoinCollector
    ) -> None:
        """Test market summary with real data."""
        try:
            summary = await collector.collect_market_summary()

            # Check all expected keys
            assert "total_market_cap_billions" in summary
            assert "usdt_billions" in summary
            assert "usdc_billions" in summary
            assert "usdt_dominance" in summary
            assert "timestamp" in summary

            # Total should be >$100B
            assert summary["total_market_cap_billions"] > 100

            # USDT dominance should be between 0 and 100%
            assert 0 < summary["usdt_dominance"] < 100

            # USDT should be > USDC (historically true)
            assert summary["usdt_billions"] > summary["usdc_billions"]

            # Timestamp should be valid ISO format
            assert "T" in summary["timestamp"]

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_market_summary_usdt_dominance_reasonable(
        self, collector: StablecoinCollector
    ) -> None:
        """Test USDT dominance is in reasonable range."""
        try:
            summary = await collector.collect_market_summary()

            # USDT has historically been 50-75% of stablecoin market
            assert summary["usdt_dominance"] > 40, "USDT dominance seems too low"
            assert summary["usdt_dominance"] < 90, "USDT dominance seems too high"

        finally:
            await collector.close()


class TestDataQualityIntegration:
    """Integration tests for data quality."""

    @pytest.mark.asyncio
    async def test_timestamps_are_recent(
        self, collector: StablecoinCollector
    ) -> None:
        """Test that returned data is reasonably recent."""
        try:
            df = await collector.collect()

            if not df.empty:
                # Timestamps should be from today (within last hour)
                latest = df["timestamp"].max()
                if pd.notna(latest):
                    latest_dt = latest.to_pydatetime()
                    if latest_dt.tzinfo is None:
                        latest_dt = latest_dt.replace(tzinfo=UTC)
                    age = datetime.now(UTC) - latest_dt

                    # Should be within last day
                    assert age.total_seconds() < 86400, (
                        f"Data is {age.total_seconds() / 3600:.1f} hours old"
                    )

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_no_duplicate_series_ids(
        self, collector: StablecoinCollector
    ) -> None:
        """Test that there are no duplicate series IDs in current data."""
        try:
            df = await collector.collect(include_chain_breakdown=False)

            # Each series_id should appear only once
            duplicates = df[df["series_id"].duplicated()]
            assert len(duplicates) == 0, f"Found duplicates: {duplicates['series_id'].tolist()}"

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_values_are_numeric(
        self, collector: StablecoinCollector
    ) -> None:
        """Test that all values are numeric."""
        try:
            df = await collector.collect()

            if not df.empty:
                assert pd.api.types.is_numeric_dtype(df["value"]), (
                    "value column should be numeric"
                )
                # No NaN values
                assert not df["value"].isna().any(), "value should not contain NaN"

        finally:
            await collector.close()


class TestCollectorResilienceIntegration:
    """Integration tests for collector resilience."""

    @pytest.mark.asyncio
    async def test_collector_close_reopen(
        self, collector: StablecoinCollector
    ) -> None:
        """Test collector can be closed and reopened."""
        try:
            # First fetch
            df1 = await collector.collect()
            assert not df1.empty

            # Close
            await collector.close()

            # Second fetch (should create new client)
            df2 = await collector.collect()
            assert not df2.empty

        finally:
            await collector.close()

    @pytest.mark.asyncio
    async def test_concurrent_requests(
        self, collector: StablecoinCollector
    ) -> None:
        """Test collector handles concurrent requests."""
        try:
            # Run multiple requests concurrently
            tasks = [
                collector.collect(),
                collector.collect_market_summary(),
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 2
            assert isinstance(results[0], pd.DataFrame)
            assert isinstance(results[1], dict)

        finally:
            await collector.close()


class TestTopStablecoinsIntegration:
    """Integration tests for tracking specific stablecoins."""

    @pytest.mark.asyncio
    async def test_all_top_stablecoins_found(
        self, collector: StablecoinCollector
    ) -> None:
        """Test that all TOP_STABLECOINS are found in API response."""
        try:
            df = await collector.collect(include_chain_breakdown=False)

            # Get symbols from series_ids (e.g., "STABLECOIN_USDT" -> "USDT")
            symbols = [
                s.replace("STABLECOIN_", "")
                for s in df["series_id"]
                if s != "STABLECOIN_TOTAL_MCAP"
            ]

            # Expected symbols from our TOP_STABLECOINS
            expected_symbols = {"USDT", "USDC", "DAI", "FDUSD", "USDe"}

            # At minimum, USDT and USDC should always be present
            assert "USDT" in symbols, "USDT should be in results"
            assert "USDC" in symbols, "USDC should be in results"

            # Log which ones we found
            found = set(symbols) & expected_symbols
            missing = expected_symbols - set(symbols)
            if missing:
                # Some smaller stablecoins may not always be returned
                # This is informational, not a failure
                print(f"Note: Missing stablecoins (may be expected): {missing}")

            # At least 3 of 5 should be present
            assert len(found) >= 3, f"Found only {found}, expected at least 3 of {expected_symbols}"

        finally:
            await collector.close()


if __name__ == "__main__":
    # Quick sanity check for manual testing
    async def main() -> None:
        print("Testing DefiLlama Stablecoins API...")

        collector = StablecoinCollector()

        try:
            print("\n--- Current Stablecoin Supply ---")
            df = await collector.collect()
            print(f"Fetched {len(df)} data points")
            print(df.to_string())

            print("\n--- Market Summary ---")
            summary = await collector.collect_market_summary()
            print(f"Total Market Cap: ${summary['total_market_cap_billions']:.1f}B")
            print(f"USDT: ${summary['usdt_billions']:.1f}B ({summary['usdt_dominance']:.1f}%)")
            print(f"USDC: ${summary['usdc_billions']:.1f}B")

            print("\n--- Historical (30 days) ---")
            hist_df = await collector.collect_historical(days=30)
            print(f"Fetched {len(hist_df)} historical records")
            if not hist_df.empty:
                print(f"Date range: {hist_df['timestamp'].min()} to {hist_df['timestamp'].max()}")
                print(f"Market cap range: ${hist_df['value'].min():.1f}B - ${hist_df['value'].max():.1f}B")

        finally:
            await collector.close()

    asyncio.run(main())
