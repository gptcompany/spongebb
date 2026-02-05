"""Nowcast engine for daily liquidity estimation.

This module provides the main orchestrator for the nowcasting pipeline,
coordinating data fetching, validation, model updates, and alerting.

Daily workflow:
1. Fetch high-frequency proxies (TGA, RRP, SOFR)
2. Validate data quality and freshness
3. Update Kalman filter with new observations
4. Generate nowcast with confidence intervals
5. Store results and alert if significant move detected

The engine supports both real-time operation and batch backtesting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from liquidity.nowcasting.kalman import KalmanTuner, LiquidityStateSpace, NowcastResult

if TYPE_CHECKING:
    from liquidity.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


@dataclass
class NowcastConfig:
    """Configuration for the nowcast engine.

    Attributes:
        innovation_threshold: Std devs for significant move alerts.
        min_observations: Minimum observations for model fitting.
        max_data_age_hours: Maximum age for data before staleness warning.
        proxy_weights: Weights for combining HF proxies.
        historical_window_days: Days of history for model fitting.
        alert_webhook_url: Optional webhook for alerts.
    """

    innovation_threshold: float = 2.0
    min_observations: int = 50
    max_data_age_hours: int = 24
    proxy_weights: dict[str, float] = field(default_factory=lambda: {
        "TGA": 0.4,
        "RRP": 0.4,
        "SOFR": 0.2,
    })
    historical_window_days: int = 252  # ~1 year
    alert_webhook_url: str | None = None

    def __post_init__(self) -> None:
        """Validate weights sum to 1."""
        total = sum(self.proxy_weights.values())
        if not np.isclose(total, 1.0):
            logger.warning(
                "Proxy weights sum to %.2f, normalizing to 1.0", total
            )
            for key in self.proxy_weights:
                self.proxy_weights[key] /= total


@dataclass
class DataQualityReport:
    """Report on data quality for nowcasting.

    Attributes:
        is_valid: Whether data passes quality checks.
        tga_fresh: TGA data freshness status.
        rrp_fresh: RRP data freshness status.
        sofr_fresh: SOFR data freshness status.
        missing_pct: Percentage of missing values.
        stalest_data_hours: Age of oldest data point.
        warnings: List of quality warnings.
    """

    is_valid: bool
    tga_fresh: bool
    rrp_fresh: bool
    sofr_fresh: bool
    missing_pct: float
    stalest_data_hours: float
    warnings: list[str] = field(default_factory=list)


class NowcastEngine:
    """Orchestrates nowcasting for Net Liquidity indices.

    The engine coordinates:
    - Data collection from high-frequency sources
    - Data validation and quality checks
    - Kalman filter model management
    - Nowcast generation with uncertainty
    - Alerting for significant moves

    Example:
        from liquidity.nowcasting import NowcastEngine

        # Create engine with default config
        engine = NowcastEngine()

        # Run daily nowcast
        result = await engine.run_daily_nowcast()
        print(f"Net Liquidity nowcast: {result.mean:.2f}T +/- {result.std:.2f}T")

        # Check for significant moves
        if engine.is_significant_move(result):
            print("Alert: Significant liquidity move detected!")
    """

    def __init__(
        self,
        config: NowcastConfig | None = None,
        state_space: LiquidityStateSpace | None = None,
    ) -> None:
        """Initialize the nowcast engine.

        Args:
            config: Engine configuration. Uses defaults if not provided.
            state_space: Pre-configured state-space model. Creates new if not provided.
        """
        self.config = config or NowcastConfig()
        self.state_space = state_space or LiquidityStateSpace()
        self._tuner = KalmanTuner()

        # Collectors initialized lazily
        self._tga_collector: BaseCollector | None = None
        self._nyfed_collector: BaseCollector | None = None
        self._sofr_collector: BaseCollector | None = None

        # Cache for latest data
        self._latest_data: dict[str, pd.DataFrame] = {}
        self._last_update: datetime | None = None

        # History for nowcasts
        self._nowcast_history: list[NowcastResult] = []

    async def _get_tga_collector(self) -> BaseCollector:
        """Get or create TGA collector."""
        if self._tga_collector is None:
            from liquidity.collectors.tga_daily import TGADailyCollector
            self._tga_collector = TGADailyCollector()
        return self._tga_collector

    async def _get_nyfed_collector(self) -> BaseCollector:
        """Get or create NY Fed collector."""
        if self._nyfed_collector is None:
            from liquidity.collectors.nyfed import NYFedCollector
            self._nyfed_collector = NYFedCollector()
        return self._nyfed_collector

    async def _get_sofr_collector(self) -> BaseCollector:
        """Get or create SOFR collector."""
        if self._sofr_collector is None:
            from liquidity.collectors.sofr import SOFRCollector
            self._sofr_collector = SOFRCollector()
        return self._sofr_collector

    async def _fetch_tga(self, days: int = 90) -> pd.DataFrame:
        """Fetch TGA data from Treasury FiscalData API.

        Args:
            days: Number of days of history to fetch.

        Returns:
            DataFrame with TGA daily values.
        """
        collector = await self._get_tga_collector()
        start_date = datetime.now(UTC) - timedelta(days=days)
        df = await collector.collect(start_date=start_date)
        self._latest_data["TGA"] = df
        return df

    async def _fetch_rrp(self, days: int = 90) -> pd.DataFrame:
        """Fetch RRP data from NY Fed API.

        Args:
            days: Number of days of history to fetch.

        Returns:
            DataFrame with RRP daily values.
        """
        collector = await self._get_nyfed_collector()
        start_date = datetime.now(UTC) - timedelta(days=days)
        df = await collector.collect_rrp(start_date=start_date)
        self._latest_data["RRP"] = df
        return df

    async def _fetch_sofr(self, days: int = 90) -> pd.DataFrame:
        """Fetch SOFR data from NY Fed API.

        Args:
            days: Number of days of history to fetch.

        Returns:
            DataFrame with SOFR daily values.
        """
        collector = await self._get_sofr_collector()
        df = await collector.collect(days=days)
        self._latest_data["SOFR"] = df
        return df

    def _validate_data(
        self,
        tga: pd.DataFrame,
        rrp: pd.DataFrame,
        sofr: pd.DataFrame,
    ) -> DataQualityReport:
        """Validate data quality and freshness.

        Args:
            tga: TGA DataFrame.
            rrp: RRP DataFrame.
            sofr: SOFR DataFrame.

        Returns:
            DataQualityReport with validation results.
        """
        warnings = []
        now = datetime.now(UTC)

        def check_freshness(df: pd.DataFrame, name: str) -> tuple[bool, float]:
            """Check if data is fresh enough."""
            if df.empty:
                warnings.append(f"{name} data is empty")
                return False, float("inf")

            latest = pd.to_datetime(df["timestamp"].max())
            if latest.tzinfo is None:
                latest = latest.tz_localize(UTC)

            age_hours = (now - latest).total_seconds() / 3600
            is_fresh = age_hours < self.config.max_data_age_hours

            if not is_fresh:
                warnings.append(
                    f"{name} data is stale: {age_hours:.1f} hours old"
                )

            return is_fresh, age_hours

        tga_fresh, tga_age = check_freshness(tga, "TGA")
        rrp_fresh, rrp_age = check_freshness(rrp, "RRP")
        sofr_fresh, sofr_age = check_freshness(sofr, "SOFR")

        # Calculate missing percentage across all data
        total_points = len(tga) + len(rrp) + len(sofr)
        if total_points > 0:
            tga_missing = tga["value"].isna().sum() if "value" in tga.columns else 0
            rrp_missing = rrp["value"].isna().sum() if "value" in rrp.columns else 0
            sofr_missing = sofr["value"].isna().sum() if "value" in sofr.columns else 0
            missing_pct = (tga_missing + rrp_missing + sofr_missing) / total_points * 100
        else:
            missing_pct = 100.0

        stalest_hours = max(tga_age, rrp_age, sofr_age)

        # Determine overall validity
        is_valid = (
            (tga_fresh or rrp_fresh)  # At least one major source fresh
            and missing_pct < 50  # Not too much missing data
        )

        return DataQualityReport(
            is_valid=is_valid,
            tga_fresh=tga_fresh,
            rrp_fresh=rrp_fresh,
            sofr_fresh=sofr_fresh,
            missing_pct=missing_pct,
            stalest_data_hours=stalest_hours,
            warnings=warnings,
        )

    def _combine_proxies(
        self,
        tga: pd.DataFrame,
        rrp: pd.DataFrame,
        sofr: pd.DataFrame,
    ) -> pd.Series:
        """Combine high-frequency proxies into observation for Kalman filter.

        The combination creates a proxy for Net Liquidity changes based on
        the high-frequency components we can observe daily.

        Net Liquidity = WALCL - TGA - RRP

        Since WALCL is only weekly, we use TGA and RRP changes as proxies
        for daily Net Liquidity changes, with SOFR spread as a sentiment
        indicator.

        Args:
            tga: TGA DataFrame (millions USD).
            rrp: RRP DataFrame (billions USD).
            sofr: SOFR DataFrame (percent).

        Returns:
            Combined series indexed by date.
        """
        # Standardize timestamps and index
        def to_series(df: pd.DataFrame, scale: float = 1.0) -> pd.Series:
            """Convert DataFrame to Series with date index."""
            if df.empty or "value" not in df.columns:
                return pd.Series(dtype=float)
            s = df.set_index("timestamp")["value"] * scale
            s.index = pd.to_datetime(s.index).normalize()
            return s

        # Convert to common scale (trillions USD)
        tga_series = to_series(tga, scale=1e-6)  # millions -> trillions
        rrp_series = to_series(rrp, scale=1e-3)  # billions -> trillions

        # Align on common dates
        all_dates = (
            set(tga_series.index) | set(rrp_series.index)
        )
        if not all_dates:
            logger.warning("No data available for proxy combination")
            return pd.Series(dtype=float)

        combined_index = pd.DatetimeIndex(sorted(all_dates))

        # Reindex with forward fill for missing values
        tga_aligned = tga_series.reindex(combined_index).ffill()
        rrp_aligned = rrp_series.reindex(combined_index).ffill()

        # Compute proxy: negative changes in TGA and RRP increase liquidity
        # This is a simplified proxy for Net Liquidity changes
        # Full calculation would be: WALCL - TGA - RRP
        # Since WALCL is slow-moving, daily changes are driven by TGA and RRP
        proxy = -(tga_aligned + rrp_aligned)

        # Add bias term to keep values positive (typical Net Liquidity ~5-6T)
        # This is just for numerical stability; the Kalman filter handles levels
        bias = 6.0  # ~$6T baseline
        proxy = proxy + bias

        return proxy.dropna()

    def is_significant_move(self, result: NowcastResult) -> bool:
        """Check if nowcast represents a significant move.

        Uses the innovation (prediction error) relative to historical
        innovation variance to detect significant moves.

        Args:
            result: Nowcast result to evaluate.

        Returns:
            True if move exceeds threshold.
        """
        if result.std <= 0:
            return False

        # Standardized innovation
        z_score = abs(result.innovation) / result.std

        return z_score > self.config.innovation_threshold

    async def _alert_significant_move(self, result: NowcastResult) -> None:
        """Send alert for significant liquidity move.

        Args:
            result: Nowcast result triggering alert.
        """
        logger.warning(
            "Significant liquidity move detected! "
            "Nowcast: %.2f, Innovation: %.2f, Threshold: %.1f std",
            result.mean,
            result.innovation,
            self.config.innovation_threshold,
        )

        if self.config.alert_webhook_url:
            # TODO: Integrate with alerts module
            logger.info(
                "Would send alert to webhook: %s",
                self.config.alert_webhook_url
            )

    async def run_daily_nowcast(self) -> NowcastResult:
        """Execute daily nowcast pipeline.

        This is the main entry point for daily nowcasting:
        1. Fetches latest HF data (TGA, RRP, SOFR)
        2. Validates data quality
        3. Updates model with new observations
        4. Generates nowcast with confidence intervals
        5. Checks for significant moves

        Returns:
            NowcastResult with point estimate and confidence intervals.

        Raises:
            ValueError: If data quality is insufficient.
        """
        logger.info("Starting daily nowcast pipeline")

        # 1. Fetch latest HF data
        tga = await self._fetch_tga()
        rrp = await self._fetch_rrp()
        sofr = await self._fetch_sofr()

        # 2. Validate data
        quality = self._validate_data(tga, rrp, sofr)
        if not quality.is_valid:
            logger.error("Data quality check failed: %s", quality.warnings)
            raise ValueError(f"Insufficient data quality: {quality.warnings}")

        for warning in quality.warnings:
            logger.warning("Data quality warning: %s", warning)

        # 3. Combine proxies
        observation = self._combine_proxies(tga, rrp, sofr)

        if len(observation) < self.config.min_observations:
            raise ValueError(
                f"Insufficient observations: {len(observation)} < "
                f"{self.config.min_observations}"
            )

        # 4. Fit/update model
        if not self.state_space.is_fitted:
            logger.info("Fitting state-space model on %d observations", len(observation))
            self.state_space.fit(observation)
        else:
            # Update with latest observation
            latest_value = observation.iloc[-1]
            latest_date = observation.index[-1]
            self.state_space.update(latest_value, timestamp=latest_date)

        # 5. Generate nowcast
        result = self.state_space.nowcast(steps=1)

        # 6. Check for significant move
        if self.is_significant_move(result):
            await self._alert_significant_move(result)

        # Track history
        self._nowcast_history.append(result)
        self._last_update = datetime.now(UTC)

        logger.info(
            "Daily nowcast complete: mean=%.2f, std=%.3f, CI=[%.2f, %.2f]",
            result.mean, result.std, result.ci_lower, result.ci_upper
        )

        return result

    def fit_on_historical(
        self,
        net_liquidity: pd.Series,
        tune_parameters: bool = True,
    ) -> NowcastResult:
        """Fit model on historical Net Liquidity data.

        Use this for backtesting or initializing the model with
        full historical data (including official WALCL releases).

        Args:
            net_liquidity: Historical Net Liquidity series.
            tune_parameters: Whether to run adaptive parameter tuning.

        Returns:
            Initial nowcast result after fitting.
        """
        logger.info(
            "Fitting on historical data: %d observations, %s to %s",
            len(net_liquidity),
            net_liquidity.index.min(),
            net_liquidity.index.max(),
        )

        if tune_parameters:
            estimates = self._tuner.adaptive_tuning(net_liquidity)
            logger.info("Tuned parameters: %s", estimates)

        self.state_space.fit(net_liquidity)

        return self.state_space.nowcast(steps=1)

    def get_nowcast_history(self) -> pd.DataFrame:
        """Get history of nowcasts as DataFrame.

        Returns:
            DataFrame with columns: timestamp, mean, std, ci_lower, ci_upper.
        """
        if not self._nowcast_history:
            return pd.DataFrame(
                columns=["timestamp", "mean", "std", "ci_lower", "ci_upper"]
            )

        records = []
        for result in self._nowcast_history:
            records.append({
                "timestamp": result.timestamp,
                "mean": result.mean,
                "std": result.std,
                "ci_lower": result.ci_lower,
                "ci_upper": result.ci_upper,
                "innovation": result.innovation,
            })

        return pd.DataFrame(records)

    def get_model_diagnostics(self) -> dict[str, Any]:
        """Get current model diagnostics.

        Returns:
            Dictionary with model statistics and diagnostics.
        """
        if not self.state_space.is_fitted:
            return {"status": "not_fitted"}

        diagnostics = self.state_space.get_diagnostics()
        diagnostics["last_update"] = self._last_update
        diagnostics["n_nowcasts"] = len(self._nowcast_history)

        return diagnostics

    async def close(self) -> None:
        """Close all collector connections."""
        if self._tga_collector is not None:
            await self._tga_collector.close()
        if self._nyfed_collector is not None:
            await self._nyfed_collector.close()
        if self._sofr_collector is not None:
            await self._sofr_collector.close()

    def __repr__(self) -> str:
        """Return string representation."""
        status = "fitted" if self.state_space.is_fitted else "not fitted"
        return f"NowcastEngine(status={status}, n_nowcasts={len(self._nowcast_history)})"
