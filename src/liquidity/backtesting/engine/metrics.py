"""Performance metrics calculator using QuantStats."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import quantstats as qs
    HAS_QUANTSTATS = True
except ImportError:
    HAS_QUANTSTATS = False


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
    """Calculate comprehensive performance metrics.

    Uses QuantStats for standard metrics plus custom calculations
    for regime-specific analytics.
    """

    def __init__(self, risk_free_rate: float = 0.05):
        """Initialize calculator.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        if not HAS_QUANTSTATS:
            raise ImportError("quantstats required. Run: uv add quantstats")

        self.risk_free_rate = risk_free_rate
        # Daily risk-free rate
        self.daily_rf = (1 + risk_free_rate) ** (1/252) - 1

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

        # Basic returns
        total_return = qs.stats.comp(returns) * 100
        cagr = qs.stats.cagr(returns) * 100
        mtd = self._mtd(returns) * 100
        ytd = self._ytd(returns) * 100

        # Risk metrics
        volatility = qs.stats.volatility(returns) * 100
        downside_dev = self._downside_deviation(returns) * 100
        max_dd = qs.stats.max_drawdown(returns) * 100
        avg_dd = self._avg_drawdown(returns) * 100
        dd_duration = self._max_drawdown_duration(returns)

        # Risk-adjusted
        sharpe = qs.stats.sharpe(returns, rf=self.daily_rf)
        sortino = qs.stats.sortino(returns, rf=self.daily_rf)
        calmar = qs.stats.calmar(returns)
        omega = self._omega_ratio(returns)

        # Relative metrics (if benchmark provided)
        info_ratio = None
        treynor = None
        if benchmark is not None:
            benchmark = benchmark.reindex(returns.index).dropna()
            common_idx = returns.index.intersection(benchmark.index)
            if len(common_idx) > 0:
                info_ratio = self._information_ratio(
                    returns.loc[common_idx],
                    benchmark.loc[common_idx]
                )
                treynor = self._treynor_ratio(
                    returns.loc[common_idx],
                    benchmark.loc[common_idx]
                )

        # Trade metrics (estimated from returns)
        win_rate = (returns > 0).mean() * 100
        wins = returns[returns > 0]
        losses = returns[returns < 0]
        profit_factor = abs(wins.sum() / losses.sum()) if len(losses) > 0 and losses.sum() != 0 else np.inf
        payoff = abs(wins.mean() / losses.mean()) if len(losses) > 0 and losses.mean() != 0 else np.inf
        expected = returns.mean() * 100

        # Tail risk
        var_95 = qs.stats.value_at_risk(returns) * 100
        cvar_95 = qs.stats.cvar(returns) * 100
        skew = returns.skew()
        kurt = returns.kurtosis()

        # Monthly
        monthly = returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)
        best_month = monthly.max() * 100
        worst_month = monthly.min() * 100
        avg_monthly = monthly.mean() * 100

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
        """Generate HTML tearsheet using QuantStats.

        Args:
            returns: Daily return series
            benchmark: Optional benchmark returns
            output_path: Path to save HTML file (required for file output)
            title: Report title

        Returns:
            HTML content string if output_path is provided and file is saved,
            None otherwise.

        Note:
            When output_path is provided, the tearsheet is saved to file
            and the HTML content is returned. When output_path is None,
            a temporary file is used and the content is returned.
        """
        import tempfile

        if output_path:
            qs.reports.html(
                returns,
                benchmark=benchmark,
                output=str(output_path),
                title=title,
            )
            # Read and return the generated HTML
            return output_path.read_text()
        else:
            # Use temporary file since QuantStats doesn't support direct HTML return
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
                temp_path = Path(f.name)
            try:
                qs.reports.html(
                    returns,
                    benchmark=benchmark,
                    output=str(temp_path),
                    title=title,
                )
                return temp_path.read_text()
            finally:
                temp_path.unlink(missing_ok=True)

    def _mtd(self, returns: pd.Series) -> float:
        """Month-to-date return."""
        if len(returns) == 0:
            return 0.0
        current_month = returns.index[-1].month
        current_year = returns.index[-1].year
        mtd_returns = returns[(returns.index.month == current_month) &
                             (returns.index.year == current_year)]
        return (1 + mtd_returns).prod() - 1

    def _ytd(self, returns: pd.Series) -> float:
        """Year-to-date return."""
        if len(returns) == 0:
            return 0.0
        current_year = returns.index[-1].year
        ytd_returns = returns[returns.index.year == current_year]
        return (1 + ytd_returns).prod() - 1

    def _downside_deviation(self, returns: pd.Series, threshold: float = 0) -> float:
        """Downside deviation (semi-deviation below threshold)."""
        downside = returns[returns < threshold]
        if len(downside) == 0:
            return 0.0
        return np.sqrt(np.mean((downside - threshold) ** 2)) * np.sqrt(252)

    def _avg_drawdown(self, returns: pd.Series) -> float:
        """Average drawdown."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max
        return drawdowns.mean()

    def _max_drawdown_duration(self, returns: pd.Series) -> int:
        """Maximum drawdown duration in days."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()

        # Find underwater periods
        underwater = cumulative < running_max
        groups = (~underwater).cumsum()
        underwater_lengths = underwater.groupby(groups).sum()

        return int(underwater_lengths.max()) if len(underwater_lengths) > 0 else 0

    def _omega_ratio(self, returns: pd.Series, threshold: float = 0) -> float:
        """Omega ratio: probability-weighted gain/loss ratio."""
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]

        if losses.sum() == 0:
            return np.inf
        return gains.sum() / losses.sum()

    def _information_ratio(
        self,
        returns: pd.Series,
        benchmark: pd.Series,
    ) -> float:
        """Information ratio: excess return / tracking error."""
        excess = returns - benchmark
        tracking_error = excess.std() * np.sqrt(252)
        if tracking_error == 0:
            return 0.0
        return (excess.mean() * 252) / tracking_error

    def _treynor_ratio(
        self,
        returns: pd.Series,
        benchmark: pd.Series,
    ) -> float:
        """Treynor ratio: excess return / beta."""
        # Calculate beta
        covariance = np.cov(returns, benchmark)[0, 1]
        benchmark_var = benchmark.var()
        beta = covariance / benchmark_var if benchmark_var > 0 else 1

        excess_return = (returns.mean() - self.daily_rf) * 252
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
            'Total Return (%)': metrics.total_return,
            'CAGR (%)': metrics.cagr,
            'Volatility (%)': metrics.volatility,
            'Sharpe': metrics.sharpe_ratio,
            'Sortino': metrics.sortino_ratio,
            'Max DD (%)': metrics.max_drawdown,
            'Calmar': metrics.calmar_ratio,
            'Win Rate (%)': metrics.win_rate,
            'VaR 95 (%)': metrics.var_95,
        }

    return pd.DataFrame(results).T
