"""Unit tests for PBoC balance sheet estimator.

Tests cover:
- MIDASFeatures: Almon weighting, feature creation
- PBoCEstimator: fit, estimate, backtest
- PBoCEstimate: dataclass validation

Uses synthetic data to verify model behavior without external dependencies.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from liquidity.nowcasting.midas.features import MIDASFeatures
from liquidity.nowcasting.midas.pboc_estimator import (
    BacktestResult,
    PBoCEstimate,
    PBoCEstimator,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def date_range() -> pd.DatetimeIndex:
    """Create a 2-year daily date range."""
    return pd.date_range("2023-01-01", "2024-12-31", freq="D")


@pytest.fixture
def synthetic_shibor(date_range: pd.DatetimeIndex) -> pd.Series:
    """Create synthetic SHIBOR overnight rate.

    Generates a mean-reverting series around 1.8% with some noise.
    """
    np.random.seed(42)
    n = len(date_range)

    # AR(1) process: x_t = 0.95 * x_{t-1} + 0.05 * 1.8 + noise
    rates = [1.8]
    for _ in range(1, n):
        noise = np.random.normal(0, 0.05)
        new_rate = 0.95 * rates[-1] + 0.05 * 1.8 + noise
        rates.append(max(0.5, min(3.0, new_rate)))  # Bound between 0.5% and 3%

    return pd.Series(rates, index=date_range, name="SHIBOR_ON")


@pytest.fixture
def synthetic_dr007(date_range: pd.DatetimeIndex) -> pd.Series:
    """Create synthetic DR007 weekly rate.

    Correlated with SHIBOR but at weekly frequency.
    """
    np.random.seed(43)
    # Weekly dates
    weekly_dates = date_range[::5]
    n = len(weekly_dates)

    rates = [1.7]
    for _ in range(1, n):
        noise = np.random.normal(0, 0.03)
        new_rate = 0.95 * rates[-1] + 0.05 * 1.7 + noise
        rates.append(max(0.5, min(3.0, new_rate)))

    # Reindex to daily for alignment (will have many NaN)
    weekly = pd.Series(rates, index=weekly_dates, name="DR007")
    return weekly.reindex(date_range)


@pytest.fixture
def synthetic_spread(date_range: pd.DatetimeIndex) -> pd.Series:
    """Create synthetic CNY-CNH spread.

    Random walk around 0 basis points.
    """
    np.random.seed(44)
    n = len(date_range)

    spread = [0.0]
    for _ in range(1, n):
        noise = np.random.normal(0, 50)  # Basis points
        new_spread = 0.9 * spread[-1] + noise
        spread.append(max(-500, min(500, new_spread)))

    return pd.Series(spread, index=date_range, name="CNY_CNH_SPREAD")


@pytest.fixture
def synthetic_pboc_monthly(date_range: pd.DatetimeIndex, synthetic_shibor: pd.Series) -> pd.Series:
    """Create synthetic PBoC monthly assets.

    Correlated with SHIBOR (negatively - lower rates = more liquidity).
    Base: ~45 trillion CNY with growth trend.
    """
    monthly_dates = pd.date_range(
        date_range[0], date_range[-1], freq="ME"
    )

    np.random.seed(45)

    # Monthly average SHIBOR as predictor
    shibor_monthly = synthetic_shibor.resample("ME").mean()

    # PBoC assets: base + trend + SHIBOR effect + noise
    base = 45.0  # Trillion CNY
    trend = np.linspace(0, 3.0, len(monthly_dates))  # Growth over 2 years
    shibor_effect = -0.5 * (shibor_monthly.reindex(monthly_dates) - 1.8)  # Lower rates = more assets
    noise = np.random.normal(0, 0.2, len(monthly_dates))

    assets = base + trend + shibor_effect.values + noise

    return pd.Series(assets, index=monthly_dates, name="PBOC_ASSETS")


# ============================================================================
# MIDASFeatures Tests
# ============================================================================


class TestMIDASFeatures:
    """Tests for MIDASFeatures class."""

    @pytest.mark.unit
    def test_almon_weights_sum_to_one(self) -> None:
        """Test that Almon weights sum to 1."""
        weights = MIDASFeatures.almon_weights(30, decay=30.0)
        assert np.isclose(weights.sum(), 1.0), f"Weights sum to {weights.sum()}, expected 1.0"

    @pytest.mark.unit
    def test_almon_weights_decay(self) -> None:
        """Test that Almon weights decay with lag."""
        weights = MIDASFeatures.almon_weights(10, decay=30.0)

        # First weight should be highest
        assert weights[0] > weights[-1], "First weight should be > last weight"

        # Weights should be monotonically decreasing
        for i in range(len(weights) - 1):
            assert weights[i] >= weights[i + 1], f"Weight at {i} should be >= weight at {i+1}"

    @pytest.mark.unit
    def test_almon_weights_different_decay(self) -> None:
        """Test that different decay parameters produce different weights."""
        weights_fast = MIDASFeatures.almon_weights(10, decay=5.0)
        weights_slow = MIDASFeatures.almon_weights(10, decay=100.0)

        # Fast decay should have more weight on first lag
        assert weights_fast[0] > weights_slow[0], "Fast decay should weight first lag more"

        # Slow decay should have more weight on later lags
        assert weights_slow[-1] > weights_fast[-1], "Slow decay should weight later lags more"

    @pytest.mark.unit
    def test_almon_weights_invalid_inputs(self) -> None:
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError, match="n_lags must be >= 1"):
            MIDASFeatures.almon_weights(0, decay=30.0)

        with pytest.raises(ValueError, match="decay must be > 0"):
            MIDASFeatures.almon_weights(10, decay=0.0)

        with pytest.raises(ValueError, match="decay must be > 0"):
            MIDASFeatures.almon_weights(10, decay=-5.0)

    @pytest.mark.unit
    def test_exponential_weights_sum_to_one(self) -> None:
        """Test that exponential weights sum to 1."""
        weights = MIDASFeatures.exponential_weights(30, half_life=10.0)
        assert np.isclose(weights.sum(), 1.0), f"Weights sum to {weights.sum()}, expected 1.0"

    @pytest.mark.unit
    def test_exponential_weights_half_life(self) -> None:
        """Test that exponential weights respect half-life."""
        # With half_life=10, weight at lag 10 should be ~half of weight at lag 0
        # But since we normalize, we check relative ratio
        weights = MIDASFeatures.exponential_weights(20, half_life=10.0)

        # Weight at lag 11 should be ~half of weight at lag 1
        ratio = weights[10] / weights[0]
        expected_ratio = 0.5
        assert np.isclose(ratio, expected_ratio, rtol=0.01), (
            f"Expected ratio ~{expected_ratio}, got {ratio}"
        )

    @pytest.mark.unit
    def test_create_midas_features_basic(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
    ) -> None:
        """Test basic MIDAS feature creation."""
        features = MIDASFeatures()
        X, names = features.create_midas_features(
            daily_series=synthetic_shibor,
            weekly_series=synthetic_dr007,
            n_daily_lags=10,
            n_weekly_lags=2,
        )

        assert isinstance(X, pd.DataFrame)
        assert len(names) > 0
        assert len(X.columns) == len(names)

        # Should have daily lag features
        daily_lag_cols = [c for c in X.columns if c.startswith("daily_lag_")]
        assert len(daily_lag_cols) == 10, f"Expected 10 daily lag features, got {len(daily_lag_cols)}"

        # Should have weekly lag features
        weekly_lag_cols = [c for c in X.columns if c.startswith("weekly_lag_")]
        assert len(weekly_lag_cols) == 2, f"Expected 2 weekly lag features, got {len(weekly_lag_cols)}"

    @pytest.mark.unit
    def test_create_midas_features_with_spread(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
        synthetic_spread: pd.Series,
    ) -> None:
        """Test MIDAS feature creation with spread series."""
        features = MIDASFeatures()
        X, names = features.create_midas_features(
            daily_series=synthetic_shibor,
            weekly_series=synthetic_dr007,
            spread_series=synthetic_spread,
            n_daily_lags=5,
            n_weekly_lags=2,
        )

        # Should have spread features
        assert "spread" in X.columns
        assert "spread_ma5" in X.columns

    @pytest.mark.unit
    def test_create_midas_features_change_features(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
    ) -> None:
        """Test that change features are created."""
        features = MIDASFeatures()
        X, names = features.create_midas_features(
            daily_series=synthetic_shibor,
            weekly_series=synthetic_dr007,
            n_daily_lags=5,
            n_weekly_lags=2,
            include_change_features=True,
        )

        # Should have change features
        change_cols = [c for c in X.columns if "change" in c or "volatility" in c]
        assert len(change_cols) > 0, "Expected change features"

    @pytest.mark.unit
    def test_create_midas_features_no_change_features(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
    ) -> None:
        """Test disabling change features."""
        features = MIDASFeatures()
        X, names = features.create_midas_features(
            daily_series=synthetic_shibor,
            weekly_series=synthetic_dr007,
            n_daily_lags=5,
            n_weekly_lags=2,
            include_change_features=False,
        )

        # Should NOT have change features
        change_cols = [c for c in X.columns if "change" in c or "volatility" in c]
        assert len(change_cols) == 0, f"Unexpected change features: {change_cols}"

    @pytest.mark.unit
    def test_create_aggregated_features(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
        synthetic_spread: pd.Series,
    ) -> None:
        """Test aggregated feature creation."""
        features = MIDASFeatures()
        X, names = features.create_aggregated_features(
            daily_series=synthetic_shibor,
            weekly_series=synthetic_dr007,
            spread_series=synthetic_spread,
            resample_freq="ME",
        )

        assert isinstance(X, pd.DataFrame)
        assert not X.empty

        # Should have aggregation features
        assert "daily_mean" in X.columns
        assert "daily_std" in X.columns
        assert "weekly_mean" in X.columns
        assert "spread_mean" in X.columns

        # Should be monthly frequency
        assert X.index.freqstr == "ME" or len(X) <= 24, "Expected monthly data"


# ============================================================================
# PBoCEstimate Tests
# ============================================================================


class TestPBoCEstimate:
    """Tests for PBoCEstimate dataclass."""

    @pytest.mark.unit
    def test_estimate_creation(self) -> None:
        """Test basic estimate creation."""
        estimate = PBoCEstimate(
            timestamp=pd.Timestamp("2024-06-15"),
            estimate=46.5,
            std=0.3,
            ci_lower=45.9,
            ci_upper=47.1,
            days_ahead=15,
            confidence=0.85,
        )

        assert estimate.estimate == 46.5
        assert estimate.std == 0.3
        assert estimate.confidence == 0.85

    @pytest.mark.unit
    def test_estimate_validation_negative_estimate(self) -> None:
        """Test that negative estimates raise ValueError."""
        with pytest.raises(ValueError, match="estimate must be >= 0"):
            PBoCEstimate(
                timestamp=pd.Timestamp("2024-06-15"),
                estimate=-1.0,
                std=0.3,
                ci_lower=-1.6,
                ci_upper=-0.4,
                days_ahead=15,
                confidence=0.85,
            )

    @pytest.mark.unit
    def test_estimate_validation_negative_std(self) -> None:
        """Test that negative std raises ValueError."""
        with pytest.raises(ValueError, match="std must be >= 0"):
            PBoCEstimate(
                timestamp=pd.Timestamp("2024-06-15"),
                estimate=46.5,
                std=-0.3,
                ci_lower=46.0,
                ci_upper=47.0,
                days_ahead=15,
                confidence=0.85,
            )

    @pytest.mark.unit
    def test_estimate_validation_invalid_confidence(self) -> None:
        """Test that invalid confidence raises ValueError."""
        with pytest.raises(ValueError, match="confidence must be in"):
            PBoCEstimate(
                timestamp=pd.Timestamp("2024-06-15"),
                estimate=46.5,
                std=0.3,
                ci_lower=46.0,
                ci_upper=47.0,
                days_ahead=15,
                confidence=1.5,  # Invalid: > 1
            )

    @pytest.mark.unit
    def test_estimate_to_dict(self) -> None:
        """Test estimate serialization."""
        estimate = PBoCEstimate(
            timestamp=pd.Timestamp("2024-06-15"),
            estimate=46.5,
            std=0.3,
            ci_lower=45.9,
            ci_upper=47.1,
            days_ahead=15,
            confidence=0.85,
            feature_importance={"daily_lag_1": 0.3, "weekly_lag_1": 0.2},
        )

        d = estimate.to_dict()

        assert isinstance(d, dict)
        assert d["estimate"] == 46.5
        assert d["std"] == 0.3
        assert "timestamp" in d
        assert d["feature_importance"] is not None


# ============================================================================
# PBoCEstimator Tests
# ============================================================================


class TestPBoCEstimator:
    """Tests for PBoCEstimator class."""

    @pytest.mark.unit
    def test_estimator_initialization(self) -> None:
        """Test estimator initialization with default and custom params."""
        # Default params
        estimator = PBoCEstimator()
        assert estimator.alpha == PBoCEstimator.DEFAULT_ALPHA
        assert estimator.n_daily_lags == PBoCEstimator.DEFAULT_DAILY_LAGS
        assert not estimator.is_fitted

        # Custom params
        estimator = PBoCEstimator(alpha=100.0, n_daily_lags=20, n_weekly_lags=2)
        assert estimator.alpha == 100.0
        assert estimator.n_daily_lags == 20
        assert estimator.n_weekly_lags == 2

    @pytest.mark.unit
    def test_fit_basic(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
        synthetic_pboc_monthly: pd.Series,
    ) -> None:
        """Test basic model fitting."""
        estimator = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        result = estimator.fit(
            shibor_daily=synthetic_shibor,
            dr007_weekly=synthetic_dr007,
            cny_cnh_spread=None,
            pboc_monthly=synthetic_pboc_monthly,
        )

        # Should return self for chaining
        assert result is estimator

        # Should be fitted
        assert estimator.is_fitted

        # Should have non-zero R^2
        assert estimator._train_r2 > 0

    @pytest.mark.unit
    def test_fit_with_spread(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
        synthetic_spread: pd.Series,
        synthetic_pboc_monthly: pd.Series,
    ) -> None:
        """Test fitting with spread feature."""
        estimator = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        estimator.fit(
            shibor_daily=synthetic_shibor,
            dr007_weekly=synthetic_dr007,
            cny_cnh_spread=synthetic_spread,
            pboc_monthly=synthetic_pboc_monthly,
        )

        assert estimator.is_fitted
        assert "spread" in estimator._feature_names

    @pytest.mark.unit
    def test_fit_empty_series_raises(self) -> None:
        """Test that empty input series raise ValueError."""
        estimator = PBoCEstimator()

        with pytest.raises(ValueError, match="cannot be empty"):
            estimator.fit(
                shibor_daily=pd.Series(dtype=float),
                dr007_weekly=pd.Series(dtype=float),
                cny_cnh_spread=None,
                pboc_monthly=pd.Series(dtype=float),
            )

    @pytest.mark.unit
    def test_estimate_requires_fit(self) -> None:
        """Test that estimate() requires fit() first."""
        estimator = PBoCEstimator()

        with pytest.raises(ValueError, match="Model not fitted"):
            estimator.estimate(
                shibor_daily=pd.Series([1.8, 1.7], index=pd.date_range("2024-01-01", periods=2)),
                dr007_weekly=pd.Series([1.7], index=pd.date_range("2024-01-01", periods=1)),
            )

    @pytest.mark.unit
    def test_estimate_returns_valid_result(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
        synthetic_pboc_monthly: pd.Series,
    ) -> None:
        """Test that estimate() returns valid PBoCEstimate."""
        estimator = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        estimator.fit(
            shibor_daily=synthetic_shibor,
            dr007_weekly=synthetic_dr007,
            cny_cnh_spread=None,
            pboc_monthly=synthetic_pboc_monthly,
        )

        estimate = estimator.estimate(
            shibor_daily=synthetic_shibor,
            dr007_weekly=synthetic_dr007,
        )

        assert isinstance(estimate, PBoCEstimate)
        assert estimate.estimate > 0
        assert estimate.std >= 0
        assert estimate.ci_lower < estimate.ci_upper
        assert 0 <= estimate.confidence <= 1
        assert estimate.days_ahead >= 0

    @pytest.mark.unit
    def test_estimate_with_as_of_date(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
        synthetic_pboc_monthly: pd.Series,
    ) -> None:
        """Test estimate with specific as_of_date."""
        estimator = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        estimator.fit(
            shibor_daily=synthetic_shibor,
            dr007_weekly=synthetic_dr007,
            cny_cnh_spread=None,
            pboc_monthly=synthetic_pboc_monthly,
        )

        # Estimate as of mid-2024
        as_of = pd.Timestamp("2024-06-15")
        estimate = estimator.estimate(
            shibor_daily=synthetic_shibor,
            dr007_weekly=synthetic_dr007,
            as_of_date=as_of,
        )

        # Timestamp should be the as_of date
        assert estimate.timestamp <= as_of

    @pytest.mark.unit
    def test_fit_with_tune_alpha(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
        synthetic_pboc_monthly: pd.Series,
    ) -> None:
        """Test fitting with alpha tuning."""
        estimator = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        # Initial alpha
        initial_alpha = estimator.alpha

        estimator.fit(
            shibor_daily=synthetic_shibor,
            dr007_weekly=synthetic_dr007,
            cny_cnh_spread=None,
            pboc_monthly=synthetic_pboc_monthly,
            tune_alpha=True,
        )

        # Alpha may or may not change, but model should be fitted
        assert estimator.is_fitted

    @pytest.mark.unit
    def test_get_diagnostics_unfitted(self) -> None:
        """Test diagnostics for unfitted model."""
        estimator = PBoCEstimator()
        diagnostics = estimator.get_diagnostics()

        assert diagnostics["fitted"] is False

    @pytest.mark.unit
    def test_get_diagnostics_fitted(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
        synthetic_pboc_monthly: pd.Series,
    ) -> None:
        """Test diagnostics for fitted model."""
        estimator = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        estimator.fit(
            shibor_daily=synthetic_shibor,
            dr007_weekly=synthetic_dr007,
            cny_cnh_spread=None,
            pboc_monthly=synthetic_pboc_monthly,
        )

        diagnostics = estimator.get_diagnostics()

        assert diagnostics["fitted"] is True
        assert "alpha" in diagnostics
        assert "train_r2" in diagnostics
        assert "train_residual_std" in diagnostics
        assert "n_features" in diagnostics
        assert "feature_importance" in diagnostics

    @pytest.mark.unit
    def test_backtest_basic(
        self,
        synthetic_shibor: pd.Series,
        synthetic_dr007: pd.Series,
        synthetic_pboc_monthly: pd.Series,
    ) -> None:
        """Test basic backtest functionality."""
        estimator = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        results_df, summary = estimator.backtest(
            shibor_daily=synthetic_shibor,
            dr007_weekly=synthetic_dr007,
            cny_cnh_spread=None,
            pboc_official=synthetic_pboc_monthly,
            train_months=12,  # Use 12 months for training
        )

        # Should return results
        assert isinstance(results_df, pd.DataFrame)
        assert isinstance(summary, dict)

        # Should have results for multiple periods
        assert len(results_df) > 0

        # Summary should have expected keys
        assert "mape" in summary
        assert "n_periods" in summary
        assert "ci_coverage" in summary


class TestBacktestResult:
    """Tests for BacktestResult dataclass."""

    @pytest.mark.unit
    def test_backtest_result_creation(self) -> None:
        """Test BacktestResult creation."""
        result = BacktestResult(
            date=pd.Timestamp("2024-06-30"),
            estimate=46.5,
            official=46.3,
            error=0.2,
            error_pct=0.43,
            ci_lower=45.9,
            ci_upper=47.1,
            in_ci=True,
        )

        assert result.estimate == 46.5
        assert result.official == 46.3
        assert result.error == 0.2
        assert result.in_ci is True


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.unit
    def test_almon_weights_single_lag(self) -> None:
        """Test Almon weights with single lag."""
        weights = MIDASFeatures.almon_weights(1, decay=30.0)
        assert len(weights) == 1
        assert weights[0] == 1.0  # Single weight should be 1.0

    @pytest.mark.unit
    def test_almon_weights_many_lags(self) -> None:
        """Test Almon weights with many lags."""
        weights = MIDASFeatures.almon_weights(100, decay=30.0)
        assert len(weights) == 100
        assert np.isclose(weights.sum(), 1.0)

    @pytest.mark.unit
    def test_features_with_missing_data(self) -> None:
        """Test feature creation with missing data."""
        dates = pd.date_range("2024-01-01", "2024-03-31", freq="D")

        # Series with NaN values
        daily = pd.Series(np.random.randn(len(dates)) + 1.8, index=dates)
        daily.iloc[10:20] = np.nan  # Add missing data

        weekly = pd.Series(np.random.randn(len(dates)) + 1.7, index=dates)
        weekly.iloc[::5] = np.nan  # Sparse weekly

        features = MIDASFeatures()
        X, names = features.create_midas_features(
            daily_series=daily,
            weekly_series=weekly,
            n_daily_lags=5,
            n_weekly_lags=2,
        )

        # Should still create features (forward-filled)
        assert not X.empty

    @pytest.mark.unit
    def test_estimator_with_small_dataset(self) -> None:
        """Test estimator behavior with small dataset."""
        dates = pd.date_range("2024-01-01", "2024-06-30", freq="D")
        monthly_dates = pd.date_range("2024-01-31", "2024-06-30", freq="ME")

        daily = pd.Series(np.random.randn(len(dates)) * 0.1 + 1.8, index=dates)
        weekly = pd.Series(np.random.randn(len(dates)) * 0.1 + 1.7, index=dates)
        monthly = pd.Series(np.random.randn(len(monthly_dates)) * 0.5 + 46, index=monthly_dates)

        estimator = PBoCEstimator(n_daily_lags=5, n_weekly_lags=2)

        # Should raise ValueError for too few observations
        with pytest.raises(ValueError, match="at least 10 observations"):
            estimator.fit(
                shibor_daily=daily,
                dr007_weekly=weekly,
                cny_cnh_spread=None,
                pboc_monthly=monthly,
            )
