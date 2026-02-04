"""Integration tests for stress indicator collector.

Tests funding market stress indicators:
- SOFR-OIS spread
- SOFR distribution width
- Repo stress ratio
- CP-Treasury spread

Requires: LIQUIDITY_FRED_API_KEY environment variable for API tests.

Run with: uv run pytest tests/integration/test_stress.py -v
"""

import asyncio
import os

import pandas as pd
import pytest

from liquidity.collectors.stress import (
    STRESS_THRESHOLDS,
    StressIndicatorCollector,
)

# Mark for tests that require FRED API key
requires_fred_api = pytest.mark.skipif(
    not os.environ.get("LIQUIDITY_FRED_API_KEY"),
    reason="LIQUIDITY_FRED_API_KEY not set - skipping FRED API tests",
)


@pytest.fixture
def stress_collector() -> StressIndicatorCollector:
    """Create a stress indicator collector instance."""
    return StressIndicatorCollector()


class TestSOFROISSpread:
    """Tests for SOFR-OIS spread indicator."""

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_sofr_ois_spread(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test SOFR-OIS spread calculation."""
        df = await stress_collector.collect_sofr_ois_spread()

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
        assert df["series_id"].unique().tolist() == ["stress_sofr_ois"]

        # Verify source is calculated
        assert df["source"].unique().tolist() == ["calculated"]

        # Verify unit is basis_points
        assert df["unit"].unique().tolist() == ["basis_points"]

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sofr_ois_values_reasonable(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test SOFR-OIS spread values are in reasonable range (-50 to +100 bps)."""
        df = await stress_collector.collect_sofr_ois_spread()

        assert not df.empty, "DataFrame should not be empty"

        # SOFR-OIS spread should be between -50 and +100 bps in normal conditions
        assert df["value"].min() >= -50, "SOFR-OIS spread should be >= -50 bps"
        assert df["value"].max() <= 100, "SOFR-OIS spread should be <= 100 bps"

        print(f"\nSOFR-OIS spread latest: {df['value'].iloc[-1]:.2f} bps")


class TestSOFRDistribution:
    """Tests for SOFR distribution width indicator."""

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_sofr_distribution(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test SOFR distribution width calculation from percentiles."""
        df = await stress_collector.collect_sofr_distribution()

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
        assert df["series_id"].unique().tolist() == ["stress_sofr_width"]

        # Verify source and unit
        assert df["source"].unique().tolist() == ["calculated"]
        assert df["unit"].unique().tolist() == ["basis_points"]

        # Width should be non-negative (99th percentile >= 1st percentile)
        assert df["value"].min() >= 0, "SOFR distribution width should be >= 0"

        print(f"\nSOFR distribution width latest: {df['value'].iloc[-1]:.2f} bps")


class TestRepoStress:
    """Tests for repo stress ratio indicator."""

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_repo_stress(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test repo stress ratio (RRP/WALCL) calculation."""
        df = await stress_collector.collect_repo_stress()

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
        assert df["series_id"].unique().tolist() == ["stress_repo"]

        # Verify source and unit
        assert df["source"].unique().tolist() == ["calculated"]
        assert df["unit"].unique().tolist() == ["percent"]

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_repo_stress_normalized(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test repo stress ratio is a valid percentage (0-100)."""
        df = await stress_collector.collect_repo_stress()

        assert not df.empty, "DataFrame should not be empty"

        # Ratio should be between 0 and 100 percent
        assert df["value"].min() >= 0, "Repo stress ratio should be >= 0%"
        assert df["value"].max() <= 100, "Repo stress ratio should be <= 100%"

        print(f"\nRepo stress ratio latest: {df['value'].iloc[-1]:.2f}%")


class TestCPSpread:
    """Tests for CP-Treasury spread indicator."""

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_cp_spread(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test CP-Treasury spread calculation."""
        df = await stress_collector.collect_cp_spread()

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
        assert df["series_id"].unique().tolist() == ["stress_cp"]

        # Verify source and unit
        assert df["source"].unique().tolist() == ["calculated"]
        assert df["unit"].unique().tolist() == ["basis_points"]

        print(f"\nCP-Treasury spread latest: {df['value'].iloc[-1]:.2f} bps")


class TestCollectAll:
    """Tests for combined stress indicator collection."""

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_all_combined(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test all stress indicators collected in one DataFrame."""
        df = await stress_collector.collect_all()

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {
            "timestamp",
            "series_id",
            "source",
            "value",
            "unit",
        }

        # Verify all indicators are present
        series_present = set(df["series_id"].unique())

        # At least some indicators should be present
        assert len(series_present) > 0, "At least one indicator should be collected"

        # Log which indicators were collected
        print(f"\nCollected indicators: {series_present}")
        for series_id in series_present:
            latest = df[df["series_id"] == series_id].iloc[-1]
            print(f"  {series_id}: {latest['value']:.2f} {latest['unit']}")

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_output_format(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test standard output format columns are present."""
        df = await stress_collector.collect()

        # Required columns
        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert expected_columns.issubset(set(df.columns))

        # Verify timestamp is datetime type
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

        # Verify value is numeric
        assert pd.api.types.is_numeric_dtype(df["value"])


class TestRegimeClassification:
    """Tests for stress regime classification."""

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_regime_classification(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test regime classification returns GREEN, YELLOW, or RED."""
        df = await stress_collector.collect()

        regime = stress_collector.get_current_regime(df)

        assert regime in ["GREEN", "YELLOW", "RED"], (
            f"Regime should be GREEN, YELLOW, or RED, got {regime}"
        )

        print(f"\nCurrent stress regime: {regime}")

    @pytest.mark.integration
    def test_regime_empty_dataframe(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test regime classification with empty DataFrame returns GREEN."""
        empty_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        regime = stress_collector.get_current_regime(empty_df)
        assert regime == "GREEN"

    @pytest.mark.integration
    def test_regime_none_returns_green(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test regime classification with None returns GREEN."""
        regime = stress_collector.get_current_regime(None)
        assert regime == "GREEN"

    @pytest.mark.integration
    def test_thresholds_applied(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test that regime classification uses defined thresholds."""
        # Create test data with values above yellow threshold
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")] * 4,
                "series_id": [
                    "stress_sofr_ois",
                    "stress_sofr_width",
                    "stress_repo",
                    "stress_cp",
                ],
                "source": ["calculated"] * 4,
                "value": [
                    30.0,  # Above yellow threshold of 25
                    25.0,  # Above green threshold of 20, below yellow of 50
                    0.5,  # Below green threshold of 1
                    30.0,  # Below green threshold of 40
                ],
                "unit": [
                    "basis_points",
                    "basis_points",
                    "percent",
                    "basis_points",
                ],
            }
        )

        # Should be RED because sofr_ois is above yellow threshold
        regime = stress_collector.get_current_regime(test_data)
        assert regime == "RED"

    @pytest.mark.integration
    def test_thresholds_yellow_regime(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test YELLOW regime when above green but below yellow threshold."""
        # Create test data with values between green and yellow thresholds
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")] * 4,
                "series_id": [
                    "stress_sofr_ois",
                    "stress_sofr_width",
                    "stress_repo",
                    "stress_cp",
                ],
                "source": ["calculated"] * 4,
                "value": [
                    15.0,  # Above green (10), below yellow (25)
                    10.0,  # Below green threshold of 20
                    0.5,  # Below green threshold of 1
                    30.0,  # Below green threshold of 40
                ],
                "unit": [
                    "basis_points",
                    "basis_points",
                    "percent",
                    "basis_points",
                ],
            }
        )

        # Should be YELLOW because sofr_ois is above green threshold
        regime = stress_collector.get_current_regime(test_data)
        assert regime == "YELLOW"

    @pytest.mark.integration
    def test_thresholds_green_regime(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test GREEN regime when all below green thresholds."""
        # Create test data with all values below green thresholds
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")] * 4,
                "series_id": [
                    "stress_sofr_ois",
                    "stress_sofr_width",
                    "stress_repo",
                    "stress_cp",
                ],
                "source": ["calculated"] * 4,
                "value": [
                    5.0,  # Below green threshold of 10
                    10.0,  # Below green threshold of 20
                    0.5,  # Below green threshold of 1
                    30.0,  # Below green threshold of 40
                ],
                "unit": [
                    "basis_points",
                    "basis_points",
                    "percent",
                    "basis_points",
                ],
            }
        )

        # Should be GREEN because all below green thresholds
        regime = stress_collector.get_current_regime(test_data)
        assert regime == "GREEN"


class TestRegistryIntegration:
    """Tests for collector registry integration."""

    @pytest.mark.integration
    def test_registry_integration(self) -> None:
        """Test that stress collector is registered in the registry."""
        from liquidity.collectors import registry

        assert "stress" in registry.list_collectors()
        collector_cls = registry.get("stress")
        assert collector_cls is StressIndicatorCollector

    @pytest.mark.integration
    def test_instantiation_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector_cls = registry.get("stress")
        collector = collector_cls()

        assert isinstance(collector, StressIndicatorCollector)
        assert collector.name == "stress"


class TestDataQuality:
    """Tests for data quality and NaN handling."""

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_no_nan_in_spread(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test NaN handling (ffill before calculation)."""
        df = await stress_collector.collect()

        # No NaN values should be in the final output
        assert not df["value"].isna().any(), "Output should not contain NaN values"

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_data_sorted_by_timestamp(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test data is sorted by timestamp."""
        df = await stress_collector.collect()

        if not df.empty:
            # Check each series is sorted
            for series_id in df["series_id"].unique():
                series_df = df[df["series_id"] == series_id]
                timestamps = series_df["timestamp"].tolist()
                assert timestamps == sorted(timestamps), (
                    f"Data for {series_id} should be sorted by timestamp"
                )


class TestThresholdsExport:
    """Tests for threshold constants export."""

    @pytest.mark.integration
    def test_thresholds_structure(self) -> None:
        """Test STRESS_THRESHOLDS constant structure."""
        assert "sofr_ois" in STRESS_THRESHOLDS
        assert "sofr_width" in STRESS_THRESHOLDS
        assert "repo_stress" in STRESS_THRESHOLDS
        assert "cp_spread" in STRESS_THRESHOLDS

        # Each threshold should have green and yellow levels
        for key in STRESS_THRESHOLDS:
            assert "green" in STRESS_THRESHOLDS[key]
            assert "yellow" in STRESS_THRESHOLDS[key]
            assert STRESS_THRESHOLDS[key]["green"] < STRESS_THRESHOLDS[key]["yellow"]


class TestFindDateColumn:
    """Tests for _find_date_column helper function."""

    def test_find_date_column_with_date(self) -> None:
        """Test finding 'date' column."""
        df = pd.DataFrame({"date": [1, 2, 3], "value": [10, 20, 30]})
        result = StressIndicatorCollector._find_date_column(df)
        assert result == "date"

    def test_find_date_column_with_index(self) -> None:
        """Test finding 'index' column."""
        df = pd.DataFrame({"index": [1, 2, 3], "value": [10, 20, 30]})
        result = StressIndicatorCollector._find_date_column(df)
        assert result == "index"

    def test_find_date_column_with_timestamp(self) -> None:
        """Test finding 'timestamp' column."""
        df = pd.DataFrame({"timestamp": [1, 2, 3], "value": [10, 20, 30]})
        result = StressIndicatorCollector._find_date_column(df)
        assert result == "timestamp"

    def test_find_date_column_from_index_name(self) -> None:
        """Test finding column from DataFrame index name."""
        df = pd.DataFrame({"value": [10, 20, 30]})
        df.index.name = "my_date"
        result = StressIndicatorCollector._find_date_column(df)
        assert result == "my_date"

    def test_find_date_column_fallback_first(self) -> None:
        """Test fallback to first column."""
        df = pd.DataFrame({"foo": [1, 2, 3], "bar": [10, 20, 30]})
        result = StressIndicatorCollector._find_date_column(df)
        assert result == "foo"

    def test_find_date_column_empty_raises(self) -> None:
        """Test that empty DataFrame raises ValueError."""
        df = pd.DataFrame()
        with pytest.raises(ValueError, match="Could not identify date column"):
            StressIndicatorCollector._find_date_column(df)


class TestRegimeEdgeCases:
    """Edge case tests for regime classification."""

    @pytest.fixture
    def stress_collector(self) -> StressIndicatorCollector:
        """Create stress collector."""
        return StressIndicatorCollector()

    @pytest.mark.integration
    def test_regime_partial_data(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test regime classification with partial indicator data."""
        # Only one indicator present
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")],
                "series_id": ["stress_sofr_ois"],
                "source": ["calculated"],
                "value": [5.0],  # Below green threshold
                "unit": ["basis_points"],
            }
        )

        regime = stress_collector.get_current_regime(test_data)
        assert regime == "GREEN"

    @pytest.mark.integration
    def test_regime_unknown_series_ignored(
        self, stress_collector: StressIndicatorCollector
    ) -> None:
        """Test unknown series IDs are ignored in regime classification."""
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")] * 2,
                "series_id": ["stress_sofr_ois", "unknown_indicator"],
                "source": ["calculated"] * 2,
                "value": [5.0, 1000.0],  # Unknown has high value but should be ignored
                "unit": ["basis_points"] * 2,
            }
        )

        regime = stress_collector.get_current_regime(test_data)
        assert regime == "GREEN"


class TestStressCollectorInstantiation:
    """Tests for StressIndicatorCollector instantiation."""

    def test_collector_instantiation(self) -> None:
        """Test default instantiation."""
        collector = StressIndicatorCollector()
        assert collector.name == "stress"

    def test_collector_custom_name(self) -> None:
        """Test custom name."""
        collector = StressIndicatorCollector(name="custom_stress")
        assert collector.name == "custom_stress"

    def test_collector_class_attributes(self) -> None:
        """Test class attributes."""
        from liquidity.collectors.stress import STRESS_SERIES_MAP

        assert StressIndicatorCollector.SERIES_MAP == STRESS_SERIES_MAP
        assert StressIndicatorCollector.THRESHOLDS == STRESS_THRESHOLDS


if __name__ == "__main__":
    # Quick sanity check
    async def main() -> None:
        collector = StressIndicatorCollector()

        print("Testing stress indicator collection...")
        df = await collector.collect()
        print(f"Collected {len(df)} data points")

        if not df.empty:
            print("\nLatest values:")
            for series_id in df["series_id"].unique():
                latest = df[df["series_id"] == series_id].iloc[-1]
                print(f"  {series_id}: {latest['value']:.2f} {latest['unit']}")

            regime = collector.get_current_regime(df)
            print(f"\nCurrent regime: {regime}")

    asyncio.run(main())
