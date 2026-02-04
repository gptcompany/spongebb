"""Tests for alert handlers."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from liquidity.alerts.config import AlertConfig, RateLimits, StressThresholds
from liquidity.alerts.discord import DiscordClient, DiscordConfig
from liquidity.alerts.formatter import LiquidityMetrics
from liquidity.alerts.handlers import AlertHandlers, AlertState


@pytest.fixture
def mock_discord_client() -> MagicMock:
    """Create mock Discord client."""
    client = MagicMock(spec=DiscordClient)
    client.send_embed.return_value = True
    client.send_embed_async = MagicMock(return_value=True)
    return client


@pytest.fixture
def alert_config() -> AlertConfig:
    """Create test alert configuration."""
    return AlertConfig(
        enabled=True,
        discord_webhook_url="https://example.com/webhook",
        dxy_move_threshold_pct=1.0,
        correlation_shift_threshold=0.3,
        stress_thresholds=StressThresholds(),
        rate_limits=RateLimits(),
    )


@pytest.fixture
def handlers(mock_discord_client: MagicMock, alert_config: AlertConfig) -> AlertHandlers:
    """Create alert handlers with mock client."""
    return AlertHandlers(mock_discord_client, alert_config)


class TestAlertState:
    """Tests for AlertState dataclass."""

    def test_default_state(self) -> None:
        """Test default state values."""
        state = AlertState()

        assert state.previous_regime is None
        assert state.previous_regime_intensity == 0.0
        assert state.previous_dxy is None
        assert state.previous_correlations == {}
        assert state.previous_stress_alerts == {}

    def test_mutable_fields_initialized(self) -> None:
        """Test that mutable fields are properly initialized."""
        state1 = AlertState()
        state2 = AlertState()

        # Should be different objects
        assert state1.previous_correlations is not state2.previous_correlations


class TestAlertHandlersInit:
    """Tests for AlertHandlers initialization."""

    def test_init_sets_rate_limits(
        self, mock_discord_client: MagicMock, alert_config: AlertConfig
    ) -> None:
        """Test that rate limits are set on initialization."""
        handlers = AlertHandlers(mock_discord_client, alert_config)

        mock_discord_client.set_rate_limit.assert_any_call("regime_change", 60)
        mock_discord_client.set_rate_limit.assert_any_call("stress_breach", 300)
        mock_discord_client.set_rate_limit.assert_any_call("dxy_move", 3600)
        mock_discord_client.set_rate_limit.assert_any_call("correlation_shift", 3600)


class TestRegimeChangeHandler:
    """Tests for regime change alert handler."""

    def test_first_regime_no_alert(self, handlers: AlertHandlers) -> None:
        """Test that first regime doesn't trigger alert."""
        result = handlers.check_regime_change(
            direction="EXPANSION",
            intensity=72,
            confidence="HIGH",
        )

        assert result is False
        assert handlers.state.previous_regime == "EXPANSION"

    def test_regime_change_triggers_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that regime change triggers alert."""
        # Set previous regime
        handlers.state.previous_regime = "EXPANSION"
        handlers.state.previous_regime_intensity = 72

        result = handlers.check_regime_change(
            direction="CONTRACTION",
            intensity=35,
            confidence="HIGH",
        )

        assert result is True
        mock_discord_client.send_embed.assert_called_once()
        assert handlers.state.previous_regime == "CONTRACTION"

    def test_same_regime_no_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that same regime doesn't trigger alert."""
        handlers.state.previous_regime = "EXPANSION"

        result = handlers.check_regime_change(
            direction="EXPANSION",
            intensity=80,
            confidence="HIGH",
        )

        assert result is False
        mock_discord_client.send_embed.assert_not_called()

    def test_disabled_no_alert(
        self, mock_discord_client: MagicMock
    ) -> None:
        """Test that disabled config doesn't trigger alert."""
        config = AlertConfig(enabled=False)
        handlers = AlertHandlers(mock_discord_client, config)

        handlers.state.previous_regime = "EXPANSION"

        result = handlers.check_regime_change(
            direction="CONTRACTION",
            intensity=35,
            confidence="HIGH",
        )

        assert result is False
        mock_discord_client.send_embed.assert_not_called()

    def test_regime_change_with_metrics(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test regime change with metrics included."""
        handlers.state.previous_regime = "EXPANSION"

        metrics = LiquidityMetrics(
            net_liquidity=5.8,
            net_liquidity_change=-120,
        )

        result = handlers.check_regime_change(
            direction="CONTRACTION",
            intensity=35,
            confidence="HIGH",
            metrics=metrics,
        )

        assert result is True


class TestStressBreachHandler:
    """Tests for stress breach alert handler."""

    def test_no_breach_no_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that no breach doesn't trigger alert."""
        result = handlers.check_stress_breach(
            indicator="sofr_ois",
            value=5.0,  # Below elevated threshold
        )

        assert result is False
        mock_discord_client.send_embed.assert_not_called()

    def test_elevated_breach_triggers_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that elevated breach triggers alert."""
        result = handlers.check_stress_breach(
            indicator="sofr_ois",
            value=15.0,  # Above elevated (10), below critical (25)
        )

        assert result is True
        mock_discord_client.send_embed.assert_called_once()
        assert handlers.state.previous_stress_alerts["sofr_ois"] == "elevated"

    def test_critical_breach_triggers_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that critical breach triggers alert."""
        result = handlers.check_stress_breach(
            indicator="sofr_ois",
            value=30.0,  # Above critical (25)
        )

        assert result is True
        assert handlers.state.previous_stress_alerts["sofr_ois"] == "critical"

    def test_same_severity_no_repeat_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that same severity doesn't repeat alert."""
        handlers.state.previous_stress_alerts["sofr_ois"] = "elevated"

        result = handlers.check_stress_breach(
            indicator="sofr_ois",
            value=15.0,
        )

        assert result is False
        mock_discord_client.send_embed.assert_not_called()

    def test_severity_upgrade_triggers_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that severity upgrade triggers new alert."""
        handlers.state.previous_stress_alerts["sofr_ois"] = "elevated"

        result = handlers.check_stress_breach(
            indicator="sofr_ois",
            value=30.0,  # Critical
        )

        assert result is True
        assert handlers.state.previous_stress_alerts["sofr_ois"] == "critical"

    def test_return_to_normal_clears_state(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that return to normal clears alert state."""
        handlers.state.previous_stress_alerts["sofr_ois"] = "elevated"

        result = handlers.check_stress_breach(
            indicator="sofr_ois",
            value=5.0,  # Normal
        )

        assert result is False
        assert "sofr_ois" not in handlers.state.previous_stress_alerts

    def test_custom_thresholds(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test custom threshold values."""
        result = handlers.check_stress_breach(
            indicator="custom_indicator",
            value=50.0,
            elevated_threshold=40.0,
            critical_threshold=80.0,
        )

        assert result is True


class TestDxyMoveHandler:
    """Tests for DXY move alert handler."""

    def test_first_dxy_no_alert(self, handlers: AlertHandlers) -> None:
        """Test that first DXY value doesn't trigger alert."""
        result = handlers.check_dxy_move(current_dxy=104.5)

        assert result is False
        assert handlers.state.previous_dxy == 104.5

    def test_small_move_no_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that small move doesn't trigger alert."""
        handlers.state.previous_dxy = 104.0

        result = handlers.check_dxy_move(current_dxy=104.5)  # ~0.5% change

        assert result is False
        mock_discord_client.send_embed.assert_not_called()

    def test_large_move_triggers_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that large move triggers alert."""
        handlers.state.previous_dxy = 100.0

        result = handlers.check_dxy_move(current_dxy=102.0)  # 2% change

        assert result is True
        mock_discord_client.send_embed.assert_called_once()

    def test_provided_change_pct(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test using provided change percentage."""
        result = handlers.check_dxy_move(current_dxy=105.0, change_pct=1.5)

        assert result is True

    def test_negative_move_triggers_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that negative move also triggers alert."""
        handlers.state.previous_dxy = 100.0

        result = handlers.check_dxy_move(current_dxy=98.0)  # -2% change

        assert result is True


class TestCorrelationShiftHandler:
    """Tests for correlation shift alert handler."""

    def test_first_correlation_no_alert(self, handlers: AlertHandlers) -> None:
        """Test that first correlation doesn't trigger alert."""
        result = handlers.check_correlation_shift(
            asset="BTC",
            current_corr=0.5,
        )

        assert result is False
        assert handlers.state.previous_correlations["BTC"] == 0.5

    def test_small_shift_no_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that small shift doesn't trigger alert."""
        handlers.state.previous_correlations["BTC"] = 0.5

        result = handlers.check_correlation_shift(
            asset="BTC",
            current_corr=0.55,  # 0.05 change
        )

        assert result is False
        mock_discord_client.send_embed.assert_not_called()

    def test_large_shift_triggers_alert(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test that large shift triggers alert."""
        handlers.state.previous_correlations["BTC"] = 0.5

        result = handlers.check_correlation_shift(
            asset="BTC",
            current_corr=0.1,  # -0.4 change
        )

        assert result is True
        mock_discord_client.send_embed.assert_called_once()

    def test_multiple_correlations(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test checking multiple correlations."""
        handlers.state.previous_correlations = {
            "BTC": 0.5,
            "SPX": 0.3,
        }

        alerts = handlers.check_multiple_correlations({
            "BTC": 0.6,  # Small change
            "SPX": -0.1,  # Large change
        })

        assert alerts == 1  # Only SPX should trigger


class TestAlertHandlersAsync:
    """Tests for async alert handler methods."""

    @pytest.mark.asyncio
    async def test_regime_change_async(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test async regime change handler."""
        from unittest.mock import AsyncMock

        mock_discord_client.send_embed_async = AsyncMock(return_value=True)
        handlers.state.previous_regime = "EXPANSION"

        result = await handlers.check_regime_change_async(
            direction="CONTRACTION",
            intensity=35,
            confidence="HIGH",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_stress_breach_async(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test async stress breach handler."""
        from unittest.mock import AsyncMock

        mock_discord_client.send_embed_async = AsyncMock(return_value=True)

        result = await handlers.check_stress_breach_async(
            indicator="sofr_ois",
            value=30.0,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_dxy_move_async(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test async DXY move handler."""
        from unittest.mock import AsyncMock

        mock_discord_client.send_embed_async = AsyncMock(return_value=True)

        result = await handlers.check_dxy_move_async(
            current_dxy=105.0,
            change_pct=1.5,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_correlation_shift_async(
        self, handlers: AlertHandlers, mock_discord_client: MagicMock
    ) -> None:
        """Test async correlation shift handler."""
        from unittest.mock import AsyncMock

        mock_discord_client.send_embed_async = AsyncMock(return_value=True)
        handlers.state.previous_correlations["BTC"] = 0.5

        result = await handlers.check_correlation_shift_async(
            asset="BTC",
            current_corr=0.1,
        )

        assert result is True


class TestAlertHandlersUtilities:
    """Tests for alert handler utility methods."""

    def test_reset_state(self, handlers: AlertHandlers) -> None:
        """Test resetting state."""
        handlers.state.previous_regime = "EXPANSION"
        handlers.state.previous_dxy = 104.5
        handlers.state.previous_correlations["BTC"] = 0.5

        handlers.reset_state()

        assert handlers.state.previous_regime is None
        assert handlers.state.previous_dxy is None
        assert handlers.state.previous_correlations == {}

    def test_repr(self, handlers: AlertHandlers) -> None:
        """Test string representation."""
        repr_str = repr(handlers)

        assert "AlertHandlers" in repr_str
        assert "enabled=True" in repr_str
