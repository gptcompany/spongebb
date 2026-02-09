"""Unit tests for OilTermStructureCollector."""

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest

from liquidity.collectors.base import CollectorFetchError
from liquidity.collectors.oil_term_structure import (
    DEFAULT_MOMENTUM_WINDOWS,
    SERIES_MAP,
    UNIT_MAP,
    OilTermStructureCollector,
)
from liquidity.collectors.registry import registry


class TestSeriesMapping:
    """Test series and unit mappings."""

    def test_wti_in_series_map(self):
        assert "wti_front" in SERIES_MAP
        assert SERIES_MAP["wti_front"] == "CL=F"

    def test_brent_in_series_map(self):
        assert "brent_front" in SERIES_MAP
        assert SERIES_MAP["brent_front"] == "BZ=F"

    def test_unit_map_has_price_units(self):
        assert UNIT_MAP["wti_front"] == "usd_per_barrel"
        assert UNIT_MAP["brent_front"] == "usd_per_barrel"

    def test_unit_map_has_momentum_units(self):
        assert UNIT_MAP["wti_front_momentum_5d"] == "percent"
        assert UNIT_MAP["wti_front_momentum_20d"] == "percent"

    def test_default_momentum_windows(self):
        assert 5 in DEFAULT_MOMENTUM_WINDOWS
        assert 20 in DEFAULT_MOMENTUM_WINDOWS


class TestOilTermStructureCollectorInit:
    """Test collector initialization."""

    def test_default_name(self):
        collector = OilTermStructureCollector()
        assert collector.name == "oil_term_structure"

    def test_custom_name(self):
        collector = OilTermStructureCollector(name="custom_oil")
        assert collector.name == "custom_oil"

    def test_default_momentum_windows(self):
        collector = OilTermStructureCollector()
        assert collector.momentum_windows == DEFAULT_MOMENTUM_WINDOWS

    def test_custom_momentum_windows(self):
        collector = OilTermStructureCollector(momentum_windows=[10, 30])
        assert collector.momentum_windows == [10, 30]


class TestCollect:
    """Test collect method."""

    @pytest.fixture
    def mock_yf_data_single(self):
        """Mock data for single symbol."""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        return pd.DataFrame(
            {"Close": [70 + i * 0.5 for i in range(30)]},
            index=dates,
        )

    @pytest.fixture
    def mock_yf_data_multi(self):
        """Mock data for multiple symbols."""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        return pd.DataFrame(
            {
                ("Close", "CL=F"): [70 + i * 0.5 for i in range(30)],
                ("Close", "BZ=F"): [72 + i * 0.5 for i in range(30)],
            },
            index=dates,
        )

    @pytest.mark.asyncio
    async def test_collect_returns_dataframe(self, mock_yf_data_single):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_yf_data_single):
            result = await collector.collect(["wti_front"])

        assert isinstance(result, pd.DataFrame)
        assert not result.empty

    @pytest.mark.asyncio
    async def test_collect_has_required_columns(self, mock_yf_data_single):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_yf_data_single):
            result = await collector.collect(["wti_front"])

        required_cols = ["timestamp", "series_id", "source", "value", "unit"]
        for col in required_cols:
            assert col in result.columns

    @pytest.mark.asyncio
    async def test_collect_correct_source(self, mock_yf_data_single):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_yf_data_single):
            result = await collector.collect(["wti_front"])

        assert (result["source"] == "yfinance").all()

    @pytest.mark.asyncio
    async def test_collect_correct_unit(self, mock_yf_data_single):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_yf_data_single):
            result = await collector.collect(["wti_front"])

        assert (result["unit"] == "usd_per_barrel").all()

    @pytest.mark.asyncio
    async def test_collect_empty_on_api_failure(self):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", side_effect=Exception("API error")), pytest.raises(CollectorFetchError):
            await collector.collect(["wti_front"])

    @pytest.mark.asyncio
    async def test_collect_empty_on_no_data(self):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=pd.DataFrame()):
            result = await collector.collect(["wti_front"])

        assert result.empty

    @pytest.mark.asyncio
    async def test_collect_invalid_symbol_ignored(self, mock_yf_data_single):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_yf_data_single):
            result = await collector.collect(["wti_front", "invalid_symbol"])

        # Should still have wti_front data
        assert "wti_front" in result["series_id"].values

    @pytest.mark.asyncio
    async def test_collect_all_invalid_symbols(self):
        collector = OilTermStructureCollector()

        result = await collector.collect(["invalid_1", "invalid_2"])

        assert result.empty

    @pytest.mark.asyncio
    async def test_collect_date_validation(self):
        collector = OilTermStructureCollector()

        # start_date >= end_date should return empty
        result = await collector.collect(
            ["wti_front"],
            start_date=datetime(2024, 2, 1, tzinfo=UTC),
            end_date=datetime(2024, 1, 1, tzinfo=UTC),
        )

        assert result.empty


class TestCollectWti:
    """Test collect_wti convenience method."""

    @pytest.fixture
    def mock_yf_data(self):
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        return pd.DataFrame(
            {"Close": [70 + i * 0.5 for i in range(30)]},
            index=dates,
        )

    @pytest.mark.asyncio
    async def test_collect_wti_returns_wti_only(self, mock_yf_data):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_yf_data):
            result = await collector.collect_wti()

        series_ids = result["series_id"].unique()
        assert len(series_ids) == 1
        assert series_ids[0] == "wti_front"


