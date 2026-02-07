"""CFTC Commitment of Traders (COT) collector via Socrata API.

Fetches disaggregated futures positioning data from CFTC Public Reporting:
- WTI Crude Oil: Commercial vs Speculator net positions
- Gold: Safe-haven positioning
- Copper: Industrial demand proxy
- Silver: Precious metals
- Natural Gas: Energy positioning

Weekly data released Friday 15:30 ET (data from previous Tuesday).
API is public, no authentication required.

Reference: https://publicreporting.cftc.gov/stories/s/Commitments-of-Traders/r4w3-av2u/
"""

import logging
from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Key commodities for liquidity analysis
# Values from CFTC Disaggregated Futures Only dataset
# Note: cftc_commodity_code has trailing space in API, so we use LIKE queries
COMMODITY_MAP: dict[str, dict[str, str]] = {
    "WTI": {
        "code": "067",  # API returns "067 " with trailing space
        "contract": "CRUDE OIL, LIGHT SWEET-WTI",
        "market": "NYME",
        "name": "WTI Crude Oil",
    },
    "GOLD": {
        "code": "088",
        "contract": "GOLD",
        "market": "CMX",
        "name": "Gold",
    },
    "COPPER": {
        "code": "085",
        "contract": "COPPER- #1",
        "market": "CMX",
        "name": "Copper",
    },
    "SILVER": {
        "code": "084",
        "contract": "SILVER",
        "market": "CMX",
        "name": "Silver",
    },
    "NATGAS": {
        "code": "023",
        "contract": "NAT GAS NYME",
        "market": "NYME",
        "name": "Natural Gas",
    },
}

# API field names for position data
# Note: swap__positions_short_all has double underscore (API quirk)
POSITION_FIELDS: dict[str, str] = {
    "comm_long": "prod_merc_positions_long",
    "comm_short": "prod_merc_positions_short",
    "spec_long": "m_money_positions_long_all",
    "spec_short": "m_money_positions_short_all",
    "swap_long": "swap_positions_long_all",
    "swap_short": "swap__positions_short_all",
    "other_long": "other_rept_positions_long",
    "other_short": "other_rept_positions_short",
    "open_interest": "open_interest_all",
}


