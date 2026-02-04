"""Unit tests for liquidity router endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from liquidity.api.server import app
from liquidity.calculators.global_liquidity import GlobalLiquidityResult
from liquidity.calculators.net_liquidity import NetLiquidityResult, Sentiment


class TestNetLiquidityEndpoint:
    """Tests for GET /liquidity/net endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_net_liq_result(self):
        """Create a mock NetLiquidityResult."""
        return NetLiquidityResult(
            timestamp=datetime.now(UTC),
            net_liquidity=6000.0,
            walcl=8000.0,
            tga=1000.0,
            rrp=1000.0,
            weekly_delta=50.0,
            monthly_delta=100.0,
            delta_60d=150.0,
            delta_90d=200.0,
            sentiment=Sentiment.BULLISH,
        )

    def test_get_net_liquidity_success(self, client, mock_net_liq_result):
        """Test successful net liquidity response."""
        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_net_liq_result

        from liquidity.api.deps import get_net_liquidity_calculator

        app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_calc

        try:
            response = client.get("/liquidity/net")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert data["value"] == 6000.0
        assert data["walcl"] == 8000.0
        assert data["tga"] == 1000.0
        assert data["rrp"] == 1000.0
        assert data["weekly_delta"] == 50.0
        assert data["sentiment"] == "BULLISH"
        assert "as_of_date" in data
        assert "metadata" in data

    def test_get_net_liquidity_no_data(self, client):
        """Test net liquidity when no data available."""
        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("No data available")

        from liquidity.api.deps import get_net_liquidity_calculator

        app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_calc

        response = client.get("/liquidity/net")

        app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "Unable to calculate" in response.json()["detail"]

    def test_net_liquidity_response_structure(self, client, mock_net_liq_result):
        """Test response has all required fields."""
        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_net_liq_result

        from liquidity.api.deps import get_net_liquidity_calculator

        app.dependency_overrides[get_net_liquidity_calculator] = lambda: mock_calc

        response = client.get("/liquidity/net")

        app.dependency_overrides.clear()

        data = response.json()

        # Check all required fields
        required_fields = [
            "value",
            "walcl",
            "tga",
            "rrp",
            "weekly_delta",
            "sentiment",
            "as_of_date",
            "metadata",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Check metadata structure
        assert "timestamp" in data["metadata"]
        assert "source" in data["metadata"]
        assert "version" in data["metadata"]


class TestGlobalLiquidityEndpoint:
    """Tests for GET /liquidity/global endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_global_liq_result(self):
        """Create a mock GlobalLiquidityResult."""
        return GlobalLiquidityResult(
            timestamp=datetime.now(UTC),
            total_usd=35000.0,
            fed_usd=6000.0,
            ecb_usd=10000.0,
            boj_usd=8000.0,
            pboc_usd=11000.0,
            boe_usd=None,
            snb_usd=None,
            boc_usd=None,
            weekly_delta=100.0,
            delta_30d=300.0,
            delta_60d=500.0,
            delta_90d=700.0,
            coverage_pct=95.0,
        )

    def test_get_global_liquidity_tier1(self, client, mock_global_liq_result):
        """Test global liquidity with Tier 1 CBs only."""
        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_global_liq_result

        from liquidity.api.deps import get_global_liquidity_calculator

        app.dependency_overrides[get_global_liquidity_calculator] = lambda: mock_calc

        response = client.get("/liquidity/global")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert data["value"] == 35000.0
        assert data["coverage_pct"] == 95.0
        assert data["components"]["fed_usd"] == 6000.0
        assert data["components"]["ecb_usd"] == 10000.0
        assert data["components"]["boj_usd"] == 8000.0
        assert data["components"]["pboc_usd"] == 11000.0

        # Tier 2 should be None
        assert data["components"]["boe_usd"] is None

    def test_get_global_liquidity_tier2(self, client):
        """Test global liquidity with Tier 2 CBs included."""
        mock_result = GlobalLiquidityResult(
            timestamp=datetime.now(UTC),
            total_usd=36500.0,
            fed_usd=6000.0,
            ecb_usd=10000.0,
            boj_usd=8000.0,
            pboc_usd=11000.0,
            boe_usd=1000.0,
            snb_usd=300.0,
            boc_usd=200.0,
            weekly_delta=100.0,
            delta_30d=300.0,
            delta_60d=500.0,
            delta_90d=700.0,
            coverage_pct=99.0,
        )

        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_result

        from liquidity.api.deps import get_global_liquidity_calculator

        app.dependency_overrides[get_global_liquidity_calculator] = lambda: mock_calc

        response = client.get("/liquidity/global?tier=2")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        # Tier 2 should be present
        assert data["components"]["boe_usd"] == 1000.0
        assert data["components"]["snb_usd"] == 300.0
        assert data["components"]["boc_usd"] == 200.0
        assert data["coverage_pct"] == 99.0

    def test_tier_query_param_validation(self, client, mock_global_liq_result):
        """Test tier query parameter validation."""
        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_global_liq_result

        from liquidity.api.deps import get_global_liquidity_calculator

        app.dependency_overrides[get_global_liquidity_calculator] = lambda: mock_calc

        # Valid: tier=1
        response = client.get("/liquidity/global?tier=1")
        assert response.status_code == 200

        # Valid: tier=2
        response = client.get("/liquidity/global?tier=2")
        assert response.status_code == 200

        # Invalid: tier=0
        response = client.get("/liquidity/global?tier=0")
        assert response.status_code == 422  # Validation error

        # Invalid: tier=3
        response = client.get("/liquidity/global?tier=3")
        assert response.status_code == 422

        app.dependency_overrides.clear()

    def test_get_global_liquidity_no_data(self, client):
        """Test global liquidity when no data available."""
        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("No data available")

        from liquidity.api.deps import get_global_liquidity_calculator

        app.dependency_overrides[get_global_liquidity_calculator] = lambda: mock_calc

        response = client.get("/liquidity/global")

        app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "Unable to calculate" in response.json()["detail"]
