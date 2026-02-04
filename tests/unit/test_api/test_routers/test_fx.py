"""Unit tests for FX router endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from liquidity.api.server import app


class TestDXYEndpoint:
    """Tests for GET /fx/dxy endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_dxy_df(self):
        """Create mock DXY data."""
        dates = pd.date_range(end=datetime.now(UTC), periods=30, freq="D")
        return pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": "DX-Y.NYB",
                "source": "yahoo",
                "value": [104.0 + i * 0.1 for i in range(30)],
                "unit": "index",
            }
        )

    def test_get_dxy_success(self, client, mock_dxy_df):
        """Test successful DXY response."""
        mock_collector = AsyncMock()
        mock_collector.collect_dxy.return_value = mock_dxy_df

        from liquidity.api.deps import get_fx_collector

        app.dependency_overrides[get_fx_collector] = lambda: mock_collector

        try:
            response = client.get("/fx/dxy")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert "current" in data
        assert "change_1d" in data
        assert "change_1w" in data
        assert "data" in data
        assert "as_of_date" in data
        assert "metadata" in data

        # Check data array structure
        assert isinstance(data["data"], list)
        assert len(data["data"]) <= 30

    def test_get_dxy_with_period(self, client, mock_dxy_df):
        """Test DXY with period parameter."""
        mock_collector = AsyncMock()
        mock_collector.collect_dxy.return_value = mock_dxy_df

        from liquidity.api.deps import get_fx_collector

        app.dependency_overrides[get_fx_collector] = lambda: mock_collector

        try:
            response = client.get("/fx/dxy?period=7d")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        mock_collector.collect_dxy.assert_called_once_with(period="7d")

    def test_get_dxy_invalid_period(self, client):
        """Test DXY with invalid period parameter."""
        response = client.get("/fx/dxy?period=invalid")
        assert response.status_code == 422  # Validation error

    def test_get_dxy_no_data(self, client):
        """Test DXY when no data available."""
        mock_collector = AsyncMock()
        mock_collector.collect_dxy.return_value = pd.DataFrame()

        from liquidity.api.deps import get_fx_collector

        app.dependency_overrides[get_fx_collector] = lambda: mock_collector

        try:
            response = client.get("/fx/dxy")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "Unable to fetch" in response.json()["detail"]


class TestFXPairsEndpoint:
    """Tests for GET /fx/pairs endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_pairs_df(self):
        """Create mock FX pairs data."""
        dates = pd.date_range(end=datetime.now(UTC), periods=7, freq="D")
        rows = []
        for symbol in ["EURUSD=X", "USDJPY=X", "GBPUSD=X"]:
            base_value = {"EURUSD=X": 1.08, "USDJPY=X": 150.0, "GBPUSD=X": 1.25}[symbol]
            for i, date in enumerate(dates):
                rows.append(
                    {
                        "timestamp": date,
                        "series_id": symbol,
                        "source": "yahoo",
                        "value": base_value + i * 0.001,
                        "unit": "rate",
                    }
                )
        return pd.DataFrame(rows)

    def test_get_fx_pairs_success(self, client, mock_pairs_df):
        """Test successful FX pairs response."""
        mock_collector = AsyncMock()
        mock_collector.collect_pairs.return_value = mock_pairs_df

        from liquidity.api.deps import get_fx_collector

        app.dependency_overrides[get_fx_collector] = lambda: mock_collector

        try:
            response = client.get("/fx/pairs")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert "pairs" in data
        assert "as_of_date" in data
        assert "metadata" in data

        # Check pairs structure
        assert isinstance(data["pairs"], dict)
        assert "EUR/USD" in data["pairs"]
        assert "USD/JPY" in data["pairs"]

        # Check pair data structure
        eur_usd = data["pairs"]["EUR/USD"]
        assert "current" in eur_usd
        assert "change_1d" in eur_usd

    def test_get_fx_pairs_no_data(self, client):
        """Test FX pairs when no data available."""
        mock_collector = AsyncMock()
        mock_collector.collect_pairs.return_value = pd.DataFrame()

        from liquidity.api.deps import get_fx_collector

        app.dependency_overrides[get_fx_collector] = lambda: mock_collector

        try:
            response = client.get("/fx/pairs")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "Unable to fetch" in response.json()["detail"]
