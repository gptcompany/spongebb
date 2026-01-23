"""Integration tests for overnight rate collectors (ESTR, SONIA, CORRA).

These tests verify:
- Primary APIs work (estr.dev, BoC Valet)
- FRED fallbacks work (requires LIQUIDITY_FRED_API_KEY)
- Cached baselines return valid data when all sources fail

Run with: uv run pytest tests/integration/test_overnight_rates.py -v
"""

import os
from unittest.mock import patch

import pandas as pd
import pytest

from liquidity.collectors.overnight_rates import (
    CORRACollector,
    ESTRCollector,
    SONIACollector,
    calculate_rate_differentials,
)


# Marker for tests that require FRED API key
requires_fred_api = pytest.mark.skipif(
    not os.environ.get("LIQUIDITY_FRED_API_KEY"),
    reason="LIQUIDITY_FRED_API_KEY not set - skipping FRED integration tests",
)


class TestESTRCollector:
    """Tests for Euro Short-Term Rate (ESTR) collector."""

    @pytest.mark.asyncio
    async def test_estr_collector_estrdev_api(self) -> None:
        """Test ESTR collection via estr.dev API (no auth required)."""
        collector = ESTRCollector()
        df = await collector._collect_estrdev()

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) >= {"timestamp", "series_id", "source", "value", "unit"}

        # Verify data values
        assert df["series_id"].iloc[0] == "ESTR"
        assert df["source"].iloc[0] == "estr_dev"
        assert df["unit"].iloc[0] == "percent"

        # Verify reasonable value range (0-10%)
        value = df["value"].iloc[0]
        assert 0 <= value <= 10, f"ESTR value {value} out of expected range (0-10%)"

        print(f"\nESTR (estr.dev): {value:.3f}%")

    @pytest.mark.asyncio
    @requires_fred_api
    async def test_estr_collector_fred_fallback(self) -> None:
        """Test ESTR collection via FRED fallback."""
        collector = ESTRCollector()
        df = await collector._collect_fred(None, None)

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) >= {"timestamp", "series_id", "source", "value", "unit"}

        # Verify data values
        assert df["series_id"].iloc[0] == "ESTR"
        assert df["source"].iloc[0] == "fred"
        assert df["unit"].iloc[0] == "percent"

        # Verify reasonable value range (0-10%)
        latest_value = df["value"].iloc[-1]
        assert 0 <= latest_value <= 10, (
            f"ESTR value {latest_value} out of expected range"
        )

        print(f"\nESTR (FRED): {latest_value:.3f}%")

    @pytest.mark.asyncio
    async def test_estr_collector_baseline(self) -> None:
        """Test ESTR cached baseline returns valid data."""
        collector = ESTRCollector()
        df = collector._get_cached_baseline()

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert df["series_id"].iloc[0] == "ESTR"
        assert df["source"].iloc[0] == "cached_baseline"
        assert df["value"].iloc[0] == ESTRCollector.BASELINE_VALUE
        assert bool(df["stale"].iloc[0]) is True

        print(f"\nESTR (baseline): {df['value'].iloc[0]:.2f}%")

    @pytest.mark.asyncio
    async def test_estr_collect_with_fallback_chain(self) -> None:
        """Test full ESTR collection with fallback chain."""
        collector = ESTRCollector()
        df = await collector.collect()

        # Should ALWAYS return data due to fallback chain
        assert not df.empty, "DataFrame should not be empty"
        assert df["series_id"].iloc[0] == "ESTR"
        assert df["unit"].iloc[0] == "percent"

        # Verify reasonable value range
        value = df["value"].iloc[-1]
        assert 0 <= value <= 10, f"ESTR value {value} out of expected range"

    @pytest.mark.asyncio
    async def test_estr_collector_registered(self) -> None:
        """Test that ESTR collector is registered."""
        from liquidity.collectors import registry

        assert "estr" in registry.list_collectors()
        collector_cls = registry.get("estr")
        assert collector_cls is ESTRCollector


