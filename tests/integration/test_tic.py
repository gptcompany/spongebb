"""Integration tests for TIC collector.

Tests TICCollector functionality:
- Major foreign holders fetch from US Treasury
- Treasury holdings by country
- FRED aggregate fallback
- Registry integration

Run with: uv run pytest tests/integration/test_tic.py -v --tb=short
"""

import asyncio
import os

import pytest

from liquidity.collectors.tic import (
    COUNTRY_CODES,
    FRED_TIC_SERIES,
    TIC_URLS,
    TICCollector,
)


@pytest.fixture
def tic_collector() -> TICCollector:
    """Create a TIC collector instance."""
    return TICCollector()


class TestTICCollectorMajorHolders:
    """Integration tests for major foreign holders."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_major_holders(self, tic_collector: TICCollector) -> None:
        """Test fetching major foreign holders of US Treasuries."""
        df = await tic_collector.collect_major_holders()

        # May be empty if Treasury servers are unavailable
        if df.empty:
            pytest.skip("TIC data unavailable from Treasury servers")

        # Verify DataFrame structure
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}

        # Verify source
        assert (df["source"] == "treasury").all()

        # Verify unit (Treasury data is in billions)
        assert (df["unit"] == "billions_usd").all()

        # Verify we have data
        assert len(df) > 0, "Should have at least some holder data"

        # Print summary
        print(f"\nMajor holders fetched: {len(df)}")
        for _, row in df.head(5).iterrows():
            print(f"  {row['series_id']}: {row['value']:,.1f} billion USD")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_major_holders_output_format(
        self, tic_collector: TICCollector
    ) -> None:
        """Test major holders output format matches spec."""
        df = await tic_collector.collect_major_holders()

        if df.empty:
            pytest.skip("TIC data unavailable from Treasury servers")

        # Check required columns
        required_cols = {"timestamp", "series_id", "source", "value", "unit"}
        assert set(df.columns) == required_cols

        # Check timestamp is datetime
        import pandas as pd

        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

        # Check series_id, source, unit are strings
        assert pd.api.types.is_string_dtype(df["series_id"])
        assert pd.api.types.is_string_dtype(df["source"])
        assert pd.api.types.is_string_dtype(df["unit"])

        # Check value is numeric
        assert pd.api.types.is_numeric_dtype(df["value"])

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_major_holders_values_reasonable(
        self, tic_collector: TICCollector
    ) -> None:
        """Test that holdings values are in reasonable range."""
        df = await tic_collector.collect_major_holders()

        if df.empty:
            pytest.skip("TIC data unavailable from Treasury servers")

        # Exclude total row for individual holder checks
        holders = df[~df["series_id"].str.contains("total")]

        if holders.empty:
            pytest.skip("No individual holder data available")

        # Holdings should be positive
        assert (holders["value"] > 0).all(), "Holdings should be positive"

        # Individual country holdings: 50B to 2T USD (in billions)
        min_val = holders["value"].min()
        max_val = holders["value"].max()

        # Japan and China are typically the largest holders (~1T USD each)
        # Smaller holders in top 25 might have ~50B USD
        assert min_val > 50, f"Minimum holding too low: {min_val:,.1f} billion"
        assert max_val < 2000, f"Maximum holding too high: {max_val:,.1f} billion"

        print(f"\nHoldings range: {min_val:,.1f} - {max_val:,.1f} billion USD")


class TestTICCollectorTreasuryHoldings:
    """Integration tests for treasury holdings by country."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_treasury_holdings(self, tic_collector: TICCollector) -> None:
        """Test fetching detailed treasury holdings."""
        df = await tic_collector.collect_treasury_holdings()

        if df.empty:
            pytest.skip("TIC holdings data unavailable")

        # Verify DataFrame structure
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}

        # Verify source
        assert (df["source"] == "treasury").all()

        # Verify data
        assert len(df) > 0

        print(f"\nTreasury holdings records: {len(df)}")


class TestTICCollectorAggregate:
    """Integration tests for FRED aggregate fallback."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.environ.get("LIQUIDITY_FRED_API_KEY"),
        reason="LIQUIDITY_FRED_API_KEY not set - skipping FRED test",
    )
    async def test_aggregate_fallback(self, tic_collector: TICCollector) -> None:
        """Test FRED aggregate series fetch."""
        df = await tic_collector.collect_aggregate()

        if df.empty:
            pytest.skip("FRED TIC data unavailable")

        # Verify DataFrame structure
        assert set(df.columns) == {"timestamp", "series_id", "source", "value", "unit"}

        # Verify source is FRED
        assert (df["source"] == "fred").all()

        # Verify unit
        assert (df["unit"] == "millions_usd").all()

        # Verify series IDs
        expected_series = {"tic_official_holdings", "tic_private_holdings"}
        actual_series = set(df["series_id"].unique())
        assert actual_series.issubset(expected_series), (
            f"Unexpected series: {actual_series - expected_series}"
        )

        print(f"\nFRED aggregate records: {len(df)}")
        for series in df["series_id"].unique():
            latest = df[df["series_id"] == series]["value"].iloc[-1]
            print(f"  {series}: {latest:,.0f} million USD")


class TestTICCollectorRegistry:
    """Tests for TIC collector registry integration."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_registry_integration(self) -> None:
        """Test that TIC collector is registered in the registry."""
        from liquidity.collectors import registry

        assert "tic" in registry.list_collectors()
        collector_cls = registry.get("tic")
        assert collector_cls is TICCollector