class TestMomentum:
    """Test momentum calculations."""

    @pytest.fixture
    def mock_uptrend_data(self):
        """Price data with steady uptrend."""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        prices = [70 + i * 0.5 for i in range(30)]  # Steady uptrend
        return pd.DataFrame({"Close": prices}, index=dates)

    @pytest.fixture
    def mock_downtrend_data(self):
        """Price data with steady downtrend."""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        prices = [85 - i * 0.5 for i in range(30)]  # Steady downtrend
        return pd.DataFrame({"Close": prices}, index=dates)

    @pytest.mark.asyncio
    async def test_momentum_series_added(self, mock_uptrend_data):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_uptrend_data):
            result = await collector.collect_with_momentum()

        series_ids = result["series_id"].unique()
        assert "wti_front" in series_ids
        assert "wti_front_momentum_5d" in series_ids
        assert "wti_front_momentum_20d" in series_ids

    @pytest.mark.asyncio
    async def test_momentum_positive_in_uptrend(self, mock_uptrend_data):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_uptrend_data):
            result = await collector.collect_with_momentum()

        # Get latest 5d momentum
        momentum_5d = result[result["series_id"] == "wti_front_momentum_5d"]
        latest_momentum = momentum_5d.iloc[-1]["value"]

        assert latest_momentum > 0  # Positive momentum in uptrend

    @pytest.mark.asyncio
    async def test_momentum_negative_in_downtrend(self, mock_downtrend_data):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_downtrend_data):
            result = await collector.collect_with_momentum()

        # Get latest 5d momentum
        momentum_5d = result[result["series_id"] == "wti_front_momentum_5d"]
        latest_momentum = momentum_5d.iloc[-1]["value"]

        assert latest_momentum < 0  # Negative momentum in downtrend

    @pytest.mark.asyncio
    async def test_momentum_unit_is_percent(self, mock_uptrend_data):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_uptrend_data):
            result = await collector.collect_with_momentum()

        momentum_data = result[result["series_id"].str.contains("momentum")]
        assert (momentum_data["unit"] == "percent").all()

    @pytest.mark.asyncio
    async def test_momentum_source_is_calculated(self, mock_uptrend_data):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_uptrend_data):
            result = await collector.collect_with_momentum()

        momentum_data = result[result["series_id"].str.contains("momentum")]
        assert (momentum_data["source"] == "calculated").all()

    @pytest.mark.asyncio
    async def test_momentum_no_nan_values(self, mock_uptrend_data):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_uptrend_data):
            result = await collector.collect_with_momentum()

        # All values should be non-null
        assert not result["value"].isna().any()


class TestBrentWtiSpread:
    """Test Brent-WTI spread calculation."""

    def test_spread_positive_when_brent_higher(self):
        df = pd.DataFrame([
            {"timestamp": datetime(2024, 1, 1), "series_id": "wti_front", "value": 70.0, "source": "yf", "unit": "usd"},
            {"timestamp": datetime(2024, 1, 1), "series_id": "brent_front", "value": 75.0, "source": "yf", "unit": "usd"},
        ])

        spread = OilTermStructureCollector.calculate_brent_wti_spread(df)

        assert len(spread) == 1
        assert spread.iloc[0]["brent_wti_spread"] == 5.0

    def test_spread_negative_when_wti_higher(self):
        df = pd.DataFrame([
            {"timestamp": datetime(2024, 1, 1), "series_id": "wti_front", "value": 80.0, "source": "yf", "unit": "usd"},
            {"timestamp": datetime(2024, 1, 1), "series_id": "brent_front", "value": 78.0, "source": "yf", "unit": "usd"},
        ])

        spread = OilTermStructureCollector.calculate_brent_wti_spread(df)

        assert spread.iloc[0]["brent_wti_spread"] == -2.0

    def test_spread_empty_when_missing_data(self):
        df = pd.DataFrame([
            {"timestamp": datetime(2024, 1, 1), "series_id": "wti_front", "value": 70.0, "source": "yf", "unit": "usd"},
        ])

        spread = OilTermStructureCollector.calculate_brent_wti_spread(df)

        assert spread.empty


class TestGetCurrentPrice:
    """Test get_current_wti_price method."""

    @pytest.fixture
    def mock_price_data(self):
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        return pd.DataFrame({"Close": [70 + i for i in range(10)]}, index=dates)

    @pytest.mark.asyncio
    async def test_returns_latest_price(self, mock_price_data):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=mock_price_data):
            price = await collector.get_current_wti_price()

        assert price == 79.0  # 70 + 9

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self):
        collector = OilTermStructureCollector()

        with patch("yfinance.download", return_value=pd.DataFrame()):
            price = await collector.get_current_wti_price()

        assert price is None


class TestRegistry:
    """Test collector registration."""

    def test_collector_registered(self):
        # Force import to trigger registration
        from liquidity.collectors import oil_term_structure  # noqa: F401

        assert "oil_term_structure" in registry._collectors

    def test_instantiate_from_registry(self):
        from liquidity.collectors import oil_term_structure  # noqa: F401

        collector_cls = registry.get("oil_term_structure")
        assert collector_cls is OilTermStructureCollector

        # Verify we can instantiate it
        instance = collector_cls()
        assert isinstance(instance, OilTermStructureCollector)
