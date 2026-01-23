"""SOFR (Secured Overnight Financing Rate) collector with multi-tier fallback.

SOFR is the primary USD overnight rate (replaced LIBOR). Essential for:
- Carry trade signals
- Funding stress detection
- Overnight funding market health

Implements ROBUST fallback: NY Fed API -> FRED -> cached baseline.
"""

import logging
from datetime import datetime
from typing import Any

import httpx
import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# NY Fed Markets API base URL
NYFED_MARKETS_API = "https://markets.newyorkfed.org/api/rates/secured/sofr"


class SOFRCollector(BaseCollector[pd.DataFrame]):
    """SOFR collector with ROBUST multi-tier fallback.

    Tier 1: NY Fed Markets API (primary, no auth required)
    Tier 2: FRED via OpenBB (fallback)
    Tier 3: Cached baseline (guaranteed)
    """

    # Cached baseline for guaranteed fallback
    BASELINE_VALUE = 4.35  # percent, Jan 2026
    BASELINE_DATE = "2026-01-22"

    def __init__(
        self,
        name: str = "sofr",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize SOFR collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()

    async def collect(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        days: int = 30,
    ) -> pd.DataFrame:
        """Collect SOFR data with multi-tier fallback (ALWAYS returns data).

        Args:
            start_date: Start date for data fetch (used for FRED fallback).
            end_date: End date for data fetch (used for FRED fallback).
            days: Number of days of historical data for NY Fed API. Default 30.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
        """
        # Tier 1: Try NY Fed Markets API
        try:
            logger.info("SOFR: Attempting Tier 1 (NY Fed Markets API)")
            return await self._collect_via_nyfed(days)
        except Exception as e:
            logger.warning("SOFR Tier 1 (NY Fed API) failed: %s", e)

        # Tier 2: Try FRED via OpenBB
        try:
            logger.info("SOFR: Attempting Tier 2 (FRED)")
            return await self._collect_via_fred(start_date, end_date)
        except Exception as e:
            logger.warning("SOFR Tier 2 (FRED) failed: %s", e)

        # Tier 3: Return cached baseline (GUARANTEED)
        logger.warning("All SOFR sources failed, returning cached baseline")
        return self._get_cached_baseline()

    async def _collect_via_nyfed(self, days: int = 30) -> pd.DataFrame:
        """Tier 1: Fetch from NY Fed Markets API.

        API endpoint: https://markets.newyorkfed.org/api/rates/secured/sofr/last/{n}.json
        No authentication required.

        Args:
            days: Number of days of historical data.

        Returns:
            DataFrame with SOFR data.

        Raises:
            CollectorFetchError: If API request fails or response is invalid.
        """
        url = f"{NYFED_MARKETS_API}/last/{days}.json"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()

            # Parse response structure
            # Expected: {"refRates": [{"effectiveDate": "2026-01-21", "percentRate": 3.63, ...}]}
            ref_rates = data.get("refRates", [])

            if not ref_rates:
                raise CollectorFetchError("NY Fed API returned no SOFR data")

            records = []
            for rate_data in ref_rates:
                effective_date = rate_data.get("effectiveDate")
                percent_rate = rate_data.get("percentRate")

                if effective_date and percent_rate is not None:
                    records.append(
                        {
                            "timestamp": pd.to_datetime(effective_date),
                            "series_id": "SOFR",
                            "source": "nyfed",
                            "value": float(percent_rate),
                            "unit": "percent",
                        }
                    )

            if not records:
                raise CollectorFetchError("Could not parse SOFR data from NY Fed API")

            df = pd.DataFrame(records)
            df = df.sort_values("timestamp").reset_index(drop=True)

            logger.info("Fetched %d SOFR data points from NY Fed API", len(df))
            return df

    async def _collect_via_fred(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> pd.DataFrame:
        """Tier 2: Fetch from FRED via FredCollector.

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with SOFR data.

        Raises:
            CollectorFetchError: If FRED fetch fails.
        """
        from liquidity.collectors.fred import FredCollector

        fred = FredCollector()
        df = await fred.collect(["SOFR"], start_date, end_date)

        if df.empty:
            raise CollectorFetchError("FRED returned no SOFR data")

        # Ensure source is marked as fred (should already be)
        df = df.copy()
        df["source"] = "fred"

        logger.info("Fetched %d SOFR data points from FRED", len(df))
        return df[["timestamp", "series_id", "source", "value", "unit"]]

    def _get_cached_baseline(self) -> pd.DataFrame:
        """Tier 3: Return cached baseline (GUARANTEED).

        Returns:
            DataFrame with single row containing baseline SOFR value.
        """
        return pd.DataFrame(
            {
                "timestamp": [pd.to_datetime(self.BASELINE_DATE)],
                "series_id": ["SOFR"],
                "source": ["cached_baseline"],
                "value": [float(self.BASELINE_VALUE)],
                "unit": ["percent"],
                "stale": [True],
            }
        )

    async def collect_latest(self) -> pd.DataFrame:
        """Convenience method to get just the latest SOFR rate.

        Returns:
            DataFrame with single row containing latest SOFR value.
        """
        # Fetch just 1 day from NY Fed
        try:
            logger.info("SOFR: Fetching latest rate from NY Fed")
            return await self._collect_via_nyfed(days=1)
        except Exception as e:
            logger.warning("SOFR latest fetch from NY Fed failed: %s", e)

        # Fall back to full collection with fallbacks
        df = await self.collect(days=1)
        if not df.empty:
            # Return only the most recent row
            return (
                df.sort_values("timestamp", ascending=False)
                .head(1)
                .reset_index(drop=True)
            )
        return df


# Register collector
registry.register("sofr", SOFRCollector)
