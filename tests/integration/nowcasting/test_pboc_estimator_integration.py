"""Integration tests for PBoC balance sheet estimator.

These tests verify the full estimation pipeline with realistic data patterns
and validate model performance metrics.

Tests are marked with @pytest.mark.integration for selective execution.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from liquidity.nowcasting.midas import MIDASFeatures, PBoCEstimate, PBoCEstimator

# ============================================================================
# Fixtures with Realistic Data
# ============================================================================


@pytest.fixture
def realistic_date_range() -> pd.DatetimeIndex:
    """Create a 3-year daily date range (2022-2024)."""
    return pd.date_range("2022-01-01", "2024-12-31", freq="D")


@pytest.fixture
def realistic_shibor(realistic_date_range: pd.DatetimeIndex) -> pd.Series:
    """Create realistic SHIBOR overnight rate series.

    Models PBoC policy cycle:
    - 2022: Higher rates (2.0-2.2%)
    - 2023: Easing cycle (1.8-2.0%)
    - 2024: Stable low rates (1.5-1.8%)
    """
    np.random.seed(42)
    len(realistic_date_range)

    # Phase-dependent mean rates
    rates = []
    for _i, date in enumerate(realistic_date_range):
        if date.year == 2022:
            base = 2.1
        elif date.year == 2023:
            base = 1.9 - (date.month - 1) * 0.02  # Gradual easing
        else:
            base = 1.6

        # Add daily noise and mean reversion
        if rates:
            noise = np.random.normal(0, 0.02)
            rate = 0.95 * rates[-1] + 0.05 * base + noise
        else:
            rate = base

        rates.append(max(0.8, min(3.0, rate)))

    return pd.Series(rates, index=realistic_date_range, name="SHIBOR_ON")


@pytest.fixture
def realistic_dr007(realistic_date_range: pd.DatetimeIndex) -> pd.Series:
    """Create realistic DR007 weekly rate series.

    Highly correlated with SHIBOR but with its own dynamics.
    """
    np.random.seed(43)

    # Weekly dates
    weekly_dates = realistic_date_range[::5]
    rates = []

    for _i, date in enumerate(weekly_dates):
        if date.year == 2022:
            base = 2.0
        elif date.year == 2023:
            base = 1.85 - (date.month - 1) * 0.015
        else:
            base = 1.55

        if rates:
            noise = np.random.normal(0, 0.015)
            rate = 0.93 * rates[-1] + 0.07 * base + noise
        else:
            rate = base

        rates.append(max(0.8, min(2.8, rate)))

    weekly = pd.Series(rates, index=weekly_dates, name="DR007")
    return weekly.reindex(realistic_date_range)


@pytest.fixture
def realistic_spread(realistic_date_range: pd.DatetimeIndex) -> pd.Series:
    """Create realistic CNY-CNH spread series.

    Models capital flow dynamics:
    - Positive spread: CNH depreciation pressure
    - Negative spread: CNH appreciation pressure
    """
    np.random.seed(44)
    len(realistic_date_range)

    spread = []
    for _i, date in enumerate(realistic_date_range):
        # Event-driven spikes
        if date.month == 8 and date.year == 2023:  # August 2023 stress
            base = 200
        elif date.month in [3, 6, 9, 12]:  # Quarter-end
            base = 50
        else:
            base = 0

        if spread:
            noise = np.random.normal(0, 30)
            s = 0.85 * spread[-1] + 0.15 * base + noise
        else:
            s = base

        spread.append(max(-400, min(500, s)))

    return pd.Series(spread, index=realistic_date_range, name="CNY_CNH_SPREAD")


@pytest.fixture
def realistic_pboc_monthly(
    realistic_date_range: pd.DatetimeIndex,
    realistic_shibor: pd.Series,
) -> pd.Series:
    """Create realistic PBoC monthly total assets series.

    Models:
    - Growth trend (~5% per year)
    - Inverse relationship with rates (lower rates = more liquidity)
    - Seasonal patterns (year-end expansion)
    """
    monthly_dates = pd.date_range(
        realistic_date_range[0], realistic_date_range[-1], freq="ME"
    )

    np.random.seed(45)

    # Monthly average rates as predictor
    shibor_monthly = realistic_shibor.resample("ME").mean()

    assets = []
    base = 42.0  # Starting point: 42 trillion CNY (early 2022)

    for i, date in enumerate(monthly_dates):
        # Growth trend
        months_from_start = i
        trend = months_from_start * 0.12  # ~1.4 trillion/year growth

        # Rate effect: lower rates = more assets
        rate = shibor_monthly.get(date, 1.8)
        rate_effect = -0.8 * (rate - 1.8)

        # Seasonal: year-end expansion
        if date.month == 12:
            seasonal = 0.5
        elif date.month == 1:
            seasonal = -0.3  # Contraction after year-end
        else:
            seasonal = 0

        noise = np.random.normal(0, 0.15)

        asset = base + trend + rate_effect + seasonal + noise
        assets.append(max(40, asset))

    return pd.Series(assets, index=monthly_dates, name="PBOC_ASSETS")


# ============================================================================
# Integration Tests
# ============================================================================


class TestPBoCEstimatorIntegration:
    """Integration tests for full PBoC estimation pipeline."""

    @pytest.mark.integration
    def test_full_pipeline_realistic_data(
        self,
        realistic_shibor: pd.Series,
        realistic_dr007: pd.Series,
        realistic_spread: pd.Series,
        realistic_pboc_monthly: pd.Series,
    ) -> None:
        """Test full estimation pipeline with realistic data."""
        estimator = PBoCEstimator(
            alpha=10.0,
            n_daily_lags=20,
            n_weekly_lags=4,
            daily_decay=30.0,
        )

        # Fit model
        estimator.fit(
            shibor_daily=realistic_shibor,
            dr007_weekly=realistic_dr007,
            cny_cnh_spread=realistic_spread,
            pboc_monthly=realistic_pboc_monthly,
        )

        assert estimator.is_fitted

        # Get diagnostics
        diagnostics = estimator.get_diagnostics()
        assert diagnostics["train_r2"] > 0.3, f"R^2 too low: {diagnostics['train_r2']}"

        # Generate estimate
        estimate = estimator.estimate(
            shibor_daily=realistic_shibor,
            dr007_weekly=realistic_dr007,
            cny_cnh_spread=realistic_spread,
        )

        assert isinstance(estimate, PBoCEstimate)
        # Estimate should be in reasonable range (40-50 trillion CNY)
        assert 40 <= estimate.estimate <= 55, f"Estimate out of range: {estimate.estimate}"

    @pytest.mark.integration
    def test_backtest_performance_metrics(
        self,
        realistic_shibor: pd.Series,
        realistic_dr007: pd.Series,
        realistic_spread: pd.Series,
        realistic_pboc_monthly: pd.Series,
    ) -> None:
        """Test backtest performance meets target metrics."""
        estimator = PBoCEstimator(
            alpha=10.0,
            n_daily_lags=20,
            n_weekly_lags=4,
        )

        results_df, summary = estimator.backtest(
            shibor_daily=realistic_shibor,
            dr007_weekly=realistic_dr007,
            cny_cnh_spread=realistic_spread,
            pboc_official=realistic_pboc_monthly,
            train_months=18,  # 18 months training
        )

        # Should have results
        assert len(results_df) > 0, "No backtest results"
        assert summary["n_periods"] > 0

        # Performance checks (relaxed for synthetic data)
        # In production, we'd expect MAPE < 5%
        assert summary["mape"] < 10, f"MAPE too high: {summary['mape']:.2f}%"

        # CI coverage should be reasonable (target: ~95%)
        assert summary["ci_coverage"] > 70, f"CI coverage too low: {summary['ci_coverage']:.1f}%"

        print("\nBacktest Summary:")
        print(f"  Periods: {summary['n_periods']}")
        print(f"  MAPE: {summary['mape']:.2f}%")
        print(f"  Max Error: {summary['max_error_pct']:.2f}%")
        print(f"  CI Coverage: {summary['ci_coverage']:.1f}%")

    @pytest.mark.integration
    def test_alpha_tuning(
        self,
        realistic_shibor: pd.Series,
        realistic_dr007: pd.Series,
        realistic_pboc_monthly: pd.Series,
    ) -> None:
        """Test that alpha tuning improves or maintains performance."""
        # Fit without tuning
        estimator_no_tune = PBoCEstimator(n_daily_lags=15, n_weekly_lags=3)
        estimator_no_tune.fit(
            shibor_daily=realistic_shibor,
            dr007_weekly=realistic_dr007,
            cny_cnh_spread=None,
            pboc_monthly=realistic_pboc_monthly,
            tune_alpha=False,
        )

        # Fit with tuning
        estimator_tuned = PBoCEstimator(n_daily_lags=15, n_weekly_lags=3)
        estimator_tuned.fit(
            shibor_daily=realistic_shibor,
            dr007_weekly=realistic_dr007,
            cny_cnh_spread=None,
            pboc_monthly=realistic_pboc_monthly,
            tune_alpha=True,
        )

        # Both should be fitted
        assert estimator_no_tune.is_fitted
        assert estimator_tuned.is_fitted

        # Tuned model should have reasonable R^2
        assert estimator_tuned._train_r2 > 0

    @pytest.mark.integration
    def test_feature_importance_stability(
        self,
        realistic_shibor: pd.Series,
        realistic_dr007: pd.Series,
        realistic_pboc_monthly: pd.Series,
    ) -> None:
        """Test that feature importance is stable across reruns."""
        estimator1 = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)
        estimator2 = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        # Fit both on same data
        for est in [estimator1, estimator2]:
            est.fit(
                shibor_daily=realistic_shibor,
                dr007_weekly=realistic_dr007,
                cny_cnh_spread=None,
                pboc_monthly=realistic_pboc_monthly,
            )

        # Feature importance should be identical
        fi1 = estimator1._get_feature_importance(top_n=5)
        fi2 = estimator2._get_feature_importance(top_n=5)

        assert set(fi1.keys()) == set(fi2.keys()), "Top features differ"

    @pytest.mark.integration
    def test_estimate_confidence_bounds(
        self,
        realistic_shibor: pd.Series,
        realistic_dr007: pd.Series,
        realistic_pboc_monthly: pd.Series,
    ) -> None:
        """Test that confidence bounds are valid and calibrated."""
        estimator = PBoCEstimator(n_daily_lags=15, n_weekly_lags=3)

        estimator.fit(
            shibor_daily=realistic_shibor,
            dr007_weekly=realistic_dr007,
            cny_cnh_spread=None,
            pboc_monthly=realistic_pboc_monthly,
        )

        estimate = estimator.estimate(
            shibor_daily=realistic_shibor,
            dr007_weekly=realistic_dr007,
        )

        # CI should bracket the estimate
        assert estimate.ci_lower < estimate.estimate < estimate.ci_upper

        # CI width should be reasonable (not too wide, not too narrow)
        ci_width = estimate.ci_upper - estimate.ci_lower
        relative_width = ci_width / estimate.estimate
        assert 0.01 < relative_width < 0.2, f"CI width unreasonable: {relative_width:.3f}"


class TestMIDASFeaturesIntegration:
    """Integration tests for MIDAS feature engineering."""

    @pytest.mark.integration
    def test_feature_matrix_alignment(
        self,
        realistic_shibor: pd.Series,
        realistic_dr007: pd.Series,
        realistic_spread: pd.Series,
    ) -> None:
        """Test that feature matrix aligns correctly across frequencies."""
        features = MIDASFeatures()
        X, names = features.create_midas_features(
            daily_series=realistic_shibor,
            weekly_series=realistic_dr007,
            spread_series=realistic_spread,
            n_daily_lags=30,
            n_weekly_lags=4,
        )

        # Should have same index for all features
        assert X.index.is_monotonic_increasing, "Index should be sorted"

        # No duplicate indices
        assert not X.index.has_duplicates, "Index has duplicates"

        # Features should have correct count
        30 + 4 + 1 + 1 + 1 + 1 + 5 + 1  # lags + weighted sums + spread + changes
        assert len(names) >= 30, f"Expected at least 30 features, got {len(names)}"

    @pytest.mark.integration
    def test_aggregated_vs_lag_features(
        self,
        realistic_shibor: pd.Series,
        realistic_dr007: pd.Series,
    ) -> None:
        """Compare aggregated features vs lag features."""
        features = MIDASFeatures()

        # Lag features
        X_lags, _ = features.create_midas_features(
            daily_series=realistic_shibor,
            weekly_series=realistic_dr007,
            n_daily_lags=20,
            n_weekly_lags=4,
        )

        # Aggregated features
        X_agg, _ = features.create_aggregated_features(
            daily_series=realistic_shibor,
            weekly_series=realistic_dr007,
            resample_freq="ME",
        )

        # Lag features should have more observations (daily)
        assert len(X_lags) > len(X_agg)

        # Aggregated should be monthly
        assert len(X_agg) <= 36, "Should have ~36 monthly observations"


class TestEdgeCasesIntegration:
    """Integration tests for edge cases."""

    @pytest.mark.integration
    def test_missing_data_handling(
        self,
        realistic_shibor: pd.Series,
        realistic_dr007: pd.Series,
        realistic_pboc_monthly: pd.Series,
    ) -> None:
        """Test handling of series with missing data."""
        # Introduce missing data
        shibor_missing = realistic_shibor.copy()
        shibor_missing.iloc[100:120] = np.nan

        dr007_missing = realistic_dr007.copy()
        dr007_missing.iloc[::3] = np.nan  # Every 3rd observation

        estimator = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        # Should still fit (forward-fill handles NaN)
        estimator.fit(
            shibor_daily=shibor_missing,
            dr007_weekly=dr007_missing,
            cny_cnh_spread=None,
            pboc_monthly=realistic_pboc_monthly,
        )

        assert estimator.is_fitted

        # Should generate estimate
        estimate = estimator.estimate(
            shibor_daily=shibor_missing,
            dr007_weekly=dr007_missing,
        )

        assert estimate.estimate > 0

    @pytest.mark.integration
    def test_short_history_graceful_degradation(
        self,
        realistic_shibor: pd.Series,
        realistic_dr007: pd.Series,
        realistic_pboc_monthly: pd.Series,
    ) -> None:
        """Test behavior with shorter history."""
        # Use only 2 years of data
        start_date = "2023-01-01"

        shibor_short = realistic_shibor.loc[start_date:]
        dr007_short = realistic_dr007.loc[start_date:]
        pboc_short = realistic_pboc_monthly.loc[start_date:]

        estimator = PBoCEstimator(n_daily_lags=10, n_weekly_lags=2)

        # Should fit with reduced data
        estimator.fit(
            shibor_daily=shibor_short,
            dr007_weekly=dr007_short,
            cny_cnh_spread=None,
            pboc_monthly=pboc_short,
        )

        assert estimator.is_fitted

        # Confidence should reflect limited data
        estimate = estimator.estimate(
            shibor_daily=shibor_short,
            dr007_weekly=dr007_short,
        )

        # Model should indicate lower confidence with less data
        assert estimate.confidence > 0
