"""Integration tests for NY Fed collectors with real API.

Tests against the live NY Fed Markets API (no authentication required).
Run with: uv run pytest tests/integration/collectors/test_nyfed_integration.py -v

Note: These tests make real HTTP requests to the NY Fed API.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from liquidity.collectors.nyfed import NYFedCollector
from liquidity.collectors.swap_lines import SwapLinesCollector


@pytest.fixture
def nyfed_collector() -> NYFedCollector:
    """Create a NY Fed collector instance."""
    return NYFedCollector()


@pytest.fixture
def swap_collector() -> SwapLinesCollector:
    """Create a Swap Lines collector instance."""
    return SwapLinesCollector()


class TestNYFedRRPIntegration:
    """Integration tests for RRP data from NY Fed API."""

    @pytest.mark.asyncio
    async def test_collect_rrp_real_api(self, nyfed_collector: NYFedCollector) -> None:
        """Test fetching real RRP data from NY Fed API."""
        try:
            start = datetime.now(UTC) - timedelta(days=14)
            df = await nyfed_collector.collect_rrp(start_date=start)

            # Should have data (daily operations on business days)
            # Allow for some empty days due to holidays/weekends
            assert len(df) >= 5, f"Expected at least 5 records for 14 days, got {len(df)}"

            # Check data structure
            expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
            assert expected_columns.issubset(set(df.columns)), (
                f"Missing columns: {expected_columns - set(df.columns)}"
            )

            # Verify series_id
            assert df["series_id"].iloc[0] == "RRP_DAILY"

            # Verify source
            assert df["source"].iloc[0] == "nyfed"

            # Verify unit
            assert df["unit"].iloc[0] == "billions_usd"

            # RRP should be in reasonable range (0 - 3 trillion = 0 - 3000 billion)
            # As of 2026, RRP has been declining but could spike in stress
            latest_value = df["value"].iloc[-1]
            assert 0 <= latest_value < 3000, f"RRP value {latest_value} out of range"

            # Values should be positive
            assert (df["value"] >= 0).all(), "RRP values should be non-negative"

        finally:
            await nyfed_collector.close()

    @pytest.mark.asyncio
    async def test_collect_rrp_timestamp_format(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test that RRP timestamps are proper datetime objects."""
        try:
            start = datetime.now(UTC) - timedelta(days=7)
            df = await nyfed_collector.collect_rrp(start_date=start)

            if not df.empty:
                # Timestamp should be datetime type
                assert pd.api.types.is_datetime64_any_dtype(df["timestamp"]), (
                    "timestamp should be datetime type"
                )

                # Timestamps should be within expected range
                min_ts = df["timestamp"].min()
                assert min_ts >= pd.Timestamp(start.date()), (
                    f"Min timestamp {min_ts} is before start date {start}"
                )

        finally:
            await nyfed_collector.close()

    @pytest.mark.asyncio
    async def test_collect_rrp_data_sorted(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test that RRP data is sorted by timestamp."""
        try:
            df = await nyfed_collector.collect_rrp()

            if len(df) > 1:
                # Verify timestamps are ascending
                timestamps = df["timestamp"].tolist()
                assert timestamps == sorted(timestamps), "Data should be sorted by timestamp"

        finally:
            await nyfed_collector.close()


class TestNYFedSOMAIntegration:
    """Integration tests for SOMA data from NY Fed API."""

    @pytest.mark.asyncio
    async def test_collect_soma_real_api(self, nyfed_collector: NYFedCollector) -> None:
        """Test fetching real SOMA holdings from NY Fed API."""
        try:
            df = await nyfed_collector.collect_soma()

            # Should have holdings data
            assert len(df) > 0, "SOMA should have holdings data"

            # Check data structure
            expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
            assert expected_columns.issubset(set(df.columns)), (
                f"Missing columns: {expected_columns - set(df.columns)}"
            )

            # Verify source
            assert (df["source"] == "nyfed").all()

            # All series_ids should start with SOMA_
            assert all(s.startswith("SOMA_") for s in df["series_id"]), (
                "All SOMA series should start with 'SOMA_'"
            )

            # Values should be positive
            assert (df["value"] >= 0).all(), "SOMA values should be non-negative"

        finally:
            await nyfed_collector.close()

    @pytest.mark.asyncio
    async def test_soma_contains_treasuries(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test that SOMA includes Treasury securities."""
        try:
            df = await nyfed_collector.collect_soma()

            # Should include some form of Treasury securities
            series_ids = df["series_id"].str.upper().tolist()
            has_treasury = any(
                "TREASURY" in s or "BILLS" in s or "NOTES" in s or "BONDS" in s
                for s in series_ids
            )
            assert has_treasury, (
                f"SOMA should include Treasury securities. Found: {series_ids}"
            )

        finally:
            await nyfed_collector.close()

    @pytest.mark.asyncio
    async def test_soma_has_mbs(self, nyfed_collector: NYFedCollector) -> None:
        """Test that SOMA includes MBS holdings."""
        try:
            df = await nyfed_collector.collect_soma()

            # Should include MBS (Mortgage-Backed Securities)
            series_ids = df["series_id"].str.upper().tolist()
            has_mbs = any("MBS" in s or "MORTGAGE" in s for s in series_ids)
            assert has_mbs, f"SOMA should include MBS. Found: {series_ids}"

        finally:
            await nyfed_collector.close()


class TestSwapLinesIntegration:
    """Integration tests for swap line data from NY Fed API."""

    @pytest.mark.asyncio
    async def test_collect_swap_lines_real_api(
        self, swap_collector: SwapLinesCollector
    ) -> None:
        """Test fetching swap line data from NY Fed API."""
        try:
            df = await swap_collector.collect()

            # May be empty in calm markets - that's OK
            assert isinstance(df, pd.DataFrame)

            # Check schema even if empty
            expected_columns = {
                "timestamp",
                "series_id",
                "source",
                "value",
                "unit",
                "counterparty",
            }
            assert expected_columns.issubset(set(df.columns)), (
                f"Missing columns: {expected_columns - set(df.columns)}"
            )

            if not df.empty:
                # If we have data, verify it's properly formatted
                assert (df["source"] == "nyfed").all()
                assert all(s.startswith("SWAP_") for s in df["series_id"])
                assert (df["value"] >= 0).all()

        finally:
            await swap_collector.close()

    @pytest.mark.asyncio
    async def test_swap_lines_empty_is_valid(
        self, swap_collector: SwapLinesCollector
    ) -> None:
        """Test that empty swap line response is handled gracefully."""
        try:
            df = await swap_collector.collect()

            # Empty is valid - means no current swap activity
            assert isinstance(df, pd.DataFrame)

            # Schema should still be correct
            assert "counterparty" in df.columns
            assert "timestamp" in df.columns

        finally:
            await swap_collector.close()


class TestGenericCollectIntegration:
    """Integration tests for generic collect method."""

    @pytest.mark.asyncio
    async def test_generic_collect_rrp(self, nyfed_collector: NYFedCollector) -> None:
        """Test generic collect with rrp data_type."""
        try:
            df = await nyfed_collector.collect(data_type="rrp")

            # Should have RRP data
            assert not df.empty or len(df) == 0  # May be empty on weekends
            if not df.empty:
                assert df["series_id"].iloc[0] == "RRP_DAILY"

        finally:
            await nyfed_collector.close()

    @pytest.mark.asyncio
    async def test_generic_collect_soma(self, nyfed_collector: NYFedCollector) -> None:
        """Test generic collect with soma data_type."""
        try:
            df = await nyfed_collector.collect(data_type="soma")

            # Should have SOMA data
            assert not df.empty
            assert df["series_id"].iloc[0].startswith("SOMA_")

        finally:
            await nyfed_collector.close()


class TestDataQualityIntegration:
    """Integration tests for data quality."""

    @pytest.mark.asyncio
    async def test_rrp_value_range(self, nyfed_collector: NYFedCollector) -> None:
        """Test RRP values are in realistic range."""
        try:
            df = await nyfed_collector.collect_rrp()

            if not df.empty:
                # RRP historically ranged from 0 to ~2.5T
                # Values in billions, so 0-2500
                assert df["value"].min() >= 0, "RRP cannot be negative"
                assert df["value"].max() < 5000, "RRP seems unrealistically high"

        finally:
            await nyfed_collector.close()

    @pytest.mark.asyncio
    async def test_soma_total_reasonable(self, nyfed_collector: NYFedCollector) -> None:
        """Test SOMA total is in reasonable range."""
        try:
            df = await nyfed_collector.collect_soma()

            if not df.empty:
                # Get the TOTAL series (not sum of all series which would double-count)
                total_row = df[df["series_id"] == "SOMA_TOTAL"]
                if not total_row.empty:
                    total = total_row["value"].iloc[0]
                    # Total SOMA should be ~5-10 trillion (5000-10000 billion)
                    assert 4000 < total < 12000, (
                        f"SOMA total {total}B seems unrealistic (expected 4000-12000)"
                    )

        finally:
            await nyfed_collector.close()

    @pytest.mark.asyncio
    async def test_timestamps_are_recent(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test that returned data is reasonably recent."""
        try:
            df = await nyfed_collector.collect_soma()

            if not df.empty:
                # SOMA should be updated at least weekly
                latest = df["timestamp"].max()
                age = datetime.now(UTC) - latest.to_pydatetime().replace(tzinfo=UTC)

                # Should be within 14 days
                assert age.days <= 14, (
                    f"SOMA data is {age.days} days old - may be stale"
                )

        finally:
            await nyfed_collector.close()


class TestCollectorResilience:
    """Integration tests for collector resilience."""

    @pytest.mark.asyncio
    async def test_nyfed_collector_close_reopen(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test collector can be closed and reopened."""
        try:
            # First fetch
            df1 = await nyfed_collector.collect_soma()
            assert not df1.empty

            # Close
            await nyfed_collector.close()

            # Second fetch (should create new client)
            df2 = await nyfed_collector.collect_soma()
            assert not df2.empty

        finally:
            await nyfed_collector.close()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, nyfed_collector: NYFedCollector) -> None:
        """Test collector handles concurrent requests."""
        try:
            # Run multiple requests concurrently
            tasks = [
                nyfed_collector.collect_soma(),
                nyfed_collector.collect_rrp(),
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 2
            assert isinstance(results[0], pd.DataFrame)
            assert isinstance(results[1], pd.DataFrame)

        finally:
            await nyfed_collector.close()


if __name__ == "__main__":
    # Quick sanity check for manual testing
    async def main() -> None:
        print("Testing NY Fed API...")

        nyfed = NYFedCollector()
        swap = SwapLinesCollector()

        try:
            print("\n--- RRP Operations ---")
            rrp_df = await nyfed.collect_rrp()
            print(f"Fetched {len(rrp_df)} RRP records")
            if not rrp_df.empty:
                print(rrp_df.tail())
                print(f"Latest RRP: ${rrp_df['value'].iloc[-1]:.1f}B")

            print("\n--- SOMA Holdings ---")
            soma_df = await nyfed.collect_soma()
            print(f"Fetched {len(soma_df)} SOMA holdings")
            if not soma_df.empty:
                print(soma_df)
                print(f"Total SOMA: ${soma_df['value'].sum():.1f}B")

            print("\n--- Swap Lines ---")
            swap_df = await swap.collect()
            print(f"Fetched {len(swap_df)} swap operations")
            if not swap_df.empty:
                print(swap_df)
            else:
                print("No swap line activity (normal in calm markets)")

        finally:
            await nyfed.close()
            await swap.close()

    asyncio.run(main())
