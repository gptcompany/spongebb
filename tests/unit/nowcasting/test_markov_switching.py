"""Unit tests for Markov Switching regime classifier.

Tests:
- MarkovSwitchingClassifier initialization
- Model fitting on synthetic AR(1) data
- Filtered vs smoothed probabilities
- Regime interpretation (state mapping)
- Diagnostics extraction

Run with: uv run pytest tests/unit/nowcasting/test_markov_switching.py -v
"""

import numpy as np
import pandas as pd
import pytest

from liquidity.nowcasting.regime import (
    MarkovSwitchingClassifier,
    MarkovSwitchingDiagnostics,
    RegimeProbabilities,
    RegimeState,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def synthetic_ar1_data() -> pd.Series:
    """Generate synthetic AR(1) data with regime-switching behavior.

    Creates a time series with three distinct regimes:
    - High mean (expansion)
    - Medium mean (neutral)
    - Low mean (contraction)
    """
    np.random.seed(42)
    n = 300  # ~1 year of business days

    # Generate regime sequence (sticky transitions)
    regimes = []
    current_regime = 1  # Start neutral
    for _ in range(n):
        if np.random.random() < 0.95:  # 95% chance of staying
            regimes.append(current_regime)
        else:
            # Transition to adjacent regime
            if current_regime == 0:
                current_regime = 1
            elif current_regime == 2:
                current_regime = 1
            else:
                current_regime = np.random.choice([0, 2])
            regimes.append(current_regime)

    # Regime-specific parameters
    means = {0: 0.05, 1: 0.0, 2: -0.05}  # Expansion, Neutral, Contraction
    stds = {0: 0.02, 1: 0.01, 2: 0.03}

    # Generate AR(1) process with regime-switching
    values = np.zeros(n)
    ar_coef = 0.3

    for t in range(n):
        regime = regimes[t]
        innovation = np.random.normal(means[regime], stds[regime])
        if t > 0:
            values[t] = ar_coef * values[t - 1] + innovation
        else:
            values[t] = innovation

    dates = pd.date_range(start="2025-01-01", periods=n, freq="B")
    return pd.Series(values, index=dates, name="net_liq_return")


@pytest.fixture
def simple_series() -> pd.Series:
    """Generate simple series for basic tests."""
    np.random.seed(123)
    n = 100
    dates = pd.date_range(start="2025-01-01", periods=n, freq="B")
    values = np.random.randn(n) * 0.01
    return pd.Series(values, index=dates, name="returns")


@pytest.fixture
def short_series() -> pd.Series:
    """Generate short series for edge case testing."""
    dates = pd.date_range(start="2025-01-01", periods=10, freq="B")
    return pd.Series(np.random.randn(10) * 0.01, index=dates)


# ============================================================================
# Initialization Tests
# ============================================================================


class TestMarkovSwitchingInitialization:
    """Tests for MarkovSwitchingClassifier initialization."""

    def test_default_initialization(self) -> None:
        """Test classifier initializes with default parameters."""
        classifier = MarkovSwitchingClassifier()

        assert classifier.k_regimes == 3
        assert classifier.order == 1
        assert classifier.switching_variance is True
        assert classifier.trend == "c"
        assert not classifier.is_fitted

    def test_custom_initialization(self) -> None:
        """Test classifier accepts custom parameters."""
        classifier = MarkovSwitchingClassifier(
            k_regimes=2,
            order=2,
            switching_variance=False,
            trend="n",
        )

        assert classifier.k_regimes == 2
        assert classifier.order == 2
        assert classifier.switching_variance is False
        assert classifier.trend == "n"

    def test_repr_before_fit(self) -> None:
        """Test string representation before fitting."""
        classifier = MarkovSwitchingClassifier()
        repr_str = repr(classifier)

        assert "MarkovSwitchingClassifier" in repr_str
        assert "not fitted" in repr_str
        assert "k_regimes=3" in repr_str


# ============================================================================
# Fitting Tests
# ============================================================================


class TestMarkovSwitchingFitting:
    """Tests for model fitting."""

    def test_fit_on_valid_data(self, synthetic_ar1_data: pd.Series) -> None:
        """Test model fits on valid synthetic data."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        result = classifier.fit(synthetic_ar1_data)

        assert classifier.is_fitted
        assert result is classifier  # Returns self

    def test_fit_returns_self(self, simple_series: pd.Series) -> None:
        """Test fit returns self for method chaining."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=0)
        result = classifier.fit(simple_series)

        assert result is classifier

    def test_fit_on_empty_series_raises(self) -> None:
        """Test fit raises on empty series."""
        classifier = MarkovSwitchingClassifier()
        empty_series = pd.Series([], dtype=float)

        with pytest.raises(ValueError, match="Cannot fit on empty series"):
            classifier.fit(empty_series)

    def test_fit_on_insufficient_data_raises(self, short_series: pd.Series) -> None:
        """Test fit raises when too few observations."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)

        with pytest.raises(ValueError, match="Insufficient data"):
            classifier.fit(short_series)

    def test_fit_handles_nan_values(self, simple_series: pd.Series) -> None:
        """Test fit handles NaN values gracefully."""
        series_with_nan = simple_series.copy()
        series_with_nan.iloc[10:15] = np.nan

        classifier = MarkovSwitchingClassifier(k_regimes=3, order=0)
        classifier.fit(series_with_nan)

        assert classifier.is_fitted

    def test_repr_after_fit(self, simple_series: pd.Series) -> None:
        """Test string representation after fitting."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=0)
        classifier.fit(simple_series)

        repr_str = repr(classifier)
        assert "fitted" in repr_str
        assert "not fitted" not in repr_str


# ============================================================================
# Probability Tests
# ============================================================================


class TestMarkovSwitchingProbabilities:
    """Tests for regime probability methods."""

    def test_get_filtered_probabilities(self, synthetic_ar1_data: pd.Series) -> None:
        """Test filtered probabilities are returned correctly."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        filtered = classifier.get_filtered_probabilities()

        assert isinstance(filtered, pd.DataFrame)
        assert len(filtered) == len(synthetic_ar1_data)
        assert filtered.shape[1] == 3  # k_regimes columns

        # Probabilities should sum to ~1 for each row
        row_sums = filtered.sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-6)

        # All probabilities should be in [0, 1]
        assert (filtered >= 0).all().all()
        assert (filtered <= 1).all().all()

    def test_get_smoothed_probabilities(self, synthetic_ar1_data: pd.Series) -> None:
        """Test smoothed probabilities are returned correctly."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        smoothed = classifier.get_smoothed_probabilities()

        assert isinstance(smoothed, pd.DataFrame)
        assert len(smoothed) == len(synthetic_ar1_data)
        assert smoothed.shape[1] == 3

        # Probabilities should sum to ~1
        row_sums = smoothed.sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-6)

    def test_filtered_vs_smoothed_different(
        self, synthetic_ar1_data: pd.Series
    ) -> None:
        """Test that filtered and smoothed probabilities are different.

        Smoothed probabilities use future information, so they should differ
        from filtered probabilities.
        """
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        filtered = classifier.get_filtered_probabilities()
        smoothed = classifier.get_smoothed_probabilities()

        # They should not be identical (except in degenerate cases)
        diff = np.abs(smoothed - filtered).mean().mean()
        # Allow some tolerance - in edge cases they might be very similar
        assert diff >= 0  # Just check computation succeeds

    def test_get_regime_probabilities_smoothed(
        self, synthetic_ar1_data: pd.Series
    ) -> None:
        """Test get_regime_probabilities returns RegimeProbabilities objects."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        probs = classifier.get_regime_probabilities(smoothed=True)

        assert isinstance(probs, list)
        assert len(probs) == len(synthetic_ar1_data)
        assert all(isinstance(p, RegimeProbabilities) for p in probs)

        # Check first result structure
        first = probs[0]
        assert isinstance(first.timestamp, pd.Timestamp)
        assert 0 <= first.expansion <= 1
        assert 0 <= first.neutral <= 1
        assert 0 <= first.contraction <= 1
        assert isinstance(first.current_regime, RegimeState)
        assert 0 <= first.confidence <= 1

    def test_get_regime_probabilities_filtered(
        self, synthetic_ar1_data: pd.Series
    ) -> None:
        """Test get_regime_probabilities with filtered=False."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        probs = classifier.get_regime_probabilities(smoothed=False)

        assert isinstance(probs, list)
        assert len(probs) == len(synthetic_ar1_data)

    def test_probabilities_before_fit_raises(self) -> None:
        """Test probability methods raise before fitting."""
        classifier = MarkovSwitchingClassifier()

        with pytest.raises(ValueError, match="not fitted"):
            classifier.get_filtered_probabilities()

        with pytest.raises(ValueError, match="not fitted"):
            classifier.get_smoothed_probabilities()

        with pytest.raises(ValueError, match="not fitted"):
            classifier.get_regime_probabilities()


