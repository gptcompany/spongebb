"""Commodity collector for precious metals and energy prices.

Fetches commodity spot prices from Yahoo Finance via yfinance:
- Gold (GC=F): $/oz
- Silver (SI=F): $/oz
- Copper (HG=F): $/lb
- WTI Crude (CL=F): $/barrel
- Brent Crude (BZ=F): $/barrel

These are "real economy" indicators that complement liquidity data.
Gold/Silver are safe haven assets, Copper indicates economic health,
Oil signals energy/inflation pressures.

FRED fallback available for gold, WTI, and Brent.
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

# Yahoo Finance commodity ticker mapping
COMMODITY_SYMBOLS: dict[str, str] = {
    "gold": "GC=F",  # Gold futures ($/oz)
    "silver": "SI=F",  # Silver futures ($/oz)
    "copper": "HG=F",  # Copper futures ($/lb)
    "wti": "CL=F",  # WTI Crude ($/barrel)
    "brent": "BZ=F",  # Brent Crude ($/barrel)
}

# Unit mapping for each symbol
UNIT_MAP: dict[str, str] = {
    "GC=F": "usd_per_oz",
    "SI=F": "usd_per_oz",
    "HG=F": "usd_per_lb",
    "CL=F": "usd_per_barrel",
    "BZ=F": "usd_per_barrel",
}

# FRED fallback series (for validation or when Yahoo fails)
FRED_FALLBACK: dict[str, str] = {
    "gold": "GOLDPMGBD228NLBM",  # LBMA PM fix
    "wti": "DCOILWTICO",  # EIA daily WTI
    "brent": "DCOILBRENTEU",  # EIA daily Brent
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


class CommodityCollector(BaseCollector[pd.DataFrame]):
    """Commodity price collector using yfinance.

    Fetches spot prices for precious metals and energy commodities:
    - Precious metals: Gold, Silver
    - Energy: WTI Crude, Brent Crude
    - Industrial: Copper

    Includes derived metrics:
    - Brent-WTI spread ($/barrel)
    - Copper/Gold ratio (risk-on/risk-off indicator)

    Example:
        collector = CommodityCollector()

        # Get all commodities
        df = await collector.collect()

        # Get precious metals only
        df = await collector.collect_precious_metals()

        # Get energy only
        df = await collector.collect_energy()

        # Calculate derived metrics
        spread = CommodityCollector.calculate_brent_wti_spread(df)
        ratio = CommodityCollector.calculate_copper_gold_ratio(df)
    """

    COMMODITY_SYMBOLS = COMMODITY_SYMBOLS
    UNIT_MAP = UNIT_MAP

    def __init__(
        self,
        name: str = "commodities",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize commodity collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()

    async def collect(
        self,
        symbols: list[str] | None = None,
        period: str = "30d",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect commodity data from Yahoo Finance.

        Args:
            symbols: List of Yahoo Finance tickers (e.g., ["GC=F", "SI=F"]).
                Defaults to all commodity symbols.
            period: Time period if start_date not provided. Valid: 1d, 5d, 30d, 90d, 1y, 2y, 5y.
            start_date: Start date for data fetch. If provided, period is ignored.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if symbols is None:
            symbols = list(COMMODITY_SYMBOLS.values())
        if end_date is None:
            end_date = datetime.now(timezone.utc)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_sync, symbols, period, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("Commodity fetch failed: %s", e)
            raise CollectorFetchError(f"Commodity data fetch failed: {e}") from e

    def _fetch_sync(
        self,
        symbols: list[str],
        period: str,
        start_date: datetime | None,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Synchronous fetch implementation using yfinance.

        Uses single yf.download() call for all symbols to avoid rate limiting.

        Args:
            symbols: Yahoo Finance tickers.
            period: Time period if start_date not provided.
            start_date: Start date (optional).
            end_date: End date.

        Returns:
            Normalized DataFrame with timestamp, series_id, source, value, unit columns.
        """
        logger.info("Fetching commodity data for symbols: %s", symbols)

        try:
            # Calculate dates
            if start_date is None:
                delta = PERIOD_MAP.get(period, timedelta(days=30))
                calc_start = end_date - delta
            else:
                calc_start = start_date

            # Single download call for all symbols (avoids rate limiting)
            df = yf.download(
                symbols,
                start=calc_start.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,
            )

            if df.empty:
                logger.warning("No commodity data returned for symbols: %s", symbols)
                return pd.DataFrame(
                    columns=["timestamp", "series_id", "source", "value", "unit"]
                )

            # Handle single vs multiple symbols (yfinance returns different formats)
            if len(symbols) == 1:
                # Single symbol: columns are just price types
                df = df[["Close"]].copy()
                df.columns = symbols
            else:
                # Multiple symbols: MultiIndex columns (price_type, ticker)
                if isinstance(df.columns, pd.MultiIndex):
                    df = df["Close"].copy()
                else:
                    df = df[[c for c in df.columns if "Close" in str(c)]].copy()

            # Reset index to get date as column
            df = df.reset_index()

            # Find date column
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
            df_long["source"] = "yahoo"

            # Assign units based on symbol
            df_long["unit"] = df_long["series_id"].map(UNIT_MAP)

            # Forward fill for weekend/holiday gaps
            df_long = df_long.sort_values(["series_id", "timestamp"])
            df_long["value"] = df_long.groupby("series_id")["value"].ffill()

            # Clean and sort
            df_long = (
                df_long.dropna(subset=["value"])
                .sort_values(["series_id", "timestamp"])
                .reset_index(drop=True)
            )

            logger.info("Fetched %d commodity data points", len(df_long))

            return df_long[["timestamp", "series_id", "source", "value", "unit"]]

        except Exception as e:
            logger.error("yfinance commodity fetch error: %s", e)
            raise

    async def collect_precious_metals(
        self,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect gold and silver data.

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with gold and silver data.
        """
        symbols = [COMMODITY_SYMBOLS["gold"], COMMODITY_SYMBOLS["silver"]]
        return await self.collect(symbols=symbols, period=period)

    async def collect_energy(
        self,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect WTI and Brent crude data.

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with WTI and Brent data.
        """
        symbols = [COMMODITY_SYMBOLS["wti"], COMMODITY_SYMBOLS["brent"]]
        return await self.collect(symbols=symbols, period=period)

    async def collect_all(
        self,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect all commodity data.

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with all commodity data.
        """
        return await self.collect(period=period)

    async def get_current_gold_price(self) -> float | None:
        """Get the most recent gold price.

        Returns:
            Most recent gold price in $/oz, or None if unavailable.
        """
        try:
            df = await self.collect(symbols=[COMMODITY_SYMBOLS["gold"]], period="5d")
            if df.empty:
                return None
            return float(df.iloc[-1]["value"])
        except Exception as e:
            logger.warning("Failed to get current gold price: %s", e)
            return None

    @staticmethod
    def calculate_brent_wti_spread(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Brent-WTI spread from commodity data.

        The Brent-WTI spread indicates:
        - Positive: Brent premium (global demand > US)
        - Negative: WTI premium (US supply constraints)

        Args:
            df: DataFrame from collect() with both BZ=F and CL=F series.

        Returns:
            DataFrame with timestamp and brent_wti_spread columns.
        """
        # Pivot to get WTI and Brent side by side
        wti = df[df["series_id"] == "CL=F"][["timestamp", "value"]].copy()
        wti = wti.rename(columns={"value": "wti"})

        brent = df[df["series_id"] == "BZ=F"][["timestamp", "value"]].copy()
        brent = brent.rename(columns={"value": "brent"})

        # Merge on timestamp
        merged = pd.merge(wti, brent, on="timestamp", how="inner")

        # Calculate spread
        merged["brent_wti_spread"] = merged["brent"] - merged["wti"]

        return merged[["timestamp", "brent_wti_spread"]]

    @staticmethod
    def calculate_copper_gold_ratio(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Copper/Gold ratio from commodity data.

        The Cu/Au ratio is a risk-on/risk-off indicator:
        - Rising: Economic optimism (copper demand up)
        - Falling: Risk-off (flight to gold)

        Args:
            df: DataFrame from collect() with both HG=F and GC=F series.

        Returns:
            DataFrame with timestamp and copper_gold_ratio columns.
            Ratio is scaled x1000 for readability (copper in $/lb, gold in $/oz).
        """
        # Pivot to get copper and gold side by side
        copper = df[df["series_id"] == "HG=F"][["timestamp", "value"]].copy()
        copper = copper.rename(columns={"value": "copper"})

        gold = df[df["series_id"] == "GC=F"][["timestamp", "value"]].copy()
        gold = gold.rename(columns={"value": "gold"})

        # Merge on timestamp
        merged = pd.merge(copper, gold, on="timestamp", how="inner")

        # Calculate ratio (scaled x1000)
        merged["copper_gold_ratio"] = (merged["copper"] / merged["gold"]) * 1000

        return merged[["timestamp", "copper_gold_ratio"]]


# Register collector with the registry
registry.register("commodities", CommodityCollector)
