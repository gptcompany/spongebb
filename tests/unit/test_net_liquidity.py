"""Unit tests for NetLiquidityCalculator."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from liquidity.calculators.net_liquidity import (
    DAILY_SERIES,
    SENTIMENT_THRESHOLDS,
    UNIT_TO_BILLIONS,
    WEEKLY_SERIES,
    NetLiquidityCalculator,
    NetLiquidityResult,
    Sentiment,
)


class TestSentiment:
    """Tests for Sentiment enum and classification."""

    def test_sentiment_enum_values(self):
        """Test Sentiment enum has correct values."""
        assert Sentiment.BULLISH.value == "BULLISH"
        assert Sentiment.NEUTRAL.value == "NEUTRAL"
        assert Sentiment.BEARISH.value == "BEARISH"

    def test_sentiment_thresholds(self):
        """Test sentiment thresholds are correct."""
        assert SENTIMENT_THRESHOLDS["bullish"] == 50.0
        assert SENTIMENT_THRESHOLDS["bearish"] == -50.0


class TestNetLiquidityResult:
    """Tests for NetLiquidityResult dataclass."""

    def test_dataclass_creation(self):
        """Test NetLiquidityResult can be created."""
        result = NetLiquidityResult(
            timestamp=datetime.now(UTC),
            net_liquidity=6000.0,
            walcl=8000.0,
            tga=1000.0,
            rrp=1000.0,
            weekly_delta=50.0,
            monthly_delta=100.0,
            delta_60d=150.0,
            delta_90d=200.0,
            sentiment=Sentiment.NEUTRAL,
        )
        assert result.net_liquidity == 6000.0
        assert result.walcl == 8000.0
        assert result.sentiment == Sentiment.NEUTRAL


class TestSeriesConfig:
    """Tests for FRED series configuration."""

    def test_daily_series_keys(self):
        """Test daily series has required keys."""
        assert "walcl" in DAILY_SERIES
        assert "tga" in DAILY_SERIES
        assert "rrp" in DAILY_SERIES

    def test_weekly_series_keys(self):
        """Test weekly series has required keys."""
        assert "walcl" in WEEKLY_SERIES
        assert "tga" in WEEKLY_SERIES
        assert "rrp" in WEEKLY_SERIES

    def test_unit_conversions(self):
        """Test unit conversion factors."""
        assert UNIT_TO_BILLIONS["WALCL"] == 0.001  # millions -> billions
        assert UNIT_TO_BILLIONS["WTREGEN"] == 0.001
        assert UNIT_TO_BILLIONS["WDTGAL"] == 1.0  # already billions
        assert UNIT_TO_BILLIONS["RRPONTSYD"] == 1.0
        assert UNIT_TO_BILLIONS["WLRRAL"] == 1.0


class TestNetLiquidityCalculator:
    """Tests for NetLiquidityCalculator class."""

    def test_init_default(self):
        """Test default initialization uses weekly series."""
        calc = NetLiquidityCalculator()
        assert calc._use_daily is False
        assert calc.series_config == WEEKLY_SERIES

    def test_init_daily(self):
        """Test initialization with daily series."""
        calc = NetLiquidityCalculator(use_daily_series=True)
        assert calc._use_daily is True
        assert calc.series_config == DAILY_SERIES

    def test_repr_weekly(self):
        """Test string representation for weekly."""
        calc = NetLiquidityCalculator()
        assert "weekly" in repr(calc)

    def test_repr_daily(self):
        """Test string representation for daily."""
        calc = NetLiquidityCalculator(use_daily_series=True)
        assert "daily" in repr(calc)

    def test_series_config_is_copy(self):
        """Test series_config returns a copy."""
        calc = NetLiquidityCalculator()
        config = calc.series_config
        config["test"] = "value"
        assert "test" not in calc.series_config


class TestGetSentiment:
    """Tests for sentiment classification."""

    def test_bullish_above_threshold(self):
        """Test BULLISH when delta > 50."""
        assert NetLiquidityCalculator.get_sentiment(51.0) == Sentiment.BULLISH
        assert NetLiquidityCalculator.get_sentiment(100.0) == Sentiment.BULLISH
        assert NetLiquidityCalculator.get_sentiment(1000.0) == Sentiment.BULLISH

    def test_bearish_below_threshold(self):
        """Test BEARISH when delta < -50."""
        assert NetLiquidityCalculator.get_sentiment(-51.0) == Sentiment.BEARISH
        assert NetLiquidityCalculator.get_sentiment(-100.0) == Sentiment.BEARISH
        assert NetLiquidityCalculator.get_sentiment(-1000.0) == Sentiment.BEARISH

    def test_neutral_in_range(self):
        """Test NEUTRAL when -50 <= delta <= 50."""
        assert NetLiquidityCalculator.get_sentiment(0.0) == Sentiment.NEUTRAL
        assert NetLiquidityCalculator.get_sentiment(50.0) == Sentiment.NEUTRAL
        assert NetLiquidityCalculator.get_sentiment(-50.0) == Sentiment.NEUTRAL
        assert NetLiquidityCalculator.get_sentiment(25.0) == Sentiment.NEUTRAL
        assert NetLiquidityCalculator.get_sentiment(-25.0) == Sentiment.NEUTRAL

    def test_boundary_values(self):
        """Test exact boundary values."""
        # Exactly at threshold is NEUTRAL
        assert NetLiquidityCalculator.get_sentiment(50.0) == Sentiment.NEUTRAL
        assert NetLiquidityCalculator.get_sentiment(-50.0) == Sentiment.NEUTRAL
        # Just above/below is BULLISH/BEARISH
        assert NetLiquidityCalculator.get_sentiment(50.01) == Sentiment.BULLISH
        assert NetLiquidityCalculator.get_sentiment(-50.01) == Sentiment.BEARISH


class TestCalculateDelta:
    """Tests for delta calculation."""

    @pytest.fixture
    def calculator(self):
        """Create a calculator instance."""
        return NetLiquidityCalculator()

    def test_delta_with_empty_df(self, calculator):
        """Test delta with empty DataFrame."""
        df = pd.DataFrame(columns=["timestamp", "net_liquidity"])
        assert calculator._calculate_delta(df, days=7) == 0.0

    def test_delta_with_single_row(self, calculator):
        """Test delta with single row DataFrame."""
        df = pd.DataFrame(
            {
                "timestamp": [datetime.now(UTC)],
                "net_liquidity": [6000.0],
            }
        )
        assert calculator._calculate_delta(df, days=7) == 0.0

    def test_delta_calculation(self, calculator):
        """Test delta calculation with multiple rows."""
        now = datetime.now(UTC)
        df = pd.DataFrame(
            {
                "timestamp": [
                    now - timedelta(days=10),
                    now - timedelta(days=7),
                    now,
                ],
                "net_liquidity": [5900.0, 5950.0, 6000.0],
            }
        )
        # Delta should be current (6000) - 7 days ago (5950) = 50
        delta = calculator._calculate_delta(df, days=7)
        assert delta == pytest.approx(50.0)

    def test_delta_not_enough_history(self, calculator):
        """Test delta when not enough historical data."""
        now = datetime.now(UTC)
        df = pd.DataFrame(
            {
                "timestamp": [now - timedelta(days=3), now],
                "net_liquidity": [5950.0, 6000.0],
            }
        )
        # Asking for 7-day delta but only 3 days of data
        delta = calculator._calculate_delta(df, days=7)
        # Should return 0.0 since no data at target date
        assert delta == 0.0


class TestCalculate:
    """Tests for the calculate method."""

    @pytest.fixture
    def mock_fred_data(self):
        """Create mock FRED data."""
        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(30, -1, -1)]
        return pd.DataFrame(
            {
                "timestamp": dates * 3,
                "series_id": (["WALCL"] * 31 + ["WDTGAL"] * 31 + ["WLRRAL"] * 31),
                "value": (
                    [8000000.0] * 31  # WALCL in millions
                    + [800.0] * 31  # WDTGAL in billions
                    + [500.0] * 31  # WLRRAL in billions
                ),
                "source": ["fred"] * 93,
            }
        )

    @pytest.mark.asyncio
    async def test_calculate_success(self, mock_fred_data):
        """Test successful calculation."""
        calc = NetLiquidityCalculator()

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_fred_data
            result = await calc.calculate()

            assert not result.empty
            assert "net_liquidity" in result.columns
            assert "walcl" in result.columns
            assert "tga" in result.columns
            assert "rrp" in result.columns

    @pytest.mark.asyncio
    async def test_calculate_empty_data(self):
        """Test calculation with empty data."""
        calc = NetLiquidityCalculator()

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = pd.DataFrame()
            result = await calc.calculate()

            assert result.empty
            assert list(result.columns) == [
                "timestamp",
                "net_liquidity",
                "walcl",
                "tga",
                "rrp",
            ]

    @pytest.mark.asyncio
    async def test_calculate_missing_walcl(self):
        """Test calculation with missing WALCL series."""
        calc = NetLiquidityCalculator()
        now = datetime.now(UTC)

        # Data without WALCL
        mock_data = pd.DataFrame(
            {
                "timestamp": [now] * 2,
                "series_id": ["WDTGAL", "WLRRAL"],
                "value": [800.0, 500.0],
                "source": ["fred"] * 2,
            }
        )

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            result = await calc.calculate()

            # Should return empty since WALCL is critical
            assert result.empty


class TestGetCurrent:
    """Tests for the get_current method."""

    @pytest.mark.asyncio
    async def test_get_current_success(self):
        """Test successful get_current call."""
        calc = NetLiquidityCalculator()
        now = datetime.now(UTC)

        # Create mock data with enough history for deltas
        dates = [now - timedelta(days=i) for i in range(100, -1, -1)]
        mock_df = pd.DataFrame(
            {
                "timestamp": dates,
                "net_liquidity": [5000 + i * 10 for i in range(101)],
                "walcl": [8000.0] * 101,
                "tga": [800.0] * 101,
                "rrp": [500.0] * 101,
            }
        )

        with patch.object(calc, "calculate", new_callable=AsyncMock) as mock:
            mock.return_value = mock_df
            result = await calc.get_current()

            assert isinstance(result, NetLiquidityResult)
            assert result.net_liquidity == mock_df.iloc[-1]["net_liquidity"]
            assert isinstance(result.sentiment, Sentiment)

    @pytest.mark.asyncio
    async def test_get_current_empty_data(self):
        """Test get_current with empty data raises ValueError."""
        calc = NetLiquidityCalculator()

        with patch.object(calc, "calculate", new_callable=AsyncMock) as mock:
            mock.return_value = pd.DataFrame()

            with pytest.raises(ValueError, match="No data available"):
                await calc.get_current()

    @pytest.mark.asyncio
    async def test_get_current_timestamp_conversion(self):
        """Test timestamp is properly converted to UTC."""
        calc = NetLiquidityCalculator()
        now = datetime.now(UTC)

        mock_df = pd.DataFrame(
            {
                "timestamp": [now - timedelta(days=1), now],
                "net_liquidity": [5900.0, 6000.0],
                "walcl": [8000.0, 8000.0],
                "tga": [800.0, 800.0],
                "rrp": [500.0, 500.0],
            }
        )

        with patch.object(calc, "calculate", new_callable=AsyncMock) as mock:
            mock.return_value = mock_df
            result = await calc.get_current()

            assert result.timestamp.tzinfo is not None