class CFTCCOTCollector(BaseCollector[pd.DataFrame]):
    """CFTC Commitment of Traders collector via Socrata API.

    Fetches weekly positioning data for key commodities from the CFTC
    Disaggregated Futures Only report. Provides net positions for:
    - Producer/Merchant (Commercials) - "Smart money" hedgers
    - Managed Money (Speculators) - Trend followers
    - Swap Dealers - Intermediaries

    Example:
        collector = CFTCCOTCollector()

        # Get all commodities, last 52 weeks
        df = await collector.collect()

        # Get specific commodities
        df = await collector.collect(commodities=["WTI", "GOLD"])

        # Get specific date range
        from datetime import date
        df = await collector.collect(
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 31)
        )
    """

    BASE_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
    COMMODITY_MAP = COMMODITY_MAP
    POSITION_FIELDS = POSITION_FIELDS

    def __init__(
        self,
        name: str = "cftc_cot",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize CFTC COT collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with timeout.

        Returns:
            Configured httpx.AsyncClient instance.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    def _empty_dataframe(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema.

        Returns:
            Empty DataFrame with timestamp, series_id, source, value, unit columns.
        """
        return pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

    def _safe_int(self, value: str | int | None, default: int = 0) -> int:
        """Safely convert value to int, handling None and malformed data.

        Args:
            value: Value to convert (string, int, or None).
            default: Default value if conversion fails.

        Returns:
            Integer value or default.
        """
        if value is None:
            return default
        try:
            # Handle string values that may have spaces
            if isinstance(value, str):
                value = value.strip()
            return int(value)
        except (ValueError, TypeError):
            logger.debug("Could not parse value to int: %s", value)
            return default

    async def collect(
        self,
        commodities: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        weeks: int = 52,
    ) -> pd.DataFrame:
        """Collect COT positioning data.

        Args:
            commodities: List of commodities to fetch. Options: WTI, GOLD, COPPER,
                SILVER, NATGAS. Defaults to all commodities.
            start_date: Start date for data fetch. If not provided, uses
                `weeks` parameter to calculate.
            end_date: End date for data fetch. Defaults to today.
            weeks: Number of weeks of data to fetch if start_date not provided.
                Defaults to 52 (1 year).

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit.
            Series IDs include:
            - cot_{commodity}_comm_net: Commercial net position
            - cot_{commodity}_spec_net: Speculator net position
            - cot_{commodity}_swap_net: Swap dealer net position
            - cot_{commodity}_oi: Open interest

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if commodities is None:
            commodities = list(self.COMMODITY_MAP.keys())

        # Validate commodities
        invalid = [c for c in commodities if c not in self.COMMODITY_MAP]
        if invalid:
            raise ValueError(
                f"Unknown commodities: {invalid}. Valid: {list(self.COMMODITY_MAP.keys())}"
            )

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(weeks=weeks)

        async def _fetch() -> pd.DataFrame:
            return await self._fetch_all_commodities(commodities, start_date, end_date)

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("CFTC COT fetch failed: %s", e)
            raise CollectorFetchError(f"CFTC COT data fetch failed: {e}") from e

    async def _fetch_all_commodities(
        self,
        commodities: list[str],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch data for all requested commodities.

        Args:
            commodities: List of commodity codes.
            start_date: Start date.
            end_date: End date.

        Returns:
            Combined DataFrame with all commodity data.
        """
        logger.info("Fetching CFTC COT data for: %s", commodities)

        all_data: list[pd.DataFrame] = []
        client = await self._get_client()

        for commodity in commodities:
            try:
                df = await self._fetch_commodity(
                    client, commodity, start_date, end_date
                )
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                logger.warning("Failed to fetch CFTC COT for %s: %s", commodity, e)

        if not all_data:
            logger.warning("No data returned from CFTC for commodities: %s", commodities)
            return self._empty_dataframe()

        result = pd.concat(all_data, ignore_index=True)
        result = result.sort_values(["timestamp", "series_id"]).reset_index(drop=True)

        logger.info("Fetched %d data points from CFTC COT", len(result))
        return result

    async def _fetch_commodity(
        self,
        client: httpx.AsyncClient,
        commodity: str,
        start_date: date,
        end_date: date,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Fetch COT data for a single commodity.

        Args:
            client: HTTP client.
            commodity: Commodity code (e.g., "WTI").
            start_date: Start date.
            end_date: End date.
            limit: Maximum records to fetch.

        Returns:
            DataFrame with normalized positioning data.
        """
        info = self.COMMODITY_MAP[commodity]

        # Build SoQL WHERE clause
        # Values are from our COMMODITY_MAP, not user input
        # Note: cftc_commodity_code has trailing spaces in API, use LIKE with wildcard
        where_clauses = [
            f"cftc_commodity_code like '{info['code']}%'",
            f"contract_market_name='{info['contract']}'",
        ]

        # Add date filters
        if start_date:
            where_clauses.append(
                f"report_date_as_yyyy_mm_dd >= '{start_date.isoformat()}'"
            )
        if end_date:
            where_clauses.append(
                f"report_date_as_yyyy_mm_dd <= '{end_date.isoformat()}'"
            )

        params = {
            "$where": " AND ".join(where_clauses),
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": str(min(limit, 50000)),  # API max is 50k
        }

        response = await client.get(self.BASE_URL, params=params)
        response.raise_for_status()

        data = response.json()

        if not data:
            logger.debug("No data returned for %s", commodity)
            return self._empty_dataframe()

        return self._parse_response(data, commodity)

    def _parse_response(self, data: list[dict], commodity: str) -> pd.DataFrame:
        """Parse API response to standard format.

        Args:
            data: List of API response records.
            commodity: Commodity code for series_id prefix.

        Returns:
            Normalized DataFrame with positioning data.
        """
        if not data:
            return self._empty_dataframe()

        records = []
        commodity_lower = commodity.lower()

        for row in data:
            # Parse timestamp
            try:
                timestamp = pd.to_datetime(row.get("report_date_as_yyyy_mm_dd"))
            except Exception as e:
                logger.debug("Skipping row with invalid timestamp: %s", e)
                continue

            # Extract raw positions with safe parsing
            comm_long = self._safe_int(row.get("prod_merc_positions_long"))
            comm_short = self._safe_int(row.get("prod_merc_positions_short"))
            spec_long = self._safe_int(row.get("m_money_positions_long_all"))
            spec_short = self._safe_int(row.get("m_money_positions_short_all"))
            swap_long = self._safe_int(row.get("swap_positions_long_all"))
            swap_short = self._safe_int(row.get("swap__positions_short_all"))
            oi = self._safe_int(row.get("open_interest_all"))

            # Calculate net positions
            comm_net = comm_long - comm_short
            spec_net = spec_long - spec_short
            swap_net = swap_long - swap_short

            # Add all series for this row
            records.extend(
                [
                    # Net positions
                    {
                        "timestamp": timestamp,
                        "series_id": f"cot_{commodity_lower}_comm_net",
                        "source": "cftc",
                        "value": comm_net,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": timestamp,
                        "series_id": f"cot_{commodity_lower}_spec_net",
                        "source": "cftc",
                        "value": spec_net,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": timestamp,
                        "series_id": f"cot_{commodity_lower}_swap_net",
                        "source": "cftc",
                        "value": swap_net,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": timestamp,
                        "series_id": f"cot_{commodity_lower}_oi",
                        "source": "cftc",
                        "value": oi,
                        "unit": "contracts",
                    },
                    # Raw long/short positions (for ratio calculations)
                    {
                        "timestamp": timestamp,
                        "series_id": f"cot_{commodity_lower}_comm_long",
                        "source": "cftc",
                        "value": comm_long,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": timestamp,
                        "series_id": f"cot_{commodity_lower}_comm_short",
                        "source": "cftc",
                        "value": comm_short,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": timestamp,
                        "series_id": f"cot_{commodity_lower}_spec_long",
                        "source": "cftc",
                        "value": spec_long,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": timestamp,
                        "series_id": f"cot_{commodity_lower}_spec_short",
                        "source": "cftc",
                        "value": spec_short,
                        "unit": "contracts",
                    },
                ]
            )

        return pd.DataFrame(records)

    async def collect_single(
        self,
        commodity: str,
        weeks: int = 52,
    ) -> pd.DataFrame:
        """Convenience method to collect a single commodity.

        Args:
            commodity: Commodity code (WTI, GOLD, COPPER, SILVER, NATGAS).
            weeks: Number of weeks of data.

        Returns:
            DataFrame with positioning data for the commodity.
        """
        return await self.collect(commodities=[commodity], weeks=weeks)

    def get_latest(self, df: pd.DataFrame, commodity: str) -> dict[str, int]:
        """Get latest positioning values for a commodity.

        Args:
            df: DataFrame from collect().
            commodity: Commodity code.

        Returns:
            Dict with comm_net, spec_net, swap_net, oi values.
        """
        commodity_lower = commodity.lower()
        latest_date = df["timestamp"].max()
        latest = df[df["timestamp"] == latest_date]

        result = {}
        for suffix in ["comm_net", "spec_net", "swap_net", "oi"]:
            series_id = f"cot_{commodity_lower}_{suffix}"
            row = latest[latest["series_id"] == series_id]
            result[suffix] = int(row["value"].iloc[0]) if not row.empty else 0

        return result


# Register collector with the registry
registry.register("cftc_cot", CFTCCOTCollector)
