"""EIA API v2 collector for Weekly Petroleum Status Report data.

Fetches petroleum data from EIA (Energy Information Administration):
- WCESTUS1: US Crude Oil Stocks (weekly, thousand barrels)
- WCRFPUS2: US Crude Oil Production (weekly, thousand b/d)
- WCRIMUS2: US Crude Oil Imports (weekly, thousand b/d)

Weekly data is released every Wednesday.
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

# EIA API v2 series mapping
# Keys are internal names, values are EIA series IDs
SERIES_MAP: dict[str, str] = {
    "crude_stocks_total": "WCESTUS1",  # US crude stocks (thousand barrels)
    "crude_production": "WCRFPUS2",  # US crude production (thousand b/d)
    "crude_imports": "WCRIMUS2",  # US crude imports (thousand b/d)
    # Refinery Utilization (percent, weekly)
    "refinery_utilization_us": "WPULEUS3",  # US total refinery utilization
    "refinery_utilization_padd1": "W_NA_YUP_R10_PER",  # PADD 1 (East Coast)
    "refinery_utilization_padd3": "W_NA_YUP_R30_PER",  # PADD 3 (Gulf Coast - 50%+ of US)
    "refinery_utilization_padd5": "W_NA_YUP_R50_PER",  # PADD 5 (West Coast)
    # Cushing, Oklahoma storage (WTI delivery point)
    "cushing_inventory": "W_EPC0_SAX_YCUOK_MBBL",  # Cushing stocks (excl SPR)
}

# Unit mapping for EIA series
UNIT_MAP: dict[str, str] = {
    "WCESTUS1": "thousand_barrels",
    "WCRFPUS2": "thousand_bpd",
    "WCRIMUS2": "thousand_bpd",
    # Refinery Utilization
    "WPULEUS3": "percent",
    "W_NA_YUP_R10_PER": "percent",
    "W_NA_YUP_R30_PER": "percent",
    "W_NA_YUP_R50_PER": "percent",
    # Cushing inventory
    "W_EPC0_SAX_YCUOK_MBBL": "thousand_barrels",
}

# API route mapping for each series
# The EIA API v2 uses different routes for different data types
ROUTE_MAP: dict[str, str] = {
    "WCESTUS1": "/petroleum/stoc/wstk/data",  # Weekly Stocks
    "WCRFPUS2": "/petroleum/sum/sndw/data",  # Weekly Supply Estimates
    "WCRIMUS2": "/petroleum/sum/sndw/data",  # Weekly Supply Estimates
    # Refinery Utilization
    "WPULEUS3": "/petroleum/sum/sndw/data",  # Weekly Supply Estimates
    "W_NA_YUP_R10_PER": "/petroleum/sum/sndw/data",  # PADD 1
    "W_NA_YUP_R30_PER": "/petroleum/sum/sndw/data",  # PADD 3
    "W_NA_YUP_R50_PER": "/petroleum/sum/sndw/data",  # PADD 5
    # Cushing inventory
    "W_EPC0_SAX_YCUOK_MBBL": "/petroleum/stoc/wstk/data",  # Weekly Stocks
}

# Refinery utilization signal thresholds (percent)
UTILIZATION_THRESHOLDS: dict[str, float] = {
    "TIGHT": 95.0,  # >95% - Supply constraint risk
    "NORMAL": 90.0,  # >90% - Healthy utilization
    "SOFT": 85.0,  # >85% - Slightly below normal
    # Below 85% = WEAK (demand concerns)
}

# Cushing storage capacity in thousand barrels (70.8 million barrels = 70,800 thousand barrels)
# Source: EIA reports ~14% of US commercial tank storage capacity
CUSHING_CAPACITY_KB: int = 70_800


class EIACollector(BaseCollector[pd.DataFrame]):
    """EIA API v2 collector for weekly petroleum data.

    Fetches US crude oil stocks, production, and imports data from the
    EIA Weekly Petroleum Status Report.

    Example:
        collector = EIACollector()
        df = await collector.collect(["WCESTUS1", "WCRFPUS2"])

        # Get all series
        df = await collector.collect()
    """

    BASE_URL = "https://api.eia.gov/v2"
    SERIES_MAP = SERIES_MAP

    def __init__(
        self,
        name: str = "eia",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize EIA collector.

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
                base_url=self.BASE_URL,
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    def _empty_df(self) -> pd.DataFrame:
        """Return an empty DataFrame with the expected schema.

        Returns:
            Empty DataFrame with timestamp, series_id, source, value, unit columns.
        """
        return pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

    async def collect(
        self,
        symbols: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect EIA petroleum data.

        Args:
            symbols: List of EIA series IDs to fetch. Defaults to all core series.
            start_date: Start date for data fetch. Defaults to 52 weeks ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if symbols is None:
            symbols = list(SERIES_MAP.values())
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(weeks=52)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fetch_series(symbols, start_date, end_date)

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("EIA fetch failed: %s", e)
            raise CollectorFetchError(f"EIA data fetch failed: {e}") from e

    async def _fetch_series(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch data for multiple series from EIA API.

        Args:
            symbols: EIA series IDs.
            start_date: Start date.
            end_date: End date.

        Returns:
            Normalized DataFrame with timestamp, series_id, source, value, unit columns.
        """
        api_key = self._settings.eia_api_key.get_secret_value()
        if not api_key:
            logger.warning("EIA_API_KEY not configured, returning empty DataFrame")
            return self._empty_df()

        logger.info("Fetching EIA series: %s", symbols)

        all_data: list[pd.DataFrame] = []
        client = await self._get_client()

        for series_id in symbols:
            try:
                df = await self._fetch_single_series(
                    client, series_id, api_key, start_date, end_date
                )
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                logger.warning("Failed to fetch EIA series %s: %s", series_id, e)

        if not all_data:
            logger.warning("No data returned from EIA for symbols: %s", symbols)
            return self._empty_df()

        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values("timestamp").reset_index(drop=True)

        logger.info("Fetched %d data points from EIA", len(result))
        return result

    async def _fetch_single_series(
        self,
        client: httpx.AsyncClient,
        series_id: str,
        api_key: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch a single series from EIA API.

        Args:
            client: HTTP client.
            series_id: EIA series ID.
            api_key: EIA API key.
            start_date: Start date.
            end_date: End date.

        Returns:
            DataFrame with timestamp, series_id, source, value, unit columns.
        """
        route = ROUTE_MAP.get(series_id, "/petroleum/stoc/wstk/data")

        params = {
            "api_key": api_key,
            "data[]": "value",
            "facets[series][]": series_id,
            "frequency": "weekly",
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 5000,  # Max rows per request
        }

        response = await client.get(route, params=params)
        response.raise_for_status()

        data = response.json()

        # Parse response
        if "response" not in data or "data" not in data["response"]:
            logger.warning("Unexpected EIA response structure for %s", series_id)
            return self._empty_df()

        records = data["response"]["data"]

        if not records:
            return self._empty_df()

        # Transform to DataFrame
        rows = []
        for record in records:
            try:
                value = record.get("value")
                if value is None:
                    continue

                rows.append(
                    {
                        "timestamp": pd.Timestamp(record["period"]),
                        "series_id": series_id,
                        "source": "eia",
                        "value": float(value),
                        "unit": UNIT_MAP.get(series_id, "unknown"),
                    }
                )
            except (KeyError, ValueError, TypeError) as e:
                logger.debug("Skipping invalid record for %s: %s", series_id, e)

        if not rows:
            return self._empty_df()

        return pd.DataFrame(rows)

    async def collect_stocks(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect crude oil stocks.

        Args:
            start_date: Start date for data fetch. Defaults to 52 weeks ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with crude stocks data (thousand barrels).
        """
        return await self.collect(["WCESTUS1"], start_date, end_date)

    async def collect_production(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect crude oil production.

        Args:
            start_date: Start date for data fetch. Defaults to 52 weeks ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with production data (thousand b/d).
        """
        return await self.collect(["WCRFPUS2"], start_date, end_date)

    async def collect_imports(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect crude oil imports.

        Args:
            start_date: Start date for data fetch. Defaults to 52 weeks ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with imports data (thousand b/d).
        """
        return await self.collect(["WCRIMUS2"], start_date, end_date)

    async def collect_refinery_utilization(
        self,
        regions: list[str] | None = None,
        lookback_weeks: int = 52,
    ) -> pd.DataFrame:
        """Collect refinery utilization data by region.

        Fetches refinery capacity utilization rates from EIA Weekly Petroleum
        Status Report. High utilization (>95%) indicates supply constraints,
        while low utilization (<85%) suggests weak demand or maintenance season.

        Args:
            regions: List of regions to fetch. Options: "us", "padd1", "padd3", "padd5".
                Defaults to all regions (US total + PADD 1, 3, 5).
            lookback_weeks: Number of weeks of historical data. Defaults to 52.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit.
            Values are refinery utilization percentages.

        Example:
            collector = EIACollector()

            # Get all regions
            df = await collector.collect_refinery_utilization()

            # Get only Gulf Coast (PADD 3)
            df = await collector.collect_refinery_utilization(regions=["padd3"])
        """
        if regions is None:
            regions = ["us", "padd1", "padd3", "padd5"]

        # Map region names to series IDs
        series_ids = []
        for region in regions:
            series_key = f"refinery_utilization_{region}"
            if series_key in SERIES_MAP:
                series_ids.append(SERIES_MAP[series_key])
            else:
                logger.warning("Unknown refinery region: %s", region)

        if not series_ids:
            logger.warning("No valid refinery utilization series requested")
            return self._empty_df()

        start_date = datetime.now(UTC) - timedelta(weeks=lookback_weeks)
        end_date = datetime.now(UTC)

        return await self.collect(series_ids, start_date, end_date)

    def calculate_utilization_signal(self, df: pd.DataFrame) -> str:
        """Classify refinery utilization level into a market signal.

        Uses US national refinery utilization rate to determine market conditions:
        - TIGHT (>95%): Supply constraint risk, refineries near max capacity
        - NORMAL (>90%): Healthy utilization, balanced market
        - SOFT (>85%): Slightly below normal, may indicate softening demand
        - WEAK (<85%): Demand concerns or major maintenance season

        Args:
            df: DataFrame with refinery utilization data. Must contain
                "refinery_utilization_us" series (WPULEUS3).

        Returns:
            Signal string: "TIGHT", "NORMAL", "SOFT", or "WEAK".

        Raises:
            ValueError: If US refinery utilization series is not in the DataFrame.

        Example:
            collector = EIACollector()
            df = await collector.collect_refinery_utilization()
            signal = collector.calculate_utilization_signal(df)
            # Returns "NORMAL" if utilization is 92%
        """
        us_series_id = SERIES_MAP["refinery_utilization_us"]

        # Filter to US national data
        us_data = df[df["series_id"] == us_series_id]

        if us_data.empty:
            raise ValueError(
                f"US refinery utilization series ({us_series_id}) not found in DataFrame"
            )

        # Get the latest value
        latest = us_data.sort_values("timestamp").iloc[-1]["value"]

        # Classify based on thresholds
        if latest > UTILIZATION_THRESHOLDS["TIGHT"]:
            return "TIGHT"
        elif latest > UTILIZATION_THRESHOLDS["NORMAL"]:
            return "NORMAL"
        elif latest > UTILIZATION_THRESHOLDS["SOFT"]:
            return "SOFT"
        else:
            return "WEAK"

    async def collect_cushing(
        self,
        lookback_weeks: int = 52,
    ) -> pd.DataFrame:
        """Collect Cushing, Oklahoma crude oil inventory data.

        Cushing is the WTI futures delivery point and holds ~14% of US
        commercial tank storage capacity (~70.8 million barrels).

        Args:
            lookback_weeks: Number of weeks of historical data. Defaults to 52.

        Returns:
            DataFrame with Cushing inventory data (thousand barrels).
        """
        start_date = datetime.now(UTC) - timedelta(weeks=lookback_weeks)
        end_date = datetime.now(UTC)
        return await self.collect(
            [SERIES_MAP["cushing_inventory"]], start_date, end_date
        )

    def calculate_cushing_utilization(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Cushing storage utilization as percentage of capacity.

        Adds 'utilization_pct' column representing current inventory as
        a percentage of the 70,800 thousand barrel capacity.

        Args:
            df: DataFrame with 'value' column containing Cushing inventory
                in thousand barrels.

        Returns:
            DataFrame with added 'utilization_pct' column.

        Note:
            - Low utilization (<30%) = tight WTI market = bullish crude
            - High utilization (>70%) = oversupplied = bearish crude
            - ~50% utilization is roughly neutral
        """
        result = df.copy()
        result["utilization_pct"] = (result["value"] / CUSHING_CAPACITY_KB) * 100
        return result

    def calculate_cushing_percentile(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate 52-week rolling percentile for Cushing inventory.

        Adds 'percentile_52w' column showing where current inventory sits
        within its trailing 52-week range (0-100 scale).

        Args:
            df: DataFrame with 'value' column containing Cushing inventory.
                Must have at least 52 data points for meaningful percentiles.

        Returns:
            DataFrame with added 'percentile_52w' column.
            First 51 rows will have NaN for percentile.

        Note:
            - Low percentile (<20) = inventory near 52-week lows = bullish
            - High percentile (>80) = inventory near 52-week highs = bearish
        """
        result = df.copy()
        result["percentile_52w"] = result["value"].rolling(52).apply(
            lambda x: (
                ((x.iloc[-1] - x.min()) / (x.max() - x.min()) * 100)
                if (x.max() - x.min()) > 0
                else 50.0  # Default to neutral if no range
            ),
            raw=False,
        )
        return result


# Register collector with the registry
registry.register("eia", EIACollector)
