"""Unit tests for correlations router endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from liquidity.analyzers.correlation_engine import CorrelationMatrix, CorrelationResult
from liquidity.api.server import app


class TestCorrelationsEndpoint:
    """Tests for GET /correlations endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_asset_prices(self):
        """Create mock asset price data."""
        dates = pd.date_range(end=datetime.now(UTC), periods=100, freq="D")
        return pd.DataFrame(
            {
                "BTC": [50000 + i * 100 for i in range(100)],
                "SPX": [4500 + i * 10 for i in range(100)],
                "GOLD": [2000 + i * 5 for i in range(100)],
                "DXY": [104 + i * 0.05 for i in range(100)],
            },
            index=dates,
        )

    @pytest.fixture
    def mock_correlations(self):
        """Create mock correlation results."""
        dates = pd.date_range(end=datetime.now(UTC), periods=100, freq="D")
        return {
            "corr_30d": pd.DataFrame(
                {
                    "BTC": [0.72] * 100,
                    "SPX": [0.65] * 100,
                    "GOLD": [0.45] * 100,
                    "DXY": [-0.55] * 100,
                },
                index=dates,
            ),
            "corr_90d": pd.DataFrame(
                {
                    "BTC": [0.70] * 100,
                    "SPX": [0.60] * 100,
                    "GOLD": [0.40] * 100,
                    "DXY": [-0.50] * 100,
                },
                index=dates,
            ),
        }

    def test_get_correlations_success(self, client, mock_asset_prices, mock_correlations):
        """Test successful correlations response."""
        mock_engine = MagicMock()
        mock_engine._fetch_asset_prices = AsyncMock(return_value=mock_asset_prices)
        mock_engine._calculate_returns.return_value = mock_asset_prices.pct_change().dropna()
        mock_engine.calculate_correlations.return_value = mock_correlations
        mock_engine.calculate_single_correlation.return_value = CorrelationResult(
            timestamp=datetime.now(UTC),
            asset="BTC",
            liquidity_metric="liquidity",
            corr_30d=0.72,
            corr_90d=0.70,
            corr_ewma=0.71,
            p_value_30d=0.001,
            p_value_90d=0.002,
            sample_size=100,
        )

        from liquidity.api.deps import get_correlation_engine

        app.dependency_overrides[get_correlation_engine] = lambda: mock_engine

        try:
            response = client.get("/correlations")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert "window" in data
        assert data["window"] == "30d"
        assert "correlations" in data
        assert "as_of_date" in data
        assert "metadata" in data

    def test_get_correlations_90d_window(self, client, mock_asset_prices, mock_correlations):
        """Test correlations with 90d window."""
        mock_engine = MagicMock()
        mock_engine._fetch_asset_prices = AsyncMock(return_value=mock_asset_prices)
        mock_engine._calculate_returns.return_value = mock_asset_prices.pct_change().dropna()
        mock_engine.calculate_correlations.return_value = mock_correlations
        mock_engine.calculate_single_correlation.return_value = CorrelationResult(
            timestamp=datetime.now(UTC),
            asset="BTC",
            liquidity_metric="liquidity",
            corr_30d=0.72,
            corr_90d=0.70,
            corr_ewma=0.71,
            p_value_30d=0.001,
            p_value_90d=0.002,
            sample_size=100,
        )

        from liquidity.api.deps import get_correlation_engine

        app.dependency_overrides[get_correlation_engine] = lambda: mock_engine

        try:
            response = client.get("/correlations?window=90d")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["window"] == "90d"

    def test_get_correlations_invalid_window(self, client):
        """Test correlations with invalid window parameter."""
        response = client.get("/correlations?window=invalid")
        assert response.status_code == 422

    def test_get_correlations_no_data(self, client):
        """Test correlations when no data available."""
        mock_engine = MagicMock()
        mock_engine._fetch_asset_prices = AsyncMock(return_value=pd.DataFrame())

        from liquidity.api.deps import get_correlation_engine

        app.dependency_overrides[get_correlation_engine] = lambda: mock_engine

        try:
            response = client.get("/correlations")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "Unable to calculate" in response.json()["detail"]


class TestCorrelationMatrixEndpoint:
    """Tests for GET /correlations/matrix endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_asset_prices(self):
        """Create mock asset price data."""
        dates = pd.date_range(end=datetime.now(UTC), periods=100, freq="D")
        return pd.DataFrame(
            {
                "BTC": [50000 + i * 100 for i in range(100)],
                "SPX": [4500 + i * 10 for i in range(100)],
                "GOLD": [2000 + i * 5 for i in range(100)],
            },
            index=dates,
        )

    def test_get_correlation_matrix_success(self, client, mock_asset_prices):
        """Test successful correlation matrix response."""
        assets = ["BTC", "SPX", "GOLD"]
        corr_df = pd.DataFrame(
            [[1.0, 0.7, 0.4], [0.7, 1.0, 0.3], [0.4, 0.3, 1.0]],
            index=pd.Index(assets),
            columns=pd.Index(assets),
        )
        p_df = pd.DataFrame(
            [[0.0, 0.001, 0.05], [0.001, 0.0, 0.1], [0.05, 0.1, 0.0]],
            index=pd.Index(assets),
            columns=pd.Index(assets),
        )
        mock_matrix = CorrelationMatrix(
            timestamp=datetime.now(UTC),
            assets=assets,
            correlations=corr_df,
            p_values=p_df,
        )

        mock_engine = MagicMock()
        mock_engine._fetch_asset_prices = AsyncMock(return_value=mock_asset_prices)
        mock_engine._calculate_returns.return_value = mock_asset_prices.pct_change().dropna()
        mock_engine.calculate_correlation_matrix.return_value = mock_matrix

        from liquidity.api.deps import get_correlation_engine

        app.dependency_overrides[get_correlation_engine] = lambda: mock_engine

        try:
            response = client.get("/correlations/matrix")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert "assets" in data
        assert "matrix" in data
        assert "as_of_date" in data
        assert "metadata" in data

        # Check matrix structure
        assert isinstance(data["matrix"], dict)
        assert "BTC" in data["matrix"]
        assert "SPX" in data["matrix"]["BTC"]
        assert data["matrix"]["BTC"]["BTC"] == 1.0  # Diagonal should be 1

    def test_get_correlation_matrix_no_data(self, client):
        """Test correlation matrix when no data available."""
        mock_engine = MagicMock()
        mock_engine._fetch_asset_prices = AsyncMock(return_value=pd.DataFrame())

        from liquidity.api.deps import get_correlation_engine

        app.dependency_overrides[get_correlation_engine] = lambda: mock_engine

        try:
            response = client.get("/correlations/matrix")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "Unable to calculate" in response.json()["detail"]
