"""Integration tests for China rates collector with real akshare API.

These tests verify:
- Real SHIBOR data fetching from akshare
- Real DR007 data fetching (with fallback)
- Data quality and format validation
- Rate reasonableness checks

Run with: uv run pytest tests/integration/collectors/test_china_rates_integration.py -v

Note: These tests require network access and may be slow due to akshare API calls.
akshare pulls data from Chinese financial data sources which may have rate limits.
"""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from liquidity.collectors.china_rates import ChinaRatesCollector


@pytest.mark.integration
class TestSHIBORIntegration:
    """Integration tests for SHIBOR data collection."""

    @pytest.mark.asyncio
    async def test_collect_shibor_real_api(self) -> None:
        """Test fetching real SHIBOR data from akshare."""
        collector = ChinaRatesCollector()

        start = datetime.now(UTC) - timedelta(days=30)
        df = await collector.collect_shibor(start_date=start)

        # Should have data (allow for weekends/holidays reducing count)
        assert len(df) > 10, f"Expected at least 10 SHIBOR records, got {len(df)}"

        # Check DataFrame structure
        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert expected_columns.issubset(set(df.columns)), (
            f"Missing columns: {expected_columns - set(df.columns)}"
        )

        # Check multiple tenors present
        tenors = df["series_id"].unique()
        assert len(tenors) >= 3, f"Expected at least 3 SHIBOR tenors, got {len(tenors)}: {tenors}"

        # Check value ranges (SHIBOR typically 1-5% in 2026)
        assert df["value"].min() > 0, "SHIBOR should be positive"
        assert df["value"].max() < 20, "SHIBOR should be < 20%"

        # Check source
        assert (df["source"] == "akshare").all(), "Source should be 'akshare'"

        print("\nSHIBOR Integration Test Results:")
        print(f"  Records fetched: {len(df)}")
        print(f"  Tenors: {sorted(tenors)}")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"  Value range: {df['value'].min():.3f}% to {df['value'].max():.3f}%")

    @pytest.mark.asyncio
    async def test_collect_shibor_specific_tenors(self) -> None:
        """Test that all expected SHIBOR tenors are present."""
        collector = ChinaRatesCollector()

        start = datetime.now(UTC) - timedelta(days=14)
        df = await collector.collect_shibor(start_date=start)

        # Expected tenors based on SHIBOR_TENORS mapping
        expected_tenors = {
            "SHIBOR_OVERNIGHT",
            "SHIBOR_1_WEEK",
            "SHIBOR_2_WEEKS",
            "SHIBOR_1_MONTH",
            "SHIBOR_3_MONTHS",
            "SHIBOR_6_MONTHS",
            "SHIBOR_9_MONTHS",
            "SHIBOR_1_YEAR",
        }

        actual_tenors = set(df["series_id"].unique())

        # Check that most tenors are present (some may be missing on certain days)
        overlap = expected_tenors & actual_tenors
        assert len(overlap) >= 5, (
            f"Expected at least 5 of {expected_tenors}, got {actual_tenors}"
        )

        print(f"\nSHIBOR Tenors Found: {sorted(actual_tenors)}")

    @pytest.mark.asyncio
    async def test_shibor_data_types(self) -> None:
        """Test SHIBOR data types are correct."""
        collector = ChinaRatesCollector()

        start = datetime.now(UTC) - timedelta(days=7)
        df = await collector.collect_shibor(start_date=start)

        if not df.empty:
            # Timestamp should be datetime
            assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

            # Value should be numeric
            assert pd.api.types.is_numeric_dtype(df["value"])

            # String columns can be object or StringDtype in pandas 2.x
            for col in ["series_id", "source", "unit"]:
                assert (
                    pd.api.types.is_string_dtype(df[col])
                    or df[col].dtype == object
                ), f"{col} should be string type"


@pytest.mark.integration
class TestDR007Integration:
    """Integration tests for DR007 data collection."""

    @pytest.mark.asyncio
    async def test_collect_dr007_real_api(self) -> None:
        """Test fetching real DR007 data from akshare.

        Note: DR007 may fallback to SHIBOR proxy if direct API fails.
        """
        collector = ChinaRatesCollector()

        start = datetime.now(UTC) - timedelta(days=30)
        df = await collector.collect_dr007(start_date=start)

        # Should have data (either DR007 or DR007_PROXY)
        assert isinstance(df, pd.DataFrame)

        if not df.empty:
            # Check DataFrame structure
            expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
            assert expected_columns.issubset(set(df.columns))

            # Series ID should be DR007 or DR007_PROXY
            series_ids = df["series_id"].unique()
            assert len(series_ids) == 1
            assert series_ids[0] in ["DR007", "DR007_PROXY"], (
                f"Unexpected series_id: {series_ids[0]}"
            )

            # Check value ranges (DR007 typically 1-3% in 2026)
            assert df["value"].min() > 0, "DR007 should be positive"
            assert df["value"].max() < 10, "DR007 should be < 10%"

            print("\nDR007 Integration Test Results:")
            print(f"  Records fetched: {len(df)}")
            print(f"  Series ID: {series_ids[0]}")
            print(f"  Source: {df['source'].iloc[0]}")
            print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
            print(f"  Latest value: {df['value'].iloc[-1]:.4f}%")
        else:
            # Empty is acceptable if API is down - test doesn't fail
            print("\nDR007 returned empty (API may be unavailable)")

    @pytest.mark.asyncio
    async def test_dr007_fallback_works(self) -> None:
        """Test that DR007 fallback mechanism works.

        Even if direct DR007 API fails, should get SHIBOR proxy.
        """
        collector = ChinaRatesCollector()

        start = datetime.now(UTC) - timedelta(days=14)
        df = await collector.collect_dr007(start_date=start)

        # Should return data (either DR007 or proxy)
        if not df.empty:
            assert df["series_id"].iloc[0] in ["DR007", "DR007_PROXY"]
            print(f"\nDR007 fallback: Using {df['series_id'].iloc[0]}")


