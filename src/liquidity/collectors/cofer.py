"""COFER (Currency Composition of Official Foreign Exchange Reserves) collector.

Collects IMF COFER data via DBnomics API for tracking global reserve currency allocation.
Essential for monitoring de-dollarization trends and USD reserve dominance.

Data source: IMF COFER dataset mirrored on DBnomics
API: https://api.db.nomics.world/v22/series/IMF/COFER
Update frequency: Quarterly (with ~3 month lag)

Key metrics:
- Reserve allocation by currency (USD, EUR, CNY, JPY, GBP, Other)
- Currency share percentages
- De-dollarization rate (YoY change in USD share)
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

# DBnomics API base URL for IMF COFER dataset
DBNOMICS_BASE_URL = "https://api.db.nomics.world/v22/series/IMF/COFER"

# COFER series codes for allocated reserves by currency (all in USD millions)
# W00 = World (all countries, excluding IO)
# Quarterly data from IMF COFER dataset via DBnomics
COFER_SERIES: dict[str, str] = {
    "usd": "Q.W00.RAXGFXARUSD_USD",  # USD reserves
    "eur": "Q.W00.RAXGFXAREURO_USD",  # EUR reserves (Euro)
    "cny": "Q.W00.RAXGFXARCNY_USD",  # CNY reserves (Chinese Renminbi)
    "jpy": "Q.W00.RAXGFXARJPY_USD",  # JPY reserves (Japanese Yen)
    "gbp": "Q.W00.RAXGFXARGBP_USD",  # GBP reserves (Pounds Sterling)
    "other": "Q.W00.RAXGFXAROC_USD",  # Other currencies
}


class COFERCollector(BaseCollector[pd.DataFrame]):
    """COFER collector for IMF reserve currency data via DBnomics.

    Tracks global foreign exchange reserve composition by currency.
    Key indicator for monitoring de-dollarization and USD dominance.

    DBnomics provides free, no-auth API access to IMF COFER data.
    """

    def __init__(
        self,
        name: str = "cofer",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize COFER collector.

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
        """Collect COFER currency share data (default entry point).

        Args:
            start_date: Start date for data fetch (filters after fetch).
            end_date: End date for data fetch (filters after fetch).

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
            Values are percentage shares of total allocated reserves.
        """
        return await self.collect_currency_shares(start_date, end_date)

    async def collect_reserves_by_currency(
        self,
        currencies: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect reserves in USD millions per currency.

        Args:
            currencies: List of currency codes to fetch. Default: all.
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
            Values are in millions of USD.
        """
        currencies = currencies or list(COFER_SERIES.keys())

        all_data: list[pd.DataFrame] = []

        for currency in currencies:
            if currency not in COFER_SERIES:
                logger.warning("Unknown COFER currency: %s, skipping", currency)
                continue

            series_code = COFER_SERIES[currency]
            try:
                df = await self._fetch_series(series_code)
                df["series_id"] = f"cofer_{currency}"
                df["unit"] = "millions_usd"
                all_data.append(df)
            except Exception as e:
                logger.warning(
                    "Failed to fetch COFER series %s (%s): %s",
                    currency,
                    series_code,
                    e,
                )

        if not all_data:
            raise CollectorFetchError("Failed to fetch any COFER currency series")

        result = pd.concat(all_data, ignore_index=True)
        result = self._filter_by_date(result, start_date, end_date)

        logger.info(
            "Fetched COFER reserves for %d currencies, %d total observations",
            len(currencies),
            len(result),
        )
        return result

    async def collect_currency_shares(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect percentage share of each currency in total reserves.

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with currency shares as percentages (sum to ~100%).
        """
        # Fetch all currency reserves
        reserves_df = await self.collect_reserves_by_currency(
            start_date=start_date, end_date=end_date
        )

        if reserves_df.empty:
            return reserves_df

        # Pivot to calculate shares
        pivot = reserves_df.pivot_table(
            index="timestamp",
            columns="series_id",
            values="value",
            aggfunc="first",
        )

        # Calculate total for each timestamp
        total = pivot.sum(axis=1)

        # Calculate shares as percentages
        shares_data: list[dict[str, Any]] = []
        for idx in range(len(pivot)):
            timestamp = pivot.index[idx]
            row = pivot.iloc[idx]
            row_total = float(total.iloc[idx])
            if row_total > 0:
                for col in pivot.columns:
                    if pd.notna(row[col]):
                        share = (float(row[col]) / row_total) * 100
                        # Extract currency from series_id (cofer_usd -> usd)
                        currency = str(col).replace("cofer_", "")
                        shares_data.append(
                            {
                                "timestamp": timestamp,
                                "series_id": f"cofer_share_{currency}",
                                "source": "dbnomics_imf",
                                "value": share,
                                "unit": "percent",
                            }
                        )

        result = pd.DataFrame(shares_data)
        result = result.sort_values(["timestamp", "series_id"]).reset_index(drop=True)

        logger.info("Calculated COFER currency shares: %d observations", len(result))
        return result

    async def collect_usd_share(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect USD share trend over time.

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with USD share percentages over time.
        """
        shares_df = await self.collect_currency_shares(start_date, end_date)

        if shares_df.empty:
            return shares_df

        # Filter to USD share only
        usd_share = shares_df[shares_df["series_id"] == "cofer_share_usd"].reset_index(
            drop=True
        )

        logger.info("Fetched USD share trend: %d observations", len(usd_share))
        return usd_share

    async def collect_total_reserves(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect total allocated reserves over time.

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with total allocated reserves in millions USD.
        """
        reserves_df = await self.collect_reserves_by_currency(
            start_date=start_date, end_date=end_date
        )

        if reserves_df.empty:
            return reserves_df

        # Group by timestamp and sum all currencies
        total_df = reserves_df.groupby("timestamp")["value"].sum().reset_index()
        total_df["series_id"] = "cofer_total"
        total_df["source"] = "dbnomics_imf"
        total_df["unit"] = "millions_usd"

        result = total_df[["timestamp", "series_id", "source", "value", "unit"]]
        result = result.sort_values("timestamp").reset_index(drop=True)

        logger.info("Calculated total reserves: %d observations", len(result))
        return result

    async def calculate_dedollarization_rate(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate YoY change in USD share (de-dollarization rate).

        Positive values indicate increasing USD share (dollarization).
        Negative values indicate decreasing USD share (de-dollarization).

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with YoY USD share change in percentage points.
        """
        usd_share = await self.collect_usd_share(start_date, end_date)

        if len(usd_share) < 5:  # Need at least 5 quarters for YoY
            logger.warning(
                "Insufficient data for YoY calculation: %d observations",
                len(usd_share),
            )
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Sort by timestamp
        usd_share = usd_share.sort_values("timestamp").reset_index(drop=True)

        # Calculate YoY change (4 quarters = 1 year)
        usd_share["yoy_change"] = usd_share["value"].diff(periods=4)

        # Filter to rows with valid YoY
        yoy_data = usd_share.dropna(subset=["yoy_change"]).copy()

        result = pd.DataFrame(
            {
                "timestamp": yoy_data["timestamp"],
                "series_id": "cofer_usd_yoy_change",
                "source": "dbnomics_imf",
                "value": yoy_data["yoy_change"],
                "unit": "percentage_points",
            }
        )

        result = result.reset_index(drop=True)
        logger.info("Calculated de-dollarization rate: %d observations", len(result))
        return result

    async def _fetch_series(self, series_code: str) -> pd.DataFrame:
        """Fetch a single series from DBnomics API.

        Args:
            series_code: The COFER series code (e.g., "Q.W00.RAXGFXARUSD_USD").

        Returns:
            DataFrame with columns: timestamp, source, value

        Raises:
            CollectorFetchError: If API request fails or returns no data.
        """
        # observations=1 is required to get actual data values
        url = f"{DBNOMICS_BASE_URL}/{series_code}?observations=1"

        async def _do_fetch() -> pd.DataFrame:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()

                # Navigate to series data
                series_docs = data.get("series", {}).get("docs", [])

                if not series_docs:
                    raise CollectorFetchError(
                        f"DBnomics API returned no data for series {series_code}"
                    )

                series_data = series_docs[0]

                # Extract periods and values
                periods = series_data.get("period_start_day", [])
                values = series_data.get("value", [])

                if not periods or not values:
                    raise CollectorFetchError(
                        f"DBnomics series {series_code} has no observations"
                    )

                if len(periods) != len(values):
                    raise CollectorFetchError(
                        f"DBnomics series {series_code} has mismatched periods/values"
                    )

                # Build DataFrame
                records = []
                for period_str, value in zip(periods, values):
                    if value is not None and not pd.isna(value):
                        records.append(
                            {
                                "timestamp": pd.to_datetime(period_str),
                                "source": "dbnomics_imf",
                                "value": float(value),
                            }
                        )

                if not records:
                    raise CollectorFetchError(
                        f"No valid observations in series {series_code}"
                    )

                df = pd.DataFrame(records)
                df = df.sort_values("timestamp").reset_index(drop=True)

                return df

        return await self.fetch_with_retry(
            _do_fetch, breaker_name=f"cofer_{series_code}"
        )

    def _filter_by_date(
        self,
        df: pd.DataFrame,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> pd.DataFrame:
        """Filter DataFrame by date range.

        Args:
            df: Input DataFrame with timestamp column.
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            Filtered DataFrame.
        """
        if df.empty:
            return df

        result = df.copy()

        if start_date:
            result = result[result["timestamp"] >= pd.to_datetime(start_date)]

        if end_date:
            result = result[result["timestamp"] <= pd.to_datetime(end_date)]

        return result.reset_index(drop=True)


# Register collector
registry.register("cofer", COFERCollector)
