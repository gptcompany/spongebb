"""Integration tests for Phase 7: Liquidity Calculators.

These tests verify the calculators work correctly with real data.
They are marked as integration tests and may be skipped if API keys are not configured.
"""

import os

import pytest

from liquidity.calculators import (
    NetLiquidityCalculator,
    GlobalLiquidityCalculator,
    StealthQECalculator,
    LiquidityValidator,
    Sentiment,
)


@pytest.mark.integration
async def test_net_liquidity_calculator_instantiation():
    """Test NetLiquidityCalculator can be instantiated."""
    calc = NetLiquidityCalculator()

    assert calc is not None
    assert "walcl" in calc.series_config
    assert "tga" in calc.series_config
    assert "rrp" in calc.series_config


@pytest.mark.integration
async def test_global_liquidity_calculator_instantiation():
    """Test GlobalLiquidityCalculator can be instantiated."""
    calc = GlobalLiquidityCalculator()

    assert calc is not None
    assert calc.GLOBAL_CB_ESTIMATE == 35_000


@pytest.mark.integration
async def test_stealth_qe_calculator_instantiation():
    """Test StealthQECalculator can be instantiated."""
    calc = StealthQECalculator()

    assert calc is not None
    assert calc.SCORE_CONFIG["WEIGHT_RRP"] == 0.40
    assert calc.SCORE_CONFIG["WEIGHT_TGA"] == 0.40
    assert calc.SCORE_CONFIG["WEIGHT_FED"] == 0.20


@pytest.mark.integration
async def test_liquidity_validator_instantiation():
    """Test LiquidityValidator can be instantiated."""
    validator = LiquidityValidator()

    assert validator is not None
    assert validator.GLOBAL_CB_ESTIMATE == 35_000


@pytest.mark.integration
async def test_sentiment_classification():
    """Test sentiment classification logic."""
    # BULLISH: weekly delta > $50B
    assert NetLiquidityCalculator.get_sentiment(60.0) == Sentiment.BULLISH

    # BEARISH: weekly delta < -$50B
    assert NetLiquidityCalculator.get_sentiment(-60.0) == Sentiment.BEARISH

    # NEUTRAL: -$50B <= weekly delta <= $50B
    assert NetLiquidityCalculator.get_sentiment(0.0) == Sentiment.NEUTRAL
    assert NetLiquidityCalculator.get_sentiment(50.0) == Sentiment.NEUTRAL
    assert NetLiquidityCalculator.get_sentiment(-50.0) == Sentiment.NEUTRAL


@pytest.mark.integration
async def test_stealth_qe_status_classification():
    """Test Stealth QE status classification."""
    calc = StealthQECalculator()

    # VERY_ACTIVE: 70-100
    assert calc.get_status(85.0) == "VERY_ACTIVE"

    # ACTIVE: 50-70
    assert calc.get_status(60.0) == "ACTIVE"

    # MODERATE: 30-50
    assert calc.get_status(40.0) == "MODERATE"

    # LOW: 10-30
    assert calc.get_status(20.0) == "LOW"

    # MINIMAL: 0-10
    assert calc.get_status(5.0) == "MINIMAL"


@pytest.mark.integration
async def test_validator_net_liquidity_check():
    """Test Net Liquidity formula validation."""
    validator = LiquidityValidator()

    # Valid case: WALCL - TGA - RRP = Net Liquidity
    result = validator.validate_net_liquidity(
        walcl=8000.0,
        tga=800.0,
        rrp=500.0,
        reported_net_liq=6700.0,  # 8000 - 800 - 500 = 6700
    )
    assert result.passed is True

    # Invalid case: wrong Net Liquidity
    result = validator.validate_net_liquidity(
        walcl=8000.0,
        tga=800.0,
        rrp=500.0,
        reported_net_liq=7000.0,  # Should be 6700
    )
    assert result.passed is False


@pytest.mark.integration
async def test_validator_coverage_check():
    """Test coverage verification."""
    validator = LiquidityValidator()

    # Tier 1 total of $30T = 85.7% of $35T estimate
    result = validator.validate_coverage(tier1_total=30_000.0)
    assert result.passed is True
    assert result.actual >= 85.0

    # Tier 1 total of $25T = 71.4% of $35T estimate (below 85%)
    result = validator.validate_coverage(tier1_total=25_000.0)
    assert result.passed is False


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("LIQUIDITY_FRED_API_KEY"),
    reason="FRED API key required for real data test",
)
async def test_net_liquidity_real_data():
    """Test Net Liquidity calculation with real FRED data."""
    calc = NetLiquidityCalculator()
    result = await calc.get_current()

    # Net Liquidity should be in reasonable range (2-10 trillion)
    assert 2000 < result.net_liquidity < 10000

    # WALCL should be larger than TGA and RRP
    assert result.walcl > result.tga
    assert result.walcl > result.rrp

    # Formula should hold
    expected = result.walcl - result.tga - result.rrp
    assert abs(result.net_liquidity - expected) < 1.0  # Within $1B


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("LIQUIDITY_FRED_API_KEY"),
    reason="FRED API key required for real data test",
)
async def test_stealth_qe_real_data():
    """Test Stealth QE calculation with real FRED data."""
    calc = StealthQECalculator()
    result = await calc.get_current()

    # Score should be 0-100
    assert 0 <= result.score_daily <= 100

    # Status should be valid
    assert result.status in ["VERY_ACTIVE", "ACTIVE", "MODERATE", "LOW", "MINIMAL"]

    # Levels should be positive
    assert result.rrp_level >= 0
    assert result.tga_level >= 0
    assert result.fed_total > 0
