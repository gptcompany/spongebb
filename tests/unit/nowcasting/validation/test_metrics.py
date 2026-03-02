from unittest.mock import MagicMock

import numpy as np
import pytest

from liquidity.nowcasting.kalman import NowcastResult
from liquidity.nowcasting.validation.metrics import (
    NowcastMetrics,
    calculate_bias,
    calculate_coverage,
    calculate_hit_rate,
    calculate_mae,
    calculate_mape,
    calculate_rmse,
    compute_all_metrics,
    evaluate_nowcast_results,
)


def test_calculate_mape():
    actual = np.array([100.0, 200.0, 300.0])
    predicted = np.array([110.0, 190.0, 330.0])

    # |10/100| = 0.1, |-10/200| = 0.05, |30/300| = 0.1
    # Mean = (0.1 + 0.05 + 0.1) / 3 = 0.25 / 3 = 0.0833...
    # MAPE = 8.333...
    mape = calculate_mape(actual, predicted)
    assert pytest.approx(mape) == 8.333333333333334


def test_calculate_mape_zero_actual():
    actual = np.array([0.0, 0.0])
    predicted = np.array([10.0, 10.0])
    mape = calculate_mape(actual, predicted)
    assert mape == float("inf")


def test_calculate_rmse():
    actual = np.array([10.0, 20.0])
    predicted = np.array([13.0, 16.0])
    # errors = [3, -4], squared = [9, 16], mean = 12.5, sqrt = 3.5355...
    rmse = calculate_rmse(actual, predicted)
    assert pytest.approx(rmse) == 3.5355339059327378


def test_calculate_mae():
    actual = np.array([10.0, 20.0])
    predicted = np.array([13.0, 16.0])
    # absolute errors = [3, 4], mean = 3.5
    mae = calculate_mae(actual, predicted)
    assert mae == 3.5


def test_calculate_coverage():
    actual = np.array([10.0, 20.0, 30.0])
    ci_lower = np.array([9.0, 21.0, 25.0])
    ci_upper = np.array([11.0, 25.0, 35.0])
    # 10 is in [9, 11] - Yes
    # 20 is in [21, 25] - No
    # 30 is in [25, 35] - Yes
    # Coverage = 2/3 = 66.66...
    coverage = calculate_coverage(actual, ci_lower, ci_upper)
    assert pytest.approx(coverage) == 66.66666666666667


def test_calculate_bias():
    actual = np.array([10.0, 20.0])
    predicted = np.array([12.0, 22.0])
    # mean(2, 2) = 2.0
    bias = calculate_bias(actual, predicted)
    assert bias == 2.0


def test_calculate_hit_rate():
    actual = np.array([10, 11, 10, 12])
    predicted = np.array([10, 12, 11, 13])
    # actual changes: [1, -1, 2]
    # predicted changes: [2, -1, 2]
    # Signs: [+, -, +] == [+, -, +] -> 3/3 = 100%
    hit_rate = calculate_hit_rate(actual, predicted)
    assert hit_rate == 100.0

    predicted_bad = np.array([10, 9, 11, 10])
    # predicted changes: [-1, 2, -1]
    # Signs match: [False, False, False] -> 0%
    hit_rate_bad = calculate_hit_rate(actual, predicted_bad)
    assert hit_rate_bad == 0.0


def test_compute_all_metrics_with_nan():
    actual = np.array([10.0, np.nan, 30.0])
    predicted = np.array([11.0, 20.0, np.nan])
    # Valid pair is only (10, 11)
    metrics = compute_all_metrics(actual, predicted)
    assert metrics.n_observations == 1
    assert metrics.mape == 10.0
    assert metrics.rmse == 1.0


def test_compute_all_metrics_empty():
    metrics = compute_all_metrics(np.array([]), np.array([]))
    assert metrics.n_observations == 0
    assert metrics.mape == float("inf")


def test_evaluate_nowcast_results():
    results = [
        MagicMock(spec=NowcastResult, mean=11.0, ci_lower=9.0, ci_upper=13.0),
        MagicMock(spec=NowcastResult, mean=19.0, ci_lower=17.0, ci_upper=21.0),
    ]
    actuals = np.array([10.0, 20.0])

    metrics = evaluate_nowcast_results(results, actuals)
    assert metrics.n_observations == 2
    assert metrics.mape == 7.5 # (10% + 5%) / 2
    assert metrics.coverage == 100.0


def test_nowcast_metrics_properties():
    metrics = NowcastMetrics(
        mape=2.5, rmse=0.1, mae=0.1, coverage=95.0, bias=0.01, n_observations=100
    )
    assert metrics.passes_threshold is True

    bad_metrics = NowcastMetrics(
        mape=4.0, rmse=0.1, mae=0.1, coverage=95.0, bias=0.01, n_observations=100
    )
    assert bad_metrics.passes_threshold is False

    d = metrics.to_dict()
    assert d["mape"] == 2.5
    assert "NowcastMetrics" in repr(metrics)
