"""NY Fed Markets API collector for RRP and SOMA data.

This module provides collectors for high-frequency data from the NY Fed Markets API:
- RRP (Reverse Repo) daily operations - used in Hayes Net Liquidity formula
- SOMA (System Open Market Account) holdings

API Docs: https://markets.newyorkfed.org/static/docs/markets-api.html
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

NYFED_BASE_URL = "https://markets.newyorkfed.org/api"


class NYFedCollector(BaseCollector[pd.DataFrame]):
    """Collector for NY Fed Markets API data.

    Provides access to:
    - RRP (Reverse Repo) daily operations - same-day data vs weekly FRED lag
    - SOMA (System Open Market Account) holdings

    The RRP data is critical for the Hayes Net Liquidity formula:
        Net Liquidity = WALCL - TGA - RRP

    API endpoints:
    - RRP: /rp/reverserepo/propositions/search.json (with startDate, endDate params)
    - SOMA: /soma/summary.json
    """

    def __init__(
        self,
        name: str = "nyfed",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize NY Fed collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def collect_rrp(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect RRP (Reverse Repo) operations data.

        Fetches daily Overnight Reverse Repo (ON RRP) operations from NY Fed.
        This provides same-day data vs the 7-day lag from FRED's WLRRAL series.

        Args:
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: today)

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
            - value is in billions USD
            - series_id is "RRP_DAILY"

        Raises:
            CollectorFetchError: If API request fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fetch_rrp(start_date, end_date)

        try:
            return await self.fetch_with_retry(_fetch, breaker_name="nyfed_rrp")
        except Exception as e:
            logger.error("NY Fed RRP fetch failed: %s", e)
            raise CollectorFetchError(f"NY Fed RRP fetch failed: {e}") from e

    async def _fetch_rrp(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch RRP operations from NY Fed API.

        Uses the reverserepo/propositions endpoint which provides daily
        Reverse Repo operation results with breakdown by counterparty type.

        Args:
            start_date: Start date for query.
            end_date: End date for query.

        Returns:
            DataFrame with RRP operations data.
        """
        client = await self._get_client()

        # Use reverserepo propositions endpoint for daily RRP data
        url = f"{NYFED_BASE_URL}/rp/reverserepo/propositions/search.json"
        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
        }

        response = await client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        operations = data.get("repo", {}).get("operations", [])

        if not operations:
            logger.warning("No RRP operations returned from NY Fed API")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        rows = []
        for op in operations:
            # Each operation has totalAmtAccepted which is the daily RRP total
            total_amt = op.get("totalAmtAccepted", 0)
            rows.append(
                {
                    "timestamp": pd.to_datetime(op["operationDate"]),
                    "series_id": "RRP_DAILY",
                    "source": "nyfed",
                    "value": float(total_amt) / 1e9,  # Convert to billions
                    "unit": "billions_usd",
                }
            )

        df = pd.DataFrame(rows)
        if len(df) > 0:
            # Aggregate by date (multiple operations per day possible)
            df = (
                df.groupby("timestamp")
                .agg(
                    {
                        "series_id": "first",
                        "source": "first",
                        "value": "sum",
                        "unit": "first",
                    }
                )
                .reset_index()
            )

        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info("Fetched %d RRP daily records from NY Fed", len(df))
        return df

    async def collect_soma(self) -> pd.DataFrame:
        """Collect SOMA (System Open Market Account) holdings summary.

        SOMA represents the Fed's balance sheet holdings - critical for
        understanding QE/QT operations.

        Returns:
            DataFrame with SOMA holdings by security type.
            Columns: timestamp, series_id, source, value, unit
            - value is in billions USD
            - series_id format: "SOMA_{security_type}"

        Raises:
            CollectorFetchError: If API request fails after retries.
        """

        async def _fetch() -> pd.DataFrame:
            return await self._fetch_soma()

        try:
            return await self.fetch_with_retry(_fetch, breaker_name="nyfed_soma")
        except Exception as e:
            logger.error("NY Fed SOMA fetch failed: %s", e)
            raise CollectorFetchError(f"NY Fed SOMA fetch failed: {e}") from e

    async def _fetch_soma(self) -> pd.DataFrame:
        """Fetch SOMA holdings from NY Fed API.

        The SOMA summary endpoint returns historical data for all dates.
        We extract the latest date's holdings.

        Returns:
            DataFrame with SOMA holdings data.
        """
        client = await self._get_client()

        url = f"{NYFED_BASE_URL}/soma/summary.json"
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()
        summaries = data.get("soma", {}).get("summary", [])

        if not summaries:
            logger.warning("No SOMA summary data returned")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Find the most recent summary by date
        dates = [s["asOfDate"] for s in summaries]
        latest_date = max(dates)
        latest_summary = next(s for s in summaries if s["asOfDate"] == latest_date)

        # Map SOMA fields to normalized series
        # Values in the API are in dollars (strings), convert to billions
        field_mapping = {
            "mbs": "MBS",
            "cmbs": "CMBS",
            "tips": "TIPS",
            "frn": "FRN",
            "tipsInflationCompensation": "TIPS_INFLATION_COMP",
            "notesbonds": "NOTES_BONDS",
            "bills": "BILLS",
            "agencies": "AGENCIES",
            "total": "TOTAL",
        }

        rows = []
        for field, series_name in field_mapping.items():
            value_str = latest_summary.get(field, "0")
            if value_str and value_str.strip():
                try:
                    value = float(value_str) / 1e9  # Convert to billions
                    rows.append(
                        {
                            "timestamp": pd.to_datetime(latest_date),
                            "series_id": f"SOMA_{series_name}",
                            "source": "nyfed",
                            "value": value,
                            "unit": "billions_usd",
                        }
                    )
                except (ValueError, TypeError):
                    pass  # Skip fields that can't be parsed

        df = pd.DataFrame(rows)
        logger.info(
            "Fetched SOMA holdings as of %s (%d series, total: %.1fT)",
            latest_date,
            len(df),
            df[df["series_id"] == "SOMA_TOTAL"]["value"].iloc[0] / 1000
            if len(df) > 0
            else 0,
        )
        return df

    async def collect(
        self,
        data_type: str = "rrp",
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Generic collect method for the collector interface.

        Args:
            data_type: Type of data to collect: "rrp" or "soma"
            **kwargs: Passed to specific collector method

        Returns:
            DataFrame with requested data.

        Raises:
            ValueError: If data_type is not recognized.
        """
        if data_type == "rrp":
            return await self.collect_rrp(**kwargs)
        elif data_type == "soma":
            return await self.collect_soma()
        else:
            raise ValueError(f"Unknown data_type: {data_type}. Use 'rrp' or 'soma'.")

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Register collector
registry.register("nyfed", NYFedCollector)
