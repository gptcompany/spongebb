"""Composite Volatility Signal calculator.

Combines MOVE Z-Score and VIX Term Structure into a unified
volatility signal for liquidity regime analysis:
- MOVE Z-Score: bond market stress (40% weight)
- VIX Term Structure: equity vol curve shape (40% weight)
- VIX level: absolute equity volatility (20% weight)

Signal range: -100 (extreme stress) to +100 (extreme calm).
Inspired by Apps Script v3.4.1 volatility signal generation.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from liquidity.calculators.move_zscore import (
    MOVESignal,
    MOVEZScoreCalculator,
    MOVEZScoreResult,
)
from liquidity.calculators.vix_term_structure import (
    TermStructure,
    VIXTermStructureCalculator,
    VIXTermStructureResult,
)
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Component weights for composite score
WEIGHT_MOVE_ZSCORE = 0.40
WEIGHT_VIX_TERM = 0.40
WEIGHT_VIX_LEVEL = 0.20

# VIX level thresholds for scoring
VIX_LOW = 15.0  # Below = calm
VIX_NEUTRAL = 20.0  # 15-20 = normal
VIX_HIGH = 25.0  # 20-25 = elevated
VIX_EXTREME = 30.0  # Above 30 = high stress


class VolatilityRegime(str, Enum):
    """Composite volatility regime classification."""

    RISK_ON = "RISK_ON"  # Score > 30: favorable for risk assets
    NEUTRAL = "NEUTRAL"  # -30 <= score <= 30: mixed signals
    RISK_OFF = "RISK_OFF"  # Score < -30: stress, reduce exposure


# Regime thresholds
REGIME_RISK_ON = 30.0
REGIME_RISK_OFF = -30.0


@dataclass
class VolatilitySignalResult:
    """Result of composite volatility signal.

    Attributes:
        timestamp: Timestamp of the calculation (UTC).
        composite_score: Combined score (-100 to +100).
        regime: Volatility regime classification.
        move_zscore: MOVE Z-Score component result.
        vix_term: VIX term structure component result.
        move_component: MOVE contribution to score.
        term_component: VIX term structure contribution to score.
        level_component: VIX level contribution to score.
    """

    timestamp: datetime
    composite_score: float
    regime: VolatilityRegime
    move_zscore: MOVEZScoreResult
    vix_term: VIXTermStructureResult
    move_component: float
    term_component: float
    level_component: float


def _score_move_zscore(move: MOVEZScoreResult) -> float:
    """Score MOVE Z-Score from -100 (stress) to +100 (calm).

    Inverted: high MOVE Z-Score = stress = negative score.
    """
    signal_scores = {
        MOVESignal.EXTREME_LOW: 100.0,
        MOVESignal.LOW: 50.0,
        MOVESignal.NORMAL: 0.0,
        MOVESignal.HIGH: -50.0,
        MOVESignal.EXTREME_HIGH: -100.0,
    }
    base = signal_scores[move.signal]
    # Fine-tune within signal band using actual Z-Score
    adjustment = max(-25.0, min(25.0, -move.zscore * 10))
    return max(-100.0, min(100.0, base + adjustment))


def _score_vix_term(vix: VIXTermStructureResult) -> float:
    """Score VIX term structure from -100 (backwardation) to +100 (contango)."""
    structure_scores = {
        TermStructure.CONTANGO: 80.0,
        TermStructure.FLAT: 0.0,
        TermStructure.BACKWARDATION: -80.0,
    }
    base = structure_scores[vix.structure]
    # Fine-tune using actual ratio distance from 1.0
    deviation = 1.0 - vix.ratio  # positive = contango, negative = backwardation
    adjustment = max(-20.0, min(20.0, deviation * 100))
    return max(-100.0, min(100.0, base + adjustment))


def _score_vix_level(vix_value: float) -> float:
    """Score VIX level from -100 (high vol) to +100 (low vol)."""
    if vix_value < VIX_LOW:
        return 100.0
    if vix_value < VIX_NEUTRAL:
        return 50.0 * (VIX_NEUTRAL - vix_value) / (VIX_NEUTRAL - VIX_LOW)
    if vix_value < VIX_HIGH:
        return -50.0 * (vix_value - VIX_NEUTRAL) / (VIX_HIGH - VIX_NEUTRAL)
    if vix_value < VIX_EXTREME:
        return -50.0 - 50.0 * (vix_value - VIX_HIGH) / (VIX_EXTREME - VIX_HIGH)
    return -100.0


def classify_regime(score: float) -> VolatilityRegime:
    """Classify composite score into volatility regime."""
    if score > REGIME_RISK_ON:
        return VolatilityRegime.RISK_ON
    if score < REGIME_RISK_OFF:
        return VolatilityRegime.RISK_OFF
    return VolatilityRegime.NEUTRAL


class VolatilitySignalCalculator:
    """Calculate composite volatility signal from MOVE + VIX.

    Combines bond and equity volatility indicators into a single
    signal for liquidity regime analysis and trading filters.

    Example:
        calculator = VolatilitySignalCalculator()
        result = await calculator.get_current()
        print(f"Score: {result.composite_score:.1f} ({result.regime.value})")
        print(f"MOVE: {result.move_zscore.signal.value}")
        print(f"VIX: {result.vix_term.structure.value}")
    """

    def __init__(
        self,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize composite volatility calculator.

        Args:
            settings: Optional settings override.
            **kwargs: Additional arguments passed to sub-calculators.
        """
        self._settings = settings or get_settings()
        self._move_calc = MOVEZScoreCalculator(settings=self._settings, **kwargs)
        self._vix_calc = VIXTermStructureCalculator(settings=self._settings, **kwargs)

    async def get_current(self) -> VolatilitySignalResult:
        """Get current composite volatility signal.

        Returns:
            VolatilitySignalResult with composite score and component details.

        Raises:
            ValueError: If insufficient data for calculation.
        """
        # Fetch both components
        move_result = await self._move_calc.get_current()
        vix_result = await self._vix_calc.get_current()

        # Score each component
        move_score = _score_move_zscore(move_result)
        term_score = _score_vix_term(vix_result)
        level_score = _score_vix_level(vix_result.vix)

        # Weighted composite
        composite = (
            WEIGHT_MOVE_ZSCORE * move_score
            + WEIGHT_VIX_TERM * term_score
            + WEIGHT_VIX_LEVEL * level_score
        )

        regime = classify_regime(composite)

        logger.info(
            "Volatility signal: %.1f (%s) [MOVE=%.1f, Term=%.1f, Level=%.1f]",
            composite,
            regime.value,
            move_score,
            term_score,
            level_score,
        )

        return VolatilitySignalResult(
            timestamp=datetime.now(UTC),
            composite_score=round(composite, 2),
            regime=regime,
            move_zscore=move_result,
            vix_term=vix_result,
            move_component=round(move_score, 2),
            term_component=round(term_score, 2),
            level_component=round(level_score, 2),
        )
