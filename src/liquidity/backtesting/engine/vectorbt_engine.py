"""Pure numpy backtesting engine for regime-based strategies.

Replaces the former VectorBT dependency with direct numpy calculations.
Optimized for macro regime validation (200-500 daily data points).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import product

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    """Results from a backtest run."""

    # Returns
    total_return: float
    annualized_return: float
    benchmark_return: float

    # Risk metrics
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float

    # Trade statistics
    total_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float

    # Time series
    equity_curve: pd.Series = field(repr=False)
    drawdown_series: pd.Series = field(repr=False)
    trades: pd.DataFrame = field(repr=False)

    # Metadata
    start_date: pd.Timestamp = field(repr=False)
    end_date: pd.Timestamp = field(repr=False)
    initial_capital: float = field(default=100000)


def _compute_trade_stats(
    trade_returns: np.ndarray,
) -> tuple[int, float, float, float, float]:
    """Compute trade-level statistics from per-trade returns.

    Returns:
        (total_trades, win_rate, avg_win, avg_loss, profit_factor)
    """
    n = len(trade_returns)
    if n == 0:
        return 0, 0.0, 0.0, 0.0, 0.0

    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns < 0]

    win_rate = (len(wins) / n) * 100 if n > 0 else 0.0
    avg_win = float(wins.mean()) * 100 if len(wins) > 0 else 0.0
    avg_loss = float(losses.mean()) * 100 if len(losses) > 0 else 0.0
    profit_factor = (
        abs(float(wins.sum()) / float(losses.sum()))
        if len(losses) > 0 and losses.sum() != 0
        else 0.0
    )
    return n, win_rate, avg_win, avg_loss, profit_factor


def _extract_trades(
    signals: pd.Series, prices: pd.Series
) -> tuple[pd.DataFrame, np.ndarray]:
    """Extract individual trades from signal series.

    A trade opens when signal changes to non-zero and closes when it changes.

    Returns:
        (trades_df, per_trade_return_array)
    """
    sig = signals.values
    px = prices.values
    idx = prices.index

    trades = []
    trade_returns = []
    i = 0
    n = len(sig)

    while i < n:
        if sig[i] != 0:
            direction = sig[i]  # 1 = long, -1 = short
            entry_idx = i
            entry_px = px[i]
            # Advance until signal changes
            j = i + 1
            while j < n and sig[j] == direction:
                j += 1
            exit_idx = min(j, n - 1)
            exit_px = px[exit_idx]

            ret = exit_px / entry_px - 1 if direction == 1 else entry_px / exit_px - 1

            trades.append(
                {
                    "entry_date": idx[entry_idx],
                    "exit_date": idx[exit_idx],
                    "direction": "long" if direction == 1 else "short",
                    "entry_price": entry_px,
                    "exit_price": exit_px,
                    "return_pct": ret * 100,
                    "duration": exit_idx - entry_idx,
                }
            )
            trade_returns.append(ret)
            i = j
        else:
            i += 1

    df = pd.DataFrame(trades) if trades else pd.DataFrame()
    return df, np.array(trade_returns) if trade_returns else np.array([])


class VectorBTBacktester:
    """Pure numpy backtesting engine for regime-based strategies.

    Supports long/short signals (-1, 0, 1), commission + slippage,
    multi-asset portfolios, and parameter sweeps.
    """

    def __init__(
        self,
        initial_capital: float = 100000,
        commission: float = 0.001,  # 0.1% = 10 bps
        slippage: float = 0.0005,  # 0.05% = 5 bps
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run_backtest(
        self,
        prices: pd.Series,
        signals: pd.Series,
        benchmark: pd.Series | None = None,
    ) -> BacktestResult:
        """Run backtest with regime signals.

        Args:
            prices: Asset price series
            signals: Signal series (-1, 0, 1)
            benchmark: Optional benchmark for comparison

        Returns:
            BacktestResult with all metrics
        """
        px = prices.values.astype(float)
        sig = signals.reindex(prices.index, fill_value=0).values.astype(float)
        n = len(px)

        # Daily asset returns
        asset_returns = np.diff(px) / px[:-1]  # length n-1

        # Strategy returns: position[t-1] * asset_return[t]
        position = sig[:-1]  # position held during period t-1 -> t

        # Apply transaction costs on position changes
        pos_changes = np.abs(np.diff(np.concatenate(([0], sig))))  # length n
        cost = pos_changes[1:] * (self.commission + self.slippage)  # length n-1

        strategy_returns = position * asset_returns - cost

        # Equity curve
        equity = self.initial_capital * np.cumprod(1 + strategy_returns)
        equity = np.concatenate(([self.initial_capital], equity))
        equity_series = pd.Series(equity, index=prices.index)

        # Drawdown
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        drawdown_series = pd.Series(drawdown, index=prices.index)

        # Metrics
        total_return = (equity[-1] / self.initial_capital - 1) * 100
        ann_factor = 252 / max(n - 1, 1)
        ann_return = ((1 + total_return / 100) ** ann_factor - 1) * 100

        daily_std = np.std(strategy_returns, ddof=1) if len(strategy_returns) > 1 else 0
        volatility = daily_std * np.sqrt(252) * 100

        daily_mean = np.mean(strategy_returns)
        sharpe = (daily_mean / daily_std * np.sqrt(252)) if daily_std > 0 else 0.0

        # Sortino: downside deviation
        downside = strategy_returns[strategy_returns < 0]
        downside_std = np.sqrt(np.mean(downside**2)) if len(downside) > 0 else 0
        sortino = (daily_mean / downside_std * np.sqrt(252)) if downside_std > 0 else 0.0

        max_dd = float(drawdown.min()) * 100
        calmar = ann_return / abs(max_dd) if max_dd != 0 else 0.0

        # Benchmark
        if benchmark is not None:
            bench_return = (benchmark.iloc[-1] / benchmark.iloc[0] - 1) * 100
        else:
            bench_return = 0.0

        # Trade stats
        trades_df, trade_ret_arr = _extract_trades(
            pd.Series(sig, index=prices.index), prices
        )
        # Subtract round-trip cost from each trade
        if len(trade_ret_arr) > 0:
            trade_ret_arr -= 2 * (self.commission + self.slippage)
        total_trades, win_rate, avg_win, avg_loss, profit_factor = _compute_trade_stats(
            trade_ret_arr
        )

        return BacktestResult(
            total_return=total_return,
            annualized_return=ann_return,
            benchmark_return=bench_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            calmar_ratio=calmar,
            total_trades=total_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            equity_curve=equity_series,
            drawdown_series=drawdown_series,
            trades=trades_df,
            start_date=prices.index[0],
            end_date=prices.index[-1],
            initial_capital=self.initial_capital,
        )

    def run_multi_asset_backtest(
        self,
        prices: pd.DataFrame,
        signals: pd.DataFrame,
        weights: pd.DataFrame | None = None,
    ) -> BacktestResult:
        """Run multi-asset portfolio backtest.

        Args:
            prices: DataFrame with asset prices as columns
            signals: DataFrame with signals per asset
            weights: Optional fixed weights. If None, equal weight.

        Returns:
            Combined portfolio BacktestResult
        """
        n_assets = len(prices.columns)

        w = 1.0 / n_assets if weights is None else None

        # Run per-asset and combine equity curves
        combined_equity = pd.Series(0.0, index=prices.index)
        total_trades_sum = 0

        for asset in prices.columns:
            asset_weight = w if w is not None else weights[asset].iloc[0]
            bt = VectorBTBacktester(
                initial_capital=self.initial_capital * asset_weight,
                commission=self.commission,
                slippage=self.slippage,
            )
            result = bt.run_backtest(prices[asset], signals[asset])
            combined_equity += result.equity_curve
            total_trades_sum += result.total_trades

        # Combined metrics
        combined_returns = combined_equity.pct_change().dropna()
        cr = combined_returns.values

        total_return = (combined_equity.iloc[-1] / self.initial_capital - 1) * 100
        ann_factor = 252 / max(len(cr), 1)
        ann_return = ((1 + total_return / 100) ** ann_factor - 1) * 100

        daily_std = np.std(cr, ddof=1) if len(cr) > 1 else 0
        volatility = daily_std * np.sqrt(252) * 100
        daily_mean = np.mean(cr) if len(cr) > 0 else 0
        sharpe = (daily_mean / daily_std * np.sqrt(252)) if daily_std > 0 else 0.0

        running_max = combined_equity.cummax()
        drawdown = (combined_equity - running_max) / running_max
        max_dd = float(drawdown.min()) * 100

        return BacktestResult(
            total_return=total_return,
            annualized_return=ann_return,
            benchmark_return=0.0,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=0.0,
            max_drawdown=max_dd,
            calmar_ratio=ann_return / abs(max_dd) if max_dd != 0 else 0,
            total_trades=total_trades_sum,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            equity_curve=combined_equity,
            drawdown_series=drawdown,
            trades=pd.DataFrame(),
            start_date=prices.index[0],
            end_date=prices.index[-1],
            initial_capital=self.initial_capital,
        )

    def parameter_sweep(
        self,
        prices: pd.Series,
        signal_func: Callable[..., pd.Series],
        param_grid: dict,
    ) -> pd.DataFrame:
        """Run parameter sweep for optimization.

        Args:
            prices: Asset price series
            signal_func: Function(params) -> signals
            param_grid: Dict of param_name -> values to test

        Returns:
            DataFrame with params and performance metrics
        """
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        results = []
        for combo in product(*param_values):
            params = dict(zip(param_names, combo, strict=False))
            sigs = signal_func(**params)
            result = self.run_backtest(prices, sigs)

            results.append(
                {
                    **params,
                    "sharpe": result.sharpe_ratio,
                    "return": result.total_return,
                    "max_dd": result.max_drawdown,
                    "win_rate": result.win_rate,
                }
            )

        return pd.DataFrame(results)
