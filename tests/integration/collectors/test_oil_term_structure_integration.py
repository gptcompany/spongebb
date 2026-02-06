"""Integration tests for OilTermStructureCollector with live data."""

from datetime import datetime, timedelta, UTC

import pandas as pd
import pytest

from liquidity.collectors.oil_term_structure import OilTermStructureCollector


@pytest.mark.integration
class TestLiveDataFetch:
    """Test with real yfinance API."""

    @pytest.mark.asyncio
    async def test_collect_wti_live(self):
        """Fetch actual WTI data from yfinance."""
        collector = OilTermStructureCollector()

        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=30)

        result = await collector.collect(
            ["wti_front"],
            start_date=start_date,
            end_date=end_date,
        )

        # Should have data (yfinance may have weekend gaps)
        assert not result.empty

        # Verify schema
        assert "timestamp" in result.columns
        assert "series_id" in result.columns
        assert "value" in result.columns

        # Price should be reasonable ($20-$200/barrel)
        prices = result[result["series_id"] == "wti_front"]["value"]
        assert prices.min() > 20, f"Price too low: {prices.min()}"
        assert prices.max() < 200, f"Price too high: {prices.max()}"

    @pytest.mark.asyncio
    async def test_collect_brent_live(self):
        """Fetch actual Brent data from yfinance."""
        collector = OilTermStructureCollector()

        result = await collector.collect(["brent_front"], period="30d")

        assert not result.empty
        assert "brent_front" in result["series_id"].values

    @pytest.mark.asyncio
    async def test_collect_both_live(self):
        """Fetch both WTI and Brent."""
        collector = OilTermStructureCollector()

        result = await collector.collect(["wti_front", "brent_front"], period="30d")

        series_ids = result["series_id"].unique()
        assert "wti_front" in series_ids
        assert "brent_front" in series_ids

    @pytest.mark.asyncio
    async def test_collect_with_momentum_live(self):
        """Fetch with momentum calculations."""
        collector = OilTermStructureCollector()

        result = await collector.collect_with_momentum(period="90d")

        # Should have price and momentum series
        series_ids = result["series_id"].unique()
        assert "wti_front" in series_ids
        assert "wti_front_momentum_5d" in series_ids
        assert "wti_front_momentum_20d" in series_ids

    @pytest.mark.asyncio
    async def test_data_freshness(self):
        """Verify data is recent (within 5 trading days)."""
        collector = OilTermStructureCollector()

        result = await collector.collect_wti(period="30d")

        if not result.empty:
            latest = result["timestamp"].max()
            # Convert to datetime if needed
            if isinstance(latest, pd.Timestamp):
                latest = latest.to_pydatetime()
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=UTC)

            days_old = (datetime.now(UTC) - latest).days
            # Allow up to 5 days for weekends/holidays
            assert days_old < 5, f"Data is {days_old} days old"

    @pytest.mark.asyncio
    async def test_brent_wti_spread_live(self):
        """Calculate Brent-WTI spread with live data."""
        collector = OilTermStructureCollector()

        df = await collector.collect(["wti_front", "brent_front"], period="30d")

        if not df.empty:
            spread = OilTermStructureCollector.calculate_brent_wti_spread(df)

            # Spread should exist and be reasonable (-$10 to +$15)
            assert not spread.empty
            assert spread["brent_wti_spread"].min() > -10
            assert spread["brent_wti_spread"].max() < 15

    @pytest.mark.asyncio
    async def test_get_current_price_live(self):
        """Get current WTI price."""
        collector = OilTermStructureCollector()

        price = await collector.get_current_wti_price()

        # Should return a valid price
        assert price is not None
        assert 20 < price < 200
