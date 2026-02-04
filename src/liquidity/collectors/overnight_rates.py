"""Overnight rate collectors for EUR, GBP, and CAD.

This module provides collectors for:
- ESTR (Euro Short-Term Rate) - ECB
- SONIA (Sterling Overnight Index Average) - BoE via FRED
- CORRA (Canadian Overnight Repo Rate Average) - BoC Valet

All collectors follow the multi-tier fallback pattern:
Primary API -> FRED fallback -> Cached baseline (guaranteed)
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pandas as pd
from openbb import obb

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# ESTR Collector (Euro Short-Term Rate)
# =============================================================================


class ESTRCollector(BaseCollector[pd.DataFrame]):
    """Euro Short-Term Rate (ESTR) collector.

    Multi-tier fallback:
    - Tier 1: estr.dev API (simplest, reliable, no auth)
    - Tier 2: FRED (series ECBESTRVOLWGTTRMDMNRT)
    - Tier 3: Cached baseline (guaranteed)

    Note: ESTR is published T+1 (next business day after effective date).
    """

    BASELINE_VALUE = 2.90  # percent (Jan 2026)
    BASELINE_DATE = "2026-01-22"

    def __init__(
        self,
        name: str = "estr",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize ESTR collector.

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
    ) -> pd.DataFrame:
        """Collect ESTR data with multi-tier fallback.

        Args:
            start_date: Start date (used for FRED fallback).
            end_date: End date (used for FRED fallback).

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
        """
        # Tier 1: estr.dev API
        try:
            logger.info("ESTR Tier 1: Attempting estr.dev API")
            return await self._collect_estrdev()
        except Exception as e:
            logger.warning("ESTR Tier 1 (estr.dev) failed: %s", e)

        # Tier 2: FRED fallback
        try:
            logger.info("ESTR Tier 2: Attempting FRED fallback")
            return await self._collect_fred(start_date, end_date)
        except Exception as e:
            logger.warning("ESTR Tier 2 (FRED) failed: %s", e)

        # Tier 3: Cached baseline (GUARANTEED)
        logger.warning("ESTR: All sources failed, using cached baseline")
        return self._get_cached_baseline()

    async def _collect_estrdev(self) -> pd.DataFrame:
        """Fetch ESTR from estr.dev API.

        Returns:
            DataFrame with latest ESTR rate.
        """
        url = "https://api.estr.dev/latest"

        async def _fetch() -> pd.DataFrame:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            # Response: {"date": "2026-01-21", "value": 1.932}
            date_str = data.get("date")
            value = data.get("value")

            if not date_str or value is None:
                raise CollectorFetchError("Invalid response from estr.dev")

            df = pd.DataFrame(
                [
                    {
                        "timestamp": pd.to_datetime(date_str),
                        "series_id": "ESTR",
                        "source": "estr_dev",
                        "value": float(value),
                        "unit": "percent",
                    }
                ]
            )

            logger.info("ESTR: Fetched %s = %.3f%% from estr.dev", date_str, value)
            return df

        return await self.fetch_with_retry(_fetch)

    async def _collect_fred(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> pd.DataFrame:
        """Fetch ESTR from FRED via OpenBB.

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with ESTR data from FRED.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(UTC)

        def _sync_fetch() -> pd.DataFrame:
            # Set API key if available
            api_key = self._settings.fred_api_key.get_secret_value()
            if api_key:
                obb.user.credentials.fred_api_key = api_key

            result = obb.economy.fred_series(
                symbol="ECBESTRVOLWGTTRMDMNRT",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                provider="fred",
            )

            df = result.to_df().reset_index()
            if df.empty:
                raise CollectorFetchError("No ESTR data from FRED")

            # Find date column
            date_col = "date" if "date" in df.columns else df.columns[0]

            # Normalize to standard format
            records = []
            for _, row in df.iterrows():
                records.append(
                    {
                        "timestamp": pd.to_datetime(row[date_col]),
                        "series_id": "ESTR",
                        "source": "fred",
                        "value": float(row["ECBESTRVOLWGTTRMDMNRT"]),
                        "unit": "percent",
                    }
                )

            return pd.DataFrame(records)

        return await asyncio.to_thread(_sync_fetch)

    def _get_cached_baseline(self) -> pd.DataFrame:
        """Return cached baseline value as guaranteed fallback.

        Returns:
            DataFrame with cached ESTR baseline.
        """
        return pd.DataFrame(
            [
                {
                    "timestamp": pd.to_datetime(self.BASELINE_DATE),
                    "series_id": "ESTR",
                    "source": "cached_baseline",
                    "value": self.BASELINE_VALUE,
                    "unit": "percent",
                    "stale": True,
                }
            ]
        )


