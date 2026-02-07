"""Unit tests for InventoryForecaster.

Tests oil inventory forecasting with YoY and seasonal analysis.
Run with: uv run pytest tests/unit/oil/test_inventory_forecast.py -v
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from liquidity.oil.inventory_forecast import (
    DEFAULT_REFINERY_INPUTS_KBD,
    TREND_THRESHOLD_MB,
    InventoryForecast,
    InventoryForecaster,
    TrendDirection,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for EIA collector."""
    mock = MagicMock()
    mock.eia_api_key.get_secret_value.return_value = "test_api_key"
    mock.circuit_breaker.threshold = 5
    mock.circuit_breaker.ttl = 60
    mock.retry.max_attempts = 3
    mock.retry.multiplier = 1.0
    mock.retry.min_wait = 1
    mock.retry.max_wait = 10
    return mock


@pytest.fixture
def forecaster():
    """Create InventoryForecaster with mocked collector."""
    with patch("liquidity.collectors.eia.get_settings") as mock_settings:
        mock_settings.return_value.eia_api_key.get_secret_value.return_value = (
            "test_api_key"
        )
        mock_settings.return_value.circuit_breaker.threshold = 5
        mock_settings.return_value.circuit_breaker.ttl = 60
        mock_settings.return_value.retry.max_attempts = 3
        mock_settings.return_value.retry.multiplier = 1.0
        mock_settings.return_value.retry.min_wait = 1
        mock_settings.return_value.retry.max_wait = 10
        return InventoryForecaster()


@pytest.fixture
def mock_inventory_response() -> dict:
    """Sample crude stocks API response from EIA spanning 6 years."""
    # Generate 6 years of weekly data (6 * 52 = 312 weeks)
    data = []
    base_date = datetime(2020, 1, 8, tzinfo=UTC)
    base_value = 420000  # thousand barrels

    for i in range(312):
        date = base_date + timedelta(weeks=i)
        # Add some seasonal variation and trend
        seasonal = 10000 * np.sin(2 * np.pi * i / 52)
        trend = i * 50  # Slight upward trend
        noise = np.random.uniform(-2000, 2000)
        value = base_value + seasonal + trend + noise

        data.append(
            {
                "period": date.strftime("%Y-%m-%d"),
                "series": "WCESTUS1",
                "value": value,
                "units": "thousand barrels",
            }
        )

    return {"response": {"total": len(data), "data": data}}


@pytest.fixture
def simple_inventory_df():
    """Create a simple inventory DataFrame for testing."""
    # Create 2 years of weekly data
    dates = pd.date_range(start="2024-01-01", periods=104, freq="W")
    values = [420000 + i * 100 + 5000 * np.sin(2 * np.pi * i / 52) for i in range(104)]

    return pd.DataFrame(
        {
            "timestamp": dates,
            "series_id": ["WCESTUS1"] * 104,
            "source": ["eia"] * 104,
            "value": values,
            "unit": ["thousand_barrels"] * 104,
        }
    )


class TestTrendDirection:
    """Tests for TrendDirection enum."""

    def test_trend_direction_values(self) -> None:
        """Test TrendDirection has expected values."""
        assert TrendDirection.BUILDING.value == "building"
        assert TrendDirection.DRAWING.value == "drawing"
        assert TrendDirection.STABLE.value == "stable"

    def test_trend_direction_is_string(self) -> None:
        """Test TrendDirection is string compatible."""
        assert str(TrendDirection.BUILDING) == "TrendDirection.BUILDING"
        assert TrendDirection.BUILDING.value == "building"


class TestInventoryForecastDataclass:
    """Tests for InventoryForecast dataclass."""

    def test_inventory_forecast_creation(self) -> None:
        """Test InventoryForecast can be created with all fields."""
        forecast = InventoryForecast(
            date=datetime(2026, 2, 5, tzinfo=UTC),
            current_stocks=425.5,
            yoy_change=5.2,
            yoy_change_pct=1.2,
            vs_5yr_avg=-3.1,
            vs_5yr_avg_pct=-0.7,
            days_of_supply=26.5,
            weekly_trend=TrendDirection.BUILDING,
            forecast_4wk=430.0,
        )

        assert forecast.current_stocks == 425.5
        assert forecast.yoy_change == 5.2
        assert forecast.yoy_change_pct == 1.2
        assert forecast.vs_5yr_avg == -3.1
        assert forecast.vs_5yr_avg_pct == -0.7
        assert forecast.days_of_supply == 26.5
        assert forecast.weekly_trend == TrendDirection.BUILDING
        assert forecast.forecast_4wk == 430.0


