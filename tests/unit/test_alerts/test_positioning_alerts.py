"""Unit tests for positioning alerts."""

from datetime import UTC, datetime, timedelta

import pytest

from liquidity.alerts.positioning_alerts import (
    PositioningAlert,
    PositioningAlertEngine,
    PositioningAlertType,
)


class TestPositioningAlertType:
    """Tests for PositioningAlertType enum."""

    def test_spec_extreme_long(self):
        """Test SPEC_EXTREME_LONG value."""
        assert PositioningAlertType.SPEC_EXTREME_LONG.value == "spec_extreme_long"

    def test_spec_extreme_short(self):
        """Test SPEC_EXTREME_SHORT value."""
        assert PositioningAlertType.SPEC_EXTREME_SHORT.value == "spec_extreme_short"

    def test_comm_extreme_long(self):
        """Test COMM_EXTREME_LONG value."""
        assert PositioningAlertType.COMM_EXTREME_LONG.value == "comm_extreme_long"

    def test_comm_extreme_short(self):
        """Test COMM_EXTREME_SHORT value."""
        assert PositioningAlertType.COMM_EXTREME_SHORT.value == "comm_extreme_short"

    def test_comm_spec_divergence(self):
        """Test COMM_SPEC_DIVERGENCE value."""
        assert PositioningAlertType.COMM_SPEC_DIVERGENCE.value == "comm_spec_divergence"

    def test_all_types_present(self):
        """Test all alert types are defined."""
        types = list(PositioningAlertType)
        assert len(types) == 5


class TestPositioningAlert:
    """Tests for PositioningAlert dataclass."""

    @pytest.fixture
    def sample_alert(self):
        """Create sample alert for testing."""
        return PositioningAlert(
            alert_type=PositioningAlertType.SPEC_EXTREME_LONG,
            commodity="WTI",
            timestamp=datetime(2026, 2, 4, 12, 0, 0, tzinfo=UTC),
            spec_percentile=95.0,
            comm_percentile=25.0,
            message="Speculators crowded long",
            severity="critical",
        )

    def test_alert_creation(self, sample_alert):
        """Test alert can be created."""
        assert sample_alert.commodity == "WTI"
        assert sample_alert.spec_percentile == 95.0
        assert sample_alert.severity == "critical"

    def test_to_dict(self, sample_alert):
        """Test alert conversion to dict."""
        result = sample_alert.to_dict()

        assert result["alert_type"] == "spec_extreme_long"
        assert result["commodity"] == "WTI"
        assert result["spec_percentile"] == 95.0
        assert result["comm_percentile"] == 25.0
        assert result["severity"] == "critical"
        assert "timestamp" in result

    def test_to_discord_embed(self, sample_alert):
        """Test Discord embed formatting."""
        embed = sample_alert.to_discord_embed()

        assert "title" in embed
        assert "WTI" in embed["title"]
        assert "📈" in embed["title"]  # Emoji for spec extreme long

        assert "description" in embed
        assert "color" in embed
        assert embed["color"] == 0xFF0000  # Red for critical

        assert "fields" in embed
        assert len(embed["fields"]) == 3

        assert "timestamp" in embed

    def test_discord_embed_warning_color(self):
        """Test warning alerts have orange color."""
        alert = PositioningAlert(
            alert_type=PositioningAlertType.SPEC_EXTREME_LONG,
            commodity="GOLD",
            timestamp=datetime.now(UTC),
            spec_percentile=92.0,
            comm_percentile=50.0,
            message="Elevated long",
            severity="warning",
        )

        embed = alert.to_discord_embed()
        assert embed["color"] == 0xFFA500  # Orange

    def test_discord_embed_divergence_emoji(self):
        """Test divergence alert has correct emoji."""
        alert = PositioningAlert(
            alert_type=PositioningAlertType.COMM_SPEC_DIVERGENCE,
            commodity="COPPER",
            timestamp=datetime.now(UTC),
            spec_percentile=80.0,
            comm_percentile=20.0,
            message="Divergence detected",
            severity="warning",
        )

        embed = alert.to_discord_embed()
        assert "⚡" in embed["title"]


