"""Unit tests for Kalman filter nowcasting module.

Tests:
- LiquidityStateSpace model fitting and nowcasting
- NowcastResult dataclass
- KalmanTuner parameter estimation
- Ragged edge handling with NaN observations

Run with: uv run pytest tests/unit/nowcasting/test_kalman.py -v
"""

import numpy as np
import pandas as pd
import pytest

from liquidity.nowcasting.kalman import KalmanTuner, LiquidityStateSpace, NowcastResult
from liquidity.nowcasting.kalman.tuning import NoiseEstimates


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_liquidity_series() -> pd.Series:
    """Generate sample Net Liquidity time series for testing.

    Creates a realistic-looking series with trend and noise.
    Values roughly represent Net Liquidity in trillions USD.
    """
    np.random.seed(42)
    n = 252  # ~1 year of daily data

    # Start at 5T, with slight upward trend and mean-reverting noise
    base = 5.0
    trend = np.linspace(0, 0.5, n)  # 0.5T increase over year
    noise = np.cumsum(np.random.normal(0, 0.02, n))  # Random walk noise

    values = base + trend + noise

    dates = pd.date_range(start="2025-01-01", periods=n, freq="B")
    return pd.Series(values, index=dates, name="net_liquidity")


@pytest.fixture
def sample_series_with_gaps(sample_liquidity_series: pd.Series) -> pd.Series:
    """Create series with missing values (ragged edge)."""
    series = sample_liquidity_series.copy()
    # Introduce NaN values at random positions (~10% missing)
    np.random.seed(123)
    missing_idx = np.random.choice(len(series), size=int(len(series) * 0.1), replace=False)
    series.iloc[missing_idx] = np.nan
    return series


@pytest.fixture
def short_series() -> pd.Series:
    """Short series for edge case testing."""
    dates = pd.date_range(start="2025-01-01", periods=5, freq="B")
    return pd.Series([5.0, 5.1, 5.05, 5.15, 5.1], index=dates)


@pytest.fixture
def kalman_tuner() -> KalmanTuner:
    """Create KalmanTuner instance."""
    return KalmanTuner()


# ============================================================================
# NowcastResult Tests
# ============================================================================

