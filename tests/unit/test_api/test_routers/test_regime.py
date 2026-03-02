"""Unit tests for regime router endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from liquidity.analyzers import CombinedRegimeAnalyzer
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
        """Test regime endpoint degrades cleanly when no data is available."""
        mock_classifier = AsyncMock()
        mock_classifier.classify.side_effect = ValueError("Insufficient data")

        from liquidity.api.deps import get_regime_classifier

        app.dependency_overrides[get_regime_classifier] = lambda: mock_classifier

        response = client.get("/regime/current")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["regime"] == "UNAVAILABLE"
        assert data["intensity"] == 0.0
        assert "degraded:" in data["components"]
        assert "degraded:" in data["metadata"]["source"]

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


class TestCombinedRegimeEndpoint:
    """Tests for GET /regime/combined endpoint."""

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

    def test_get_combined_regime_value_error_returns_fallback(
        self, client, mock_expansion_result
    ):
        """Oil-data failures should degrade to a valid combined regime response."""
        with (
            patch.object(
                CombinedRegimeAnalyzer,
                "get_combined_regime",
                new=AsyncMock(
                    side_effect=ValueError("No supply-demand data available from EIA")
                ),
            ),
            patch(
                "liquidity.api.routers.regime.RegimeClassifier.classify",
                new=AsyncMock(return_value=mock_expansion_result),
            ),
        ):
            response = client.get("/regime/combined")

        assert response.status_code == 200
        data = response.json()
        assert data["liquidity_regime"] == "EXPANSION"
        assert data["oil_regime"] == "balanced"
        assert data["combined_regime"] == "bullish"
        assert data["commodity_signal"] == "long"
        assert any("Fallback activated" in driver for driver in data["drivers"])

    def test_get_combined_regime_fallback_can_return_neutral(self, client):
        """If both oil and liquidity are unavailable, fallback should stay valid."""
        with (
            patch.object(
                CombinedRegimeAnalyzer,
                "get_combined_regime",
                new=AsyncMock(
                    side_effect=ValueError("No supply-demand data available from EIA")
                ),
            ),
            patch(
                "liquidity.api.routers.regime.RegimeClassifier.classify",
                new=AsyncMock(side_effect=RuntimeError("QuestDB unavailable")),
            ),
        ):
            response = client.get("/regime/combined")

        assert response.status_code == 200
        data = response.json()
        assert data["liquidity_regime"] == "NEUTRAL"
        assert data["oil_regime"] == "balanced"
        assert data["combined_regime"] == "neutral"
        assert data["commodity_signal"] == "neutral"
