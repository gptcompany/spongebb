"""TGA Daily collector from US Treasury FiscalData API.

Fetches Treasury General Account (TGA) daily closing balance from the
Daily Treasury Statement (DTS). Updates daily by 4PM ET.

This provides same-day TGA data, reducing lag from 7 days (weekly FRED WDTGAL)
to <1 day.

API Docs: https://fiscaldata.treasury.gov/api-documentation/
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# API Configuration
FISCALDATA_BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
ENDPOINT = "v1/accounting/dts/operating_cash_balance"

# Account type for TGA closing balance
# Note: The API has multiple account types, we want the closing balance
TGA_ACCOUNT_TYPE = "Treasury General Account (TGA) Closing Balance"


class TGADailyCollector(BaseCollector[pd.DataFrame]):
    """Collector for daily TGA data from US Treasury FiscalData API.

    Fetches Treasury General Account closing balance from the Daily Treasury
    Statement (DTS). Updates daily by 4PM ET.

    Note: The API's `close_today_bal` field is null after April 2022.
    We use `open_today_bal` which represents the previous day's closing balance
    (equivalent to current day's opening balance).

    Example:
        collector = TGADailyCollector()
        df = await collector.collect()

        # Get last 30 days
        from datetime import datetime, timedelta, UTC
        start = datetime.now(UTC) - timedelta(days=30)
        df = await collector.collect(start_date=start)

    API Reference:
        Endpoint: v1/accounting/dts/operating_cash_balance
        Filter: account_type:eq:Treasury General Account (TGA) Closing Balance
        Fields: record_date, account_type, open_today_bal, open_month_bal
    """

    def __init__(
        self,
        name: str = "tga_daily",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize TGA Daily collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Returns:
            Configured httpx.AsyncClient instance.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def collect(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect TGA daily data.

        Args:
            start_date: Start date (default: 90 days ago).
            end_date: End date (default: today).

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit.
            Values are in millions USD.

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fetch_tga(start_date, end_date)

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("TGA daily fetch failed: %s", e)
            raise CollectorFetchError(f"TGA daily fetch failed: {e}") from e

    async def _fetch_tga(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch TGA data from FiscalData API.

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            Normalized DataFrame with TGA daily values.
        """
        client = await self._get_client()

        params = {
            "fields": "record_date,account_type,open_today_bal,open_month_bal",
            "filter": (
                f"account_type:eq:{TGA_ACCOUNT_TYPE},"
                f"record_date:gte:{start_date.strftime('%Y-%m-%d')},"
                f"record_date:lte:{end_date.strftime('%Y-%m-%d')}"
            ),
            "sort": "-record_date",
            "page[size]": "500",
            "format": "json",
        }

        url = f"{FISCALDATA_BASE_URL}/{ENDPOINT}"
        response = await client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        records = data.get("data", [])

        if not records:
            logger.warning("No TGA data returned for date range %s to %s", start_date, end_date)
            return pd.DataFrame(columns=["timestamp", "series_id", "source", "value", "unit"])

        # Parse records
        rows = []
        for record in records:
            # Use open_today_bal as the closing balance
            # (close_today_bal is null after April 2022)
            value = record.get("open_today_bal")
            if value is not None:
                rows.append(
                    {
                        "timestamp": pd.to_datetime(record["record_date"]),
                        "series_id": "TGA_DAILY",
                        "source": "fiscaldata",
                        "value": float(value),  # millions USD
                        "unit": "millions_usd",
                    }
                )

        df = pd.DataFrame(rows)
        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(
            "Fetched %d TGA daily records: %s to %s",
            len(df),
            df["timestamp"].min() if len(df) > 0 else "N/A",
            df["timestamp"].max() if len(df) > 0 else "N/A",
        )

        return df

    async def collect_latest(self) -> pd.DataFrame:
        """Collect the latest TGA value.

        Convenience method that fetches only the most recent TGA balance.

        Returns:
            DataFrame with single row containing latest TGA value.
        """
        # Fetch last 7 days to ensure we get at least one value
        # (weekends/holidays have no data)
        start = datetime.now(UTC) - timedelta(days=7)
        df = await self.collect(start_date=start)

        if df.empty:
            return df

        # Return only the latest row
        return df.iloc[[-1]].reset_index(drop=True)

    async def close(self) -> None:
        """Close the HTTP client.

        Should be called when the collector is no longer needed to release
        resources.
        """
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Register collector with the registry
registry.register("tga_daily", TGADailyCollector)
