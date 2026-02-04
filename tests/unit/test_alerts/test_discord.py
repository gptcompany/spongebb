"""Tests for Discord client."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from liquidity.alerts.discord import (
    DiscordClient,
    DiscordConfig,
    create_discord_client,
)


class TestDiscordConfig:
    """Tests for DiscordConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")

        assert config.webhook_url == "https://example.com/webhook"
        assert config.username == "Liquidity Monitor"
        assert config.avatar_url is None
        assert config.rate_limit_seconds == 60

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = DiscordConfig(
            webhook_url="https://example.com/webhook",
            username="Custom Bot",
            avatar_url="https://example.com/avatar.png",
            rate_limit_seconds=120,
        )

        assert config.username == "Custom Bot"
        assert config.avatar_url == "https://example.com/avatar.png"
        assert config.rate_limit_seconds == 120


class TestDiscordClient:
    """Tests for DiscordClient class."""

    def test_is_configured_with_url(self) -> None:
        """Test is_configured returns True when URL is set."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        assert client.is_configured is True

    def test_is_configured_without_url(self) -> None:
        """Test is_configured returns False when URL is empty."""
        config = DiscordConfig(webhook_url="")
        client = DiscordClient(config=config)

        assert client.is_configured is False

    def test_set_rate_limit(self) -> None:
        """Test setting rate limit for specific alert type."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        client.set_rate_limit("test_alert", 120)

        assert client.get_rate_limit("test_alert") == 120

    def test_get_rate_limit_default(self) -> None:
        """Test getting default rate limit for unknown alert type."""
        config = DiscordConfig(webhook_url="https://example.com/webhook", rate_limit_seconds=60)
        client = DiscordClient(config=config)

        assert client.get_rate_limit("unknown_alert") == 60

    def test_can_send_first_time(self) -> None:
        """Test can_send returns True for first alert."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        assert client.can_send("test_alert") is True

    def test_can_send_not_configured(self) -> None:
        """Test can_send returns False when not configured."""
        config = DiscordConfig(webhook_url="")
        client = DiscordClient(config=config)

        assert client.can_send("test_alert") is False

    def test_can_send_after_rate_limit(self) -> None:
        """Test can_send returns False during rate limit."""
        config = DiscordConfig(webhook_url="https://example.com/webhook", rate_limit_seconds=60)
        client = DiscordClient(config=config)

        # Simulate previous send
        client._last_sent["test_alert"] = datetime.now(UTC)

        assert client.can_send("test_alert") is False

    def test_can_send_after_rate_limit_expired(self) -> None:
        """Test can_send returns True after rate limit expires."""
        config = DiscordConfig(webhook_url="https://example.com/webhook", rate_limit_seconds=60)
        client = DiscordClient(config=config)

        # Simulate old send
        client._last_sent["test_alert"] = datetime.now(UTC) - timedelta(seconds=61)

        assert client.can_send("test_alert") is True

    def test_time_until_can_send_first_time(self) -> None:
        """Test time_until_can_send returns 0 for first alert."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        assert client.time_until_can_send("test_alert") == 0.0

    def test_time_until_can_send_during_rate_limit(self) -> None:
        """Test time_until_can_send returns remaining time."""
        config = DiscordConfig(webhook_url="https://example.com/webhook", rate_limit_seconds=60)
        client = DiscordClient(config=config)

        client._last_sent["test_alert"] = datetime.now(UTC) - timedelta(seconds=30)
        remaining = client.time_until_can_send("test_alert")

        # Should be approximately 30 seconds
        assert 29 <= remaining <= 31

    def test_reset_rate_limit(self) -> None:
        """Test resetting rate limit for specific alert type."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        client._last_sent["test_alert"] = datetime.now(UTC)
        client.reset_rate_limit("test_alert")

        assert "test_alert" not in client._last_sent

    def test_reset_all_rate_limits(self) -> None:
        """Test resetting all rate limits."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        client._last_sent["alert1"] = datetime.now(UTC)
        client._last_sent["alert2"] = datetime.now(UTC)
        client.reset_all_rate_limits()

        assert len(client._last_sent) == 0

    def test_get_last_sent(self) -> None:
        """Test getting last sent timestamp."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        now = datetime.now(UTC)
        client._last_sent["test_alert"] = now

        assert client.get_last_sent("test_alert") == now
        assert client.get_last_sent("unknown_alert") is None

    def test_send_embed_not_configured(self) -> None:
        """Test send_embed returns False when not configured."""
        config = DiscordConfig(webhook_url="")
        client = DiscordClient(config=config)

        mock_embed = MagicMock()
        result = client.send_embed(mock_embed, "test_alert")

        assert result is False

    def test_send_embed_rate_limited(self) -> None:
        """Test send_embed returns False when rate limited."""
        config = DiscordConfig(webhook_url="https://example.com/webhook", rate_limit_seconds=60)
        client = DiscordClient(config=config)

        client._last_sent["test_alert"] = datetime.now(UTC)

        mock_embed = MagicMock()
        result = client.send_embed(mock_embed, "test_alert")

        assert result is False

    @patch("liquidity.alerts.discord.DiscordWebhook")
    def test_send_embed_success(self, mock_webhook_class: MagicMock) -> None:
        """Test send_embed returns True on success."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_webhook = MagicMock()
        mock_webhook.execute.return_value = mock_response
        mock_webhook_class.return_value = mock_webhook

        mock_embed = MagicMock()
        result = client.send_embed(mock_embed, "test_alert")

        assert result is True
        assert "test_alert" in client._last_sent
        mock_webhook.add_embed.assert_called_once_with(mock_embed)

    @patch("liquidity.alerts.discord.DiscordWebhook")
    def test_send_embed_failure(self, mock_webhook_class: MagicMock) -> None:
        """Test send_embed returns False on failure."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_webhook = MagicMock()
        mock_webhook.execute.return_value = mock_response
        mock_webhook_class.return_value = mock_webhook

        mock_embed = MagicMock()
        result = client.send_embed(mock_embed, "test_alert")

        assert result is False
        assert "test_alert" not in client._last_sent

    @patch("liquidity.alerts.discord.DiscordWebhook")
    def test_send_embed_exception(self, mock_webhook_class: MagicMock) -> None:
        """Test send_embed handles exceptions gracefully."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        # Mock exception
        mock_webhook = MagicMock()
        mock_webhook.execute.side_effect = Exception("Network error")
        mock_webhook_class.return_value = mock_webhook

        mock_embed = MagicMock()
        result = client.send_embed(mock_embed, "test_alert")

        assert result is False

    def test_repr(self) -> None:
        """Test string representation."""
        config = DiscordConfig(webhook_url="https://example.com/webhook", rate_limit_seconds=60)
        client = DiscordClient(config=config)

        assert "configured" in repr(client)
        assert "60s" in repr(client)


