"""Regime-Conditional VaR Calculator."""

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from .cvar import ExpectedShortfall
from .var.historical import HistoricalVaR


class RegimeType(str, Enum):
    """Liquidity regime types."""

    EXPANSION = "EXPANSION"
    NEUTRAL = "NEUTRAL"
    CONTRACTION = "CONTRACTION"


@dataclass
class RegimeVaRResult:
    """VaR result conditioned on regime."""

    current_regime: RegimeType
    regime_probability: float
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    observation_count: int


@dataclass
class WeightedVaRResult:
    """Probability-weighted VaR across regimes."""

    weighted_var_95: float
    weighted_var_99: float
    weighted_cvar_95: float
    weighted_cvar_99: float
    regime_vars: dict[RegimeType, RegimeVaRResult]
    current_regime: RegimeType
    current_probability: float


class RegimeConditionalVaR:
    """VaR calculator conditioned on liquidity regime.

    Segments historical returns by regime and computes
    regime-specific VaR. Also provides probability-weighted
    VaR using regime forecasts.

    Example:
        >>> calc = RegimeConditionalVaR()
        >>> results = calc.calculate_by_regime(returns, regime_series)
        >>> print(f"Contraction VaR: {results[RegimeType.CONTRACTION].var_95:.2%}")
    """

    def __init__(
        self,
        window: int = 252,
        min_observations: int = 30,
    ) -> None:
        """Initialize calculator.

        Args:
            window: Observation window
            min_observations: Minimum obs per regime for VaR
        """
        self.window = window
        self.min_observations = min_observations
        self.var_calc = HistoricalVaR(window=window)
        self.cvar_calc = ExpectedShortfall(window=window)

    def segment_by_regime(
        self,
        returns: pd.Series,
        regime_series: pd.Series,
    ) -> dict[RegimeType, pd.Series]:
        """Segment returns by regime.

        Args:
            returns: Series of returns
            regime_series: Series of regime labels

        Returns:
            Dict mapping regime to returns subset
        """
        aligned = pd.concat([returns, regime_series], axis=1, join="inner")
        aligned.columns = pd.Index(["returns", "regime"])

        segments: dict[RegimeType, pd.Series] = {}
        for regime in RegimeType:
            mask = aligned["regime"] == regime.value
            regime_returns = aligned.loc[mask, "returns"]
            if len(regime_returns) >= self.min_observations:
                segments[regime] = regime_returns

        return segments

    def calculate_by_regime(
        self,
        returns: pd.Series,
        regime_series: pd.Series,
    ) -> dict[RegimeType, RegimeVaRResult]:
        """Calculate VaR for each regime.

        Args:
            returns: Series of returns
            regime_series: Series of regime labels

        Returns:
            Dict mapping regime to VaRResult
        """
        segments = self.segment_by_regime(returns, regime_series)
        results: dict[RegimeType, RegimeVaRResult] = {}

        total_obs = len(returns)

        for regime, regime_returns in segments.items():
            var_result = self.var_calc.calculate(regime_returns)
            cvar_result = self.cvar_calc.calculate_historical(regime_returns)

            regime_prob = len(regime_returns) / total_obs if total_obs > 0 else 0.0

            results[regime] = RegimeVaRResult(
                current_regime=regime,
                regime_probability=regime_prob,
                var_95=var_result.var_95,
                var_99=var_result.var_99,
                cvar_95=cvar_result.cvar_95,
                cvar_99=cvar_result.cvar_99,
                observation_count=len(regime_returns),
            )

        return results

    def calculate_weighted(
        self,
        returns: pd.Series,
        regime_series: pd.Series,
        regime_probabilities: dict[RegimeType, float] | None = None,
        current_regime: RegimeType | None = None,
    ) -> WeightedVaRResult:
        """Calculate probability-weighted VaR.

        Args:
            returns: Series of returns
            regime_series: Historical regime series
            regime_probabilities: Optional current regime probs (from forecast)
            current_regime: Optional current regime state

        Returns:
            WeightedVaRResult with combined VaR
        """
        regime_vars = self.calculate_by_regime(returns, regime_series)

        # Use provided probabilities or historical frequencies
        if regime_probabilities is None:
            regime_probabilities = {
                r: result.regime_probability for r, result in regime_vars.items()
            }

        # Normalize probabilities
        total_prob = sum(regime_probabilities.values())
        if total_prob > 0:
            regime_probabilities = {r: p / total_prob for r, p in regime_probabilities.items()}

        # Weighted VaR
        weighted_var_95 = 0.0
        weighted_var_99 = 0.0
        weighted_cvar_95 = 0.0
        weighted_cvar_99 = 0.0

        for regime, result in regime_vars.items():
            prob = regime_probabilities.get(regime, 0.0)
            weighted_var_95 += prob * result.var_95
            weighted_var_99 += prob * result.var_99
            weighted_cvar_95 += prob * result.cvar_95
            weighted_cvar_99 += prob * result.cvar_99

        # Determine current regime
        if current_regime is None and regime_probabilities:
            current_regime = max(regime_probabilities.items(), key=lambda x: x[1])[0]
        elif current_regime is None:
            current_regime = RegimeType.NEUTRAL

        return WeightedVaRResult(
            weighted_var_95=weighted_var_95,
            weighted_var_99=weighted_var_99,
            weighted_cvar_95=weighted_cvar_95,
            weighted_cvar_99=weighted_cvar_99,
            regime_vars=regime_vars,
            current_regime=current_regime,
            current_probability=regime_probabilities.get(current_regime, 0.0),
        )


# Regime risk multipliers (from empirical research)
REGIME_RISK_MULTIPLIERS: dict[RegimeType, float] = {
    RegimeType.EXPANSION: 0.8,
    RegimeType.NEUTRAL: 1.0,
    RegimeType.CONTRACTION: 1.5,
}
