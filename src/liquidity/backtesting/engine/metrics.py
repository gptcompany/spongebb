"""Performance metrics calculator using pure numpy.

Replaces the former QuantStats dependency with direct numpy/pandas calculations.
All standard risk-adjusted metrics computed from daily return series.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""

    # Return metrics
    total_return: float
    cagr: float  # Compound Annual Growth Rate
    mtd: float  # Month-to-date
    ytd: float  # Year-to-date

    # Risk metrics
    volatility: float
    downside_deviation: float
    max_drawdown: float
    avg_drawdown: float
    drawdown_duration: int  # Days

    # Risk-adjusted metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float

    # Trade metrics
    win_rate: float
    profit_factor: float
    payoff_ratio: float  # Avg win / Avg loss
    expected_return: float  # Per trade

    # Tail risk
    var_95: float
    cvar_95: float  # Expected Shortfall
    skewness: float
    kurtosis: float

    # Time metrics
    best_month: float
    worst_month: float
    avg_monthly_return: float

    # Optional relative metrics (must be at end due to defaults)
    information_ratio: float | None = None
    treynor_ratio: float | None = None


class MetricsCalculator:
    """Calculate comprehensive performance metrics with pure numpy.

    All computations use numpy/pandas directly — no external
    analytics libraries required.
    """

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate
        self.daily_rf = (1 + risk_free_rate) ** (1 / 252) - 1

    def calculate(
        self,
        returns: pd.Series,
        benchmark: pd.Series | None = None,
    ) -> PerformanceMetrics:
        """Calculate all performance metrics.

        Args:
            returns: Daily return series
            benchmark: Optional benchmark returns for relative metrics

        Returns:
            PerformanceMetrics with all calculations
        """
        returns = returns.dropna()
        r = returns.values

        # Basic returns
        total_return = float((np.prod(1 + r) - 1) * 100)
        n_years = len(r) / 252
        cagr = float(((np.prod(1 + r)) ** (1 / n_years) - 1) * 100) if n_years > 0 else 0.0
        mtd = self._mtd(returns) * 100
        ytd = self._ytd(returns) * 100

        # Risk metrics
        daily_std = float(np.std(r, ddof=1)) if len(r) > 1 else 0.0
        volatility = daily_std * np.sqrt(252) * 100
        downside_dev = self._downside_deviation(returns) * 100
        max_dd = self._max_drawdown(r) * 100
        avg_dd = self._avg_drawdown(returns) * 100
        dd_duration = self._max_drawdown_duration(returns)

        # Risk-adjusted
        excess_mean = float(np.mean(r) - self.daily_rf)
        sharpe = float(excess_mean / daily_std * np.sqrt(252)) if daily_std > 0 else 0.0

        down_r = r[r < self.daily_rf]
        down_std = float(np.sqrt(np.mean((down_r - self.daily_rf) ** 2))) if len(down_r) > 0 else 0.0
        sortino = float(excess_mean / down_std * np.sqrt(252)) if down_std > 0 else 0.0

        calmar = cagr / abs(max_dd) if max_dd != 0 else 0.0
        omega = self._omega_ratio(returns)

        # Relative metrics
        info_ratio = None
        treynor = None
        if benchmark is not None:
            benchmark = benchmark.reindex(returns.index).dropna()
            common_idx = returns.index.intersection(benchmark.index)
            if len(common_idx) > 0:
                info_ratio = self._information_ratio(
                    returns.loc[common_idx], benchmark.loc[common_idx]
                )
                treynor = self._treynor_ratio(
                    returns.loc[common_idx], benchmark.loc[common_idx]
                )

        # Trade metrics (from daily returns)
        wins = r[r > 0]
        losses = r[r < 0]
        win_rate = float(len(wins) / len(r) * 100) if len(r) > 0 else 0.0
        profit_factor = (
            abs(float(wins.sum()) / float(losses.sum()))
            if len(losses) > 0 and losses.sum() != 0
            else np.inf
        )
        payoff = (
            abs(float(wins.mean()) / float(losses.mean()))
            if len(losses) > 0 and losses.mean() != 0
            else np.inf
        )
        expected = float(np.mean(r) * 100)

        # Tail risk
        var_95 = float(np.percentile(r, 5) * 100)
        tail = r[r <= np.percentile(r, 5)]
        cvar_95 = float(np.mean(tail) * 100) if len(tail) > 0 else var_95
        skew = float(pd.Series(r).skew())
        kurt = float(pd.Series(r).kurtosis())

        # Monthly
        monthly = returns.resample("ME").apply(lambda x: (1 + x).prod() - 1)
        best_month = float(monthly.max() * 100) if len(monthly) > 0 else 0.0
        worst_month = float(monthly.min() * 100) if len(monthly) > 0 else 0.0
        avg_monthly = float(monthly.mean() * 100) if len(monthly) > 0 else 0.0

        return PerformanceMetrics(
            total_return=total_return,
            cagr=cagr,
            mtd=mtd,
            ytd=ytd,
            volatility=volatility,
            downside_deviation=downside_dev,
            max_drawdown=max_dd,
            avg_drawdown=avg_dd,
            drawdown_duration=dd_duration,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            omega_ratio=omega,
            information_ratio=info_ratio,
            treynor_ratio=treynor,
            win_rate=win_rate,
            profit_factor=profit_factor,
            payoff_ratio=payoff,
            expected_return=expected,
            var_95=var_95,
            cvar_95=cvar_95,
            skewness=skew,
            kurtosis=kurt,
            best_month=best_month,
            worst_month=worst_month,
            avg_monthly_return=avg_monthly,
        )

    def generate_tearsheet(
        self,
        returns: pd.Series,
        benchmark: pd.Series | None = None,
        output_path: Path | None = None,
        title: str = "Strategy Performance",
    ) -> str | None:
        """Generate a simple HTML tearsheet.

        Args:
            returns: Daily return series
            benchmark: Optional benchmark returns
            output_path: Path to save HTML file
            title: Report title

        Returns:
            HTML content string
        """
        metrics = self.calculate(returns, benchmark)

        # Build simple HTML report
        rows = [
            ("Total Return (%)", f"{metrics.total_return:.2f}"),
            ("CAGR (%)", f"{metrics.cagr:.2f}"),
            ("Volatility (%)", f"{metrics.volatility:.2f}"),
            ("Sharpe Ratio", f"{metrics.sharpe_ratio:.3f}"),
            ("Sortino Ratio", f"{metrics.sortino_ratio:.3f}"),
            ("Calmar Ratio", f"{metrics.calmar_ratio:.3f}"),
            ("Max Drawdown (%)", f"{metrics.max_drawdown:.2f}"),
            ("Win Rate (%)", f"{metrics.win_rate:.1f}"),
            ("VaR 95 (%)", f"{metrics.var_95:.2f}"),
            ("CVaR 95 (%)", f"{metrics.cvar_95:.2f}"),
        ]
        table_rows = "\n".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows
        )
        html = f"""<!DOCTYPE html>