class TestTICSeriesIdFormat:
    """Tests for series_id format."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_series_id_format(self, tic_collector: TICCollector) -> None:
        """Test series_id format is tic_{country}_holdings."""
        df = await tic_collector.collect_major_holders()

        if df.empty:
            pytest.skip("TIC data unavailable")

        import re

        for series_id in df["series_id"]:
            # Should match tic_{country}_holdings pattern
            assert re.match(r"tic_[a-z]+_holdings", series_id), (
                f"Invalid series_id format: {series_id}"
            )

        print(f"\nSeries IDs: {df['series_id'].unique().tolist()}")


class TestTICNoNaNValues:
    """Tests for data quality."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_no_nan_values(self, tic_collector: TICCollector) -> None:
        """Test that output has no NaN values."""
        df = await tic_collector.collect_major_holders()

        if df.empty:
            pytest.skip("TIC data unavailable")

        # Check no NaN in any column
        assert df["timestamp"].isna().sum() == 0, "timestamp has NaN"
        assert df["series_id"].isna().sum() == 0, "series_id has NaN"
        assert df["source"].isna().sum() == 0, "source has NaN"
        assert df["value"].isna().sum() == 0, "value has NaN"
        assert df["unit"].isna().sum() == 0, "unit has NaN"


class TestTICCollectorSymbols:
    """Tests for TIC symbols and mappings."""

    def test_tic_urls_defined(self) -> None:
        """Test TIC URLs are defined."""
        assert "mfh" in TIC_URLS
        assert "holdings" in TIC_URLS
        assert "mfh_csv" in TIC_URLS

    def test_fred_series_defined(self) -> None:
        """Test FRED series are defined."""
        assert "official" in FRED_TIC_SERIES
        assert "private" in FRED_TIC_SERIES

    def test_country_codes_major_holders(self) -> None:
        """Test country codes include major holders."""
        # Japan and China should be mapped
        assert "Japan" in COUNTRY_CODES or "JAPAN" in COUNTRY_CODES
        assert "China, Mainland" in COUNTRY_CODES or "China" in COUNTRY_CODES

        # Verify lowercase codes
        japan_code = COUNTRY_CODES.get("Japan") or COUNTRY_CODES.get("JAPAN")
        assert japan_code == "japan"


class TestTICCollectorConvenienceMethods:
    """Tests for convenience methods."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_japan_holdings(self, tic_collector: TICCollector) -> None:
        """Test getting Japan holdings."""
        holdings = await tic_collector.get_japan_holdings()

        if holdings is None:
            pytest.skip("Japan holdings not available")

        # Japan typically holds ~1T USD (in billions: 500 to 1500)
        assert holdings > 500, f"Japan holdings too low: {holdings:,.1f} billion"
        assert holdings < 1500, f"Japan holdings too high: {holdings:,.1f} billion"

        print(f"\nJapan holdings: {holdings:,.1f} billion USD")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_china_holdings(self, tic_collector: TICCollector) -> None:
        """Test getting China holdings."""
        holdings = await tic_collector.get_china_holdings()

        if holdings is None:
            pytest.skip("China holdings not available")

        # China typically holds ~800B-1T USD (in billions: 500 to 1200)
        assert holdings > 500, f"China holdings too low: {holdings:,.1f} billion"
        assert holdings < 1200, f"China holdings too high: {holdings:,.1f} billion"

        print(f"\nChina holdings: {holdings:,.1f} billion USD")


class TestTICCollectorInstantiation:
    """Tests for TIC collector instantiation."""

    def test_collector_instantiation(self) -> None:
        """Test TICCollector can be instantiated."""
        collector = TICCollector()
        assert collector.name == "tic"

    def test_collector_class_attributes(self) -> None:
        """Test class attributes are accessible."""
        assert TICCollector.TIC_URLS == TIC_URLS
        assert TICCollector.FRED_TIC_SERIES == FRED_TIC_SERIES
        assert TICCollector.COUNTRY_CODES == COUNTRY_CODES


if __name__ == "__main__":
    # Run a quick sanity check
    async def main() -> None:
        collector = TICCollector()

        print("Fetching TIC major holders...")
        try:
            df = await collector.collect_major_holders()
            if not df.empty:
                print(f"Records: {len(df)}")
                print("\nTop 5 holders:")
                for _, row in df.head(5).iterrows():
                    print(f"  {row['series_id']}: {row['value']:,.1f} billion USD")
            else:
                print("No data returned")
        except Exception as e:
            print(f"Error: {e}")

        print("\n\nFetching Japan and China holdings...")
        japan = await collector.get_japan_holdings()
        china = await collector.get_china_holdings()
        print(f"Japan: {japan:,.1f} billion USD" if japan else "Japan: N/A")
        print(f"China: {china:,.1f} billion USD" if china else "China: N/A")

    asyncio.run(main())
