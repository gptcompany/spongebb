"""Tests for AlertManager high-level interface."""

import os
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from liquidity.alerts import (
    AlertManager,
    AlertConfig,
    DiscordClient,
    DiscordConfig,
    LiquidityMetrics,
)


@pytest.fixture
def mock_discord_client() -> MagicMock:
    """Create mock Discord client."""
    client = MagicMock(spec=DiscordClient)
    client.is_configured = True
    client.send_embed.return_value = True
    client.send_embed_async = AsyncMock(return_value=True)
    return client


@pytest.fixture
def alert_config() -> AlertConfig:
    """Create test alert configuration."""
    return AlertConfig(
        enabled=True,
        discord_webhook_url="https://example.com/webhook",
    )


class TestAlertManagerInit:
    """Tests for AlertManager initialization."""

    def test_init_with_config(self, alert_config: AlertConfig) -> None:
        """Test initialization with provided config."""
        manager = AlertManager(config=alert_config)

        assert manager.config == alert_config
        assert manager.is_enabled is True

    def test_init_with_discord_client(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test initialization with provided Discord client."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        assert manager.is_enabled is True

    def test_init_from_env(self) -> None:
        """Test initialization from environment."""
        with patch.dict(
            os.environ,
            {"LIQUIDITY_DISCORD_WEBHOOK_URL": "https://example.com/webhook"},
            clear=True,
        ):
            manager = AlertManager()

            assert manager.is_enabled is True

    def test_init_disabled_without_webhook(self) -> None:
        """Test that manager is disabled without webhook URL."""
        with patch.dict(os.environ, {}, clear=True):
            manager = AlertManager()

            assert manager.is_enabled is False


class TestAlertManagerProperties:
    """Tests for AlertManager properties."""

    def test_config_property(self, alert_config: AlertConfig) -> None:
        """Test config property."""
        manager = AlertManager(config=alert_config)

        assert manager.config == alert_config

    def test_handlers_property(self, alert_config: AlertConfig) -> None:
        """Test handlers property."""
        manager = AlertManager(config=alert_config)

        assert manager.handlers is not None

    def test_scheduler_property_before_start(self, alert_config: AlertConfig) -> None:
        """Test scheduler property before starting."""
        manager = AlertManager(config=alert_config)

        assert manager.scheduler is None


class TestAlertManagerSyncMethods:
    """Tests for synchronous AlertManager methods."""

    def test_check_regime_change(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test sync regime change check."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        # First call sets state
        manager.check_regime_change(
            direction="EXPANSION",
            intensity=72,
            confidence="HIGH",
        )

        # Second call with change
        result = manager.check_regime_change(
            direction="CONTRACTION",
            intensity=35,
            confidence="HIGH",
        )

        assert result is True
        mock_discord_client.send_embed.assert_called_once()

    def test_check_stress(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test sync stress check."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        result = manager.check_stress(
            indicator="sofr_ois",
            value=30.0,
        )

        assert result is True
        mock_discord_client.send_embed.assert_called_once()

    def test_check_dxy(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test sync DXY check."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        result = manager.check_dxy(current=105.0, change_pct=1.5)

        assert result is True
        mock_discord_client.send_embed.assert_called_once()

    def test_check_correlation(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test sync correlation check."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        # First call sets state
        manager.check_correlation(asset="BTC", correlation=0.5)

        # Second call with shift
        result = manager.check_correlation(asset="BTC", correlation=0.1)

        assert result is True


class TestAlertManagerAsyncMethods:
    """Tests for asynchronous AlertManager methods."""

    @pytest.mark.asyncio
    async def test_check_regime_change_async(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test async regime change check."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        # First call sets state
        await manager.check_regime_change_async(
            direction="EXPANSION",
            intensity=72,
            confidence="HIGH",
        )

        # Second call with change
        result = await manager.check_regime_change_async(
            direction="CONTRACTION",
            intensity=35,
            confidence="HIGH",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_stress_async(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test async stress check."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        result = await manager.check_stress_async(
            indicator="sofr_ois",
            value=30.0,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_dxy_async(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test async DXY check."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        result = await manager.check_dxy_async(current=105.0, change_pct=1.5)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_correlation_async(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test async correlation check."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        # First call sets state
        await manager.check_correlation_async(asset="BTC", correlation=0.5)

        # Second call with shift
        result = await manager.check_correlation_async(asset="BTC", correlation=0.1)

        assert result is True


class TestAlertManagerUtilities:
    """Tests for AlertManager utility methods."""

    def test_reset_state(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test resetting state."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        # Set some state
        manager.check_regime_change(
            direction="EXPANSION",
            intensity=72,
            confidence="HIGH",
        )

        manager.reset_state()

        # State should be cleared
        assert manager.handlers.state.previous_regime is None

    def test_repr_enabled(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test repr when enabled."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        assert "enabled" in repr(manager)

    def test_repr_disabled(self) -> None:
        """Test repr when disabled."""
        with patch.dict(os.environ, {}, clear=True):
            manager = AlertManager()

            assert "disabled" in repr(manager)

    def test_stop_scheduler_before_start(self, alert_config: AlertConfig) -> None:
        """Test stopping scheduler before it's started."""
        manager = AlertManager(config=alert_config)

        # Should not raise
        manager.stop_scheduler()


class TestAlertManagerWithMetrics:
    """Tests for AlertManager with LiquidityMetrics."""

    def test_regime_change_with_metrics(
        self, alert_config: AlertConfig, mock_discord_client: MagicMock
    ) -> None:
        """Test regime change with metrics."""
        manager = AlertManager(
            config=alert_config,
            discord_client=mock_discord_client,
        )

        metrics = LiquidityMetrics(
            net_liquidity=5.8,
            net_liquidity_change=-120,
            global_liquidity=28.2,
            global_liquidity_change=-450,
            dxy=104.5,
            dxy_change_pct=0.8,
        )

        # First call sets state
        manager.check_regime_change(
            direction="EXPANSION",
            intensity=72,
            confidence="HIGH",
            metrics=metrics,
        )

        # Second call with change
        result = manager.check_regime_change(
            direction="CONTRACTION",
            intensity=35,
            confidence="HIGH",
            metrics=metrics,
        )

        assert result is True
