"""Unit tests for regime router endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from liquidity.analyzers.regime_classifier import RegimeDirection, RegimeResult
from liquidity.api.server import app


class TestRegimeEndpoint:
    """Tests for GET /regime/current endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_expansion_result(self):
        """Create a mock EXPANSION RegimeResult."""
        return RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.EXPANSION,
            intensity=75.0,
            confidence="HIGH",
            net_liq_percentile=0.70,
            global_liq_percentile=0.75,
            stealth_qe_score=0.60,
            components="NET:0.70 GLO:0.75 SQE:0.60",
        )

    @pytest.fixture
    def mock_contraction_result(self):
        """Create a mock CONTRACTION RegimeResult."""
        return RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.CONTRACTION,
            intensity=60.0,
            confidence="MEDIUM",
            net_liq_percentile=0.30,
            global_liq_percentile=0.35,
            stealth_qe_score=0.20,
            components="NET:0.30 GLO:0.35 SQE:0.20",
        )

    def test_get_current_regime_expansion(self, client, mock_expansion_result):
        """Test regime endpoint returns EXPANSION correctly."""
        mock_classifier = AsyncMock()
        mock_classifier.classify.return_value = mock_expansion_result

        from liquidity.api.deps import get_regime_classifier

        app.dependency_overrides[get_regime_classifier] = lambda: mock_classifier

        response = client.get("/regime/current")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert data["regime"] == "EXPANSION"
        assert data["intensity"] == 75.0
        assert data["confidence"] == "HIGH"
        assert "NET:0.70" in data["components"]

    def test_get_current_regime_contraction(self, client, mock_contraction_result):
        """Test regime endpoint returns CONTRACTION correctly."""
        mock_classifier = AsyncMock()
        mock_classifier.classify.return_value = mock_contraction_result

        from liquidity.api.deps import get_regime_classifier

        app.dependency_overrides[get_regime_classifier] = lambda: mock_classifier

        response = client.get("/regime/current")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert data["regime"] == "CONTRACTION"
        assert data["intensity"] == 60.0
        assert data["confidence"] == "MEDIUM"

    def test_get_current_regime_no_data(self, client):
        """Test regime endpoint when no data available."""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = ValueError("Insufficient data")

        from liquidity.api.deps import get_regime_classifier

        app.dependency_overrides[get_regime_classifier] = lambda: mock_classifier

        response = client.get("/regime/current")

        app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "Unable to classify" in response.json()["detail"]

    def test_regime_response_structure(self, client, mock_expansion_result):
        """Test response has all required fields."""
        mock_classifier = AsyncMock()
        mock_classifier.classify.return_value = mock_expansion_result

        from liquidity.api.deps import get_regime_classifier

        app.dependency_overrides[get_regime_classifier] = lambda: mock_classifier

        response = client.get("/regime/current")

        app.dependency_overrides.clear()

        data = response.json()

        # Check all required fields
        required_fields = [
            "regime",
            "intensity",
            "confidence",
            "components",
            "as_of_date",
            "metadata",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Regime must be one of two values
        assert data["regime"] in ["EXPANSION", "CONTRACTION"]

        # Confidence must be one of three values
        assert data["confidence"] in ["HIGH", "MEDIUM", "LOW"]

    def test_regime_no_neutral(self, client, mock_expansion_result, mock_contraction_result):
        """Test that regime is never NEUTRAL (binary classification)."""
        mock_classifier = AsyncMock()

        from liquidity.api.deps import get_regime_classifier

        # Test multiple results
        for result in [mock_expansion_result, mock_contraction_result]:
            mock_classifier.classify.return_value = result
            app.dependency_overrides[get_regime_classifier] = lambda: mock_classifier

            response = client.get("/regime/current")
            data = response.json()

            # No NEUTRAL regime allowed
            assert data["regime"] != "NEUTRAL"
            assert data["regime"] in ["EXPANSION", "CONTRACTION"]

        app.dependency_overrides.clear()

    def test_regime_intensity_in_bounds(self, client, mock_expansion_result):
        """Test intensity is always in 0-100 range."""
        mock_classifier = AsyncMock()
        mock_classifier.classify.return_value = mock_expansion_result

        from liquidity.api.deps import get_regime_classifier

        app.dependency_overrides[get_regime_classifier] = lambda: mock_classifier

        response = client.get("/regime/current")

        app.dependency_overrides.clear()

        data = response.json()
        assert 0 <= data["intensity"] <= 100