<html><head><title>{title}</title></head>
<body><h1>{title}</h1>
<table border="1"><tr><th>Metric</th><th>Value</th></tr>
{table_rows}
</table></body></html>"""

        if output_path:
            output_path.write_text(html)
        return html

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _max_drawdown(r: np.ndarray) -> float:
        cumulative = np.cumprod(1 + r)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return float(drawdown.min()) if len(drawdown) > 0 else 0.0

    @staticmethod
    def _mtd(returns: pd.Series) -> float:
        if len(returns) == 0:
            return 0.0
        last = returns.index[-1]
        mtd_ret = returns[(returns.index.month == last.month) & (returns.index.year == last.year)]
        return float((1 + mtd_ret).prod() - 1)

    @staticmethod
    def _ytd(returns: pd.Series) -> float:
        if len(returns) == 0:
            return 0.0
        ytd_ret = returns[returns.index.year == returns.index[-1].year]
        return float((1 + ytd_ret).prod() - 1)

    @staticmethod
    def _downside_deviation(returns: pd.Series, threshold: float = 0) -> float:
        downside = returns[returns < threshold]
        if len(downside) == 0:
            return 0.0
        return float(np.sqrt(np.mean((downside - threshold) ** 2)) * np.sqrt(252))

    @staticmethod
    def _avg_drawdown(returns: pd.Series) -> float:
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max
        return float(drawdowns.mean())

    @staticmethod
    def _max_drawdown_duration(returns: pd.Series) -> int:
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        underwater = cumulative < running_max
        groups = (~underwater).cumsum()
        underwater_lengths = underwater.groupby(groups).sum()
        return int(underwater_lengths.max()) if len(underwater_lengths) > 0 else 0

    @staticmethod
    def _omega_ratio(returns: pd.Series, threshold: float = 0) -> float:
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]
        if losses.sum() == 0:
            return np.inf
        return float(gains.sum() / losses.sum())

    def _information_ratio(self, returns: pd.Series, benchmark: pd.Series) -> float:
        excess = returns - benchmark
        tracking_error = float(excess.std() * np.sqrt(252))
        if tracking_error == 0:
            return 0.0
        return float(excess.mean() * 252) / tracking_error

    def _treynor_ratio(self, returns: pd.Series, benchmark: pd.Series) -> float:
        covariance = np.cov(returns, benchmark)[0, 1]
        benchmark_var = float(benchmark.var())
        beta = covariance / benchmark_var if benchmark_var > 0 else 1
        excess_return = float((returns.mean() - self.daily_rf) * 252)
        return excess_return / beta if beta != 0 else 0.0


def compare_strategies(
    strategies: dict[str, pd.Series],
    benchmark: pd.Series | None = None,
) -> pd.DataFrame:
    """Compare multiple strategies side by side.

    Args:
        strategies: Dict of strategy_name -> returns series
        benchmark: Optional benchmark for comparison

    Returns:
        DataFrame with metrics for each strategy
    """
    calculator = MetricsCalculator()
    results = {}

    for name, returns in strategies.items():
        metrics = calculator.calculate(returns, benchmark)
        results[name] = {
            "Total Return (%)": metrics.total_return,
            "CAGR (%)": metrics.cagr,
            "Volatility (%)": metrics.volatility,
            "Sharpe": metrics.sharpe_ratio,
            "Sortino": metrics.sortino_ratio,
            "Max DD (%)": metrics.max_drawdown,
            "Calmar": metrics.calmar_ratio,
            "Win Rate (%)": metrics.win_rate,
            "VaR 95 (%)": metrics.var_95,
        }

    return pd.DataFrame(results).T