class TestCreateDiscordClient:
    """Tests for create_discord_client factory function."""

    def test_create_with_url(self) -> None:
        """Test creating client with URL."""
        client = create_discord_client(
            webhook_url="https://example.com/webhook",
            username="Test Bot",
        )

        assert client.is_configured is True
        assert client.config.username == "Test Bot"

    @patch.dict("os.environ", {"LIQUIDITY_DISCORD_WEBHOOK_URL": "https://env.com/webhook"})
    def test_create_from_env(self) -> None:
        """Test creating client from environment variable."""
        client = create_discord_client()

        assert client.is_configured is True
        assert client.config.webhook_url == "https://env.com/webhook"

    def test_create_without_url(self) -> None:
        """Test creating client without URL."""
        with patch.dict("os.environ", {}, clear=True):
            client = create_discord_client()

            assert client.is_configured is False


class TestDiscordClientAsync:
    """Tests for async Discord client methods."""

    @pytest.mark.asyncio
    async def test_send_embed_async_not_configured(self) -> None:
        """Test async send_embed returns False when not configured."""
        config = DiscordConfig(webhook_url="")
        client = DiscordClient(config=config)

        mock_embed = MagicMock()
        result = await client.send_embed_async(mock_embed, "test_alert")

        assert result is False

    @pytest.mark.asyncio
    async def test_send_embed_async_rate_limited(self) -> None:
        """Test async send_embed returns False when rate limited."""
        config = DiscordConfig(webhook_url="https://example.com/webhook", rate_limit_seconds=60)
        client = DiscordClient(config=config)

        client._last_sent["test_alert"] = datetime.now(UTC)

        mock_embed = MagicMock()
        result = await client.send_embed_async(mock_embed, "test_alert")

        assert result is False

    @pytest.mark.asyncio
    @patch("liquidity.alerts.discord.AsyncDiscordWebhook")
    async def test_send_embed_async_success(self, mock_webhook_class: MagicMock) -> None:
        """Test async send_embed returns True on success."""
        config = DiscordConfig(webhook_url="https://example.com/webhook")
        client = DiscordClient(config=config)

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_webhook = MagicMock()
        mock_webhook.execute = AsyncMock(return_value=mock_response)
        mock_webhook_class.return_value = mock_webhook

        mock_embed = MagicMock()
        result = await client.send_embed_async(mock_embed, "test_alert")

        assert result is True
        assert "test_alert" in client._last_sent
