"""Unit tests for volatility router endpoints."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from liquidity.api.server import app


class TestVolatilityFallbacks:
    """Tests degraded responses for volatility widget endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_get_move_zscore_no_data_returns_degraded_payload(self, client):
        """MOVE endpoint should degrade cleanly when data is unavailable."""
        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("No MOVE data available")

        from liquidity.api.deps import get_move_zscore_calculator

        app.dependency_overrides[get_move_zscore_calculator] = lambda: mock_calc

        try:
            response = client.get("/volatility/move-zscore")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["current_move"] == 0.0
        assert data["zscore"] == 0.0
        assert data["signal"] == "UNKNOWN"
        assert "degraded:" in data["metadata"]["source"]

    def test_get_vix_term_structure_no_data_returns_degraded_payload(self, client):
        """VIX term structure endpoint should degrade cleanly when data is unavailable."""
        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("No VIX term structure data")

        from liquidity.api.deps import get_vix_term_structure_calculator

        app.dependency_overrides[get_vix_term_structure_calculator] = lambda: mock_calc

        try:
            response = client.get("/volatility/vix-term-structure")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["vix"] == 0.0
        assert data["vix3m"] == 0.0
        assert data["structure"] == "UNKNOWN"
        assert "degraded:" in data["metadata"]["source"]

    def test_get_volatility_signal_no_data_returns_degraded_payload(self, client):
        """Composite volatility endpoint should degrade cleanly when data is unavailable."""
        mock_calc = AsyncMock()
        mock_calc.get_current.side_effect = ValueError("No volatility signal data")

        from liquidity.api.deps import get_volatility_signal_calculator

        app.dependency_overrides[get_volatility_signal_calculator] = lambda: mock_calc

        try:
            response = client.get("/volatility/signal")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["composite_score"] == 0.0
        assert data["regime"] == "NEUTRAL"
        assert data["move_signal"] == "UNKNOWN"
        assert data["vix_structure"] == "UNKNOWN"
        assert "degraded:" in data["metadata"]["source"]
