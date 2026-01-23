"""Integration tests for commodity collector.

Tests CommodityCollector functionality:
- Precious metals (gold, silver) fetch
- Energy (WTI, Brent) fetch
- Copper fetch
- Batch download (single yf.download for multiple symbols)
- Derived metrics (Brent-WTI spread, Cu/Au ratio)

Run with: uv run pytest tests/integration/test_commodities.py -v
"""

import asyncio

import pandas as pd
import pytest

from liquidity.collectors.commodities import (
    COMMODITY_SYMBOLS,
    UNIT_MAP,
    CommodityCollector,
)


@pytest.fixture
def commodity_collector() -> CommodityCollector:
    """Create a commodity collector instance."""
    return CommodityCollector()


class TestCommoditySymbols:
    """Tests for commodity symbols mapping."""

    def test_commodity_symbols_defined(self) -> None:
        """Test all 5 commodities are mapped."""
        assert len(COMMODITY_SYMBOLS) == 5
        assert "gold" in COMMODITY_SYMBOLS
        assert "silver" in COMMODITY_SYMBOLS
        assert "copper" in COMMODITY_SYMBOLS
        assert "wti" in COMMODITY_SYMBOLS
        assert "brent" in COMMODITY_SYMBOLS

    def test_commodity_symbol_tickers(self) -> None:
        """Test Yahoo Finance ticker format."""
        assert COMMODITY_SYMBOLS["gold"] == "GC=F"
        assert COMMODITY_SYMBOLS["silver"] == "SI=F"
        assert COMMODITY_SYMBOLS["copper"] == "HG=F"
        assert COMMODITY_SYMBOLS["wti"] == "CL=F"
        assert COMMODITY_SYMBOLS["brent"] == "BZ=F"

    def test_unit_map_complete(self) -> None:
        """Test all symbols have units defined."""
        for symbol in COMMODITY_SYMBOLS.values():
            assert symbol in UNIT_MAP, f"Missing unit for {symbol}"

    def test_unit_map_values(self) -> None:
        """Test unit values are correct."""
        assert UNIT_MAP["GC=F"] == "usd_per_oz"
        assert UNIT_MAP["SI=F"] == "usd_per_oz"
        assert UNIT_MAP["HG=F"] == "usd_per_lb"
        assert UNIT_MAP["CL=F"] == "usd_per_barrel"
        assert UNIT_MAP["BZ=F"] == "usd_per_barrel"


class TestCommodityCollector:
    """Tests for CommodityCollector instantiation and basic methods."""

    def test_collector_instantiation(self) -> None:
        """Test CommodityCollector can be instantiated."""
        collector = CommodityCollector()
        assert collector.name == "commodities"

    def test_collector_class_attributes(self) -> None:
        """Test class attributes are accessible."""
        assert CommodityCollector.COMMODITY_SYMBOLS == COMMODITY_SYMBOLS
        assert CommodityCollector.UNIT_MAP == UNIT_MAP


