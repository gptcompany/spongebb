"""Unit tests for China rates collector.

Tests use mocked akshare responses to verify:
- DataFrame structure and normalization
- SHIBOR tenor parsing
- DR007 fallback to SHIBOR proxy
- Error handling for empty/invalid responses
"""

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from liquidity.collectors.china_rates import (
    SHIBOR_TENORS,
    ChinaRatesCollector,
)


@pytest.fixture
def mock_shibor_data() -> pd.DataFrame:
    """Sample akshare SHIBOR response."""
    return pd.DataFrame({
        "日期": ["2026-02-04", "2026-02-03", "2026-02-02"],
        "O/N-定价": [1.325, 1.320, 1.318],
        "O/N-涨跌幅": [0.005, 0.002, -0.001],
        "1W-定价": [1.650, 1.645, 1.640],
        "1W-涨跌幅": [0.005, 0.005, 0.003],
        "2W-定价": [1.750, 1.745, 1.740],
        "2W-涨跌幅": [0.005, 0.005, 0.003],
        "1M-定价": [1.850, 1.845, 1.840],
        "1M-涨跌幅": [0.005, 0.005, 0.002],
        "3M-定价": [1.950, 1.945, 1.940],
        "3M-涨跌幅": [0.005, 0.005, 0.002],
        "6M-定价": [2.050, 2.045, 2.040],
        "6M-涨跌幅": [0.005, 0.005, 0.002],
        "9M-定价": [2.150, 2.145, 2.140],
        "9M-涨跌幅": [0.005, 0.005, 0.002],
        "1Y-定价": [2.250, 2.245, 2.240],
        "1Y-涨跌幅": [0.005, 0.005, 0.002],
    })


@pytest.fixture
def mock_dr007_data() -> pd.DataFrame:
    """Sample akshare DR007 response."""
    return pd.DataFrame({
        "日期": ["2026-02-04", "2026-02-03", "2026-02-02"],
        "利率": [1.70, 1.68, 1.65],
    })


@pytest.fixture
def mock_akshare(mock_shibor_data: pd.DataFrame, mock_dr007_data: pd.DataFrame) -> MagicMock:
    """Create a mock akshare module."""
    mock_ak = MagicMock()
    mock_ak.macro_china_shibor_all.return_value = mock_shibor_data
    mock_ak.rate_interbank.return_value = mock_dr007_data
    return mock_ak


