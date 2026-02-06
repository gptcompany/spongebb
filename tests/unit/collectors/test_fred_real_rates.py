"""Unit tests for FRED collector real rates functionality.

Tests use mocked FRED responses to verify:
- TIPS and nominal yield series are in SERIES_MAP
- Unit mappings are correct
- fetch_real_rates() method fetches correct symbols
- DataFrame structure and normalization
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from liquidity.collectors.fred import SERIES_MAP, UNIT_MAP, FredCollector

# Real rates series constants for testing
REAL_RATES_SERIES = ["DFII10", "DFII5", "DGS5"]


@pytest.fixture
def mock_real_rates_data() -> pd.DataFrame:
    """Sample FRED real rates response."""
    return pd.DataFrame([
        {
            "timestamp": pd.Timestamp("2026-01-15"),
            "series_id": "DFII10",
            "source": "fred",
            "value": 2.15,
            "unit": "percent",
        },
        {
            "timestamp": pd.Timestamp("2026-01-15"),
            "series_id": "DFII5",
            "source": "fred",
            "value": 1.95,
            "unit": "percent",
        },
        {
            "timestamp": pd.Timestamp("2026-01-15"),
            "series_id": "DGS5",
            "source": "fred",
            "value": 4.35,
            "unit": "percent",
        },
        {
            "timestamp": pd.Timestamp("2026-01-16"),
            "series_id": "DFII10",
            "source": "fred",
            "value": 2.18,
            "unit": "percent",
        },
        {
            "timestamp": pd.Timestamp("2026-01-16"),
            "series_id": "DFII5",
            "source": "fred",
            "value": 1.98,
            "unit": "percent",
        },
        {
            "timestamp": pd.Timestamp("2026-01-16"),
            "series_id": "DGS5",
            "source": "fred",
            "value": 4.40,
            "unit": "percent",
        },
    ])


class TestSeriesMapConfiguration:
    """Tests for SERIES_MAP configuration."""

    @pytest.mark.unit
    def test_tips_10y_in_series_map(self) -> None:
        """Test 10-Year TIPS is in SERIES_MAP."""
        assert "tips_10y" in SERIES_MAP
        assert SERIES_MAP["tips_10y"] == "DFII10"

    @pytest.mark.unit
    def test_tips_5y_in_series_map(self) -> None:
        """Test 5-Year TIPS is in SERIES_MAP."""
        assert "tips_5y" in SERIES_MAP
        assert SERIES_MAP["tips_5y"] == "DFII5"

    @pytest.mark.unit
    def test_nominal_5y_in_series_map(self) -> None:
        """Test 5-Year Treasury Nominal is in SERIES_MAP."""
        assert "nominal_5y" in SERIES_MAP
        assert SERIES_MAP["nominal_5y"] == "DGS5"


class TestUnitMapConfiguration:
    """Tests for UNIT_MAP configuration."""

    @pytest.mark.unit
    def test_dfii10_unit_mapping(self) -> None:
        """Test DFII10 has correct unit mapping."""
        assert "DFII10" in UNIT_MAP
        assert UNIT_MAP["DFII10"] == "percent"

    @pytest.mark.unit
    def test_dfii5_unit_mapping(self) -> None:
        """Test DFII5 has correct unit mapping."""
        assert "DFII5" in UNIT_MAP
        assert UNIT_MAP["DFII5"] == "percent"

    @pytest.mark.unit
    def test_dgs5_unit_mapping(self) -> None:
        """Test DGS5 has correct unit mapping."""
        assert "DGS5" in UNIT_MAP
        assert UNIT_MAP["DGS5"] == "percent"


class TestFetchRealRates:
    """Tests for fetch_real_rates method."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_real_rates_calls_collect(
        self, mock_real_rates_data: pd.DataFrame
    ) -> None:
        """Test fetch_real_rates delegates to collect with correct symbols."""
        collector = FredCollector()
        collector.collect = AsyncMock(return_value=mock_real_rates_data)

        result = await collector.fetch_real_rates()

        collector.collect.assert_called_once()
        call_args = collector.collect.call_args
        symbols = call_args.args[0] if call_args.args else call_args.kwargs.get("symbols")
        assert set(symbols) == set(REAL_RATES_SERIES)
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_real_rates_with_date_range(
        self, mock_real_rates_data: pd.DataFrame
    ) -> None:
        """Test fetch_real_rates passes date range to collect."""
        collector = FredCollector()
        collector.collect = AsyncMock(return_value=mock_real_rates_data)

        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 1, tzinfo=UTC)

        await collector.fetch_real_rates(start_date=start, end_date=end)

        call_args = collector.collect.call_args
        assert call_args.kwargs.get("start_date") == start or call_args.args[1] == start
        assert call_args.kwargs.get("end_date") == end or call_args.args[2] == end

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_real_rates_returns_correct_columns(
        self, mock_real_rates_data: pd.DataFrame
    ) -> None:
        """Test fetch_real_rates returns DataFrame with correct structure."""
        collector = FredCollector()
        collector.collect = AsyncMock(return_value=mock_real_rates_data)

        result = await collector.fetch_real_rates()

        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert set(result.columns) == expected_columns

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fetch_real_rates_returns_all_series(
        self, mock_real_rates_data: pd.DataFrame
    ) -> None:
        """Test fetch_real_rates returns all expected series."""
        collector = FredCollector()
        collector.collect = AsyncMock(return_value=mock_real_rates_data)

        result = await collector.fetch_real_rates()

        series_present = set(result["series_id"].unique())
        assert series_present == set(REAL_RATES_SERIES)


