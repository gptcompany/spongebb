"""Unit tests for RealRatesAnalyzer."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from liquidity.analyzers.real_rates import (
    REAL_RATES_SERIES,
    RealRatesAnalyzer,
    RealRatesState,
)


@pytest.fixture
def analyzer():
    """Default analyzer instance with mocked collector."""
    with patch("liquidity.analyzers.real_rates.FredCollector") as mock_collector_class:
        mock_collector = MagicMock()
        mock_collector_class.return_value = mock_collector
        analyzer = RealRatesAnalyzer()
        analyzer._collector = mock_collector
        yield analyzer


@pytest.fixture
def sample_data():
    """Sample FRED data for testing."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")

    # Create data in long format (as returned by FredCollector)
    data = []
    for i, date in enumerate(dates):
        # TIPS yields (real rates)
        data.append({
            "timestamp": date,
            "series_id": "DFII10",
            "value": 1.5 + i * 0.01,  # 10Y TIPS
            "source": "fred",
            "unit": "percent",
        })
        data.append({
            "timestamp": date,
            "series_id": "DFII5",
            "value": 1.3 + i * 0.01,  # 5Y TIPS
            "source": "fred",
            "unit": "percent",
        })
        # Nominal yields
        data.append({
            "timestamp": date,
            "series_id": "DGS10",
            "value": 4.0 + i * 0.02,  # 10Y nominal
            "source": "fred",
            "unit": "percent",
        })
        data.append({
            "timestamp": date,
            "series_id": "DGS5",
            "value": 3.8 + i * 0.02,  # 5Y nominal
            "source": "fred",
            "unit": "percent",
        })

    return pd.DataFrame(data)


class TestRealRatesState:
    """Test RealRatesState dataclass."""

    def test_state_creation(self):
        state = RealRatesState(
            timestamp=datetime.now(UTC),
            tips_10y=1.5,
            tips_5y=1.3,
            nominal_10y=4.0,
            nominal_5y=3.8,
            bei_10y=2.5,
            bei_5y=2.5,
            forward_5y5y=2.5,
        )

        assert state.tips_10y == 1.5
        assert state.tips_5y == 1.3
        assert state.nominal_10y == 4.0
        assert state.nominal_5y == 3.8
        assert state.bei_10y == 2.5
        assert state.bei_5y == 2.5
        assert state.forward_5y5y == 2.5

    def test_bei_calculation_logic(self):
        """BEI should equal nominal minus real."""
        tips_10y = 1.5
        nominal_10y = 4.0
        expected_bei = nominal_10y - tips_10y  # 2.5

        state = RealRatesState(
            timestamp=datetime.now(UTC),
            tips_10y=tips_10y,
            tips_5y=1.3,
            nominal_10y=nominal_10y,
            nominal_5y=3.8,
            bei_10y=expected_bei,
            bei_5y=2.5,
            forward_5y5y=2.5,
        )

        assert state.bei_10y == expected_bei

    def test_forward_5y5y_calculation_logic(self):
        """5Y5Y forward should equal 2 * BEI_10Y - BEI_5Y."""
        bei_10y = 2.5
        bei_5y = 2.3
        expected_forward = 2 * bei_10y - bei_5y  # 2.7

        state = RealRatesState(
            timestamp=datetime.now(UTC),
            tips_10y=1.5,
            tips_5y=1.5,
            nominal_10y=4.0,
            nominal_5y=3.8,
            bei_10y=bei_10y,
            bei_5y=bei_5y,
            forward_5y5y=expected_forward,
        )

        assert state.forward_5y5y == expected_forward