class TestChinaRatesCollector:
    """Unit tests for ChinaRatesCollector."""

    @pytest.mark.unit
    async def test_collect_shibor_returns_dataframe(
        self, mock_shibor_data: pd.DataFrame, mock_akshare: MagicMock
    ) -> None:
        """Test SHIBOR collection returns properly formatted DataFrame."""
        collector = ChinaRatesCollector()

        with patch.dict(sys.modules, {"akshare": mock_akshare}):
            result = await collector.collect_shibor()

            assert isinstance(result, pd.DataFrame)
            assert not result.empty
            assert set(result.columns) >= {"timestamp", "series_id", "source", "value", "unit"}

    @pytest.mark.unit
    async def test_collect_shibor_all_tenors(
        self, mock_shibor_data: pd.DataFrame, mock_akshare: MagicMock
    ) -> None:
        """Test SHIBOR collection includes all tenors."""
        collector = ChinaRatesCollector()

        with patch.dict(sys.modules, {"akshare": mock_akshare}):
            result = await collector.collect_shibor()

            # Should have data for all tenors
            series_ids = result["series_id"].unique()
            for tenor_name in SHIBOR_TENORS.values():
                expected_id = f"SHIBOR_{tenor_name}"
                assert expected_id in series_ids, f"Missing {expected_id}"

    @pytest.mark.unit
    async def test_collect_shibor_data_format(
        self, mock_shibor_data: pd.DataFrame, mock_akshare: MagicMock
    ) -> None:
        """Test SHIBOR data values are properly formatted."""
        collector = ChinaRatesCollector()

        with patch.dict(sys.modules, {"akshare": mock_akshare}):
            result = await collector.collect_shibor()

            # Source should be 'akshare'
            assert (result["source"] == "akshare").all()

            # Unit should be 'percent'
            assert (result["unit"] == "percent").all()

            # Values should be numeric and reasonable (0-10%)
            assert result["value"].dtype in ["float64", "float32"]
            assert (result["value"] > 0).all()
            assert (result["value"] < 10).all()

    @pytest.mark.unit
    async def test_collect_shibor_handles_empty_response(self) -> None:
        """Test handling of empty API response."""
        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        mock_ak.macro_china_shibor_all.return_value = pd.DataFrame()

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect_shibor()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0
            assert "timestamp" in result.columns

    @pytest.mark.unit
    async def test_collect_shibor_handles_none_response(self) -> None:
        """Test handling of None API response."""
        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        mock_ak.macro_china_shibor_all.return_value = None

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect_shibor()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

    @pytest.mark.unit
    async def test_collect_dr007_returns_dataframe(
        self, mock_dr007_data: pd.DataFrame
    ) -> None:
        """Test DR007 collection returns properly formatted DataFrame."""
        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        mock_ak.rate_interbank.return_value = mock_dr007_data

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect_dr007()

            assert isinstance(result, pd.DataFrame)
            assert not result.empty
            assert set(result.columns) >= {"timestamp", "series_id", "source", "value", "unit"}

    @pytest.mark.unit
    async def test_collect_dr007_fallback_to_shibor(
        self, mock_shibor_data: pd.DataFrame
    ) -> None:
        """Test DR007 falls back to SHIBOR proxy if rate_interbank fails."""
        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        # rate_interbank fails
        mock_ak.rate_interbank.side_effect = Exception("API error")
        # SHIBOR succeeds
        mock_ak.macro_china_shibor_all.return_value = mock_shibor_data

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect_dr007()

            # Should fallback to SHIBOR proxy
            assert not result.empty
            assert (result["series_id"] == "DR007_PROXY").all()
            assert (result["source"] == "akshare_shibor_proxy").all()

    @pytest.mark.unit
    async def test_collect_dr007_data_values(
        self, mock_dr007_data: pd.DataFrame
    ) -> None:
        """Test DR007 data values are properly formatted."""
        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        mock_ak.rate_interbank.return_value = mock_dr007_data

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect_dr007()

            # Series ID should be DR007
            assert (result["series_id"] == "DR007").all()

            # Source should be 'akshare'
            assert (result["source"] == "akshare").all()

            # Values should be numeric and reasonable (0-10%)
            assert result["value"].dtype in ["float64", "float32"]
            assert (result["value"] > 0).all()
            assert (result["value"] < 10).all()

    @pytest.mark.unit
    async def test_collect_all_combines_data(
        self,
        mock_shibor_data: pd.DataFrame,
        mock_dr007_data: pd.DataFrame,
    ) -> None:
        """Test collect_all combines SHIBOR and DR007 data."""
        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        mock_ak.macro_china_shibor_all.return_value = mock_shibor_data
        mock_ak.rate_interbank.return_value = mock_dr007_data

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect_all()

            # Should have both SHIBOR and DR007 data
            series_ids = result["series_id"].unique()
            has_shibor = any("SHIBOR" in s for s in series_ids)
            has_dr007 = any("DR007" in s for s in series_ids)

            assert has_shibor, "Expected SHIBOR data"
            assert has_dr007, "Expected DR007 data"

    @pytest.mark.unit
    async def test_collect_generic_shibor(
        self, mock_shibor_data: pd.DataFrame
    ) -> None:
        """Test generic collect method with data_type='shibor'."""
        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        mock_ak.macro_china_shibor_all.return_value = mock_shibor_data

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect(data_type="shibor")

            assert not result.empty
            assert all("SHIBOR" in s for s in result["series_id"])

    @pytest.mark.unit
    async def test_collect_generic_dr007(
        self, mock_dr007_data: pd.DataFrame
    ) -> None:
        """Test generic collect method with data_type='dr007'."""
        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        mock_ak.rate_interbank.return_value = mock_dr007_data

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect(data_type="dr007")

            assert not result.empty
            assert (result["series_id"] == "DR007").all()

    @pytest.mark.unit
    async def test_collect_invalid_data_type(self) -> None:
        """Test collect raises ValueError for invalid data_type."""
        collector = ChinaRatesCollector()

        with pytest.raises(ValueError, match="Unknown data_type"):
            await collector.collect(data_type="invalid")

    @pytest.mark.unit
    def test_get_cached_baseline(self) -> None:
        """Test cached baseline returns valid data."""
        collector = ChinaRatesCollector()

        result = collector.get_cached_baseline()

        assert not result.empty
        assert len(result) == 2  # SHIBOR_1_WEEK and DR007_PROXY

        # Check structure
        assert set(result.columns) >= {"timestamp", "series_id", "source", "value", "unit", "stale"}

        # Check values
        assert "SHIBOR_1_WEEK" in result["series_id"].values
        assert "DR007_PROXY" in result["series_id"].values
        assert (result["source"] == "cached_baseline").all()
        assert (result["stale"] == True).all()  # noqa: E712

    @pytest.mark.unit
    async def test_collector_registered(self) -> None:
        """Test that china_rates collector is registered."""
        from liquidity.collectors import registry

        assert "china_rates" in registry.list_collectors()
        collector_cls = registry.get("china_rates")
        assert collector_cls is ChinaRatesCollector

    @pytest.mark.unit
    def test_shibor_tenors_mapping(self) -> None:
        """Test SHIBOR tenors mapping is complete."""
        expected_tenors = ["O/N", "1W", "2W", "1M", "3M", "6M", "9M", "1Y"]
        for tenor in expected_tenors:
            assert tenor in SHIBOR_TENORS, f"Missing tenor: {tenor}"

    @pytest.mark.unit
    async def test_date_filtering(
        self, mock_shibor_data: pd.DataFrame
    ) -> None:
        """Test date range filtering works correctly."""
        collector = ChinaRatesCollector()

        # Set narrow date range that includes Feb 3 only
        start_date = datetime(2026, 2, 3)
        end_date = datetime(2026, 2, 3, 23, 59, 59)

        mock_ak = MagicMock()
        mock_ak.macro_china_shibor_all.return_value = mock_shibor_data

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect_shibor(
                start_date=start_date,
                end_date=end_date,
            )

            # Should only have data from Feb 3
            if not result.empty:
                dates = result["timestamp"].dt.date.unique()
                assert len(dates) == 1
                assert dates[0] == datetime(2026, 2, 3).date()


class TestChinaRatesErrorHandling:
    """Tests for error handling in ChinaRatesCollector."""

    @pytest.mark.unit
    async def test_api_exception_handling(self) -> None:
        """Test handling of API exceptions."""
        from liquidity.collectors.base import CollectorFetchError

        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        mock_ak.macro_china_shibor_all.side_effect = RuntimeError("Network error")

        with patch.dict(sys.modules, {"akshare": mock_ak}), pytest.raises(CollectorFetchError):
            await collector.collect_shibor()

    @pytest.mark.unit
    async def test_collect_all_partial_failure(
        self, mock_shibor_data: pd.DataFrame
    ) -> None:
        """Test collect_all handles partial failures gracefully."""
        collector = ChinaRatesCollector()

        mock_ak = MagicMock()
        # SHIBOR succeeds
        mock_ak.macro_china_shibor_all.return_value = mock_shibor_data
        # DR007 fails (will trigger fallback to SHIBOR proxy)
        mock_ak.rate_interbank.side_effect = Exception("API error")

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            result = await collector.collect_all()

            # Should still return SHIBOR data (via DR007 proxy fallback to SHIBOR)
            assert not result.empty
