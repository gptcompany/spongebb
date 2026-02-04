"""Unit tests for API schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from liquidity.api.schemas import (
    APIMetadata,
    ErrorResponse,
    GlobalLiquidityComponent,
    GlobalLiquidityResponse,
    HealthResponse,
    NetLiquidityResponse,
    RegimeResponse,
    StealthQEResponse,
)


class TestAPIMetadata:
    """Tests for APIMetadata model."""

    def test_create_with_defaults(self):
        """Test creation with default values."""
        meta = APIMetadata(timestamp=datetime.now(UTC))
        assert meta.source == "openbb_liquidity"
        assert meta.version == "1.0.0"
        assert meta.timestamp is not None

    def test_create_with_custom_values(self):
        """Test creation with custom values."""
        ts = datetime.now(UTC)
        meta = APIMetadata(timestamp=ts, source="test", version="2.0.0")
        assert meta.source == "test"
        assert meta.version == "2.0.0"


class TestNetLiquidityResponse:
    """Tests for NetLiquidityResponse model."""

    @pytest.fixture
    def valid_response(self):
        """Create a valid response fixture."""
        return NetLiquidityResponse(
            value=6000.0,
            walcl=8000.0,
            tga=1000.0,
            rrp=1000.0,
            weekly_delta=50.0,
            sentiment="BULLISH",
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )

    def test_valid_response(self, valid_response):
        """Test valid response creation."""
        assert valid_response.value == 6000.0
        assert valid_response.walcl == 8000.0
        assert valid_response.sentiment == "BULLISH"

    def test_serialization(self, valid_response):
        """Test JSON serialization."""
        json_data = valid_response.model_dump_json()
        assert "value" in json_data
        assert "6000.0" in json_data

    def test_net_liquidity_formula_check(self, valid_response):
        """Verify WALCL - TGA - RRP = Net Liquidity."""
        expected = valid_response.walcl - valid_response.tga - valid_response.rrp
        assert valid_response.value == expected


class TestGlobalLiquidityResponse:
    """Tests for GlobalLiquidityResponse model."""

    @pytest.fixture
    def valid_response(self):
        """Create a valid response fixture."""
        return GlobalLiquidityResponse(
            value=35000.0,
            components=GlobalLiquidityComponent(
                fed_usd=6000.0,
                ecb_usd=10000.0,
                boj_usd=8000.0,
                pboc_usd=11000.0,
            ),
            weekly_delta=100.0,
            coverage_pct=95.0,
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )

    def test_valid_response(self, valid_response):
        """Test valid response creation."""
        assert valid_response.value == 35000.0
        assert valid_response.coverage_pct == 95.0
        assert valid_response.components.fed_usd == 6000.0

    def test_tier2_components_optional(self):
        """Test that Tier 2 components are optional."""
        response = GlobalLiquidityResponse(
            value=35000.0,
            components=GlobalLiquidityComponent(
                fed_usd=6000.0,
                ecb_usd=10000.0,
                boj_usd=8000.0,
                pboc_usd=11000.0,
            ),
            weekly_delta=100.0,
            coverage_pct=95.0,
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.components.boe_usd is None
        assert response.components.snb_usd is None
        assert response.components.boc_usd is None

    def test_tier2_components_included(self):
        """Test Tier 2 components can be included."""
        response = GlobalLiquidityResponse(
            value=36500.0,
            components=GlobalLiquidityComponent(
                fed_usd=6000.0,
                ecb_usd=10000.0,
                boj_usd=8000.0,
                pboc_usd=11000.0,
                boe_usd=1000.0,
                snb_usd=300.0,
                boc_usd=200.0,
            ),
            weekly_delta=100.0,
            coverage_pct=99.0,
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.components.boe_usd == 1000.0
        assert response.coverage_pct == 99.0


class TestRegimeResponse:
    """Tests for RegimeResponse model."""

    def test_expansion_response(self):
        """Test EXPANSION regime response."""
        response = RegimeResponse(
            regime="EXPANSION",
            intensity=75.0,
            confidence="HIGH",
            components="NET:0.70 GLO:0.75 SQE:0.60",
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.regime == "EXPANSION"
        assert response.intensity == 75.0
        assert response.confidence == "HIGH"

    def test_contraction_response(self):
        """Test CONTRACTION regime response."""
        response = RegimeResponse(
            regime="CONTRACTION",
            intensity=60.0,
            confidence="MEDIUM",
            components="NET:0.30 GLO:0.35 SQE:0.20",
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.regime == "CONTRACTION"
        assert response.confidence == "MEDIUM"

    def test_intensity_bounds(self):
        """Test intensity field bounds validation."""
        # Valid bounds
        response = RegimeResponse(
            regime="EXPANSION",
            intensity=0.0,
            confidence="LOW",
            components="NET:0.50 GLO:0.50 SQE:0.50",
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.intensity == 0.0

        response = RegimeResponse(
            regime="EXPANSION",
            intensity=100.0,
            confidence="HIGH",
            components="NET:1.00 GLO:1.00 SQE:1.00",
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.intensity == 100.0

    def test_intensity_out_of_bounds(self):
        """Test intensity rejects out-of-bounds values."""
        with pytest.raises(ValidationError):
            RegimeResponse(
                regime="EXPANSION",
                intensity=-1.0,  # Invalid
                confidence="HIGH",
                components="NET:0.50",
                as_of_date=datetime.now(UTC),
                metadata=APIMetadata(timestamp=datetime.now(UTC)),
            )

        with pytest.raises(ValidationError):
            RegimeResponse(
                regime="EXPANSION",
                intensity=101.0,  # Invalid
                confidence="HIGH",
                components="NET:0.50",
                as_of_date=datetime.now(UTC),
                metadata=APIMetadata(timestamp=datetime.now(UTC)),
            )


class TestStealthQEResponse:
    """Tests for StealthQEResponse model."""

    def test_very_active_response(self):
        """Test VERY_ACTIVE stealth QE response."""
        response = StealthQEResponse(
            score=85.0,
            status="VERY_ACTIVE",
            rrp_level=500.0,
            rrp_velocity=-15.0,
            tga_level=300.0,
            tga_spending=100.0,
            fed_total=8000.0,
            fed_change=50.0,
            components="RRP:80% TGA:70% FED:40%",
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.score == 85.0
        assert response.status == "VERY_ACTIVE"

    def test_optional_fields(self):
        """Test optional weekly change fields can be None."""
        response = StealthQEResponse(
            score=0.0,
            status="MINIMAL",
            rrp_level=500.0,
            rrp_velocity=None,
            tga_level=300.0,
            tga_spending=None,
            fed_total=8000.0,
            fed_change=None,
            components="RRP:0% TGA:0% FED:0%",
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.rrp_velocity is None
        assert response.tga_spending is None
        assert response.fed_change is None

    def test_score_bounds(self):
        """Test score field bounds validation."""
        # Valid at 0
        response = StealthQEResponse(
            score=0.0,
            status="MINIMAL",
            rrp_level=500.0,
            rrp_velocity=None,
            tga_level=300.0,
            tga_spending=None,
            fed_total=8000.0,
            fed_change=None,
            components="RRP:0%",
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.score == 0.0

        # Valid at 100
        response = StealthQEResponse(
            score=100.0,
            status="VERY_ACTIVE",
            rrp_level=500.0,
            rrp_velocity=-20.0,
            tga_level=300.0,
            tga_spending=200.0,
            fed_total=8000.0,
            fed_change=100.0,
            components="RRP:100%",
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
        assert response.score == 100.0

    def test_score_out_of_bounds(self):
        """Test score rejects out-of-bounds values."""
        with pytest.raises(ValidationError):
            StealthQEResponse(
                score=-1.0,  # Invalid
                status="MINIMAL",
                rrp_level=500.0,
                rrp_velocity=None,
                tga_level=300.0,
                tga_spending=None,
                fed_total=8000.0,
                fed_change=None,
                components="RRP:0%",
                as_of_date=datetime.now(UTC),
                metadata=APIMetadata(timestamp=datetime.now(UTC)),
            )


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_healthy_response(self):
        """Test healthy status response."""
        response = HealthResponse(
            status="healthy",
            questdb_connected=True,
        )
        assert response.status == "healthy"
        assert response.questdb_connected is True
        assert response.version == "1.0.0"

    def test_degraded_response(self):
        """Test degraded status response."""
        response = HealthResponse(
            status="degraded",
            questdb_connected=False,
        )
        assert response.status == "degraded"
        assert response.questdb_connected is False


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response(self):
        """Test error response creation."""
        response = ErrorResponse(
            error="ServiceUnavailable",
            message="Unable to calculate liquidity",
            detail="FRED API timeout",
        )
        assert response.error == "ServiceUnavailable"
        assert response.message == "Unable to calculate liquidity"
        assert response.detail == "FRED API timeout"

    def test_error_without_detail(self):
        """Test error response without detail."""
        response = ErrorResponse(
            error="InternalError",
            message="Something went wrong",
        )
        assert response.detail is None
