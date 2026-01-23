"""Stress indicator collector for funding market stress signals.

Tracks funding market stress through key spreads and ratios:
- SOFR-OIS Spread: Funding premium over policy rate
- SOFR Distribution Width: Dispersion in overnight funding costs
- Repo Stress Ratio: Reverse repo as % of Fed balance sheet
- CP-Treasury Spread: Commercial paper funding stress

These indicators are critical for detecting funding stress before it impacts markets.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import pandas as pd
from openbb import obb

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# FRED series for stress indicators
STRESS_SERIES_MAP: dict[str, str] = {
    "sofr": "SOFR",  # Secured Overnight Financing Rate (percent, daily)
    "effr": "EFFR",  # Effective Federal Funds Rate (proxy for OIS, percent, daily)
    "sofr_1pct": "SOFR1",  # SOFR 1st percentile (percent, daily)
    "sofr_99pct": "SOFR99",  # SOFR 99th percentile (percent, daily)
    "rrp_daily": "RRPONTSYD",  # Fed reverse repo operations (billions, daily)
    "fed_assets": "WALCL",  # Fed total assets (millions, weekly)
    "cp_3m": "DCPF3M",  # 3-month financial commercial paper rate (percent, daily)
    "tbill_3m": "DTB3",  # 3-month Treasury bill rate (percent, daily)
}

# Stress thresholds for regime classification
STRESS_THRESHOLDS = {
    "sofr_ois": {"green": 10, "yellow": 25},  # basis points
    "sofr_width": {"green": 20, "yellow": 50},  # basis points
    "repo_stress": {"green": 1, "yellow": 3},  # percent
    "cp_spread": {"green": 40, "yellow": 100},  # basis points
}

RegimeType = Literal["GREEN", "YELLOW", "RED"]


class StressIndicatorCollector(BaseCollector[pd.DataFrame]):
    """Collector for funding market stress indicators.

    Calculates four key stress metrics:
    1. SOFR-OIS Spread: (SOFR - EFFR) * 100 in bps (Normal: 0-10, Stress: >25)
    2. SOFR Distribution Width: (SOFR99 - SOFR1) in bps (Normal: <20, Crisis: >50)
    3. Repo Stress Ratio: (RRPONTSYD / WALCL) * 100 (Normal: <1%, Elevated: >3%)
    4. CP-Treasury Spread: (DCPF3M - DTB3) * 100 in bps (Normal: 20-40, Stress: >100)

    Example:
        collector = StressIndicatorCollector()
        df = await collector.collect()
        regime = collector.get_current_regime(df)
    """

    SERIES_MAP = STRESS_SERIES_MAP
    THRESHOLDS = STRESS_THRESHOLDS

    def __init__(
        self,
        name: str = "stress",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize stress indicator collector.

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
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect all stress indicators.

        Args:
            start_date: Start date for data fetch. Defaults to 60 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        return await self.collect_all(start_date, end_date)

    async def collect_all(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect all stress indicators combined.

        Args:
            start_date: Start date for data fetch. Defaults to 60 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with all stress indicators.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=60)
        if end_date is None:
            end_date = datetime.now(UTC)

        # Collect all indicators in parallel
        results = await asyncio.gather(
            self.collect_sofr_ois_spread(start_date, end_date),
            self.collect_sofr_distribution(start_date, end_date),
            self.collect_repo_stress(start_date, end_date),
            self.collect_cp_spread(start_date, end_date),
            return_exceptions=True,
        )

        dfs = []
        for i, result in enumerate(results):
            indicator_names = [
                "sofr_ois_spread",
                "sofr_distribution",
                "repo_stress",
                "cp_spread",
            ]
            if isinstance(result, Exception):
                logger.warning("Failed to collect %s: %s", indicator_names[i], result)
            elif isinstance(result, pd.DataFrame) and not result.empty:
                dfs.append(result)

        if not dfs:
            logger.warning("No stress indicators collected successfully")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.sort_values("timestamp").reset_index(drop=True)

        logger.info("Collected %d stress indicator data points", len(combined))
        return combined

    async def collect_sofr_ois_spread(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect SOFR-OIS spread (SOFR - EFFR).

        Normal: 0-10 bps, Stress: >25 bps

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with SOFR-OIS spread in basis points.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=60)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_sofr_ois_spread_sync, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("SOFR-OIS spread fetch failed: %s", e)
            raise CollectorFetchError(f"SOFR-OIS spread fetch failed: {e}") from e

    def _fetch_sofr_ois_spread_sync(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Synchronous fetch for SOFR-OIS spread."""
        logger.info("Fetching SOFR and EFFR for spread calculation")

        result = obb.economy.fred_series(
            symbol="SOFR,EFFR",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            provider="fred",
        )

        df = result.to_df().reset_index()

        if df.empty or "SOFR" not in df.columns or "EFFR" not in df.columns:
            logger.warning("Missing SOFR or EFFR data for spread calculation")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Find date column
        date_col = self._find_date_column(df)

        # Forward fill to handle missing values before calculation
        df["SOFR"] = df["SOFR"].ffill()
        df["EFFR"] = df["EFFR"].ffill()

        # Calculate spread in basis points: (SOFR - EFFR) * 100
        df["spread"] = (df["SOFR"] - df["EFFR"]) * 100

        result_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(df[date_col]),
                "series_id": "stress_sofr_ois",
                "source": "calculated",
                "value": df["spread"],
                "unit": "basis_points",
            }
        )

        result_df = result_df.dropna(subset=["value"]).reset_index(drop=True)
        logger.info("Calculated %d SOFR-OIS spread points", len(result_df))
        return result_df

    async def collect_sofr_distribution(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect SOFR distribution width (99th - 1st percentile).

        Normal: <20 bps, Crisis: >50 bps

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with SOFR distribution width in basis points.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=60)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_sofr_distribution_sync, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("SOFR distribution fetch failed: %s", e)
            raise CollectorFetchError(f"SOFR distribution fetch failed: {e}") from e

    def _fetch_sofr_distribution_sync(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Synchronous fetch for SOFR distribution width."""
        logger.info("Fetching SOFR percentiles for distribution width")

        result = obb.economy.fred_series(
            symbol="SOFR1,SOFR99",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            provider="fred",
        )

        df = result.to_df().reset_index()

        if df.empty or "SOFR1" not in df.columns or "SOFR99" not in df.columns:
            logger.warning("Missing SOFR percentile data for distribution calculation")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        date_col = self._find_date_column(df)

        # Forward fill to handle missing values
        df["SOFR1"] = df["SOFR1"].ffill()
        df["SOFR99"] = df["SOFR99"].ffill()

        # Calculate width in basis points: (SOFR99 - SOFR1) * 100
        df["width"] = (df["SOFR99"] - df["SOFR1"]) * 100

        result_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(df[date_col]),
                "series_id": "stress_sofr_width",
                "source": "calculated",
                "value": df["width"],
                "unit": "basis_points",
            }
        )

        result_df = result_df.dropna(subset=["value"]).reset_index(drop=True)
        logger.info("Calculated %d SOFR distribution width points", len(result_df))
        return result_df

    async def collect_repo_stress(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect repo stress ratio (RRP / Fed Assets).

        Normal: <1%, Elevated: >3%

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with repo stress ratio in percent.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=60)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_repo_stress_sync, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("Repo stress fetch failed: %s", e)
            raise CollectorFetchError(f"Repo stress fetch failed: {e}") from e

    def _fetch_repo_stress_sync(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Synchronous fetch for repo stress ratio."""
        logger.info("Fetching RRP and WALCL for repo stress ratio")

        result = obb.economy.fred_series(
            symbol="RRPONTSYD,WALCL",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            provider="fred",
        )

        df = result.to_df().reset_index()

        if df.empty or "RRPONTSYD" not in df.columns or "WALCL" not in df.columns:
            logger.warning("Missing RRP or WALCL data for repo stress calculation")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        date_col = self._find_date_column(df)

        # Forward fill to handle different update frequencies
        # WALCL is weekly, RRPONTSYD is daily
        df["RRPONTSYD"] = df["RRPONTSYD"].ffill()
        df["WALCL"] = df["WALCL"].ffill()

        # Calculate ratio: (RRP billions * 1000 / WALCL millions) * 100
        # RRP is in billions, WALCL is in millions, so multiply RRP by 1000
        df["ratio"] = (df["RRPONTSYD"] * 1000 / df["WALCL"]) * 100

        result_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(df[date_col]),
                "series_id": "stress_repo",
                "source": "calculated",
                "value": df["ratio"],
                "unit": "percent",
            }
        )

        result_df = result_df.dropna(subset=["value"]).reset_index(drop=True)
        logger.info("Calculated %d repo stress ratio points", len(result_df))
        return result_df

    async def collect_cp_spread(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect CP-Treasury spread (3M CP - 3M T-Bill).

        Normal: 20-40 bps, Stress: >100 bps

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with CP-Treasury spread in basis points.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=60)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_cp_spread_sync, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("CP spread fetch failed: %s", e)
            raise CollectorFetchError(f"CP spread fetch failed: {e}") from e

    def _fetch_cp_spread_sync(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Synchronous fetch for CP-Treasury spread."""
        logger.info("Fetching CP and T-Bill rates for spread calculation")

        result = obb.economy.fred_series(
            symbol="DCPF3M,DTB3",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            provider="fred",
        )

        df = result.to_df().reset_index()

        if df.empty or "DCPF3M" not in df.columns or "DTB3" not in df.columns:
            logger.warning("Missing CP or T-Bill data for spread calculation")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        date_col = self._find_date_column(df)

        # Forward fill to handle missing values
        df["DCPF3M"] = df["DCPF3M"].ffill()
        df["DTB3"] = df["DTB3"].ffill()

        # Calculate spread in basis points: (CP - T-Bill) * 100
        df["spread"] = (df["DCPF3M"] - df["DTB3"]) * 100

        result_df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(df[date_col]),
                "series_id": "stress_cp",
                "source": "calculated",
                "value": df["spread"],
                "unit": "basis_points",
            }
        )

        result_df = result_df.dropna(subset=["value"]).reset_index(drop=True)
        logger.info("Calculated %d CP-Treasury spread points", len(result_df))
        return result_df

    def get_current_regime(self, df: pd.DataFrame | None = None) -> RegimeType:
        """Determine the current stress regime based on latest indicators.

        Regime logic:
        - RED: Any indicator exceeds yellow threshold
        - YELLOW: Any indicator exceeds green threshold
        - GREEN: All indicators within green thresholds

        Args:
            df: DataFrame with stress indicators. If None, returns "GREEN".

        Returns:
            "GREEN", "YELLOW", or "RED"
        """
        if df is None or df.empty:
            logger.warning("No data provided for regime classification")
            return "GREEN"

        # Get latest value for each indicator
        latest_values: dict[str, float] = {}
        for series_id in [
            "stress_sofr_ois",
            "stress_sofr_width",
            "stress_repo",
            "stress_cp",
        ]:
            series_df = df[df["series_id"] == series_id]
            if not series_df.empty:
                latest_values[series_id] = float(
                    series_df.sort_values("timestamp").iloc[-1]["value"]
                )

        if not latest_values:
            logger.warning("No valid stress indicator values for regime classification")
            return "GREEN"

        # Map series_id to threshold keys
        threshold_map = {
            "stress_sofr_ois": "sofr_ois",
            "stress_sofr_width": "sofr_width",
            "stress_repo": "repo_stress",
            "stress_cp": "cp_spread",
        }

        # Check thresholds
        is_yellow = False
        is_red = False

        for series_id, value in latest_values.items():
            threshold_key = threshold_map.get(series_id)
            if threshold_key is None:
                continue

            thresholds = self.THRESHOLDS.get(threshold_key)
            if thresholds is None:
                continue

            if value > thresholds["yellow"]:
                is_red = True
                logger.info(
                    "RED regime: %s = %.2f > %.2f (yellow threshold)",
                    series_id,
                    value,
                    thresholds["yellow"],
                )
            elif value > thresholds["green"]:
                is_yellow = True
                logger.debug(
                    "YELLOW indicator: %s = %.2f > %.2f (green threshold)",
                    series_id,
                    value,
                    thresholds["green"],
                )

        if is_red:
            return "RED"
        elif is_yellow:
            return "YELLOW"
        else:
            return "GREEN"

    @staticmethod
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


# Register collector with the registry
registry.register("stress", StressIndicatorCollector)