class TestCommodityCollectorIntegration:
    """Integration tests with real Yahoo Finance data."""

    @pytest.mark.asyncio
    async def test_collect_all_commodities(
        self, commodity_collector: CommodityCollector
    ) -> None:
        """Test collecting all commodities."""
        df = await commodity_collector.collect(period="5d")

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        assert set(df.columns) == {
            "timestamp",
            "series_id",
            "source",
            "value",
            "unit",
        }

        # Verify source
        assert (df["source"] == "yahoo").all()

        # Verify all 5 commodities present
        symbols = df["series_id"].unique().tolist()
        print(f"\nCommodities fetched: {symbols}")

        expected = ["GC=F", "SI=F", "HG=F", "CL=F", "BZ=F"]
        for symbol in expected:
            assert symbol in symbols, f"Missing {symbol}"

    @pytest.mark.asyncio
    async def test_collect_precious_metals(
        self, commodity_collector: CommodityCollector
    ) -> None:
        """Test collecting precious metals only."""
        df = await commodity_collector.collect_precious_metals(period="5d")

        # Verify only gold and silver
        symbols = df["series_id"].unique().tolist()
        assert "GC=F" in symbols, "Gold should be present"
        assert "SI=F" in symbols, "Silver should be present"
        assert len(symbols) == 2, "Should only have 2 symbols"

        # Verify units
        assert (df["unit"] == "usd_per_oz").all()

        # Verify value ranges
        gold = df[df["series_id"] == "GC=F"]["value"]
        assert gold.min() > 1000, f"Gold too low: {gold.min()}"
        assert gold.max() < 5000, f"Gold too high: {gold.max()}"
        print(f"\nGold (latest): ${gold.iloc[-1]:.2f}/oz")

        silver = df[df["series_id"] == "SI=F"]["value"]
        assert silver.min() > 10, f"Silver too low: {silver.min()}"
        assert silver.max() < 100, f"Silver too high: {silver.max()}"
        print(f"Silver (latest): ${silver.iloc[-1]:.2f}/oz")

    @pytest.mark.asyncio
    async def test_collect_energy(
        self, commodity_collector: CommodityCollector
    ) -> None:
        """Test collecting energy commodities only."""
        df = await commodity_collector.collect_energy(period="5d")

        # Verify only WTI and Brent
        symbols = df["series_id"].unique().tolist()
        assert "CL=F" in symbols, "WTI should be present"
        assert "BZ=F" in symbols, "Brent should be present"
        assert len(symbols) == 2, "Should only have 2 symbols"

        # Verify units
        assert (df["unit"] == "usd_per_barrel").all()

        # Verify value ranges
        wti = df[df["series_id"] == "CL=F"]["value"]
        assert wti.min() > 20, f"WTI too low: {wti.min()}"
        assert wti.max() < 200, f"WTI too high: {wti.max()}"
        print(f"\nWTI (latest): ${wti.iloc[-1]:.2f}/barrel")

        brent = df[df["series_id"] == "BZ=F"]["value"]
        assert brent.min() > 20, f"Brent too low: {brent.min()}"
        assert brent.max() < 200, f"Brent too high: {brent.max()}"
        print(f"Brent (latest): ${brent.iloc[-1]:.2f}/barrel")

    @pytest.mark.asyncio
    async def test_output_format(self, commodity_collector: CommodityCollector) -> None:
        """Test output DataFrame has correct format."""
        df = await commodity_collector.collect(period="5d")

        # Verify column types
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
        assert pd.api.types.is_string_dtype(df["series_id"])
        assert pd.api.types.is_string_dtype(df["source"])
        assert pd.api.types.is_numeric_dtype(df["value"])
        assert pd.api.types.is_string_dtype(df["unit"])

        # Verify no NaN values (ffill should handle gaps)
        assert df["value"].isna().sum() == 0

    @pytest.mark.asyncio
    async def test_forward_fill_applied(
        self, commodity_collector: CommodityCollector
    ) -> None:
        """Test that gaps are forward filled."""
        df = await commodity_collector.collect(period="30d")

        # Should have no NaN values after processing
        assert df["value"].isna().sum() == 0, "All values should be filled"

        # Data should be sorted by series_id and timestamp
        for series_id in df["series_id"].unique():
            series_data = df[df["series_id"] == series_id]
            timestamps = series_data["timestamp"].values
            assert all(
                timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1)
            ), f"Data for {series_id} should be sorted"


