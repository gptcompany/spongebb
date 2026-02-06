"""Unit tests for TermStructureAlertEngine."""

from datetime import datetime, UTC

import pytest

from liquidity.alerts.oil_term_structure_alerts import (
    TermStructureAlert,
    TermStructureAlertEngine,
    TermStructureAlertType,
)
from liquidity.analyzers.term_structure import (
    CurveShape,
    RollYieldMetrics,
    TermStructureSignal,
)


@pytest.fixture
def engine():
    """Default alert engine."""
    return TermStructureAlertEngine()


@pytest.fixture
def backwardation_signal():
    """Backwardation signal fixture."""
    return TermStructureSignal(
        timestamp=datetime.now(UTC),
        curve_shape=CurveShape.BACKWARDATION,
        intensity=75,
        roll_yield_proxy=15.0,
        momentum_5d=5.0,
        momentum_20d=4.0,
        confidence=0.8,
    )


@pytest.fixture
def contango_signal():
    """Contango signal fixture."""
    return TermStructureSignal(
        timestamp=datetime.now(UTC),
        curve_shape=CurveShape.CONTANGO,
        intensity=80,
        roll_yield_proxy=-12.0,
        momentum_5d=-4.0,
        momentum_20d=-5.0,
        confidence=0.75,
    )


@pytest.fixture
def flat_signal():
    """Flat signal fixture."""
    return TermStructureSignal(
        timestamp=datetime.now(UTC),
        curve_shape=CurveShape.FLAT,
        intensity=30,
        roll_yield_proxy=1.0,
        momentum_5d=0.5,
        momentum_20d=0.3,
        confidence=0.6,
    )


class TestRegimeChangeAlert:
    """Test regime change detection."""

    def test_no_alert_on_first_signal(self, engine, backwardation_signal):
        """First signal should not trigger regime change."""
        alerts = engine.check_alerts(backwardation_signal)

        regime_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.REGIME_CHANGE
        ]
        assert len(regime_alerts) == 0

    def test_alert_on_regime_change(self, engine, backwardation_signal, contango_signal):
        """Regime change should trigger alert."""
        # First signal - no alert
        engine.check_alerts(backwardation_signal)

        # Second signal with different shape - should alert
        alerts = engine.check_alerts(contango_signal)

        regime_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.REGIME_CHANGE
        ]
        assert len(regime_alerts) == 1
        assert "BACKWARDATION → CONTANGO" in regime_alerts[0].message

    def test_no_alert_same_regime(self, engine, backwardation_signal):
        """Same regime should not trigger alert."""
        engine.check_alerts(backwardation_signal)

        # Create another backwardation signal
        signal2 = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.BACKWARDATION,
            intensity=80,
            roll_yield_proxy=18.0,
            momentum_5d=6.0,
            momentum_20d=5.0,
            confidence=0.85,
        )

        alerts = engine.check_alerts(signal2)

        regime_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.REGIME_CHANGE
        ]
        assert len(regime_alerts) == 0

    def test_flat_to_backwardation(self, engine, flat_signal, backwardation_signal):
        """Transition from flat should also alert."""
        engine.check_alerts(flat_signal)
        alerts = engine.check_alerts(backwardation_signal)

        regime_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.REGIME_CHANGE
        ]
        assert len(regime_alerts) == 1