# =============================================================================
# SONIA Collector (Sterling Overnight Index Average)
# =============================================================================


class SONIACollector(BaseCollector[pd.DataFrame]):
    """Sterling Overnight Index Average (SONIA) collector.

    Multi-tier fallback:
    - Tier 1: FRED (series IUDSOIA) - BoE IADB is unreliable per research
    - Tier 2: Cached baseline (guaranteed)

    Note: SONIA is published T+1 (next business day after effective date).
    """

    BASELINE_VALUE = 4.70  # percent (Jan 2026)
    BASELINE_DATE = "2026-01-22"

    def __init__(
        self,
        name: str = "sonia",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize SONIA collector.

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
    ) -> pd.DataFrame:
        """Collect SONIA data with multi-tier fallback.

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
        """
        # Tier 1: FRED (primary source since BoE IADB is unreliable)
        try:
            logger.info("SONIA Tier 1: Attempting FRED")
            return await self._collect_fred(start_date, end_date)
        except Exception as e:
            logger.warning("SONIA Tier 1 (FRED) failed: %s", e)

        # Tier 2: Cached baseline (GUARANTEED)
        logger.warning("SONIA: All sources failed, using cached baseline")
        return self._get_cached_baseline()

    async def _collect_fred(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> pd.DataFrame:
        """Fetch SONIA from FRED via OpenBB.

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with SONIA data from FRED.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(UTC)

        def _sync_fetch() -> pd.DataFrame:
            # Set API key if available
            api_key = self._settings.fred_api_key.get_secret_value()
            if api_key:
                obb.user.credentials.fred_api_key = api_key

            result = obb.economy.fred_series(
                symbol="IUDSOIA",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                provider="fred",
            )

            df = result.to_df().reset_index()
            if df.empty:
                raise CollectorFetchError("No SONIA data from FRED")

            # Find date column
            date_col = "date" if "date" in df.columns else df.columns[0]

            # Normalize to standard format
            records = []
            for _, row in df.iterrows():
                records.append(
                    {
                        "timestamp": pd.to_datetime(row[date_col]),
                        "series_id": "SONIA",
                        "source": "fred",
                        "value": float(row["IUDSOIA"]),
                        "unit": "percent",
                    }
                )

            return pd.DataFrame(records)

        return await asyncio.to_thread(_sync_fetch)

    def _get_cached_baseline(self) -> pd.DataFrame:
        """Return cached baseline value as guaranteed fallback.

        Returns:
            DataFrame with cached SONIA baseline.
        """
        return pd.DataFrame(
            [
                {
                    "timestamp": pd.to_datetime(self.BASELINE_DATE),
                    "series_id": "SONIA",
                    "source": "cached_baseline",
                    "value": self.BASELINE_VALUE,
                    "unit": "percent",
                    "stale": True,
                }
            ]
        )


# =============================================================================
# CORRA Collector (Canadian Overnight Repo Rate Average)
# =============================================================================


class CORRACollector(BaseCollector[pd.DataFrame]):
    """Canadian Overnight Repo Rate Average (CORRA) collector.

    Multi-tier fallback:
    - Tier 1: BoC Valet API (highly reliable, no auth required)
    - Tier 2: Cached baseline (guaranteed)

    Note: BoC Valet is the most reliable CB API - no fallback usually needed.
    """

    BASELINE_VALUE = 3.00  # percent (Jan 2026)
    BASELINE_DATE = "2026-01-22"
    VALET_BASE_URL = "https://www.bankofcanada.ca/valet/observations"

    def __init__(
        self,
        name: str = "corra",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize CORRA collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()

    async def collect(
        self,
        recent: int = 30,
    ) -> pd.DataFrame:
        """Collect CORRA data with multi-tier fallback.

        Args:
            recent: Number of recent observations to fetch (default 30).

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
        """
        # Tier 1: BoC Valet API
        try:
            logger.info("CORRA Tier 1: Attempting BoC Valet API")
            return await self._collect_valet(recent)
        except Exception as e:
            logger.warning("CORRA Tier 1 (BoC Valet) failed: %s", e)

        # Tier 2: Cached baseline (GUARANTEED)
        logger.warning("CORRA: All sources failed, using cached baseline")
        return self._get_cached_baseline()

    async def _collect_valet(self, recent: int) -> pd.DataFrame:
        """Fetch CORRA from BoC Valet API.

        Args:
            recent: Number of recent observations to fetch.

        Returns:
            DataFrame with CORRA data.
        """
        url = f"{self.VALET_BASE_URL}/AVG.INTWO/json"
        params = {"recent": str(recent)}

        async def _fetch() -> pd.DataFrame:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            observations = data.get("observations", [])
            if not observations:
                raise CollectorFetchError("No observations from BoC Valet")

            records = []
            for obs in observations:
                date_str = obs.get("d")
                # Value is nested: {"AVG.INTWO": {"v": "2.2500"}}
                value_obj = obs.get("AVG.INTWO", {})
                value_str = value_obj.get("v")

                if date_str and value_str is not None:
                    records.append(
                        {
                            "timestamp": pd.to_datetime(date_str),
                            "series_id": "CORRA",
                            "source": "boc_valet",
                            "value": float(value_str),  # Note: value is STRING
                            "unit": "percent",
                        }
                    )

            if not records:
                raise CollectorFetchError("No valid CORRA observations parsed")

            df = pd.DataFrame(records)
            df = df.sort_values("timestamp").reset_index(drop=True)

            logger.info("CORRA: Fetched %d observations from BoC Valet", len(df))
            return df

        return await self.fetch_with_retry(_fetch)

    def _get_cached_baseline(self) -> pd.DataFrame:
        """Return cached baseline value as guaranteed fallback.

        Returns:
            DataFrame with cached CORRA baseline.
        """
        return pd.DataFrame(
            [
                {
                    "timestamp": pd.to_datetime(self.BASELINE_DATE),
                    "series_id": "CORRA",
                    "source": "cached_baseline",
                    "value": self.BASELINE_VALUE,
                    "unit": "percent",
                    "stale": True,
                }
            ]
        )


# =============================================================================
# Rate Differential Calculation
# =============================================================================


def calculate_rate_differentials(
    sofr_df: pd.DataFrame,
    estr_df: pd.DataFrame,
    sonia_df: pd.DataFrame,
    corra_df: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate SOFR vs other overnight rate differentials for carry trade signals.

    Args:
        sofr_df: SOFR data with columns [timestamp, value]
        estr_df: ESTR data with columns [timestamp, value]
        sonia_df: SONIA data with columns [timestamp, value]
        corra_df: CORRA data with columns [timestamp, value]

    Returns:
        DataFrame with columns:
        - timestamp
        - sofr_estr_spread (SOFR - ESTR, positive = USD yield advantage)
        - sofr_sonia_spread (SOFR - SONIA)
        - sofr_corra_spread (SOFR - CORRA)

    Note: Positive spread = carry trade favors borrowing in foreign currency, lending in USD.
    """
    # Merge all rates on timestamp with outer join
    merged = sofr_df[["timestamp", "value"]].rename(columns={"value": "sofr"})
    merged = merged.merge(
        estr_df[["timestamp", "value"]].rename(columns={"value": "estr"}),
        on="timestamp",
        how="outer",
    )
    merged = merged.merge(
        sonia_df[["timestamp", "value"]].rename(columns={"value": "sonia"}),
        on="timestamp",
        how="outer",
    )
    merged = merged.merge(
        corra_df[["timestamp", "value"]].rename(columns={"value": "corra"}),
        on="timestamp",
        how="outer",
    )

    # Forward-fill for date alignment (rates publish on different schedules)
    merged = merged.sort_values("timestamp").ffill()

    # Calculate spreads
    result = pd.DataFrame(
        {
            "timestamp": merged["timestamp"],
            "sofr_estr_spread": merged["sofr"] - merged["estr"],
            "sofr_sonia_spread": merged["sofr"] - merged["sonia"],
            "sofr_corra_spread": merged["sofr"] - merged["corra"],
        }
    )

    return result.dropna()


# =============================================================================
# Registry
# =============================================================================

# Register all collectors
registry.register("estr", ESTRCollector)
registry.register("sonia", SONIACollector)
registry.register("corra", CORRACollector)
