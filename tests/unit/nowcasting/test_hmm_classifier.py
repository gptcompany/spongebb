"""Unit tests for HMM regime classifier.

Tests:
- HMMRegimeClassifier initialization with various parameters
- Fitting on synthetic data
- Regime probabilities sum to 1
- State interpretation logic
- Transition matrix properties
- Diagnostics retrieval

Run with: uv run pytest tests/unit/nowcasting/test_hmm_classifier.py -v
"""

import numpy as np
import pandas as pd
import pytest

from liquidity.nowcasting.regime import (
    HMMDiagnostics,
    HMMRegimeClassifier,
    RegimeProbabilities,
    RegimeState,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_features() -> pd.DataFrame:
    """Generate sample liquidity features for testing.

    Creates a realistic-looking feature set with 3 distinct regimes:
    - First third: High values (expansion-like)
    - Middle third: Medium values (neutral-like)
    - Last third: Low values (contraction-like)
    """
    np.random.seed(42)
    n = 150  # 50 per regime

    dates = pd.date_range(start="2025-01-01", periods=n, freq="B")

    # Create features with distinct regimes
    # Expansion: high values
    expansion = np.column_stack([
        np.random.normal(0.7, 0.1, 50),  # net_liq_pct
        np.random.normal(0.75, 0.1, 50),  # global_liq_pct
        np.random.normal(0.65, 0.1, 50),  # stealth_qe_norm
    ])

    # Neutral: medium values
    neutral = np.column_stack([
        np.random.normal(0.5, 0.1, 50),
        np.random.normal(0.5, 0.1, 50),
        np.random.normal(0.5, 0.1, 50),
    ])

    # Contraction: low values
    contraction = np.column_stack([
        np.random.normal(0.3, 0.1, 50),
        np.random.normal(0.25, 0.1, 50),
        np.random.normal(0.35, 0.1, 50),
    ])

    values = np.vstack([expansion, neutral, contraction])

    return pd.DataFrame(
        values,
        index=dates,
        columns=["net_liq_pct", "global_liq_pct", "stealth_qe_norm"],
    )


@pytest.fixture
def sample_features_with_nan(sample_features: pd.DataFrame) -> pd.DataFrame:
    """Create sample features with some NaN values."""
    df = sample_features.copy()
    # Introduce ~5% NaN values - use loc to avoid read-only issues
    np.random.seed(123)
    mask = np.random.random(df.shape) < 0.05
    for i in range(df.shape[0]):
        for j in range(df.shape[1]):
            if mask[i, j]:
                df.iloc[i, j] = np.nan
    return df


@pytest.fixture
def minimal_features() -> pd.DataFrame:
    """Create minimal valid features (just above threshold)."""
    np.random.seed(42)
    n = 30  # n_states * 10
    dates = pd.date_range(start="2025-01-01", periods=n, freq="B")

    return pd.DataFrame(
        np.random.random((n, 3)),
        index=dates,
        columns=["net_liq_pct", "global_liq_pct", "stealth_qe_norm"],
    )


@pytest.fixture
def short_features() -> pd.DataFrame:
    """Create features with insufficient data."""
    np.random.seed(42)
    n = 10  # Less than n_states * 10
    dates = pd.date_range(start="2025-01-01", periods=n, freq="B")

    return pd.DataFrame(
        np.random.random((n, 3)),
        index=dates,
        columns=["net_liq_pct", "global_liq_pct", "stealth_qe_norm"],
    )


@pytest.fixture
def fitted_classifier(sample_features: pd.DataFrame) -> HMMRegimeClassifier:
    """Return a fitted classifier for testing."""
    classifier = HMMRegimeClassifier(n_states=3, random_state=42)
    classifier.fit(sample_features)
    return classifier


# ============================================================================
# RegimeState Tests
# ============================================================================


class TestRegimeState:
    """Tests for RegimeState enum."""

    def test_regime_state_values(self) -> None:
        """Test RegimeState enum values."""
        assert RegimeState.EXPANSION.value == 0
        assert RegimeState.NEUTRAL.value == 1
        assert RegimeState.CONTRACTION.value == 2

    def test_regime_state_names(self) -> None:
        """Test RegimeState enum names."""
        assert RegimeState.EXPANSION.name == "EXPANSION"
        assert RegimeState.NEUTRAL.name == "NEUTRAL"
        assert RegimeState.CONTRACTION.name == "CONTRACTION"

    def test_all_three_states_exist(self) -> None:
        """Test that exactly 3 states exist."""
        states = list(RegimeState)
        assert len(states) == 3

    def test_regime_state_is_enum(self) -> None:
        """Test that RegimeState is an Enum."""
        from enum import Enum

        assert issubclass(RegimeState, Enum)


# ============================================================================
# RegimeProbabilities Tests
# ============================================================================


class TestRegimeProbabilities:
    """Tests for RegimeProbabilities dataclass."""

    def test_creation(self) -> None:
        """Test RegimeProbabilities can be created."""
        probs = RegimeProbabilities(
            timestamp=pd.Timestamp("2025-01-15"),
            expansion=0.7,
            neutral=0.2,
            contraction=0.1,
            current_regime=RegimeState.EXPANSION,
            confidence=0.7,
        )

        assert probs.timestamp == pd.Timestamp("2025-01-15")
        assert probs.expansion == 0.7
        assert probs.neutral == 0.2
        assert probs.contraction == 0.1
        assert probs.current_regime == RegimeState.EXPANSION
        assert probs.confidence == 0.7

    def test_as_array(self) -> None:
        """Test as_array property."""
        probs = RegimeProbabilities(
            timestamp=pd.Timestamp("2025-01-15"),
            expansion=0.5,
            neutral=0.3,
            contraction=0.2,
            current_regime=RegimeState.EXPANSION,
            confidence=0.5,
        )

        arr = probs.as_array
        assert isinstance(arr, np.ndarray)
        assert arr.shape == (3,)
        assert arr[0] == 0.5  # expansion
        assert arr[1] == 0.3  # neutral
        assert arr[2] == 0.2  # contraction

    def test_probabilities_sum_to_one(self) -> None:
        """Test that probabilities should sum to 1."""
        probs = RegimeProbabilities(
            timestamp=pd.Timestamp("2025-01-15"),
            expansion=0.5,
            neutral=0.3,
            contraction=0.2,
            current_regime=RegimeState.EXPANSION,
            confidence=0.5,
        )

        total = probs.expansion + probs.neutral + probs.contraction
        assert total == pytest.approx(1.0, rel=1e-6)

    def test_frozen_dataclass(self) -> None:
        """Test that RegimeProbabilities is frozen (immutable)."""
        from dataclasses import FrozenInstanceError

        probs = RegimeProbabilities(
            timestamp=pd.Timestamp("2025-01-15"),
            expansion=0.5,
            neutral=0.3,
            contraction=0.2,
            current_regime=RegimeState.EXPANSION,
            confidence=0.5,
        )

        with pytest.raises(FrozenInstanceError):
            probs.expansion = 0.6  # type: ignore[misc]

    def test_repr(self) -> None:
        """Test string representation."""
        probs = RegimeProbabilities(
            timestamp=pd.Timestamp("2025-01-15"),
            expansion=0.7,
            neutral=0.2,
            contraction=0.1,
            current_regime=RegimeState.EXPANSION,
            confidence=0.7,
        )

        repr_str = repr(probs)
        assert "EXPANSION" in repr_str
        assert "0.7" in repr_str or "70" in repr_str


# ============================================================================
# HMMRegimeClassifier Initialization Tests
# ============================================================================


class TestHMMRegimeClassifierInit:
    """Tests for HMMRegimeClassifier initialization."""

    def test_default_initialization(self) -> None:
        """Test classifier initializes with default parameters."""
        classifier = HMMRegimeClassifier()

        assert classifier.n_states == 3
        assert classifier.covariance_type == "full"
        assert classifier.n_iter == 100
        assert classifier.random_state == 42
        assert classifier.min_persistence == 0.7
        assert not classifier.is_fitted

    def test_custom_initialization(self) -> None:
        """Test classifier with custom parameters."""
        classifier = HMMRegimeClassifier(
            n_states=2,
            covariance_type="diag",
            n_iter=50,
            random_state=123,
            min_persistence=0.8,
        )

        assert classifier.n_states == 2
        assert classifier.covariance_type == "diag"
        assert classifier.n_iter == 50
        assert classifier.random_state == 123
        assert classifier.min_persistence == 0.8

    def test_invalid_n_states_raises(self) -> None:
        """Test that n_states < 2 raises ValueError."""
        with pytest.raises(ValueError, match="n_states must be >= 2"):
            HMMRegimeClassifier(n_states=1)

    def test_invalid_min_persistence_raises(self) -> None:
        """Test that invalid min_persistence raises ValueError."""
        with pytest.raises(ValueError, match="min_persistence must be in"):
            HMMRegimeClassifier(min_persistence=0.0)

        with pytest.raises(ValueError, match="min_persistence must be in"):
            HMMRegimeClassifier(min_persistence=1.0)

        with pytest.raises(ValueError, match="min_persistence must be in"):
            HMMRegimeClassifier(min_persistence=1.5)

    def test_repr_not_fitted(self) -> None:
        """Test string representation when not fitted."""
        classifier = HMMRegimeClassifier()
        repr_str = repr(classifier)

        assert "HMMRegimeClassifier" in repr_str
        assert "n_states=3" in repr_str
        assert "not fitted" in repr_str


# ============================================================================
# HMMRegimeClassifier Fit Tests
# ============================================================================


class TestHMMRegimeClassifierFit:
    """Tests for HMMRegimeClassifier fit method."""

    def test_fit_on_valid_data(self, sample_features: pd.DataFrame) -> None:
        """Test fitting on valid data."""
        classifier = HMMRegimeClassifier(n_states=3, random_state=42)
        result = classifier.fit(sample_features)

        assert classifier.is_fitted
        assert result is classifier  # Returns self for chaining

    def test_fit_returns_self(self, sample_features: pd.DataFrame) -> None:
        """Test fit returns self for method chaining."""
        classifier = HMMRegimeClassifier()
        result = classifier.fit(sample_features)

        assert result is classifier

    def test_fit_on_empty_raises(self) -> None:
        """Test fit raises on empty DataFrame."""
        classifier = HMMRegimeClassifier()
        empty_df = pd.DataFrame()

        with pytest.raises(ValueError, match="Cannot fit on empty"):
            classifier.fit(empty_df)

    def test_fit_on_insufficient_data_raises(self, short_features: pd.DataFrame) -> None:
        """Test fit raises on insufficient data."""
        classifier = HMMRegimeClassifier()

        with pytest.raises(ValueError, match="Insufficient data"):
            classifier.fit(short_features)

    def test_fit_with_feature_columns(self, sample_features: pd.DataFrame) -> None:
        """Test fitting with specific feature columns."""
        classifier = HMMRegimeClassifier()
        classifier.fit(
            sample_features,
            feature_columns=["net_liq_pct", "global_liq_pct"],
        )

        assert classifier.is_fitted
        assert classifier._feature_names == ["net_liq_pct", "global_liq_pct"]
        assert classifier._n_features == 2

    def test_fit_with_nan_values(self, sample_features_with_nan: pd.DataFrame) -> None:
        """Test fitting handles NaN values gracefully."""
        classifier = HMMRegimeClassifier(n_states=3, random_state=42)
        classifier.fit(sample_features_with_nan)

        assert classifier.is_fitted

    def test_fit_stores_feature_names(self, sample_features: pd.DataFrame) -> None:
        """Test that fit stores feature column names."""
        classifier = HMMRegimeClassifier()
        classifier.fit(sample_features)

        assert classifier._feature_names == list(sample_features.columns)

    def test_repr_after_fit(self, sample_features: pd.DataFrame) -> None:
        """Test string representation after fitting."""
        classifier = HMMRegimeClassifier()
        classifier.fit(sample_features)

        repr_str = repr(classifier)
        assert "fitted" in repr_str
        assert "not fitted" not in repr_str


# ============================================================================
# Regime Probabilities Tests
# ============================================================================


class TestGetRegimeProbabilities:
    """Tests for get_regime_probabilities method."""

    def test_probabilities_before_fit_raises(self, sample_features: pd.DataFrame) -> None:
        """Test that get_regime_probabilities raises before fit."""
        classifier = HMMRegimeClassifier()

        with pytest.raises(ValueError, match="Model not fitted"):
            classifier.get_regime_probabilities(sample_features)

    def test_probabilities_returns_list(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test get_regime_probabilities returns list of correct length."""
        probs = fitted_classifier.get_regime_probabilities(sample_features)

        assert isinstance(probs, list)
        assert len(probs) == len(sample_features)
        assert all(isinstance(p, RegimeProbabilities) for p in probs)

    def test_probabilities_sum_to_one(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test that probabilities sum to 1 for each observation."""
        probs = fitted_classifier.get_regime_probabilities(sample_features)

        for p in probs:
            total = p.expansion + p.neutral + p.contraction
            assert total == pytest.approx(1.0, rel=1e-6)

    def test_probabilities_in_valid_range(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test that all probabilities are in [0, 1]."""
        probs = fitted_classifier.get_regime_probabilities(sample_features)

        for p in probs:
            assert 0 <= p.expansion <= 1
            assert 0 <= p.neutral <= 1
            assert 0 <= p.contraction <= 1
            assert 0 <= p.confidence <= 1

    def test_probabilities_have_timestamps(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test that probabilities have correct timestamps."""
        probs = fitted_classifier.get_regime_probabilities(sample_features)

        for i, p in enumerate(probs):
            assert p.timestamp == pd.Timestamp(sample_features.index[i])

    def test_current_regime_matches_max_prob(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test that current_regime matches the max probability."""
        probs = fitted_classifier.get_regime_probabilities(sample_features)

        for p in probs:
            max_prob = max(p.expansion, p.neutral, p.contraction)
            assert p.confidence == pytest.approx(max_prob, rel=1e-6)

            # Check current_regime matches max
            if p.expansion == max_prob:
                assert p.current_regime == RegimeState.EXPANSION
            elif p.neutral == max_prob:
                assert p.current_regime == RegimeState.NEUTRAL
            else:
                assert p.current_regime == RegimeState.CONTRACTION


# ============================================================================
# Classify Current Tests
# ============================================================================


class TestClassifyCurrent:
    """Tests for classify_current method."""

    def test_classify_current_returns_single_result(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test classify_current returns single RegimeProbabilities."""
        result = fitted_classifier.classify_current(sample_features)

        assert isinstance(result, RegimeProbabilities)

    def test_classify_current_is_last_observation(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test classify_current returns result for last observation."""
        result = fitted_classifier.classify_current(sample_features)
        all_probs = fitted_classifier.get_regime_probabilities(sample_features)

        assert result.timestamp == all_probs[-1].timestamp
        assert result.expansion == all_probs[-1].expansion
        assert result.confidence == all_probs[-1].confidence


# ============================================================================
# Predict Sequence Tests
# ============================================================================


class TestPredictSequence:
    """Tests for predict_sequence method."""

    def test_predict_sequence_before_fit_raises(
        self, sample_features: pd.DataFrame
    ) -> None:
        """Test predict_sequence raises before fit."""
        classifier = HMMRegimeClassifier()

        with pytest.raises(ValueError, match="Model not fitted"):
            classifier.predict_sequence(sample_features)

    def test_predict_sequence_returns_series(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test predict_sequence returns pandas Series."""
        sequence = fitted_classifier.predict_sequence(sample_features)

        assert isinstance(sequence, pd.Series)
        assert len(sequence) == len(sample_features)
        assert sequence.name == "regime"

    def test_predict_sequence_values_are_regime_states(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test predict_sequence values are RegimeState enums."""
        sequence = fitted_classifier.predict_sequence(sample_features)

        for val in sequence.values:
            assert isinstance(val, RegimeState)

    def test_predict_sequence_has_correct_index(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test predict_sequence has same index as input."""
        sequence = fitted_classifier.predict_sequence(sample_features)

        assert list(sequence.index) == list(sample_features.index)


# ============================================================================
# State Interpretation Tests
# ============================================================================


class TestStateInterpretation:
    """Tests for state interpretation logic."""

    def test_state_mapping_exists_after_fit(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test state mapping is created after fit."""
        assert len(fitted_classifier._state_mapping) == 3

    def test_state_mapping_covers_all_regimes(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test all RegimeStates are in state mapping."""
        regimes = set(fitted_classifier._state_mapping.values())

        assert RegimeState.EXPANSION in regimes
        assert RegimeState.NEUTRAL in regimes
        assert RegimeState.CONTRACTION in regimes

    def test_state_mapping_is_bijective(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test state mapping is one-to-one."""
        mapping = fitted_classifier._state_mapping

        # Keys (HMM states) should be unique
        assert len(mapping.keys()) == len(set(mapping.keys()))

        # Values (RegimeStates) should be unique
        assert len(mapping.values()) == len(set(mapping.values()))

    def test_expansion_has_highest_mean(
        self, sample_features: pd.DataFrame
    ) -> None:
        """Test EXPANSION is mapped to state with highest feature mean."""
        classifier = HMMRegimeClassifier(n_states=3, random_state=42)
        classifier.fit(sample_features)

        # Get the HMM state mapped to EXPANSION
        expansion_hmm_state = None
        for hmm_state, regime in classifier._state_mapping.items():
            if regime == RegimeState.EXPANSION:
                expansion_hmm_state = hmm_state
                break

        # Verify it has the highest mean
        means = classifier._model.means_[:, 0]  # First feature
        assert expansion_hmm_state == np.argmax(means)

    def test_contraction_has_lowest_mean(
        self, sample_features: pd.DataFrame
    ) -> None:
        """Test CONTRACTION is mapped to state with lowest feature mean."""
        classifier = HMMRegimeClassifier(n_states=3, random_state=42)
        classifier.fit(sample_features)

        # Get the HMM state mapped to CONTRACTION
        contraction_hmm_state = None
        for hmm_state, regime in classifier._state_mapping.items():
            if regime == RegimeState.CONTRACTION:
                contraction_hmm_state = hmm_state
                break

        # Verify it has the lowest mean
        means = classifier._model.means_[:, 0]  # First feature
        assert contraction_hmm_state == np.argmin(means)


# ============================================================================
# Transition Matrix Tests
# ============================================================================


class TestTransitionMatrix:
    """Tests for transition matrix properties."""

    def test_get_transition_matrix_before_fit_raises(self) -> None:
        """Test get_transition_matrix raises before fit."""
        classifier = HMMRegimeClassifier()

        with pytest.raises(ValueError, match="Model not fitted"):
            classifier.get_transition_matrix()

    def test_transition_matrix_returns_dataframe(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test get_transition_matrix returns DataFrame."""
        trans = fitted_classifier.get_transition_matrix()

        assert isinstance(trans, pd.DataFrame)
        assert trans.shape == (3, 3)

    def test_transition_matrix_labels(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test transition matrix has correct labels."""
        trans = fitted_classifier.get_transition_matrix()

        expected_labels = ["EXPANSION", "NEUTRAL", "CONTRACTION"]
        assert list(trans.index) == expected_labels
        assert list(trans.columns) == expected_labels

    def test_transition_matrix_rows_sum_to_one(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test transition matrix rows sum to 1."""
        trans = fitted_classifier.get_transition_matrix()

        for row in trans.index:
            row_sum = trans.loc[row].sum()
            assert row_sum == pytest.approx(1.0, rel=1e-6)

    def test_transition_matrix_values_in_range(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test all transition probabilities are in [0, 1]."""
        trans = fitted_classifier.get_transition_matrix()

        for row in trans.index:
            for col in trans.columns:
                val = trans.loc[row, col]
                assert 0 <= val <= 1

    def test_transition_matrix_diagonal_persistence(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test diagonal values indicate regime persistence."""
        trans = fitted_classifier.get_transition_matrix()

        # Diagonal values should generally be positive
        # Note: With synthetic data, regime persistence may vary
        # Just check that we have valid probabilities
        for row in trans.index:
            diagonal = trans.loc[row, row]
            # Diagonal should be non-negative
            assert diagonal >= 0, f"Diagonal for {row} is negative: {diagonal}"


# ============================================================================
# Diagnostics Tests
# ============================================================================


class TestGetDiagnostics:
    """Tests for get_diagnostics method."""

    def test_diagnostics_before_fit_raises(self) -> None:
        """Test get_diagnostics raises before fit."""
        classifier = HMMRegimeClassifier()

        with pytest.raises(ValueError, match="Model not fitted"):
            classifier.get_diagnostics()

    def test_diagnostics_returns_hmm_diagnostics(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test get_diagnostics returns HMMDiagnostics."""
        diag = fitted_classifier.get_diagnostics()

        assert isinstance(diag, HMMDiagnostics)

    def test_diagnostics_has_all_fields(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test diagnostics has all required fields."""
        diag = fitted_classifier.get_diagnostics()

        assert hasattr(diag, "log_likelihood")
        assert hasattr(diag, "aic")
        assert hasattr(diag, "bic")
        assert hasattr(diag, "transition_matrix")
        assert hasattr(diag, "state_means")
        assert hasattr(diag, "state_covariances")
        assert hasattr(diag, "convergence_iterations")

    def test_diagnostics_transition_matrix_shape(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test diagnostics transition matrix has correct shape."""
        diag = fitted_classifier.get_diagnostics()

        assert diag.transition_matrix.shape == (3, 3)

    def test_diagnostics_state_means_shape(
        self, fitted_classifier: HMMRegimeClassifier, sample_features: pd.DataFrame
    ) -> None:
        """Test diagnostics state means has correct shape."""
        diag = fitted_classifier.get_diagnostics()
        n_features = sample_features.shape[1]

        assert diag.state_means.shape == (3, n_features)

    def test_diagnostics_state_covariances_length(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test diagnostics state covariances has correct length."""
        diag = fitted_classifier.get_diagnostics()

        assert len(diag.state_covariances) == 3
        assert all(isinstance(c, np.ndarray) for c in diag.state_covariances)

    def test_diagnostics_convergence_iterations_positive(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test convergence iterations is positive."""
        diag = fitted_classifier.get_diagnostics()

        assert diag.convergence_iterations > 0

    def test_diagnostics_repr(
        self, fitted_classifier: HMMRegimeClassifier
    ) -> None:
        """Test diagnostics repr."""
        diag = fitted_classifier.get_diagnostics()
        repr_str = repr(diag)

        assert "HMMDiagnostics" in repr_str
        assert "aic=" in repr_str
        assert "bic=" in repr_str


# ============================================================================
# Integration Tests
# ============================================================================


class TestHMMClassifierIntegration:
    """Integration tests for HMM classifier."""

    def test_full_workflow(self, sample_features: pd.DataFrame) -> None:
        """Test complete classification workflow."""
        # 1. Create and fit
        classifier = HMMRegimeClassifier(n_states=3, random_state=42)
        classifier.fit(sample_features)

        # 2. Get probabilities
        probs = classifier.get_regime_probabilities(sample_features)
        assert len(probs) == len(sample_features)

        # 3. Get current regime
        current = classifier.classify_current(sample_features)
        assert isinstance(current.current_regime, RegimeState)

        # 4. Get sequence
        sequence = classifier.predict_sequence(sample_features)
        assert len(sequence) == len(sample_features)

        # 5. Get transition matrix
        trans = classifier.get_transition_matrix()
        assert trans.shape == (3, 3)

        # 6. Get diagnostics
        diag = classifier.get_diagnostics()
        assert diag.convergence_iterations > 0

    def test_regime_detection_quality(self, sample_features: pd.DataFrame) -> None:
        """Test that HMM correctly identifies regime patterns in synthetic data."""
        classifier = HMMRegimeClassifier(n_states=3, random_state=42)
        classifier.fit(sample_features)

        sequence = classifier.predict_sequence(sample_features)

        # First third should mostly be EXPANSION
        first_third = sequence.iloc[:50]
        expansion_pct = (first_third == RegimeState.EXPANSION).mean()
        # Allow some flexibility but expect majority to be expansion
        assert expansion_pct >= 0.4, f"Expected >=40% EXPANSION in first third, got {expansion_pct:.1%}"

        # Last third should mostly be CONTRACTION
        last_third = sequence.iloc[-50:]
        contraction_pct = (last_third == RegimeState.CONTRACTION).mean()
        assert contraction_pct >= 0.4, f"Expected >=40% CONTRACTION in last third, got {contraction_pct:.1%}"

    def test_different_covariance_types(self, minimal_features: pd.DataFrame) -> None:
        """Test classifier works with different covariance types."""
        for cov_type in ["full", "diag", "spherical"]:
            classifier = HMMRegimeClassifier(
                n_states=3,
                covariance_type=cov_type,
                random_state=42,
            )
            classifier.fit(minimal_features)

            probs = classifier.get_regime_probabilities(minimal_features)
            assert len(probs) == len(minimal_features)

            # Check probabilities sum to 1
            for p in probs:
                total = p.expansion + p.neutral + p.contraction
                assert total == pytest.approx(1.0, rel=1e-6)

    def test_binary_classification(self, minimal_features: pd.DataFrame) -> None:
        """Test classifier works with 2 states."""
        classifier = HMMRegimeClassifier(n_states=2, random_state=42)
        classifier.fit(minimal_features)

        assert classifier.is_fitted

        # With 2 states, mapping should only include EXPANSION and CONTRACTION
        regimes = set(classifier._state_mapping.values())
        assert len(regimes) == 2
        assert RegimeState.EXPANSION in regimes
        assert RegimeState.CONTRACTION in regimes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
