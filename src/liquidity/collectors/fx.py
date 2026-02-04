"""FX collector for DXY and major currency pairs.

Fetches FX data from Yahoo Finance via yfinance:
- DXY: US Dollar Index (ICE)
- Major pairs: EUR/USD, USD/JPY, GBP/USD, etc.

FX data shows the *effect* of liquidity flows. DXY strength/weakness
signals risk sentiment. Individual pairs enable granular carry trade analysis.

DXY fallback via FRED (DTWEXBGS - Broad Dollar Index) when Yahoo unavailable.
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

# Yahoo Finance FX ticker mapping
# Keys are internal names, values are Yahoo Finance tickers
FX_SYMBOLS: dict[str, str] = {
    "dxy": "DX-Y.NYB",  # ICE US Dollar Index
    "eurusd": "EURUSD=X",  # EUR/USD
    "usdjpy": "USDJPY=X",  # USD/JPY
    "gbpusd": "GBPUSD=X",  # GBP/USD
    "usdchf": "USDCHF=X",  # USD/CHF
    "usdcad": "USDCAD=X",  # USD/CAD
    "usdcny": "USDCNY=X",  # USD/CNY
    "audusd": "AUDUSD=X",  # AUD/USD
}

# FRED fallback series for DXY
FRED_DXY_SERIES = "DTWEXBGS"  # Nominal Broad USD Index (different calc but correlated)

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


class FXCollector(BaseCollector[pd.DataFrame]):
    """FX data collector using yfinance.

    Fetches FX data showing liquidity flow effects:
    - DXY strength/weakness signals risk sentiment
    - Individual pairs for carry trade analysis

    Example:
        collector = FXCollector()

        # Get DXY only
        df = await collector.collect_dxy()

        # Get major pairs
        df = await collector.collect_pairs()

        # Get all FX data
        df = await collector.collect_all()
    """

    FX_SYMBOLS = FX_SYMBOLS

    def __init__(
        self,
        name: str = "fx",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize FX collector.

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
        """Collect FX data from Yahoo Finance.

        Args:
            symbols: List of Yahoo Finance tickers (e.g., ["DX-Y.NYB", "EURUSD=X"]).
                Defaults to all FX symbols.
            period: Time period if start_date not provided. Valid: 1d, 5d, 30d, 90d, 1y, 2y, 5y.
            start_date: Start date for data fetch. If provided, period is ignored.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if symbols is None:
            symbols = list(FX_SYMBOLS.values())
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_sync, symbols, period, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("FX fetch failed: %s", e)
            raise CollectorFetchError(f"FX data fetch failed: {e}") from e

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
        logger.info("Fetching FX data for symbols: %s", symbols)

        try:
            # Calculate dates
            if start_date is None:
                delta = PERIOD_MAP.get(period, timedelta(days=30))
                calc_start = end_date - delta
            else:
                calc_start = start_date

            # Single download call for all symbols (avoids rate limiting)
            # yfinance returns MultiIndex columns: (price_type, ticker)
            df = yf.download(
                symbols,
                start=calc_start.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True,  # Use adjusted prices
            )

            if df is None or df.empty:
                logger.warning("No FX data returned for symbols: %s", symbols)
                return pd.DataFrame(
                    columns=["timestamp", "series_id", "source", "value", "unit"]
                )

            # Handle single vs multiple symbols (yfinance returns different formats)
            if len(symbols) == 1:
                # Single symbol: columns are just price types
                df = df[["Close"]].copy()
                df.columns = pd.Index(symbols)
            else:
                # Multiple symbols: MultiIndex columns (price_type, ticker)
                # Extract just Close prices
                if isinstance(df.columns, pd.MultiIndex):
                    df = df["Close"].copy()
                else:
                    # If already flat columns after yfinance processing
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

            # Assign units based on series type
            def get_unit(series_id: str) -> str:
                if series_id == "DX-Y.NYB" or series_id == FRED_DXY_SERIES:
                    return "index"
                return "rate"

            df_long["unit"] = df_long["series_id"].apply(get_unit)

            # Handle DXY weekend gaps (DXY doesn't trade Sunday, FX pairs do)
            # Apply ffill for DXY only
            dxy_mask = df_long["series_id"] == "DX-Y.NYB"
            if dxy_mask.any():
                dxy_data = df_long[dxy_mask].copy()
                # Sort by timestamp and forward-fill NaN values
                dxy_data = dxy_data.sort_values("timestamp")
                dxy_data["value"] = dxy_data["value"].ffill()
                df_long.loc[dxy_mask, "value"] = dxy_data["value"].values

            # Clean and sort
            df_long = (
                df_long.dropna(subset=["value"])
                .sort_values(["series_id", "timestamp"])
                .reset_index(drop=True)
            )

            logger.info("Fetched %d FX data points", len(df_long))

            return df_long[["timestamp", "series_id", "source", "value", "unit"]]

        except Exception as e:
            logger.error("yfinance FX fetch error: %s", e)
            raise

    async def collect_dxy(
        self,
        period: str = "30d",
        use_fred_fallback: bool = True,
    ) -> pd.DataFrame:
        """Collect DXY (US Dollar Index) data.

        Args:
            period: Time period for data fetch.
            use_fred_fallback: Whether to fallback to FRED if Yahoo fails.

        Returns:
            DataFrame with DXY data.
        """
        try:
            return await self.collect(symbols=["DX-Y.NYB"], period=period)
        except CollectorFetchError as e:
            if not use_fred_fallback:
                raise

            logger.warning("DXY Yahoo fetch failed, trying FRED fallback: %s", e)
            return await self._collect_dxy_fred(period)

    async def _collect_dxy_fred(self, period: str = "30d") -> pd.DataFrame:
        """Fallback: Collect DXY proxy from FRED (Broad Dollar Index).

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with FRED DXY proxy data.
        """
        # Import here to avoid circular dependency
        from openbb import obb

        delta = PERIOD_MAP.get(period, timedelta(days=30))
        end_date = datetime.now(UTC)
        start_date = end_date - delta

        def _fetch_fred() -> pd.DataFrame:
            result = obb.economy.fred_series(  # type: ignore[attr-defined]
                symbol=FRED_DXY_SERIES,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                provider="fred",
            )
            df = result.to_df().reset_index()

            if df.empty:
                return pd.DataFrame(
                    columns=["timestamp", "series_id", "source", "value", "unit"]
                )

            # Find date column
            date_col = "date" if "date" in df.columns else df.columns[0]

            # Normalize
            normalized = pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(df[date_col]),
                    "series_id": "DXY",  # Normalize to DXY name
                    "source": "fred",
                    "value": df[FRED_DXY_SERIES],
                    "unit": "index",
                }
            )

            return normalized.dropna(subset=["value"]).sort_values("timestamp")

        logger.info("Fetching DXY from FRED fallback (DTWEXBGS)")
        return await asyncio.to_thread(_fetch_fred)

    async def collect_pairs(
        self,
        pairs: list[str] | None = None,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect major FX pair data.

        Args:
            pairs: List of pair tickers. Defaults to all major pairs (excluding DXY).
            period: Time period for data fetch.

        Returns:
            DataFrame with FX pair data.
        """
        if pairs is None:
            # All pairs except DXY
            pairs = [v for k, v in FX_SYMBOLS.items() if k != "dxy"]

        return await self.collect(symbols=pairs, period=period)

    async def collect_all(
        self,
        period: str = "30d",
    ) -> pd.DataFrame:
        """Collect all FX data (DXY + major pairs).

        Args:
            period: Time period for data fetch.

        Returns:
            DataFrame with all FX data.
        """
        return await self.collect(period=period)

    async def get_current_dxy(self) -> float | None:
        """Get the most recent DXY value.

        Returns:
            Most recent DXY value, or None if unavailable.
        """
        try:
            df = await self.collect_dxy(period="5d")
            if df.empty:
                return None
            return float(df.iloc[-1]["value"])
        except Exception as e:
            logger.warning("Failed to get current DXY: %s", e)
            return None


# Register collector with the registry
registry.register("fx", FXCollector)