class TestIntensityAlert:
    """Test intensity-based alerts."""

    def test_warning_at_70(self, engine):
        """Intensity >= 70 should trigger warning."""
        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.BACKWARDATION,
            intensity=75,
            roll_yield_proxy=10.0,
            momentum_5d=3.0,
            momentum_20d=3.0,
            confidence=0.7,
        )

        alerts = engine.check_alerts(signal)

        intensity_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.HIGH_INTENSITY
        ]
        assert len(intensity_alerts) == 1
        assert intensity_alerts[0].severity == "WARNING"

    def test_critical_at_90(self, engine):
        """Intensity >= 90 should trigger critical."""
        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.CONTANGO,
            intensity=95,
            roll_yield_proxy=-20.0,
            momentum_5d=-8.0,
            momentum_20d=-10.0,
            confidence=0.9,
        )

        alerts = engine.check_alerts(signal)

        intensity_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.HIGH_INTENSITY
        ]
        assert len(intensity_alerts) == 1
        assert intensity_alerts[0].severity == "CRITICAL"

    def test_no_alert_below_threshold(self, engine, flat_signal):
        """Intensity below 70 should not alert."""
        alerts = engine.check_alerts(flat_signal)

        intensity_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.HIGH_INTENSITY
        ]
        assert len(intensity_alerts) == 0

    def test_custom_thresholds(self):
        """Custom thresholds should be respected."""
        engine = TermStructureAlertEngine(
            intensity_warning=50,
            intensity_critical=80,
        )

        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.BACKWARDATION,
            intensity=55,
            roll_yield_proxy=5.0,
            momentum_5d=2.0,
            momentum_20d=2.0,
            confidence=0.6,
        )

        alerts = engine.check_alerts(signal)

        intensity_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.HIGH_INTENSITY
        ]
        assert len(intensity_alerts) == 1


class TestRollYieldAlert:
    """Test roll yield alerts."""

    def test_alert_on_extreme_positive(self, engine, backwardation_signal):
        """Extreme positive roll yield should alert."""
        roll_yield = RollYieldMetrics(
            monthly_yield=30.0,
            quarterly_yield=25.0,
            annual_yield=28.0,
            yield_trend="IMPROVING",
            days_in_current_regime=10,
        )

        alerts = engine.check_alerts(backwardation_signal, roll_yield)

        roll_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.EXTREME_ROLL_YIELD
        ]
        assert len(roll_alerts) == 1
        assert "+28.0%" in roll_alerts[0].message
        assert "positive" in roll_alerts[0].message

    def test_alert_on_extreme_negative(self, engine, contango_signal):
        """Extreme negative roll yield should alert."""
        roll_yield = RollYieldMetrics(
            monthly_yield=-25.0,
            quarterly_yield=-22.0,
            annual_yield=-24.0,
            yield_trend="DETERIORATING",
            days_in_current_regime=15,
        )

        alerts = engine.check_alerts(contango_signal, roll_yield)

        roll_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.EXTREME_ROLL_YIELD
        ]
        assert len(roll_alerts) == 1
        assert "negative" in roll_alerts[0].message

    def test_no_alert_moderate_yield(self, engine, backwardation_signal):
        """Moderate roll yield should not alert."""
        roll_yield = RollYieldMetrics(
            monthly_yield=10.0,
            quarterly_yield=8.0,
            annual_yield=15.0,  # Below 20% threshold
            yield_trend="STABLE",
            days_in_current_regime=5,
        )

        alerts = engine.check_alerts(backwardation_signal, roll_yield)

        roll_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.EXTREME_ROLL_YIELD
        ]
        assert len(roll_alerts) == 0

    def test_custom_roll_threshold(self):
        """Custom roll yield threshold should be respected."""
        engine = TermStructureAlertEngine(roll_yield_threshold=10.0)

        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.BACKWARDATION,
            intensity=60,
            roll_yield_proxy=12.0,
            momentum_5d=3.0,
            momentum_20d=3.0,
            confidence=0.7,
        )

        roll_yield = RollYieldMetrics(
            monthly_yield=15.0,
            quarterly_yield=12.0,
            annual_yield=12.0,  # Above 10% custom threshold
            yield_trend="STABLE",
            days_in_current_regime=5,
        )

        alerts = engine.check_alerts(signal, roll_yield)

        roll_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.EXTREME_ROLL_YIELD
        ]
        assert len(roll_alerts) == 1


