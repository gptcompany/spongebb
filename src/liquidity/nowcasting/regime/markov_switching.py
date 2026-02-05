"""Markov Switching regression model using statsmodels.

Provides parameter-switching regime detection with Hamilton filter.

The Markov Switching model differs from HMM in that:
- Parameters (mean, variance, AR coefficients) switch between regimes
- Uses Maximum Likelihood Estimation (MLE) for fitting
- Provides both filtered (real-time) and smoothed (full-sample) probabilities
- Better suited for economic/financial time series with regime-dependent dynamics

Key components:
- MarkovSwitchingClassifier: Main classifier wrapper
- MarkovSwitchingDiagnostics: Model diagnostics dataclass
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

from .hmm_classifier import RegimeProbabilities, RegimeState

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from statsmodels.tsa.regime_switching.markov_regression import (
        MarkovRegressionResults,
    )

logger = logging.getLogger(__name__)


@dataclass
class MarkovSwitchingDiagnostics:
    """Diagnostics for Markov Switching model.

    Attributes:
        log_likelihood: Model log-likelihood.
        aic: Akaike Information Criterion.
        bic: Bayesian Information Criterion.
        transition_matrix: Regime transition probability matrix.
        regime_params: Mean and variance per regime.
        smoothed_vs_filtered_diff: Average difference between smoothed and
            filtered probabilities (indicates look-ahead benefit).
        expected_duration: Expected duration in each regime (in periods).
        converged: Whether MLE optimization converged.
    """

    log_likelihood: float
    aic: float
    bic: float
    transition_matrix: NDArray[np.float64]
    regime_params: dict[str, dict[str, float]]
    smoothed_vs_filtered_diff: float
    expected_duration: dict[str, float]
    converged: bool


class MarkovSwitchingClassifier:
    """Markov Switching regression for regime detection.

    Uses statsmodels MarkovRegression with:
    - Hamilton filter for filtered probabilities (real-time applicable)
    - Kim smoother for smoothed probabilities (better for historical analysis)
    - Parameter switching (mean/variance per regime)

    The model estimates:
    - Regime-specific means (intercepts)
    - Regime-specific variances (if switching_variance=True)
    - AR coefficients (if order > 0)
    - Transition probabilities between regimes

    Example:
        classifier = MarkovSwitchingClassifier(k_regimes=3)
        classifier.fit(net_liquidity_series)

        # Get smoothed probabilities (historical analysis)
        probs = classifier.get_regime_probabilities(smoothed=True)

        # Get filtered probabilities (real-time)
        probs_realtime = classifier.get_regime_probabilities(smoothed=False)

        # Current regime classification
        current = classifier.classify_current()
        print(f"Current regime: {current.current_regime.name}")
    """

    def __init__(
        self,
        k_regimes: int = 3,
        order: int = 1,
        switching_variance: bool = True,
        trend: str = "c",
    ) -> None:
        """Initialize Markov Switching classifier.

        Args:
            k_regimes: Number of regimes (default: 3 for expansion/neutral/contraction).
            order: AR order (default: 1). Set to 0 for no autoregression.
            switching_variance: Whether variance switches between regimes.
            trend: Trend specification. Options:
                - "n": No constant
                - "c": Constant (default)
                - "t": Linear trend
                - "ct": Constant and linear trend
        """
        self.k_regimes = k_regimes
        self.order = order
        self.switching_variance = switching_variance
        self.trend = trend

        self._model: MarkovRegression | None = None
        # Use Any for results as statsmodels types are imprecise
        self._results: Any = None
        self._is_fitted = False
        self._state_mapping: dict[int, RegimeState] = {}
        self._endog_index: pd.Index | None = None

    @property
    def is_fitted(self) -> bool:
        """Return whether model has been fitted."""
        return self._is_fitted

    def fit(
        self,
        endog: pd.Series,
        exog: pd.DataFrame | None = None,
    ) -> MarkovSwitchingClassifier:
        """Fit Markov Switching model.

        Args:
            endog: Endogenous variable (e.g., Net Liquidity returns or levels).
                Should be a pandas Series with DatetimeIndex.
            exog: Optional exogenous regressors as DataFrame.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If endog is empty or has insufficient data.
        """
        if endog.empty:
            raise ValueError("Cannot fit on empty series")

        min_obs = self.k_regimes * 20 + self.order
        if len(endog) < min_obs:
            raise ValueError(
                f"Insufficient data: {len(endog)} observations, "
                f"need at least {min_obs}"
            )

        # Store index for later use
        self._endog_index = endog.index

        # Handle NaN values
        endog_clean = endog.copy()
        if endog_clean.isna().any():
            logger.warning(
                "NaN values found in endog (%d/%d), forward-filling",
                endog_clean.isna().sum(),
                len(endog_clean),
            )
            endog_clean = endog_clean.ffill().bfill()

        # Prepare exogenous variables if provided
        exog_clean = None
        if exog is not None:
            exog_clean = exog.copy()
            if exog_clean.isna().values.any():  # type: ignore[union-attr]
                logger.warning("NaN values found in exog, forward-filling")
                exog_clean = exog_clean.ffill().bfill()

        # Initialize model
        self._model = MarkovRegression(
            endog=endog_clean,
            k_regimes=self.k_regimes,
            order=self.order,
            switching_variance=self.switching_variance,
            trend=self.trend,
            exog=exog_clean,
        )

        # Fit with MLE - suppress convergence warnings but log them
        assert self._model is not None, "Model not initialized"
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter("always")

            try:
                self._results = self._model.fit(disp=False, maxiter=500)
            except Exception as e:
                logger.error("Markov Switching fitting failed: %s", e)
                raise ValueError(f"Model fitting failed: {e}") from e

            # Log any convergence warnings
            for w in caught_warnings:
                if "converge" in str(w.message).lower():
                    logger.warning("Convergence warning: %s", w.message)

        self._is_fitted = True

        # Map states to regimes based on regime-specific means
        self._map_states_to_regimes()

        logger.info(
            "Markov Switching fitted: %d observations, %d regimes, order=%d",
            len(endog_clean),
            self.k_regimes,
            self.order,
        )

        return self

    def get_filtered_probabilities(self) -> pd.DataFrame:
        """Get filtered regime probabilities (using data up to t).

        Filtered probabilities use only information available up to time t,
        making them suitable for real-time applications.

        Returns:
            DataFrame with columns for each regime probability, indexed by time.

        Raises:
            ValueError: If model not fitted.
        """
        if not self._is_fitted or self._results is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Get filtered marginal probabilities
        # statsmodels returns a DataFrame with DatetimeIndex and integer columns
        filtered = self._results.filtered_marginal_probabilities

        # Rename columns for clarity
        if isinstance(filtered, pd.DataFrame):
            df = filtered.copy()
            df.columns = [f"regime_{i}" for i in range(self.k_regimes)]
        else:
            # Fallback for array output
            col_names = pd.Index([f"regime_{i}" for i in range(self.k_regimes)])
            df = pd.DataFrame(filtered, index=self._endog_index, columns=col_names)

        return df

    def get_smoothed_probabilities(self) -> pd.DataFrame:
        """Get smoothed regime probabilities (using all data).

        Smoothed probabilities use information from the entire sample,
        providing better estimates for historical analysis.

        Returns:
            DataFrame with columns for each regime probability, indexed by time.

        Raises:
            ValueError: If model not fitted.
        """
        if not self._is_fitted or self._results is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Get smoothed marginal probabilities
        # statsmodels returns a DataFrame with DatetimeIndex and integer columns
        smoothed = self._results.smoothed_marginal_probabilities

        # Rename columns for clarity
        if isinstance(smoothed, pd.DataFrame):
            df = smoothed.copy()
            df.columns = pd.Index([f"regime_{i}" for i in range(self.k_regimes)])
        else:
            # Fallback for array output
            col_names = pd.Index([f"regime_{i}" for i in range(self.k_regimes)])
            df = pd.DataFrame(smoothed, index=self._endog_index, columns=col_names)

        return df

    def get_regime_probabilities(
        self,
        smoothed: bool = True,
    ) -> list[RegimeProbabilities]:
        """Get regime probabilities compatible with ensemble.

        Args:
            smoothed: Use smoothed (True) or filtered (False) probabilities.

        Returns:
            List of RegimeProbabilities for each time step.

        Raises:
            ValueError: If model not fitted.
        """
        if not self._is_fitted or self._results is None:
            raise ValueError("Model not fitted. Call fit() first.")

        if smoothed:
            probs_df = self.get_smoothed_probabilities()
        else:
            probs_df = self.get_filtered_probabilities()

        results = []
        for timestamp, row in probs_df.iterrows():
            probs_array = cast("NDArray[np.float64]", np.asarray(row.values))
            ordered_probs = self._reorder_probs(probs_array)

            most_likely = RegimeState(int(np.argmax(ordered_probs)))

            # Cast timestamp to ensure type safety (iterrows returns Hashable)
            ts = pd.Timestamp(timestamp)  # type: ignore[arg-type]

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

    def classify_current(self) -> RegimeProbabilities:
        """Classify current regime using latest filtered probability.

        Uses filtered (not smoothed) probabilities for real-time applicability.

        Returns:
            RegimeProbabilities for the most recent time step.
        """
        probs = self.get_regime_probabilities(smoothed=False)
        return probs[-1]

    def get_diagnostics(self) -> MarkovSwitchingDiagnostics:
        """Get model diagnostics.

        Returns:
            MarkovSwitchingDiagnostics with model statistics.

        Raises:
            ValueError: If model not fitted.
        """
        if not self._is_fitted or self._results is None or self._model is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Extract transition matrix from model
        # statsmodels stores it column-stochastic, we need row-stochastic
        # Shape is (k, k, 1) for time-invariant models
        raw_transmat = self._model.regime_transition_matrix(self._results.params)
        if len(raw_transmat.shape) == 3:
            raw_transmat = raw_transmat.squeeze()

        # Transpose to get row-stochastic (rows sum to 1)
        transition_matrix = raw_transmat.T

        # Only reorder if we have 3 regimes (standard case)
        if self.k_regimes == 3 and len(self._state_mapping) == 3:
            reverse_mapping = {v: k for k, v in self._state_mapping.items()}
            reorder_idx = [
                reverse_mapping[RegimeState(i)] for i in range(self.k_regimes)
            ]
            transition_reordered = transition_matrix[np.ix_(reorder_idx, reorder_idx)]
        else:
            transition_reordered = transition_matrix

        # Extract regime-specific parameters
        regime_params = self._extract_regime_params()

        # Calculate smoothed vs filtered difference
        smoothed = self.get_smoothed_probabilities()
        filtered = self.get_filtered_probabilities()
        smoothed_vs_filtered_diff = float(np.abs(smoothed - filtered).mean().mean())

        # Calculate expected duration in each regime
        # E[duration] = 1 / (1 - p_ii) where p_ii is diagonal of transition matrix
        expected_duration: dict[str, float] = {}

        if self.k_regimes == 3 and len(self._state_mapping) == 3:
            regime_order = [RegimeState.EXPANSION, RegimeState.NEUTRAL, RegimeState.CONTRACTION]
            for i, regime in enumerate(regime_order):
                p_stay = float(transition_reordered[i, i])
                duration = 1 / (1 - p_stay) if p_stay < 1 else float("inf")
                expected_duration[regime.name] = duration
        else:
            # For non-standard regime counts
            for i in range(self.k_regimes):
                p_stay = float(transition_reordered[i, i])
                duration = 1 / (1 - p_stay) if p_stay < 1 else float("inf")
                expected_duration[f"regime_{i}"] = duration

        # Check convergence
        converged = True
        if hasattr(self._results, "mle_retvals") and self._results.mle_retvals is not None:
            converged = self._results.mle_retvals.get("converged", True)

        return MarkovSwitchingDiagnostics(
            log_likelihood=float(self._results.llf),
            aic=float(self._results.aic),
            bic=float(self._results.bic),
            transition_matrix=transition_reordered,
            regime_params=regime_params,
            smoothed_vs_filtered_diff=smoothed_vs_filtered_diff,
            expected_duration=expected_duration,
            converged=converged,
        )

    def _extract_regime_params(self) -> dict[str, dict[str, float]]:
        """Extract regime-specific parameters from fitted model.

        Returns:
            Dictionary mapping regime names to their parameters.
        """
        if self._results is None:
            return {}

        params = self._results.params
        regime_params: dict[str, dict[str, float]] = {}

        # Parameter names vary by model specification
        # For switching_variance with trend="c", we typically have:
        # - const[regime] for regime-specific intercepts
        # - sigma2[regime] for regime-specific variances

        reverse_mapping = {v: k for k, v in self._state_mapping.items()}

        # Only iterate over regimes that exist in the mapping
        for regime_state in [RegimeState.EXPANSION, RegimeState.NEUTRAL, RegimeState.CONTRACTION]:
            if regime_state not in reverse_mapping:
                continue  # Skip regimes not in the model (e.g., NEUTRAL for 2-regime)

            ms_state = reverse_mapping[regime_state]
            regime_name = regime_state.name

            regime_params[regime_name] = {}

            # Try to extract mean (constant/intercept)
            # Parameter naming convention varies
            const_key = f"const[{ms_state}]"
            if const_key in params.index:
                regime_params[regime_name]["mean"] = float(params[const_key])
            else:
                # Alternative: check for regime-specific means in summary
                # The first k_regimes params are often the regime means
                if ms_state < len(params):
                    regime_params[regime_name]["mean"] = float(params.iloc[ms_state])

            # Try to extract variance
            if self.switching_variance:
                sigma_key = f"sigma2[{ms_state}]"
                if sigma_key in params.index:
                    regime_params[regime_name]["variance"] = float(params[sigma_key])

        return regime_params

    def _map_states_to_regimes(self) -> None:
        """Map model regimes to economic interpretation.

        Uses regime-specific means: highest mean -> EXPANSION.

        For 3 regimes: EXPANSION (highest), NEUTRAL (middle), CONTRACTION (lowest)
        For 2 regimes: EXPANSION (highest), CONTRACTION (lowest)
        For other k: Uses generic mapping
        """
        if self._results is None:
            raise ValueError("Results not available")

        # Get regime-specific means
        # For MarkovRegression, we need to extract from parameters
        params = self._results.params

        means = []
        for state in range(self.k_regimes):
            # Try different parameter naming conventions
            const_key = f"const[{state}]"
            if const_key in params.index:
                mean = params[const_key]
            else:
                # Fall back to positional (first k params are often means)
                mean = params.iloc[state] if state < len(params) else 0.0
            means.append((state, float(mean)))

        # Sort by mean (descending)
        sorted_states = sorted(means, key=lambda x: x[1], reverse=True)

        # Map based on number of regimes
        if self.k_regimes == 3:
            # Standard 3-regime case
            self._state_mapping = {
                sorted_states[0][0]: RegimeState.EXPANSION,
                sorted_states[1][0]: RegimeState.NEUTRAL,
                sorted_states[2][0]: RegimeState.CONTRACTION,
            }
        elif self.k_regimes == 2:
            # 2-regime case: only expansion and contraction
            self._state_mapping = {
                sorted_states[0][0]: RegimeState.EXPANSION,
                sorted_states[1][0]: RegimeState.CONTRACTION,
            }
        else:
            # Generic case: map to expansion/contraction with neutrals in between
            self._state_mapping = {
                sorted_states[0][0]: RegimeState.EXPANSION,
                sorted_states[-1][0]: RegimeState.CONTRACTION,
            }
            for i in range(1, self.k_regimes - 1):
                self._state_mapping[sorted_states[i][0]] = RegimeState.NEUTRAL

        logger.debug("Markov Switching state mapping: %s", self._state_mapping)

    def _reorder_probs(self, probs: NDArray[np.float64]) -> NDArray[np.float64]:
        """Reorder probabilities to match [EXPANSION, NEUTRAL, CONTRACTION].

        Args:
            probs: Probabilities in model state order.

        Returns:
            Probabilities in RegimeState order (always length 3).
            For 2-regime models, NEUTRAL will be 0.
        """
        ordered = np.zeros(3)
        for ms_state, regime in self._state_mapping.items():
            if ms_state < len(probs):
                ordered[regime.value] = probs[ms_state]
        return ordered

    def _interpret_regimes(self) -> dict[int, RegimeState]:
        """Map model regimes to economic interpretation.

        Uses regime-specific means: highest mean -> EXPANSION.

        Returns:
            Dictionary mapping model states to RegimeState.
        """
        return self._state_mapping.copy()

    def __repr__(self) -> str:
        """Return string representation."""
        status = "fitted" if self._is_fitted else "not fitted"
        return (
            f"MarkovSwitchingClassifier(k_regimes={self.k_regimes}, "
            f"order={self.order}, status={status})"
        )
