"""Yahoo Finance collector for market indicators.

Fetches market data from Yahoo Finance via OpenBB SDK:
- MOVE: Bond Market Volatility Index (^MOVE)

The MOVE index is a key indicator of bond market stress and is used
in correlation analysis with liquidity conditions.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from openbb import obb

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Yahoo Finance symbol mapping
# Keys are internal names, values are Yahoo Finance symbols
SYMBOLS: dict[str, str] = {
    "move": "^MOVE",  # MOVE Bond Volatility Index
}

# Period to timedelta mapping
PERIOD_MAP: dict[str, timedelta] = {
    "1d": timedelta(days=1),
    "5d": timedelta(days=5),
    "1mo": timedelta(days=30),
    "3mo": timedelta(days=90),
    "6mo": timedelta(days=180),
    "1y": timedelta(days=365),
    "2y": timedelta(days=730),
    "5y": timedelta(days=1825),
    "10y": timedelta(days=3650),
}


class YahooCollector(BaseCollector[pd.DataFrame]):
    """Yahoo Finance data collector using OpenBB SDK.

    Fetches market indicators that are not available from FRED,
    particularly the MOVE index for bond market volatility.

    Example:
        collector = YahooCollector()
        df = await collector.collect(["^MOVE"])

        # Get current price only
        price = await collector.get_current_price("^MOVE")
    """

    SYMBOLS = SYMBOLS

    def __init__(
        self,
        name: str = "yahoo",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Yahoo Finance collector.

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
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        period: str = "5y",
    ) -> pd.DataFrame:
        """Collect Yahoo Finance historical data.

        Args:
            symbols: List of Yahoo Finance symbols to fetch. Defaults to MOVE.
            start_date: Start date for data fetch. If provided, period is ignored.
            end_date: End date for data fetch. Defaults to today.
            period: Time period for data fetch if start_date not provided.
                Valid: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max.

        Returns:
            DataFrame with columns: timestamp, symbol, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if symbols is None:
            symbols = ["^MOVE"]
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_sync, symbols, start_date, end_date, period
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("Yahoo Finance fetch failed: %s", e)
            raise CollectorFetchError(f"Yahoo Finance data fetch failed: {e}") from e

    def _fetch_sync(
        self,
        symbols: list[str],
        start_date: datetime | None,
        end_date: datetime,
        period: str,
    ) -> pd.DataFrame:
        """Synchronous fetch implementation using OpenBB.

        Args:
            symbols: Yahoo Finance symbols.
            start_date: Start date (optional).
            end_date: End date.
            period: Time period if start_date not provided.

        Returns:
            Normalized DataFrame with timestamp, symbol, source, value, unit columns.
        """
        logger.info("Fetching Yahoo Finance symbols: %s", symbols)

        all_data = []

        for symbol in symbols:
            try:
                # Calculate start date from period if not provided
                if start_date is None:
                    delta = PERIOD_MAP.get(period, timedelta(days=1825))  # Default 5y
                    calc_start = end_date - delta
                else:
                    calc_start = start_date

                # Fetch data using OpenBB equity historical
                result = obb.equity.price.historical(  # type: ignore[attr-defined]
                    symbol=symbol,
                    start_date=calc_start.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d"),
                    provider="yfinance",
                )

                df = result.to_df()

                if df.empty:
                    logger.warning("No data returned for symbol: %s", symbol)
                    continue

                # Normalize to our format
                df = df.reset_index()

                # Find date column
                date_col = next(
                    (
                        col
                        for col in ["date", "index", "timestamp"]
                        if col in df.columns
                    ),
                    df.columns[0],
                )

                # Vectorized normalization instead of row iteration
                normalized = pd.DataFrame(
                    {
                        "timestamp": pd.to_datetime(df[date_col]),
                        "symbol": symbol,
                        "source": "yahoo",
                        "value": df.get("close", df.get("adj_close")),
                        "unit": "index",
                    }
                )
                all_data.append(normalized)

            except Exception as e:
                logger.warning("Failed to fetch %s: %s", symbol, e)
                if symbol == "^MOVE":
                    logger.info("Attempting fallback for MOVE index")
                    continue
                raise

        if not all_data:
            logger.warning(
                "No data fetched from Yahoo Finance for symbols: %s", symbols
            )
            return pd.DataFrame(
                columns=["timestamp", "symbol", "source", "value", "unit"]
            )

        result_df = pd.concat(all_data, ignore_index=True)
        result_df = (
            result_df.dropna(subset=["value"])
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        logger.info("Fetched %d data points from Yahoo Finance", len(result_df))

        return result_df

    async def get_current_price(self, symbol: str) -> float | None:
        """Get the most recent price for a symbol.

        Args:
            symbol: Yahoo Finance symbol.

        Returns:
            Most recent close price, or None if unavailable.
        """
        # Fetch last 5 days to ensure we get recent data
        df = await self.collect([symbol], period="5d")

        if df.empty:
            return None

        # Get most recent value
        return float(df.iloc[-1]["value"])

    async def collect_move(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect MOVE index data.

        Args:
            start_date: Start date for data fetch. Defaults to 30 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with MOVE index data.
        """
        return await self.collect(
            ["^MOVE"],
            start_date=start_date or datetime.now(UTC) - timedelta(days=30),
            end_date=end_date,
        )


# Register collector with the registry
registry.register("yahoo", YahooCollector)
