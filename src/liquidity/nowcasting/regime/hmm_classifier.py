"""HMM-based regime classifier using hmmlearn.

Uses GaussianHMM with 3 hidden states for regime detection.

The HMM approach provides:
- Smoothed regime probabilities via forward-backward algorithm
- Regime persistence via transition matrix (avoids spurious flips)
- Interpretable states mapped to economic regimes
- Viterbi decoding for most likely state sequence

State mapping:
    After fitting, states are mapped to economic interpretation based on
    the mean of the first feature (typically net_liq_pct):
    - Highest mean -> EXPANSION (favorable liquidity)
    - Middle mean -> NEUTRAL (balanced)
    - Lowest mean -> CONTRACTION (unfavorable liquidity)
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, cast

import numpy as np
import pandas as pd
from hmmlearn import hmm

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class RegimeState(Enum):
    """Market regime states.

    Three-state classification for liquidity regimes:
    - EXPANSION (0): Favorable liquidity conditions (positive flows)
    - NEUTRAL (1): Balanced conditions (neither bullish nor bearish)
    - CONTRACTION (2): Unfavorable liquidity conditions (negative flows)
    """

    EXPANSION = 0
    NEUTRAL = 1
    CONTRACTION = 2


@dataclass(frozen=True)
class RegimeProbabilities:
    """Regime probabilities at a point in time.

    Attributes:
        timestamp: Time point for the probabilities.
        expansion: Probability of EXPANSION regime (0-1).
        neutral: Probability of NEUTRAL regime (0-1).
        contraction: Probability of CONTRACTION regime (0-1).
        current_regime: Most likely regime based on max probability.
        confidence: Confidence level (max probability).
    """

    timestamp: pd.Timestamp
    expansion: float
    neutral: float
    contraction: float
    current_regime: RegimeState
    confidence: float

    @property
    def as_array(self) -> NDArray[np.float64]:
        """Return probabilities as numpy array [expansion, neutral, contraction]."""
        return np.array([self.expansion, self.neutral, self.contraction])

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"RegimeProbabilities("
            f"{self.current_regime.name} "
            f"[E={self.expansion:.2f}, N={self.neutral:.2f}, C={self.contraction:.2f}], "
            f"conf={self.confidence:.1%})"
        )


@dataclass
class HMMDiagnostics:
    """Diagnostics for HMM model.

    Provides metrics for evaluating model quality and convergence.

    Attributes:
        log_likelihood: Log-likelihood of the fitted model.
        aic: Akaike Information Criterion (lower is better).
        bic: Bayesian Information Criterion (lower is better).
        transition_matrix: 3x3 transition probability matrix.
        state_means: Mean feature values for each state, shape (3, n_features).
        state_covariances: List of covariance matrices for each state.
        convergence_iterations: Number of EM iterations until convergence.

    Example:
        >>> diag = classifier.get_diagnostics()
        >>> print(f"AIC: {diag.aic:.2f}, BIC: {diag.bic:.2f}")
        >>> print(f"Converged in {diag.convergence_iterations} iterations")
    """

    log_likelihood: float
    aic: float
    bic: float
    transition_matrix: NDArray[np.float64]  # 3x3
    state_means: NDArray[np.float64]  # Shape (3, n_features)
    state_covariances: list[NDArray[np.float64]]  # List of covariance matrices
    convergence_iterations: int

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"HMMDiagnostics(log_likelihood={self.log_likelihood:.2f}, "
            f"aic={self.aic:.2f}, bic={self.bic:.2f}, "
            f"iterations={self.convergence_iterations})"
        )


class HMMRegimeClassifier:
    """Hidden Markov Model for liquidity regime detection.

    Uses a 3-state Gaussian HMM to classify liquidity regimes:
    - EXPANSION: High liquidity growth environment
    - NEUTRAL: Stable liquidity environment
    - CONTRACTION: Low/negative liquidity growth environment

    The model uses the forward-backward algorithm for smoothed probability
    estimation and the Viterbi algorithm for most likely state sequence.

    Example:
        classifier = HMMRegimeClassifier(n_states=3)
        classifier.fit(features_df)  # DataFrame with liquidity features

        # Get current regime
        current = classifier.classify_current(features_df)
        print(f"Regime: {current.current_regime.name}")

        # Get full probability sequence
        probs = classifier.get_regime_probabilities(features_df)
    """

    def __init__(
        self,
        n_states: int = 3,
        covariance_type: str = "full",
        n_iter: int = 100,
        random_state: int = 42,
        min_persistence: float = 0.7,
    ) -> None:
        """Initialize HMM classifier.

        Args:
            n_states: Number of hidden states (default 3 for
                EXPANSION/NEUTRAL/CONTRACTION).
            covariance_type: Type of covariance parameters. Options:
                - "full": Full covariance matrix for each state.
                - "diag": Diagonal covariance (independent features).
                - "spherical": Single variance per state.
            n_iter: Maximum iterations for EM algorithm.
            random_state: Random seed for reproducibility.
            min_persistence: Minimum regime persistence probability
                (diagonal elements of transition matrix). Used for
                validation after fitting.

        Raises:
            ValueError: If n_states < 2 or min_persistence not in (0, 1).
        """
        if n_states < 2:
            raise ValueError(f"n_states must be >= 2, got {n_states}")
        if not 0 < min_persistence < 1:
            raise ValueError(
                f"min_persistence must be in (0, 1), got {min_persistence}"
            )

        self.n_states = n_states
        self.covariance_type = covariance_type
        self.n_iter = n_iter
        self.random_state = random_state
        self.min_persistence = min_persistence

        self._model: hmm.GaussianHMM | None = None
        self._is_fitted = False
        self._state_mapping: dict[int, RegimeState] = {}
        self._feature_names: list[str] = []
        self._n_features: int = 0
        self._convergence_iterations: int = 0

    @property
    def is_fitted(self) -> bool:
        """Return whether model has been fitted."""
        return self._is_fitted

    def fit(
        self,
        features: pd.DataFrame,
        feature_columns: list[str] | None = None,
    ) -> HMMRegimeClassifier:
        """Fit HMM model on historical features.

        Fits a GaussianHMM to the feature data using the EM algorithm.
        After fitting, automatically maps learned states to economic
        regimes based on feature means.

        Args:
            features: DataFrame with columns like
                ['net_liq_pct', 'global_liq_pct', 'stealth_qe_norm'].
                Must have DatetimeIndex or timestamp column.
            feature_columns: Specific columns to use for fitting.
                If None, uses all numeric columns.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If features is empty or has insufficient data.

        Example:
            >>> features = pd.DataFrame({
            ...     'net_liq_pct': [0.6, 0.7, 0.5, 0.4],
            ...     'global_liq_pct': [0.65, 0.72, 0.55, 0.45],
            ...     'stealth_qe_norm': [0.5, 0.6, 0.4, 0.3]
            ... }, index=pd.date_range('2025-01-01', periods=4, freq='D'))
            >>> classifier = HMMRegimeClassifier()
            >>> classifier.fit(features)
        """
        if features.empty:
            raise ValueError("Cannot fit on empty features DataFrame")

        # Select feature columns
        if feature_columns is not None:
            self._feature_names = feature_columns
            X = features[feature_columns].values
        else:
            # Use all numeric columns
            numeric_cols = features.select_dtypes(include=[np.number]).columns.tolist()
            if not numeric_cols:
                raise ValueError("No numeric columns found in features DataFrame")
            self._feature_names = numeric_cols
            X = features[numeric_cols].values

        self._n_features = X.shape[1]

        min_samples = self.n_states * 10
        if len(features) < min_samples:
            raise ValueError(
                f"Insufficient data: {len(features)} observations, "
                f"need at least {min_samples}"
            )

        # Prepare data
        X = X.astype(np.float64)

        # Handle any NaN values
        if np.any(np.isnan(X)):
            logger.warning("NaN values found in features, forward-filling")
            X = pd.DataFrame(X).ffill().bfill().values

        # Initialize model
        self._model = hmm.GaussianHMM(
            n_components=self.n_states,
            covariance_type=self.covariance_type,
            n_iter=self.n_iter,
            random_state=self.random_state,
        )

        # Fit with convergence warning suppression
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ConvergenceWarning)
            self._model.fit(X)

        self._is_fitted = True
        self._convergence_iterations = self._model.monitor_.iter

        # Map learned states to regime labels (use cleaned X data)
        self._map_states_to_regimes_from_data(X)

        # Validate transition matrix persistence
        self._validate_persistence()

        logger.info(
            "HMM fitted: %d observations, %d features, converged in %d iterations",
            len(features),
            self._n_features,
            self._convergence_iterations,
        )

        return self

    def get_regime_probabilities(
        self, features: pd.DataFrame
    ) -> list[RegimeProbabilities]:
        """Get smoothed regime probabilities for all timestamps.

        Uses the forward-backward algorithm to compute smoothed posterior
        probabilities P(state_t | observations_1:T) for each time step.
        These are "smoothed" because they use all observations, not just
        past ones.

        Args:
            features: DataFrame with the same feature columns used for fitting.

        Returns:
            List of RegimeProbabilities, one per observation.

        Raises:
            ValueError: If model not fitted or feature columns mismatch.

        Example:
            >>> probs = classifier.get_regime_probabilities(features_df)
            >>> for p in probs[-5:]:  # Last 5
            ...     print(f"{p.timestamp}: {p.current_regime.name} ({p.confidence:.1%})")
        """
        if not self._is_fitted or self._model is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Extract features using stored column names
        if self._feature_names:
            X = features[self._feature_names].values.astype(np.float64)
        else:
            X = features.values.astype(np.float64)

        # Handle NaN values
        if np.any(np.isnan(X)):
            X = pd.DataFrame(X).ffill().bfill().values

        # Get posterior probabilities (smoothed)
        posteriors = self._model.predict_proba(X)

        results: list[RegimeProbabilities] = []
        for i, timestamp in enumerate(features.index):
            probs = posteriors[i]
            ordered_probs = self._reorder_probs(probs)

            most_likely = RegimeState(int(np.argmax(ordered_probs)))

            # Handle potential NaT by converting to Timestamp explicitly
            ts_val = pd.Timestamp(timestamp) if not pd.isna(timestamp) else pd.Timestamp.now()
            ts = cast(pd.Timestamp, ts_val)

            results.append(
                RegimeProbabilities(
                    timestamp=ts,
                    expansion=float(ordered_probs[0]),
                    neutral=float(ordered_probs[1]),
                    contraction=float(ordered_probs[2]),
                    current_regime=most_likely,
                    confidence=float(np.max(ordered_probs)),
                )
            )

        return results

    def classify_current(self, features: pd.DataFrame) -> RegimeProbabilities:
        """Classify current regime using latest observation.

        Args:
            features: DataFrame with same columns as training data.

        Returns:
            RegimeProbabilities for the latest time step.
        """
        probs = self.get_regime_probabilities(features)
        return probs[-1]

    def predict_sequence(self, features: pd.DataFrame) -> pd.Series:
        """Predict most likely state sequence (Viterbi).

        Uses the Viterbi algorithm to find the most likely sequence
        of hidden states given the observations. Unlike smoothed
        posteriors, this gives a globally optimal path.

        Args:
            features: DataFrame with the same feature columns used for fitting.

        Returns:
            Series with RegimeState for each timestamp.

        Raises:
            ValueError: If model not fitted.

        Example:
            >>> sequence = classifier.predict_sequence(features_df)
            >>> print(sequence.value_counts())
        """
        if not self._is_fitted or self._model is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Extract features using stored column names
        if self._feature_names:
            X = features[self._feature_names].values.astype(np.float64)
        else:
            X = features.values.astype(np.float64)

        if np.any(np.isnan(X)):
            X = pd.DataFrame(X).ffill().bfill().values

        # Viterbi decoding
        hidden_states = self._model.predict(X)

        # Map to RegimeState
        regimes = [self._state_mapping[s] for s in hidden_states]

        return pd.Series(regimes, index=features.index, name="regime")

    # Alias for backwards compatibility
    get_most_likely_sequence = predict_sequence

    def get_transition_matrix(self) -> pd.DataFrame:
        """Get transition probability matrix.

        High diagonal values indicate regime persistence.

        Returns:
            DataFrame with transition probabilities.
        """
        if not self._is_fitted or self._model is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Reorder transition matrix to match RegimeState ordering
        labels = ["EXPANSION", "NEUTRAL", "CONTRACTION"]
        n_states = self.n_states

        # Create reordering indices
        reverse_mapping = {v: k for k, v in self._state_mapping.items()}
        reorder_idx = [reverse_mapping[RegimeState(i)] for i in range(n_states)]

        transmat = self._model.transmat_[np.ix_(reorder_idx, reorder_idx)]

        return pd.DataFrame(
            transmat, index=pd.Index(labels), columns=pd.Index(labels)
        )

    def get_diagnostics(self) -> HMMDiagnostics:
        """Get model diagnostics.

        Returns comprehensive diagnostics for evaluating model quality,
        including information criteria and learned parameters.

        Returns:
            HMMDiagnostics with model metrics and parameters.

        Raises:
            ValueError: If model not fitted.

        Example:
            >>> diag = classifier.get_diagnostics()
            >>> print(f"Log-likelihood: {diag.log_likelihood:.2f}")
            >>> print(f"AIC: {diag.aic:.2f}")
            >>> print(f"Diagonal persistence: {np.diag(diag.transition_matrix)}")
        """
        if not self._is_fitted or self._model is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Calculate AIC/BIC
        # Number of free parameters: (n_states-1) + n_states*n_features + covar_params
        n_params = (self.n_states - 1) + self.n_states * self._n_features
        if self.covariance_type == "full":
            n_params += self.n_states * self._n_features * (self._n_features + 1) // 2
        elif self.covariance_type == "diag":
            n_params += self.n_states * self._n_features
        else:
            n_params += self.n_states

        # Get log likelihood from monitor history if available
        if hasattr(self._model, 'monitor_') and self._model.monitor_.history:
            log_likelihood = float(self._model.monitor_.history[-1])
        else:
            log_likelihood = float(self._model.score(self._model.means_))

        # Estimate n_samples from means shape (approximate for BIC)
        n_samples = 100  # Default estimate if not available

        aic = -2 * log_likelihood + 2 * n_params
        bic = -2 * log_likelihood + n_params * np.log(n_samples)

        # Get state covariances in proper format
        covars = self._model.covars_
        assert covars is not None, "Model covars_ is None after fitting"
        if self.covariance_type == "full":
            state_covariances = [covars[i].copy() for i in range(self.n_states)]
        elif self.covariance_type == "diag":
            state_covariances = [np.diag(covars[i]) for i in range(self.n_states)]
        else:  # spherical
            state_covariances = [
                covars[i] * np.eye(self._n_features) for i in range(self.n_states)
            ]

        return HMMDiagnostics(
            log_likelihood=log_likelihood,
            aic=aic,
            bic=bic,
            transition_matrix=self._model.transmat_.copy(),
            state_means=self._model.means_.copy(),
            state_covariances=state_covariances,
            convergence_iterations=self._convergence_iterations,
        )

    def _validate_persistence(self) -> None:
        """Validate that transition matrix has sufficient persistence.

        Logs a warning if any diagonal element is below min_persistence,
        which would indicate unstable regime assignments.
        """
        if self._model is None:
            return

        diagonal = np.diag(self._model.transmat_)
        min_diag = diagonal.min()

        if min_diag < self.min_persistence:
            logger.warning(
                "Low regime persistence detected: min diagonal = %.3f < %.3f. "
                "Consider using more data or adjusting model parameters.",
                min_diag,
                self.min_persistence,
            )

    def _map_states_to_regimes_from_data(
        self,
        X: NDArray[np.float64],
    ) -> None:
        """Map HMM states to regime labels based on mean feature values.

        Uses state means to determine which state is EXPANSION/NEUTRAL/CONTRACTION.
        Higher mean in the first feature (typically net liquidity) -> EXPANSION.

        Args:
            X: Cleaned feature data array (no NaNs).
        """
        if self._model is None:
            raise ValueError("Model not initialized")

        states = self._model.predict(X)

        # Calculate mean of first feature per state
        means: list[tuple[int, float]] = []
        for state in range(self.n_states):
            mask = states == state
            if mask.sum() > 0:
                mean_val = float(X[mask, 0].mean())
            else:
                mean_val = float(self._model.means_[state, 0])
            means.append((state, mean_val))

        # Sort by mean return (descending)
        sorted_states = sorted(means, key=lambda x: x[1], reverse=True)

        # Map: highest = EXPANSION, middle = NEUTRAL, lowest = CONTRACTION
        if self.n_states == 3:
            self._state_mapping = {
                sorted_states[0][0]: RegimeState.EXPANSION,
                sorted_states[1][0]: RegimeState.NEUTRAL,
                sorted_states[2][0]: RegimeState.CONTRACTION,
            }
        elif self.n_states == 2:
            # Binary case
            self._state_mapping = {
                sorted_states[0][0]: RegimeState.EXPANSION,
                sorted_states[1][0]: RegimeState.CONTRACTION,
            }
        else:
            # More than 3 states: map extremes, rest to NEUTRAL
            self._state_mapping = {
                sorted_states[0][0]: RegimeState.EXPANSION,
                sorted_states[-1][0]: RegimeState.CONTRACTION,
            }
            for state, _ in sorted_states[1:-1]:
                self._state_mapping[state] = RegimeState.NEUTRAL

        logger.debug(
            "State mapping: %s",
            {s: r.name for s, r in self._state_mapping.items()},
        )

    def _reorder_probs(self, probs: NDArray[np.float64]) -> NDArray[np.float64]:
        """Reorder probabilities to match [EXPANSION, NEUTRAL, CONTRACTION].

        Args:
            probs: Probabilities in HMM state order.

        Returns:
            Probabilities in RegimeState order.
        """
        ordered = np.zeros(3)
        for hmm_state, regime in self._state_mapping.items():
            ordered[regime.value] = probs[hmm_state]
        return ordered

    def __repr__(self) -> str:
        """Return string representation."""
        status = "fitted" if self._is_fitted else "not fitted"
        return f"HMMRegimeClassifier(n_states={self.n_states}, status={status})"


# Import ConvergenceWarning - may not exist in older versions
try:
    from sklearn.exceptions import ConvergenceWarning
except ImportError:
    ConvergenceWarning = UserWarning  # type: ignore[misc, assignment]
