"""Regime Classifier for liquidity environment detection.

Classifies the current liquidity regime as EXPANSION or CONTRACTION based on:
1. Net Liquidity percentile (40%) - Fed balance sheet dynamics
2. Global Liquidity percentile (40%) - Multi-CB aggregate flows
3. Stealth QE score (20%) - Hidden liquidity injection signals

The classifier uses rolling percentiles to adapt to changing market conditions
rather than fixed thresholds, avoiding lookahead bias.

Binary Classification:
    - EXPANSION: Composite > 0.5 (favorable liquidity environment)
    - CONTRACTION: Composite <= 0.5 (unfavorable liquidity environment)

No NEUTRAL state - forces decisive regime classification.

Combined Regime Analysis:
    CombinedRegimeAnalyzer merges liquidity regime with oil supply-demand
    regime to produce a unified macro signal:
    - VERY_BULLISH: Expansion + Tight oil = commodities rally
    - BULLISH: Favorable cross-currents
    - NEUTRAL: Mixed signals
    - BEARISH: Unfavorable cross-currents
    - VERY_BEARISH: Contraction + Loose oil = commodities sell-off
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import pandas as pd

from liquidity.calculators.global_liquidity import GlobalLiquidityCalculator
from liquidity.calculators.net_liquidity import NetLiquidityCalculator
from liquidity.calculators.stealth_qe import StealthQECalculator
from liquidity.config import Settings, get_settings

if TYPE_CHECKING:
    from liquidity.oil.regime import OilRegimeClassifier

logger = logging.getLogger(__name__)


class RegimeDirection(str, Enum):
    """Liquidity regime direction.

    Binary classification - no NEUTRAL to force decisive calls.
    """

    EXPANSION = "EXPANSION"  # Favorable liquidity environment
    CONTRACTION = "CONTRACTION"  # Unfavorable liquidity environment


# Configuration for regime classification
REGIME_CONFIG = {
    "WEIGHT_NET_LIQUIDITY": 0.40,
    "WEIGHT_GLOBAL_LIQUIDITY": 0.40,
    "WEIGHT_STEALTH_QE": 0.20,
    "DEFAULT_LOOKBACK_DAYS": 90,
    "STEALTH_QE_MAX_SCORE": 100.0,  # For normalization
}


@dataclass
class RegimeResult:
    """Result of regime classification.

    Attributes:
        timestamp: Timestamp of the classification.
        direction: EXPANSION or CONTRACTION.
        intensity: Strength of the signal (0-100).
        confidence: HIGH/MEDIUM/LOW based on component agreement.
        net_liq_percentile: Net liquidity percentile in lookback window.
        global_liq_percentile: Global liquidity percentile in lookback window.
        stealth_qe_score: Normalized stealth QE score (0-1).
        components: String representation of component contributions.
    """

    timestamp: datetime
    direction: RegimeDirection
    intensity: float  # 0-100
    confidence: str  # HIGH, MEDIUM, LOW
    net_liq_percentile: float  # 0-1
    global_liq_percentile: float  # 0-1
    stealth_qe_score: float  # 0-1 (normalized)
    components: str  # "NET:0.65 GLO:0.70 SQE:0.45"


class RegimeClassifier:
    """Classify liquidity regime based on multiple indicators.

    The classifier combines three liquidity metrics using a weighted composite:
    - Net Liquidity (40%): Fed balance sheet dynamics (Hayes formula)
    - Global Liquidity (40%): Multi-CB aggregate in USD
    - Stealth QE (20%): Hidden liquidity injection signals

    Algorithm:
    1. Calculate rolling percentiles for net/global liquidity
    2. Normalize stealth QE score to 0-1 scale
    3. Compute weighted composite
    4. Direction: EXPANSION if composite > 0.5, else CONTRACTION
    5. Intensity: abs(composite - 0.5) * 200 (scale 0-100)
    6. Confidence: HIGH if all 3 agree, MEDIUM if 2 agree, LOW if split

    Example:
        classifier = RegimeClassifier()
        result = await classifier.classify()
        print(f"Regime: {result.direction}")
        print(f"Intensity: {result.intensity:.1f}")
        print(f"Confidence: {result.confidence}")
    """

    REGIME_CONFIG = REGIME_CONFIG

    def __init__(
        self,
        settings: Settings | None = None,
        lookback_days: int | None = None,
        weights: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Regime Classifier.

        Args:
            settings: Optional settings override.
            lookback_days: Lookback window for percentile calculation.
                Defaults to 90 days.
            weights: Optional weight overrides for components.
                Must include NET_LIQUIDITY, GLOBAL_LIQUIDITY, STEALTH_QE.
            **kwargs: Additional arguments passed to calculators.
        """
        self._settings = settings or get_settings()
        self._lookback_days = lookback_days or REGIME_CONFIG["DEFAULT_LOOKBACK_DAYS"]

        # Allow weight customization but validate
        if weights:
            self._validate_weights(weights)
            self._weights = weights
        else:
            self._weights = {
                "NET_LIQUIDITY": REGIME_CONFIG["WEIGHT_NET_LIQUIDITY"],
                "GLOBAL_LIQUIDITY": REGIME_CONFIG["WEIGHT_GLOBAL_LIQUIDITY"],
                "STEALTH_QE": REGIME_CONFIG["WEIGHT_STEALTH_QE"],
            }

        # Initialize calculators
        self._net_liq_calc = NetLiquidityCalculator(settings=self._settings, **kwargs)
        self._global_liq_calc = GlobalLiquidityCalculator(
            settings=self._settings, **kwargs
        )
        self._stealth_qe_calc = StealthQECalculator(settings=self._settings, **kwargs)

    def _validate_weights(self, weights: dict[str, float]) -> None:
        """Validate that weights sum to 1.0 and all keys are present.

        Args:
            weights: Weight dictionary to validate.

        Raises:
            ValueError: If weights are invalid.
        """
        required_keys = {"NET_LIQUIDITY", "GLOBAL_LIQUIDITY", "STEALTH_QE"}
        if not required_keys.issubset(weights.keys()):
            missing = required_keys - set(weights.keys())
            raise ValueError(f"Missing required weight keys: {missing}")

        total = sum(weights[k] for k in required_keys)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total:.3f}")

    async def classify(
        self,
        as_of: datetime | None = None,
    ) -> RegimeResult:
        """Classify the current liquidity regime.

        Args:
            as_of: Optional date for historical classification.
                Defaults to current date.

        Returns:
            RegimeResult with classification details.

        Raises:
            ValueError: If insufficient data for classification.
        """
        if as_of is None:
            as_of = datetime.now(UTC)

        logger.info(
            "Classifying regime as of %s with %d-day lookback",
            as_of.date(),
            self._lookback_days,
        )

        # Fetch current stealth QE score (daily value)
        stealth_qe_result = await self._stealth_qe_calc.get_current()

        # Get time series for percentile calculation
        net_liq_df = await self._net_liq_calc.calculate()
        global_liq_df = await self._global_liq_calc.calculate()

        # Calculate percentiles using rolling window (avoid lookahead bias)
        net_liq_percentile = self._calculate_percentile(
            net_liq_df, "net_liquidity", self._lookback_days
        )
        global_liq_percentile = self._calculate_percentile(
            global_liq_df, "global_liquidity", self._lookback_days
        )

        # Normalize stealth QE score to 0-1
        stealth_qe_normalized = (
            stealth_qe_result.score_daily / REGIME_CONFIG["STEALTH_QE_MAX_SCORE"]
        )
        stealth_qe_normalized = max(0.0, min(1.0, stealth_qe_normalized))

        # Calculate weighted composite
        composite = (
            net_liq_percentile * self._weights["NET_LIQUIDITY"]
            + global_liq_percentile * self._weights["GLOBAL_LIQUIDITY"]
            + stealth_qe_normalized * self._weights["STEALTH_QE"]
        )

        # Determine direction (no NEUTRAL - binary classification)
        direction = (
            RegimeDirection.EXPANSION
            if composite > 0.5
            else RegimeDirection.CONTRACTION
        )

        # Calculate intensity (0-100 scale)
        intensity = abs(composite - 0.5) * 200
        intensity = max(0.0, min(100.0, intensity))

        # Determine confidence based on component agreement
        confidence = self._calculate_confidence(
            net_liq_percentile, global_liq_percentile, stealth_qe_normalized
        )

        # Format components string
        components = (
            f"NET:{net_liq_percentile:.2f} "
            f"GLO:{global_liq_percentile:.2f} "
            f"SQE:{stealth_qe_normalized:.2f}"
        )

        result = RegimeResult(
            timestamp=as_of,
            direction=direction,
            intensity=intensity,
            confidence=confidence,
            net_liq_percentile=net_liq_percentile,
            global_liq_percentile=global_liq_percentile,
            stealth_qe_score=stealth_qe_normalized,
            components=components,
        )

        logger.info(
            "Regime classification: %s, intensity=%.1f, confidence=%s",
            result.direction.value,
            result.intensity,
            result.confidence,
        )

        return result

    def _calculate_percentile(
        self,
        df: pd.DataFrame,
        column: str,
        lookback_days: int,
    ) -> float:
        """Calculate the current value's percentile within the lookback window.

        Uses only historical data to avoid lookahead bias.

        Args:
            df: DataFrame with time series data.
            column: Column name to calculate percentile for.
            lookback_days: Number of days for the rolling window.

        Returns:
            Percentile value (0-1).
        """
        if df.empty or column not in df.columns:
            logger.warning(
                "Cannot calculate percentile: empty data or missing column %s", column
            )
            return 0.5  # Default to neutral

        # Ensure we have enough data
        if len(df) < 2:
            logger.warning("Insufficient data for percentile calculation")
            return 0.5

        # Get the last N days of data
        df_window = df.tail(lookback_days)

        if len(df_window) < 2:
            return 0.5

        # Get current value (latest)
        current_value = df_window[column].iloc[-1]

        # Calculate percentile: count of values below current / total count
        # This avoids lookahead bias by only using historical values
        values_below = (df_window[column] < current_value).sum()
        total_values = len(df_window)

        percentile = values_below / total_values

        return percentile

    def _calculate_confidence(
        self,
        net_liq_pct: float,
        global_liq_pct: float,
        stealth_qe_norm: float,
    ) -> str:
        """Calculate confidence based on component agreement.

        HIGH: All 3 components agree on direction (all > 0.5 or all < 0.5)
        MEDIUM: 2 of 3 components agree
        LOW: Components are split (< 2 agree)

        Args:
            net_liq_pct: Net liquidity percentile (0-1).
            global_liq_pct: Global liquidity percentile (0-1).
            stealth_qe_norm: Normalized stealth QE score (0-1).

        Returns:
            Confidence level: HIGH, MEDIUM, or LOW.
        """
        # Count how many indicate expansion (> 0.5)
        expansion_signals = sum(
            [
                net_liq_pct > 0.5,
                global_liq_pct > 0.5,
                stealth_qe_norm > 0.5,
            ]
        )

        # All agree (all expansion or all contraction)
        if expansion_signals == 3 or expansion_signals == 0:
            return "HIGH"

        # 2 of 3 agree
        if expansion_signals == 2 or expansion_signals == 1:
            return "MEDIUM"

        # Should not reach here, but default to LOW
        return "LOW"

    async def classify_historical(
        self,
        start_date: datetime,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Classify regime for a historical date range.

        Args:
            start_date: Start date for classification.
            end_date: End date for classification. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, direction, intensity,
            confidence, net_liq_percentile, global_liq_percentile,
            stealth_qe_score.
        """
        if end_date is None:
            end_date = datetime.now(UTC)

        logger.info(
            "Classifying historical regime from %s to %s",
            start_date.date(),
            end_date.date(),
        )

        # Fetch full time series
        net_liq_df = await self._net_liq_calc.calculate(
            start_date=start_date, end_date=end_date
        )
        global_liq_df = await self._global_liq_calc.calculate(
            start_date=start_date, end_date=end_date
        )
        stealth_qe_df = await self._stealth_qe_calc.calculate_daily(
            start_date=start_date, end_date=end_date
        )

        if net_liq_df.empty or global_liq_df.empty or stealth_qe_df.empty:
            logger.warning("Insufficient data for historical classification")
            return self._empty_historical_dataframe()

        # Align timestamps across all series
        net_liq_df = net_liq_df.set_index("timestamp")
        global_liq_df = global_liq_df.set_index("timestamp")
        stealth_qe_df = stealth_qe_df.set_index("timestamp")

        # Get common timestamps
        common_index = (
            net_liq_df.index.intersection(global_liq_df.index)
            .intersection(stealth_qe_df.index)
        )

        if len(common_index) < self._lookback_days:
            logger.warning(
                "Not enough common data points for historical classification"
            )
            return self._empty_historical_dataframe()

        results = []
        for i, ts in enumerate(common_index):
            # Skip if not enough history for lookback
            if i < self._lookback_days:
                continue

            # Get lookback window
            lookback_start = max(0, i - self._lookback_days)
            window_index = common_index[lookback_start : i + 1]

            # Calculate rolling percentiles
            net_window = net_liq_df.loc[window_index, "net_liquidity"]
            global_window = global_liq_df.loc[window_index, "global_liquidity"]

            current_net = net_window.iloc[-1]
            current_global = global_window.iloc[-1]

            net_liq_pct = (net_window < current_net).sum() / len(net_window)
            global_liq_pct = (global_window < current_global).sum() / len(global_window)

            # Normalize stealth QE
            stealth_score = stealth_qe_df.loc[ts, "score_daily"]
            stealth_norm = stealth_score / REGIME_CONFIG["STEALTH_QE_MAX_SCORE"]
            stealth_norm = max(0.0, min(1.0, stealth_norm))

            # Calculate composite
            composite = (
                net_liq_pct * self._weights["NET_LIQUIDITY"]
                + global_liq_pct * self._weights["GLOBAL_LIQUIDITY"]
                + stealth_norm * self._weights["STEALTH_QE"]
            )

            # Determine direction
            direction = (
                RegimeDirection.EXPANSION
                if composite > 0.5
                else RegimeDirection.CONTRACTION
            )

            # Calculate intensity
            intensity = abs(composite - 0.5) * 200
            intensity = max(0.0, min(100.0, intensity))

            # Determine confidence
            confidence = self._calculate_confidence(
                net_liq_pct, global_liq_pct, stealth_norm
            )

            results.append(
                {
                    "timestamp": ts,
                    "direction": direction.value,
                    "intensity": intensity,
                    "confidence": confidence,
                    "net_liq_percentile": net_liq_pct,
                    "global_liq_percentile": global_liq_pct,
                    "stealth_qe_score": stealth_norm,
                }
            )

        result_df = pd.DataFrame(results)
        if not result_df.empty:
            logger.info(
                "Classified %d historical regime observations",
                len(result_df),
            )

        return result_df

    def _empty_historical_dataframe(self) -> pd.DataFrame:
        """Return an empty DataFrame with historical classification columns."""
        return pd.DataFrame(
            columns=[
                "timestamp",
                "direction",
                "intensity",
                "confidence",
                "net_liq_percentile",
                "global_liq_percentile",
                "stealth_qe_score",
            ]
        )

    def __repr__(self) -> str:
        """Return string representation of the classifier."""
        return (
            f"RegimeClassifier(lookback={self._lookback_days}, "
            f"weights={self._weights})"
        )


# =============================================================================
# Combined Regime Analysis (Liquidity + Oil)
# =============================================================================


class CombinedRegime(str, Enum):
    """Combined liquidity-oil regime classification.

    Maps the combination of liquidity regime (EXPANSION/CONTRACTION) and
    oil supply-demand regime (TIGHT/BALANCED/LOOSE) into a unified signal.
    """

    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


@dataclass
class CombinedRegimeState:
    """Combined liquidity and oil regime state.

    Attributes:
        timestamp: Timestamp of the analysis.
        liquidity_regime: Liquidity regime direction (EXPANSION/CONTRACTION).
        oil_regime: Oil supply-demand regime (TIGHT/BALANCED/LOOSE).
        combined_regime: Combined regime classification.
        confidence: Average confidence from both classifiers (0-1).
        commodity_signal: Trading signal (long/short/neutral).
        drivers: List of factors driving the current regime.
    """

    timestamp: datetime
    liquidity_regime: str  # EXPANSION or CONTRACTION
    oil_regime: Any  # OilRegime enum (avoid circular import)
    combined_regime: CombinedRegime
    confidence: float
    commodity_signal: str  # "long", "short", "neutral"
    drivers: list[str]


class CombinedRegimeAnalyzer:
    """Combines liquidity and oil regime for macro signals.

    The analyzer produces a unified regime classification by combining:
    - Liquidity regime: EXPANSION (favorable) vs CONTRACTION (unfavorable)
    - Oil supply-demand regime: TIGHT (bullish) vs LOOSE (bearish)

    The REGIME_MATRIX maps all 6 combinations to 5 output states.

    Example:
        analyzer = CombinedRegimeAnalyzer()
        state = await analyzer.get_combined_regime()
        print(f"Combined: {state.combined_regime.value}")
        print(f"Signal: {state.commodity_signal}")
    """

    # Regime combination matrix
    # Maps (liquidity_regime, oil_regime) -> combined_regime
    REGIME_MATRIX: dict[tuple[str, str], CombinedRegime] = {}

    @classmethod
    def _init_regime_matrix(cls) -> None:
        """Initialize the regime matrix lazily to avoid circular imports."""
        if cls.REGIME_MATRIX:
            return

        from liquidity.oil.regime import OilRegime

        cls.REGIME_MATRIX = {
            ("EXPANSION", OilRegime.TIGHT): CombinedRegime.VERY_BULLISH,
            ("EXPANSION", OilRegime.BALANCED): CombinedRegime.BULLISH,
            ("EXPANSION", OilRegime.LOOSE): CombinedRegime.NEUTRAL,
            ("EXPANSION", OilRegime.UNKNOWN): CombinedRegime.BULLISH,  # Liquidity is expansionary
            ("NEUTRAL", OilRegime.TIGHT): CombinedRegime.BULLISH,
            ("NEUTRAL", OilRegime.BALANCED): CombinedRegime.NEUTRAL,
            ("NEUTRAL", OilRegime.LOOSE): CombinedRegime.BEARISH,
            ("NEUTRAL", OilRegime.UNKNOWN): CombinedRegime.NEUTRAL,
            ("CONTRACTION", OilRegime.TIGHT): CombinedRegime.NEUTRAL,
            ("CONTRACTION", OilRegime.BALANCED): CombinedRegime.BEARISH,
            ("CONTRACTION", OilRegime.LOOSE): CombinedRegime.VERY_BEARISH,
            ("CONTRACTION", OilRegime.UNKNOWN): CombinedRegime.BEARISH,  # Liquidity is contracting
        }

    def __init__(
        self,
        liquidity_classifier: RegimeClassifier | None = None,
        oil_classifier: OilRegimeClassifier | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the Combined Regime Analyzer.

        Args:
            liquidity_classifier: Optional pre-configured liquidity classifier.
            oil_classifier: Optional pre-configured oil regime classifier.
            settings: Optional settings override.
        """
        self._settings = settings or get_settings()

        # Lazy import to avoid circular dependency
        from liquidity.oil.regime import OilRegimeClassifier

        self._init_regime_matrix()

        self._liquidity = liquidity_classifier or RegimeClassifier(
            settings=self._settings
        )
        self._oil = oil_classifier or OilRegimeClassifier()

    async def get_combined_regime(self) -> CombinedRegimeState:
        """Get combined liquidity-oil regime.

        Fetches both liquidity and oil regime classifications and combines
        them using the REGIME_MATRIX.

        Returns:
            CombinedRegimeState with unified classification.

        Raises:
            ValueError: If either classifier fails to produce a result.
        """
        # Get individual regimes
        liquidity_result = await self._liquidity.classify()
        oil_state = await self._oil.classify()

        # Map liquidity direction to string for matrix lookup
        liquidity_regime = liquidity_result.direction.value

        # Combine regimes
        combined = self._combine_regimes(liquidity_regime, oil_state.regime)

        # Calculate confidence (average, normalized to 0-1)
        # Liquidity confidence is categorical (HIGH/MEDIUM/LOW), convert to numeric
        liq_conf_map = {"HIGH": 1.0, "MEDIUM": 0.66, "LOW": 0.33}
        liq_conf = liq_conf_map.get(liquidity_result.confidence, 0.5)
        # Oil confidence is 0-100, normalize to 0-1
        oil_conf = oil_state.confidence / 100.0
        confidence = (liq_conf + oil_conf) / 2

        # Generate trading signal
        signal = self._regime_to_signal(combined)

        # Collect drivers
        drivers = [
            f"Liquidity: {liquidity_regime} (intensity {liquidity_result.intensity:.0f})",
            f"Oil: {oil_state.regime.value}",
            *oil_state.drivers,
        ]

        return CombinedRegimeState(
            timestamp=datetime.now(UTC),
            liquidity_regime=liquidity_regime,
            oil_regime=oil_state.regime,
            combined_regime=combined,
            confidence=confidence,
            commodity_signal=signal,
            drivers=drivers,
        )

    def _combine_regimes(
        self,
        liquidity: str,
        oil_regime: Any,
    ) -> CombinedRegime:
        """Combine liquidity and oil regimes using the matrix.

        Args:
            liquidity: Liquidity regime (EXPANSION/CONTRACTION).
            oil_regime: Oil regime (OilRegime enum).

        Returns:
            Combined regime classification.
        """
        # Handle liquidity NEUTRAL (not in original binary classifier but
        # may be added for 3-state classification)
        if liquidity not in ("EXPANSION", "CONTRACTION", "NEUTRAL"):
            logger.warning("Unknown liquidity regime: %s, defaulting to NEUTRAL", liquidity)
            liquidity = "NEUTRAL"

        return self.REGIME_MATRIX.get(
            (liquidity, oil_regime),
            CombinedRegime.NEUTRAL,
        )

    def _regime_to_signal(self, regime: CombinedRegime) -> str:
        """Convert combined regime to trading signal.

        Args:
            regime: Combined regime classification.

        Returns:
            Trading signal: "long", "short", or "neutral".
        """
        if regime in (CombinedRegime.VERY_BULLISH, CombinedRegime.BULLISH):
            return "long"
        elif regime in (CombinedRegime.VERY_BEARISH, CombinedRegime.BEARISH):
            return "short"
        return "neutral"

    def __repr__(self) -> str:
        """Return string representation of the analyzer."""
        return f"CombinedRegimeAnalyzer(liquidity={self._liquidity}, oil={self._oil})"