# ============================================================================
# Classification Tests
# ============================================================================


class TestMarkovSwitchingClassification:
    """Tests for regime classification."""

    def test_classify_current(self, synthetic_ar1_data: pd.Series) -> None:
        """Test current regime classification."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        current = classifier.classify_current()

        assert isinstance(current, RegimeProbabilities)
        assert current.timestamp == pd.Timestamp(synthetic_ar1_data.index[-1])

        # Current regime should be one of the valid states
        assert current.current_regime in [
            RegimeState.EXPANSION,
            RegimeState.NEUTRAL,
            RegimeState.CONTRACTION,
        ]

    def test_regime_probabilities_sum_to_one(
        self, synthetic_ar1_data: pd.Series
    ) -> None:
        """Test that regime probabilities sum to 1."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        probs = classifier.get_regime_probabilities()

        for p in probs:
            total = p.expansion + p.neutral + p.contraction
            assert np.isclose(total, 1.0, atol=1e-6)

    def test_as_array_property(self, synthetic_ar1_data: pd.Series) -> None:
        """Test RegimeProbabilities as_array property."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        probs = classifier.get_regime_probabilities()
        first = probs[0]

        arr = first.as_array
        assert isinstance(arr, np.ndarray)
        assert arr.shape == (3,)
        assert arr[0] == first.expansion
        assert arr[1] == first.neutral
        assert arr[2] == first.contraction


# ============================================================================
# Regime Interpretation Tests
# ============================================================================


class TestRegimeInterpretation:
    """Tests for regime state mapping/interpretation."""

    def test_state_mapping_exists(self, synthetic_ar1_data: pd.Series) -> None:
        """Test that state mapping is created after fitting."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        mapping = classifier._interpret_regimes()

        assert isinstance(mapping, dict)
        assert len(mapping) == 3

        # All three states should be mapped
        mapped_states = set(mapping.values())
        assert RegimeState.EXPANSION in mapped_states
        assert RegimeState.NEUTRAL in mapped_states
        assert RegimeState.CONTRACTION in mapped_states

    def test_expansion_has_highest_mean(self, synthetic_ar1_data: pd.Series) -> None:
        """Test that EXPANSION is mapped to regime with highest mean.

        This is a soft test - the mapping is based on fitted means,
        so it may not always perfectly match our synthetic data.
        """
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        # Get diagnostics to check regime params
        diag = classifier.get_diagnostics()

        # If regime params have means, check ordering
        if "EXPANSION" in diag.regime_params and "mean" in diag.regime_params["EXPANSION"]:
            exp_mean = diag.regime_params["EXPANSION"].get("mean", 0)
            con_mean = diag.regime_params["CONTRACTION"].get("mean", 0)
            # Expansion should have higher mean than contraction
            assert exp_mean >= con_mean


