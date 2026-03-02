"""Positioning alert system for CFTC COT extreme conditions.

Generates alerts when speculator or commercial positioning reaches extreme
levels based on historical percentile ranks.

Alert Types:
- SPEC_EXTREME_LONG: Speculators crowded long (reversal risk)
- SPEC_EXTREME_SHORT: Speculators crowded short (squeeze risk)
- COMM_EXTREME_LONG: Smart money bullish (trend confirmation)
- COMM_EXTREME_SHORT: Smart money bearish (trend confirmation)
- COMM_SPEC_DIVERGENCE: Smart money disagrees with speculators

Reference: Sentiment analysis based on CFTC Commitment of Traders report.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PositioningAlertType(Enum):
    """Types of positioning alerts."""

    SPEC_EXTREME_LONG = "spec_extreme_long"  # Speculators crowded long
    SPEC_EXTREME_SHORT = "spec_extreme_short"  # Speculators crowded short
    COMM_EXTREME_LONG = "comm_extreme_long"  # Commercials bullish
    COMM_EXTREME_SHORT = "comm_extreme_short"  # Commercials bearish
    COMM_SPEC_DIVERGENCE = "comm_spec_divergence"  # Smart vs dumb money disagree


@dataclass
class PositioningAlert:
    """Container for a positioning alert."""

    alert_type: PositioningAlertType
    commodity: str
    timestamp: datetime
    spec_percentile: float
    comm_percentile: float
    message: str
    severity: str  # "warning" or "critical"

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_type": self.alert_type.value,
            "commodity": self.commodity,
            "timestamp": self.timestamp.isoformat(),
            "spec_percentile": self.spec_percentile,
            "comm_percentile": self.comm_percentile,
            "message": self.message,
            "severity": self.severity,
        }

    def to_discord_embed(self) -> dict[str, Any]:
        """Format alert for Discord webhook.

        Returns:
            Discord embed dict with title, description, color, fields, timestamp.
        """
        color_map = {
            "warning": 0xFFA500,  # Orange
            "critical": 0xFF0000,  # Red
        }

        emoji_map = {
            PositioningAlertType.SPEC_EXTREME_LONG: "📈",
            PositioningAlertType.SPEC_EXTREME_SHORT: "📉",
            PositioningAlertType.COMM_EXTREME_LONG: "🔵",
            PositioningAlertType.COMM_EXTREME_SHORT: "🔴",
            PositioningAlertType.COMM_SPEC_DIVERGENCE: "⚡",
        }

        return {
            "title": f"{emoji_map.get(self.alert_type, '📊')} {self.commodity} Positioning Alert",
            "description": self.message,
            "color": color_map.get(self.severity, 0x808080),
            "fields": [
                {
                    "name": "Speculator Percentile",
                    "value": f"{self.spec_percentile:.1f}%",
                    "inline": True,
                },
                {
                    "name": "Commercial Percentile",
                    "value": f"{self.comm_percentile:.1f}%",
                    "inline": True,
                },
                {
                    "name": "Alert Type",
                    "value": self.alert_type.value,
                    "inline": True,
                },
            ],
            "timestamp": self.timestamp.isoformat(),
        }


class PositioningAlertEngine:
    """Engine for generating positioning alerts.

    Monitors speculator and commercial positioning percentiles and generates
    alerts when extreme conditions are detected.

    Example:
        engine = PositioningAlertEngine(discord_webhook_url="https://...")

        # Check for extremes
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=95.0,
            comm_percentile=15.0,
            timestamp=datetime.now(UTC),
        )

        # Send alerts
        await engine.send_alerts(alerts)
    """

    # Default thresholds
    THRESHOLDS = {
        "extreme_high": 90,
        "extreme_low": 10,
        "critical_high": 95,
        "critical_low": 5,
        "divergence_high": 70,
        "divergence_low": 30,
    }

    # Dedup window (prevent spam)
    DEDUP_HOURS = 168  # 1 week

    def __init__(
        self,
        discord_webhook_url: str | None = None,
        thresholds: dict[str, int] | None = None,
        dedup_hours: int = 168,
    ) -> None:
        """Initialize positioning alert engine.

        Args:
            discord_webhook_url: Discord webhook URL for notifications.
            thresholds: Custom threshold overrides.
            dedup_hours: Hours to wait before re-alerting same commodity.
        """
        self.webhook_url = discord_webhook_url
        self.dedup_hours = dedup_hours
        self._last_alerts: dict[str, datetime] = {}  # Dedup by commodity+type

        if thresholds:
            self.THRESHOLDS = {**self.THRESHOLDS, **thresholds}

    def _dedup_key(self, commodity: str, alert_type: PositioningAlertType) -> str:
        """Generate dedup key for alert."""
        return f"{commodity}:{alert_type.value}"

    def _should_alert(
        self, commodity: str, alert_type: PositioningAlertType
    ) -> bool:
        """Check if alert should be sent (dedup check).

        Args:
            commodity: Commodity code.
            alert_type: Type of alert.

        Returns:
            True if alert should be sent (not deduplicated).
        """
        key = self._dedup_key(commodity, alert_type)
        last_alert = self._last_alerts.get(key)

        if last_alert is None:
            return True

        window = timedelta(hours=self.dedup_hours)
        return datetime.now(UTC) - last_alert > window

    def _record_alert(
        self, commodity: str, alert_type: PositioningAlertType
    ) -> None:
        """Record that an alert was sent for dedup tracking."""
        key = self._dedup_key(commodity, alert_type)
        self._last_alerts[key] = datetime.now(UTC)

    def _create_alert(
        self,
        alert_type: PositioningAlertType,
        commodity: str,
        timestamp: datetime,
        spec_percentile: float,
        comm_percentile: float,
        message: str,
        severity: str,
    ) -> PositioningAlert:
        """Create a positioning alert."""
        return PositioningAlert(
            alert_type=alert_type,
            commodity=commodity,
            timestamp=timestamp,
            spec_percentile=spec_percentile,
            comm_percentile=comm_percentile,
            message=message,
            severity=severity,
        )

    def _try_emit_alert(
        self,
        alert_type: PositioningAlertType,
        commodity: str,
        timestamp: datetime,
        spec_percentile: float,
        comm_percentile: float,
        message: str,
        severity: str,
        skip_dedup: bool,
        alerts: list[PositioningAlert],
    ) -> None:
        """Emit an alert if dedup allows it."""
        if skip_dedup or self._should_alert(commodity, alert_type):
            alerts.append(
                self._create_alert(
                    alert_type, commodity, timestamp,
                    spec_percentile, comm_percentile, message, severity,
                )
            )
            self._record_alert(commodity, alert_type)

    def check_extremes(
        self,
        commodity: str,
        spec_percentile: float,
        comm_percentile: float,
        timestamp: datetime | None = None,
        skip_dedup: bool = False,
    ) -> list[PositioningAlert]:
        """Check for extreme positioning and generate alerts.

        Args:
            commodity: Commodity code (e.g., "WTI", "GOLD").
            spec_percentile: Speculator net position percentile (0-100).
            comm_percentile: Commercial net position percentile (0-100).
            timestamp: Alert timestamp. Defaults to now.
            skip_dedup: If True, skip deduplication checks.

        Returns:
            List of PositioningAlert objects for detected extremes.
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        alerts: list[PositioningAlert] = []

        def emit(at: PositioningAlertType, msg: str, sev: str) -> None:
            self._try_emit_alert(
                at, commodity, timestamp, spec_percentile, comm_percentile, msg, sev, skip_dedup, alerts,
            )

        # Speculator extremes (higher priority)
        if spec_percentile >= self.THRESHOLDS["critical_high"]:
            emit(PositioningAlertType.SPEC_EXTREME_LONG,
                 f"Speculators at {spec_percentile:.1f}th percentile - CROWDED LONG", "critical")
        elif spec_percentile >= self.THRESHOLDS["extreme_high"]:
            emit(PositioningAlertType.SPEC_EXTREME_LONG,
                 f"Speculators at {spec_percentile:.1f}th percentile - elevated long", "warning")
        elif spec_percentile <= self.THRESHOLDS["critical_low"]:
            emit(PositioningAlertType.SPEC_EXTREME_SHORT,
                 f"Speculators at {spec_percentile:.1f}th percentile - CROWDED SHORT", "critical")
        elif spec_percentile <= self.THRESHOLDS["extreme_low"]:
            emit(PositioningAlertType.SPEC_EXTREME_SHORT,
                 f"Speculators at {spec_percentile:.1f}th percentile - elevated short", "warning")

        # Commercial extremes (less frequent, higher signal value)
        if comm_percentile >= self.THRESHOLDS["extreme_high"]:
            emit(PositioningAlertType.COMM_EXTREME_LONG,
                 f"Commercials at {comm_percentile:.1f}th percentile - SMART MONEY BULLISH", "critical")
        elif comm_percentile <= self.THRESHOLDS["extreme_low"]:
            emit(PositioningAlertType.COMM_EXTREME_SHORT,
                 f"Commercials at {comm_percentile:.1f}th percentile - SMART MONEY BEARISH", "critical")

        # Divergence (specs bullish, comms bearish or vice versa)
        if (spec_percentile >= self.THRESHOLDS["divergence_high"]
                and comm_percentile <= self.THRESHOLDS["divergence_low"]):
            emit(PositioningAlertType.COMM_SPEC_DIVERGENCE,
                 "Smart money vs speculators DIVERGING - commercials bearish while specs bullish", "warning")
        elif (spec_percentile <= self.THRESHOLDS["divergence_low"]
                and comm_percentile >= self.THRESHOLDS["divergence_high"]):
            emit(PositioningAlertType.COMM_SPEC_DIVERGENCE,
                 "Smart money vs speculators DIVERGING - commercials bullish while specs bearish", "warning")

        return alerts

    def check_all_commodities(
        self,
        percentile_data: dict[str, dict[str, float]],
        timestamp: datetime | None = None,
    ) -> list[PositioningAlert]:
        """Check extremes for multiple commodities.

        Args:
            percentile_data: Dict mapping commodity to {spec_pctl, comm_pctl}.
            timestamp: Alert timestamp.

        Returns:
            List of all generated alerts.
        """
        all_alerts = []

        for commodity, data in percentile_data.items():
            alerts = self.check_extremes(
                commodity=commodity,
                spec_percentile=data.get("spec_pctl", 50.0),
                comm_percentile=data.get("comm_pctl", 50.0),
                timestamp=timestamp,
            )
            all_alerts.extend(alerts)

        return all_alerts

    async def send_alerts(self, alerts: list[PositioningAlert]) -> bool:
        """Send alerts to Discord webhook.

        Args:
            alerts: List of alerts to send.

        Returns:
            True if alerts were sent successfully.
        """
        if not self.webhook_url or not alerts:
            return False

        embeds = [alert.to_discord_embed() for alert in alerts]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json={"embeds": embeds},
                )
                response.raise_for_status()
                logger.info("Sent %d positioning alerts to Discord", len(alerts))
                return True
        except httpx.HTTPError as e:
            logger.error("Failed to send positioning alerts: %s", e)
            return False

    def reset_dedup(self, commodity: str | None = None) -> None:
        """Reset deduplication state.

        Args:
            commodity: Optional commodity to reset. If None, resets all.
        """
        if commodity is None:
            self._last_alerts.clear()
        else:
            keys_to_remove = [
                k for k in self._last_alerts if k.startswith(f"{commodity}:")
            ]
            for key in keys_to_remove:
                del self._last_alerts[key]

    def get_alert_history(self) -> dict[str, datetime]:
        """Get dedup history showing last alert times.

        Returns:
            Dict mapping commodity:alert_type to last alert datetime.
        """
        return dict(self._last_alerts)
