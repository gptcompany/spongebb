"""Metrics for evaluating nowcast accuracy.

This module provides standard forecast accuracy metrics:
- MAPE (Mean Absolute Percentage Error)
- RMSE (Root Mean Squared Error)
- MAE (Mean Absolute Error)
- Coverage (confidence interval calibration)
- Bias (systematic over/under prediction)

These metrics are used for backtesting and monitoring nowcast quality.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

    from liquidity.nowcasting.kalman import NowcastResult

logger = logging.getLogger(__name__)


@dataclass
class NowcastMetrics:
    """Collection of nowcast accuracy metrics.

    Attributes:
        mape: Mean Absolute Percentage Error (%).
        rmse: Root Mean Squared Error (in native units).
        mae: Mean Absolute Error (in native units).
        coverage: Percentage of actuals within confidence intervals.
        bias: Mean signed error (positive = over-prediction).
        n_observations: Number of observations used.
        hit_rate: Percentage of direction predictions correct.
    """

    mape: float
    rmse: float
    mae: float
    coverage: float
    bias: float
    n_observations: int
    hit_rate: float = 0.0

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"NowcastMetrics(MAPE={self.mape:.2f}%, RMSE={self.rmse:.4f}, "
            f"MAE={self.mae:.4f}, Coverage={self.coverage:.1f}%, "
            f"Bias={self.bias:.4f}, n={self.n_observations})"
        )

    @property
    def passes_threshold(self) -> bool:
        """Check if MAPE is below 3% target."""
        return self.mape < 3.0

    def to_dict(self) -> dict[str, float | int]:
        """Convert to dictionary."""
        return {
            "mape": self.mape,
            "rmse": self.rmse,
            "mae": self.mae,
            "coverage": self.coverage,
            "bias": self.bias,
            "n_observations": self.n_observations,
            "hit_rate": self.hit_rate,
        }


def calculate_mape(
    actual: np.ndarray | pd.Series,
    predicted: np.ndarray | pd.Series,
    epsilon: float = 1e-10,
) -> float:
    """Calculate Mean Absolute Percentage Error.

    MAPE = (100 / n) * sum(|actual - predicted| / |actual|)

    Args:
        actual: Actual values.
        predicted: Predicted values.
        epsilon: Small value to avoid division by zero.

    Returns:
        MAPE as percentage (0-100+).
    """
    actual_arr = np.asarray(actual)
    predicted_arr = np.asarray(predicted)

    # Filter out zero/near-zero actuals
    mask = np.abs(actual_arr) > epsilon
    if not mask.any():
        logger.warning("All actual values are near zero, MAPE undefined")
        return float("inf")

    actual_filtered = actual_arr[mask]
    predicted_filtered = predicted_arr[mask]

    ape = np.abs((actual_filtered - predicted_filtered) / actual_filtered) * 100
    return float(np.mean(ape))


def calculate_rmse(
    actual: np.ndarray | pd.Series,
    predicted: np.ndarray | pd.Series,
) -> float:
    """Calculate Root Mean Squared Error.

    RMSE = sqrt(mean((actual - predicted)^2))

    Args:
        actual: Actual values.
        predicted: Predicted values.

    Returns:
        RMSE in native units.
    """
    actual_arr = np.asarray(actual)
    predicted_arr = np.asarray(predicted)

    mse = np.mean((actual_arr - predicted_arr) ** 2)
    return float(np.sqrt(mse))


def calculate_mae(
    actual: np.ndarray | pd.Series,
    predicted: np.ndarray | pd.Series,
) -> float:
    """Calculate Mean Absolute Error.

    MAE = mean(|actual - predicted|)

    Args:
        actual: Actual values.
        predicted: Predicted values.

    Returns:
        MAE in native units.
    """
    actual_arr = np.asarray(actual)
    predicted_arr = np.asarray(predicted)

    return float(np.mean(np.abs(actual_arr - predicted_arr)))


def calculate_coverage(
    actual: np.ndarray | pd.Series,
    ci_lower: np.ndarray | pd.Series,
    ci_upper: np.ndarray | pd.Series,
) -> float:
    """Calculate confidence interval coverage.

    Coverage = percentage of actuals within [ci_lower, ci_upper]

    For a well-calibrated 95% CI, coverage should be ~95%.

    Args:
        actual: Actual values.
        ci_lower: Lower bounds of confidence intervals.
        ci_upper: Upper bounds of confidence intervals.

    Returns:
        Coverage as percentage (0-100).
    """
    actual_arr = np.asarray(actual)
    lower_arr = np.asarray(ci_lower)
    upper_arr = np.asarray(ci_upper)

    within_ci = (actual_arr >= lower_arr) & (actual_arr <= upper_arr)
    return float(np.mean(within_ci) * 100)


def calculate_bias(
    actual: np.ndarray | pd.Series,
    predicted: np.ndarray | pd.Series,
) -> float:
    """Calculate forecast bias (mean signed error).

    Bias = mean(predicted - actual)

    Positive bias = systematic over-prediction
    Negative bias = systematic under-prediction

    Args:
        actual: Actual values.
        predicted: Predicted values.

    Returns:
        Bias in native units.
    """
    actual_arr = np.asarray(actual)
    predicted_arr = np.asarray(predicted)

    return float(np.mean(predicted_arr - actual_arr))


def calculate_hit_rate(
    actual: np.ndarray | pd.Series,
    predicted: np.ndarray | pd.Series,
) -> float:
    """Calculate direction prediction accuracy.

    Hit rate = percentage of correct direction predictions.
    Direction is determined by sign of change from previous value.

    Args:
        actual: Actual values.
        predicted: Predicted values.

    Returns:
        Hit rate as percentage (0-100).
    """
    actual_arr = np.asarray(actual)
    predicted_arr = np.asarray(predicted)

    if len(actual_arr) < 2:
        return 50.0  # Baseline for single observation

    # Calculate changes
    actual_change = np.diff(actual_arr)
    predicted_change = np.diff(predicted_arr)

    # Check if signs match (both positive, both negative, or both zero)
    correct = np.sign(actual_change) == np.sign(predicted_change)

    return float(np.mean(correct) * 100)


def compute_all_metrics(
    actual: np.ndarray | pd.Series,
    predicted: np.ndarray | pd.Series,
    ci_lower: np.ndarray | pd.Series | None = None,
    ci_upper: np.ndarray | pd.Series | None = None,
) -> NowcastMetrics:
    """Compute all nowcast accuracy metrics.

    Args:
        actual: Actual values.
        predicted: Predicted values.
        ci_lower: Optional lower bounds of confidence intervals.
        ci_upper: Optional upper bounds of confidence intervals.

    Returns:
        NowcastMetrics with all computed metrics.
    """
    actual_arr = np.asarray(actual)
    predicted_arr = np.asarray(predicted)

    # Handle NaN values
    valid_mask = ~(np.isnan(actual_arr) | np.isnan(predicted_arr))
    actual_valid = actual_arr[valid_mask]
    predicted_valid = predicted_arr[valid_mask]

    n_obs = len(actual_valid)

    if n_obs == 0:
        logger.warning("No valid observations for metrics computation")
        return NowcastMetrics(
            mape=float("inf"),
            rmse=float("inf"),
            mae=float("inf"),
            coverage=0.0,
            bias=0.0,
            n_observations=0,
            hit_rate=50.0,
        )

    mape = calculate_mape(actual_valid, predicted_valid)
    rmse = calculate_rmse(actual_valid, predicted_valid)
    mae = calculate_mae(actual_valid, predicted_valid)
    bias = calculate_bias(actual_valid, predicted_valid)
    hit_rate = calculate_hit_rate(actual_valid, predicted_valid)

    # Coverage if CI provided
    if ci_lower is not None and ci_upper is not None:
        lower_arr = np.asarray(ci_lower)[valid_mask]
        upper_arr = np.asarray(ci_upper)[valid_mask]
        coverage = calculate_coverage(actual_valid, lower_arr, upper_arr)
    else:
        coverage = 0.0

    return NowcastMetrics(
        mape=mape,
        rmse=rmse,
        mae=mae,
        coverage=coverage,
        bias=bias,
        n_observations=n_obs,
        hit_rate=hit_rate,
    )


def evaluate_nowcast_results(
    results: list[NowcastResult],
    actuals: np.ndarray | pd.Series,
) -> NowcastMetrics:
    """Evaluate a list of NowcastResults against actual values.

    Args:
        results: List of NowcastResult objects.
        actuals: Corresponding actual values.

    Returns:
        NowcastMetrics summarizing performance.
    """
    if len(results) != len(actuals):
        raise ValueError(
            f"Length mismatch: {len(results)} results vs {len(actuals)} actuals"
        )

    predicted = np.array([r.mean for r in results])
    ci_lower = np.array([r.ci_lower for r in results])
    ci_upper = np.array([r.ci_upper for r in results])

    return compute_all_metrics(
        actual=np.asarray(actuals),
        predicted=predicted,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
    )
