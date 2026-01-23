"""Risk ETF collector for sentiment tracking.

Tracks shares outstanding and prices for risk sentiment ETFs:
- SPY: SPDR S&P 500 ETF Trust (equity risk appetite)
- TLT: iShares 20+ Year Treasury Bond ETF (flight to safety)
- HYG: iShares iBoxx High Yield Corporate Bond ETF (credit risk appetite)
- IEF: iShares 7-10 Year Treasury Bond ETF (duration positioning)
- LQD: iShares iBoxx Investment Grade Corporate Bond ETF (credit quality)

Risk ETFs provide insight into market sentiment:
- High SPY flows + low TLT flows = Risk-on sentiment
- Low SPY flows + high TLT flows = Risk-off / flight to safety
- High HYG flows = Credit risk appetite
- High LQD flows = Flight to quality within credit

The SPY/TLT flow ratio is a key risk appetite indicator.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Risk ETF ticker mapping
RISK_ETF_TICKERS: dict[str, str] = {
    "SPY": "SPY",  # S&P 500 (equity risk)
    "TLT": "TLT",  # 20+ Year Treasury (flight to safety)
    "HYG": "HYG",  # High Yield Corporate (credit risk appetite)
    "IEF": "IEF",  # 7-10 Year Treasury (duration positioning)
    "LQD": "LQD",  # Investment Grade Corporate (credit quality)
}

# Risk ETF type mapping
RISK_ETF_TYPE: dict[str, str] = {
    "SPY": "equity",
    "TLT": "treasury_long",
    "HYG": "high_yield",
    "IEF": "treasury_mid",
    "LQD": "investment_grade",
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


class RiskETFCollector(BaseCollector[pd.DataFrame]):
    """Risk ETF collector using yfinance.

    Tracks risk sentiment ETFs for flow analysis:
    - Current shares outstanding (from .info)
    - Historical prices (from batch download)
    - Risk appetite ratio (SPY vs TLT flows)

    Note: yfinance doesn't provide historical shares outstanding data.
    Full flow tracking requires storing snapshots over time in QuestDB.

    Example:
        collector = RiskETFCollector()

        # Get current shares outstanding
        df = await collector.collect_current_shares()

        # Get historical prices
        df = await collector.collect_historical_prices()

        # Get equity ETFs only (SPY)
        df = await collector.collect_equity_etfs()

        # Get bond ETFs only (TLT, IEF, HYG, LQD)
        df = await collector.collect_bond_etfs()

        # Calculate risk appetite ratio
        ratio = await collector.calculate_risk_appetite(shares_df)
    """

    RISK_ETF_TICKERS = RISK_ETF_TICKERS
    RISK_ETF_TYPE = RISK_ETF_TYPE

    def __init__(
        self,
        name: str = "risk_etfs",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Risk ETF collector.

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
        """Fetch current shares outstanding for risk ETFs.

        Uses yf.Ticker().info to get current snapshot of:
        - Shares outstanding
        - Total assets
        - NAV price

        Args:
            etfs: List of ETF tickers. Defaults to all risk ETFs.

        Returns:
            DataFrame with current ETF data.

        Raises:
            CollectorFetchError: If data fetch fails.
        """
        if etfs is None:
            etfs = list(RISK_ETF_TICKERS.values())

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(self._fetch_shares_sync, etfs)

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("Risk ETF shares fetch failed: %s", e)
            raise CollectorFetchError(f"Risk ETF shares fetch failed: {e}") from e

    def _fetch_shares_sync(self, etfs: list[str]) -> pd.DataFrame:
        """Synchronous fetch for shares outstanding.

        Args:
            etfs: List of ETF tickers.

        Returns:
            DataFrame with shares outstanding data.
        """
        logger.info("Fetching shares outstanding for risk ETFs: %s", etfs)

        results = []
        for etf in etfs:
            try:
                ticker = yf.Ticker(etf)
                info = ticker.info

                results.append(
                    {
                        "timestamp": datetime.now(timezone.utc),
                        "etf": etf,
                        "risk_type": RISK_ETF_TYPE.get(etf, "unknown"),
                        "source": "yfinance",
                        "shares_outstanding": info.get("sharesOutstanding"),
                        "total_assets": info.get("totalAssets"),
                        "nav_price": info.get("navPrice"),
                    }
                )
            except Exception as e:
                logger.warning("Failed to fetch info for %s: %s", etf, e)
                results.append(
                    {
                        "timestamp": datetime.now(timezone.utc),
                        "etf": etf,
                        "risk_type": RISK_ETF_TYPE.get(etf, "unknown"),
                        "source": "yfinance",
                        "shares_outstanding": None,
                        "total_assets": None,
                        "nav_price": None,
                    }
                )

        df = pd.DataFrame(results)
        logger.info("Fetched shares data for %d risk ETFs", len(df))
        return df

    async def collect_historical_prices(
        self,
        etfs: list[str] | None = None,
        period: str = "30d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch historical risk ETF prices.

        Uses batch yf.download() for efficiency.

        Args:
            etfs: List of ETF tickers. Defaults to all risk ETFs.
            period: Time period if start_date not provided.
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with historical price data.

        Raises:
            CollectorFetchError: If data fetch fails.
        """
        if etfs is None:
            etfs = list(RISK_ETF_TICKERS.values())
        if end_date is None:
            end_date = datetime.now(timezone.utc)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_prices_sync, etfs, period, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("Risk ETF prices fetch failed: %s", e)
            raise CollectorFetchError(f"Risk ETF prices fetch failed: {e}") from e

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
        logger.info("Fetching historical prices for risk ETFs: %s", etfs)

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

            if df.empty:
                logger.warning("No risk ETF price data returned for: %s", etfs)
                return pd.DataFrame(
                    columns=[
                        "timestamp",
                        "etf",
                        "risk_type",
                        "source",
                        "close",
                        "volume",
                    ]
                )

            # Handle single vs multiple ETFs
            if len(etfs) == 1:
                # Single ETF: columns are just price types
                close_df = df[["Close"]].copy()
                close_df.columns = etfs
                volume_df = df[["Volume"]].copy()
                volume_df.columns = etfs
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
            df_long["risk_type"] = df_long["etf"].map(RISK_ETF_TYPE)
            df_long["source"] = "yfinance"

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

            logger.info("Fetched %d risk ETF price data points", len(df_long))

            return df_long[
                ["timestamp", "etf", "risk_type", "source", "close", "volume"]
            ]

        except Exception as e:
            logger.error("yfinance risk ETF fetch error: %s", e)
            raise

    async def collect_equity_etfs(
        self,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect SPY data (equity risk ETF).

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with SPY data.
        """
        etfs = [RISK_ETF_TICKERS["SPY"]]
        return await self.collect_historical_prices(etfs=etfs, period=period)

    async def collect_bond_etfs(
        self,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect bond ETFs (TLT, IEF, HYG, LQD).

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with bond ETF data.
        """
        etfs = [
            RISK_ETF_TICKERS["TLT"],
            RISK_ETF_TICKERS["IEF"],
            RISK_ETF_TICKERS["HYG"],
            RISK_ETF_TICKERS["LQD"],
        ]
        return await self.collect_historical_prices(etfs=etfs, period=period)

    async def collect_all(
        self,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect all risk ETF historical prices.

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with all risk ETF price data.
        """
        return await self.collect_historical_prices(period=period)

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

    async def calculate_risk_appetite(
        self, shares_df: pd.DataFrame | None = None
    ) -> dict[str, Any]:
        """Calculate risk appetite ratio from SPY and TLT flows.

        Risk appetite is measured by comparing equity flows (SPY) vs
        treasury flows (TLT). Higher ratio = more risk-on sentiment.

        Args:
            shares_df: Optional DataFrame with shares_outstanding for SPY and TLT.
                       If not provided, fetches current shares automatically.

        Returns:
            Dict with risk appetite metrics:
            - spy_shares: SPY shares outstanding
            - tlt_shares: TLT shares outstanding
            - spy_tlt_ratio: SPY shares / TLT shares
            - sentiment: "risk_on", "risk_off", or "neutral"
        """
        # Fetch shares data if not provided
        if shares_df is None:
            shares_df = await self.collect_current_shares(etfs=["SPY", "TLT"])

        return self._calculate_risk_appetite_from_df(shares_df)

    @staticmethod
    def _calculate_risk_appetite_from_df(shares_df: pd.DataFrame) -> dict[str, Any]:
        """Calculate risk appetite from a DataFrame (static helper).

        Args:
            shares_df: DataFrame with shares_outstanding for SPY and TLT.

        Returns:
            Dict with risk appetite metrics.
        """
        result: dict[str, Any] = {
            "spy_shares": None,
            "tlt_shares": None,
            "spy_tlt_ratio": None,
            "sentiment": "unknown",
        }

        if shares_df.empty:
            return result

        # Get latest shares for SPY and TLT
        spy_data = shares_df[shares_df["etf"] == "SPY"]
        tlt_data = shares_df[shares_df["etf"] == "TLT"]

        if spy_data.empty or tlt_data.empty:
            logger.warning("Missing SPY or TLT data for risk appetite calculation")
            return result

        spy_shares = spy_data["shares_outstanding"].iloc[-1]
        tlt_shares = tlt_data["shares_outstanding"].iloc[-1]

        if spy_shares is None or tlt_shares is None:
            return result

        if tlt_shares == 0:
            logger.warning("TLT shares is zero, cannot calculate ratio")
            return result

        ratio = spy_shares / tlt_shares

        # Determine sentiment based on ratio
        # SPY typically has 900M+ shares, TLT has 100-150M shares
        # Neutral ratio is around 6-10
        if ratio > 10.0:
            sentiment = "risk_on"
        elif ratio < 6.0:
            sentiment = "risk_off"
        else:
            sentiment = "neutral"

        result["spy_shares"] = spy_shares
        result["tlt_shares"] = tlt_shares
        result["spy_tlt_ratio"] = ratio
        result["sentiment"] = sentiment

        logger.info(
            "Risk appetite: SPY/TLT ratio=%.2f, sentiment=%s",
            ratio,
            sentiment,
        )

        return result


# Register collector with the registry
registry.register("risk_etfs", RiskETFCollector)
