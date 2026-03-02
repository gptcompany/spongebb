"""Shared fixtures for workspace tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from liquidity.api.deps import (
    get_global_liquidity_calculator,
    get_net_liquidity_calculator,
    get_regime_classifier,
    get_stealth_qe_calculator,
)
from liquidity.openbb_ext.workspace_app import app


@pytest.fixture
def workspace_client():
    """TestClient using the workspace app with mocked calculators."""
    # Mock NetLiquidityCalculator
    mock_net = AsyncMock()
    mock_net.get_current.return_value = MagicMock(
        net_liquidity=5800.5,
        walcl=7500.0,
        tga=800.0,
        rrp=900.5,
        weekly_delta=50.2,
        sentiment=MagicMock(value="BULLISH"),
        timestamp=datetime(2026, 2, 21, tzinfo=UTC),
    )
    mock_net.calculate.return_value = MagicMock(
        empty=True,  # Simplify chart tests — triggers "No data" annotation path
    )

    # Mock GlobalLiquidityCalculator
    mock_global = AsyncMock()
    mock_global.get_current.return_value = MagicMock(
        total_usd=28500.0,
        fed_usd=5800.0,
        ecb_usd=8200.0,
        boj_usd=5100.0,
        pboc_usd=6400.0,
        boe_usd=None,
        snb_usd=None,
        boc_usd=None,
        weekly_delta=120.5,
        coverage_pct=95.2,
        timestamp=datetime(2026, 2, 21, tzinfo=UTC),
    )
    mock_global.calculate.return_value = MagicMock(empty=True)

    # Mock StealthQECalculator
    mock_stealth = AsyncMock()
    mock_stealth.get_current.return_value = MagicMock(
        score_daily=72.5,
        status="ACTIVE",
        rrp_level=500.0,
        tga_level=750.0,
        fed_total=7500.0,
        timestamp=datetime(2026, 2, 21, tzinfo=UTC),
    )

    # Mock RegimeClassifier
    mock_regime = AsyncMock()
    mock_regime.classify.return_value = MagicMock(
        direction=MagicMock(value="EXPANSION"),
        intensity=75.0,
        confidence="HIGH",
        timestamp=datetime(2026, 2, 21, tzinfo=UTC),
    )

    app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_net
    app.dependency_overrides[get_global_liquidity_calculator] = lambda: mock_global
    app.dependency_overrides[get_stealth_qe_calculator] = lambda: mock_stealth
    app.dependency_overrides[get_regime_classifier] = lambda: mock_regime

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
