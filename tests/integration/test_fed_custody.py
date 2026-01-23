"""Integration tests for Fed Custody Holdings collector.

These tests require:
- Valid FRED API key (LIQUIDITY_FRED_API_KEY env var)

Run with: uv run pytest tests/integration/test_fed_custody.py -v

Fed Custody Holdings series (all weekly, Wednesday level):
- WSEFINTL1: Total custody holdings (foreign official + international)
- WMTSECL1: Marketable US Treasury securities (~90% of total)
- WFASECL1: Federal agency debt & MBS (~7% of total)
"""

import asyncio
import os

import pytest

from liquidity.collectors.fed_custody import (
    FedCustodyCollector,
)

# Skip integration tests if no FRED API key is set
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("LIQUIDITY_FRED_API_KEY"),
        reason="LIQUIDITY_FRED_API_KEY not set - skipping Fed Custody integration tests",
    ),
]


@pytest.fixture
def custody_collector() -> FedCustodyCollector:
    """Create a Fed Custody collector instance."""
    return FedCustodyCollector()


class TestFedCustodyCollector:
    """Integration tests for FedCustodyCollector."""

    @pytest.mark.asyncio
    async def test_collect_total(self, custody_collector: FedCustodyCollector) -> None:
        """Test fetching total custody holdings (WSEFINTL1)."""
        df = await custody_collector.collect_total()

        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}
        assert df["series_id"].unique().tolist() == ["fed_custody_total"]
        assert df["source"].unique().tolist() == ["fred"]
        assert df["unit"].unique().tolist() == ["millions_usd"]

    @pytest.mark.asyncio
    async def test_collect_treasuries(
        self, custody_collector: FedCustodyCollector
    ) -> None:
        """Test fetching Treasury securities only (WMTSECL1)."""
        df = await custody_collector.collect_treasuries()

        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}
        assert df["series_id"].unique().tolist() == ["fed_custody_treasuries"]
        assert df["source"].unique().tolist() == ["fred"]

    @pytest.mark.asyncio
    async def test_collect_agencies(
        self, custody_collector: FedCustodyCollector
    ) -> None:
        """Test fetching agency debt/MBS securities (WFASECL1)."""
        df = await custody_collector.collect_agencies()

        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}
        assert df["series_id"].unique().tolist() == ["fed_custody_agencies"]
        assert df["source"].unique().tolist() == ["fred"]

    @pytest.mark.asyncio
    async def test_collect_all_combined(
        self, custody_collector: FedCustodyCollector
    ) -> None:
        """Test fetching all three series in one DataFrame."""
        df = await custody_collector.collect_all()

        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}

        # Verify all three series are present
        series_present = set(df["series_id"].unique())
        expected_series = {
            "fed_custody_total",
            "fed_custody_treasuries",
            "fed_custody_agencies",
        }
        assert series_present == expected_series, (
            f"Expected {expected_series}, got {series_present}"
        )

    @pytest.mark.asyncio
    async def test_output_format(self, custody_collector: FedCustodyCollector) -> None:
        """Test that output has standard columns present."""
        df = await custody_collector.collect()

        # Standard output format
        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert set(df.columns) == expected_columns

        # Verify timestamp is datetime
        assert df["timestamp"].dtype.name.startswith("datetime")

        # Verify source is always 'fred'
        assert df["source"].unique().tolist() == ["fred"]

    @pytest.mark.asyncio
    async def test_values_reasonable(
        self, custody_collector: FedCustodyCollector
    ) -> None:
        """Test that total custody holdings are between 2T-5T USD (current ~3T)."""
        df = await custody_collector.collect_total()

        # Values are in millions USD
        # Total custody holdings typically ~3T USD = 3,000,000 millions
        min_value = df["value"].min()
        max_value = df["value"].max()

        # Sanity check: between 2T and 5T USD
        assert min_value > 2_000_000, f"Total custody too low: {min_value} millions"
        assert max_value < 5_000_000, f"Total custody too high: {max_value} millions"

        latest_value = df.sort_values("timestamp")["value"].iloc[-1]
        print(
            f"\nTotal Custody Holdings (latest): ${latest_value / 1_000_000:.2f} trillion USD"
        )

    @pytest.mark.asyncio
    async def test_treasuries_majority(
        self, custody_collector: FedCustodyCollector
    ) -> None:
        """Test that Treasuries represent > 80% of total holdings."""
        df = await custody_collector.collect_all()

        # Get latest values for each series
        latest = df.sort_values("timestamp").groupby("series_id").last().reset_index()

        total = latest[latest["series_id"] == "fed_custody_total"]["value"].iloc[0]
        treasuries = latest[latest["series_id"] == "fed_custody_treasuries"][
            "value"
        ].iloc[0]

        treasuries_pct = (treasuries / total) * 100

        # Treasuries should be > 80% of total (typically ~90%)
        assert treasuries_pct > 80, (
            f"Treasuries should be >80% of total, got {treasuries_pct:.1f}%"
        )

        print(f"\nTreasuries % of total: {treasuries_pct:.1f}%")

    @pytest.mark.asyncio
    async def test_weekly_change(self, custody_collector: FedCustodyCollector) -> None:
        """Test that week-over-week change calculation works."""
        df = await custody_collector.get_weekly_change()

        assert not df.empty, "Weekly change DataFrame should not be empty"
        expected_columns = {"timestamp", "series_id", "value", "change", "change_pct"}
        assert set(df.columns) == expected_columns

        # Verify change values are present
        assert df["change"].notna().any(), "Should have some non-NaN changes"
        assert df["change_pct"].notna().any(), "Should have some non-NaN change %"

        # Print latest weekly changes
        latest = df.sort_values("timestamp").groupby("series_id").last()
        print("\nLatest weekly changes:")
        for series_id, row in latest.iterrows():
            print(
                f"  {series_id}: {row['change']:+,.0f} millions ({row['change_pct']:+.2f}%)"
            )

    @pytest.mark.asyncio
    async def test_registry_integration(self) -> None:
        """Test that Fed Custody collector is registered as 'fed_custody'."""
        from liquidity.collectors import registry

        assert "fed_custody" in registry.list_collectors()
        collector_cls = registry.get("fed_custody")
        assert collector_cls is FedCustodyCollector

        # Verify instantiation works
        collector = collector_cls()
        assert collector.name == "fed_custody"

    @pytest.mark.asyncio
    async def test_no_nan_values(self, custody_collector: FedCustodyCollector) -> None:
        """Test that ffill handles gaps and no NaN values in result."""
        df = await custody_collector.collect_all()

        # After ffill, there should be no NaN values in the value column
        assert df["value"].isna().sum() == 0, "Should have no NaN values after ffill"
        assert df["timestamp"].isna().sum() == 0, "Should have no NaN timestamps"
        assert df["series_id"].isna().sum() == 0, "Should have no NaN series IDs"


if __name__ == "__main__":
    # Run a quick sanity check
    async def main() -> None:
        collector = FedCustodyCollector()

        print("Fetching all custody holdings...")
        df = await collector.collect_all()
        print(f"Fetched {len(df)} rows")
        print(df.tail(10))

        print("\nCalculating weekly changes...")
        changes = await collector.get_weekly_change()
        print(changes.tail(10))

        # Get latest values
        latest = df.sort_values("timestamp").groupby("series_id").last()
        total = latest.loc["fed_custody_total", "value"]
        treasuries = latest.loc["fed_custody_treasuries", "value"]
        agencies = latest.loc["fed_custody_agencies", "value"]

        print("\nLatest values:")
        print(f"  Total: ${total / 1_000_000:.2f}T")
        print(
            f"  Treasuries: ${treasuries / 1_000_000:.2f}T ({treasuries / total * 100:.1f}%)"
        )
        print(
            f"  Agencies: ${agencies / 1_000_000:.2f}T ({agencies / total * 100:.1f}%)"
        )

    asyncio.run(main())
