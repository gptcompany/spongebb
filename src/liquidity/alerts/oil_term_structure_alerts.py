"""Oil term structure alerts for contango/backwardation monitoring.

Generates alerts for:
- Curve shape changes (regime transitions)
- High intensity signals (extreme momentum)
- Extreme roll yields
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

from liquidity.analyzers.term_structure import (
    CurveShape,
    RollYieldMetrics,
    TermStructureSignal,
)

logger = logging.getLogger(__name__)


class TermStructureAlertType(str, Enum):
    """Types of term structure alerts."""

    REGIME_CHANGE = "REGIME_CHANGE"
    HIGH_INTENSITY = "HIGH_INTENSITY"
    EXTREME_ROLL_YIELD = "EXTREME_ROLL_YIELD"


@dataclass
class TermStructureAlert:
    """Term structure alert data."""

    timestamp: datetime
    alert_type: TermStructureAlertType
    curve_shape: str
    intensity: float
    message: str
    severity: str  # INFO, WARNING, CRITICAL


class TermStructureAlertEngine:
    """Generate alerts for oil term structure changes.

    Monitors term structure signals and generates alerts when:
    1. Curve shape changes (CONTANGO <-> BACKWARDATION)
    2. Intensity exceeds warning/critical thresholds
    3. Roll yield is extreme (>20% annualized)

    Example:
        engine = TermStructureAlertEngine()

        # Check signal for alerts
        alerts = engine.check_alerts(signal, roll_yield)

        for alert in alerts:
            print(f"{alert.severity}: {alert.message}")

        # Send to Discord
        for alert in alerts:
            await engine.send_alert(alert)
    """

    # Thresholds
    INTENSITY_WARNING = 70
    INTENSITY_CRITICAL = 90
    ROLL_YIELD_THRESHOLD = 20.0  # % annualized

    def __init__(
        self,
        discord_webhook: str | None = None,
        intensity_warning: float = 70,
        intensity_critical: float = 90,
        roll_yield_threshold: float = 20.0,
    ) -> None:
        """Initialize term structure alert engine.

        Args:
            discord_webhook: Discord webhook URL for sending alerts.
            intensity_warning: Intensity threshold for warning alerts.
            intensity_critical: Intensity threshold for critical alerts.
            roll_yield_threshold: Roll yield threshold for alerts (%).
        """
        self.discord_webhook = discord_webhook
        self.INTENSITY_WARNING = intensity_warning
        self.INTENSITY_CRITICAL = intensity_critical
        self.ROLL_YIELD_THRESHOLD = roll_yield_threshold

        self._last_shape: CurveShape | None = None
        self._http_client: httpx.AsyncClient | None = None

    def check_alerts(
        self,
        signal: TermStructureSignal,
        roll_yield: RollYieldMetrics | None = None,
    ) -> list[TermStructureAlert]:
        """Check for alert conditions.

        Args:
            signal: Current term structure signal.
            roll_yield: Optional roll yield metrics.

        Returns:
            List of triggered alerts.
        """
        alerts = []

        # 1. Check for curve shape change
        if self._last_shape is not None and signal.curve_shape != self._last_shape:
            alerts.append(self._create_regime_change_alert(signal))

        # 2. Check for high intensity
        if signal.intensity >= self.INTENSITY_CRITICAL:
            alerts.append(self._create_intensity_alert(signal, "CRITICAL"))
        elif signal.intensity >= self.INTENSITY_WARNING:
            alerts.append(self._create_intensity_alert(signal, "WARNING"))

        # 3. Check for extreme roll yield
        if roll_yield is not None and abs(roll_yield.annual_yield) > self.ROLL_YIELD_THRESHOLD:
                alerts.append(self._create_roll_yield_alert(signal, roll_yield))

        # Update state
        self._last_shape = signal.curve_shape

        return alerts

    def _create_regime_change_alert(
        self,
        signal: TermStructureSignal,
    ) -> TermStructureAlert:
        """Create alert for regime change."""
        old_shape = self._last_shape.value if self._last_shape else "UNKNOWN"
        new_shape = signal.curve_shape.value

        message = f"Oil term structure shifted: {old_shape} → {new_shape}"

        return TermStructureAlert(
            timestamp=signal.timestamp,
            alert_type=TermStructureAlertType.REGIME_CHANGE,
            curve_shape=new_shape,
            intensity=signal.intensity,
            message=message,
            severity="WARNING",
        )

    def _create_intensity_alert(
        self,
        signal: TermStructureSignal,
        severity: str,
    ) -> TermStructureAlert:
        """Create alert for high intensity."""
        shape = signal.curve_shape.value

        if shape == "BACKWARDATION":
            direction = "tight supply"
        elif shape == "CONTANGO":
            direction = "oversupply"
        else:
            direction = "neutral"

        message = (
            f"Strong {shape.lower()} signal ({signal.intensity:.0f}/100): {direction}"
        )

        return TermStructureAlert(
            timestamp=signal.timestamp,
            alert_type=TermStructureAlertType.HIGH_INTENSITY,
            curve_shape=shape,
            intensity=signal.intensity,
            message=message,
            severity=severity,
        )

    def _create_roll_yield_alert(
        self,
        signal: TermStructureSignal,
        roll_yield: RollYieldMetrics,
    ) -> TermStructureAlert:
        """Create alert for extreme roll yield."""
        direction = "positive" if roll_yield.annual_yield > 0 else "negative"

        message = (
            f"Extreme roll yield: {roll_yield.annual_yield:+.1f}% annualized ({direction})"
        )

        return TermStructureAlert(
            timestamp=signal.timestamp,
            alert_type=TermStructureAlertType.EXTREME_ROLL_YIELD,
            curve_shape=signal.curve_shape.value,
            intensity=signal.intensity,
            message=message,
            severity="WARNING",
        )

    def format_discord_message(self, alert: TermStructureAlert) -> dict[str, Any]:
        """Format alert for Discord webhook.

        Args:
            alert: Alert to format.

        Returns:
            Discord message payload.
        """
        # Color based on severity
        color_map = {
            "INFO": 0x3498DB,     # Blue
            "WARNING": 0xF39C12,  # Orange
            "CRITICAL": 0xE74C3C,  # Red
        }
        color = color_map.get(alert.severity, 0x95A5A6)

        # Emoji based on alert type
        emoji_map = {
            TermStructureAlertType.REGIME_CHANGE: "🔄",
            TermStructureAlertType.HIGH_INTENSITY: "⚠️",
            TermStructureAlertType.EXTREME_ROLL_YIELD: "📊",
        }
        emoji = emoji_map.get(alert.alert_type, "📢")

        return {
            "embeds": [{
                "title": f"{emoji} Oil Term Structure Alert",
                "description": alert.message,
                "color": color,
                "fields": [
                    {"name": "Curve Shape", "value": alert.curve_shape, "inline": True},
                    {"name": "Intensity", "value": f"{alert.intensity:.0f}/100", "inline": True},
                    {"name": "Severity", "value": alert.severity, "inline": True},
                ],
                "timestamp": alert.timestamp.isoformat(),
            }]
        }

    async def send_alert(self, alert: TermStructureAlert) -> bool:
        """Send alert to Discord.

        Args:
            alert: Alert to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.discord_webhook:
            logger.warning("Discord webhook not configured, skipping alert")
            return False

        message = self.format_discord_message(alert)

        try:
            if self._http_client is None:
                self._http_client = httpx.AsyncClient()

            response = await self._http_client.post(
                self.discord_webhook,
                json=message,
                timeout=10.0,
            )

            if response.status_code == 204:
                logger.info("Sent term structure alert: %s", alert.alert_type.value)
                return True
            else:
                logger.warning(
                    "Discord webhook returned %d: %s",
                    response.status_code,
                    response.text,
                )
                return False

        except Exception as e:
            logger.error("Failed to send Discord alert: %s", e)
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    def reset_state(self) -> None:
        """Reset alert state (for testing)."""
        self._last_shape = None
