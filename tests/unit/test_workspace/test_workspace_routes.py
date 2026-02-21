"""Tests for /workspace/* metric and chart endpoints."""

from unittest.mock import AsyncMock, MagicMock

from liquidity.api.deps import get_net_liquidity_calculator
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
        """When calculator raises ValueError, endpoint returns 503."""
        from fastapi.testclient import TestClient

        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("QuestDB down")

        app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_calc
        client = TestClient(app)

        try:
            resp = client.get("/workspace/metrics/net-liquidity")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 503
        assert "QuestDB down" in resp.json()["detail"]

    def test_metric_calculator_unexpected_error_returns_500(self):
        """When calculator raises unexpected exception, endpoint returns 500."""
        from fastapi.testclient import TestClient

        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = RuntimeError("unexpected")

        app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_calc
        client = TestClient(app)

        try:
            resp = client.get("/workspace/metrics/net-liquidity")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"
