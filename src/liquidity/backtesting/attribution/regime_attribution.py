"""Regime-based P&L attribution and transition analysis."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class RegimePerformance:
    """Performance metrics for a single regime."""

    regime: str
    n_periods: int
    pct_time: float  # % of time in this regime

    # Returns
    total_return: float  # %
    annualized_return: float  # %
    avg_daily_return: float  # %

    # Risk
    volatility: float  # Annualized %
    max_drawdown: float  # %
    avg_drawdown: float  # %

    # Risk-adjusted
    sharpe_ratio: float
    sortino_ratio: float

    # Trade quality
    win_rate: float  # %
    profit_factor: float
    avg_win: float  # %
    avg_loss: float  # %


@dataclass
class TransitionAnalysis:
    """Analysis of performance around regime transitions."""

    transition_type: str  # e.g., "EXPANSION_to_CONTRACTION"
    n_transitions: int

    # Pre-transition performance (N days before)
    pre_return: float  # %
    pre_volatility: float  # %

    # Post-transition performance (N days after)
    post_return: float  # %
    post_volatility: float  # %

    # Transition edge
    transition_alpha: float  # Post return - pre return
    transition_signal_value: float  # Average signal strength at transition

    # Timing
    avg_duration_from: float  # Avg days in from-regime before transition
    avg_duration_to: float  # Avg days in to-regime after transition


class RegimeAttributionAnalyzer:
    """Analyze strategy performance by liquidity regime.

    Breaks down P&L by regime state to understand:
    - Which regimes contribute most to returns
    - Performance during regime transitions
    - Optimal holding periods per regime
    """

    def __init__(self, transition_window: int = 10):
        """Initialize analyzer.

        Args:
            transition_window: Days before/after transition to analyze
        """
        self.transition_window = transition_window

    def compute_regime_performance(
        self,
        returns: pd.Series,
        regimes: pd.Series,
    ) -> dict[str, RegimePerformance]:
        """Compute performance metrics by regime.

        Args:
            returns: Daily return series
            regimes: Regime classification series (aligned with returns)

        Returns:
            Dict mapping regime name to RegimePerformance
        """
        results = {}

        for regime in regimes.unique():
            mask = regimes == regime
            regime_returns = returns[mask]

            if len(regime_returns) < 2:
                continue

            # Basic stats
            n_periods = len(regime_returns)
            pct_time = n_periods / len(returns) * 100
            total_return = (1 + regime_returns).prod() - 1
            annualized = (
                (1 + total_return) ** (252 / n_periods) - 1 if n_periods > 0 else 0
            )
            avg_daily = regime_returns.mean()

            # Risk
            volatility = regime_returns.std() * np.sqrt(252)
            cumulative = (1 + regime_returns).cumprod()
            running_max = cumulative.cummax()
            drawdowns = (cumulative - running_max) / running_max
            max_dd = drawdowns.min()
            avg_dd = drawdowns.mean()

            # Risk-adjusted
            rf_daily = 0.05 / 252  # Assume 5% risk-free
            excess_return = avg_daily - rf_daily
            sharpe = (
                (excess_return / regime_returns.std() * np.sqrt(252))
                if regime_returns.std() > 0
                else 0
            )

            # Sortino (downside deviation)
            downside = regime_returns[regime_returns < 0]
            downside_dev = (
                np.sqrt(np.mean(downside**2)) * np.sqrt(252)
                if len(downside) > 0
                else 0.001
            )
            sortino = (excess_return * 252) / downside_dev if downside_dev > 0 else 0

            # Trade quality
            wins = regime_returns[regime_returns > 0]
            losses = regime_returns[regime_returns < 0]
            win_rate = (
                len(wins) / len(regime_returns) * 100 if len(regime_returns) > 0 else 0
            )
            profit_factor = (
                abs(wins.sum() / losses.sum())
                if len(losses) > 0 and losses.sum() != 0
                else np.inf
            )
            avg_win = wins.mean() * 100 if len(wins) > 0 else 0
            avg_loss = losses.mean() * 100 if len(losses) > 0 else 0

            results[regime] = RegimePerformance(
                regime=regime,
                n_periods=n_periods,
                pct_time=pct_time,
                total_return=total_return * 100,
                annualized_return=annualized * 100,
                avg_daily_return=avg_daily * 100,
                volatility=volatility * 100,
                max_drawdown=max_dd * 100,
                avg_drawdown=avg_dd * 100,
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_win=avg_win,
                avg_loss=avg_loss,
            )

        return results

    def analyze_transitions(
        self,
        returns: pd.Series,
        regimes: pd.Series,
        signals: pd.Series | None = None,
    ) -> list[TransitionAnalysis]:
        """Analyze performance around regime transitions.

        Args:
            returns: Daily return series
            regimes: Regime classification series
            signals: Optional signal strength series

        Returns:
            List of TransitionAnalysis for each transition type
        """
        # Find transition points
        transitions = regimes != regimes.shift(1)
        transition_dates = returns.index[transitions]

        # Group by transition type
        transition_data: dict[str, dict[str, list]] = {}
        for date in transition_dates[1:]:  # Skip first (no from-regime)
            idx = returns.index.get_loc(date)
            if idx < self.transition_window or idx + self.transition_window >= len(
                returns
            ):
                continue

            from_regime = regimes.iloc[idx - 1]
            to_regime = regimes.iloc[idx]
            trans_type = f"{from_regime}_to_{to_regime}"

            if trans_type not in transition_data:
                transition_data[trans_type] = {
                    "pre_returns": [],
                    "post_returns": [],
                    "signal_values": [],
                }

            # Pre-transition returns
            pre_returns = returns.iloc[idx - self.transition_window : idx]
            post_returns = returns.iloc[idx : idx + self.transition_window]

            transition_data[trans_type]["pre_returns"].append(pre_returns.sum())
            transition_data[trans_type]["post_returns"].append(post_returns.sum())

            if signals is not None:
                transition_data[trans_type]["signal_values"].append(signals.iloc[idx])

        # Compute statistics
        results = []
        for trans_type, data in transition_data.items():
            pre_returns_arr = np.array(data["pre_returns"])
            post_returns_arr = np.array(data["post_returns"])
            signal_values = (
                np.array(data["signal_values"])
                if data["signal_values"]
                else np.array([0])
            )

            results.append(
                TransitionAnalysis(
                    transition_type=trans_type,
                    n_transitions=len(pre_returns_arr),
                    pre_return=np.mean(pre_returns_arr) * 100,
                    pre_volatility=np.std(pre_returns_arr) * np.sqrt(252) * 100,
                    post_return=np.mean(post_returns_arr) * 100,
                    post_volatility=np.std(post_returns_arr) * np.sqrt(252) * 100,
                    transition_alpha=(
                        np.mean(post_returns_arr) - np.mean(pre_returns_arr)
                    )
                    * 100,
                    transition_signal_value=np.mean(signal_values),
                    avg_duration_from=0,  # Would need regime duration tracking
                    avg_duration_to=0,
                )
            )

        return results

    def compute_regime_durations(
        self,
        regimes: pd.Series,
    ) -> pd.DataFrame:
        """Compute regime duration statistics.

        Args:
            regimes: Regime classification series

        Returns:
            DataFrame with duration stats per regime
        """
        # Find regime streaks
        regime_groups = (regimes != regimes.shift(1)).cumsum()
        durations = regimes.groupby(regime_groups).agg(["first", "count"])
        durations.columns = ["regime_name", "duration"]

        # Reset index to avoid ambiguity between index level and column
        durations = durations.reset_index(drop=True)

        # Aggregate by regime
        stats = durations.groupby("regime_name")["duration"].agg(
            [
                "count",
                "mean",
                "std",
                "min",
                "max",
                "median",
            ]
        )
        stats.columns = [
            "n_occurrences",
            "avg_duration",
            "std_duration",
            "min_duration",
            "max_duration",
            "median_duration",
        ]
        stats.index.name = None

        return stats

    def generate_attribution_report(
        self,
        returns: pd.Series,
        regimes: pd.Series,
        signals: pd.Series | None = None,
    ) -> dict:
        """Generate comprehensive attribution report.

        Args:
            returns: Daily return series
            regimes: Regime classification series
            signals: Optional signal strength series

        Returns:
            Dict with full attribution analysis
        """
        regime_perf = self.compute_regime_performance(returns, regimes)
        transitions = self.analyze_transitions(returns, regimes, signals)
        durations = self.compute_regime_durations(regimes)

        # Summary metrics
        total_return = (1 + returns).prod() - 1

        # Contribution by regime
        contributions = {}
        for regime, perf in regime_perf.items():
            regime_contribution = (
                (perf.total_return / 100) * (perf.pct_time / 100) * total_return
            )
            contributions[regime] = {
                "return_contribution": regime_contribution * 100,
                "pct_of_total": (
                    (regime_contribution / total_return) * 100 if total_return != 0 else 0
                ),
            }

        return {
            "regime_performance": regime_perf,
            "transitions": transitions,
            "durations": durations.to_dict(),
            "contributions": contributions,
            "total_return": total_return * 100,
        }

    def to_dataframe(
        self,
        regime_performance: dict[str, RegimePerformance],
    ) -> pd.DataFrame:
        """Convert regime performance to DataFrame.

        Args:
            regime_performance: Dict from compute_regime_performance

        Returns:
            DataFrame with one row per regime
        """
        records = []
        for _regime, perf in regime_performance.items():
            records.append(
                {
                    "Regime": perf.regime,
                    "Time (%)": perf.pct_time,
                    "Return (%)": perf.total_return,
                    "Ann. Return (%)": perf.annualized_return,
                    "Volatility (%)": perf.volatility,
                    "Sharpe": perf.sharpe_ratio,
                    "Sortino": perf.sortino_ratio,
                    "Max DD (%)": perf.max_drawdown,
                    "Win Rate (%)": perf.win_rate,
                    "Profit Factor": perf.profit_factor,
                }
            )

        return pd.DataFrame(records).set_index("Regime")
