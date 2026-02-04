"""Alert configuration with thresholds and rate limits.

Defines configurable thresholds for all alert types:
- Regime changes
- Stress indicator breaches
- DXY significant moves
- Correlation regime shifts
"""

import os
from dataclasses import dataclass, field


@dataclass
class StressThresholds:
    """Thresholds for stress indicator alerts.

    Values in basis points for spreads, percent for ratios.
    """

    # SOFR-OIS spread thresholds (basis points)
    sofr_ois_elevated: float = 10.0  # Warning level
    sofr_ois_critical: float = 25.0  # Critical level

    # SOFR distribution width thresholds (basis points)
    sofr_width_elevated: float = 20.0
    sofr_width_critical: float = 50.0

    # Repo stress ratio thresholds (percent)
    repo_stress_elevated: float = 1.0
    repo_stress_critical: float = 3.0

    # CP-Treasury spread thresholds (basis points)
    cp_spread_elevated: float = 40.0
    cp_spread_critical: float = 100.0


@dataclass
class RateLimits:
    """Rate limits for each alert type (in seconds).

    Prevents alert spam by enforcing minimum time between alerts of the same type.
    """

    regime_change: int = 60  # 1 minute
    stress_breach: int = 300  # 5 minutes
    dxy_move: int = 3600  # 1 hour
    correlation_shift: int = 3600  # 1 hour

    # Default rate limit for unspecified alert types
    default: int = 60


@dataclass
class AlertConfig:
    """Main alert configuration.

    Attributes:
        enabled: Whether alerting is enabled globally.
        discord_webhook_url: Discord webhook URL for sending alerts.
        discord_username: Bot username displayed in Discord.
        discord_avatar_url: Optional avatar URL for the bot.
        dxy_move_threshold_pct: Minimum DXY change (%) to trigger alert.
        correlation_shift_threshold: Minimum correlation change to trigger alert.
        check_interval_seconds: Interval between alert checks.
        stress_thresholds: Thresholds for stress indicator alerts.
        rate_limits: Rate limits for each alert type.
    """

    enabled: bool = True
    discord_webhook_url: str = ""
    discord_username: str = "Liquidity Monitor"
    discord_avatar_url: str | None = None

    # Alert thresholds
    dxy_move_threshold_pct: float = 1.0
    correlation_shift_threshold: float = 0.3

    # Check interval
    check_interval_seconds: int = 300  # 5 minutes

    # Nested configurations
    stress_thresholds: StressThresholds = field(default_factory=StressThresholds)
    rate_limits: RateLimits = field(default_factory=RateLimits)


def load_alert_config() -> AlertConfig:
    """Load alert configuration from environment variables.

    Environment variables:
        LIQUIDITY_DISCORD_WEBHOOK_URL: Discord webhook URL (required for alerts)
        LIQUIDITY_ALERTS_ENABLED: Enable/disable alerts (default: true)
        LIQUIDITY_DISCORD_USERNAME: Bot username (default: Liquidity Monitor)
        LIQUIDITY_DXY_THRESHOLD: DXY move threshold % (default: 1.0)
        LIQUIDITY_CORR_THRESHOLD: Correlation shift threshold (default: 0.3)
        LIQUIDITY_ALERT_INTERVAL: Check interval in seconds (default: 300)

    Returns:
        AlertConfig instance with loaded configuration.
    """
    webhook_url = os.getenv("LIQUIDITY_DISCORD_WEBHOOK_URL", "")
    enabled = os.getenv("LIQUIDITY_ALERTS_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    # Disable if no webhook URL provided
    if not webhook_url:
        enabled = False

    return AlertConfig(
        enabled=enabled,
        discord_webhook_url=webhook_url,
        discord_username=os.getenv("LIQUIDITY_DISCORD_USERNAME", "Liquidity Monitor"),
        discord_avatar_url=os.getenv("LIQUIDITY_DISCORD_AVATAR_URL"),
        dxy_move_threshold_pct=float(os.getenv("LIQUIDITY_DXY_THRESHOLD", "1.0")),
        correlation_shift_threshold=float(os.getenv("LIQUIDITY_CORR_THRESHOLD", "0.3")),
        check_interval_seconds=int(os.getenv("LIQUIDITY_ALERT_INTERVAL", "300")),
    )