class TestSONIACollector:
    """Tests for Sterling Overnight Index Average (SONIA) collector."""

    @pytest.mark.asyncio
    @requires_fred_api
    async def test_sonia_collector_fred(self) -> None:
        """Test SONIA collection via FRED (primary source)."""
        collector = SONIACollector()
        df = await collector._collect_fred(None, None)

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) >= {"timestamp", "series_id", "source", "value", "unit"}

        # Verify data values
        assert df["series_id"].iloc[0] == "SONIA"
        assert df["source"].iloc[0] == "fred"
        assert df["unit"].iloc[0] == "percent"

        # Verify reasonable value range (0-10%)
        latest_value = df["value"].iloc[-1]
        assert 0 <= latest_value <= 10, (
            f"SONIA value {latest_value} out of expected range"
        )

        print(f"\nSONIA (FRED): {latest_value:.3f}%")

    @pytest.mark.asyncio
    async def test_sonia_collector_baseline(self) -> None:
        """Test SONIA cached baseline returns valid data."""
        collector = SONIACollector()
        df = collector._get_cached_baseline()

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert df["series_id"].iloc[0] == "SONIA"
        assert df["source"].iloc[0] == "cached_baseline"
        assert df["value"].iloc[0] == SONIACollector.BASELINE_VALUE
        assert bool(df["stale"].iloc[0]) is True

        print(f"\nSONIA (baseline): {df['value'].iloc[0]:.2f}%")

    @pytest.mark.asyncio
    async def test_sonia_collect_with_fallback_chain(self) -> None:
        """Test full SONIA collection with fallback chain."""
        collector = SONIACollector()

        # Mock FRED failure to test baseline fallback
        with patch.object(collector, "_collect_fred", side_effect=Exception("Mocked")):
            df = await collector.collect()

        # Should return cached baseline
        assert not df.empty, "DataFrame should not be empty"
        assert df["series_id"].iloc[0] == "SONIA"
        assert df["source"].iloc[0] == "cached_baseline"

    @pytest.mark.asyncio
    async def test_sonia_collector_registered(self) -> None:
        """Test that SONIA collector is registered."""
        from liquidity.collectors import registry

        assert "sonia" in registry.list_collectors()
        collector_cls = registry.get("sonia")
        assert collector_cls is SONIACollector


class TestCORRACollector:
    """Tests for Canadian Overnight Repo Rate Average (CORRA) collector."""

    @pytest.mark.asyncio
    async def test_corra_collector_valet_api(self) -> None:
        """Test CORRA collection via BoC Valet API (no auth required)."""
        collector = CORRACollector()
        df = await collector._collect_valet(recent=10)

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) >= {"timestamp", "series_id", "source", "value", "unit"}

        # Verify data values
        assert df["series_id"].iloc[0] == "CORRA"
        assert df["source"].iloc[0] == "boc_valet"
        assert df["unit"].iloc[0] == "percent"

        # Verify reasonable value range (0-10%)
        latest_value = df["value"].iloc[-1]
        assert 0 <= latest_value <= 10, (
            f"CORRA value {latest_value} out of expected range"
        )

        # Should have multiple observations
        assert len(df) >= 5, f"Expected at least 5 observations, got {len(df)}"

        print(f"\nCORRA (BoC Valet): {latest_value:.4f}%")
        print(f"  Observations fetched: {len(df)}")

    @pytest.mark.asyncio
    async def test_corra_collector_baseline(self) -> None:
        """Test CORRA cached baseline returns valid data."""
        collector = CORRACollector()
        df = collector._get_cached_baseline()

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert df["series_id"].iloc[0] == "CORRA"
        assert df["source"].iloc[0] == "cached_baseline"
        assert df["value"].iloc[0] == CORRACollector.BASELINE_VALUE
        assert bool(df["stale"].iloc[0]) is True

        print(f"\nCORRA (baseline): {df['value'].iloc[0]:.2f}%")

    @pytest.mark.asyncio
    async def test_corra_collect_with_fallback_chain(self) -> None:
        """Test full CORRA collection with fallback chain."""
        collector = CORRACollector()
        df = await collector.collect()

        # Should ALWAYS return data (BoC Valet is highly reliable)
        assert not df.empty, "DataFrame should not be empty"
        assert df["series_id"].iloc[0] == "CORRA"
        assert df["unit"].iloc[0] == "percent"

        # Verify reasonable value range
        value = df["value"].iloc[-1]
        assert 0 <= value <= 10, f"CORRA value {value} out of expected range"

    @pytest.mark.asyncio
    async def test_corra_collector_registered(self) -> None:
        """Test that CORRA collector is registered."""
        from liquidity.collectors import registry

        assert "corra" in registry.list_collectors()
        collector_cls = registry.get("corra")
        assert collector_cls is CORRACollector


