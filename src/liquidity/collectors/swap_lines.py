"""Central Bank Swap Lines collector from NY Fed.

This module provides access to Fed swap line operations data. Swap lines are
emergency USD liquidity facilities between the Fed and foreign central banks.

High swap line usage indicates global USD funding stress - a critical signal
for liquidity analysis.

Standing swap line partners (since 2013):
- ECB (European Central Bank)
- BoJ (Bank of Japan)
- BoE (Bank of England)
- SNB (Swiss National Bank)
- BoC (Bank of Canada)

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

# Central bank partners with standing swap lines
SWAP_PARTNERS = {
    "ECB": "European Central Bank",
    "BOJ": "Bank of Japan",
    "BOE": "Bank of England",
    "SNB": "Swiss National Bank",
    "BOC": "Bank of Canada",
}


class SwapLinesCollector(BaseCollector[pd.DataFrame]):
    """Collector for central bank liquidity swap line data.

    Tracks USD swap line usage between Fed and major central banks.
    High usage indicates global USD funding stress - a key liquidity signal.

    In normal market conditions, swap lines see minimal usage. Spikes occur
    during stress events (e.g., 2008, 2020 COVID).

    API endpoints:
    - FX Swaps latest: /fxs/all/latest.json
    - FX Swaps search: /fxs/all/search.json (with startDate, endDate params)
    - Counterparties: /fxs/list/counterparties.json
    """

    def __init__(
        self,
        name: str = "swap_lines",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Swap Lines collector.

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

    async def collect(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect swap line operations data.

        Note: Returns empty DataFrame in calm markets when no swap operations
        have occurred. This is expected behavior, not an error.

        Args:
            start_date: Start date (default: 90 days ago) - for filtering results
            end_date: End date (default: today) - for filtering results

        Returns:
            DataFrame with swap line usage by partner.
            Columns: timestamp, series_id, source, value, unit, counterparty
            - value is in billions USD
            - series_id format: "SWAP_{counterparty}"

        Raises:
            CollectorFetchError: If API request fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fetch_swap_lines(start_date, end_date)

        try:
            return await self.fetch_with_retry(_fetch, breaker_name="nyfed_swap")
        except Exception as e:
            logger.error("Swap lines fetch failed: %s", e)
            raise CollectorFetchError(f"Swap lines fetch failed: {e}") from e

    async def _fetch_swap_lines(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch swap line operations from NY Fed API.

        Uses the /fxs/all/latest.json endpoint which returns current swap
        operations. In calm markets, this typically returns an empty list.

        Args:
            start_date: Start date for filtering.
            end_date: End date for filtering.

        Returns:
            DataFrame with swap line operations data.
        """
        client = await self._get_client()

        # Use the correct FX swaps endpoint
        url = f"{NYFED_BASE_URL}/fxs/all/latest.json"

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # No swap operations (normal in calm markets)
                logger.info("No swap line operations found (market calm)")
                return self._empty_df()
            raise

        # Parse response - operations array contains swap activity
        operations = data.get("fxSwaps", {}).get("operations", [])

        if not operations:
            # Empty operations is normal in calm markets
            logger.info("No swap line operations - market conditions calm")
            return self._empty_df()

        rows = []
        for op in operations:
            counterparty = op.get("counterparty", "UNKNOWN")
            settlement_date = op.get("settlementDate")
            amount = op.get("amount", 0)

            if settlement_date:
                op_timestamp = pd.to_datetime(settlement_date)

                # Filter by date range
                if start_date.replace(tzinfo=None) <= op_timestamp.replace(
                    tzinfo=None
                ) <= end_date.replace(tzinfo=None):
                    # Normalize counterparty name for series_id
                    clean_counterparty = (
                        counterparty.upper()
                        .replace(" ", "_")
                        .replace("BANK_OF_", "BO")
                    )
                    rows.append(
                        {
                            "timestamp": op_timestamp,
                            "series_id": f"SWAP_{clean_counterparty}",
                            "source": "nyfed",
                            "value": float(amount) / 1e9,  # Convert to billions
                            "unit": "billions_usd",
                            "counterparty": counterparty,
                        }
                    )

        df = pd.DataFrame(rows)

        if len(df) > 0:
            df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info("Fetched %d swap line operations", len(df))
        return df

    def _empty_df(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema.

        Returns:
            Empty DataFrame with expected columns.
        """
        return pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit", "counterparty"]
        )

    async def get_total_outstanding(self) -> pd.DataFrame:
        """Get total outstanding swap line amounts by counterparty.

        Convenience method to aggregate swap line usage.

        Returns:
            DataFrame with total outstanding by counterparty.
        """
        df = await self.collect()

        if df.empty:
            return df

        # Group by counterparty and get latest amounts
        latest = (
            df.sort_values("timestamp")
            .groupby("counterparty")
            .last()
            .reset_index()
        )

        return latest

    async def get_counterparties(self) -> list[str]:
        """Get list of available swap line counterparties.

        Returns:
            List of central bank names that have swap line arrangements.
        """
        client = await self._get_client()
        url = f"{NYFED_BASE_URL}/fxs/list/counterparties.json"

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            counterparties = data.get("fxSwaps", {}).get("counterparties", [])
            logger.info("Retrieved %d swap line counterparties", len(counterparties))
            return counterparties
        except Exception as e:
            logger.warning("Failed to fetch counterparties: %s", e)
            # Return known standing swap line partners as fallback
            return list(SWAP_PARTNERS.values())

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Register collector
registry.register("swap_lines", SwapLinesCollector)
