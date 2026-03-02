import pandas as pd
import numpy as np
import pytest
from datetime import UTC, datetime
from unittest.mock import MagicMock

from liquidity.analyzers.alert_engine import (
    Alert,
    AlertEngine,
    AlertSeverity,
    AlertType,
    SEVERITY_COLORS,
)
from liquidity.analyzers.regime_classifier import RegimeDirection, RegimeResult


@pytest.fixture
def engine():
    return AlertEngine()


@pytest.fixture
def mock_regime_expansion():
    return RegimeResult(
        timestamp=datetime.now(UTC),
        direction=RegimeDirection.EXPANSION,
        intensity=80.0,
        confidence="High",
        net_liq_percentile=0.8,
        global_liq_percentile=0.8,
        stealth_qe_score=80.0,
        components={},
    )


@pytest.fixture
def mock_regime_contraction():
    return RegimeResult(
        timestamp=datetime.now(UTC),
        direction=RegimeDirection.CONTRACTION,
        intensity=20.0,
        confidence="High",
        net_liq_percentile=0.2,
        global_liq_percentile=0.2,
        stealth_qe_score=20.0,
        components={},
    )


def test_check_regime_shift_none(engine, mock_regime_expansion):
    # No previous
    assert engine.check_regime_shift(mock_regime_expansion, None) is None
    
    # Same regime
    assert engine.check_regime_shift(mock_regime_expansion, mock_regime_expansion) is None


def test_check_regime_shift_detected(engine, mock_regime_expansion, mock_regime_contraction):
    alert = engine.check_regime_shift(mock_regime_contraction, mock_regime_expansion)
    
    assert alert is not None
    assert alert.alert_type == AlertType.REGIME_SHIFT
    assert alert.severity == AlertSeverity.HIGH
    assert "EXPANSION -> CONTRACTION" in alert.title


def test_check_correlation_shift_insufficient_data(engine):
    series = pd.Series([0.5, 0.6])
    assert engine.check_correlation_shift(series, "BTC") is None


def test_check_correlation_shift_no_breach(engine):
    # Create stable series
    data = [0.5] * 100
    series = pd.Series(data)
    assert engine.check_correlation_shift(series, "BTC") is None


def test_check_correlation_shift_absolute_breach(engine):
    # ROLLING_WINDOW = 90
    data = [0.5 + (0.01 if i % 2 == 0 else 0) for i in range(90)]
    data += [0.5, 0.9] # Last change is 0.4 > 0.3
    series = pd.Series(data)
    
    alert = engine.check_correlation_shift(series, "BTC")
    assert alert is not None
    assert alert.alert_type == AlertType.CORRELATION_SURGE
    assert alert.asset == "BTC"
    assert alert.change == pytest.approx(0.4)


def test_check_correlation_shift_statistical_breach(engine):
    # Stable small variance, then jump that is small absolute but high Z
    data = [0.5, 0.51] * 45 # mean ~0.505, std small
    data += [0.505, 0.65] # jump to 0.65
    series = pd.Series(data)
    
    alert = engine.check_correlation_shift(series, "BTC")
    assert alert is not None
    assert alert.z_score > engine.SIGMA_THRESHOLD


def test_check_all_critical(engine, mock_regime_expansion, mock_regime_contraction):
    # Setup correlation breakdown
    data = [0.8 + (0.01 if i % 2 == 0 else 0) for i in range(90)]
    data += [0.8, 0.2] # Drop of 0.6
    correlations = {"BTC": pd.Series(data)}
    
    alerts = engine.check_all(
        regime=mock_regime_contraction,
        correlations=correlations,
        previous_regime=mock_regime_expansion
    )
    
    # Should have 2 alerts: Regime shift and Correlation breakdown
    assert len(alerts) == 2
    
    # The regime shift alert should be upgraded to CRITICAL
    regime_alert = next(a for a in alerts if a.alert_type == AlertType.REGIME_SHIFT)
    assert regime_alert.severity == AlertSeverity.CRITICAL
    assert "CRITICAL" in regime_alert.title


def test_format_discord_payload(engine, mock_regime_expansion):
    alert = Alert(
        timestamp=datetime.now(UTC),
        alert_type=AlertType.REGIME_SHIFT,
        severity=AlertSeverity.HIGH,
        title="Test Title",
        message="Test Message",
        metadata={"current_direction": "EXPANSION", "intensity": 80.0}
    )
    
    payload = engine.format_discord_payload(alert)
    assert "embeds" in payload
    embed = payload["embeds"][0]
    assert embed["title"] == "Test Title"
    assert embed["color"] == SEVERITY_COLORS[AlertSeverity.HIGH]
    
    # Check fields
    field_names = [f["name"] for f in embed["fields"]]
    assert "Direction" in field_names
    assert "Severity" in field_names