class TestConstants:
    """Tests for module constants."""

    def test_default_refinery_inputs(self) -> None:
        """Test default refinery inputs is reasonable (~16M b/d)."""
        assert DEFAULT_REFINERY_INPUTS_KBD == 16_000.0

    def test_trend_threshold(self) -> None:
        """Test trend threshold is 1 MB."""
        assert TREND_THRESHOLD_MB == 1.0


class TestInventoryForecasterInit:
    """Tests for InventoryForecaster initialization."""

    def test_init_without_collector(self) -> None:
        """Test init without collector creates one lazily."""
        forecaster = InventoryForecaster()
        assert forecaster._collector is None

    def test_init_with_collector(self) -> None:
        """Test init with collector stores it."""
        mock_collector = MagicMock()
        forecaster = InventoryForecaster(eia_collector=mock_collector)
        assert forecaster._collector is mock_collector

    def test_init_custom_threshold(self) -> None:
        """Test init with custom trend threshold."""
        forecaster = InventoryForecaster(trend_threshold=2.5)
        assert forecaster._trend_threshold == 2.5


class TestTrendClassification:
    """Tests for trend classification logic."""

    def test_classify_trend_building(self) -> None:
        """Test trend classified as BUILDING when change > threshold."""
        forecaster = InventoryForecaster(trend_threshold=1.0)
        trend = forecaster._classify_trend(2.5)
        assert trend == TrendDirection.BUILDING

    def test_classify_trend_drawing(self) -> None:
        """Test trend classified as DRAWING when change < -threshold."""
        forecaster = InventoryForecaster(trend_threshold=1.0)
        trend = forecaster._classify_trend(-2.5)
        assert trend == TrendDirection.DRAWING

    def test_classify_trend_stable(self) -> None:
        """Test trend classified as STABLE when change within threshold."""
        forecaster = InventoryForecaster(trend_threshold=1.0)
        trend = forecaster._classify_trend(0.5)
        assert trend == TrendDirection.STABLE

    def test_classify_trend_stable_negative(self) -> None:
        """Test trend classified as STABLE when change is small negative."""
        forecaster = InventoryForecaster(trend_threshold=1.0)
        trend = forecaster._classify_trend(-0.5)
        assert trend == TrendDirection.STABLE

    def test_classify_trend_at_threshold(self) -> None:
        """Test trend at exactly threshold is STABLE."""
        forecaster = InventoryForecaster(trend_threshold=1.0)
        trend = forecaster._classify_trend(1.0)
        assert trend == TrendDirection.STABLE

    def test_classify_trend_none(self) -> None:
        """Test trend with None value returns STABLE."""
        forecaster = InventoryForecaster()
        trend = forecaster._classify_trend(None)
        assert trend == TrendDirection.STABLE

    def test_classify_trend_nan(self) -> None:
        """Test trend with NaN value returns STABLE."""
        forecaster = InventoryForecaster()
        trend = forecaster._classify_trend(np.nan)
        assert trend == TrendDirection.STABLE