class TestPositioningAlertEngine:
    """Tests for PositioningAlertEngine."""

    @pytest.fixture
    def engine(self):
        """Create engine for testing."""
        return PositioningAlertEngine()

    def test_default_thresholds(self, engine):
        """Test default thresholds are set."""
        assert engine.THRESHOLDS["extreme_high"] == 90
        assert engine.THRESHOLDS["extreme_low"] == 10
        assert engine.THRESHOLDS["critical_high"] == 95
        assert engine.THRESHOLDS["critical_low"] == 5

    def test_custom_thresholds(self):
        """Test custom threshold override."""
        engine = PositioningAlertEngine(thresholds={"extreme_high": 85})
        assert engine.THRESHOLDS["extreme_high"] == 85
        assert engine.THRESHOLDS["extreme_low"] == 10  # Default preserved

    def test_spec_extreme_long_critical(self, engine):
        """Test spec extreme long critical alert."""
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
            skip_dedup=True,
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == PositioningAlertType.SPEC_EXTREME_LONG
        assert alerts[0].severity == "critical"
        assert "CROWDED LONG" in alerts[0].message

    def test_spec_extreme_long_warning(self, engine):
        """Test spec extreme long warning alert."""
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=92.0,
            comm_percentile=50.0,
            skip_dedup=True,
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == PositioningAlertType.SPEC_EXTREME_LONG
        assert alerts[0].severity == "warning"
        assert "elevated long" in alerts[0].message

    def test_spec_extreme_short_critical(self, engine):
        """Test spec extreme short critical alert."""
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=3.0,
            comm_percentile=50.0,
            skip_dedup=True,
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == PositioningAlertType.SPEC_EXTREME_SHORT
        assert alerts[0].severity == "critical"
        assert "CROWDED SHORT" in alerts[0].message

    def test_spec_extreme_short_warning(self, engine):
        """Test spec extreme short warning alert."""
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=8.0,
            comm_percentile=50.0,
            skip_dedup=True,
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == PositioningAlertType.SPEC_EXTREME_SHORT
        assert alerts[0].severity == "warning"

    def test_comm_extreme_long(self, engine):
        """Test commercial extreme long alert."""
        alerts = engine.check_extremes(
            commodity="GOLD",
            spec_percentile=50.0,
            comm_percentile=95.0,
            skip_dedup=True,
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == PositioningAlertType.COMM_EXTREME_LONG
        assert alerts[0].severity == "critical"
        assert "SMART MONEY BULLISH" in alerts[0].message

    def test_comm_extreme_short(self, engine):
        """Test commercial extreme short alert."""
        alerts = engine.check_extremes(
            commodity="GOLD",
            spec_percentile=50.0,
            comm_percentile=5.0,
            skip_dedup=True,
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == PositioningAlertType.COMM_EXTREME_SHORT
        assert alerts[0].severity == "critical"
        assert "SMART MONEY BEARISH" in alerts[0].message

    def test_divergence_specs_bullish(self, engine):
        """Test divergence when specs bullish, comms bearish."""
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=75.0,
            comm_percentile=25.0,
            skip_dedup=True,
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == PositioningAlertType.COMM_SPEC_DIVERGENCE
        assert "commercials bearish while specs bullish" in alerts[0].message

    def test_divergence_comms_bullish(self, engine):
        """Test divergence when comms bullish, specs bearish."""
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=25.0,
            comm_percentile=75.0,
            skip_dedup=True,
        )

        assert len(alerts) == 1
        assert alerts[0].alert_type == PositioningAlertType.COMM_SPEC_DIVERGENCE
        assert "commercials bullish while specs bearish" in alerts[0].message

    def test_no_alerts_normal_conditions(self, engine):
        """Test no alerts when conditions are normal."""
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=50.0,
            comm_percentile=50.0,
            skip_dedup=True,
        )

        assert len(alerts) == 0

    def test_no_alerts_near_thresholds(self, engine):
        """Test no alerts just below thresholds."""
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=60.0,  # Within normal range (no extremes, no divergence)
            comm_percentile=50.0,  # Within normal range
            skip_dedup=True,
        )

        assert len(alerts) == 0

    def test_multiple_alerts_extreme_conditions(self, engine):
        """Test multiple alerts can be generated."""
        # Spec extreme long + comm extreme short
        alerts = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=5.0,
            skip_dedup=True,
        )

        # Should get spec extreme + comm extreme + divergence
        assert len(alerts) >= 2
        types = {a.alert_type for a in alerts}
        assert PositioningAlertType.SPEC_EXTREME_LONG in types
        assert PositioningAlertType.COMM_EXTREME_SHORT in types


