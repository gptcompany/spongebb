from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

from liquidity.nowcasting.engine import NowcastConfig, NowcastEngine
from liquidity.nowcasting.kalman import NowcastResult


@pytest.fixture
def config():
    return NowcastConfig(
        innovation_threshold=2.0,
        min_observations=5,
        max_data_age_hours=24,
    )


@pytest.fixture
def mock_state_space():
    ss = MagicMock()
    ss.is_fitted = False

    # Mock nowcast result
    result = NowcastResult(
        mean=6.5,
        std=0.1,
        ci_lower=6.3,
        ci_upper=6.7,
        timestamp=datetime.now(UTC),
        innovation=0.05,
        kalman_gain=0.5,
        filtered_state=6.4
    )
    ss.nowcast.return_value = result
    return ss


@pytest.fixture
def engine(config, mock_state_space):
    engine = NowcastEngine(config=config, state_space=mock_state_space)

    # Mock collectors
    engine._tga_collector = AsyncMock()
    engine._nyfed_collector = AsyncMock()
    engine._sofr_collector = AsyncMock()

    # Mock data return values
    dates = pd.date_range(end=datetime.now(UTC), periods=10, freq="D")
    base_df = pd.DataFrame({"timestamp": dates, "value": np.random.randn(10)})

    engine._tga_collector.collect.return_value = base_df.copy()
    engine._nyfed_collector.collect_rrp.return_value = base_df.copy()
    engine._sofr_collector.collect.return_value = base_df.copy()

    return engine


def test_nowcast_config_normalization():
    """Test that weights are normalized to sum to 1.0."""
    config = NowcastConfig(proxy_weights={"A": 2.0, "B": 2.0})
    assert config.proxy_weights["A"] == 0.5
    assert config.proxy_weights["B"] == 0.5


@pytest.mark.asyncio
async def test_run_daily_nowcast_success(engine, mock_state_space):
    """Test successful daily nowcast execution."""
    result = await engine.run_daily_nowcast()

    assert isinstance(result, NowcastResult)
    assert result.mean == 6.5

    # Assert collectors were called
    engine._tga_collector.collect.assert_called_once()
    engine._nyfed_collector.collect_rrp.assert_called_once()
    engine._sofr_collector.collect.assert_called_once()

    # Assert state space was fitted
    mock_state_space.fit.assert_called_once()
    mock_state_space.nowcast.assert_called_once_with(steps=1)


@pytest.mark.asyncio
async def test_run_daily_nowcast_update(engine, mock_state_space):
    """Test daily nowcast execution when model is already fitted."""
    mock_state_space.is_fitted = True

    result = await engine.run_daily_nowcast()

    assert isinstance(result, NowcastResult)

    # Assert state space was updated, not fitted
    mock_state_space.fit.assert_not_called()
    mock_state_space.update.assert_called_once()
    mock_state_space.nowcast.assert_called_once_with(steps=1)


def test_validate_data_freshness(engine):
    """Test data quality validation."""
    now = datetime.now(UTC)

    # Fresh data
    fresh_df = pd.DataFrame({"timestamp": [now], "value": [1.0]})
    # Stale data
    stale_df = pd.DataFrame({"timestamp": [now - timedelta(days=2)], "value": [1.0]})
    # Test valid case
    report = engine._validate_data(fresh_df, fresh_df, fresh_df)
    assert bool(report.is_valid) is True
    assert report.tga_fresh is True
    assert len(report.warnings) == 0

    # Test stale case
    report2 = engine._validate_data(stale_df, stale_df, fresh_df)
    assert bool(report2.is_valid) is False
    assert report2.tga_fresh is False
    assert len(report2.warnings) > 0


@pytest.mark.asyncio
async def test_run_daily_nowcast_insufficient_quality(engine):
    """Test nowcast raises error on bad data quality."""
    stale_date = datetime.now(UTC) - timedelta(days=5)
    stale_df = pd.DataFrame({"timestamp": [stale_date], "value": [1.0]})

    engine._tga_collector.collect.return_value = stale_df
    engine._nyfed_collector.collect_rrp.return_value = stale_df

    with pytest.raises(ValueError, match="Insufficient data quality"):
        await engine.run_daily_nowcast()


def test_combine_proxies(engine):
    """Test proxy combination logic."""
    dates = pd.date_range("2026-01-01", periods=3, tz=UTC)

    tga = pd.DataFrame({"timestamp": dates, "value": [1000000.0, 2000000.0, 3000000.0]})  # millions
    rrp = pd.DataFrame({"timestamp": dates, "value": [1000.0, 2000.0, 3000.0]})  # billions
    sofr = pd.DataFrame({"timestamp": dates, "value": [5.0, 5.0, 5.0]})

    combined = engine._combine_proxies(tga, rrp, sofr)

    # Check length
    assert len(combined) == 3

    # Calculate expected for first row: bias + (-(1T + 1T))
    # 1000000 millions = 1T
    # 1000 billions = 1T
    # bias = 6.0
    # Expected: 6.0 - 2.0 = 4.0
    assert np.isclose(combined.iloc[0], 4.0)


def test_is_significant_move(engine):
    """Test significant move detection."""
    # Setup significant result (z_score = 0.5 / 0.1 = 5.0 > 2.0)
    sig_result = NowcastResult(
        mean=6.5, std=0.1, ci_lower=6.3, ci_upper=6.7,
        timestamp=datetime.now(UTC), innovation=0.5,
        kalman_gain=0.5, filtered_state=6.4
    )
    assert engine.is_significant_move(sig_result) is True

    # Setup insignificant result (z_score = 0.05 / 0.1 = 0.5 < 2.0)
    insig_result = NowcastResult(
        mean=6.5, std=0.1, ci_lower=6.3, ci_upper=6.7,
        timestamp=datetime.now(UTC), innovation=0.05,
        kalman_gain=0.5, filtered_state=6.4
    )
    assert engine.is_significant_move(insig_result) is False


def test_get_nowcast_history(engine):
    """Test history retrieval."""
    assert engine.get_nowcast_history().empty

    # Add a mock result
    result = NowcastResult(
        mean=6.5, std=0.1, ci_lower=6.3, ci_upper=6.7,
        timestamp=datetime.now(UTC), innovation=0.05,
        kalman_gain=0.5, filtered_state=6.4
    )
    engine._nowcast_history.append(result)

    history_df = engine.get_nowcast_history()
    assert not history_df.empty
    assert len(history_df) == 1
    assert "mean" in history_df.columns
    assert history_df.iloc[0]["mean"] == 6.5
