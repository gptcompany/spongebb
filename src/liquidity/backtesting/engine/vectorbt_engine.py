"""VectorBT-based backtesting engine."""

from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import product

import numpy as np
import pandas as pd

try:
    import vectorbt as vbt

    HAS_VECTORBT = True
except ImportError:
    vbt = None
    HAS_VECTORBT = False


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


class VectorBTBacktester:
    """Vectorized backtesting engine using VectorBT.

    Optimized for:
    - Regime-based strategies
    - Multi-asset portfolios
    - Parameter sweeps
    """

    def __init__(
        self,
        initial_capital: float = 100000,
        commission: float = 0.001,  # 0.1% = 10 bps
        slippage: float = 0.0005,  # 0.05% = 5 bps
    ):
        """Initialize backtester.

        Args:
            initial_capital: Starting capital
            commission: Commission per trade (fraction)
            slippage: Slippage per trade (fraction)
        """
        if not HAS_VECTORBT:
            raise ImportError("vectorbt required. Run: uv add vectorbt")

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
        # Convert signals to entries/exits
        entries = (signals == 1) & (signals.shift(1) != 1)
        exits = (signals != 1) & (signals.shift(1) == 1)

        # For short signals
        short_entries = (signals == -1) & (signals.shift(1) != -1)
        short_exits = (signals != -1) & (signals.shift(1) == -1)

        # Run VectorBT portfolio
        pf = vbt.Portfolio.from_signals(
            close=prices,
            entries=entries,
            exits=exits,
            short_entries=short_entries,
            short_exits=short_exits,
            init_cash=self.initial_capital,
            fees=self.commission + self.slippage,
            freq="D",
        )

        # Extract metrics
        stats = pf.stats()

        # Get trades
        trades_df = pf.trades.records_readable

        # Calculate Calmar ratio
        ann_return = stats.get("Total Return [%]", 0) / 100 * (252 / len(prices))
        max_dd = abs(stats.get("Max Drawdown [%]", 1) / 100)
        calmar = ann_return / max_dd if max_dd > 0 else 0

        # Benchmark comparison
        if benchmark is not None:
            bench_return = (benchmark.iloc[-1] / benchmark.iloc[0] - 1) * 100
        else:
            bench_return = 0.0

        return BacktestResult(
            total_return=stats.get("Total Return [%]", 0),
            annualized_return=ann_return * 100,
            benchmark_return=bench_return,
            volatility=stats.get("Annualized Volatility [%]", 0),
            sharpe_ratio=stats.get("Sharpe Ratio", 0),
            sortino_ratio=stats.get("Sortino Ratio", 0),
            max_drawdown=stats.get("Max Drawdown [%]", 0),
            calmar_ratio=calmar,
            total_trades=stats.get("Total Trades", 0),
            win_rate=stats.get("Win Rate [%]", 0),
            avg_win=stats.get("Avg Winning Trade [%]", 0),
            avg_loss=stats.get("Avg Losing Trade [%]", 0),
            profit_factor=stats.get("Profit Factor", 0),
            equity_curve=pf.value(),
            drawdown_series=pf.drawdown(),
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

        if weights is None:
            weights = pd.DataFrame(
                1.0 / n_assets,
                index=prices.index,
                columns=prices.columns,
            )

        # Run per-asset backtests
        pfs = []
        for asset in prices.columns:
            entries = (signals[asset] == 1) & (signals[asset].shift(1) != 1)
            exits = (signals[asset] != 1) & (signals[asset].shift(1) == 1)

            pf = vbt.Portfolio.from_signals(
                close=prices[asset],
                entries=entries,
                exits=exits,
                init_cash=self.initial_capital * weights[asset].iloc[0],
                fees=self.commission + self.slippage,
                freq="D",
            )
            pfs.append(pf)

        # Combine portfolios
        combined_value = sum(pf.value() for pf in pfs)
        combined_returns = combined_value.pct_change().dropna()

        # Calculate combined metrics
        ann_vol = combined_returns.std() * np.sqrt(252) * 100
        ann_return = (
            (combined_value.iloc[-1] / self.initial_capital)
            ** (252 / len(combined_value))
            - 1
        ) * 100
        sharpe = (
            (combined_returns.mean() / combined_returns.std()) * np.sqrt(252)
            if combined_returns.std() > 0
            else 0
        )

        # Drawdown
        rolling_max = combined_value.cummax()
        drawdown = (combined_value - rolling_max) / rolling_max
        max_dd = drawdown.min() * 100

        return BacktestResult(
            total_return=(combined_value.iloc[-1] / self.initial_capital - 1) * 100,
            annualized_return=ann_return,
            benchmark_return=0.0,
            volatility=ann_vol,
            sharpe_ratio=sharpe,
            sortino_ratio=0.0,  # Would need downside deviation
            max_drawdown=max_dd,
            calmar_ratio=ann_return / abs(max_dd) if max_dd != 0 else 0,
            total_trades=sum(pf.trades.count() for pf in pfs),
            win_rate=0.0,  # Aggregated from individual
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            equity_curve=combined_value,
            drawdown_series=drawdown,
            trades=pd.DataFrame(),  # Would need to concatenate
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
            signals = signal_func(**params)
            result = self.run_backtest(prices, signals)

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
