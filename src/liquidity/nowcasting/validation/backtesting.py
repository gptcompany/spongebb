"""Walk-forward backtesting for nowcast validation.

This module provides pseudo-real-time backtesting to evaluate nowcast
accuracy before deployment. The key principle is information leak prevention:
at each point, the model only sees data that would have been available
at that time.

Backtesting Protocol:
1. Train on first N days of historical data
2. Generate nowcast for day N+1 using only data through day N
3. Wait for official release (typically 3-5 days later)
4. Compare nowcast to official value
5. Roll forward one day and repeat

This simulates real-world operation where we nowcast before official
Fed releases using high-frequency proxies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from liquidity.nowcasting.kalman import LiquidityStateSpace
from liquidity.nowcasting.validation.metrics import NowcastMetrics, compute_all_metrics

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for nowcast backtesting.

    Attributes:
        train_window: Number of days for initial training.
        release_lag: Days between nowcast and official release.
        step_size: Days to advance between tests (1 = daily).
        min_test_periods: Minimum test periods required.
        refit_frequency: How often to refit model (1 = every step).
    """

    train_window: int = 252  # ~1 year
    release_lag: int = 5     # Fed releases WALCL on Thursdays
    step_size: int = 1       # Daily testing
    min_test_periods: int = 50
    refit_frequency: int = 5  # Refit every 5 days


@dataclass
class BacktestResult:
    """Single backtest observation result.

    Attributes:
        date: Date of nowcast.
        nowcast: Nowcast point estimate.
        ci_lower: 95% CI lower bound.
        ci_upper: 95% CI upper bound.
        std: Standard deviation of estimate.
        official: Official value (when released).
        error: Nowcast - Official.
        pct_error: Absolute percentage error.
        within_ci: Whether official is within CI.
    """

    date: pd.Timestamp
    nowcast: float
    ci_lower: float
    ci_upper: float
    std: float
    official: float
    error: float
    pct_error: float
    within_ci: bool

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "nowcast": self.nowcast,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "std": self.std,
            "official": self.official,
            "error": self.error,
            "pct_error": self.pct_error,
            "within_ci": self.within_ci,
        }


@dataclass
class BacktestSummary:
    """Summary of backtest results.

    Attributes:
        config: Configuration used for backtest.
        metrics: Computed accuracy metrics.
        results: Individual test results.
        start_date: First test date.
        end_date: Last test date.
        n_tests: Number of test periods.
        execution_time_seconds: Total backtest duration.
    """

    config: BacktestConfig
    metrics: NowcastMetrics
    results: list[BacktestResult]
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    n_tests: int
    execution_time_seconds: float = 0.0

    def to_dataframe(self) -> pd.DataFrame:
        """Convert results to DataFrame."""
        return pd.DataFrame([r.to_dict() for r in self.results])

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"BacktestSummary(n_tests={self.n_tests}, "
            f"MAPE={self.metrics.mape:.2f}%, "
            f"Coverage={self.metrics.coverage:.1f}%, "
            f"period={self.start_date.date()} to {self.end_date.date()})"
        )


