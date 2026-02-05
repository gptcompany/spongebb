"""Integration tests for cross-currency basis collector with real API.

Tests against the live ECB SDW API (no authentication required).
Run with: uv run pytest tests/integration/collectors/test_xccy_basis_integration.py -v

Note: These tests make real HTTP requests to the ECB API.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from liquidity.collectors.xccy_basis import (
    STRESS_THRESHOLDS,
    XCcyBasisCollector,
)


@pytest.fixture
def xccy_collector() -> XCcyBasisCollector:
    """Create a cross-currency basis collector instance."""
    return XCcyBasisCollector()


class TestXCcyBasisIntegration:
    """Integration tests for XCcyBasisCollector."""

    @pytest.mark.asyncio
    async def test_collect_returns_data(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test fetching cross-currency basis data.

        The collector has multiple fallback sources, so it should
        always return data (even if just cached baseline).
        """
        try:
            start = datetime.now(UTC) - timedelta(days=180)
            df = await xccy_collector.collect(start_date=start)

            # Should have data (from any source)
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0

            # Check data structure
            expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
            assert expected_columns.issubset(set(df.columns)), (
                f"Missing columns: {expected_columns - set(df.columns)}"
            )

            # Verify series_id format
            assert all(
                s.startswith("XCCY_EURUSD_") for s in df["series_id"]
            ), "All series should be XCCY_EURUSD_*"

            # Verify unit
            assert (df["unit"] == "bps").all()

        finally:
            await xccy_collector.close()

    @pytest.mark.asyncio
    async def test_collect_with_different_tenors(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test collection with different tenor parameters."""
        try:
            start = datetime.now(UTC) - timedelta(days=90)

            for tenor in ["3M", "1Y"]:
                df = await xccy_collector.collect(start_date=start, tenor=tenor)

                assert isinstance(df, pd.DataFrame)
                # Should get data or cached baseline
                assert len(df) > 0

        finally:
            await xccy_collector.close()

    @pytest.mark.asyncio
    async def test_collect_latest(self, xccy_collector: XCcyBasisCollector) -> None:
        """Test collect_latest returns single row."""
        try:
            df = await xccy_collector.collect_latest()

            assert isinstance(df, pd.DataFrame)
            assert len(df) <= 1  # At most one row

            if len(df) == 1:
                # Verify timestamp is recent
                latest_ts = df["timestamp"].iloc[0]
                age = datetime.now(UTC) - latest_ts.to_pydatetime().replace(tzinfo=UTC)
                # Should be within last year (allowing for monthly data)
                assert age.days <= 400, f"Data is {age.days} days old"

        finally:
            await xccy_collector.close()


class TestStressLevels:
    """Integration tests for stress level interpretation."""

    def test_stress_classification_thresholds(self) -> None:
        """Test stress classification at boundary values."""
        # Boundary tests
        assert XCcyBasisCollector.classify_stress(0.001) == "normal"
        assert XCcyBasisCollector.classify_stress(0) == "mild"
        assert XCcyBasisCollector.classify_stress(-0.001) == "mild"
        assert XCcyBasisCollector.classify_stress(-10) == "moderate"
        assert XCcyBasisCollector.classify_stress(-30) == "severe"

    def test_historical_crisis_levels(self) -> None:
        """Test stress levels against historical crisis data."""
        # Global Financial Crisis 2008: basis reached ~-100 bps
        assert XCcyBasisCollector.classify_stress(-100) == "severe"

        # European Debt Crisis 2011-2012: basis reached ~-60 bps
        assert XCcyBasisCollector.classify_stress(-60) == "severe"

        # COVID-19 March 2020: basis reached ~-50 bps
        assert XCcyBasisCollector.classify_stress(-50) == "severe"

        # Normal market conditions: around -5 to -15 bps
        assert XCcyBasisCollector.classify_stress(-10) == "moderate"
        assert XCcyBasisCollector.classify_stress(-5) == "mild"

    @pytest.mark.asyncio
    async def test_current_stress_level(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test current stress level is reasonable."""
        try:
            df = await xccy_collector.collect_latest()

            if len(df) > 0 and "stale" not in df.columns:
                # Only test if we got fresh data
                latest_value = df["value"].iloc[0]
                stress_level = XCcyBasisCollector.classify_stress(latest_value)

                # Stress level should be one of the valid levels
                assert stress_level in ["normal", "mild", "moderate", "severe"]

                # Log for informational purposes
                print(f"Current basis: {latest_value:.1f} bps ({stress_level})")

        finally:
            await xccy_collector.close()


class TestDataQuality:
    """Integration tests for data quality."""

    @pytest.mark.asyncio
    async def test_basis_value_range(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test basis values are in realistic range."""
        try:
            df = await xccy_collector.collect()

            if not df.empty and df["source"].iloc[0] != "cached_baseline":
                # Basis typically ranges from -200 to +50 bps historically
                # During extreme crises could go lower
                assert df["value"].min() > -300, "Basis seems unrealistically negative"
                assert df["value"].max() < 100, "Basis seems unrealistically positive"

        finally:
            await xccy_collector.close()

    @pytest.mark.asyncio
    async def test_timestamps_are_valid(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test timestamps are valid datetime objects."""
        try:
            df = await xccy_collector.collect()

            if not df.empty:
                # Timestamp should be datetime type
                assert pd.api.types.is_datetime64_any_dtype(df["timestamp"]), (
                    "timestamp should be datetime type"
                )

                # All timestamps should be in the past
                for ts in df["timestamp"]:
                    assert ts.to_pydatetime().replace(tzinfo=UTC) <= datetime.now(UTC)

        finally:
            await xccy_collector.close()

    @pytest.mark.asyncio
    async def test_data_is_sorted(self, xccy_collector: XCcyBasisCollector) -> None:
        """Test data is sorted by timestamp ascending."""
        try:
            df = await xccy_collector.collect()

            if len(df) > 1:
                timestamps = df["timestamp"].tolist()
                assert timestamps == sorted(timestamps), "Data should be sorted"

        finally:
            await xccy_collector.close()


class TestFallbackBehavior:
    """Integration tests for fallback behavior."""

    @pytest.mark.asyncio
    async def test_always_returns_data(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test collector always returns data (due to cached baseline)."""
        try:
            df = await xccy_collector.collect()

            # Should never return empty due to cached baseline
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0

        finally:
            await xccy_collector.close()

    @pytest.mark.asyncio
    async def test_cached_baseline_is_valid(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test cached baseline has valid data."""
        baseline = xccy_collector._get_cached_baseline()

        assert len(baseline) == 1
        assert baseline["source"].iloc[0] == "cached_baseline"
        assert baseline["stale"].iloc[0] is True

        # Baseline value should be reasonable
        value = baseline["value"].iloc[0]
        assert -50 < value < 0, "Baseline should be in typical range"


class TestCollectorResilience:
    """Integration tests for collector resilience."""

    @pytest.mark.asyncio
    async def test_close_and_reopen(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test collector can be closed and reopened."""
        try:
            # First fetch
            df1 = await xccy_collector.collect()
            assert len(df1) > 0

            # Close
            await xccy_collector.close()

            # Second fetch (should create new client)
            df2 = await xccy_collector.collect()
            assert len(df2) > 0

        finally:
            await xccy_collector.close()

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test collector handles concurrent requests."""
        try:
            # Run multiple requests concurrently
            tasks = [
                xccy_collector.collect(),
                xccy_collector.collect_latest(),
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 2
            assert all(isinstance(r, pd.DataFrame) for r in results)

        finally:
            await xccy_collector.close()


class TestSourceAttribution:
    """Integration tests for source attribution."""

    @pytest.mark.asyncio
    async def test_source_is_attributed(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test all rows have a source attributed."""
        try:
            df = await xccy_collector.collect()

            if not df.empty:
                # All rows should have a source
                assert not df["source"].isna().any()

                # Source should be one of the known sources
                valid_sources = {"ecb_sdw", "calculated", "cached_baseline"}
                actual_sources = set(df["source"].unique())
                assert actual_sources.issubset(valid_sources), (
                    f"Unknown sources: {actual_sources - valid_sources}"
                )

        finally:
            await xccy_collector.close()


if __name__ == "__main__":
    # Quick sanity check for manual testing
    async def main() -> None:
        print("Testing Cross-Currency Basis Collector...")

        collector = XCcyBasisCollector()

        try:
            print("\n--- Cross-Currency Basis (6 months) ---")
            start = datetime.now(UTC) - timedelta(days=180)
            df = await collector.collect(start_date=start)

            print(f"Fetched {len(df)} records")
            print(f"Source(s): {df['source'].unique().tolist()}")

            if not df.empty:
                print("\nData preview:")
                print(df.tail(10))

                latest_value = df["value"].iloc[-1]
                stress = XCcyBasisCollector.classify_stress(latest_value)
                print(f"\nLatest basis: {latest_value:.1f} bps")
                print(f"Stress level: {stress}")

                print(f"\nStress thresholds: {STRESS_THRESHOLDS}")

        finally:
            await collector.close()

    asyncio.run(main())