class TestRateDifferentials:
    """Tests for rate differential calculation utility."""

    def test_calculate_rate_differentials_basic(self) -> None:
        """Test rate differential calculation with sample data."""
        # Create sample DataFrames
        dates = pd.date_range("2026-01-15", periods=5, freq="D")

        sofr_df = pd.DataFrame(
            {"timestamp": dates, "value": [4.35, 4.35, 4.36, 4.37, 4.38]}
        )
        estr_df = pd.DataFrame(
            {"timestamp": dates, "value": [2.90, 2.90, 2.91, 2.92, 2.93]}
        )
        sonia_df = pd.DataFrame(
            {"timestamp": dates, "value": [4.70, 4.70, 4.69, 4.68, 4.67]}
        )
        corra_df = pd.DataFrame(
            {"timestamp": dates, "value": [3.00, 3.00, 3.01, 3.02, 3.03]}
        )

        # Calculate differentials
        result = calculate_rate_differentials(sofr_df, estr_df, sonia_df, corra_df)

        # Verify structure
        assert not result.empty
        assert "timestamp" in result.columns
        assert "sofr_estr_spread" in result.columns
        assert "sofr_sonia_spread" in result.columns
        assert "sofr_corra_spread" in result.columns

        # Verify calculations (SOFR - other rate)
        # First row: 4.35 - 2.90 = 1.45, 4.35 - 4.70 = -0.35, 4.35 - 3.00 = 1.35
        assert abs(result["sofr_estr_spread"].iloc[0] - 1.45) < 0.01
        assert abs(result["sofr_sonia_spread"].iloc[0] - (-0.35)) < 0.01
        assert abs(result["sofr_corra_spread"].iloc[0] - 1.35) < 0.01

        print(f"\nRate differentials calculated: {len(result)} observations")
        print(f"  SOFR-ESTR spread: {result['sofr_estr_spread'].iloc[-1]:.2f}%")
        print(f"  SOFR-SONIA spread: {result['sofr_sonia_spread'].iloc[-1]:.2f}%")
        print(f"  SOFR-CORRA spread: {result['sofr_corra_spread'].iloc[-1]:.2f}%")

    def test_calculate_rate_differentials_misaligned_dates(self) -> None:
        """Test rate differential calculation with misaligned dates."""
        # Create DataFrames with different date ranges (simulating different schedules)
        sofr_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-15", "2026-01-16", "2026-01-17"]),
                "value": [4.35, 4.36, 4.37],
            }
        )
        estr_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    ["2026-01-15", "2026-01-17"]
                ),  # Missing 16th
                "value": [2.90, 2.92],
            }
        )
        sonia_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    ["2026-01-16", "2026-01-17"]
                ),  # Missing 15th
                "value": [4.70, 4.69],
            }
        )
        corra_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-15", "2026-01-16", "2026-01-17"]),
                "value": [3.00, 3.01, 3.02],
            }
        )

        # Calculate differentials (should handle misalignment with ffill)
        result = calculate_rate_differentials(sofr_df, estr_df, sonia_df, corra_df)

        # Should have results after forward fill
        assert not result.empty
        # After ffill, Jan 17 should have all values
        jan17 = result[result["timestamp"] == "2026-01-17"]
        if not jan17.empty:
            assert not pd.isna(jan17["sofr_estr_spread"].iloc[0])
            assert not pd.isna(jan17["sofr_sonia_spread"].iloc[0])
            assert not pd.isna(jan17["sofr_corra_spread"].iloc[0])

    def test_calculate_rate_differentials_empty_handling(self) -> None:
        """Test rate differential calculation handles empty result gracefully."""
        # Create non-overlapping DataFrames
        sofr_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-10"]),
                "value": [4.35],
            }
        )
        estr_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-20"]),
                "value": [2.90],
            }
        )
        sonia_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-25"]),
                "value": [4.70],
            }
        )
        corra_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-30"]),
                "value": [3.00],
            }
        )

        # Should not raise, but may return fewer rows after dropna
        result = calculate_rate_differentials(sofr_df, estr_df, sonia_df, corra_df)

        # Result structure should be valid even if empty
        assert "timestamp" in result.columns
        assert "sofr_estr_spread" in result.columns


class TestCollectorDataQuality:
    """Tests verifying data quality from live APIs."""

    @pytest.mark.asyncio
    async def test_estr_data_reasonable_range(self) -> None:
        """Test ESTR data is in reasonable range."""
        collector = ESTRCollector()
        df = await collector.collect()

        # ESTR typically 2-5% in current environment
        latest = df["value"].iloc[-1]
        assert 0 < latest < 10, f"ESTR rate {latest} out of expected range (0-10%)"

    @pytest.mark.asyncio
    async def test_corra_data_reasonable_range(self) -> None:
        """Test CORRA data is in reasonable range."""
        collector = CORRACollector()
        df = await collector.collect()

        # CORRA typically 2-6% in current environment
        latest = df["value"].iloc[-1]
        assert 0 < latest < 10, f"CORRA rate {latest} out of expected range (0-10%)"

    @pytest.mark.asyncio
    async def test_all_collectors_output_format(self) -> None:
        """Test all collectors return data in standard format."""
        collectors = [
            ESTRCollector(),
            SONIACollector(),
            CORRACollector(),
        ]

        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}

        for collector in collectors:
            # Use baseline to ensure we get data
            df = collector._get_cached_baseline()

            # Verify required columns (stale column is optional)
            assert expected_columns.issubset(set(df.columns)), (
                f"{collector.name} missing columns: {expected_columns - set(df.columns)}"
            )

            # Verify types
            assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
            # String columns can be object or StringDtype in pandas 2.x
            assert (
                pd.api.types.is_string_dtype(df["series_id"])
                or df["series_id"].dtype == object
            )
            assert (
                pd.api.types.is_string_dtype(df["source"])
                or df["source"].dtype == object
            )
            assert pd.api.types.is_numeric_dtype(df["value"])
            assert (
                pd.api.types.is_string_dtype(df["unit"]) or df["unit"].dtype == object
            )