class NowcastBacktester:
    """Walk-forward validation for nowcast accuracy.

    Implements pseudo-real-time backtesting to evaluate nowcast
    performance before deployment. Uses strict information barriers
    to prevent lookahead bias.

    Example:
        backtester = NowcastBacktester()

        # Run backtest on historical data
        summary = backtester.run_backtest(
            historical_data=net_liquidity_df,
            train_window=252,  # 1 year training
        )

        print(f"Backtest MAPE: {summary.metrics.mape:.2f}%")
        print(f"Coverage: {summary.metrics.coverage:.1f}%")

        # Check if meets target
        if summary.metrics.passes_threshold:
            print("Model meets MAPE < 3% target!")
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        """Initialize the backtester.

        Args:
            config: Backtest configuration. Uses defaults if not provided.
        """
        self.config = config or BacktestConfig()
        self._results: list[BacktestResult] = []

    def run_backtest(
        self,
        historical_data: pd.DataFrame | pd.Series,
        official_column: str = "official",
        proxy_column: str = "proxy",
        train_window: int | None = None,
    ) -> BacktestSummary:
        """Execute pseudo-real-time backtest.

        Args:
            historical_data: DataFrame with columns for proxy and official values,
                or Series of official values (proxy will be derived).
            official_column: Column name for official releases.
            proxy_column: Column name for HF proxy data.
            train_window: Override config train window.

        Returns:
            BacktestSummary with results and metrics.

        Raises:
            ValueError: If insufficient data for backtesting.
        """
        import time
        start_time = time.time()

        train_window = train_window or self.config.train_window

        # Handle Series vs DataFrame input
        if isinstance(historical_data, pd.Series):
            df = pd.DataFrame({
                official_column: historical_data,
                proxy_column: historical_data,  # Use same data as proxy
            })
        else:
            df = historical_data.copy()

        # Validate data
        if official_column not in df.columns:
            raise ValueError(f"Column '{official_column}' not found in data")

        n_total = len(df)
        n_test = n_total - train_window - self.config.release_lag

        if n_test < self.config.min_test_periods:
            raise ValueError(
                f"Insufficient data for backtesting: {n_test} test periods "
                f"< {self.config.min_test_periods} minimum"
            )

        logger.info(
            "Starting backtest: %d total observations, %d train, %d test",
            n_total, train_window, n_test
        )

        self._results = []

        # Use proxy column for training if available, else official
        train_col = proxy_column if proxy_column in df.columns else official_column

        # Walk-forward loop
        for test_idx in range(train_window, n_total - self.config.release_lag,
                             self.config.step_size):

            # Train data: everything up to test_idx (exclusive)
            train_data = df[train_col].iloc[:test_idx]

            # Skip if too much missing data
            if train_data.isna().sum() / len(train_data) > 0.3:
                logger.debug("Skipping idx %d: too much missing data", test_idx)
                continue

            # Fit model (only refit periodically for efficiency)
            need_refit = (
                test_idx == train_window or
                (test_idx - train_window) % self.config.refit_frequency == 0
            )

            if need_refit:
                try:
                    model = LiquidityStateSpace()
                    model.fit(train_data.dropna())
                except Exception as e:
                    logger.warning("Model fit failed at idx %d: %s", test_idx, e)
                    continue

            # Generate nowcast
            try:
                nowcast = model.nowcast(steps=1)
            except Exception as e:
                logger.warning("Nowcast failed at idx %d: %s", test_idx, e)
                continue

            # Get official value (released after lag)
            official_idx = test_idx + self.config.release_lag
            if official_idx >= n_total:
                break

            official = df[official_column].iloc[official_idx]

            if pd.isna(official):
                continue

            # Compute error
            error = nowcast.mean - official
            pct_error = abs(error / official) * 100 if official != 0 else float("inf")
            within_ci = nowcast.ci_lower <= official <= nowcast.ci_upper

            # Store result
            result = BacktestResult(
                date=df.index[test_idx] if isinstance(df.index, pd.DatetimeIndex)
                     else pd.Timestamp(df.index[test_idx]),
                nowcast=nowcast.mean,
                ci_lower=nowcast.ci_lower,
                ci_upper=nowcast.ci_upper,
                std=nowcast.std,
                official=float(official),
                error=error,
                pct_error=pct_error,
                within_ci=within_ci,
            )
            self._results.append(result)

            if len(self._results) % 50 == 0:
                logger.info("Backtest progress: %d tests completed", len(self._results))

        # Compute summary metrics
        if not self._results:
            raise ValueError("No valid backtest results generated")

        metrics = self._compute_metrics()

        execution_time = time.time() - start_time

        summary = BacktestSummary(
            config=self.config,
            metrics=metrics,
            results=self._results,
            start_date=self._results[0].date,
            end_date=self._results[-1].date,
            n_tests=len(self._results),
            execution_time_seconds=execution_time,
        )

        logger.info(
            "Backtest complete: %d tests, MAPE=%.2f%%, Coverage=%.1f%%, "
            "Time=%.1fs",
            summary.n_tests, metrics.mape, metrics.coverage, execution_time
        )

        return summary

    def _compute_metrics(self) -> NowcastMetrics:
        """Compute metrics from backtest results."""
        if not self._results:
            return NowcastMetrics(
                mape=float("inf"),
                rmse=float("inf"),
                mae=float("inf"),
                coverage=0.0,
                bias=0.0,
                n_observations=0,
            )

        actual = np.array([r.official for r in self._results])
        predicted = np.array([r.nowcast for r in self._results])
        ci_lower = np.array([r.ci_lower for r in self._results])
        ci_upper = np.array([r.ci_upper for r in self._results])

        return compute_all_metrics(
            actual=actual,
            predicted=predicted,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
        )

    def run_expanding_window_backtest(
        self,
        historical_data: pd.DataFrame | pd.Series,
        official_column: str = "official",
        initial_window: int = 126,  # 6 months
        expansion_step: int = 21,   # 1 month
    ) -> list[BacktestSummary]:
        """Run backtest with expanding training window.

        Tests model performance as more historical data becomes available.
        Useful for understanding learning curve and optimal training size.

        Args:
            historical_data: Historical data for backtesting.
            official_column: Column name for official values.
            initial_window: Starting training window size.
            expansion_step: How many days to add each iteration.

        Returns:
            List of BacktestSummary for each window size.
        """
        summaries = []

        max_window = len(historical_data) - self.config.release_lag - self.config.min_test_periods

        for window in range(initial_window, max_window, expansion_step):
            logger.info("Running expanding window backtest with window=%d", window)

            try:
                summary = self.run_backtest(
                    historical_data=historical_data,
                    official_column=official_column,
                    train_window=window,
                )
                summaries.append(summary)
            except ValueError as e:
                logger.warning("Skipping window %d: %s", window, e)
                break

        return summaries

    def cross_validate(
        self,
        historical_data: pd.DataFrame | pd.Series,
        official_column: str = "official",
        n_folds: int = 5,
    ) -> list[BacktestSummary]:
        """Run time-series cross-validation.

        Uses TimeSeriesSplit-style validation where each fold uses
        all previous data for training and the next chunk for testing.

        Args:
            historical_data: Historical data for cross-validation.
            official_column: Column name for official values.
            n_folds: Number of cross-validation folds.

        Returns:
            List of BacktestSummary for each fold.
        """
        n_total = len(historical_data)
        fold_size = n_total // (n_folds + 1)

        summaries = []

        for fold in range(n_folds):
            train_end = (fold + 1) * fold_size
            test_end = min((fold + 2) * fold_size, n_total)

            logger.info(
                "CV Fold %d/%d: train[0:%d], test[%d:%d]",
                fold + 1, n_folds, train_end, train_end, test_end
            )

            # Use subset for this fold
            fold_data = historical_data.iloc[:test_end]

            try:
                summary = self.run_backtest(
                    historical_data=fold_data,
                    official_column=official_column,
                    train_window=train_end,
                )
                summaries.append(summary)
            except ValueError as e:
                logger.warning("Skipping fold %d: %s", fold + 1, e)

        return summaries

    def get_results_dataframe(self) -> pd.DataFrame:
        """Get backtest results as DataFrame."""
        if not self._results:
            return pd.DataFrame()
        return pd.DataFrame([r.to_dict() for r in self._results])

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"NowcastBacktester(train_window={self.config.train_window}, "
            f"release_lag={self.config.release_lag}, "
            f"n_results={len(self._results)})"
        )
