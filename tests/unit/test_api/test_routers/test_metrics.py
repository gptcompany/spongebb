"""Unit tests for metrics router endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from liquidity.api.server import app
from liquidity.calculators.stealth_qe import StealthQEResult


class TestStealthQEEndpoint:
    """Tests for GET /metrics/stealth-qe endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_very_active_result(self):
        """Create a mock VERY_ACTIVE StealthQEResult."""
        return StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=85.0,
            score_weekly=82.0,
            rrp_level=500.0,
            rrp_velocity=-15.0,
            tga_level=300.0,
            tga_spending=100.0,
            fed_total=8000.0,
            fed_change=50.0,
            components="RRP:80% TGA:70% FED:40%",
            status="VERY_ACTIVE",
        )

    @pytest.fixture
    def mock_minimal_result(self):
        """Create a mock MINIMAL StealthQEResult."""
        return StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=5.0,
            score_weekly=None,
            rrp_level=1000.0,
            rrp_velocity=2.0,  # Positive = not bullish
            tga_level=800.0,
            tga_spending=-50.0,  # Negative = not bullish
            fed_total=7900.0,
            fed_change=-10.0,  # Negative = not bullish
            components="RRP:0% TGA:0% FED:0%",
            status="MINIMAL",
        )

    def test_get_stealth_qe_very_active(self, client, mock_very_active_result):
        """Test stealth QE endpoint returns VERY_ACTIVE correctly."""
        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_very_active_result

        from liquidity.api.deps import get_stealth_qe_calculator

        app.dependency_overrides[get_stealth_qe_calculator] = lambda: mock_calc

        response = client.get("/metrics/stealth-qe")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert data["score"] == 85.0
        assert data["status"] == "VERY_ACTIVE"
        assert data["rrp_velocity"] == -15.0
        assert data["tga_spending"] == 100.0
        assert data["fed_change"] == 50.0
        assert "RRP:80%" in data["components"]

    def test_get_stealth_qe_minimal(self, client, mock_minimal_result):
        """Test stealth QE endpoint returns MINIMAL correctly."""
        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_minimal_result

        from liquidity.api.deps import get_stealth_qe_calculator

        app.dependency_overrides[get_stealth_qe_calculator] = lambda: mock_calc

        response = client.get("/metrics/stealth-qe")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert data["score"] == 5.0
        assert data["status"] == "MINIMAL"
        assert data["rrp_velocity"] == 2.0  # Positive
        assert data["tga_spending"] == -50.0  # Negative

    def test_get_stealth_qe_no_data(self, client):
        """Test stealth QE endpoint when no data available."""
        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("No data available")

        from liquidity.api.deps import get_stealth_qe_calculator

        app.dependency_overrides[get_stealth_qe_calculator] = lambda: mock_calc

        response = client.get("/metrics/stealth-qe")

        app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "Unable to calculate" in response.json()["detail"]

    def test_stealth_qe_response_structure(self, client, mock_very_active_result):
        """Test response has all required fields."""
        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_very_active_result

        from liquidity.api.deps import get_stealth_qe_calculator

        app.dependency_overrides[get_stealth_qe_calculator] = lambda: mock_calc

        response = client.get("/metrics/stealth-qe")

        app.dependency_overrides.clear()

        data = response.json()

        # Check all required fields
        required_fields = [
            "score",
            "status",
            "rrp_level",
            "rrp_velocity",
            "tga_level",
            "tga_spending",
            "fed_total",
            "fed_change",
            "components",
            "as_of_date",
            "metadata",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_stealth_qe_score_in_bounds(self, client, mock_very_active_result):
        """Test score is always in 0-100 range."""
        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_very_active_result

        from liquidity.api.deps import get_stealth_qe_calculator

        app.dependency_overrides[get_stealth_qe_calculator] = lambda: mock_calc

        response = client.get("/metrics/stealth-qe")

        app.dependency_overrides.clear()

        data = response.json()
        assert 0 <= data["score"] <= 100

    def test_stealth_qe_status_values(self, client):
        """Test all status values are valid."""
        valid_statuses = ["VERY_ACTIVE", "ACTIVE", "MODERATE", "LOW", "MINIMAL"]

        for status in valid_statuses:
            mock_result = StealthQEResult(
                timestamp=datetime.now(UTC),
                score_daily=50.0,
                score_weekly=None,
                rrp_level=500.0,
                rrp_velocity=-5.0,
                tga_level=300.0,
                tga_spending=50.0,
                fed_total=8000.0,
                fed_change=20.0,
                components="RRP:40% TGA:40% FED:20%",
                status=status,
            )

            mock_calc = AsyncMock()
            mock_calc.get_current.return_value = mock_result

            from liquidity.api.deps import get_stealth_qe_calculator

            app.dependency_overrides[get_stealth_qe_calculator] = lambda mc=mock_calc: mc

            response = client.get("/metrics/stealth-qe")
            data = response.json()

            assert data["status"] == status

        app.dependency_overrides.clear()

    def test_stealth_qe_optional_weekly_values(self, client):
        """Test weekly change fields can be None when not enough data."""
        mock_result = StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=30.0,
            score_weekly=None,  # Not a Wednesday
            rrp_level=500.0,
            rrp_velocity=None,  # Not enough history
            tga_level=300.0,
            tga_spending=None,  # Not enough history
            fed_total=8000.0,
            fed_change=None,  # Not enough history
            components="RRP:0% TGA:0% FED:0%",
            status="LOW",
        )

        mock_calc = AsyncMock()
        mock_calc.get_current.return_value = mock_result

        from liquidity.api.deps import get_stealth_qe_calculator

        app.dependency_overrides[get_stealth_qe_calculator] = lambda: mock_calc

        response = client.get("/metrics/stealth-qe")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        # Optional fields can be null
        assert data["rrp_velocity"] is None
        assert data["tga_spending"] is None
        assert data["fed_change"] is None