class TestNowcastResult:
    """Tests for NowcastResult dataclass."""

    def test_nowcast_result_creation(self) -> None:
        """Test NowcastResult can be created with all fields."""
        result = NowcastResult(
            timestamp=pd.Timestamp("2025-06-01"),
            mean=5.5,
            std=0.1,
            ci_lower=5.3,
            ci_upper=5.7,
            kalman_gain=np.array([[0.5], [0.1]]),
            innovation=0.05,
            filtered_state=np.array([5.5, 0.01]),
            n_missing=5,
        )

        assert result.mean == 5.5
        assert result.std == 0.1
        assert result.ci_lower == 5.3
        assert result.ci_upper == 5.7
        assert result.innovation == 0.05
        assert result.n_missing == 5

    def test_nowcast_result_ci_width(self) -> None:
        """Test CI width property."""
        result = NowcastResult(
            timestamp=pd.Timestamp("2025-06-01"),
            mean=5.5,
            std=0.1,
            ci_lower=5.3,
            ci_upper=5.7,
            kalman_gain=np.array([[0.5]]),
            innovation=0.0,
            filtered_state=np.array([5.5]),
        )

        assert result.ci_width == pytest.approx(0.4, rel=1e-6)

    def test_nowcast_result_level_trend(self) -> None:
        """Test level and trend extraction from filtered state."""
        result = NowcastResult(
            timestamp=pd.Timestamp("2025-06-01"),
            mean=5.5,
            std=0.1,
            ci_lower=5.3,
            ci_upper=5.7,
            kalman_gain=np.array([[0.5], [0.1]]),
            innovation=0.0,
            filtered_state=np.array([5.5, 0.02]),
        )

        assert result.level == 5.5
        assert result.trend == 0.02

    def test_nowcast_result_frozen(self) -> None:
        """Test NowcastResult is immutable (frozen dataclass)."""
        result = NowcastResult(
            timestamp=pd.Timestamp("2025-06-01"),
            mean=5.5,
            std=0.1,
            ci_lower=5.3,
            ci_upper=5.7,
            kalman_gain=np.array([[0.5]]),
            innovation=0.0,
            filtered_state=np.array([5.5]),
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            result.mean = 6.0  # type: ignore[misc]

    def test_nowcast_result_repr(self) -> None:
        """Test string representation."""
        result = NowcastResult(
            timestamp=pd.Timestamp("2025-06-01"),
            mean=5.5,
            std=0.1,
            ci_lower=5.3,
            ci_upper=5.7,
            kalman_gain=np.array([[0.5]]),
            innovation=0.0,
            filtered_state=np.array([5.5]),
        )

        repr_str = repr(result)
        assert "5.50" in repr_str
        assert "5.30" in repr_str
        assert "5.70" in repr_str


# ============================================================================
# LiquidityStateSpace Tests
# ============================================================================

class TestLiquidityStateSpace:
    """Tests for LiquidityStateSpace model."""

    def test_model_initialization(self) -> None:
        """Test model can be initialized with default parameters."""
        model = LiquidityStateSpace()

        assert model.level == "local level"
        assert model.trend == "local linear trend"
        assert not model.is_fitted

    def test_model_initialization_custom(self) -> None:
        """Test model initialization with custom parameters."""
        model = LiquidityStateSpace(
            level="local level",
            trend=None,
            seasonal=5,
        )

        assert model.trend is None
        assert model.seasonal == 5

    def test_fit_on_valid_data(self, sample_liquidity_series: pd.Series) -> None:
        """Test model fits on valid data."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        assert model.is_fitted
        assert model._results is not None

    def test_fit_returns_self(self, sample_liquidity_series: pd.Series) -> None:
        """Test fit returns self for method chaining."""
        model = LiquidityStateSpace()
        result = model.fit(sample_liquidity_series)

        assert result is model

    def test_fit_on_empty_series_raises(self) -> None:
        """Test fit raises on empty series."""
        model = LiquidityStateSpace()
        empty_series = pd.Series([], dtype=float)

        with pytest.raises(ValueError, match="Cannot fit on empty series"):
            model.fit(empty_series)

    def test_fit_on_insufficient_data_raises(self) -> None:
        """Test fit raises when too few observations."""
        model = LiquidityStateSpace()
        short_series = pd.Series([1.0, 2.0, 3.0])

        with pytest.raises(ValueError, match="Insufficient data"):
            model.fit(short_series)

    def test_nowcast_after_fit(self, sample_liquidity_series: pd.Series) -> None:
        """Test nowcast works after fitting."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        result = model.nowcast(steps=1)

        assert isinstance(result, NowcastResult)
        assert not np.isnan(result.mean)
        assert result.std > 0
        assert result.ci_lower < result.mean < result.ci_upper

    def test_nowcast_before_fit_raises(self) -> None:
        """Test nowcast raises when model not fitted."""
        model = LiquidityStateSpace()

        with pytest.raises(ValueError, match="Model not fitted"):
            model.nowcast()

    def test_nowcast_multi_step(self, sample_liquidity_series: pd.Series) -> None:
        """Test multi-step ahead nowcast."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        result = model.nowcast(steps=5)

        assert isinstance(result, NowcastResult)
        # Multi-step forecast should have wider CI
        single_step = model.nowcast(steps=1)
        assert result.ci_width >= single_step.ci_width

    def test_nowcast_mean_reasonable(self, sample_liquidity_series: pd.Series) -> None:
        """Test nowcast mean is in reasonable range."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        result = model.nowcast()

        # Should be close to last observed value
        last_value = sample_liquidity_series.iloc[-1]
        assert abs(result.mean - last_value) < 1.0  # Within $1T

    def test_ragged_edge_handling(self, sample_series_with_gaps: pd.Series) -> None:
        """Test model handles missing values (ragged edge)."""
        model = LiquidityStateSpace()
        model.fit(sample_series_with_gaps)

        assert model.is_fitted

        result = model.nowcast()
        assert result.n_missing > 0
        assert not np.isnan(result.mean)

    def test_predict_in_sample(self, sample_liquidity_series: pd.Series) -> None:
        """Test in-sample predictions."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        predictions = model.predict_in_sample()

        assert isinstance(predictions, pd.DataFrame)
        assert "observed" in predictions.columns
        assert "predicted" in predictions.columns
        assert "level" in predictions.columns
        assert "residual" in predictions.columns
        assert len(predictions) == len(sample_liquidity_series)

    def test_update_with_new_observation(self, sample_liquidity_series: pd.Series) -> None:
        """Test updating model with new observation."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        original_nowcast = model.nowcast()

        # Update with new observation
        new_obs = sample_liquidity_series.iloc[-1] + 0.1
        updated_nowcast = model.update(new_obs)

        # Nowcast should have changed
        assert updated_nowcast.mean != original_nowcast.mean

    def test_update_with_missing_observation(self, sample_liquidity_series: pd.Series) -> None:
        """Test updating with missing (NaN) observation."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        # Update with missing observation
        result = model.update(None)

        # Should still produce valid nowcast
        assert not np.isnan(result.mean)

    def test_get_smoothed_state(self, sample_liquidity_series: pd.Series) -> None:
        """Test smoothed state retrieval."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        smoothed = model.get_smoothed_state()

        assert isinstance(smoothed, pd.DataFrame)
        assert "level_smoothed" in smoothed.columns
        assert "trend_smoothed" in smoothed.columns
        assert len(smoothed) == len(sample_liquidity_series)

    def test_get_diagnostics(self, sample_liquidity_series: pd.Series) -> None:
        """Test model diagnostics."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        diag = model.get_diagnostics()

        assert "aic" in diag
        assert "bic" in diag
        assert "llf" in diag
        assert "mse" in diag
        assert "mae" in diag
        assert "durbin_watson" in diag
        assert diag["mse"] >= 0
        assert 0 < diag["durbin_watson"] < 4

    def test_repr(self) -> None:
        """Test string representation."""
        model = LiquidityStateSpace()
        assert "not fitted" in repr(model)

    def test_repr_after_fit(self, sample_liquidity_series: pd.Series) -> None:
        """Test string representation after fitting."""
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)
        assert "fitted" in repr(model)


# ============================================================================
# KalmanTuner Tests
# ============================================================================

class TestKalmanTuner:
    """Tests for KalmanTuner parameter estimation."""

    def test_tuner_initialization(self) -> None:
        """Test tuner initializes with default parameters."""
        tuner = KalmanTuner()

        assert tuner._level_scale == 0.05
        assert tuner._trend_scale == 0.001
        assert "TGA" in tuner._measurement_errors
        assert "RRP" in tuner._measurement_errors

    def test_tuner_custom_errors(self) -> None:
        """Test tuner accepts custom measurement errors."""
        custom_errors = {"CUSTOM": 0.5}
        tuner = KalmanTuner(measurement_errors=custom_errors)

        assert "CUSTOM" in tuner._measurement_errors
        assert tuner._measurement_errors["CUSTOM"] == 0.5

    def test_estimate_measurement_noise_default(self, kalman_tuner: KalmanTuner) -> None:
        """Test measurement noise estimation with defaults."""
        R = kalman_tuner.estimate_measurement_noise()

        assert isinstance(R, np.ndarray)
        assert len(R) == 3  # TGA, RRP, SOFR
        assert all(r > 0 for r in R)

    def test_estimate_measurement_noise_custom_series(self, kalman_tuner: KalmanTuner) -> None:
        """Test measurement noise with custom series list."""
        R = kalman_tuner.estimate_measurement_noise(series_names=["TGA", "VIX"])

        assert len(R) == 2
        # TGA error = 0.5, VIX error = 0.5, so variances = 0.25
        assert R[0] == pytest.approx(0.25, rel=1e-6)
        assert R[1] == pytest.approx(0.25, rel=1e-6)

    def test_estimate_process_noise(
        self, kalman_tuner: KalmanTuner, sample_liquidity_series: pd.Series
    ) -> None:
        """Test process noise estimation from data."""
        level_var, trend_var = kalman_tuner.estimate_process_noise(sample_liquidity_series)

        assert level_var > 0
        assert trend_var > 0
        assert level_var > trend_var  # Level noise > trend noise

    def test_estimate_process_noise_short_series(self, kalman_tuner: KalmanTuner) -> None:
        """Test process noise estimation with short series uses defaults."""
        short = pd.Series([1.0, 2.0, 3.0])
        level_var, trend_var = kalman_tuner.estimate_process_noise(short)

        # Should use defaults without error
        assert level_var > 0
        assert trend_var > 0

    def test_estimate_from_data(
        self, kalman_tuner: KalmanTuner, sample_liquidity_series: pd.Series
    ) -> None:
        """Test full noise estimation from data."""
        estimates = kalman_tuner.estimate_from_data(sample_liquidity_series)

        assert isinstance(estimates, NoiseEstimates)
        assert estimates.measurement_noise.size > 0
        assert estimates.process_noise_level > 0
        assert estimates.process_noise_trend > 0
        assert estimates.signal_to_noise > 0

    def test_estimate_from_residuals(self, kalman_tuner: KalmanTuner) -> None:
        """Test noise estimation from model residuals."""
        # Create synthetic residuals
        np.random.seed(42)
        residuals = pd.Series(np.random.normal(0, 0.1, 100))

        meas_var, proc_var = KalmanTuner.estimate_from_residuals(residuals)

        assert meas_var > 0
        assert proc_var >= 0
        assert meas_var + proc_var > 0

    def test_adaptive_tuning(
        self, kalman_tuner: KalmanTuner, sample_liquidity_series: pd.Series
    ) -> None:
        """Test adaptive parameter tuning."""
        estimates = kalman_tuner.adaptive_tuning(
            sample_liquidity_series,
            n_iterations=2,  # Reduce for test speed
        )

        assert isinstance(estimates, NoiseEstimates)
        assert estimates.measurement_noise.size > 0

    def test_tuner_repr(self, kalman_tuner: KalmanTuner) -> None:
        """Test tuner string representation."""
        repr_str = repr(kalman_tuner)
        assert "KalmanTuner" in repr_str
        assert "level_scale" in repr_str


# ============================================================================
# Integration Tests
# ============================================================================

class TestKalmanIntegration:
    """Integration tests for Kalman filter components."""

    def test_full_workflow(self, sample_liquidity_series: pd.Series) -> None:
        """Test complete nowcasting workflow."""
        # 1. Tune parameters
        tuner = KalmanTuner()
        estimates = tuner.estimate_from_data(sample_liquidity_series)

        # 2. Create and fit model
        model = LiquidityStateSpace()
        model.fit(sample_liquidity_series)

        # 3. Generate nowcast
        result = model.nowcast(steps=1)

        # 4. Verify result quality
        assert result.mean > 0
        assert result.ci_lower < result.mean < result.ci_upper
        assert result.std > 0

        # 5. Get diagnostics
        diag = model.get_diagnostics()
        assert diag["mse"] < 1.0  # Reasonable fit

    def test_ragged_edge_workflow(self, sample_series_with_gaps: pd.Series) -> None:
        """Test workflow with missing data."""
        model = LiquidityStateSpace()
        model.fit(sample_series_with_gaps)

        result = model.nowcast()

        # Should handle missing data gracefully
        assert not np.isnan(result.mean)
        assert result.n_missing > 0

        # In-sample predictions should align with available data
        predictions = model.predict_in_sample()
        assert len(predictions) == len(sample_series_with_gaps)

    def test_sequential_updates(self, sample_liquidity_series: pd.Series) -> None:
        """Test sequential model updates."""
        # Use first 200 observations for initial fit
        initial_data = sample_liquidity_series.iloc[:200]

        model = LiquidityStateSpace()
        model.fit(initial_data)

        # Sequentially update with remaining observations
        nowcasts = []
        for i in range(200, min(210, len(sample_liquidity_series))):
            new_obs = sample_liquidity_series.iloc[i]
            result = model.update(new_obs)
            nowcasts.append(result)

        # Check all nowcasts are valid
        assert len(nowcasts) == min(10, len(sample_liquidity_series) - 200)
        assert all(not np.isnan(nc.mean) for nc in nowcasts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
