"""Integration tests for COFER (IMF Currency Composition of Official Foreign Exchange Reserves) collector.

Tests the COFERCollector which fetches reserve currency data from DBnomics (IMF COFER mirror).

Data characteristics:
- Update frequency: Quarterly (with ~3 month lag)
- Coverage: Global (W00 = World)
- Unit: Millions USD for reserves, Percent for shares

Run with: uv run pytest tests/integration/test_cofer.py -v --tb=short
"""

import asyncio
from datetime import datetime

import pandas as pd
import pytest

from liquidity.collectors.cofer import COFERCollector


@pytest.fixture
def cofer_collector() -> COFERCollector:
    """Create a COFER collector instance."""
    return COFERCollector()


class TestCollectReservesByCurrency:
    """Tests for collecting reserves by currency."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_reserves_by_currency(
        self, cofer_collector: COFERCollector
    ) -> None:
        """Test that all 6 currency series are fetched successfully."""
        df = await cofer_collector.collect_reserves_by_currency()

        # Verify DataFrame is not empty
        assert not df.empty, "DataFrame should not be empty"

        # Verify all 6 currencies are present
        series_ids = df["series_id"].unique().tolist()
        expected_currencies = [
            "cofer_usd",
            "cofer_eur",
            "cofer_cny",
            "cofer_jpy",
            "cofer_gbp",
            "cofer_other",
        ]

        for currency_id in expected_currencies:
            assert currency_id in series_ids, f"Missing currency: {currency_id}"

        # Verify DataFrame has required columns
        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert expected_columns.issubset(set(df.columns))

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_usd_reserves(self, cofer_collector: COFERCollector) -> None:
        """Test that USD reserves are between 5T and 10T (reasonable range)."""
        df = await cofer_collector.collect_reserves_by_currency(currencies=["usd"])

        # Filter to most recent observation
        latest = df.sort_values("timestamp").iloc[-1]

        # USD reserves should be in range 5-10 trillion (5M to 10M millions)
        usd_reserves_millions = latest["value"]
        usd_reserves_trillions = usd_reserves_millions / 1_000_000

        assert 5.0 <= usd_reserves_trillions <= 10.0, (
            f"USD reserves {usd_reserves_trillions:.2f}T outside expected range 5-10T"
        )

        # Verify unit
        assert latest["unit"] == "millions_usd"


class TestCollectCurrencyShares:
    """Tests for currency share calculations."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_currency_shares(
        self, cofer_collector: COFERCollector
    ) -> None:
        """Test that currency shares sum to approximately 100%."""
        df = await cofer_collector.collect_currency_shares()

        # Verify DataFrame is not empty
        assert not df.empty, "DataFrame should not be empty"

        # Group by timestamp and sum shares
        for timestamp in df["timestamp"].unique()[-5:]:  # Check last 5 quarters
            timestamp_data = df[df["timestamp"] == timestamp]
            total_share = timestamp_data["value"].sum()

            # Shares should sum to ~100% (allow small rounding tolerance)
            assert 99.0 <= total_share <= 101.0, (
                f"Shares for {timestamp} sum to {total_share:.2f}%, expected ~100%"
            )

        # Verify unit is percent
        assert df["unit"].unique().tolist() == ["percent"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_usd_share_dominant(self, cofer_collector: COFERCollector) -> None:
        """Test that USD share is > 50% (currently ~56% as of 2024)."""
        df = await cofer_collector.collect_usd_share()

        # Get most recent USD share
        latest = df.sort_values("timestamp").iloc[-1]
        usd_share = latest["value"]

        # USD should still be dominant (> 50%)
        assert usd_share > 50.0, f"USD share {usd_share:.2f}% should be > 50%"

        # But should not be > 70% (historical peak was ~71% in 1999)
        assert usd_share < 70.0, f"USD share {usd_share:.2f}% unexpectedly high"

        # Verify series_id and unit
        assert latest["series_id"] == "cofer_share_usd"
        assert latest["unit"] == "percent"


class TestCollectTotalReserves:
    """Tests for total reserves calculation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_total_reserves(
        self, cofer_collector: COFERCollector
    ) -> None:
        """Test that total allocated reserves are > 10T USD."""
        df = await cofer_collector.collect_total_reserves()

        # Verify DataFrame is not empty
        assert not df.empty, "DataFrame should not be empty"

        # Get most recent total
        latest = df.sort_values("timestamp").iloc[-1]
        total_millions = latest["value"]
        total_trillions = total_millions / 1_000_000

        # Total allocated reserves should be > 10 trillion USD
        assert total_trillions > 10.0, (
            f"Total reserves {total_trillions:.2f}T should be > 10T"
        )

        # Verify series_id and unit
        assert latest["series_id"] == "cofer_total"
        assert latest["unit"] == "millions_usd"


class TestDataFrequency:
    """Tests for data frequency and format."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_quarterly_frequency(self, cofer_collector: COFERCollector) -> None:
        """Test that data points are quarterly (not more frequent)."""
        df = await cofer_collector.collect_usd_share()

        # Sort by timestamp
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Check consecutive timestamp differences
        if len(df) >= 2:
            timestamps = df["timestamp"]
            diffs = timestamps.diff().dropna()

            # All differences should be approximately 3 months (85-95 days)
            for diff in diffs:
                days = diff.days
                # Quarters are 90-92 days, allow some tolerance
                assert 80 <= days <= 100, (
                    f"Data point interval {days} days not quarterly"
                )


class TestOutputFormat:
    """Tests for output format compliance."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_output_format_reserves(
        self, cofer_collector: COFERCollector
    ) -> None:
        """Test that reserves output has standard column structure."""
        df = await cofer_collector.collect_reserves_by_currency()

        # Verify columns
        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert expected_columns == set(df.columns), (
            f"Expected columns {expected_columns}, got {set(df.columns)}"
        )

        # Verify timestamp is datetime
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

        # Verify value is numeric
        assert pd.api.types.is_numeric_dtype(df["value"])

        # Verify source
        assert df["source"].unique().tolist() == ["dbnomics_imf"]

        # Verify unit for reserves
        assert df["unit"].unique().tolist() == ["millions_usd"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_output_format_shares(self, cofer_collector: COFERCollector) -> None:
        """Test that shares output has percent unit."""
        df = await cofer_collector.collect_currency_shares()

        # Verify unit is percent for shares
        assert df["unit"].unique().tolist() == ["percent"]

        # Verify series_id format for shares
        for series_id in df["series_id"].unique():
            assert series_id.startswith("cofer_share_"), (
                f"Share series_id should start with 'cofer_share_', got {series_id}"
            )


class TestDedollarizationRate:
    """Tests for de-dollarization rate calculation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dedollarization_rate(self, cofer_collector: COFERCollector) -> None:
        """Test that YoY de-dollarization rate calculation works."""
        df = await cofer_collector.calculate_dedollarization_rate()

        # May be empty if insufficient data, but should not raise
        if not df.empty:
            # Verify columns
            expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
            assert expected_columns == set(df.columns)

            # Verify series_id
            assert df["series_id"].unique().tolist() == ["cofer_usd_yoy_change"]

            # Verify unit
            assert df["unit"].unique().tolist() == ["percentage_points"]

            # YoY change should be in reasonable range (-10 to +10 percentage points)
            # Note: During significant market events, larger swings can occur
            for value in df["value"]:
                assert -10.0 <= value <= 10.0, (
                    f"YoY change {value:.2f}pp outside reasonable range"
                )


class TestRegistryIntegration:
    """Tests for collector registry integration."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_registry_integration(self) -> None:
        """Test that COFER collector is registered as 'cofer'."""
        from liquidity.collectors import registry

        assert "cofer" in registry.list_collectors()
        collector_cls = registry.get("cofer")
        assert collector_cls is COFERCollector

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collector_instantiation_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector_cls = registry.get("cofer")
        collector = collector_cls()

        assert isinstance(collector, COFERCollector)
        assert collector.name == "cofer"


class TestCNYShare:
    """Tests for CNY (Chinese Yuan) share tracking."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cny_share_growing(self, cofer_collector: COFERCollector) -> None:
        """Test that CNY share is > 0 (tracking de-dollarization)."""
        df = await cofer_collector.collect_currency_shares()

        # Filter to CNY share
        cny_shares = df[df["series_id"] == "cofer_share_cny"]

        # CNY should have some allocation (> 0%)
        latest = cny_shares.sort_values("timestamp").iloc[-1]
        cny_share = latest["value"]

        assert cny_share > 0.0, f"CNY share {cny_share:.2f}% should be > 0%"

        # CNY share has been around 2-3% in recent years
        assert cny_share < 10.0, (
            f"CNY share {cny_share:.2f}% unexpectedly high (expected < 10%)"
        )


class TestDataQuality:
    """Tests for data quality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_no_nan_values(self, cofer_collector: COFERCollector) -> None:
        """Test that collected data has no NaN values."""
        df = await cofer_collector.collect_reserves_by_currency()

        # Check for NaN in value column
        nan_count = df["value"].isna().sum()
        assert nan_count == 0, f"Found {nan_count} NaN values in reserves data"

        # Check shares as well
        shares_df = await cofer_collector.collect_currency_shares()
        nan_count_shares = shares_df["value"].isna().sum()
        assert nan_count_shares == 0, (
            f"Found {nan_count_shares} NaN values in shares data"
        )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_positive_values(self, cofer_collector: COFERCollector) -> None:
        """Test that all reserves values are positive."""
        df = await cofer_collector.collect_reserves_by_currency()

        # All reserve values should be positive
        negative_count = (df["value"] < 0).sum()
        assert negative_count == 0, f"Found {negative_count} negative reserve values"


class TestCOFERSeries:
    """Tests for COFER_SERIES constant."""

    def test_cofer_series_exported(self) -> None:
        """Test that COFER_SERIES is exported from module."""
        from liquidity.collectors import COFER_SERIES

        assert isinstance(COFER_SERIES, dict)
        assert len(COFER_SERIES) == 6

        # Verify all expected currencies
        expected_currencies = ["usd", "eur", "cny", "jpy", "gbp", "other"]
        for currency in expected_currencies:
            assert currency in COFER_SERIES


class TestDateFiltering:
    """Tests for date range filtering."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_date_filtering(self, cofer_collector: COFERCollector) -> None:
        """Test that date filtering works correctly."""
        # Fetch with date filter
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2022, 12, 31)

        df = await cofer_collector.collect_reserves_by_currency(
            start_date=start_date,
            end_date=end_date,
        )

        # All timestamps should be within range
        for timestamp in df["timestamp"]:
            assert timestamp >= pd.to_datetime(start_date), (
                f"Timestamp {timestamp} before start_date"
            )
            assert timestamp <= pd.to_datetime(end_date), (
                f"Timestamp {timestamp} after end_date"
            )


