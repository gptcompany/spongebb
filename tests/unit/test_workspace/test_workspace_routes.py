"""Tests for /workspace/* metric and chart endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pandas as pd

from liquidity.api.deps import (
    get_net_liquidity_calculator,
    get_regime_classifier,
    get_volatility_signal_calculator,
)
from liquidity.openbb_ext.workspace_app import app


class TestWorkspaceMetrics:
    """Tests for /workspace/metrics/* endpoints."""

    def test_metric_net_liquidity_returns_value_and_delta(self, workspace_client):
        """GET /workspace/metrics/net-liquidity returns 200 with correct KPI shape."""
        resp = workspace_client.get("/workspace/metrics/net-liquidity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == 5800.5
        assert data["delta"] == 50.2
        assert "Net Liquidity" in data["label"]

    def test_metric_global_liquidity(self, workspace_client):
        """GET /workspace/metrics/global-liquidity returns 200 with correct value."""
        resp = workspace_client.get("/workspace/metrics/global-liquidity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == 28500.0
        assert data["delta"] == 120.5

    def test_metric_stealth_qe(self, workspace_client):
        """GET /workspace/metrics/stealth-qe returns 200 with score and status."""
        resp = workspace_client.get("/workspace/metrics/stealth-qe")
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == 72.5
        assert data["sentiment"] == "ACTIVE"

    def test_metric_regime(self, workspace_client):
        """GET /workspace/metrics/regime returns 200 with regime direction in label."""
        resp = workspace_client.get("/workspace/metrics/regime")
        assert resp.status_code == 200
        data = resp.json()
        assert "EXPANSION" in data["label"]
        assert data["value"] == 75.0


class TestWorkspaceCharts:
    """Tests for /workspace/charts/* endpoints."""

    def test_chart_net_liquidity_returns_plotly_json(self, workspace_client):
        """GET /workspace/charts/net-liquidity returns 200 with Plotly structure."""
        resp = workspace_client.get("/workspace/charts/net-liquidity")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "layout" in data

    def test_chart_global_liquidity(self, workspace_client):
        """GET /workspace/charts/global-liquidity returns 200 with Plotly structure."""
        resp = workspace_client.get("/workspace/charts/global-liquidity")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "layout" in data


class TestWorkspaceErrorHandling:
    """Tests for error handling in workspace endpoints."""

    def test_metric_calculator_value_error_returns_503(self):
        """Net liquidity workspace metric degrades cleanly on ValueError."""
        from fastapi.testclient import TestClient

        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("QuestDB down")

        app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_calc
        client = TestClient(app)

        try:
            resp = client.get("/workspace/metrics/net-liquidity")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json() == {
            "value": 0.0,
            "label": "Net Liquidity unavailable",
            "delta": None,
            "unit": "B USD",
            "sentiment": "DEGRADED",
        }

    def test_metric_calculator_unexpected_error_returns_500(self):
        """Net liquidity workspace metric returns degraded payload on unexpected errors."""
        from fastapi.testclient import TestClient

        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = RuntimeError("unexpected")

        app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_calc
        client = TestClient(app)

        try:
            resp = client.get("/workspace/metrics/net-liquidity")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json() == {
            "value": 0.0,
            "label": "Net Liquidity unavailable",
            "delta": None,
            "unit": "B USD",
            "sentiment": "ERROR",
        }

    def test_metric_regime_value_error_returns_degraded_payload(self):
        """Regime widget should degrade cleanly instead of returning a 5xx."""
        from fastapi.testclient import TestClient

        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = ValueError("Insufficient data")

        app.dependency_overrides[get_regime_classifier] = lambda: mock_classifier
        client = TestClient(app)

        try:
            resp = client.get("/workspace/metrics/regime")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json() == {
            "value": 0.0,
            "label": "Regime unavailable",
            "delta": None,
            "unit": "%",
            "sentiment": "DEGRADED",
        }

    def test_metric_global_liquidity_value_error_returns_degraded_payload(self):
        """Global liquidity widget should degrade cleanly instead of returning a 5xx."""
        from fastapi.testclient import TestClient

        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("No global liquidity data")

        from liquidity.api.deps import get_global_liquidity_calculator

        app.dependency_overrides[get_global_liquidity_calculator] = lambda: mock_calc
        client = TestClient(app)

        try:
            resp = client.get("/workspace/metrics/global-liquidity")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json() == {
            "value": 0.0,
            "label": "Global Liquidity unavailable",
            "delta": None,
            "unit": "B USD",
            "sentiment": "DEGRADED",
        }

    def test_metric_stealth_qe_value_error_returns_degraded_payload(self):
        """Stealth QE widget should degrade cleanly instead of returning a 5xx."""
        from fastapi.testclient import TestClient

        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("No stealth QE data")

        from liquidity.api.deps import get_stealth_qe_calculator

        app.dependency_overrides[get_stealth_qe_calculator] = lambda: mock_calc
        client = TestClient(app)

        try:
            resp = client.get("/workspace/metrics/stealth-qe")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json() == {
            "value": 0.0,
            "label": "Stealth QE unavailable",
            "delta": None,
            "unit": "/100",
            "sentiment": "DEGRADED",
        }

    def test_metric_volatility_signal_value_error_returns_degraded_payload(self):
        """Volatility widget should degrade cleanly instead of returning a 5xx."""
        from fastapi.testclient import TestClient

        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("No volatility data")

        app.dependency_overrides[get_volatility_signal_calculator] = lambda: mock_calc
        client = TestClient(app)

        try:
            resp = client.get("/workspace/metrics/volatility-signal")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json() == {
            "value": 0.0,
            "label": "Vol Signal unavailable",
            "delta": None,
            "unit": "/100",
            "sentiment": "DEGRADED",
        }

    def test_chart_net_liquidity_value_error_returns_placeholder_chart(self):
        """Chart widget should return a placeholder figure when data is unavailable."""
        from fastapi.testclient import TestClient

        mock_calc = AsyncMock()
        mock_calc.calculate.side_effect = ValueError("QuestDB down")

        app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_calc
        client = TestClient(app)

        try:
            resp = client.get("/workspace/charts/net-liquidity")
        finally:
            app.dependency_overrides.clear()

        data = resp.json()

        assert resp.status_code == 200
        assert data["layout"]["title"]["text"] == "Fed Net Liquidity Index (B USD)"
        assert "QuestDB down" in data["layout"]["annotations"][0]["text"]

    def test_chart_net_liquidity_uses_timestamp_column_for_x_axis(self):
        """Chart should serialize timestamp column values instead of pandas indexes."""
        from fastapi.testclient import TestClient

        history = pd.DataFrame(
            {
                "timestamp": [
                    datetime(2026, 2, 20, tzinfo=UTC),
                    datetime(2026, 2, 21, tzinfo=UTC),
                ],
                "net_liquidity": [5800.5, 5810.0],
            }
        )
        history.index = pd.Index(
            [
                pd.Timestamp("2026-02-20T00:00:00Z"),
                pd.Timestamp("2026-02-21T00:00:00Z"),
            ]
        )

        mock_calc = AsyncMock()
        mock_calc.calculate.return_value = history
        mock_calc.get_current.return_value = MagicMock()

        app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_calc
        client = TestClient(app)

        try:
            resp = client.get("/workspace/charts/net-liquidity")
        finally:
            app.dependency_overrides.clear()

        data = resp.json()

        assert resp.status_code == 200
        assert data["data"][0]["x"] == ["2026-02-20", "2026-02-21"]