class TestDerivedMetrics:
    """Tests for derived metric calculations."""

    @pytest.mark.asyncio
    async def test_brent_wti_spread_calculation(
        self, commodity_collector: CommodityCollector
    ) -> None:
        """Test Brent-WTI spread calculation."""
        df = await commodity_collector.collect_energy(period="30d")
        spread_df = CommodityCollector.calculate_brent_wti_spread(df)

        # Verify output format
        assert "timestamp" in spread_df.columns
        assert "brent_wti_spread" in spread_df.columns

        # Verify spread is calculated (Brent - WTI)
        # Historically, Brent trades at a small premium or discount to WTI
        spread = spread_df["brent_wti_spread"]
        assert spread.min() > -30, f"Spread too negative: {spread.min()}"
        assert spread.max() < 30, f"Spread too positive: {spread.max()}"

        print(f"\nBrent-WTI spread (latest): ${spread.iloc[-1]:.2f}/barrel")
        print(f"Spread range: ${spread.min():.2f} to ${spread.max():.2f}")

    @pytest.mark.asyncio
    async def test_copper_gold_ratio_calculation(
        self, commodity_collector: CommodityCollector
    ) -> None:
        """Test Copper/Gold ratio calculation."""
        # Need both copper and gold
        symbols = [COMMODITY_SYMBOLS["copper"], COMMODITY_SYMBOLS["gold"]]
        df = await commodity_collector.collect(symbols=symbols, period="30d")

        ratio_df = CommodityCollector.calculate_copper_gold_ratio(df)

        # Verify output format
        assert "timestamp" in ratio_df.columns
        assert "copper_gold_ratio" in ratio_df.columns

        # Verify ratio is reasonable (copper ~$4/lb, gold ~$2000/oz)
        # Ratio = (copper / gold) * 1000, typically 1-5
        ratio = ratio_df["copper_gold_ratio"]
        assert ratio.min() > 0.5, f"Ratio too low: {ratio.min()}"
        assert ratio.max() < 10, f"Ratio too high: {ratio.max()}"

        print(f"\nCu/Au ratio (latest): {ratio.iloc[-1]:.4f}")
        print(f"Ratio range: {ratio.min():.4f} to {ratio.max():.4f}")

    def test_brent_wti_spread_with_mock_data(self) -> None:
        """Test Brent-WTI spread with mock data."""
        mock_data = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3),
                "series_id": ["CL=F", "CL=F", "CL=F"],
                "value": [70.0, 71.0, 72.0],
            }
        )
        mock_brent = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3),
                "series_id": ["BZ=F", "BZ=F", "BZ=F"],
                "value": [75.0, 76.0, 77.0],
            }
        )
        df = pd.concat([mock_data, mock_brent])

        spread_df = CommodityCollector.calculate_brent_wti_spread(df)

        # Spread should be 5.0 for all rows (75-70, 76-71, 77-72)
        assert (spread_df["brent_wti_spread"] == 5.0).all()

    def test_copper_gold_ratio_with_mock_data(self) -> None:
        """Test Cu/Au ratio with mock data."""
        mock_copper = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3),
                "series_id": ["HG=F", "HG=F", "HG=F"],
                "value": [4.0, 4.0, 4.0],
            }
        )
        mock_gold = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3),
                "series_id": ["GC=F", "GC=F", "GC=F"],
                "value": [2000.0, 2000.0, 2000.0],
            }
        )
        df = pd.concat([mock_copper, mock_gold])

        ratio_df = CommodityCollector.calculate_copper_gold_ratio(df)

        # Ratio should be (4 / 2000) * 1000 = 2.0
        assert (ratio_df["copper_gold_ratio"] == 2.0).all()


class TestCommodityCollectorRegistry:
    """Tests for commodity collector registry."""

    @pytest.mark.asyncio
    async def test_collector_registered(self) -> None:
        """Test that commodity collector is registered."""
        from liquidity.collectors import registry

        assert "commodities" in registry.list_collectors()
        collector_cls = registry.get("commodities")
        assert collector_cls is CommodityCollector


class TestCommodityCollectorConvenience:
    """Tests for convenience methods."""

    @pytest.mark.asyncio
    async def test_get_current_gold_price(
        self, commodity_collector: CommodityCollector
    ) -> None:
        """Test getting current gold price."""
        price = await commodity_collector.get_current_gold_price()

        if price is None:
            pytest.skip("Could not fetch current gold price")

        # Gold should be in reasonable range
        assert 1000 < price < 5000, f"Gold price out of range: {price}"
        print(f"\nCurrent gold price: ${price:.2f}/oz")


if __name__ == "__main__":
    # Run a quick sanity check
    async def main() -> None:
        collector = CommodityCollector()

        print("Fetching all commodities...")
        df = await collector.collect(period="30d")
        print(f"Total data points: {len(df)}")

        for series in df["series_id"].unique():
            latest = df[df["series_id"] == series]["value"].iloc[-1]
            unit = df[df["series_id"] == series]["unit"].iloc[0]
            print(f"{series}: {latest:.2f} ({unit})")

        print("\nCalculating Brent-WTI spread...")
        spread = CommodityCollector.calculate_brent_wti_spread(df)
        print(f"Latest spread: ${spread['brent_wti_spread'].iloc[-1]:.2f}/barrel")

        print("\nCalculating Cu/Au ratio...")
        ratio = CommodityCollector.calculate_copper_gold_ratio(df)
        print(f"Latest ratio: {ratio['copper_gold_ratio'].iloc[-1]:.4f}")

    asyncio.run(main())