class TestBreakevenCalculation:
    """Test breakeven inflation calculation."""

    @pytest.mark.asyncio
    async def test_calculate_breakeven_returns_dataframe(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        result = await analyzer.calculate_breakeven()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_calculate_breakeven_columns(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        result = await analyzer.calculate_breakeven()

        expected_columns = [
            "timestamp",
            "tips_10y",
            "tips_5y",
            "nominal_10y",
            "nominal_5y",
            "bei_10y",
            "bei_5y",
            "forward_5y5y",
        ]
        assert list(result.columns) == expected_columns

    @pytest.mark.asyncio
    async def test_bei_calculation(self, analyzer, sample_data):
        """BEI = nominal - TIPS."""
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        result = await analyzer.calculate_breakeven()

        # Check first row
        row = result.iloc[0]
        expected_bei_10y = row["nominal_10y"] - row["tips_10y"]
        expected_bei_5y = row["nominal_5y"] - row["tips_5y"]

        assert abs(row["bei_10y"] - expected_bei_10y) < 0.001
        assert abs(row["bei_5y"] - expected_bei_5y) < 0.001

    @pytest.mark.asyncio
    async def test_forward_5y5y_calculation(self, analyzer, sample_data):
        """5Y5Y forward = 2 * BEI_10Y - BEI_5Y."""
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        result = await analyzer.calculate_breakeven()

        # Check each row
        for _, row in result.iterrows():
            expected_forward = 2 * row["bei_10y"] - row["bei_5y"]
            assert abs(row["forward_5y5y"] - expected_forward) < 0.001

    @pytest.mark.asyncio
    async def test_empty_data_handling(self, analyzer):
        analyzer._collector.collect = AsyncMock(return_value=pd.DataFrame())

        result = await analyzer.calculate_breakeven()

        assert result.empty
        assert "bei_10y" in result.columns

    @pytest.mark.asyncio
    async def test_missing_series_handling(self, analyzer):
        """Handle missing series gracefully."""
        # Data with only 10Y series
        data = pd.DataFrame([
            {"timestamp": datetime.now(UTC), "series_id": "DFII10", "value": 1.5, "source": "fred", "unit": "percent"},
            {"timestamp": datetime.now(UTC), "series_id": "DGS10", "value": 4.0, "source": "fred", "unit": "percent"},
        ])
        analyzer._collector.collect = AsyncMock(return_value=data)

        result = await analyzer.calculate_breakeven()

        assert result.empty

    @pytest.mark.asyncio
    async def test_nan_values_dropped(self, analyzer, sample_data):
        """NaN values should be dropped from result."""
        # Add a row with NaN
        nan_row = pd.DataFrame([{
            "timestamp": datetime(2024, 1, 15),
            "series_id": "DFII10",
            "value": np.nan,
            "source": "fred",
            "unit": "percent",
        }])
        data_with_nan = pd.concat([sample_data, nan_row], ignore_index=True)
        analyzer._collector.collect = AsyncMock(return_value=data_with_nan)

        result = await analyzer.calculate_breakeven()

        # Should not have NaN in result
        assert not result.isna().any().any()


class TestGetCurrentState:
    """Test get_current_state method."""

    @pytest.mark.asyncio
    async def test_returns_state_object(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        state = await analyzer.get_current_state()

        assert isinstance(state, RealRatesState)

    @pytest.mark.asyncio
    async def test_returns_latest_values(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        state = await analyzer.get_current_state()

        # Should be the last date in sample_data
        assert state.timestamp == pd.Timestamp("2024-01-10")

    @pytest.mark.asyncio
    async def test_raises_on_empty_data(self, analyzer):
        analyzer._collector.collect = AsyncMock(return_value=pd.DataFrame())

        with pytest.raises(ValueError, match="No real rates data available"):
            await analyzer.get_current_state()

    @pytest.mark.asyncio
    async def test_state_values_are_floats(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        state = await analyzer.get_current_state()

        assert isinstance(state.tips_10y, float)
        assert isinstance(state.tips_5y, float)
        assert isinstance(state.nominal_10y, float)
        assert isinstance(state.nominal_5y, float)
        assert isinstance(state.bei_10y, float)
        assert isinstance(state.bei_5y, float)
        assert isinstance(state.forward_5y5y, float)


class TestGetBeiHistory:
    """Test get_bei_history method."""

    @pytest.mark.asyncio
    async def test_returns_full_history(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        result = await analyzer.get_bei_history()

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_resample_weekly(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        result = await analyzer.get_bei_history(resample="W")

        # 10 days should collapse to 2 weeks
        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_resample_none_returns_daily(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        result = await analyzer.get_bei_history(resample=None)

        assert len(result) == 10


class TestInterpretation:
    """Test interpretation methods."""

    def test_interpret_bei_very_low(self, analyzer):
        result = analyzer.interpret_bei(1.0)
        assert "Deflationary" in result or "Very low" in result

    def test_interpret_bei_below_target(self, analyzer):
        result = analyzer.interpret_bei(1.8)
        assert "Below" in result or "Subdued" in result

    def test_interpret_bei_near_target(self, analyzer):
        result = analyzer.interpret_bei(2.2)
        assert "Near" in result or "anchored" in result

    def test_interpret_bei_above_target(self, analyzer):
        result = analyzer.interpret_bei(2.7)
        assert "Above" in result or "Elevated" in result

    def test_interpret_bei_high(self, analyzer):
        result = analyzer.interpret_bei(3.5)
        assert "High" in result or "unanchoring" in result

    def test_interpret_forward_below_target(self, analyzer):
        result = analyzer.interpret_forward_5y5y(1.5)
        assert "deflation" in result.lower() or "below" in result.lower()

    def test_interpret_forward_near_target(self, analyzer):
        result = analyzer.interpret_forward_5y5y(2.0)
        assert "anchored" in result.lower() or "target" in result.lower()

    def test_interpret_forward_slightly_elevated(self, analyzer):
        result = analyzer.interpret_forward_5y5y(2.3)
        assert "monitor" in result.lower() or "elevated" in result.lower()

    def test_interpret_forward_elevated(self, analyzer):
        result = analyzer.interpret_forward_5y5y(2.8)
        assert "elevated" in result.lower() or "unanchoring" in result.lower()


class TestSeriesMap:
    """Test FRED series mapping."""

    def test_series_map_has_required_keys(self):
        required = ["tips_10y", "tips_5y", "nominal_10y", "nominal_5y"]
        for key in required:
            assert key in REAL_RATES_SERIES

    def test_series_map_fred_ids(self):
        assert REAL_RATES_SERIES["tips_10y"] == "DFII10"
        assert REAL_RATES_SERIES["tips_5y"] == "DFII5"
        assert REAL_RATES_SERIES["nominal_10y"] == "DGS10"
        assert REAL_RATES_SERIES["nominal_5y"] == "DGS5"


class TestDateRangeDefaults:
    """Test default date range handling."""

    @pytest.mark.asyncio
    async def test_default_start_date_one_year_ago(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        await analyzer.calculate_breakeven()

        # Check that collect was called with start_date about 1 year ago
        call_args = analyzer._collector.collect.call_args
        start_date = call_args.kwargs.get("start_date") or call_args.args[1] if len(call_args.args) > 1 else None

        if start_date:
            days_ago = (datetime.now(UTC) - start_date).days
            assert 360 <= days_ago <= 370

    @pytest.mark.asyncio
    async def test_custom_date_range(self, analyzer, sample_data):
        analyzer._collector.collect = AsyncMock(return_value=sample_data)

        start = datetime(2023, 6, 1, tzinfo=UTC)
        end = datetime(2023, 12, 31, tzinfo=UTC)

        await analyzer.calculate_breakeven(start_date=start, end_date=end)

        call_args = analyzer._collector.collect.call_args
        assert call_args.kwargs.get("start_date") == start or (len(call_args.args) > 1 and call_args.args[1] == start)
        assert call_args.kwargs.get("end_date") == end or (len(call_args.args) > 2 and call_args.args[2] == end)
