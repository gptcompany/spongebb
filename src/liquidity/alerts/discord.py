"""Discord webhook client with rate limiting.

Provides a thread-safe Discord webhook client that respects rate limits
to prevent alert spam while ensuring important notifications are delivered.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from discord_webhook import AsyncDiscordWebhook, DiscordEmbed, DiscordWebhook

logger = logging.getLogger(__name__)


@dataclass
class DiscordConfig:
    """Discord webhook configuration.

    Attributes:
        webhook_url: Discord webhook URL.
        username: Bot username displayed in messages.
        avatar_url: Optional avatar URL for the bot.
        rate_limit_seconds: Default minimum seconds between same alert type.
    """

    webhook_url: str
    username: str = "Liquidity Monitor"
    avatar_url: str | None = None
    rate_limit_seconds: int = 60


@dataclass
class DiscordClient:
    """Discord webhook client with rate limiting.

    Sends Discord embeds via webhook with per-alert-type rate limiting
    to prevent notification spam.

    Example:
        config = DiscordConfig(webhook_url="https://discord.com/api/webhooks/...")
        client = DiscordClient(config)

        embed = DiscordEmbed(title="Test", description="Test message")
        success = await client.send_embed_async(embed, "test_alert")
    """

    config: DiscordConfig
    _last_sent: dict[str, datetime] = field(default_factory=dict)
    _type_rate_limits: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize mutable fields."""
        if self._last_sent is None:
            self._last_sent = {}
        if self._type_rate_limits is None:
            self._type_rate_limits = {}

    @property
    def is_configured(self) -> bool:
        """Check if Discord webhook is configured."""
        return bool(self.config.webhook_url)

    def set_rate_limit(self, alert_type: str, seconds: int) -> None:
        """Set rate limit for a specific alert type.

        Args:
            alert_type: Alert type identifier.
            seconds: Minimum seconds between alerts of this type.
        """
        self._type_rate_limits[alert_type] = seconds

    def get_rate_limit(self, alert_type: str) -> int:
        """Get rate limit for a specific alert type.

        Args:
            alert_type: Alert type identifier.

        Returns:
            Rate limit in seconds.
        """
        return self._type_rate_limits.get(alert_type, self.config.rate_limit_seconds)

    def can_send(self, alert_type: str) -> bool:
        """Check if an alert can be sent based on rate limiting.

        Args:
            alert_type: Alert type identifier.

        Returns:
            True if enough time has passed since last alert of this type.
        """
        if not self.is_configured:
            return False

        if alert_type not in self._last_sent:
            return True

        elapsed = (datetime.now(UTC) - self._last_sent[alert_type]).total_seconds()
        rate_limit = self.get_rate_limit(alert_type)

        return elapsed >= rate_limit

    def time_until_can_send(self, alert_type: str) -> float:
        """Get seconds until an alert can be sent.

        Args:
            alert_type: Alert type identifier.

        Returns:
            Seconds until rate limit expires (0 if can send now).
        """
        if alert_type not in self._last_sent:
            return 0.0

        elapsed = (datetime.now(UTC) - self._last_sent[alert_type]).total_seconds()
        rate_limit = self.get_rate_limit(alert_type)

        remaining = rate_limit - elapsed
        return max(0.0, remaining)

    def send_embed(self, embed: DiscordEmbed, alert_type: str) -> bool:
        """Send embed synchronously with rate limiting.

        Args:
            embed: Discord embed to send.
            alert_type: Alert type for rate limiting.

        Returns:
            True if embed was sent successfully, False if rate limited or failed.
        """
        if not self.can_send(alert_type):
            remaining = self.time_until_can_send(alert_type)
            logger.debug(
                "Rate limited: %s (%.0f seconds remaining)", alert_type, remaining
            )
            return False

        if not self.is_configured:
            logger.warning("Discord webhook not configured, skipping alert")
            return False

        try:
            webhook = DiscordWebhook(
                url=self.config.webhook_url,
                username=self.config.username,
                avatar_url=self.config.avatar_url,
            )
            webhook.add_embed(embed)
            response = webhook.execute()

            # Handle response - discord-webhook returns response object or list
            if response is None:
                logger.warning("Discord webhook returned None response")
                return False

            # response can be a list when using rate_limit_retry
            if isinstance(response, list):
                response = response[0] if response else None

            if response is not None and hasattr(response, "status_code"):
                if response.status_code in (200, 204):
                    self._last_sent[alert_type] = datetime.now(UTC)
                    logger.info("Discord alert sent: %s", alert_type)
                    return True
                else:
                    logger.warning(
                        "Discord webhook failed: %s - %s",
                        response.status_code,
                        getattr(response, "text", ""),
                    )
                    return False

            # If we got here, assume success (some versions don't return status)
            self._last_sent[alert_type] = datetime.now(UTC)
            logger.info("Discord alert sent: %s", alert_type)
            return True

        except Exception as e:
            logger.exception("Failed to send Discord alert: %s", e)
            return False

    async def send_embed_async(self, embed: DiscordEmbed, alert_type: str) -> bool:
        """Send embed asynchronously with rate limiting.

        Args:
            embed: Discord embed to send.
            alert_type: Alert type for rate limiting.

        Returns:
            True if embed was sent successfully, False if rate limited or failed.
        """
        if not self.can_send(alert_type):
            remaining = self.time_until_can_send(alert_type)
            logger.debug(
                "Rate limited: %s (%.0f seconds remaining)", alert_type, remaining
            )
            return False

        if not self.is_configured:
            logger.warning("Discord webhook not configured, skipping alert")
            return False

        try:
            webhook = AsyncDiscordWebhook(
                url=self.config.webhook_url,
                username=self.config.username,
                avatar_url=self.config.avatar_url,
            )
            webhook.add_embed(embed)
            response = await webhook.execute()

            # Handle response
            if response is None:
                logger.warning("Discord webhook returned None response")
                return False

            if isinstance(response, list):
                response = response[0] if response else None

            if response is not None and hasattr(response, "status_code"):
                if response.status_code in (200, 204):
                    self._last_sent[alert_type] = datetime.now(UTC)
                    logger.info("Discord alert sent: %s", alert_type)
                    return True
                else:
                    logger.warning(
                        "Discord webhook failed: %s - %s",
                        response.status_code,
                        getattr(response, "text", ""),
                    )
                    return False

            # Assume success if no status code
            self._last_sent[alert_type] = datetime.now(UTC)
            logger.info("Discord alert sent: %s", alert_type)
            return True

        except Exception as e:
            logger.exception("Failed to send Discord alert: %s", e)
            return False

    def reset_rate_limit(self, alert_type: str) -> None:
        """Reset rate limit for a specific alert type.

        Args:
            alert_type: Alert type to reset.
        """
        self._last_sent.pop(alert_type, None)

    def reset_all_rate_limits(self) -> None:
        """Reset all rate limits."""
        self._last_sent.clear()

    def get_last_sent(self, alert_type: str) -> datetime | None:
        """Get the timestamp of the last sent alert.

        Args:
            alert_type: Alert type to check.

        Returns:
            Datetime of last sent alert, or None if never sent.
        """
        return self._last_sent.get(alert_type)

    def __repr__(self) -> str:
        """Return string representation."""
        configured = "configured" if self.is_configured else "not configured"
        return f"DiscordClient({configured}, rate_limit={self.config.rate_limit_seconds}s)"


def create_discord_client(
    webhook_url: str | None = None,
    username: str = "Liquidity Monitor",
    rate_limit_seconds: int = 60,
) -> DiscordClient:
    """Factory function to create a Discord client.

    Args:
        webhook_url: Discord webhook URL. If None, reads from environment.
        username: Bot username.
        rate_limit_seconds: Default rate limit.

    Returns:
        Configured DiscordClient instance.
    """
    import os

    if webhook_url is None:
        webhook_url = os.getenv("LIQUIDITY_DISCORD_WEBHOOK_URL", "")

    config = DiscordConfig(
        webhook_url=webhook_url,
        username=username,
        rate_limit_seconds=rate_limit_seconds,
    )

    return DiscordClient(config=config)
