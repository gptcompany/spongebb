"""Tests for pure numpy backtesting engine."""

import numpy as np
import pandas as pd
import pytest

from liquidity.backtesting.engine.vectorbt_engine import (
    BacktestResult,
    VectorBTBacktester,
)


class TestVectorBTBacktester:
    """Test backtester."""

    @pytest.fixture
    def sample_prices(self) -> pd.Series:
        """Create sample price series with uptrend."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        returns = np.random.normal(0.0003, 0.015, 500)
        prices = 100 * np.exp(np.cumsum(returns))
        return pd.Series(prices, index=dates, name="price")

    @pytest.fixture
    def sample_signals(self, sample_prices: pd.Series) -> pd.Series:
        """Create sample signal series."""
        signals = np.zeros(len(sample_prices))
        for i in range(0, len(signals), 100):
            signals[i : i + 50] = 1  # Long
            signals[i + 50 : i + 100] = -1  # Short
        return pd.Series(signals, index=sample_prices.index, name="signal")

    def test_run_backtest_returns_result(
        self, sample_prices: pd.Series, sample_signals: pd.Series
    ) -> None:
        """Backtest should return BacktestResult."""
        bt = VectorBTBacktester()
        result = bt.run_backtest(sample_prices, sample_signals)

        assert isinstance(result, BacktestResult)
        assert result.total_return is not None
        assert result.sharpe_ratio is not None
        assert result.equity_curve is not None

    def test_equity_curve_length(
        self, sample_prices: pd.Series, sample_signals: pd.Series
    ) -> None:
        """Equity curve should match price length."""
        bt = VectorBTBacktester()
        result = bt.run_backtest(sample_prices, sample_signals)

        assert len(result.equity_curve) == len(sample_prices)

    def test_initial_capital_used(
        self, sample_prices: pd.Series, sample_signals: pd.Series
    ) -> None:
        """Initial capital should set starting value."""
        bt = VectorBTBacktester(initial_capital=50000)
        result = bt.run_backtest(sample_prices, sample_signals)

        assert result.initial_capital == 50000
        assert abs(result.equity_curve.iloc[0] - 50000) < 1000

    def test_commission_affects_returns(
        self, sample_prices: pd.Series, sample_signals: pd.Series
    ) -> None:
        """Higher commission should reduce returns."""
        bt_low = VectorBTBacktester(commission=0.0001)
        bt_high = VectorBTBacktester(commission=0.01)

        result_low = bt_low.run_backtest(sample_prices, sample_signals)
        result_high = bt_high.run_backtest(sample_prices, sample_signals)

        assert result_low.total_return >= result_high.total_return

    def test_max_drawdown_exists(
        self, sample_prices: pd.Series, sample_signals: pd.Series
    ) -> None:
        """Max drawdown should be a valid number."""
        bt = VectorBTBacktester()
        result = bt.run_backtest(sample_prices, sample_signals)

        assert result.max_drawdown is not None
        assert not pd.isna(result.max_drawdown)
        assert result.max_drawdown <= 0

    def test_trades_extracted(
        self, sample_prices: pd.Series, sample_signals: pd.Series
    ) -> None:
        """Trades DataFrame should contain extracted trades."""
        bt = VectorBTBacktester()
        result = bt.run_backtest(sample_prices, sample_signals)

        assert result.total_trades > 0
        assert isinstance(result.trades, pd.DataFrame)
        if not result.trades.empty:
            assert "entry_date" in result.trades.columns
            assert "return_pct" in result.trades.columns

    def test_multi_asset_backtest(self) -> None:
        """Multi-asset backtest should work."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=200, freq="B")

        prices = pd.DataFrame(
            {
                "btc": 100 * np.exp(np.cumsum(np.random.normal(0.001, 0.03, 200))),
                "spx": 100 * np.exp(np.cumsum(np.random.normal(0.0003, 0.01, 200))),
            },
            index=dates,
        )

        signals = pd.DataFrame(
            {
                "btc": np.where(np.arange(200) % 50 < 25, 1, 0),
                "spx": np.where(np.arange(200) % 50 < 25, 1, 0),
            },
            index=dates,
        )

        bt = VectorBTBacktester()
        result = bt.run_multi_asset_backtest(prices, signals)

        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) == 200

    def test_parameter_sweep(self, sample_prices: pd.Series) -> None:
        """Parameter sweep should return results DataFrame."""

        def make_signals(window: int, threshold: float) -> pd.Series:
            returns = sample_prices.pct_change(window)
            signals = pd.Series(0, index=sample_prices.index)
            signals[returns > threshold] = 1
            signals[returns < -threshold] = -1
            return signals

        bt = VectorBTBacktester()
        results = bt.parameter_sweep(
            sample_prices,
            make_signals,
            {"window": [10, 20], "threshold": [0.02, 0.05]},
        )

        assert isinstance(results, pd.DataFrame)
        assert len(results) == 4  # 2x2 combinations
        assert "sharpe" in results.columns
        assert "return" in results.columns

    def test_benchmark_return(self, sample_prices: pd.Series, sample_signals: pd.Series) -> None:
        """Benchmark return should be calculated when provided."""
        benchmark = sample_prices * 1.001  # slightly different
        bt = VectorBTBacktester()
        result = bt.run_backtest(sample_prices, sample_signals, benchmark=benchmark)

        assert result.benchmark_return != 0.0

    def test_all_flat_signals(self, sample_prices: pd.Series) -> None:
        """All-flat signals should produce zero trades."""
        flat = pd.Series(0, index=sample_prices.index)
        bt = VectorBTBacktester()
        result = bt.run_backtest(sample_prices, flat)

        assert result.total_trades == 0
        assert result.total_return == pytest.approx(0.0, abs=0.1)


class TestBacktestResult:
    """Test BacktestResult dataclass."""

    def test_result_fields(self) -> None:
        """Verify all required fields exist."""
        result = BacktestResult(
            total_return=10.5,
            annualized_return=12.0,
            benchmark_return=8.0,
            volatility=15.0,
            sharpe_ratio=0.8,
            sortino_ratio=1.2,
            max_drawdown=-15.0,
            calmar_ratio=0.8,
            total_trades=50,
            win_rate=55.0,
            avg_win=2.5,
            avg_loss=-1.5,
            profit_factor=1.8,
            equity_curve=pd.Series([100, 105, 110]),
            drawdown_series=pd.Series([0, -0.02, -0.01]),
            trades=pd.DataFrame(),
            start_date=pd.Timestamp("2020-01-01"),
            end_date=pd.Timestamp("2022-01-01"),
        )

        assert result.sharpe_ratio == 0.8
        assert result.total_trades == 50

    def test_result_repr_excludes_series(self) -> None:
        """Result repr should not include large series."""
        result = BacktestResult(
            total_return=10.5,
            annualized_return=12.0,
            benchmark_return=8.0,
            volatility=15.0,
            sharpe_ratio=0.8,
            sortino_ratio=1.2,
            max_drawdown=-15.0,
            calmar_ratio=0.8,
            total_trades=50,
            win_rate=55.0,
            avg_win=2.5,
            avg_loss=-1.5,
            profit_factor=1.8,
            equity_curve=pd.Series([100, 105, 110]),
            drawdown_series=pd.Series([0, -0.02, -0.01]),
            trades=pd.DataFrame(),
            start_date=pd.Timestamp("2020-01-01"),
            end_date=pd.Timestamp("2022-01-01"),
        )

        repr_str = repr(result)
        assert "equity_curve" not in repr_str
        assert "sharpe_ratio" in repr_str
