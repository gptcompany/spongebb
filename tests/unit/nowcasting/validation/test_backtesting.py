from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from liquidity.nowcasting.validation.backtesting import (
    BacktestConfig,
    BacktestResult,
    NowcastBacktester,
)


@pytest.fixture
def sample_data():
    dates = pd.date_range("2024-01-01", periods=400)
    data = np.linspace(5.0, 6.0, 400) + np.random.normal(0, 0.01, 400)
    return pd.Series(data, index=dates)


def test_backtest_config():
    config = BacktestConfig(train_window=100, release_lag=3)
    assert config.train_window == 100
    assert config.release_lag == 3


def test_backtest_result_to_dict():
    result = BacktestResult(
        date=pd.Timestamp("2024-01-01"),
        nowcast=5.5,
        ci_lower=5.4,
        ci_upper=5.6,
        std=0.05,
        official=5.52,
        error=-0.02,
        pct_error=0.36,
        within_ci=True,
    )
    d = result.to_dict()
    assert d["date"] == pd.Timestamp("2024-01-01")
    assert d["nowcast"] == 5.5


@patch("liquidity.nowcasting.validation.backtesting.LiquidityStateSpace")
def test_run_backtest_success(mock_lss_cls, sample_data):
    # Setup mock model
    mock_model = MagicMock()
    mock_lss_cls.return_value = mock_model

    # Mock nowcast result
    mock_nowcast = MagicMock()
    mock_nowcast.mean = 5.5
    mock_nowcast.ci_lower = 5.4
    mock_nowcast.ci_upper = 5.6
    mock_nowcast.std = 0.05
    mock_model.nowcast.return_value = mock_nowcast

    config = BacktestConfig(train_window=200, min_test_periods=10, release_lag=5)
    backtester = NowcastBacktester(config)

    summary = backtester.run_backtest(sample_data)

    assert summary.n_tests > 0
    assert len(summary.results) == summary.n_tests
    assert isinstance(summary.to_dataframe(), pd.DataFrame)
    assert "BacktestSummary" in repr(summary)
    assert "NowcastBacktester" in repr(backtester)


def test_run_backtest_insufficient_data(sample_data):
    # Total 400 points
    # train_window 350 + release_lag 5 = 355
    # n_test = 400 - 355 = 45
    # min_test_periods = 50 -> should fail
    config = BacktestConfig(train_window=350, min_test_periods=50, release_lag=5)
    backtester = NowcastBacktester(config)

    with pytest.raises(ValueError, match="Insufficient data for backtesting"):
        backtester.run_backtest(sample_data)


def test_run_backtest_missing_column():
    df = pd.DataFrame({"wrong_col": [1, 2, 3]})
    backtester = NowcastBacktester()
    with pytest.raises(ValueError, match="Column 'official' not found"):
        backtester.run_backtest(df)


@patch("liquidity.nowcasting.validation.backtesting.NowcastBacktester.run_backtest")
def test_expanding_window_backtest(mock_run, sample_data):
    mock_summary = MagicMock()
    mock_run.return_value = mock_summary

    backtester = NowcastBacktester()
    summaries = backtester.run_expanding_window_backtest(
        sample_data, initial_window=100, expansion_step=100
    )

    # Should run for windows 100, 200, 300
    assert len(summaries) >= 3


@patch("liquidity.nowcasting.validation.backtesting.NowcastBacktester.run_backtest")
def test_cross_validate(mock_run, sample_data):
    mock_summary = MagicMock()
    mock_run.return_value = mock_summary

    backtester = NowcastBacktester()
    summaries = backtester.cross_validate(sample_data, n_folds=3)

    assert len(summaries) == 3