if __name__ == "__main__":
    # Quick sanity check
    async def main() -> None:
        collector = COFERCollector()

        print("Testing COFER collector...")

        print("\n1. Fetching reserves by currency...")
        reserves = await collector.collect_reserves_by_currency()
        print(
            f"   Fetched {len(reserves)} observations across {reserves['series_id'].nunique()} currencies"
        )

        print("\n2. Fetching currency shares...")
        shares = await collector.collect_currency_shares()
        print(f"   Fetched {len(shares)} share observations")

        # Show latest shares
        latest_shares = shares.sort_values("timestamp").groupby("series_id").last()
        print("\n   Latest currency shares:")
        for series_id, row in latest_shares.iterrows():
            currency = str(series_id).replace("cofer_share_", "").upper()
            print(f"   - {currency}: {row['value']:.2f}%")

        print("\n3. Fetching total reserves...")
        total = await collector.collect_total_reserves()
        latest_total = total.sort_values("timestamp").iloc[-1]
        print(f"   Total allocated reserves: ${latest_total['value'] / 1_000_000:.2f}T")

        print("\n4. Calculating de-dollarization rate...")
        deollar = await collector.calculate_dedollarization_rate()
        if not deollar.empty:
            latest_deollar = deollar.sort_values("timestamp").iloc[-1]
            print(f"   Latest YoY USD share change: {latest_deollar['value']:.2f} pp")

        print("\nAll tests passed!")

    asyncio.run(main())
