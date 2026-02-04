"""ETF flows collector for commodity ETF tracking.

Tracks shares outstanding and prices for commodity ETFs:
- GLD: SPDR Gold Shares
- SLV: iShares Silver Trust
- USO: United States Oil Fund
- CPER: United States Copper Index Fund
- DBA: Invesco DB Agriculture Fund

ETF flows indicate where real money is moving. Changes in shares outstanding
reflect creation/redemption activity driven by investor demand.

Flow estimation requires historical shares data, which yfinance doesn't provide.
For v1, we collect current snapshots. Full flow tracking requires persistence.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# ETF ticker mapping
ETF_TICKERS: dict[str, str] = {
    "gld": "GLD",  # SPDR Gold Shares
    "slv": "SLV",  # iShares Silver Trust
    "uso": "USO",  # United States Oil Fund
    "cper": "CPER",  # United States Copper Index Fund
    "dba": "DBA",  # Invesco DB Agriculture Fund
}

# ETF to underlying commodity mapping
ETF_UNDERLYING: dict[str, str] = {
    "GLD": "gold",
    "SLV": "silver",
    "USO": "oil",
    "CPER": "copper",
    "DBA": "agriculture",
}

# Period to timedelta mapping
PERIOD_MAP: dict[str, timedelta] = {
    "1d": timedelta(days=1),
    "5d": timedelta(days=5),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "60d": timedelta(days=60),
    "90d": timedelta(days=90),
    "1y": timedelta(days=365),
    "2y": timedelta(days=730),
    "5y": timedelta(days=1825),
}


class ETFFlowCollector(BaseCollector[pd.DataFrame]):
    """ETF flows collector using yfinance.

    Tracks commodity ETFs for flow analysis:
    - Current shares outstanding (from .info)
    - Historical prices (from batch download)
    - Estimated AUM changes

    Note: yfinance doesn't provide historical shares outstanding data.
    Full flow tracking requires storing snapshots over time in QuestDB.

    Example:
        collector = ETFFlowCollector()

        # Get current shares outstanding
        df = await collector.collect_current_shares()

        # Get historical prices
        df = await collector.collect_historical_prices()

        # Get precious metal ETFs only
        df = await collector.collect_precious_metal_etfs()
    """

    ETF_TICKERS = ETF_TICKERS
    ETF_UNDERLYING = ETF_UNDERLYING

    def __init__(
        self,
        name: str = "etf_flows",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize ETF flow collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()

    async def collect(
        self,
        etfs: list[str] | None = None,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect ETF data (current shares + historical prices).

        Args:
            etfs: List of ETF tickers. Defaults to all ETFs.
            period: Time period for historical prices.

        Returns:
            DataFrame with historical price data.
        """
        return await self.collect_historical_prices(etfs=etfs, period=period)

    async def collect_current_shares(
        self,
        etfs: list[str] | None = None,
    ) -> pd.DataFrame:
        """Fetch current shares outstanding for ETFs.

        Uses yf.Ticker().info to get current snapshot of:
        - Shares outstanding
        - Total assets
        - NAV price
        - Market price

        Args:
            etfs: List of ETF tickers. Defaults to all ETFs.

        Returns:
            DataFrame with current ETF data.

        Raises:
            CollectorFetchError: If data fetch fails.
        """
        if etfs is None:
            etfs = list(ETF_TICKERS.values())

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(self._fetch_shares_sync, etfs)

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("ETF shares fetch failed: %s", e)
            raise CollectorFetchError(f"ETF shares fetch failed: {e}") from e

    def _fetch_shares_sync(self, etfs: list[str]) -> pd.DataFrame:
        """Synchronous fetch for shares outstanding.

        Args:
            etfs: List of ETF tickers.

        Returns:
            DataFrame with shares outstanding data.
        """
        logger.info("Fetching shares outstanding for ETFs: %s", etfs)

        results = []
        for etf in etfs:
            try:
                ticker = yf.Ticker(etf)
                info = ticker.info

                results.append(
                    {
                        "timestamp": datetime.now(UTC),
                        "etf": etf,
                        "underlying": ETF_UNDERLYING.get(etf, "unknown"),
                        "shares_outstanding": info.get("sharesOutstanding"),
                        "total_assets": info.get("totalAssets"),
                        "nav_price": info.get("navPrice"),
                        "market_price": info.get("regularMarketPrice"),
                        "source": "yahoo",
                    }
                )
            except Exception as e:
                logger.warning("Failed to fetch info for %s: %s", etf, e)
                results.append(
                    {
                        "timestamp": datetime.now(UTC),
                        "etf": etf,
                        "underlying": ETF_UNDERLYING.get(etf, "unknown"),
                        "shares_outstanding": None,
                        "total_assets": None,
                        "nav_price": None,
                        "market_price": None,
                        "source": "yahoo",
                    }
                )

        df = pd.DataFrame(results)
        logger.info("Fetched shares data for %d ETFs", len(df))
        return df

    async def collect_historical_prices(
        self,
        etfs: list[str] | None = None,
        period: str = "30d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch historical ETF prices.

        Uses batch yf.download() for efficiency.

        Args:
            etfs: List of ETF tickers. Defaults to all ETFs.
            period: Time period if start_date not provided.
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with historical price data.

        Raises:
            CollectorFetchError: If data fetch fails.
        """
        if etfs is None:
            etfs = list(ETF_TICKERS.values())
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_prices_sync, etfs, period, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("ETF prices fetch failed: %s", e)
            raise CollectorFetchError(f"ETF prices fetch failed: {e}") from e

    def _fetch_prices_sync(
        self,
        etfs: list[str],
        period: str,
        start_date: datetime | None,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Synchronous fetch for historical prices.

        Args:
            etfs: List of ETF tickers.
            period: Time period if start_date not provided.
            start_date: Start date (optional).
            end_date: End date.

        Returns:
            DataFrame with historical prices.
        """
        logger.info("Fetching historical prices for ETFs: %s", etfs)

        try:
            # Calculate dates
            if start_date is None:
                delta = PERIOD_MAP.get(period, timedelta(days=30))
                calc_start = end_date - delta
            else:
                calc_start = start_date

            # Batch download
            df = yf.download(
                etfs,
                start=calc_start.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )

            if df is None or df.empty:
                logger.warning("No ETF price data returned for: %s", etfs)
                return pd.DataFrame(
                    columns=[
                        "timestamp",
                        "etf",
                        "underlying",
                        "source",
                        "close",
                        "volume",
                    ]
                )

            # Handle single vs multiple ETFs
            if len(etfs) == 1:
                # Single ETF: columns are just price types
                close_df = df[["Close"]].copy()
                close_df.columns = pd.Index(etfs)
                volume_df = df[["Volume"]].copy()
                volume_df.columns = pd.Index(etfs)
            else:
                # Multiple ETFs: MultiIndex columns
                if isinstance(df.columns, pd.MultiIndex):
                    close_df = df["Close"].copy()
                    volume_df = df["Volume"].copy()
                else:
                    close_df = df[[c for c in df.columns if "Close" in str(c)]].copy()
                    volume_df = df[[c for c in df.columns if "Volume" in str(c)]].copy()

            # Reset index
            close_df = close_df.reset_index()
            volume_df = volume_df.reset_index()

            # Find date column
            date_col = "Date" if "Date" in close_df.columns else close_df.columns[0]

            # Melt close prices
            value_cols = [c for c in close_df.columns if c != date_col]
            close_long = close_df.melt(
                id_vars=[date_col],
                value_vars=value_cols,
                var_name="etf",
                value_name="close",
            )
            close_long = close_long.rename(columns={date_col: "timestamp"})

            # Melt volume
            volume_long = volume_df.melt(
                id_vars=[date_col],
                value_vars=value_cols,
                var_name="etf",
                value_name="volume",
            )
            volume_long = volume_long.rename(columns={date_col: "timestamp"})

            # Merge close and volume
            df_long = pd.merge(close_long, volume_long, on=["timestamp", "etf"])

            # Normalize
            df_long["timestamp"] = pd.to_datetime(df_long["timestamp"])
            df_long["underlying"] = df_long["etf"].map(ETF_UNDERLYING)
            df_long["source"] = "yahoo"

            # Forward fill for gaps
            df_long = df_long.sort_values(["etf", "timestamp"])
            df_long["close"] = df_long.groupby("etf")["close"].ffill()
            df_long["volume"] = df_long.groupby("etf")["volume"].ffill()

            # Clean and sort
            df_long = (
                df_long.dropna(subset=["close"])
                .sort_values(["etf", "timestamp"])
                .reset_index(drop=True)
            )

            logger.info("Fetched %d ETF price data points", len(df_long))

            return df_long[
                ["timestamp", "etf", "underlying", "source", "close", "volume"]
            ]

        except Exception as e:
            logger.error("yfinance ETF fetch error: %s", e)
            raise

    async def collect_precious_metal_etfs(
        self,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect GLD and SLV data.

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with GLD and SLV data.
        """
        etfs = [ETF_TICKERS["gld"], ETF_TICKERS["slv"]]
        return await self.collect_historical_prices(etfs=etfs, period=period)

    async def collect_all(
        self,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect all ETF historical prices.

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with all ETF price data.
        """
        return await self.collect_historical_prices(period=period)

    async def get_gld_holdings(self) -> dict[str, Any] | None:
        """Get current GLD shares outstanding and NAV.

        Returns:
            Dict with GLD holdings info, or None if unavailable.
        """
        try:
            df = await self.collect_current_shares(etfs=["GLD"])
            if df.empty:
                return None
            row = df.iloc[0]
            return {
                "etf": row["etf"],
                "shares_outstanding": row["shares_outstanding"],
                "total_assets": row["total_assets"],
                "nav_price": row["nav_price"],
                "market_price": row["market_price"],
            }
        except Exception as e:
            logger.warning("Failed to get GLD holdings: %s", e)
            return None

    @staticmethod
    def estimate_daily_flows(shares_df: pd.DataFrame) -> pd.DataFrame:
        """Estimate daily flows from shares outstanding changes.

        Note: This requires historical shares data which yfinance doesn't
        provide directly. For now, this method expects a DataFrame with
        multiple timestamps (e.g., from stored historical snapshots).

        For v1: Returns current snapshot unchanged.
        For v2: Would compare against stored historical data in QuestDB.

        Args:
            shares_df: DataFrame with timestamps and shares_outstanding.

        Returns:
            DataFrame with flow estimates (or unchanged if single timestamp).
        """
        if len(shares_df) <= 1:
            logger.info("Single timestamp - flow estimation requires historical data")
            return shares_df

        # Sort by timestamp
        df = shares_df.sort_values(["etf", "timestamp"]).copy()

        # Calculate change in shares outstanding
        df["shares_change"] = df.groupby("etf")["shares_outstanding"].diff()

        return df


# Register collector with the registry
registry.register("etf_flows", ETFFlowCollector)
