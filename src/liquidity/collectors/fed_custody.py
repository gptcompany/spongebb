"""Fed Custody Holdings collector for foreign official and international accounts.

Fetches weekly custody holdings data from FRED:
- WSEFINTL1: Total custody holdings (foreign official + international)
- WMTSECL1: Marketable US Treasury securities (~90% of total)
- WFASECL1: Federal agency debt & MBS (~7% of total)

These series track securities held in custody by the Federal Reserve for foreign
central banks and international organizations. Declines may signal:
- Foreign CB selling (reducing USD reserves)
- De-dollarization trends
- Stealth tightening of global USD liquidity
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


# FRED series mapping for Fed Custody Holdings
# All series are weekly (Wednesday level) and in millions USD
CUSTODY_SERIES: dict[str, str] = {
    "fed_custody_total": "WSEFINTL1",  # Total custody holdings
    "fed_custody_treasuries": "WMTSECL1",  # Marketable US Treasury securities
    "fed_custody_agencies": "WFASECL1",  # Federal agency debt & MBS
}

# Unit mapping for custody series
CUSTODY_UNIT_MAP: dict[str, str] = {
    "WSEFINTL1": "millions_usd",
    "WMTSECL1": "millions_usd",
    "WFASECL1": "millions_usd",
}


def _find_date_column(df: pd.DataFrame) -> str:
    """Find the date column in a DataFrame.

    Args:
        df: DataFrame to search.

    Returns:
        Name of the date column.

    Raises:
        ValueError: If no date column can be identified.
    """
    for col in ["date", "index", "timestamp"]:
        if col in df.columns:
            return str(col)

    if df.index.name:
        return str(df.index.name)

    if len(df.columns) > 0:
        return str(df.columns[0])

    raise ValueError("Could not identify date column in DataFrame")


class FedCustodyCollector(BaseCollector[pd.DataFrame]):
    """Fed Custody Holdings collector using OpenBB SDK.

    Fetches weekly custody holdings data for foreign official and international accounts.
    These represent securities held by the Federal Reserve on behalf of foreign central
    banks and international organizations.

    Series:
    - WSEFINTL1: Total custody holdings (~3T USD in 2024)
    - WMTSECL1: Treasury securities (~90% of total)
    - WFASECL1: Agency debt & MBS (~7% of total)

    Example:
        collector = FedCustodyCollector()
        df = await collector.collect_all()

        # Get week-over-week change
        changes = await collector.get_weekly_change()
    """

    CUSTODY_SERIES = CUSTODY_SERIES

    def __init__(
        self,
        name: str = "fed_custody",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Fed Custody collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()

        # Set OpenBB FRED API key if available
        api_key = self._settings.fred_api_key.get_secret_value()
        if api_key:
            obb.user.credentials.fred_api_key = api_key
            logger.debug("FRED API key configured from settings")

    async def collect(
        self,
        symbols: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect Fed custody holdings data.

        Default behavior fetches all three series (total, treasuries, agencies).

        Args:
            symbols: List of FRED series IDs to fetch. Defaults to all custody series.
            start_date: Start date for data fetch. Defaults to 90 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if symbols is None:
            symbols = list(CUSTODY_SERIES.values())
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_sync, symbols, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("Fed Custody fetch failed: %s", e)
            raise CollectorFetchError(f"Fed Custody data fetch failed: {e}") from e

    def _fetch_sync(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Synchronous fetch implementation using OpenBB.

        Args:
            symbols: FRED series IDs.
            start_date: Start date.
            end_date: End date.

        Returns:
            Normalized DataFrame with timestamp, series_id, source, value, unit columns.
        """
        logger.info("Fetching Fed Custody series: %s", symbols)

        # Fetch data using OpenBB
        result = obb.economy.fred_series(
            symbol=",".join(symbols),
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            provider="fred",
        )

        # Convert to DataFrame
        df = result.to_df().reset_index()

        if df.empty:
            logger.warning("No data returned from FRED for symbols: %s", symbols)
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Find date column
        date_col = _find_date_column(df)

        # Melt to long format
        value_vars = [col for col in df.columns if col in symbols]

        if not value_vars:
            logger.warning("No value columns found matching symbols: %s", symbols)
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        df_long = df.melt(
            id_vars=[date_col],
            value_vars=value_vars,
            var_name="series_id",
            value_name="value",
        )

        # Normalize columns
        df_long = df_long.rename(columns={date_col: "timestamp"})
        df_long["timestamp"] = pd.to_datetime(df_long["timestamp"])
        df_long["source"] = "fred"
        df_long["unit"] = (
            df_long["series_id"].map(CUSTODY_UNIT_MAP).fillna("millions_usd")
        )

        # Forward fill NaN values (weekly data may have gaps)
        # Group by series and forward fill within each series
        df_long = df_long.sort_values(["series_id", "timestamp"])
        df_long["value"] = df_long.groupby("series_id")["value"].ffill()

        # Clean and sort
        df_long = (
            df_long.dropna(subset=["value"])
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        # Map FRED series IDs to internal series names
        reverse_map = {v: k for k, v in CUSTODY_SERIES.items()}
        df_long["series_id"] = df_long["series_id"].map(lambda x: reverse_map.get(x, x))

        logger.info("Fetched %d data points from FRED for Fed Custody", len(df_long))

        return df_long[["timestamp", "series_id", "source", "value", "unit"]]

    async def collect_total(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect total custody holdings (WSEFINTL1).

        Args:
            start_date: Start date for data fetch. Defaults to 90 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with total custody holdings data.
        """
        return await self.collect(["WSEFINTL1"], start_date, end_date)

    async def collect_treasuries(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect Treasury securities held in custody (WMTSECL1).

        Represents ~90% of total custody holdings.

        Args:
            start_date: Start date for data fetch. Defaults to 90 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with Treasury securities custody data.
        """
        return await self.collect(["WMTSECL1"], start_date, end_date)

    async def collect_agencies(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect agency debt and MBS held in custody (WFASECL1).

        Represents ~7% of total custody holdings.

        Args:
            start_date: Start date for data fetch. Defaults to 90 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with agency securities custody data.
        """
        return await self.collect(["WFASECL1"], start_date, end_date)

    async def collect_all(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect all custody series combined.

        Fetches WSEFINTL1 (total), WMTSECL1 (treasuries), and WFASECL1 (agencies).

        Args:
            start_date: Start date for data fetch. Defaults to 90 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with all custody series combined.
        """
        return await self.collect(list(CUSTODY_SERIES.values()), start_date, end_date)

    async def get_weekly_change(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate week-over-week change in custody holdings.

        Args:
            start_date: Start date for data fetch. Defaults to 90 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, value, change, change_pct
        """
        df = await self.collect_all(start_date, end_date)

        if df.empty:
            return pd.DataFrame(
                columns=["timestamp", "series_id", "value", "change", "change_pct"]
            )

        # Calculate weekly changes by series
        result_dfs = []
        for series_id in df["series_id"].unique():
            series_df = df[df["series_id"] == series_id].copy()
            series_df = series_df.sort_values("timestamp")
            series_df["change"] = series_df["value"].diff()
            series_df["change_pct"] = series_df["value"].pct_change() * 100
            result_dfs.append(series_df)

        result = pd.concat(result_dfs, ignore_index=True)
        result = result.dropna(subset=["change"])

        logger.info("Calculated weekly changes for %d data points", len(result))

        return result[["timestamp", "series_id", "value", "change", "change_pct"]]

    async def get_yoy_change(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate year-over-year change in custody holdings.

        Compares each data point to the value 52 weeks prior.

        Args:
            start_date: Start date for data fetch. Defaults to 400 days ago (to have YoY data).
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, value, yoy_change, yoy_change_pct
        """
        # Need more history for YoY calculation
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=400)

        df = await self.collect_all(start_date, end_date)

        if df.empty:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "series_id",
                    "value",
                    "yoy_change",
                    "yoy_change_pct",
                ]
            )

        # Calculate YoY changes by series (52 weeks = ~1 year)
        result_dfs = []
        for series_id in df["series_id"].unique():
            series_df = df[df["series_id"] == series_id].copy()
            series_df = series_df.sort_values("timestamp")
            series_df["yoy_change"] = series_df["value"].diff(periods=52)
            series_df["yoy_change_pct"] = (
                series_df["value"].pct_change(periods=52) * 100
            )
            result_dfs.append(series_df)

        result = pd.concat(result_dfs, ignore_index=True)
        result = result.dropna(subset=["yoy_change"])

        logger.info("Calculated YoY changes for %d data points", len(result))

        return result[
            ["timestamp", "series_id", "value", "yoy_change", "yoy_change_pct"]
        ]


# Register collector with the registry
registry.register("fed_custody", FedCustodyCollector)
