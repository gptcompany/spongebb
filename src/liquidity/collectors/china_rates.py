"""China interbank rates collector using akshare.

Provides SHIBOR and DR007 as daily proxies for PBoC policy stance.
These rates help with nowcasting when official PBoC balance sheet data lags by ~1 month.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Tenor mapping for SHIBOR
SHIBOR_TENORS = {
    "O/N": "OVERNIGHT",
    "1W": "1_WEEK",
    "2W": "2_WEEKS",
    "1M": "1_MONTH",
    "3M": "3_MONTHS",
    "6M": "6_MONTHS",
    "9M": "9_MONTHS",
    "1Y": "1_YEAR",
}


class ChinaRatesCollector(BaseCollector[pd.DataFrame]):
    """Collector for China interbank rates using akshare.

    Provides:
    - SHIBOR (Shanghai Interbank Offered Rate) - multiple tenors
    - DR007 (7-day repo rate) - PBoC's de facto policy target

    These rates serve as high-frequency proxies for PBoC policy stance,
    useful for nowcasting when official balance sheet data lags by ~1 month.

    Requires: pip install akshare>=1.18.0
    """

    # Cached baselines for guaranteed fallback (Jan 2026 values)
    SHIBOR_1W_BASELINE = 1.65  # percent
    DR007_BASELINE = 1.70  # percent
    BASELINE_DATE = "2026-02-01"

    def __init__(
        self,
        name: str = "china_rates",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize China rates collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()

    async def collect_shibor(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect SHIBOR rates for all tenors.

        Args:
            start_date: Start date (default: 90 days ago)
            end_date: End date (default: today)

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now(UTC)

        # Ensure start_date and end_date are timezone-naive for comparison
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_shibor_sync, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch, breaker_name="china_shibor")
        except Exception as e:
            logger.error("SHIBOR fetch failed: %s", e)
            raise CollectorFetchError(f"SHIBOR fetch failed: {e}") from e

    def _fetch_shibor_sync(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Synchronous SHIBOR fetch using akshare."""
        try:
            import akshare as ak
        except ImportError as e:
            raise CollectorFetchError(
                "akshare not installed. Run: pip install akshare>=1.18.0"
            ) from e

        logger.info("Fetching SHIBOR rates via akshare")

        # Get SHIBOR all tenors
        try:
            df_raw = ak.macro_china_shibor_all()
        except Exception as e:
            logger.error("akshare macro_china_shibor_all failed: %s", e)
            raise CollectorFetchError(f"SHIBOR API error: {e}") from e

        if df_raw is None or df_raw.empty:
            logger.warning("No SHIBOR data returned")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Parse the data
        # Columns: 日期, O/N-定价, O/N-涨跌幅, 1W-定价, 1W-涨跌幅, ...
        rows = []

        for _, row in df_raw.iterrows():
            try:
                date = pd.to_datetime(row["日期"])
            except (KeyError, ValueError):
                continue

            # Filter by date range (compare naive datetimes)
            if date < pd.Timestamp(start_date) or date > pd.Timestamp(end_date):
                continue

            # Extract each tenor's rate
            for tenor, tenor_name in SHIBOR_TENORS.items():
                col_name = f"{tenor}-定价"
                if col_name in row.index and pd.notna(row[col_name]):
                    try:
                        value = float(row[col_name])
                        rows.append({
                            "timestamp": date,
                            "series_id": f"SHIBOR_{tenor_name}",
                            "source": "akshare",
                            "value": value,
                            "unit": "percent",
                        })
                    except (ValueError, TypeError):
                        continue

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info("Fetched %d SHIBOR records", len(df))
        return df

    async def collect_dr007(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect DR007 (7-day repo rate).

        DR007 is the PBoC's de-facto policy rate target.
        It reflects interbank funding conditions more accurately than SHIBOR.

        Fallback: If DR007 not available, use SHIBOR 1W as proxy.

        Args:
            start_date: Start date (default: 90 days ago)
            end_date: End date (default: today)

        Returns:
            DataFrame with DR007 rate data.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now(UTC)

        # Ensure start_date and end_date are timezone-naive for comparison
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_dr007_sync, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch, breaker_name="china_dr007")
        except Exception as e:
            logger.error("DR007 fetch failed: %s", e)
            raise CollectorFetchError(f"DR007 fetch failed: {e}") from e

    def _fetch_dr007_sync(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Synchronous DR007 fetch using akshare."""
        try:
            import akshare as ak
        except ImportError as e:
            raise CollectorFetchError(
                "akshare not installed. Run: pip install akshare>=1.18.0"
            ) from e

        logger.info("Fetching DR007 rates via akshare")

        # Try rate_interbank function first
        try:
            df_raw = ak.rate_interbank(
                market="中国银行间同业拆借市场",
                symbol="DR007",
                indicator="利率"
            )

            if df_raw is not None and not df_raw.empty:
                return self._parse_dr007_data(df_raw, start_date, end_date)
        except Exception as e:
            logger.warning("ak.rate_interbank failed: %s, trying SHIBOR fallback", e)

        # Fallback: use SHIBOR 1W as DR007 proxy
        logger.info("Using SHIBOR 1W as DR007 proxy")
        return self._dr007_from_shibor(start_date, end_date)

    def _parse_dr007_data(
        self,
        df_raw: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Parse DR007 data from akshare response.

        Args:
            df_raw: Raw DataFrame from akshare.
            start_date: Start date filter.
            end_date: End date filter.

        Returns:
            Normalized DataFrame.
        """
        rows = []

        # Try to identify date and value columns
        date_col = None
        value_col = None

        for col in df_raw.columns:
            col_lower = str(col).lower()
            if "日期" in col or "date" in col_lower:
                date_col = col
            elif "利率" in col or "rate" in col_lower or "dr007" in col_lower:
                value_col = col

        # If we couldn't find columns, try positional
        if date_col is None and len(df_raw.columns) >= 1:
            date_col = df_raw.columns[0]
        if value_col is None and len(df_raw.columns) >= 2:
            value_col = df_raw.columns[1]

        if date_col is None or value_col is None:
            logger.warning("Could not identify DR007 columns in: %s", df_raw.columns.tolist())
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        for _, row in df_raw.iterrows():
            try:
                date = pd.to_datetime(row[date_col])
                value = float(row[value_col])
            except (ValueError, TypeError, KeyError):
                continue

            # Filter by date range
            if date < pd.Timestamp(start_date) or date > pd.Timestamp(end_date):
                continue

            rows.append({
                "timestamp": date,
                "series_id": "DR007",
                "source": "akshare",
                "value": value,
                "unit": "percent",
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info("Fetched %d DR007 records", len(df))
        return df

    def _dr007_from_shibor(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Extract DR007 proxy from SHIBOR 1W rate.

        SHIBOR 1W is a reasonable proxy for DR007 as both represent
        1-week interbank funding costs.

        Args:
            start_date: Start date filter.
            end_date: End date filter.

        Returns:
            DataFrame with DR007_PROXY series.
        """
        shibor_df = self._fetch_shibor_sync(start_date, end_date)

        if shibor_df.empty:
            logger.warning("SHIBOR data empty, cannot create DR007 proxy")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Filter for 1W rate
        df = shibor_df[shibor_df["series_id"] == "SHIBOR_1_WEEK"].copy()

        if df.empty:
            logger.warning("SHIBOR 1W not found, cannot create DR007 proxy")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        df["series_id"] = "DR007_PROXY"
        df["source"] = "akshare_shibor_proxy"

        logger.info("Created %d DR007_PROXY records from SHIBOR 1W", len(df))
        return df.reset_index(drop=True)

    async def collect(
        self,
        data_type: str = "shibor",
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Generic collect method.

        Args:
            data_type: "shibor" or "dr007"
            **kwargs: Passed to specific collector

        Returns:
            DataFrame with rate data.

        Raises:
            ValueError: If data_type is unknown.
        """
        if data_type == "shibor":
            return await self.collect_shibor(**kwargs)
        elif data_type == "dr007":
            return await self.collect_dr007(**kwargs)
        else:
            raise ValueError(f"Unknown data_type: {data_type}. Use 'shibor' or 'dr007'.")

    async def collect_all(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect all China rate data (SHIBOR + DR007).

        Args:
            start_date: Start date filter.
            end_date: End date filter.

        Returns:
            Combined DataFrame with all rate series.
        """
        shibor_task = self.collect_shibor(start_date, end_date)
        dr007_task = self.collect_dr007(start_date, end_date)

        shibor_df, dr007_df = await asyncio.gather(
            shibor_task, dr007_task, return_exceptions=True
        )

        frames = []

        if isinstance(shibor_df, pd.DataFrame) and not shibor_df.empty:
            frames.append(shibor_df)
        elif isinstance(shibor_df, Exception):
            logger.warning("SHIBOR collection failed: %s", shibor_df)

        if isinstance(dr007_df, pd.DataFrame) and not dr007_df.empty:
            frames.append(dr007_df)
        elif isinstance(dr007_df, Exception):
            logger.warning("DR007 collection failed: %s", dr007_df)

        if not frames:
            logger.warning("All China rate collections failed, returning empty DataFrame")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        return pd.concat(frames, ignore_index=True)

    def get_cached_baseline(self) -> pd.DataFrame:
        """Get cached baseline values (GUARANTEED data).

        Returns:
            DataFrame with baseline SHIBOR 1W and DR007 values.
        """
        baseline_date = pd.to_datetime(self.BASELINE_DATE)
        return pd.DataFrame([
            {
                "timestamp": baseline_date,
                "series_id": "SHIBOR_1_WEEK",
                "source": "cached_baseline",
                "value": self.SHIBOR_1W_BASELINE,
                "unit": "percent",
                "stale": True,
            },
            {
                "timestamp": baseline_date,
                "series_id": "DR007_PROXY",
                "source": "cached_baseline",
                "value": self.DR007_BASELINE,
                "unit": "percent",
                "stale": True,
            },
        ])


# Register collector
registry.register("china_rates", ChinaRatesCollector)
