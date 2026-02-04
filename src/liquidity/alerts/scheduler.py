"""Alert check scheduler using asyncio.

Runs periodic alert checks at configurable intervals.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from liquidity.alerts.config import AlertConfig
from liquidity.alerts.handlers import AlertHandlers

logger = logging.getLogger(__name__)


class AlertScheduler:
    """Run alert checks on a schedule.

    Periodically runs all alert checks at the configured interval.
    Uses asyncio for non-blocking operation.

    Example:
        scheduler = AlertScheduler(handlers, config)

        # Start in background
        task = asyncio.create_task(scheduler.start())

        # Later, stop gracefully
        scheduler.stop()
        await task
    """

    def __init__(
        self,
        handlers: AlertHandlers,
        config: AlertConfig,
        check_interval_seconds: int | None = None,
    ) -> None:
        """Initialize the alert scheduler.

        Args:
            handlers: Alert handlers instance.
            config: Alert configuration.
            check_interval_seconds: Override for check interval.
                Defaults to config.check_interval_seconds.
        """
        self._handlers = handlers
        self._config = config
        self._interval = check_interval_seconds or config.check_interval_seconds
        self._running = False
        self._check_callbacks: list[Callable[[], Coroutine[Any, Any, None]]] = []
        self._last_check: datetime | None = None
        self._check_count = 0

    @property
    def is_running(self) -> bool:
        """Check if scheduler is currently running."""
        return self._running

    @property
    def last_check(self) -> datetime | None:
        """Get timestamp of last check."""
        return self._last_check

    @property
    def check_count(self) -> int:
        """Get total number of checks performed."""
        return self._check_count

    def register_check(
        self, callback: Callable[[], Coroutine[Any, Any, None]]
    ) -> None:
        """Register a custom check callback.

        Args:
            callback: Async function to call on each check cycle.
        """
        self._check_callbacks.append(callback)

    async def start(self) -> None:
        """Start the alert check loop.

        Runs continuously until stop() is called.
        """
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        logger.info(
            "Starting alert scheduler with %d second interval",
            self._interval,
        )

        while self._running:
            try:
                await self._run_checks()
                self._last_check = datetime.now(UTC)
                self._check_count += 1
            except Exception as e:
                logger.exception("Error during alert check: %s", e)

            # Sleep in small increments to allow for graceful shutdown
            for _ in range(self._interval):
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def _run_checks(self) -> None:
        """Run all registered alert checks."""
        logger.debug("Running alert checks...")

        # Run custom callbacks
        for callback in self._check_callbacks:
            try:
                await callback()
            except Exception as e:
                logger.exception("Check callback error: %s", e)

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._running:
            return

        logger.info("Stopping alert scheduler...")
        self._running = False

    async def run_once(self) -> None:
        """Run checks once without starting the loop."""
        await self._run_checks()
        self._last_check = datetime.now(UTC)
        self._check_count += 1

    def __repr__(self) -> str:
        """Return string representation."""
        status = "running" if self._running else "stopped"
        return f"AlertScheduler({status}, interval={self._interval}s)"


class FullAlertScheduler(AlertScheduler):
    """Alert scheduler with integrated data fetching.

    Extends AlertScheduler with built-in data collection and alert checking
    for regime, stress, DXY, and correlations.

    Example:
        from liquidity.analyzers import RegimeClassifier, CorrelationEngine
        from liquidity.collectors import FXCollector, StressIndicatorCollector

        scheduler = FullAlertScheduler(
            handlers=handlers,
            config=config,
            regime_classifier=RegimeClassifier(),
            fx_collector=FXCollector(),
            stress_collector=StressIndicatorCollector(),
            correlation_engine=CorrelationEngine(),
        )

        await scheduler.start()
    """

    def __init__(
        self,
        handlers: AlertHandlers,
        config: AlertConfig,
        regime_classifier: Any | None = None,
        fx_collector: Any | None = None,
        stress_collector: Any | None = None,
        correlation_engine: Any | None = None,
        check_interval_seconds: int | None = None,
    ) -> None:
        """Initialize full alert scheduler.

        Args:
            handlers: Alert handlers instance.
            config: Alert configuration.
            regime_classifier: Optional RegimeClassifier instance.
            fx_collector: Optional FXCollector instance.
            stress_collector: Optional StressIndicatorCollector instance.
            correlation_engine: Optional CorrelationEngine instance.
            check_interval_seconds: Override for check interval.
        """
        super().__init__(handlers, config, check_interval_seconds)
        self._regime_classifier = regime_classifier
        self._fx_collector = fx_collector
        self._stress_collector = stress_collector
        self._correlation_engine = correlation_engine

    async def _run_checks(self) -> None:
        """Run all alert checks with data fetching."""
        logger.debug("Running full alert checks...")

        # Run regime check
        if self._regime_classifier is not None:
            await self._check_regime()

        # Run stress check
        if self._stress_collector is not None:
            await self._check_stress()

        # Run DXY check
        if self._fx_collector is not None:
            await self._check_dxy()

        # Run correlation check
        if self._correlation_engine is not None:
            await self._check_correlations()

        # Run custom callbacks
        await super()._run_checks()

    async def _check_regime(self) -> None:
        """Check regime and alert on change."""
        try:
            result = await self._regime_classifier.classify()

            await self._handlers.check_regime_change_async(
                direction=result.direction.value,
                intensity=result.intensity,
                confidence=result.confidence,
                metrics=None,  # Could fetch metrics separately
            )
        except Exception as e:
            logger.warning("Regime check failed: %s", e)

    async def _check_stress(self) -> None:
        """Check stress indicators and alert on breaches."""
        try:
            df = await self._stress_collector.collect()

            if df.empty:
                return

            # Check each stress indicator
            for series_id in [
                "stress_sofr_ois",
                "stress_sofr_width",
                "stress_repo",
                "stress_cp",
            ]:
                series_df = df[df["series_id"] == series_id]
                if series_df.empty:
                    continue

                latest = series_df.sort_values("timestamp").iloc[-1]
                value = float(latest["value"])

                # Determine unit
                unit = "bps" if series_id != "stress_repo" else "percent"

                # Map to config thresholds
                indicator_map = {
                    "stress_sofr_ois": "sofr_ois",
                    "stress_sofr_width": "sofr_width",
                    "stress_repo": "repo_stress",
                    "stress_cp": "cp_spread",
                }

                indicator_name = indicator_map.get(series_id, series_id)

                await self._handlers.check_stress_breach_async(
                    indicator=indicator_name,
                    value=value,
                    unit=unit,
                )

        except Exception as e:
            logger.warning("Stress check failed: %s", e)

    async def _check_dxy(self) -> None:
        """Check DXY and alert on significant moves."""
        try:
            current_dxy = await self._fx_collector.get_current_dxy()

            if current_dxy is not None:
                await self._handlers.check_dxy_move_async(current_dxy)

        except Exception as e:
            logger.warning("DXY check failed: %s", e)

    async def _check_correlations(self) -> None:
        """Check correlations and alert on shifts."""
        # Note: CorrelationEngine requires asset returns data
        # This would need to be fetched separately
        logger.debug("Correlation check not implemented in scheduler")
        pass

    def __repr__(self) -> str:
        """Return string representation."""
        components = []
        if self._regime_classifier:
            components.append("regime")
        if self._stress_collector:
            components.append("stress")
        if self._fx_collector:
            components.append("dxy")
        if self._correlation_engine:
            components.append("corr")

        status = "running" if self._running else "stopped"
        return (
            f"FullAlertScheduler({status}, "
            f"interval={self._interval}s, "
            f"components=[{', '.join(components)}])"
        )
