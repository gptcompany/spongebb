"""Integration tests for SOFR collector.

Tests the multi-tier fallback:
- Tier 1: NY Fed Markets API (primary, no auth required)
- Tier 2: FRED fallback (requires LIQUIDITY_FRED_API_KEY)
- Tier 3: Cached baseline (guaranteed)

Run with: uv run pytest tests/integration/test_sofr_collector.py -v
"""

import asyncio
import os
from unittest.mock import patch

import pytest

from liquidity.collectors.sofr import SOFRCollector


@pytest.fixture
def sofr_collector() -> SOFRCollector:
    """Create a SOFR collector instance."""
    return SOFRCollector()


class TestSOFRCollectorNYFed:
    """Tests for NY Fed API (Tier 1) - always available, no auth."""

    @pytest.mark.asyncio
    async def test_sofr_collector_nyfed_api(
        self, sofr_collector: SOFRCollector
    ) -> None:
        """Test NY Fed API directly (always works, no auth required)."""
        # Fetch last 7 days of SOFR data
        df = await sofr_collector._collect_via_nyfed(days=7)

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {
            "timestamp",
            "series_id",
            "source",
            "value",
            "unit",
        }

        # Verify series_id
        assert df["series_id"].unique().tolist() == ["SOFR"]

        # Verify source is 'nyfed'
        assert df["source"].unique().tolist() == ["nyfed"]

        # Verify unit
        assert df["unit"].unique().tolist() == ["percent"]

        # Verify value is in reasonable range (0-10 percent)
        assert df["value"].min() >= 0, "SOFR rate should be >= 0"
        assert df["value"].max() <= 10, "SOFR rate should be <= 10%"

        # Verify we got some data points
        assert len(df) >= 1, "Should have at least 1 data point"

    @pytest.mark.asyncio
    async def test_sofr_collector_collect_latest(
        self, sofr_collector: SOFRCollector
    ) -> None:
        """Test collect_latest convenience method."""
        df = await sofr_collector.collect_latest()

        # Should return exactly 1 row
        assert len(df) == 1, "collect_latest should return exactly 1 row"

        # Verify structure
        assert "timestamp" in df.columns
        assert "series_id" in df.columns
        assert "value" in df.columns
        assert df["series_id"].iloc[0] == "SOFR"

    @pytest.mark.asyncio
    async def test_sofr_collector_full_collect(
        self, sofr_collector: SOFRCollector
    ) -> None:
        """Test full collect method (should use NY Fed as primary)."""
        df = await sofr_collector.collect(days=7)

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert "timestamp" in df.columns
        assert "series_id" in df.columns
        assert "source" in df.columns
        assert "value" in df.columns
        assert "unit" in df.columns

        # Should prefer nyfed source (Tier 1)
        assert df["source"].iloc[0] == "nyfed"

        # Verify series_id is SOFR
        assert df["series_id"].iloc[0] == "SOFR"


class TestSOFRCollectorFallback:
    """Tests for fallback behavior (Tier 2 and Tier 3)."""

    @pytest.mark.asyncio
    async def test_sofr_collector_fred_fallback(
        self, sofr_collector: SOFRCollector
    ) -> None:
        """Test FRED fallback when NY Fed fails."""
        # Skip if no FRED API key
        if not os.environ.get("LIQUIDITY_FRED_API_KEY"):
            pytest.skip("LIQUIDITY_FRED_API_KEY not set - skipping FRED fallback test")

        # Mock NY Fed to fail
        with patch.object(
            sofr_collector,
            "_collect_via_nyfed",
            side_effect=Exception("Simulated NY Fed failure"),
        ):
            df = await sofr_collector.collect()

            # Should fall back to FRED
            assert not df.empty, "DataFrame should not be empty after FRED fallback"
            assert df["source"].iloc[0] == "fred"
            assert df["series_id"].iloc[0] == "SOFR"
            assert df["unit"].iloc[0] == "percent"

    @pytest.mark.asyncio
    async def test_sofr_collector_baseline_fallback(
        self, sofr_collector: SOFRCollector
    ) -> None:
        """Test cached baseline when all sources fail."""
        # Mock both NY Fed and FRED to fail
        with patch.object(
            sofr_collector,
            "_collect_via_nyfed",
            side_effect=Exception("Simulated NY Fed failure"),
        ):
            with patch.object(
                sofr_collector,
                "_collect_via_fred",
                side_effect=Exception("Simulated FRED failure"),
            ):
                df = await sofr_collector.collect()

                # Should return cached baseline
                assert not df.empty, (
                    "DataFrame should not be empty with cached baseline"
                )
                assert len(df) == 1, "Cached baseline should have exactly 1 row"
                assert df["source"].iloc[0] == "cached_baseline"
                assert df["series_id"].iloc[0] == "SOFR"
                assert df["unit"].iloc[0] == "percent"

                # Verify baseline value matches class constant
                assert df["value"].iloc[0] == SOFRCollector.BASELINE_VALUE
                assert "stale" in df.columns
                assert df["stale"].iloc[0] == True  # noqa: E712

    @pytest.mark.asyncio
    async def test_sofr_collector_always_returns_data(
        self, sofr_collector: SOFRCollector
    ) -> None:
        """Test that collect() always returns data (never raises on data fetch)."""
        # Even with everything mocked to fail, we should get baseline
        with patch.object(
            sofr_collector,
            "_collect_via_nyfed",
            side_effect=Exception("Network error"),
        ):
            with patch.object(
                sofr_collector,
                "_collect_via_fred",
                side_effect=Exception("API key invalid"),
            ):
                df = await sofr_collector.collect()

                # Should always return non-empty DataFrame
                assert not df.empty
                assert df["source"].iloc[0] == "cached_baseline"


class TestSOFRCollectorRegistry:
    """Tests for collector registry integration."""

    @pytest.mark.asyncio
    async def test_collector_registered(self) -> None:
        """Test that SOFR collector is registered in the registry."""
        from liquidity.collectors import registry

        assert "sofr" in registry.list_collectors()
        collector_cls = registry.get("sofr")
        assert collector_cls is SOFRCollector

    @pytest.mark.asyncio
    async def test_collector_instantiation_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector_cls = registry.get("sofr")
        collector = collector_cls()

        assert isinstance(collector, SOFRCollector)
        assert collector.name == "sofr"


class TestSOFRDataValidation:
    """Tests for data validation and format."""

    @pytest.mark.asyncio
    async def test_sofr_data_columns(self, sofr_collector: SOFRCollector) -> None:
        """Test that output has correct column structure."""
        df = await sofr_collector.collect(days=3)

        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert expected_columns.issubset(set(df.columns))

    @pytest.mark.asyncio
    async def test_sofr_timestamp_is_datetime(
        self, sofr_collector: SOFRCollector
    ) -> None:
        """Test that timestamp column is datetime type."""
        import pandas as pd

        df = await sofr_collector.collect(days=3)

        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

    @pytest.mark.asyncio
    async def test_sofr_value_is_numeric(self, sofr_collector: SOFRCollector) -> None:
        """Test that value column is numeric."""
        import pandas as pd

        df = await sofr_collector.collect(days=3)

        assert pd.api.types.is_numeric_dtype(df["value"])


if __name__ == "__main__":
    # Quick sanity check
    async def main() -> None:
        collector = SOFRCollector()

        print("Testing NY Fed API (Tier 1)...")
        df = await collector._collect_via_nyfed(days=7)
        print(f"Fetched {len(df)} rows from NY Fed")
        print(df.head())
        print(f"\nLatest SOFR rate: {df['value'].iloc[-1]:.2f}%")

    asyncio.run(main())