class TestDiscordFormatting:
    """Test Discord message formatting."""

    def test_format_includes_required_fields(self, engine):
        """Format should include all required Discord fields."""
        alert = TermStructureAlert(
            timestamp=datetime.now(UTC),
            alert_type=TermStructureAlertType.REGIME_CHANGE,
            curve_shape="BACKWARDATION",
            intensity=75,
            message="Test message",
            severity="WARNING",
        )

        message = engine.format_discord_message(alert)

        assert "embeds" in message
        embed = message["embeds"][0]
        assert "title" in embed
        assert "description" in embed
        assert "color" in embed
        assert "fields" in embed
        assert len(embed["fields"]) == 3

    def test_emoji_by_alert_type(self, engine):
        """Each alert type should have correct emoji."""
        for alert_type, expected_emoji in [
            (TermStructureAlertType.REGIME_CHANGE, "🔄"),
            (TermStructureAlertType.HIGH_INTENSITY, "⚠️"),
            (TermStructureAlertType.EXTREME_ROLL_YIELD, "📊"),
        ]:
            alert = TermStructureAlert(
                timestamp=datetime.now(UTC),
                alert_type=alert_type,
                curve_shape="CONTANGO",
                intensity=80,
                message="Test",
                severity="WARNING",
            )

            message = engine.format_discord_message(alert)
            assert expected_emoji in message["embeds"][0]["title"]

    def test_color_by_severity(self, engine):
        """Each severity should have correct color."""
        for severity, expected_color in [
            ("INFO", 0x3498DB),
            ("WARNING", 0xF39C12),
            ("CRITICAL", 0xE74C3C),
        ]:
            alert = TermStructureAlert(
                timestamp=datetime.now(UTC),
                alert_type=TermStructureAlertType.HIGH_INTENSITY,
                curve_shape="CONTANGO",
                intensity=80,
                message="Test",
                severity=severity,
            )

            message = engine.format_discord_message(alert)
            assert message["embeds"][0]["color"] == expected_color


class TestAlertState:
    """Test alert state management."""

    def test_reset_state(self, engine, backwardation_signal, contango_signal):
        """Reset should clear last shape memory."""
        # Set initial state
        engine.check_alerts(backwardation_signal)

        # Reset
        engine.reset_state()

        # Now contango should not trigger regime change (no previous state)
        alerts = engine.check_alerts(contango_signal)

        regime_alerts = [
            a for a in alerts
            if a.alert_type == TermStructureAlertType.REGIME_CHANGE
        ]
        assert len(regime_alerts) == 0


class TestMultipleAlerts:
    """Test scenarios with multiple alerts."""

    def test_regime_and_intensity_together(self, engine, flat_signal):
        """Can have both regime change and intensity alert."""
        engine.check_alerts(flat_signal)

        # High intensity backwardation (regime change + intensity)
        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.BACKWARDATION,
            intensity=95,
            roll_yield_proxy=25.0,
            momentum_5d=10.0,
            momentum_20d=8.0,
            confidence=0.9,
        )

        alerts = engine.check_alerts(signal)

        alert_types = [a.alert_type for a in alerts]
        assert TermStructureAlertType.REGIME_CHANGE in alert_types
        assert TermStructureAlertType.HIGH_INTENSITY in alert_types

    def test_all_three_alerts(self, engine, flat_signal):
        """Can trigger all three alert types simultaneously."""
        engine.check_alerts(flat_signal)

        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.BACKWARDATION,
            intensity=95,
            roll_yield_proxy=30.0,
            momentum_5d=12.0,
            momentum_20d=10.0,
            confidence=0.95,
        )

        roll_yield = RollYieldMetrics(
            monthly_yield=35.0,
            quarterly_yield=30.0,
            annual_yield=32.0,
            yield_trend="IMPROVING",
            days_in_current_regime=3,
        )

        alerts = engine.check_alerts(signal, roll_yield)

        assert len(alerts) == 3
        alert_types = {a.alert_type for a in alerts}
        assert alert_types == {
            TermStructureAlertType.REGIME_CHANGE,
            TermStructureAlertType.HIGH_INTENSITY,
            TermStructureAlertType.EXTREME_ROLL_YIELD,
        }
