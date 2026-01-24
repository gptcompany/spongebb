"""Credit market collector for lending standards and funding rates.

Tracks credit demand-side indicators that complement central bank balance sheet data:
- SLOOS: Fed Senior Loan Officer Opinion Survey (quarterly, leading indicator)
- CP Rates: Commercial paper rates (daily, funding stress)

These indicators help assess credit conditions in the real economy and can provide
early warning signals of economic stress.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.fred import FredCollector
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# SLOOS series for lending standards
SLOOS_SERIES: list[str] = [
    "DRTSCILM",  # C&I loans to large/middle firms (main indicator)
    "DRTSCIS",  # C&I loans to small firms
    "DRTSROM",  # Commercial real estate loans
    "DRSDCILM",  # Demand for C&I from large firms
]

# Commercial paper rate series
CP_SERIES: list[str] = [
    "DCPF3M",  # 3-month Financial CP (already used in stress collector)
    "DCPN3M",  # 3-month Nonfinancial CP
]

# Thresholds for lending standards regime classification
LENDING_THRESHOLDS = {
    "tightening": 20.0,  # Net % > 20% = tightening
    "easing": -10.0,  # Net % < -10% = easing
}

LendingRegimeType = Literal["TIGHTENING", "NEUTRAL", "EASING"]


class CreditCollector(BaseCollector[pd.DataFrame]):
    """Credit market collector for lending standards and funding rates.

    Tracks credit demand-side indicators:
    - SLOOS: Fed Senior Loan Officer Opinion Survey (quarterly, leading indicator)
    - CP Rates: Commercial paper rates (daily, funding stress)

    SLOOS Interpretation:
    - Positive values = Net tightening (more banks tightening than easing)
    - Negative values = Net easing
    - Range: Typically -30% to +70%
    - Crisis peaks: 70%+ (2008 GFC, 2020 COVID)
    - Expansion troughs: -20% to -30%
    - Lead time: Tightening precedes recessions by 6-12 months

    Example:
        collector = CreditCollector()
        sloos_df = await collector.collect_sloos()
        regime = collector.get_lending_standards_regime(sloos_df)
    """

    SLOOS_SERIES = SLOOS_SERIES
    CP_SERIES = CP_SERIES
    THRESHOLDS = LENDING_THRESHOLDS

    def __init__(
        self,
        name: str = "credit",
        settings: Settings | None = None,
        fred_collector: FredCollector | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize credit market collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            fred_collector: Optional FredCollector instance for dependency injection.
                If not provided, a new one will be created.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()
        self._fred = fred_collector or FredCollector(
            name="credit_fred", settings=self._settings
        )

    async def collect(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect all credit market data (SLOOS and CP rates).

        Args:
            start_date: Start date for data fetch. Defaults to 1 year ago for SLOOS.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now(UTC)

        # Collect both SLOOS and CP rates in parallel
        results = await asyncio.gather(
            self.collect_sloos(start_date, end_date),
            self.collect_cp_rates(start_date, end_date),
            return_exceptions=True,
        )

        dfs = []
        for i, result in enumerate(results):
            indicator_names = ["sloos", "cp_rates"]
            if isinstance(result, Exception):
                logger.warning("Failed to collect %s: %s", indicator_names[i], result)
            elif isinstance(result, pd.DataFrame) and not result.empty:
                dfs.append(result)

        if not dfs:
            logger.warning("No credit market data collected successfully")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        combined = pd.concat(dfs, ignore_index=True)
        combined = combined.sort_values("timestamp").reset_index(drop=True)

        logger.info("Collected %d credit market data points", len(combined))
        return combined

    async def collect_sloos(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect SLOOS (Senior Loan Officer Opinion Survey) data.

        SLOOS is a quarterly survey of bank lending standards. Positive values
        indicate net tightening (more banks tightening than easing), negative
        values indicate net easing.

        Series collected:
        - DRTSCILM: C&I loans to large/middle firms (primary indicator)
        - DRTSCIS: C&I loans to small firms
        - DRTSROM: Commercial real estate loans
        - DRSDCILM: Demand for C&I from large firms

        Args:
            start_date: Start date for data fetch. Defaults to 1 year ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with SLOOS data in standard format.

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fred.collect(
                symbols=self.SLOOS_SERIES,
                start_date=start_date,
                end_date=end_date,
            )

        try:
            df = await self.fetch_with_retry(_fetch, breaker_name="credit_sloos")
            logger.info("Collected %d SLOOS data points", len(df))
            return df
        except Exception as e:
            logger.error("SLOOS fetch failed: %s", e)
            raise CollectorFetchError(f"SLOOS data fetch failed: {e}") from e

    async def collect_cp_rates(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect commercial paper rate data.

        Commercial paper rates reflect short-term corporate funding costs.
        The spread between CP rates and Treasury bills indicates funding stress.

        Series collected:
        - DCPF3M: 3-month Financial CP rate
        - DCPN3M: 3-month Nonfinancial CP rate

        Args:
            start_date: Start date for data fetch. Defaults to 60 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with CP rate data in standard format.

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=60)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fred.collect(
                symbols=self.CP_SERIES,
                start_date=start_date,
                end_date=end_date,
            )

        try:
            df = await self.fetch_with_retry(_fetch, breaker_name="credit_cp")
            logger.info("Collected %d CP rate data points", len(df))
            return df
        except Exception as e:
            logger.error("CP rates fetch failed: %s", e)
            raise CollectorFetchError(f"CP rates fetch failed: {e}") from e

    def get_lending_standards_regime(
        self, df: pd.DataFrame | None = None
    ) -> LendingRegimeType:
        """Determine the current lending standards regime based on SLOOS data.

        Uses DRTSCILM (C&I loans to large/middle firms) as the primary indicator.

        Regime classification:
        - TIGHTENING: DRTSCILM > 20% (banks are tightening lending standards)
        - EASING: DRTSCILM < -10% (banks are easing lending standards)
        - NEUTRAL: Otherwise

        Historical context:
        - 2008 GFC: DRTSCILM peaked at ~84%
        - 2020 COVID: DRTSCILM peaked at ~72%
        - Recessions: Typically preceded by DRTSCILM > 40%
        - Expansions: DRTSCILM often -20% to -30%

        Args:
            df: DataFrame with SLOOS data. If None, returns "NEUTRAL".

        Returns:
            "TIGHTENING", "NEUTRAL", or "EASING"
        """
        if df is None or df.empty:
            logger.warning("No data provided for regime classification")
            return "NEUTRAL"

        # Filter for DRTSCILM (primary indicator)
        drtscilm_df = df[df["series_id"] == "DRTSCILM"]

        if drtscilm_df.empty:
            logger.warning("DRTSCILM not found in data, cannot classify regime")
            return "NEUTRAL"

        # Get the latest value
        latest = drtscilm_df.sort_values("timestamp").iloc[-1]
        value = float(latest["value"])

        logger.debug("Latest DRTSCILM value: %.2f%%", value)

        # Classify regime
        if value > self.THRESHOLDS["tightening"]:
            logger.info(
                "TIGHTENING regime: DRTSCILM = %.2f%% > %.2f%%",
                value,
                self.THRESHOLDS["tightening"],
            )
            return "TIGHTENING"
        elif value < self.THRESHOLDS["easing"]:
            logger.info(
                "EASING regime: DRTSCILM = %.2f%% < %.2f%%",
                value,
                self.THRESHOLDS["easing"],
            )
            return "EASING"
        else:
            logger.debug("NEUTRAL regime: DRTSCILM = %.2f%%", value)
            return "NEUTRAL"

    async def collect_ci_spread(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate the spread between financial and nonfinancial CP rates.

        This spread indicates relative funding stress between financial and
        non-financial corporations. A widening spread suggests stress in
        financial sector funding.

        Args:
            start_date: Start date for data fetch.
            end_date: End date for data fetch.

        Returns:
            DataFrame with CP spread (DCPF3M - DCPN3M) in basis points.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=60)
        if end_date is None:
            end_date = datetime.now(UTC)

        cp_df = await self.collect_cp_rates(start_date, end_date)

        if cp_df.empty:
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Pivot to wide format
        pivot = cp_df.pivot(index="timestamp", columns="series_id", values="value")

        if "DCPF3M" not in pivot.columns or "DCPN3M" not in pivot.columns:
            logger.warning("Missing CP series for spread calculation")
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Forward fill and calculate spread in basis points
        pivot = pivot.ffill()
        spread = (pivot["DCPF3M"] - pivot["DCPN3M"]) * 100

        result = pd.DataFrame(
            {
                "timestamp": spread.index,
                "series_id": "credit_cp_spread",
                "source": "calculated",
                "value": spread.values,
                "unit": "basis_points",
            }
        )

        result = result.dropna(subset=["value"]).reset_index(drop=True)
        logger.info("Calculated %d CP spread points", len(result))
        return result


# Register collector with the registry
registry.register("credit", CreditCollector)
