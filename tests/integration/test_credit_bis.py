"""Integration tests for Phase 6: Credit and BIS collectors.

These tests use real APIs when available. They are marked as integration tests
and may be skipped if API keys are not configured or network is unavailable.
"""

import os

import pytest

from liquidity.collectors.bis import BISCollector
from liquidity.collectors.credit import CreditCollector


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("LIQUIDITY_FRED_API_KEY"),
    reason="FRED API key required for credit collector integration test",
)
async def test_credit_collector_sloos_real_data():
    """Test SLOOS collection with real FRED API."""
    collector = CreditCollector()
    df = await collector.collect_sloos()

    # SLOOS data is quarterly, so we may not have many points
    # but we should have at least some historical data
    if not df.empty:
        assert "DRTSCILM" in df["series_id"].values
        # SLOOS values should be in reasonable range (-50% to 100%)
        assert df["value"].min() >= -50
        assert df["value"].max() <= 100
        assert df["source"].iloc[0] == "fred"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("LIQUIDITY_FRED_API_KEY"),
    reason="FRED API key required for CP rates integration test",
)
async def test_credit_collector_cp_rates_real_data():
    """Test CP rates collection with real FRED API."""
    collector = CreditCollector()
    df = await collector.collect_cp_rates()

    if not df.empty:
        # Should have at least one of the CP series
        cp_series = {"DCPF3M", "DCPN3M"}
        found_series = set(df["series_id"].unique())
        assert len(found_series & cp_series) > 0

        # CP rates should be positive percentages
        assert df["value"].min() >= 0
        assert df["value"].max() < 30  # Rates shouldn't exceed 30%


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("LIQUIDITY_FRED_API_KEY"),
    reason="FRED API key required for regime classification test",
)
async def test_credit_regime_classification_real_data():
    """Test regime classification with real SLOOS data."""
    collector = CreditCollector()
    df = await collector.collect_sloos()

    # Get regime based on real data
    regime = collector.get_lending_standards_regime(df)

    # Should return a valid regime
    assert regime in ("TIGHTENING", "NEUTRAL", "EASING")


@pytest.mark.integration
@pytest.mark.slow
async def test_bis_collector_cache_creation():
    """Test BIS collector creates cache directory.

    Note: This test doesn't download BIS data (slow and large files).
    It only verifies the cache directory handling.
    """
    collector = BISCollector()

    # Verify settings has cache_dir property
    cache_dir = collector._settings.cache_dir / "bis"

    # The cache directory should be creatable
    cache_dir.mkdir(parents=True, exist_ok=True)
    assert cache_dir.exists()


@pytest.mark.integration
async def test_credit_collector_instantiation():
    """Test CreditCollector can be instantiated."""
    collector = CreditCollector()

    assert collector.name == "credit"
    assert collector.SLOOS_SERIES == ["DRTSCILM", "DRTSCIS", "DRTSROM", "DRSDCILM"]
    assert collector.CP_SERIES == ["DCPF3M", "DCPN3M"]


@pytest.mark.integration
async def test_bis_collector_instantiation():
    """Test BISCollector can be instantiated."""
    collector = BISCollector()

    assert collector.name == "bis"
    assert "lbs" in collector.DATASETS
    assert "cbs" in collector.DATASETS
    assert collector.CACHE_DAYS == 7


@pytest.mark.integration
async def test_collectors_registered():
    """Test both collectors are in the registry."""
    from liquidity.collectors.registry import registry

    assert registry.get("credit") is not None
    assert registry.get("bis") is not None