class TestPositioningAlertEngineDedup:
    """Tests for deduplication logic."""

    @pytest.fixture
    def engine(self):
        """Create engine with short dedup window for testing."""
        return PositioningAlertEngine(dedup_hours=1)

    def test_dedup_blocks_duplicate(self, engine):
        """Test dedup blocks duplicate alerts."""
        # First call should generate alert
        alerts1 = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        assert len(alerts1) == 1

        # Second call should be deduplicated
        alerts2 = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        assert len(alerts2) == 0

    def test_dedup_different_commodities(self, engine):
        """Test dedup allows different commodities."""
        alerts1 = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        assert len(alerts1) == 1

        alerts2 = engine.check_extremes(
            commodity="GOLD",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        assert len(alerts2) == 1  # Different commodity

    def test_dedup_different_alert_types(self, engine):
        """Test dedup allows different alert types for same commodity."""
        # First call - spec extreme
        alerts1 = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        assert len(alerts1) == 1

        # Second call - comm extreme (different type)
        alerts2 = engine.check_extremes(
            commodity="WTI",
            spec_percentile=50.0,
            comm_percentile=5.0,
        )
        assert len(alerts2) == 1  # Different alert type

    def test_skip_dedup_flag(self, engine):
        """Test skip_dedup flag bypasses deduplication."""
        alerts1 = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        assert len(alerts1) == 1

        # With skip_dedup=True
        alerts2 = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
            skip_dedup=True,
        )
        assert len(alerts2) == 1  # Not deduplicated

    def test_reset_dedup_all(self, engine):
        """Test reset_dedup clears all state."""
        engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        engine.check_extremes(
            commodity="GOLD",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )

        engine.reset_dedup()

        # Both should now generate alerts
        alerts1 = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        alerts2 = engine.check_extremes(
            commodity="GOLD",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )

        assert len(alerts1) == 1
        assert len(alerts2) == 1

    def test_reset_dedup_single_commodity(self, engine):
        """Test reset_dedup for single commodity."""
        engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        engine.check_extremes(
            commodity="GOLD",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )

        engine.reset_dedup("WTI")

        # WTI should generate alert, GOLD should not
        alerts1 = engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )
        alerts2 = engine.check_extremes(
            commodity="GOLD",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )

        assert len(alerts1) == 1
        assert len(alerts2) == 0

    def test_get_alert_history(self, engine):
        """Test get_alert_history returns dedup state."""
        engine.check_extremes(
            commodity="WTI",
            spec_percentile=96.0,
            comm_percentile=50.0,
        )

        history = engine.get_alert_history()

        assert len(history) == 1
        assert "WTI:spec_extreme_long" in history


class TestPositioningAlertEngineCheckAll:
    """Tests for check_all_commodities method."""

    @pytest.fixture
    def engine(self):
        """Create engine for testing."""
        return PositioningAlertEngine()

    def test_check_all_commodities(self, engine):
        """Test checking multiple commodities at once."""
        data = {
            "WTI": {"spec_pctl": 96.0, "comm_pctl": 50.0},
            "GOLD": {"spec_pctl": 50.0, "comm_pctl": 95.0},
            "COPPER": {"spec_pctl": 50.0, "comm_pctl": 50.0},
        }

        alerts = engine.check_all_commodities(data)

        assert len(alerts) == 2
        commodities = {a.commodity for a in alerts}
        assert "WTI" in commodities
        assert "GOLD" in commodities
        assert "COPPER" not in commodities

    def test_check_all_empty_data(self, engine):
        """Test with empty data."""
        alerts = engine.check_all_commodities({})
        assert len(alerts) == 0

    def test_check_all_missing_keys(self, engine):
        """Test with missing percentile keys uses defaults."""
        data = {
            "WTI": {},  # Missing spec_pctl and comm_pctl
        }

        alerts = engine.check_all_commodities(data)
        assert len(alerts) == 0  # Default 50.0 generates no alerts
