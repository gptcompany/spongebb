"""Integration tests for CFTC COT collector.

Tests CFTCCOTCollector with real CFTC Socrata API.
Run with: uv run pytest tests/integration/collectors/test_cftc_cot_integration.py -v

Note: These tests make real API calls to CFTC public API (no auth required).
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from liquidity.collectors.cftc_cot import CFTCCOTCollector


@pytest.fixture
def cftc_collector() -> CFTCCOTCollector:
    """Create CFTC COT collector for integration tests."""
    return CFTCCOTCollector()


@pytest.mark.integration
class TestCFTCCOTRealAPI:
    """Integration tests using real CFTC Socrata API."""

    @pytest.mark.asyncio
    async def test_collect_wti_real_data(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test collecting real WTI crude oil positioning data."""
        df = await cftc_collector.collect(commodities=["WTI"], weeks=4)

        # Should return data
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

        # Should have correct schema
        assert "timestamp" in df.columns
        assert "series_id" in df.columns
        assert "source" in df.columns
        assert "value" in df.columns
        assert "unit" in df.columns

        # Should have CFTC source
        assert all(df["source"] == "cftc")

        # Should have contracts unit
        assert all(df["unit"] == "contracts")

        # Should have WTI series
        wti_series = [s for s in df["series_id"].unique() if "wti" in s]
        assert len(wti_series) > 0

    @pytest.mark.asyncio
    async def test_collect_gold_real_data(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test collecting real Gold positioning data."""
        df = await cftc_collector.collect(commodities=["GOLD"], weeks=4)

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

        # Should have gold series
        gold_series = [s for s in df["series_id"].unique() if "gold" in s]
        assert len(gold_series) > 0

    @pytest.mark.asyncio
    async def test_collect_multiple_commodities_real(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test collecting multiple commodities from real API."""
        df = await cftc_collector.collect(
            commodities=["WTI", "GOLD", "COPPER"], weeks=2
        )

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

        # Should have series for all commodities
        series_ids = df["series_id"].unique()
        assert any("wti" in s for s in series_ids)
        assert any("gold" in s for s in series_ids)
        assert any("copper" in s for s in series_ids)

    @pytest.mark.asyncio
    async def test_data_freshness(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test that data is reasonably fresh (within 14 days)."""
        df = await cftc_collector.collect(commodities=["WTI"], weeks=4)

        assert len(df) > 0

        # Latest data should be within 14 days (COT released weekly on Friday)
        latest_date = df["timestamp"].max()
        days_old = (pd.Timestamp.now() - latest_date).days

        # Data should be within 14 days (to allow for release delay)
        assert days_old <= 14, f"Data is {days_old} days old"

    @pytest.mark.asyncio
    async def test_open_interest_positive(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test that open interest values are positive."""
        df = await cftc_collector.collect(commodities=["WTI"], weeks=4)

        oi_data = df[df["series_id"] == "cot_wti_oi"]

        assert len(oi_data) > 0
        # Open interest should always be positive
        assert all(oi_data["value"] > 0)

    @pytest.mark.asyncio
    async def test_net_positions_have_reasonable_values(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test that net position values are reasonable (can be positive or negative)."""
        df = await cftc_collector.collect(commodities=["WTI"], weeks=4)

        comm_net = df[df["series_id"] == "cot_wti_comm_net"]
        spec_net = df[df["series_id"] == "cot_wti_spec_net"]

        assert len(comm_net) > 0
        assert len(spec_net) > 0

        # Net positions can be positive or negative but should be non-zero
        # (at least some of them)
        assert comm_net["value"].abs().max() > 0
        assert spec_net["value"].abs().max() > 0

    @pytest.mark.asyncio
    async def test_date_range_filtering(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test that date range filtering works correctly."""
        end_date = date.today()
        start_date = end_date - timedelta(weeks=8)

        df = await cftc_collector.collect(
            commodities=["WTI"],
            start_date=start_date,
            end_date=end_date,
        )

        assert len(df) > 0

        # All dates should be within the range
        min_date = df["timestamp"].min().date()
        max_date = df["timestamp"].max().date()

        assert min_date >= start_date
        assert max_date <= end_date

    @pytest.mark.asyncio
    async def test_collect_single_convenience(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test collect_single convenience method with real API."""
        df = await cftc_collector.collect_single("GOLD", weeks=4)

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

        # Should only have gold series
        series_ids = df["series_id"].unique()
        assert all("gold" in s for s in series_ids)

    @pytest.mark.asyncio
    async def test_get_latest_with_real_data(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test get_latest method with real API data."""
        df = await cftc_collector.collect(commodities=["WTI"], weeks=4)

        latest = cftc_collector.get_latest(df, "WTI")

        assert "comm_net" in latest
        assert "spec_net" in latest
        assert "swap_net" in latest
        assert "oi" in latest

        # OI should be positive
        assert latest["oi"] > 0

    @pytest.mark.asyncio
    async def test_all_commodities_available(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test that all configured commodities return data."""
        commodities = ["WTI", "GOLD", "COPPER", "SILVER", "NATGAS"]

        for commodity in commodities:
            df = await cftc_collector.collect(commodities=[commodity], weeks=2)
            assert len(df) > 0, f"No data for {commodity}"

    @pytest.mark.asyncio
    async def test_collector_cleanup(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test that collector properly cleans up resources."""
        # Make a request to initialize client
        await cftc_collector.collect(commodities=["WTI"], weeks=1)

        # Close should work
        await cftc_collector.close()
        assert cftc_collector._client is None


@pytest.mark.integration
class TestCFTCCOTDataQuality:
    """Data quality tests for CFTC COT data."""

    @pytest.mark.asyncio
    async def test_no_duplicate_timestamps(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test that there are no duplicate timestamps per series."""
        df = await cftc_collector.collect(commodities=["WTI"], weeks=52)

        for series_id in df["series_id"].unique():
            series_data = df[df["series_id"] == series_id]
            duplicates = series_data["timestamp"].duplicated().sum()
            assert duplicates == 0, f"Found {duplicates} duplicates for {series_id}"

    @pytest.mark.asyncio
    async def test_weekly_frequency(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test that data is approximately weekly frequency."""
        df = await cftc_collector.collect(commodities=["WTI"], weeks=12)

        oi_data = df[df["series_id"] == "cot_wti_oi"].sort_values("timestamp")

        if len(oi_data) >= 2:
            # Calculate days between consecutive reports
            diffs = oi_data["timestamp"].diff().dropna().dt.days

            # Most diffs should be ~7 days (weekly)
            median_diff = diffs.median()
            assert 5 <= median_diff <= 9, f"Median diff is {median_diff} days"

    @pytest.mark.asyncio
    async def test_positions_sum_to_open_interest_approximately(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test that long + short positions relate to open interest."""
        df = await cftc_collector.collect(commodities=["WTI"], weeks=4)

        # Get latest data
        latest_date = df["timestamp"].max()
        latest = df[df["timestamp"] == latest_date]

        comm_long = latest[latest["series_id"] == "cot_wti_comm_long"]["value"].iloc[0]
        comm_short = latest[latest["series_id"] == "cot_wti_comm_short"]["value"].iloc[0]
        spec_long = latest[latest["series_id"] == "cot_wti_spec_long"]["value"].iloc[0]
        spec_short = latest[latest["series_id"] == "cot_wti_spec_short"]["value"].iloc[0]
        oi = latest[latest["series_id"] == "cot_wti_oi"]["value"].iloc[0]

        # Sum of major position types should be less than or equal to total OI
        # (non-reportables and other categories exist)
        total_positions = comm_long + spec_long + comm_short + spec_short
        assert total_positions <= oi * 2.5, "Positions exceed reasonable multiple of OI"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
