"""Unit tests for stress indicator router endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from liquidity.api.server import app


class TestStressIndicatorsEndpoint:
    """Tests for GET /stress/indicators endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_stress_df(self):
        """Create mock stress indicator data."""
        now = datetime.now(UTC)
        return pd.DataFrame(
            [
                {
                    "timestamp": now,
                    "series_id": "stress_sofr_ois",
                    "source": "calculated",
                    "value": 5.2,
                    "unit": "basis_points",
                },
                {
                    "timestamp": now,
                    "series_id": "stress_sofr_width",
                    "source": "calculated",
                    "value": 15.0,
                    "unit": "basis_points",
                },
                {
                    "timestamp": now,
                    "series_id": "stress_repo",
                    "source": "calculated",
                    "value": 0.8,
                    "unit": "percent",
                },
                {
                    "timestamp": now,
                    "series_id": "stress_cp",
                    "source": "calculated",
                    "value": 25.0,
                    "unit": "basis_points",
                },
            ]
        )

    def test_get_stress_indicators_success(self, client, mock_stress_df):
        """Test successful stress indicators response."""
        mock_collector = MagicMock()
        mock_collector.collect = AsyncMock(return_value=mock_stress_df)
        mock_collector.get_current_regime.return_value = "GREEN"

        from liquidity.api.deps import get_stress_collector

        app.dependency_overrides[get_stress_collector] = lambda: mock_collector

        try:
            response = client.get("/stress/indicators")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "sofr_ois_spread" in data
        assert "sofr_percentile" in data
        assert "repo_stress" in data
        assert "cp_spread" in data
        assert "overall_stress" in data
        assert "as_of_date" in data
        assert "metadata" in data

        # Check values
        assert data["sofr_ois_spread"] == 5.2
        assert data["repo_stress"] == "low"  # 0.8% < 1%
        assert data["overall_stress"] == "normal"  # GREEN regime

    def test_get_stress_indicators_elevated(self, client):
        """Test stress indicators with elevated stress."""
        now = datetime.now(UTC)
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": now,
                    "series_id": "stress_sofr_ois",
                    "source": "calculated",
                    "value": 30.0,  # Above yellow threshold (25)
                    "unit": "basis_points",
                },
                {
                    "timestamp": now,
                    "series_id": "stress_repo",
                    "source": "calculated",
                    "value": 2.5,  # Between 1% and 3%
                    "unit": "percent",
                },
            ]
        )

        # Create a proper mock with both async and sync methods
        mock_collector = MagicMock()
        mock_collector.collect = AsyncMock(return_value=mock_df)
        mock_collector.get_current_regime.return_value = "RED"

        from liquidity.api.deps import get_stress_collector

        app.dependency_overrides[get_stress_collector] = lambda: mock_collector

        try:
            response = client.get("/stress/indicators")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert data["repo_stress"] == "medium"  # 1% < 2.5% < 3%
        assert data["overall_stress"] == "critical"  # RED regime

    def test_get_stress_indicators_no_data(self, client):
        """Test stress indicators degrade cleanly when no data is available."""
        mock_collector = MagicMock()
        mock_collector.collect = AsyncMock(return_value=pd.DataFrame())

        from liquidity.api.deps import get_stress_collector

        app.dependency_overrides[get_stress_collector] = lambda: mock_collector

        try:
            response = client.get("/stress/indicators")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["repo_stress"] == "unknown"
        assert data["overall_stress"] == "unknown"
        assert data["sofr_ois_spread"] is None
        assert "degraded:" in data["metadata"]["source"]

    def test_stress_response_structure(self, client, mock_stress_df):
        """Test response has all required fields with correct types."""
        mock_collector = MagicMock()
        mock_collector.collect = AsyncMock(return_value=mock_stress_df)
        mock_collector.get_current_regime.return_value = "GREEN"

        from liquidity.api.deps import get_stress_collector

        app.dependency_overrides[get_stress_collector] = lambda: mock_collector

        try:
            response = client.get("/stress/indicators")
        finally:
            app.dependency_overrides.clear()

        data = response.json()

        # Check metadata structure
        assert "timestamp" in data["metadata"]
        assert "source" in data["metadata"]
        assert "version" in data["metadata"]
