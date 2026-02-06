"""Asset price loader for backtesting."""


import numpy as np
import pandas as pd
import yfinance as yf

# Asset ticker mapping
ASSET_TICKERS = {
    "btc": "BTC-USD",
    "spx": "^GSPC",
    "gold": "GC=F",
    "tlt": "TLT",
    "hyg": "HYG",
    "dxy": "DX-Y.NYB",
}


class AssetLoader:
    """Load asset prices for backtesting."""

    def __init__(self, cache_dir: str | None = None):
        """Initialize loader.

        Args:
            cache_dir: Optional directory for caching data
        """
        self.cache_dir = cache_dir

    def load_prices(
        self,
        assets: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pd.DataFrame:
        """Load adjusted close prices for assets.

        Args:
            assets: List of asset names (btc, spx, gold, tlt, etc.)
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with asset prices as columns
        """
        tickers = [ASSET_TICKERS.get(a.lower(), a) for a in assets]

        # Download in batch
        data = yf.download(
            tickers,
            start=start_date,
            end=end_date,
            progress=False,
        )

        # Extract adjusted close
        if len(tickers) == 1:
            prices = data["Adj Close"].to_frame(name=assets[0])
        else:
            prices = data["Adj Close"]
            prices.columns = [a.lower() for a in assets]

        return prices

    def load_returns(
        self,
        assets: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        log_returns: bool = True,
    ) -> pd.DataFrame:
        """Load asset returns.

        Args:
            assets: List of asset names
            start_date: Start date
            end_date: End date
            log_returns: If True, use log returns; else simple returns

        Returns:
            DataFrame with returns as columns
        """
        prices = self.load_prices(assets, start_date, end_date)

        returns = (
            np.log(prices / prices.shift(1)) if log_returns else prices.pct_change()
        )

        return returns.dropna()

    def align_with_liquidity(
        self,
        asset_returns: pd.DataFrame,
        liquidity_data: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Align asset returns with liquidity data on common index.

        Args:
            asset_returns: DataFrame of returns
            liquidity_data: DataFrame of liquidity metrics

        Returns:
            Tuple of (aligned_returns, aligned_liquidity)
        """
        # Find common index
        common_idx = asset_returns.index.intersection(liquidity_data.index)

        return (
            asset_returns.loc[common_idx],
            liquidity_data.loc[common_idx],
        )
