"""Tests for asset price loader."""

from unittest.mock import patch

import pandas as pd

from liquidity.backtesting.data.asset_loader import ASSET_TICKERS, AssetLoader


class TestAssetLoader:
    """Test asset loader."""

    def test_asset_tickers_mapping(self):
        """Verify ticker mapping."""
        assert ASSET_TICKERS["btc"] == "BTC-USD"
        assert ASSET_TICKERS["spx"] == "^GSPC"
        assert ASSET_TICKERS["gold"] == "GC=F"

    @patch("liquidity.backtesting.data.asset_loader.yf.download")
    def test_load_prices_returns_dataframe(self, mock_download):
        """Load prices should return DataFrame."""
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        mock_data = pd.DataFrame(
            {
                ("Adj Close", "BTC-USD"): [
                    100,
                    101,
                    102,
                    103,
                    104,
                    105,
                    106,
                    107,
                    108,
                    109,
                ],
                ("Adj Close", "^GSPC"): [
                    4000,
                    4010,
                    4020,
                    4030,
                    4040,
                    4050,
                    4060,
                    4070,
                    4080,
                    4090,
                ],
            },
            index=dates,
        )
        mock_data.columns = pd.MultiIndex.from_tuples(mock_data.columns)
        mock_download.return_value = mock_data

        loader = AssetLoader()
        prices = loader.load_prices(
            ["btc", "spx"],
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-01-15"),
        )

        assert isinstance(prices, pd.DataFrame)
        assert len(prices) == 10

    @patch("liquidity.backtesting.data.asset_loader.yf.download")
    def test_load_returns_calculates_correctly(self, mock_download):
        """Returns should be calculated correctly."""
        dates = pd.date_range("2024-01-01", periods=3, freq="B")
        mock_data = pd.DataFrame(
            {
                "Adj Close": [100.0, 110.0, 121.0],
            },
            index=dates,
        )
        mock_download.return_value = mock_data

        loader = AssetLoader()
        returns = loader.load_returns(
            ["test"],
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-01-05"),
            log_returns=False,
        )

        # First return: (110-100)/100 = 0.10
        assert abs(returns.iloc[0, 0] - 0.10) < 0.01

    def test_align_with_liquidity(self):
        """Alignment should find common index."""
        dates1 = pd.date_range("2024-01-01", periods=10, freq="B")
        dates2 = pd.date_range("2024-01-05", periods=10, freq="B")

        returns = pd.DataFrame({"btc": range(10)}, index=dates1)
        liquidity = pd.DataFrame({"net": range(10)}, index=dates2)

        loader = AssetLoader()
        aligned_r, aligned_l = loader.align_with_liquidity(returns, liquidity)

        assert len(aligned_r) == len(aligned_l)
        assert aligned_r.index.equals(aligned_l.index)
