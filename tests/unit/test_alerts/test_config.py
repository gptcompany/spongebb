"""Tests for alert configuration."""

import os
from unittest.mock import patch

from liquidity.alerts.config import (
    AlertConfig,
    RateLimits,
    StressThresholds,
    load_alert_config,
)


class TestStressThresholds:
    """Tests for StressThresholds dataclass."""

    def test_default_values(self) -> None:
        """Test default threshold values."""
        thresholds = StressThresholds()

        assert thresholds.sofr_ois_elevated == 10.0
        assert thresholds.sofr_ois_critical == 25.0
        assert thresholds.sofr_width_elevated == 20.0
        assert thresholds.sofr_width_critical == 50.0
        assert thresholds.repo_stress_elevated == 1.0
        assert thresholds.repo_stress_critical == 3.0
        assert thresholds.cp_spread_elevated == 40.0
        assert thresholds.cp_spread_critical == 100.0

    def test_custom_values(self) -> None:
        """Test custom threshold values."""
        thresholds = StressThresholds(
            sofr_ois_elevated=15.0,
            sofr_ois_critical=30.0,
        )

        assert thresholds.sofr_ois_elevated == 15.0
        assert thresholds.sofr_ois_critical == 30.0


class TestRateLimits:
    """Tests for RateLimits dataclass."""

    def test_default_values(self) -> None:
        """Test default rate limit values."""
        limits = RateLimits()

        assert limits.regime_change == 60
        assert limits.stress_breach == 300
        assert limits.dxy_move == 3600
        assert limits.correlation_shift == 3600
        assert limits.default == 60

    def test_custom_values(self) -> None:
        """Test custom rate limit values."""
        limits = RateLimits(
            regime_change=120,
            stress_breach=600,
        )

        assert limits.regime_change == 120
        assert limits.stress_breach == 600


class TestAlertConfig:
    """Tests for AlertConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = AlertConfig()

        assert config.enabled is True
        assert config.discord_webhook_url == ""
        assert config.discord_username == "Liquidity Monitor"
        assert config.discord_avatar_url is None
        assert config.dxy_move_threshold_pct == 1.0
        assert config.correlation_shift_threshold == 0.3
        assert config.check_interval_seconds == 300

    def test_nested_defaults(self) -> None:
        """Test that nested configs are initialized."""
        config = AlertConfig()

        assert isinstance(config.stress_thresholds, StressThresholds)
        assert isinstance(config.rate_limits, RateLimits)

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = AlertConfig(
            enabled=False,
            discord_webhook_url="https://discord.com/api/webhooks/test",
            dxy_move_threshold_pct=1.5,
        )

        assert config.enabled is False
        assert config.discord_webhook_url == "https://discord.com/api/webhooks/test"
        assert config.dxy_move_threshold_pct == 1.5


class TestLoadAlertConfig:
    """Tests for load_alert_config function."""

    def test_load_default_config(self) -> None:
        """Test loading config with no environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_alert_config()

            # Should be disabled without webhook URL
            assert config.enabled is False
            assert config.discord_webhook_url == ""

    def test_load_with_webhook_url(self) -> None:
        """Test loading config with webhook URL set."""
        env = {
            "LIQUIDITY_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_alert_config()

            assert config.enabled is True
            assert config.discord_webhook_url == "https://discord.com/api/webhooks/test"

    def test_load_with_disabled_flag(self) -> None:
        """Test loading config with explicit disable."""
        env = {
            "LIQUIDITY_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
            "LIQUIDITY_ALERTS_ENABLED": "false",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_alert_config()

            assert config.enabled is False

    def test_load_custom_thresholds(self) -> None:
        """Test loading config with custom thresholds."""
        env = {
            "LIQUIDITY_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
            "LIQUIDITY_DXY_THRESHOLD": "2.0",
            "LIQUIDITY_CORR_THRESHOLD": "0.5",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_alert_config()

            assert config.dxy_move_threshold_pct == 2.0
            assert config.correlation_shift_threshold == 0.5

    def test_load_custom_interval(self) -> None:
        """Test loading config with custom check interval."""
        env = {
            "LIQUIDITY_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
            "LIQUIDITY_ALERT_INTERVAL": "600",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_alert_config()

            assert config.check_interval_seconds == 600

    def test_load_custom_username(self) -> None:
        """Test loading config with custom Discord username."""
        env = {
            "LIQUIDITY_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
            "LIQUIDITY_DISCORD_USERNAME": "Custom Bot Name",
        }

        with patch.dict(os.environ, env, clear=True):
            config = load_alert_config()

            assert config.discord_username == "Custom Bot Name"
