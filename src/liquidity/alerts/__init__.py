"""Alert module for liquidity monitoring notifications.

Provides Discord webhook alerting for:
- Regime changes (EXPANSION <-> CONTRACTION)
- Stress threshold breaches
- Significant DXY moves (>1% daily)
- Correlation regime shifts (>0.3 change)

Example:
    from liquidity.alerts import AlertManager

    # Create manager with automatic configuration
    manager = AlertManager()

    # Check for alerts (sync)
    manager.check_regime_change(
        direction="CONTRACTION",
        intensity=35,
        confidence="HIGH",
    )

    # Or use async
    await manager.check_regime_change_async(...)

    # Start scheduled checks
    await manager.start_scheduler()
"""

from liquidity.alerts.config import (
    AlertConfig,
    RateLimits,
    StressThresholds,
    load_alert_config,
)
from liquidity.alerts.discord import DiscordClient, DiscordConfig, create_discord_client
from liquidity.alerts.formatter import AlertColors, AlertFormatter, LiquidityMetrics
from liquidity.alerts.handlers import AlertHandlers, AlertState
from liquidity.alerts.scheduler import AlertScheduler, FullAlertScheduler


class AlertManager:
    """High-level alert management interface.

    Combines DiscordClient, AlertHandlers, and AlertScheduler into a single
    easy-to-use interface for sending alerts.

    Example:
        manager = AlertManager()

        # Check for regime change
        manager.check_regime_change(
            direction="CONTRACTION",
            intensity=35,
            confidence="HIGH",
        )

        # Check stress indicators
        manager.check_stress("sofr_ois", value=15.5)

        # Start scheduled monitoring
        await manager.start_scheduler()
    """

    def __init__(
        self,
        config: AlertConfig | None = None,
        discord_client: DiscordClient | None = None,
    ) -> None:
        """Initialize alert manager.

        Args:
            config: Alert configuration. Loads from environment if None.
            discord_client: Discord client. Creates new one if None.
        """
        self._config = config or load_alert_config()
        self._discord = discord_client or create_discord_client(
            webhook_url=self._config.discord_webhook_url,
            username=self._config.discord_username,
            rate_limit_seconds=self._config.rate_limits.default,
        )
        self._handlers = AlertHandlers(self._discord, self._config)
        self._scheduler: AlertScheduler | None = None

    @property
    def is_enabled(self) -> bool:
        """Check if alerts are enabled."""
        return self._config.enabled and self._discord.is_configured

    @property
    def config(self) -> AlertConfig:
        """Get alert configuration."""
        return self._config

    @property
    def handlers(self) -> AlertHandlers:
        """Get alert handlers."""
        return self._handlers

    @property
    def scheduler(self) -> AlertScheduler | None:
        """Get scheduler if started."""
        return self._scheduler

    # Sync methods
    def check_regime_change(
        self,
        direction: str,
        intensity: float,
        confidence: str,
        metrics: LiquidityMetrics | None = None,
    ) -> bool:
        """Check and alert on regime change.

        Args:
            direction: Current regime (EXPANSION/CONTRACTION).
            intensity: Regime intensity (0-100).
            confidence: Confidence level (HIGH/MEDIUM/LOW).
            metrics: Optional key liquidity metrics.

        Returns:
            True if alert was sent.
        """
        return self._handlers.check_regime_change(
            direction=direction,
            intensity=intensity,
            confidence=confidence,
            metrics=metrics,
        )

    def check_stress(
        self,
        indicator: str,
        value: float,
        elevated_threshold: float | None = None,
        critical_threshold: float | None = None,
        unit: str = "bps",
    ) -> bool:
        """Check and alert on stress threshold breach.

        Args:
            indicator: Indicator name.
            value: Current value.
            elevated_threshold: Optional elevated threshold.
            critical_threshold: Optional critical threshold.
            unit: Unit of measurement.

        Returns:
            True if alert was sent.
        """
        return self._handlers.check_stress_breach(
            indicator=indicator,
            value=value,
            elevated_threshold=elevated_threshold,
            critical_threshold=critical_threshold,
            unit=unit,
        )

    def check_dxy(self, current: float, change_pct: float | None = None) -> bool:
        """Check and alert on DXY move.

        Args:
            current: Current DXY value.
            change_pct: Optional change percentage.

        Returns:
            True if alert was sent.
        """
        return self._handlers.check_dxy_move(current, change_pct)

    def check_correlation(
        self,
        asset: str,
        correlation: float,
        liquidity_metric: str = "Global Liquidity",
    ) -> bool:
        """Check and alert on correlation shift.

        Args:
            asset: Asset name.
            correlation: Current correlation value.
            liquidity_metric: Liquidity metric name.

        Returns:
            True if alert was sent.
        """
        return self._handlers.check_correlation_shift(
            asset=asset,
            current_corr=correlation,
            liquidity_metric=liquidity_metric,
        )

    # Async methods
    async def check_regime_change_async(
        self,
        direction: str,
        intensity: float,
        confidence: str,
        metrics: LiquidityMetrics | None = None,
    ) -> bool:
        """Async version of check_regime_change."""
        return await self._handlers.check_regime_change_async(
            direction=direction,
            intensity=intensity,
            confidence=confidence,
            metrics=metrics,
        )

    async def check_stress_async(
        self,
        indicator: str,
        value: float,
        elevated_threshold: float | None = None,
        critical_threshold: float | None = None,
        unit: str = "bps",
    ) -> bool:
        """Async version of check_stress."""
        return await self._handlers.check_stress_breach_async(
            indicator=indicator,
            value=value,
            elevated_threshold=elevated_threshold,
            critical_threshold=critical_threshold,
            unit=unit,
        )

    async def check_dxy_async(
        self, current: float, change_pct: float | None = None
    ) -> bool:
        """Async version of check_dxy."""
        return await self._handlers.check_dxy_move_async(current, change_pct)

    async def check_correlation_async(
        self,
        asset: str,
        correlation: float,
        liquidity_metric: str = "Global Liquidity",
    ) -> bool:
        """Async version of check_correlation."""
        return await self._handlers.check_correlation_shift_async(
            asset=asset,
            current_corr=correlation,
            liquidity_metric=liquidity_metric,
        )

    # Scheduler methods
    async def start_scheduler(
        self,
        check_interval: int | None = None,
    ) -> None:
        """Start the alert scheduler.

        Args:
            check_interval: Override check interval in seconds.
        """
        if self._scheduler is not None and self._scheduler.is_running:
            return

        self._scheduler = AlertScheduler(
            handlers=self._handlers,
            config=self._config,
            check_interval_seconds=check_interval,
        )
        await self._scheduler.start()

    def stop_scheduler(self) -> None:
        """Stop the alert scheduler."""
        if self._scheduler is not None:
            self._scheduler.stop()

    def reset_state(self) -> None:
        """Reset all alert state."""
        self._handlers.reset_state()

    def __repr__(self) -> str:
        """Return string representation."""
        status = "enabled" if self.is_enabled else "disabled"
        return f"AlertManager({status})"


__all__ = [
    # Main interface
    "AlertManager",
    # Config
    "AlertConfig",
    "RateLimits",
    "StressThresholds",
    "load_alert_config",
    # Discord
    "DiscordClient",
    "DiscordConfig",
    "create_discord_client",
    # Formatter
    "AlertFormatter",
    "AlertColors",
    "LiquidityMetrics",
    # Handlers
    "AlertHandlers",
    "AlertState",
    # Scheduler
    "AlertScheduler",
    "FullAlertScheduler",
]
