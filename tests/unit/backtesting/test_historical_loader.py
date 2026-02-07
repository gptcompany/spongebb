"""Tests for historical data loader."""

from unittest.mock import Mock, patch

import pandas as pd

from liquidity.backtesting.data.historical_loader import (
    PUBLICATION_LAGS,
    HistoricalLoader,
    PointInTimeData,
)


class TestHistoricalLoader:
    """Test historical data loader."""

    def test_publication_lags_defined(self):
        """Verify publication lags are defined for key series."""
        assert "WALCL" in PUBLICATION_LAGS
        assert "WTREGEN" in PUBLICATION_LAGS
        assert PUBLICATION_LAGS["WALCL"] == 7

    @patch("liquidity.backtesting.data.historical_loader.Fred")
    def test_get_series_with_lag_applies_shift(self, mock_fred_class):
        """Lagged series should be shifted forward."""
        # Setup mock
        mock_fred = Mock()
        mock_fred_class.return_value = mock_fred

        dates = pd.date_range("2024-01-01", periods=10, freq="W")
        mock_data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], index=dates)
        mock_fred.get_series.return_value = mock_data

        loader = HistoricalLoader(api_key="test")
        result = loader.get_series_with_lag(
            "WALCL",
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-03-01"),
        )

        # Result should be shifted by 7 days
        assert result.index[0] == dates[0] + pd.Timedelta(days=7)

    @patch("liquidity.backtesting.data.historical_loader.Fred")
    def test_load_liquidity_data_calculates_net(self, mock_fred_class):
        """Net liquidity should be WALCL - TGA - RRP."""
        mock_fred = Mock()
        mock_fred_class.return_value = mock_fred

        def mock_get_series(series_id, **kwargs):
            dates = pd.date_range("2024-01-01", periods=5, freq="B")
            if series_id == "WALCL":
                return pd.Series([100, 100, 100, 100, 100], index=dates)
            elif series_id == "WTREGEN":
                return pd.Series([10, 10, 10, 10, 10], index=dates)
            elif series_id == "RRPONTSYD":
                return pd.Series([20, 20, 20, 20, 20], index=dates)
            return pd.Series()

        mock_fred.get_series.side_effect = mock_get_series

        loader = HistoricalLoader(api_key="test")
        df = loader.load_liquidity_data(
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-01-10"),
        )

        # Net = 100 - 10 - 20 = 70 (after forward fill)
        assert "net_liquidity" in df.columns


class TestPointInTimeData:
    """Test PointInTimeData dataclass."""

    def test_dataclass_fields(self):
        """Verify dataclass fields."""
        pit = PointInTimeData(
            series_id="WALCL",
            as_of_date=pd.Timestamp("2024-01-15"),
            data=pd.Series([1, 2, 3]),
            publication_lag_days=7,
        )
        assert pit.series_id == "WALCL"
        assert pit.publication_lag_days == 7