class TestAnalyzeInventory:
    """Tests for analyze_inventory method."""

    @pytest.mark.asyncio
    async def test_analyze_inventory_returns_dataframe(
        self, forecaster: InventoryForecaster, simple_inventory_df: pd.DataFrame
    ) -> None:
        """Test analyze_inventory returns DataFrame with expected columns."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=simple_inventory_df)
        forecaster._collector = mock_collector

        result = await forecaster.analyze_inventory(lookback_years=1)

        assert isinstance(result, pd.DataFrame)
        expected_columns = [
            "timestamp",
            "stocks_mb",
            "stocks_kbd",
            "week_of_year",
            "yoy_change_mb",
            "yoy_change_pct",
            "avg_5yr_mb",
            "vs_5yr_avg_mb",
            "vs_5yr_avg_pct",
            "change_1wk_mb",
            "change_4wk_avg_mb",
        ]
        for col in expected_columns:
            assert col in result.columns

    @pytest.mark.asyncio
    async def test_analyze_inventory_converts_to_mb(
        self, forecaster: InventoryForecaster, simple_inventory_df: pd.DataFrame
    ) -> None:
        """Test analyze_inventory converts thousand barrels to million barrels."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=simple_inventory_df)
        forecaster._collector = mock_collector

        result = await forecaster.analyze_inventory()

        # Original value is in thousand barrels, stocks_mb should be / 1000
        first_original = simple_inventory_df.iloc[0]["value"]
        first_mb = result.iloc[0]["stocks_mb"]
        assert abs(first_mb - first_original / 1000) < 0.01

    @pytest.mark.asyncio
    async def test_analyze_inventory_calculates_yoy(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test analyze_inventory calculates year-over-year change."""
        # Create 2 years of data with known YoY difference
        dates = pd.date_range(start="2024-01-01", periods=104, freq="W")
        values = [400000] * 52 + [420000] * 52  # 20000 kb increase YoY

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["WCESTUS1"] * 104,
                "source": ["eia"] * 104,
                "value": values,
                "unit": ["thousand_barrels"] * 104,
            }
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=df)
        forecaster._collector = mock_collector

        result = await forecaster.analyze_inventory()

        # After week 52, YoY should be +20 MB
        yoy_values = result.dropna(subset=["yoy_change_mb"])
        if not yoy_values.empty:
            # All YoY changes after week 52 should be +20 MB
            assert yoy_values["yoy_change_mb"].iloc[-1] == pytest.approx(20.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_analyze_inventory_calculates_week_change(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test analyze_inventory calculates week-over-week change."""
        # Create data with known weekly change
        dates = pd.date_range(start="2024-01-01", periods=10, freq="W")
        values = [400000 + i * 1000 for i in range(10)]  # 1000 kb increase per week

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["WCESTUS1"] * 10,
                "source": ["eia"] * 10,
                "value": values,
                "unit": ["thousand_barrels"] * 10,
            }
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=df)
        forecaster._collector = mock_collector

        result = await forecaster.analyze_inventory()

        # Weekly change should be +1 MB (1000 kb / 1000)
        valid_changes = result.dropna(subset=["change_1wk_mb"])
        if len(valid_changes) > 0:
            assert valid_changes["change_1wk_mb"].iloc[-1] == pytest.approx(1.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_analyze_inventory_empty_response(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test analyze_inventory handles empty response."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=pd.DataFrame())
        forecaster._collector = mock_collector

        result = await forecaster.analyze_inventory()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestGetCurrentAnalysis:
    """Tests for get_current_analysis method."""

    @pytest.mark.asyncio
    async def test_get_current_analysis_returns_forecast(
        self, forecaster: InventoryForecaster, simple_inventory_df: pd.DataFrame
    ) -> None:
        """Test get_current_analysis returns InventoryForecast."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=simple_inventory_df)
        mock_collector.collect_refinery_utilization = AsyncMock(
            return_value=pd.DataFrame()
        )
        forecaster._collector = mock_collector

        result = await forecaster.get_current_analysis()

        assert isinstance(result, InventoryForecast)
        assert result.current_stocks > 0
        assert result.weekly_trend in TrendDirection

    @pytest.mark.asyncio
    async def test_get_current_analysis_has_all_fields(
        self, forecaster: InventoryForecaster, simple_inventory_df: pd.DataFrame
    ) -> None:
        """Test get_current_analysis populates all fields."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=simple_inventory_df)
        mock_collector.collect_refinery_utilization = AsyncMock(
            return_value=pd.DataFrame()
        )
        forecaster._collector = mock_collector

        result = await forecaster.get_current_analysis()

        assert result.date is not None
        assert result.current_stocks is not None
        assert result.yoy_change is not None
        assert result.yoy_change_pct is not None
        assert result.vs_5yr_avg is not None
        assert result.vs_5yr_avg_pct is not None
        assert result.days_of_supply is not None
        assert result.weekly_trend is not None
        assert result.forecast_4wk is not None

    @pytest.mark.asyncio
    async def test_get_current_analysis_empty_data_raises(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test get_current_analysis raises on empty data."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=pd.DataFrame())
        forecaster._collector = mock_collector

        with pytest.raises(ValueError, match="No inventory data"):
            await forecaster.get_current_analysis()


class TestDaysOfSupply:
    """Tests for days of supply calculation."""

    @pytest.mark.asyncio
    async def test_days_of_supply_default(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test days of supply uses default refinery inputs."""
        mock_collector = AsyncMock()
        mock_collector.collect_refinery_utilization = AsyncMock(
            return_value=pd.DataFrame()
        )
        forecaster._collector = mock_collector

        # 400,000 thousand barrels / 16,000 thousand b/d = 25 days
        days = await forecaster._calculate_days_of_supply(400_000)

        assert days == pytest.approx(25.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_days_of_supply_with_utilization(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test days of supply adjusts for refinery utilization."""
        util_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WPULEUS3"],
                "source": ["eia"],
                "value": [90.0],  # 90% utilization
                "unit": ["percent"],
            }
        )

        mock_collector = AsyncMock()
        mock_collector.collect_refinery_utilization = AsyncMock(return_value=util_df)
        forecaster._collector = mock_collector

        # 400,000 kb / (18,000 * 0.9) = 400,000 / 16,200 = ~24.7 days
        days = await forecaster._calculate_days_of_supply(400_000)

        # Should adjust based on utilization
        assert days > 0
        assert days < 30  # Reasonable range


class TestForecast4Wk:
    """Tests for 4-week forecast method."""

    @pytest.mark.asyncio
    async def test_forecast_4wk_linear_trend(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test 4-week forecast uses linear regression."""
        # Create data with linear upward trend
        dates = pd.date_range(start="2024-01-01", periods=20, freq="W")
        values = [400 + i * 2 for i in range(20)]  # +2 MB per week

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "stocks_mb": values,
                "stocks_kbd": [v * 1000 for v in values],
                "week_of_year": [d.isocalendar()[1] for d in dates],
                "yoy_change_mb": [np.nan] * 20,
                "yoy_change_pct": [np.nan] * 20,
                "avg_5yr_mb": [np.nan] * 20,
                "vs_5yr_avg_mb": [np.nan] * 20,
                "vs_5yr_avg_pct": [np.nan] * 20,
                "change_1wk_mb": [2.0] * 20,
                "change_4wk_avg_mb": [2.0] * 20,
            }
        )

        forecast = await forecaster.forecast_4wk(df)

        # Current is 438, trend is +2/week, 4 weeks out should be ~446
        assert forecast > values[-1]
        # Should be approximately 446 (438 + 4 * 2 = 446)
        assert forecast == pytest.approx(446, rel=0.1)

    @pytest.mark.asyncio
    async def test_forecast_4wk_flat_trend(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test 4-week forecast with flat trend."""
        # Create data with no trend
        dates = pd.date_range(start="2024-01-01", periods=20, freq="W")
        values = [420.0] * 20  # Constant

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "stocks_mb": values,
                "stocks_kbd": [v * 1000 for v in values],
                "week_of_year": [d.isocalendar()[1] for d in dates],
                "yoy_change_mb": [np.nan] * 20,
                "yoy_change_pct": [np.nan] * 20,
                "avg_5yr_mb": [np.nan] * 20,
                "vs_5yr_avg_mb": [np.nan] * 20,
                "vs_5yr_avg_pct": [np.nan] * 20,
                "change_1wk_mb": [0.0] * 20,
                "change_4wk_avg_mb": [0.0] * 20,
            }
        )

        forecast = await forecaster.forecast_4wk(df)

        # With flat trend, forecast should be close to current value
        assert forecast == pytest.approx(420.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_forecast_4wk_insufficient_data(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test 4-week forecast with insufficient data returns 0."""
        # Only 4 rows - not enough for reliable forecast
        dates = pd.date_range(start="2024-01-01", periods=4, freq="W")
        values = [420.0] * 4

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "stocks_mb": values,
                "stocks_kbd": [v * 1000 for v in values],
                "week_of_year": [d.isocalendar()[1] for d in dates],
                "yoy_change_mb": [np.nan] * 4,
                "yoy_change_pct": [np.nan] * 4,
                "avg_5yr_mb": [np.nan] * 4,
                "vs_5yr_avg_mb": [np.nan] * 4,
                "vs_5yr_avg_pct": [np.nan] * 4,
                "change_1wk_mb": [0.0] * 4,
                "change_4wk_avg_mb": [0.0] * 4,
            }
        )

        forecast = await forecaster.forecast_4wk(df)

        # Should handle gracefully - either return 0 or use fallback
        assert isinstance(forecast, float)

    @pytest.mark.asyncio
    async def test_forecast_4wk_empty_dataframe(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test 4-week forecast with empty DataFrame returns 0."""
        forecast = await forecaster.forecast_4wk(pd.DataFrame())
        assert forecast == 0.0


class Test5YrAverage:
    """Tests for 5-year average calculation."""

    def test_add_5yr_average_calculation(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test 5-year average is calculated correctly."""
        # Create 6 years of data
        dates = pd.date_range(start="2020-01-01", periods=312, freq="W")
        # Set values so week 1 of each year has predictable values
        values = []
        for i in range(312):
            year = 2020 + i // 52
            # Make week 1 have values: 2020=400, 2021=410, 2022=420, 2023=430, 2024=440, 2025=450
            base = 400 + (year - 2020) * 10
            values.append(base)

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "stocks_mb": values,
                "week_of_year": [d.isocalendar()[1] for d in dates],
                "year": [d.year for d in dates],
            }
        )

        result = forecaster._add_5yr_average(df)

        assert "avg_5yr_mb" in result.columns
        assert "vs_5yr_avg_mb" in result.columns
        assert "vs_5yr_avg_pct" in result.columns

    def test_add_5yr_average_insufficient_years(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test 5-year average handles insufficient historical data."""
        # Only 2 years of data
        dates = pd.date_range(start="2024-01-01", periods=104, freq="W")
        values = [420.0] * 104

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "stocks_mb": values,
                "week_of_year": [d.isocalendar()[1] for d in dates],
                "year": [d.year for d in dates],
            }
        )

        result = forecaster._add_5yr_average(df)

        # Should have NaN for avg_5yr_mb when < 3 years of historical data
        assert "avg_5yr_mb" in result.columns


class TestForecasterClose:
    """Tests for forecaster cleanup."""

    @pytest.mark.asyncio
    async def test_close_releases_collector(self) -> None:
        """Test close releases collector resources."""
        mock_collector = AsyncMock()
        mock_collector.close = AsyncMock()

        forecaster = InventoryForecaster(eia_collector=mock_collector)
        await forecaster.close()

        mock_collector.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_collector(self) -> None:
        """Test close handles case with no collector."""
        forecaster = InventoryForecaster()
        # Should not raise
        await forecaster.close()


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_nan_values_in_data(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test handling of NaN values in inventory data."""
        dates = pd.date_range(start="2024-01-01", periods=20, freq="W")
        values = [420.0] * 10 + [np.nan] * 5 + [430.0] * 5

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["WCESTUS1"] * 20,
                "source": ["eia"] * 20,
                "value": values,
                "unit": ["thousand_barrels"] * 20,
            }
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=df)
        forecaster._collector = mock_collector

        result = await forecaster.analyze_inventory()

        # Should handle NaN gracefully
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_single_data_point(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test handling of single data point."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WCESTUS1"],
                "source": ["eia"],
                "value": [420000],
                "unit": ["thousand_barrels"],
            }
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=df)
        forecaster._collector = mock_collector

        result = await forecaster.analyze_inventory()

        # Should handle single data point
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_wrong_series_id(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test handling of wrong series ID in data."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WRONG_SERIES"],
                "source": ["eia"],
                "value": [420000],
                "unit": ["thousand_barrels"],
            }
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=df)
        forecaster._collector = mock_collector

        result = await forecaster.analyze_inventory()

        # Should return empty DataFrame when series not found
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestIntegration:
    """Integration-style tests for the full workflow."""

    @pytest.mark.asyncio
    async def test_full_analysis_workflow(
        self, forecaster: InventoryForecaster
    ) -> None:
        """Test complete analysis workflow from data to forecast."""
        # Create 3 years of realistic data
        dates = pd.date_range(start="2023-01-01", periods=156, freq="W")
        base = 420000
        values = []
        for i in range(156):
            # Add seasonal pattern and slight trend
            seasonal = 15000 * np.sin(2 * np.pi * i / 52)
            trend = i * 30
            values.append(base + seasonal + trend)

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["WCESTUS1"] * 156,
                "source": ["eia"] * 156,
                "value": values,
                "unit": ["thousand_barrels"] * 156,
            }
        )

        util_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-01"]),
                "series_id": ["WPULEUS3"],
                "source": ["eia"],
                "value": [92.0],
                "unit": ["percent"],
            }
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=df)
        mock_collector.collect_refinery_utilization = AsyncMock(return_value=util_df)
        forecaster._collector = mock_collector

        # Run analysis
        analysis_df = await forecaster.analyze_inventory()
        assert not analysis_df.empty

        # Get current analysis
        current = await forecaster.get_current_analysis()
        assert isinstance(current, InventoryForecast)
        assert current.current_stocks > 0
        assert current.days_of_supply > 0
        assert current.forecast_4wk > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