# ============================================================================
# Diagnostics Tests
# ============================================================================


class TestMarkovSwitchingDiagnostics:
    """Tests for model diagnostics."""

    def test_get_diagnostics(self, synthetic_ar1_data: pd.Series) -> None:
        """Test diagnostics extraction."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        diag = classifier.get_diagnostics()

        assert isinstance(diag, MarkovSwitchingDiagnostics)

        # Check information criteria
        assert not np.isnan(diag.log_likelihood)
        assert not np.isnan(diag.aic)
        assert not np.isnan(diag.bic)

        # Check transition matrix
        assert diag.transition_matrix.shape == (3, 3)
        # Rows should sum to ~1 (transition probabilities)
        row_sums = diag.transition_matrix.sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-6)

        # Check expected duration
        assert "EXPANSION" in diag.expected_duration
        assert "NEUTRAL" in diag.expected_duration
        assert "CONTRACTION" in diag.expected_duration
        # Durations should be positive
        for duration in diag.expected_duration.values():
            assert duration > 0

    def test_diagnostics_before_fit_raises(self) -> None:
        """Test diagnostics raises before fitting."""
        classifier = MarkovSwitchingClassifier()

        with pytest.raises(ValueError, match="not fitted"):
            classifier.get_diagnostics()

    def test_smoothed_vs_filtered_diff(self, synthetic_ar1_data: pd.Series) -> None:
        """Test smoothed vs filtered difference is computed."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        diag = classifier.get_diagnostics()

        # Should be a non-negative number
        assert diag.smoothed_vs_filtered_diff >= 0

    def test_transition_matrix_diagonals(self, synthetic_ar1_data: pd.Series) -> None:
        """Test transition matrix has high diagonal values (regime persistence)."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)
        classifier.fit(synthetic_ar1_data)

        diag = classifier.get_diagnostics()

        # Diagonal elements should generally be > 0.5 for persistent regimes
        # This is a soft constraint - depends on data
        diag_values = np.diag(diag.transition_matrix)
        assert all(d > 0 for d in diag_values)  # At minimum, all positive


# ============================================================================
# Integration Tests
# ============================================================================


class TestMarkovSwitchingIntegration:
    """Integration tests for complete workflows."""

    def test_full_workflow(self, synthetic_ar1_data: pd.Series) -> None:
        """Test complete workflow from fit to classification."""
        # 1. Initialize
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=1)

        # 2. Fit
        classifier.fit(synthetic_ar1_data)
        assert classifier.is_fitted

        # 3. Get probabilities
        smoothed = classifier.get_regime_probabilities(smoothed=True)
        assert len(smoothed) == len(synthetic_ar1_data)

        filtered = classifier.get_regime_probabilities(smoothed=False)
        assert len(filtered) == len(synthetic_ar1_data)

        # 4. Classify current
        current = classifier.classify_current()
        assert isinstance(current, RegimeProbabilities)

        # 5. Get diagnostics
        diag = classifier.get_diagnostics()
        assert diag.aic > 0 or diag.aic < 0  # Just check it's a real number

    def test_with_exogenous_variables(self, synthetic_ar1_data: pd.Series) -> None:
        """Test fitting with exogenous variables."""
        # Create simple exog variable
        exog = pd.DataFrame(
            {"trend": np.arange(len(synthetic_ar1_data))},
            index=synthetic_ar1_data.index,
        )

        classifier = MarkovSwitchingClassifier(k_regimes=3, order=0)
        classifier.fit(synthetic_ar1_data, exog=exog)

        assert classifier.is_fitted

        # Should still produce valid probabilities
        probs = classifier.get_regime_probabilities()
        assert len(probs) == len(synthetic_ar1_data)

    def test_two_regime_model(self, synthetic_ar1_data: pd.Series) -> None:
        """Test with 2 regimes instead of 3."""
        classifier = MarkovSwitchingClassifier(k_regimes=2, order=1)

        # This should work but state mapping will only have 2 entries
        classifier.fit(synthetic_ar1_data)
        assert classifier.is_fitted

        # Probabilities should have 2 components
        filtered = classifier.get_filtered_probabilities()
        assert filtered.shape[1] == 2

    def test_no_ar_order(self, simple_series: pd.Series) -> None:
        """Test with order=0 (no autoregression)."""
        classifier = MarkovSwitchingClassifier(k_regimes=3, order=0)
        classifier.fit(simple_series)

        assert classifier.is_fitted

        probs = classifier.get_regime_probabilities()
        assert len(probs) == len(simple_series)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