class TestBreakevenInflationCalculation:
    """Tests for calculating BEI from real rates data."""

    @pytest.mark.unit
    def test_bei_5y_calculation(self, mock_real_rates_data: pd.DataFrame) -> None:
        """Test 5-Year Breakeven Inflation calculation.

        BEI_5Y = DGS5 (nominal) - DFII5 (real)
        """
        # Pivot to wide format
        pivot = mock_real_rates_data.pivot(
            index="timestamp", columns="series_id", values="value"
        )

        # Calculate BEI
        bei_5y = pivot["DGS5"] - pivot["DFII5"]

        # First day: 4.35 - 1.95 = 2.40
        assert abs(bei_5y.iloc[0] - 2.40) < 0.01

        # Second day: 4.40 - 1.98 = 2.42
        assert abs(bei_5y.iloc[1] - 2.42) < 0.01

    @pytest.mark.unit
    def test_real_rates_values_reasonable(
        self, mock_real_rates_data: pd.DataFrame
    ) -> None:
        """Test that mock real rates values are in reasonable range.

        TIPS yields typically range from -1% to +3% in normal conditions.
        Nominal 5Y Treasury typically ranges from 1% to 6%.
        """
        tips_10y = mock_real_rates_data[
            mock_real_rates_data["series_id"] == "DFII10"
        ]["value"]
        tips_5y = mock_real_rates_data[
            mock_real_rates_data["series_id"] == "DFII5"
        ]["value"]
        nominal_5y = mock_real_rates_data[
            mock_real_rates_data["series_id"] == "DGS5"
        ]["value"]

        # TIPS yields should be reasonable (can be negative)
        assert (tips_10y >= -1.0).all() and (tips_10y <= 4.0).all()
        assert (tips_5y >= -1.0).all() and (tips_5y <= 4.0).all()

        # Nominal yield should be reasonable
        assert (nominal_5y >= 0.5).all() and (nominal_5y <= 7.0).all()

        # Nominal should be higher than TIPS (positive BEI)
        assert (nominal_5y.values > tips_5y.values).all()


class TestCollectorRegistration:
    """Tests for collector registration."""

    @pytest.mark.unit
    def test_fred_collector_has_series_map(self) -> None:
        """Test FredCollector class has SERIES_MAP attribute."""
        assert hasattr(FredCollector, "SERIES_MAP")
        assert FredCollector.SERIES_MAP is SERIES_MAP

    @pytest.mark.unit
    def test_real_rates_series_accessible_via_collector(self) -> None:
        """Test real rates series are accessible via collector."""
        assert "tips_10y" in FredCollector.SERIES_MAP
        assert "tips_5y" in FredCollector.SERIES_MAP
        assert "nominal_5y" in FredCollector.SERIES_MAP
