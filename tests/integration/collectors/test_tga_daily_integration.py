"""Integration tests for TGA Daily collector with real API.

Tests fetch real data from the US Treasury FiscalData API.
No authentication required - the API is public.

Run with: uv run pytest tests/integration/collectors/test_tga_daily_integration.py -v
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from liquidity.collectors.tga_daily import TGADailyCollector


@pytest.fixture
def tga_collector() -> TGADailyCollector:
    """Create a TGA Daily collector instance."""
    return TGADailyCollector()


class TestTGADailyCollectorRealAPI:
    """Integration tests using real FiscalData API."""

    @pytest.mark.asyncio
    async def test_collect_real_api(self, tga_collector: TGADailyCollector) -> None:
        """Test fetching real TGA data from FiscalData API."""
        try:
            # Fetch last 30 days
            start = datetime.now(UTC) - timedelta(days=30)
            df = await tga_collector.collect(start_date=start)

            # Should have data (weekdays only, ~20 records expected)
            assert len(df) > 10, f"Expected at least 10 records for 30 days, got {len(df)}"

            # Check data structure
            assert "timestamp" in df.columns
            assert "series_id" in df.columns
            assert "source" in df.columns
            assert "value" in df.columns
            assert "unit" in df.columns

            # Check series_id is correct
            assert df["series_id"].unique().tolist() == ["TGA_DAILY"]

            # Check source is correct
            assert df["source"].unique().tolist() == ["fiscaldata"]

            # Check unit is correct
            assert df["unit"].unique().tolist() == ["millions_usd"]

            # TGA should be in reasonable range (100B - 2T = 100000 - 2000000 million)
            latest_value = df["value"].iloc[-1]
            assert 100000 < latest_value < 2000000, (
                f"TGA value {latest_value} out of expected range (100B - 2T)"
            )

            print(f"\nFetched {len(df)} TGA daily records")
            print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
            print(f"Latest TGA: ${latest_value / 1_000_000:.3f} trillion USD")

        finally:
            await tga_collector.close()

    @pytest.mark.asyncio
    async def test_collect_date_range(self, tga_collector: TGADailyCollector) -> None:
        """Test fetching specific date range."""
        try:
            # Use a fixed historical range (Jan 2026)
            start = datetime(2026, 1, 1, tzinfo=UTC)
            end = datetime(2026, 1, 31, tzinfo=UTC)

            df = await tga_collector.collect(start_date=start, end_date=end)

            assert len(df) > 0, "Should have at least some data for January 2026"

            # Verify all timestamps are within range (compare dates, ignoring tz)
            min_date = df["timestamp"].min().date()
            max_date = df["timestamp"].max().date()
            assert min_date >= start.date(), f"Min date {min_date} is before start {start.date()}"
            assert max_date <= end.date(), f"Max date {max_date} is after end {end.date()}"

            print(f"\nJanuary 2026 data: {len(df)} records")

        finally:
            await tga_collector.close()

    @pytest.mark.asyncio
    async def test_collect_latest(self, tga_collector: TGADailyCollector) -> None:
        """Test collect_latest returns single most recent value."""
        try:
            df = await tga_collector.collect_latest()

            # Should have exactly 1 row
            assert len(df) == 1, f"Expected 1 row, got {len(df)}"

            # Value should be reasonable
            value = df["value"].iloc[0]
            assert 100000 < value < 2000000, f"TGA value {value} out of range"

            print(f"\nLatest TGA: ${value / 1_000_000:.3f} trillion USD")
            print(f"As of: {df['timestamp'].iloc[0]}")

        finally:
            await tga_collector.close()

    @pytest.mark.asyncio
    async def test_data_is_sorted_by_timestamp(self, tga_collector: TGADailyCollector) -> None:
        """Test that returned data is sorted ascending by timestamp."""
        try:
            start = datetime.now(UTC) - timedelta(days=30)
            df = await tga_collector.collect(start_date=start)

            assert len(df) > 1, "Need at least 2 rows to test sorting"

            # Verify ascending order
            timestamps = df["timestamp"].tolist()
            assert timestamps == sorted(timestamps), "Data should be sorted ascending"

        finally:
            await tga_collector.close()

    @pytest.mark.asyncio
    async def test_no_duplicate_dates(self, tga_collector: TGADailyCollector) -> None:
        """Test that there are no duplicate dates in the data."""
        try:
            start = datetime.now(UTC) - timedelta(days=30)
            df = await tga_collector.collect(start_date=start)

            unique_dates = df["timestamp"].nunique()
            total_rows = len(df)

            assert unique_dates == total_rows, (
                f"Found duplicates: {total_rows - unique_dates} duplicate dates"
            )

        finally:
            await tga_collector.close()


class TestTGADailyCollectorDataValidation:
    """Tests for data format validation with real API."""

    @pytest.mark.asyncio
    async def test_timestamp_is_datetime(self, tga_collector: TGADailyCollector) -> None:
        """Test that timestamp column is datetime type."""
        try:
            df = await tga_collector.collect_latest()

            assert pd.api.types.is_datetime64_any_dtype(df["timestamp"]), (
                f"timestamp is {df['timestamp'].dtype}, expected datetime"
            )

        finally:
            await tga_collector.close()

    @pytest.mark.asyncio
    async def test_value_is_numeric(self, tga_collector: TGADailyCollector) -> None:
        """Test that value column is numeric."""
        try:
            df = await tga_collector.collect_latest()

            assert pd.api.types.is_numeric_dtype(df["value"]), (
                f"value is {df['value'].dtype}, expected numeric"
            )

        finally:
            await tga_collector.close()

    @pytest.mark.asyncio
    async def test_value_is_positive(self, tga_collector: TGADailyCollector) -> None:
        """Test that all values are positive."""
        try:
            start = datetime.now(UTC) - timedelta(days=30)
            df = await tga_collector.collect(start_date=start)

            assert (df["value"] > 0).all(), "All TGA values should be positive"

        finally:
            await tga_collector.close()


class TestTGADailyCollectorRegistry:
    """Tests for registry integration with real collector."""

    @pytest.mark.asyncio
    async def test_collector_from_registry_works(self) -> None:
        """Test that collector from registry fetches real data."""
        from liquidity.collectors import registry

        collector_cls = registry.get("tga_daily")
        collector = collector_cls()

        try:
            df = await collector.collect_latest()

            assert len(df) == 1
            assert df["series_id"].iloc[0] == "TGA_DAILY"

        finally:
            await collector.close()


class TestTGADailyCollectorResilience:
    """Tests for collector resilience and error handling."""

    @pytest.mark.asyncio
    async def test_handles_future_date_range(self, tga_collector: TGADailyCollector) -> None:
        """Test handling of future date range (no data expected)."""
        try:
            # Request data for the future
            start = datetime.now(UTC) + timedelta(days=30)
            end = datetime.now(UTC) + timedelta(days=60)

            df = await tga_collector.collect(start_date=start, end_date=end)

            # Should return empty DataFrame with correct columns
            assert len(df) == 0
            assert list(df.columns) == ["timestamp", "series_id", "source", "value", "unit"]

        finally:
            await tga_collector.close()

    @pytest.mark.asyncio
    async def test_handles_very_old_date_range(self, tga_collector: TGADailyCollector) -> None:
        """Test handling of very old date range (may have limited data)."""
        try:
            # Request data from 2020
            start = datetime(2020, 1, 1, tzinfo=UTC)
            end = datetime(2020, 1, 31, tzinfo=UTC)

            df = await tga_collector.collect(start_date=start, end_date=end)

            # Should return data or empty DataFrame
            assert isinstance(df, pd.DataFrame)
            if len(df) > 0:
                assert df["series_id"].iloc[0] == "TGA_DAILY"

        finally:
            await tga_collector.close()


if __name__ == "__main__":
    # Quick sanity check
    async def main() -> None:
        collector = TGADailyCollector()

        print("Testing FiscalData API...")
        try:
            df = await collector.collect(start_date=datetime.now(UTC) - timedelta(days=30))
            print(f"Fetched {len(df)} rows from FiscalData")
            print(df.head())
            print(f"\nLatest TGA: ${df['value'].iloc[-1] / 1_000_000:.3f} trillion USD")
        finally:
            await collector.close()

    asyncio.run(main())
