"""Oil term structure collector for contango/backwardation analysis.

Fetches WTI and Brent futures front month prices from Yahoo Finance
and calculates momentum metrics as proxies for term structure shape.

Since yfinance only provides front month continuous contracts (CL=F, BZ=F),
we use price momentum as a proxy for term structure:
- Rising prices with high momentum → backwardation (supply tight)
- Falling prices with negative momentum → contango (supply abundant)

Full term structure (6+ contracts) would require CME API access.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Yahoo Finance futures tickers
SERIES_MAP: dict[str, str] = {
    "wti_front": "CL=F",  # WTI Crude front month
    "brent_front": "BZ=F",  # Brent Crude front month
}

# Unit mapping
UNIT_MAP: dict[str, str] = {
    "wti_front": "usd_per_barrel",
    "brent_front": "usd_per_barrel",
    "wti_front_momentum_5d": "percent",
    "wti_front_momentum_20d": "percent",
    "brent_front_momentum_5d": "percent",
    "brent_front_momentum_20d": "percent",
}

# Default momentum windows
DEFAULT_MOMENTUM_WINDOWS = [5, 20]

# Period to timedelta mapping
PERIOD_MAP: dict[str, timedelta] = {
    "30d": timedelta(days=30),
    "60d": timedelta(days=60),
    "90d": timedelta(days=90),
    "1y": timedelta(days=365),
    "2y": timedelta(days=730),
}


class OilTermStructureCollector(BaseCollector[pd.DataFrame]):
    """Collect WTI/Brent futures prices for term structure analysis.

    This collector fetches front month continuous contract prices and
    calculates momentum metrics as proxies for term structure shape.

    Since yfinance only provides front month data, we cannot calculate
    true calendar spreads or roll yields. Instead, we use:
    - 5-day momentum: Short-term price direction
    - 20-day momentum: Medium-term trend

    These can be correlated with EIA inventory and CFTC positioning
    data to infer term structure direction.

    Example:
        collector = OilTermStructureCollector()

        # Get WTI prices only
        df = await collector.collect_wti()

        # Get prices with momentum calculations
        df = await collector.collect_with_momentum()

        # Get all oil data
        df = await collector.collect()
    """

    SERIES_MAP = SERIES_MAP
    UNIT_MAP = UNIT_MAP

    def __init__(
        self,
        name: str = "oil_term_structure",
        settings: Settings | None = None,
        momentum_windows: list[int] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize oil term structure collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            momentum_windows: Windows for momentum calculation (default: [5, 20]).
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()
        self.momentum_windows = momentum_windows or DEFAULT_MOMENTUM_WINDOWS

    async def collect(
        self,
        symbols: list[str] | None = None,
        period: str = "90d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect futures price data.

        Args:
            symbols: List of series IDs (e.g., ["wti_front", "brent_front"]).
                Defaults to all available series.
            period: Time period if start_date not provided. Valid: 30d, 60d, 90d, 1y, 2y.
            start_date: Start date for data fetch. If provided, period is ignored.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if symbols is None:
            symbols = list(SERIES_MAP.keys())

        # Validate symbols
        valid_symbols = [s for s in symbols if s in SERIES_MAP]
        if not valid_symbols:
            logger.warning("No valid symbols provided: %s", symbols)
            return self._empty_dataframe()

        if end_date is None:
            end_date = datetime.now(UTC)

        # Calculate start date from period if not provided
        if start_date is None:
            delta = PERIOD_MAP.get(period, timedelta(days=90))
            start_date = end_date - delta

        # Validate date range
        if start_date >= end_date:
            logger.warning("start_date >= end_date, returning empty DataFrame")
            return self._empty_dataframe()

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_sync, valid_symbols, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("Oil term structure fetch failed: %s", e)
            raise CollectorFetchError(f"Oil term structure data fetch failed: {e}") from e

    def _fetch_sync(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Synchronous fetch implementation using yfinance.

        Args:
            symbols: Series IDs to fetch.
            start_date: Start date.
            end_date: End date.

        Returns:
            Normalized DataFrame with timestamp, series_id, source, value, unit columns.
        """
        # Map series IDs to Yahoo tickers
        tickers = [SERIES_MAP[s] for s in symbols]

        logger.info("Fetching oil term structure data for: %s", tickers)

        try:
            # Single download call for all symbols
            df = yf.download(
                tickers,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )

            if df is None or df.empty:
                logger.warning("No oil data returned for tickers: %s", tickers)
                return self._empty_dataframe()

            # Handle single vs multiple symbols
            if len(tickers) == 1:
                df = df[["Close"]].copy()
                df.columns = pd.Index(symbols)
            else:
                if isinstance(df.columns, pd.MultiIndex):
                    df = df["Close"].copy()
                    # Rename columns from tickers to series IDs
                    ticker_to_series = {v: k for k, v in SERIES_MAP.items() if k in symbols}
                    df.columns = [ticker_to_series.get(c, c) for c in df.columns]
                else:
                    df = df[[c for c in df.columns if "Close" in str(c)]].copy()

            # Reset index
            df = df.reset_index()
            date_col = "Date" if "Date" in df.columns else df.columns[0]

            # Melt to long format
            value_cols = [c for c in df.columns if c != date_col]
            df_long = df.melt(
                id_vars=[date_col],
                value_vars=value_cols,
                var_name="series_id",
                value_name="value",
            )

            # Normalize
            df_long = df_long.rename(columns={date_col: "timestamp"})
            df_long["timestamp"] = pd.to_datetime(df_long["timestamp"])
            df_long["source"] = "yfinance"

            # Assign units
            df_long["unit"] = df_long["series_id"].map(
                lambda x: UNIT_MAP.get(x, "usd_per_barrel")
            )

            # Forward fill weekend/holiday gaps
            df_long = df_long.sort_values(["series_id", "timestamp"])
            df_long["value"] = df_long.groupby("series_id")["value"].ffill()

            # Clean and sort
            df_long = (
                df_long.dropna(subset=["value"])
                .sort_values(["series_id", "timestamp"])
                .reset_index(drop=True)
            )

            logger.info("Fetched %d oil term structure data points", len(df_long))

            return df_long[["timestamp", "series_id", "source", "value", "unit"]]

        except Exception as e:
            logger.error("yfinance oil term structure fetch error: %s", e)
            raise

    async def collect_wti(
        self,
        period: str = "90d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method for WTI only.

        Args:
            period: Time period if start_date not provided.
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with WTI front month data.
        """
        return await self.collect(
            ["wti_front"],
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

    async def collect_with_momentum(
        self,
        symbols: list[str] | None = None,
        period: str = "90d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect prices with momentum calculations.

        Adds momentum series for each price series:
        - {series_id}_momentum_5d: 5-day percentage change
        - {series_id}_momentum_20d: 20-day percentage change

        Args:
            symbols: Series IDs to fetch (default: wti_front only).
            period: Time period if start_date not provided.
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with price and momentum series.
        """
        if symbols is None:
            symbols = ["wti_front"]

        df = await self.collect(
            symbols,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            return df

        # Calculate momentum for each series
        momentum_dfs = []
        for series_id in df["series_id"].unique():
            series_data = df[df["series_id"] == series_id].sort_values("timestamp")

            if len(series_data) < max(self.momentum_windows):
                # Not enough data for momentum calculation
                continue

            for window in self.momentum_windows:
                momentum = series_data["value"].pct_change(window) * 100
                momentum_series_id = f"{series_id}_momentum_{window}d"

                momentum_df = pd.DataFrame({
                    "timestamp": series_data["timestamp"],
                    "series_id": momentum_series_id,
                    "source": "calculated",
                    "value": momentum.values,
                    "unit": "percent",
                })

                # Drop NaN values from beginning
                momentum_df = momentum_df.dropna(subset=["value"])
                momentum_dfs.append(momentum_df)

        # Combine price and momentum data
        if momentum_dfs:
            df = pd.concat([df] + momentum_dfs, ignore_index=True)

        return df.sort_values(["timestamp", "series_id"]).reset_index(drop=True)

    async def get_current_wti_price(self) -> float | None:
        """Get the most recent WTI price.

        Returns:
            Most recent WTI price in $/barrel, or None if unavailable.
        """
        try:
            df = await self.collect(symbols=["wti_front"], period="30d")
            if df.empty:
                return None
            latest = df[df["series_id"] == "wti_front"].iloc[-1]
            return float(latest["value"])
        except Exception as e:
            logger.warning("Failed to get current WTI price: %s", e)
            return None

    def _empty_dataframe(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

    @staticmethod
    def calculate_brent_wti_spread(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Brent-WTI spread from price data.

        The Brent-WTI spread indicates:
        - Positive: Brent premium (global demand > US supply)
        - Negative: WTI premium (US export constraints)

        Args:
            df: DataFrame from collect() with both wti_front and brent_front series.

        Returns:
            DataFrame with timestamp and brent_wti_spread columns.
        """
        wti = df[df["series_id"] == "wti_front"][["timestamp", "value"]].copy()
        wti = wti.rename(columns={"value": "wti"})

        brent = df[df["series_id"] == "brent_front"][["timestamp", "value"]].copy()
        brent = brent.rename(columns={"value": "brent"})

        merged = pd.merge(wti, brent, on="timestamp", how="inner")
        merged["brent_wti_spread"] = merged["brent"] - merged["wti"]

        return merged[["timestamp", "brent_wti_spread"]]


# Register collector with the registry
registry.register("oil_term_structure", OilTermStructureCollector)
