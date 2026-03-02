"""Unit tests for API server and health endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from liquidity.api.server import app


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_check_healthy(self, client):
        """Test health check when QuestDB is connected."""
        mock_storage = MagicMock()
        mock_storage.health_check.return_value = True

        with patch("liquidity.api.server.get_storage", return_value=mock_storage):
            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["questdb_connected"] is True
        assert data["version"] == "1.0.0"

    def test_health_check_degraded(self, client):
        """Test health check when QuestDB is disconnected."""
        mock_storage = MagicMock()
        mock_storage.health_check.return_value = False

        with patch("liquidity.api.server.get_storage", return_value=mock_storage):
            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["questdb_connected"] is False

    def test_health_check_storage_error(self, client):
        """Test health check when storage raises exception."""
        with patch("liquidity.api.server.get_storage", side_effect=Exception("Connection failed")):
            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["questdb_connected"] is False


class TestRootEndpoint:
    """Tests for the root endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_root_returns_info(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "docs" in data
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"


class TestOpenAPIDocs:
    """Tests for OpenAPI documentation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_docs_available(self, client):
        """Test /docs endpoint is available."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_available(self, client):
        """Test /openapi.json endpoint is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "SpongeBB API"
        assert data["info"]["version"] == "1.0.0"

    def test_openapi_has_endpoints(self, client):
        """Test OpenAPI schema includes all endpoints."""
        response = client.get("/openapi.json")
        data = response.json()
        paths = data["paths"]

        # Check all expected endpoints
        assert "/health" in paths
        assert "/liquidity/net" in paths
        assert "/liquidity/global" in paths
        assert "/regime/current" in paths
        assert "/metrics/stealth-qe" in paths

    def test_openapi_tags(self, client):
        """Test OpenAPI schema has endpoints with correct tags."""
        response = client.get("/openapi.json")
        data = response.json()
        str(data["paths"])

        # Endpoints should exist under their respective prefixes
        assert "/liquidity/net" in data["paths"]
        assert "/liquidity/global" in data["paths"]
        assert "/regime/current" in data["paths"]
        assert "/metrics/stealth-qe" in data["paths"]

        # Check tags in endpoint definitions
        assert "liquidity" in str(data["paths"]["/liquidity/net"])
        assert "regime" in str(data["paths"]["/regime/current"])
        assert "metrics" in str(data["paths"]["/metrics/stealth-qe"])


class TestCORSMiddleware:
    """Tests for CORS configuration."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_cors_allows_workspace_origin(self, client):
        """Test CORS allows OpenBB Workspace origin."""
        response = client.options(
            "/health",
            headers={
                "Origin": "https://pro.openbb.co",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI CORS middleware handles preflight
        assert response.status_code in [200, 204]

    def test_cors_only_get_allowed(self, client):
        """Test only GET methods are allowed."""
        # POST should fail on read-only endpoints
        response = client.post("/health")
        assert response.status_code == 405  # Method not allowed


class TestAppMetadata:
    """Tests for application metadata."""

    def test_app_title(self):
        """Test app has correct title."""
        assert app.title == "SpongeBB API"

    def test_app_version(self):
        """Test app has correct version."""
        assert app.version == "1.0.0"

    def test_app_description(self):
        """Test app has description."""
        assert "liquidity" in app.description.lower()
        assert "Hayes" in app.description
