"""Alert handlers for detecting and sending alerts.

Handles detection and alerting for:
- Regime changes (EXPANSION <-> CONTRACTION)
- Stress threshold breaches
- Significant DXY moves (>1%)
- Correlation regime shifts (>0.3 change)
"""

import logging
from dataclasses import dataclass, field

from liquidity.alerts.config import AlertConfig
from liquidity.alerts.discord import DiscordClient
from liquidity.alerts.formatter import AlertFormatter, LiquidityMetrics

logger = logging.getLogger(__name__)


@dataclass
class AlertState:
    """Track state for alert detection.

    Stores previous values to detect changes that should trigger alerts.
    """

    previous_regime: str | None = None
    previous_regime_intensity: float = 0.0
    previous_dxy: float | None = None
    previous_correlations: dict[str, float] = field(default_factory=dict)
    previous_stress_alerts: dict[str, str] = field(default_factory=dict)


class AlertHandlers:
    """Handlers for detecting and sending liquidity alerts.

    Monitors liquidity conditions and sends Discord alerts when:
    - Regime changes from EXPANSION to CONTRACTION or vice versa
    - Stress indicators breach thresholds
    - DXY moves more than 1% in a day
    - Asset-liquidity correlations shift by more than 0.3

    Example:
        from liquidity.alerts.discord import create_discord_client
        from liquidity.alerts.config import load_alert_config

        config = load_alert_config()
        client = create_discord_client()
        handlers = AlertHandlers(client, config)

        # Check for regime change
        await handlers.check_regime_change_async(regime_result)
    """

    def __init__(
        self,
        discord_client: DiscordClient,
        config: AlertConfig,
        formatter: AlertFormatter | None = None,
    ) -> None:
        """Initialize alert handlers.

        Args:
            discord_client: Discord client for sending alerts.
            config: Alert configuration.
            formatter: Optional custom formatter. Uses default AlertFormatter if None.
        """
        self._discord = discord_client
        self._config = config
        self._formatter = formatter or AlertFormatter()
        self._state = AlertState()

        # Configure rate limits from config
        self._discord.set_rate_limit("regime_change", config.rate_limits.regime_change)
        self._discord.set_rate_limit("stress_breach", config.rate_limits.stress_breach)
        self._discord.set_rate_limit("dxy_move", config.rate_limits.dxy_move)
        self._discord.set_rate_limit(
            "correlation_shift", config.rate_limits.correlation_shift
        )

    @property
    def state(self) -> AlertState:
        """Get current alert state."""
        return self._state

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
            True if alert was sent, False otherwise.
        """
        if not self._config.enabled:
            return False

        previous = self._state.previous_regime
        prev_intensity = self._state.previous_regime_intensity

        # Check for actual regime change
        if previous is not None and direction != previous:
            embed = self._formatter.regime_change(
                previous=previous,
                current=direction,
                prev_intensity=prev_intensity,
                curr_intensity=intensity,
                confidence=confidence,
                metrics=metrics,
            )

            sent = self._discord.send_embed(embed, "regime_change")

            if sent:
                logger.info(
                    "Regime change alert sent: %s -> %s (confidence: %s)",
                    previous,
                    direction,
                    confidence,
                )

            # Update state after sending
            self._state.previous_regime = direction
            self._state.previous_regime_intensity = intensity
            return sent

        # Update state even if no alert sent
        self._state.previous_regime = direction
        self._state.previous_regime_intensity = intensity
        return False

    async def check_regime_change_async(
        self,
        direction: str,
        intensity: float,
        confidence: str,
        metrics: LiquidityMetrics | None = None,
    ) -> bool:
        """Async version of check_regime_change.

        Args:
            direction: Current regime (EXPANSION/CONTRACTION).
            intensity: Regime intensity (0-100).
            confidence: Confidence level (HIGH/MEDIUM/LOW).
            metrics: Optional key liquidity metrics.

        Returns:
            True if alert was sent, False otherwise.
        """
        if not self._config.enabled:
            return False

        previous = self._state.previous_regime
        prev_intensity = self._state.previous_regime_intensity

        if previous is not None and direction != previous:
            embed = self._formatter.regime_change(
                previous=previous,
                current=direction,
                prev_intensity=prev_intensity,
                curr_intensity=intensity,
                confidence=confidence,
                metrics=metrics,
            )

            sent = await self._discord.send_embed_async(embed, "regime_change")

            if sent:
                logger.info(
                    "Regime change alert sent: %s -> %s (confidence: %s)",
                    previous,
                    direction,
                    confidence,
                )

            self._state.previous_regime = direction
            self._state.previous_regime_intensity = intensity
            return sent

        self._state.previous_regime = direction
        self._state.previous_regime_intensity = intensity
        return False

    def check_stress_breach(
        self,
        indicator: str,
        value: float,
        elevated_threshold: float | None = None,
        critical_threshold: float | None = None,
        unit: str = "bps",
    ) -> bool:
        """Check and alert on stress threshold breach.

        Args:
            indicator: Indicator name (e.g., "sofr_ois").
            value: Current indicator value.
            elevated_threshold: Optional custom elevated threshold.
            critical_threshold: Optional custom critical threshold.
            unit: Unit of measurement (bps/percent).

        Returns:
            True if alert was sent, False otherwise.
        """
        if not self._config.enabled:
            return False

        # Get thresholds from config or use provided values
        thresholds = self._config.stress_thresholds
        indicator_lower = indicator.lower().replace("-", "_").replace(" ", "_")

        if elevated_threshold is None:
            elevated_threshold = getattr(
                thresholds, f"{indicator_lower}_elevated", 10.0
            )
        if critical_threshold is None:
            critical_threshold = getattr(
                thresholds, f"{indicator_lower}_critical", 25.0
            )

        # Determine severity (thresholds are guaranteed non-None at this point)
        if critical_threshold is not None and value >= critical_threshold:
            severity = "critical"
            threshold = critical_threshold
        elif elevated_threshold is not None and value >= elevated_threshold:
            severity = "elevated"
            threshold = elevated_threshold
        else:
            # Clear previous alert state if back to normal
            self._state.previous_stress_alerts.pop(indicator, None)
            return False

        # Check if this severity level was already alerted
        previous_severity = self._state.previous_stress_alerts.get(indicator)
        if previous_severity == severity:
            # Already alerted at this level, skip
            return False

        # Send alert (threshold is guaranteed non-None at this point due to above checks)
        embed = self._formatter.stress_breach(
            indicator=indicator,
            value=value,
            threshold=threshold if threshold is not None else 0.0,
            severity=severity,
            unit=unit,
        )

        alert_type = f"stress_{indicator}"
        sent = self._discord.send_embed(embed, alert_type)

        if sent:
            self._state.previous_stress_alerts[indicator] = severity
            logger.info(
                "Stress alert sent: %s = %.2f (%s)",
                indicator,
                value,
                severity,
            )

        return sent

    async def check_stress_breach_async(
        self,
        indicator: str,
        value: float,
        elevated_threshold: float | None = None,
        critical_threshold: float | None = None,
        unit: str = "bps",
    ) -> bool:
        """Async version of check_stress_breach."""
        if not self._config.enabled:
            return False

        thresholds = self._config.stress_thresholds
        indicator_lower = indicator.lower().replace("-", "_").replace(" ", "_")

        if elevated_threshold is None:
            elevated_threshold = getattr(
                thresholds, f"{indicator_lower}_elevated", 10.0
            )
        if critical_threshold is None:
            critical_threshold = getattr(
                thresholds, f"{indicator_lower}_critical", 25.0
            )

        if critical_threshold is not None and value >= critical_threshold:
            severity = "critical"
            threshold = critical_threshold
        elif elevated_threshold is not None and value >= elevated_threshold:
            severity = "elevated"
            threshold = elevated_threshold
        else:
            self._state.previous_stress_alerts.pop(indicator, None)
            return False

        previous_severity = self._state.previous_stress_alerts.get(indicator)
        if previous_severity == severity:
            return False

        embed = self._formatter.stress_breach(
            indicator=indicator,
            value=value,
            threshold=threshold if threshold is not None else 0.0,
            severity=severity,
            unit=unit,
        )

        alert_type = f"stress_{indicator}"
        sent = await self._discord.send_embed_async(embed, alert_type)

        if sent:
            self._state.previous_stress_alerts[indicator] = severity
            logger.info(
                "Stress alert sent: %s = %.2f (%s)",
                indicator,
                value,
                severity,
            )

        return sent

    def check_dxy_move(
        self,
        current_dxy: float,
        change_pct: float | None = None,
    ) -> bool:
        """Check and alert on significant DXY move.

        Args:
            current_dxy: Current DXY value.
            change_pct: Optional pre-calculated change percentage.
                If None, calculates from previous value.

        Returns:
            True if alert was sent, False otherwise.
        """
        if not self._config.enabled:
            return False

        previous = self._state.previous_dxy

        # Calculate change if not provided
        if change_pct is None:
            if previous is None:
                self._state.previous_dxy = current_dxy
                return False
            change_pct = ((current_dxy - previous) / previous) * 100

        threshold = self._config.dxy_move_threshold_pct

        # Check threshold
        if abs(change_pct) >= threshold:
            embed = self._formatter.dxy_move(
                current=current_dxy,
                change_pct=change_pct,
                previous=previous,
            )

            sent = self._discord.send_embed(embed, "dxy_move")

            if sent:
                logger.info(
                    "DXY move alert sent: %.2f (%+.2f%%)",
                    current_dxy,
                    change_pct,
                )

            self._state.previous_dxy = current_dxy
            return sent

        # Update state
        self._state.previous_dxy = current_dxy
        return False

    async def check_dxy_move_async(
        self,
        current_dxy: float,
        change_pct: float | None = None,
    ) -> bool:
        """Async version of check_dxy_move."""
        if not self._config.enabled:
            return False

        previous = self._state.previous_dxy

        if change_pct is None:
            if previous is None:
                self._state.previous_dxy = current_dxy
                return False
            change_pct = ((current_dxy - previous) / previous) * 100

        threshold = self._config.dxy_move_threshold_pct

        if abs(change_pct) >= threshold:
            embed = self._formatter.dxy_move(
                current=current_dxy,
                change_pct=change_pct,
                previous=previous,
            )

            sent = await self._discord.send_embed_async(embed, "dxy_move")

            if sent:
                logger.info(
                    "DXY move alert sent: %.2f (%+.2f%%)",
                    current_dxy,
                    change_pct,
                )

            self._state.previous_dxy = current_dxy
            return sent

        self._state.previous_dxy = current_dxy
        return False

    def check_correlation_shift(
        self,
        asset: str,
        current_corr: float,
        liquidity_metric: str = "Global Liquidity",
    ) -> bool:
        """Check and alert on correlation regime shift.

        Args:
            asset: Asset name (e.g., "BTC", "SPX").
            current_corr: Current correlation value (-1 to 1).
            liquidity_metric: Name of the liquidity metric.

        Returns:
            True if alert was sent, False otherwise.
        """
        if not self._config.enabled:
            return False

        previous = self._state.previous_correlations.get(asset)

        if previous is None:
            self._state.previous_correlations[asset] = current_corr
            return False

        change = current_corr - previous
        threshold = self._config.correlation_shift_threshold

        if abs(change) >= threshold:
            embed = self._formatter.correlation_shift(
                asset=asset,
                previous=previous,
                current=current_corr,
                change=change,
                liquidity_metric=liquidity_metric,
            )

            alert_type = f"corr_{asset}"
            sent = self._discord.send_embed(embed, alert_type)

            if sent:
                logger.info(
                    "Correlation shift alert sent: %s = %.2f (change: %+.2f)",
                    asset,
                    current_corr,
                    change,
                )

            self._state.previous_correlations[asset] = current_corr
            return sent

        self._state.previous_correlations[asset] = current_corr
        return False

    async def check_correlation_shift_async(
        self,
        asset: str,
        current_corr: float,
        liquidity_metric: str = "Global Liquidity",
    ) -> bool:
        """Async version of check_correlation_shift."""
        if not self._config.enabled:
            return False

        previous = self._state.previous_correlations.get(asset)

        if previous is None:
            self._state.previous_correlations[asset] = current_corr
            return False

        change = current_corr - previous
        threshold = self._config.correlation_shift_threshold

        if abs(change) >= threshold:
            embed = self._formatter.correlation_shift(
                asset=asset,
                previous=previous,
                current=current_corr,
                change=change,
                liquidity_metric=liquidity_metric,
            )

            alert_type = f"corr_{asset}"
            sent = await self._discord.send_embed_async(embed, alert_type)

            if sent:
                logger.info(
                    "Correlation shift alert sent: %s = %.2f (change: %+.2f)",
                    asset,
                    current_corr,
                    change,
                )

            self._state.previous_correlations[asset] = current_corr
            return sent

        self._state.previous_correlations[asset] = current_corr
        return False

    def check_multiple_correlations(
        self,
        correlations: dict[str, float],
        liquidity_metric: str = "Global Liquidity",
    ) -> int:
        """Check multiple asset correlations for shifts.

        Args:
            correlations: Dict of asset -> correlation value.
            liquidity_metric: Name of the liquidity metric.

        Returns:
            Number of alerts sent.
        """
        alerts_sent = 0
        for asset, corr in correlations.items():
            if self.check_correlation_shift(asset, corr, liquidity_metric):
                alerts_sent += 1
        return alerts_sent

    async def check_multiple_correlations_async(
        self,
        correlations: dict[str, float],
        liquidity_metric: str = "Global Liquidity",
    ) -> int:
        """Async version of check_multiple_correlations."""
        alerts_sent = 0
        for asset, corr in correlations.items():
            if await self.check_correlation_shift_async(asset, corr, liquidity_metric):
                alerts_sent += 1
        return alerts_sent

    def reset_state(self) -> None:
        """Reset all alert state."""
        self._state = AlertState()

    def __repr__(self) -> str:
        """Return string representation."""
        return f"AlertHandlers(enabled={self._config.enabled})"