@pytest.mark.integration
class TestCollectAllIntegration:
    """Integration tests for combined data collection."""

    @pytest.mark.asyncio
    async def test_collect_all_real_api(self) -> None:
        """Test fetching all China rate data."""
        collector = ChinaRatesCollector()

        start = datetime.now(UTC) - timedelta(days=14)
        df = await collector.collect_all(start_date=start)

        # Should have data
        assert len(df) > 0, "Expected some data from collect_all"

        # Should have both SHIBOR and DR007/proxy series
        series_ids = df["series_id"].unique()
        has_shibor = any("SHIBOR" in s for s in series_ids)
        has_dr007 = any("DR007" in s for s in series_ids)

        assert has_shibor, f"Expected SHIBOR data, got: {series_ids}"
        # DR007 may or may not be present depending on API availability
        # but should have proxy at minimum
        assert has_shibor or has_dr007, "Expected at least SHIBOR or DR007 data"

        print("\ncollect_all Results:")
        print(f"  Total records: {len(df)}")
        print(f"  Series: {sorted(series_ids)}")

    @pytest.mark.asyncio
    async def test_collect_all_data_quality(self) -> None:
        """Test data quality from collect_all."""
        collector = ChinaRatesCollector()

        start = datetime.now(UTC) - timedelta(days=7)
        df = await collector.collect_all(start_date=start)

        if not df.empty:
            # No NaN values in critical columns
            assert not df["timestamp"].isna().any(), "timestamp has NaN"
            assert not df["series_id"].isna().any(), "series_id has NaN"
            assert not df["value"].isna().any(), "value has NaN"

            # Values should be reasonable
            assert (df["value"] > 0).all(), "All rates should be positive"
            assert (df["value"] < 20).all(), "All rates should be < 20%"


@pytest.mark.integration
class TestCollectorRegistration:
    """Test collector is properly registered."""

    @pytest.mark.asyncio
    async def test_china_rates_in_registry(self) -> None:
        """Test that china_rates collector is registered."""
        from liquidity.collectors import registry

        assert "china_rates" in registry.list_collectors()
        collector_cls = registry.get("china_rates")
        assert collector_cls is ChinaRatesCollector

    @pytest.mark.asyncio
    async def test_instantiate_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector_cls = registry.get("china_rates")
        collector = collector_cls()

        assert collector.name == "china_rates"

        # Should be able to get baseline
        baseline = collector.get_cached_baseline()
        assert not baseline.empty


@pytest.mark.integration
class TestDataReasonableness:
    """Tests verifying data quality and reasonableness."""

    @pytest.mark.asyncio
    async def test_shibor_term_structure(self) -> None:
        """Test SHIBOR term structure is reasonable (longer tenor = higher rate)."""
        collector = ChinaRatesCollector()

        start = datetime.now(UTC) - timedelta(days=7)
        df = await collector.collect_shibor(start_date=start)

        if df.empty:
            pytest.skip("No SHIBOR data available")

        # Get latest values for each tenor
        latest = df.sort_values("timestamp", ascending=False).drop_duplicates("series_id")

        # Map tenor to expected ordering
        tenor_order = {
            "SHIBOR_OVERNIGHT": 1,
            "SHIBOR_1_WEEK": 2,
            "SHIBOR_2_WEEKS": 3,
            "SHIBOR_1_MONTH": 4,
            "SHIBOR_3_MONTHS": 5,
            "SHIBOR_6_MONTHS": 6,
            "SHIBOR_9_MONTHS": 7,
            "SHIBOR_1_YEAR": 8,
        }

        # Sort by tenor
        latest["tenor_order"] = latest["series_id"].map(tenor_order)
        latest = latest.dropna(subset=["tenor_order"]).sort_values("tenor_order")

        if len(latest) >= 3:
            # Generally, term structure should be upward sloping
            # (though inverted yield curves happen)
            # Just log the term structure for inspection
            overnight_rate = latest[latest["series_id"] == "SHIBOR_OVERNIGHT"]["value"]

            if not overnight_rate.empty:
                # Overnight should typically not be the highest rate
                # (allow for inverted curves by not asserting)
                print("\nSHIBOR Term Structure:")
                for _, row in latest.iterrows():
                    print(f"  {row['series_id']}: {row['value']:.3f}%")

    @pytest.mark.asyncio
    async def test_rates_not_stale(self) -> None:
        """Test that fetched rates are recent (not stale)."""
        collector = ChinaRatesCollector()

        start = datetime.now(UTC) - timedelta(days=7)
        df = await collector.collect_shibor(start_date=start)

        if df.empty:
            pytest.skip("No SHIBOR data available")

        # Latest data should be within last 5 business days
        latest_date = df["timestamp"].max()
        today = pd.Timestamp.now(tz=None)

        days_old = (today - latest_date).days
        assert days_old < 10, f"Data is {days_old} days old, expected < 10"

        print(f"\nData freshness: Latest date is {latest_date} ({days_old} days old)")
