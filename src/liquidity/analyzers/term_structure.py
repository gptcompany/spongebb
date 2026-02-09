"""Term structure analysis for oil contango/backwardation detection.

This analyzer classifies oil market term structure based on price momentum,
since direct term structure data (futures curve) is not available via yfinance.

Term structure states:
- CONTANGO: Futures price > Spot price (bearish, supply abundant)
- BACKWARDATION: Futures price < Spot price (bullish, supply tight)
- FLAT: No significant premium/discount

We use momentum as a proxy:
- Rising prices (positive momentum) → backwardation tendency
- Falling prices (negative momentum) → contango tendency
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Literal

import numpy as np
import pandas as pd


class CurveShape(str, Enum):
    """Term structure curve shape classification."""

    CONTANGO = "CONTANGO"
    BACKWARDATION = "BACKWARDATION"
    FLAT = "FLAT"


@dataclass
class TermStructureSignal:
    """Term structure analysis result."""

    timestamp: datetime
    curve_shape: CurveShape
    intensity: float  # 0-100 (strength of the signal)
    roll_yield_proxy: float  # Annualized % (positive in backwardation)
    momentum_5d: float  # 5-day price momentum %
    momentum_20d: float  # 20-day price momentum %
    confidence: float  # 0-1 (confidence in the classification)


@dataclass
class RollYieldMetrics:
    """Detailed roll yield analysis."""

    monthly_yield: float  # 1-month annualized %
    quarterly_yield: float  # 3-month annualized %
    annual_yield: float  # 12-month estimate %
    yield_trend: Literal["IMPROVING", "STABLE", "DETERIORATING"]
    days_in_current_regime: int


class TermStructureAnalyzer:
    """Analyze oil term structure for trading signals.

    Uses price momentum as a proxy for term structure shape since
    we only have front month continuous contract data.

    Example:
        analyzer = TermStructureAnalyzer()

        # Analyze with momentum data
        signal = analyzer.analyze(price_data)

        print(f"Curve: {signal.curve_shape}")
        print(f"Intensity: {signal.intensity}")
        print(f"Roll Yield: {signal.roll_yield_proxy}%")

        # Get detailed roll yield metrics
        roll = analyzer.calculate_roll_yield(price_data)
        print(f"Monthly yield: {roll.monthly_yield}%")
    """

    # Default thresholds
    MOMENTUM_THRESHOLD = 2.0  # % for backwardation/contango classification
    INTENSITY_SCALE = 10.0  # Multiplier for intensity calculation

    def __init__(
        self,
        momentum_threshold: float = 2.0,
        use_eia_correlation: bool = True,
    ) -> None:
        """Initialize term structure analyzer.

        Args:
            momentum_threshold: Minimum momentum % to classify as non-flat.
            use_eia_correlation: Whether to use EIA inventory data to refine signal.
        """
        self.momentum_threshold = momentum_threshold
        self.use_eia_correlation = use_eia_correlation

    def analyze(
        self,
        price_data: pd.DataFrame,
        eia_data: pd.DataFrame | None = None,
    ) -> TermStructureSignal:
        """Analyze term structure and generate signal.

        Args:
            price_data: DataFrame with momentum series from OilTermStructureCollector.
                Required series: wti_front_momentum_5d, wti_front_momentum_20d
            eia_data: Optional EIA inventory data for correlation analysis.

        Returns:
            TermStructureSignal with curve shape and metrics.
        """
        # Extract momentum values
        momentum_5d = self._get_latest_momentum(price_data, "wti_front_momentum_5d")
        momentum_20d = self._get_latest_momentum(price_data, "wti_front_momentum_20d")

        # Classify curve shape
        curve_shape, intensity = self._classify_curve(
            momentum_5d, momentum_20d, eia_data
        )

        # Calculate roll yield proxy
        roll_yield = self._estimate_roll_yield(momentum_5d, momentum_20d)

        # Calculate confidence
        confidence = self._calculate_confidence(
            momentum_5d, momentum_20d, eia_data is not None
        )

        return TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=curve_shape,
            intensity=intensity,
            roll_yield_proxy=roll_yield,
            momentum_5d=momentum_5d,
            momentum_20d=momentum_20d,
            confidence=confidence,
        )

    def calculate_roll_yield(
        self,
        price_data: pd.DataFrame,
    ) -> RollYieldMetrics:
        """Calculate detailed roll yield metrics.

        Roll yield is the return from rolling futures contracts:
        - Backwardation: positive roll yield (buy cheap, sell dear)
        - Contango: negative roll yield (buy dear, sell cheap)

        Args:
            price_data: DataFrame with momentum series.

        Returns:
            RollYieldMetrics with yields at different horizons.
        """
        momentum_5d = self._get_latest_momentum(price_data, "wti_front_momentum_5d")
        momentum_20d = self._get_latest_momentum(price_data, "wti_front_momentum_20d")

        # Estimate yields at different horizons (annualized)
        # Assume momentum approximates the curve slope
        monthly_yield = momentum_5d * (252 / 5)  # Annualize 5-day
        quarterly_yield = momentum_20d * (252 / 20)  # Annualize 20-day
        annual_yield = (monthly_yield + quarterly_yield) / 2  # Blended

        # Determine trend
        trend = self._determine_yield_trend(momentum_5d, momentum_20d)

        # Count days in current regime
        days = self._count_regime_days(price_data)

        return RollYieldMetrics(
            monthly_yield=round(monthly_yield, 2),
            quarterly_yield=round(quarterly_yield, 2),
            annual_yield=round(annual_yield, 2),
            yield_trend=trend,
            days_in_current_regime=days,
        )

    def classify_batch(
        self,
        price_data: pd.DataFrame,
        lookback_days: int = 30,
    ) -> pd.DataFrame:
        """Classify curve shape for historical data.

        Args:
            price_data: DataFrame with momentum series.
            lookback_days: Number of days to analyze.

        Returns:
            DataFrame with date, curve_shape, intensity, roll_yield columns.
        """
        if price_data.empty or "series_id" not in price_data.columns:
            return pd.DataFrame()

        results = []

        # Get unique dates from momentum series
        momentum_data = price_data[
            price_data["series_id"] == "wti_front_momentum_5d"
        ].sort_values("timestamp")

        if momentum_data.empty:
            return pd.DataFrame()

        dates = momentum_data["timestamp"].unique()[-lookback_days:]

        for date in dates:
            # Filter data up to this date
            mask = price_data["timestamp"] <= pd.Timestamp(date)
            subset = price_data[mask]

            if subset.empty:
                continue

            signal = self.analyze(subset)

            results.append({
                "timestamp": date,
                "curve_shape": signal.curve_shape.value,
                "intensity": signal.intensity,
                "roll_yield_proxy": signal.roll_yield_proxy,
                "confidence": signal.confidence,
            })

        return pd.DataFrame(results)

    def _get_latest_momentum(
        self,
        df: pd.DataFrame,
        series_id: str,
    ) -> float:
        """Extract latest momentum value from DataFrame."""
        if df.empty:
            return 0.0

        filtered = df[df["series_id"] == series_id]
        if filtered.empty:
            return 0.0

        # Get the latest value
        latest = filtered.sort_values("timestamp").iloc[-1]
        value = latest["value"]

        return float(value) if pd.notna(value) else 0.0

    def _classify_curve(
        self,
        momentum_5d: float,
        _momentum_20d: float,
        eia_data: pd.DataFrame | None,
    ) -> tuple[CurveShape, float]:
        """Classify term structure based on momentum.

        Args:
            momentum_5d: 5-day momentum percentage.
            momentum_20d: 20-day momentum percentage.
            eia_data: Optional EIA inventory data.

        Returns:
            Tuple of (CurveShape, intensity 0-100).
        """
        # Use short-term momentum as primary signal
        if momentum_5d > self.momentum_threshold:
            base_shape = CurveShape.BACKWARDATION
            base_intensity = min(abs(momentum_5d) * self.INTENSITY_SCALE, 100)
        elif momentum_5d < -self.momentum_threshold:
            base_shape = CurveShape.CONTANGO
            base_intensity = min(abs(momentum_5d) * self.INTENSITY_SCALE, 100)
        else:
            base_shape = CurveShape.FLAT
            # Intensity for flat is inverse of momentum strength
            base_intensity = max(0, 50 - abs(momentum_5d) * 10)

        # Adjust with EIA inventory correlation if available
        if eia_data is not None and self.use_eia_correlation:
            inventory_signal = self._get_inventory_signal(eia_data)

            # Inventory build → contango bias (weakens backwardation)
            # Inventory draw → backwardation bias (weakens contango)
            if inventory_signal > 0:  # Build
                if base_shape == CurveShape.BACKWARDATION:
                    base_intensity *= 0.8
            elif inventory_signal < 0 and base_shape == CurveShape.CONTANGO:  # Draw
                    base_intensity *= 0.8

        return base_shape, max(0, min(100, base_intensity))

    def _get_inventory_signal(self, eia_data: pd.DataFrame) -> float:
        """Get inventory change signal from EIA data.

        Args:
            eia_data: EIA inventory DataFrame.

        Returns:
            Positive for build, negative for draw.
        """
        if eia_data.empty:
            return 0.0

        # Look for crude inventory series
        inventory = eia_data[
            eia_data["series_id"].str.contains("crude_stocks", case=False, na=False)
        ]

        if len(inventory) < 2:
            return 0.0

        sorted_inv = inventory.sort_values("timestamp")
        change = sorted_inv["value"].iloc[-1] - sorted_inv["value"].iloc[-2]

        return float(change)

    def _estimate_roll_yield(
        self,
        momentum_5d: float,
        momentum_20d: float,
    ) -> float:
        """Estimate annualized roll yield from momentum.

        In backwardation: positive roll yield (earn from roll)
        In contango: negative roll yield (pay to roll)

        Args:
            momentum_5d: 5-day momentum percentage.
            momentum_20d: 20-day momentum percentage.

        Returns:
            Annualized roll yield estimate.
        """
        # Use average momentum as proxy for curve slope
        avg_momentum = (momentum_5d + momentum_20d) / 2

        # Annualize assuming ~12 monthly rolls
        annualized = avg_momentum * 12

        return round(annualized, 2)

    def _calculate_confidence(
        self,
        momentum_5d: float,
        momentum_20d: float,
        has_eia: bool,
    ) -> float:
        """Calculate confidence in the signal classification.

        Args:
            momentum_5d: 5-day momentum percentage.
            momentum_20d: 20-day momentum percentage.
            has_eia: Whether EIA data was available.

        Returns:
            Confidence score 0-1.
        """
        confidence = 0.5  # Base confidence

        # Agreement between timeframes increases confidence
        if np.sign(momentum_5d) == np.sign(momentum_20d):
            confidence += 0.2

        # Strong momentum increases confidence
        if abs(momentum_5d) > 3:
            confidence += 0.1

        if abs(momentum_20d) > 5:
            confidence += 0.1

        # EIA data increases confidence
        if has_eia:
            confidence += 0.1

        return min(1.0, confidence)

    def _determine_yield_trend(
        self,
        momentum_5d: float,
        momentum_20d: float,
    ) -> Literal["IMPROVING", "STABLE", "DETERIORATING"]:
        """Determine roll yield trend.

        Args:
            momentum_5d: 5-day momentum.
            momentum_20d: 20-day momentum.

        Returns:
            Trend classification.
        """
        diff = momentum_5d - momentum_20d

        if diff > 0.5:
            return "IMPROVING"
        elif diff < -0.5:
            return "DETERIORATING"
        else:
            return "STABLE"

    def _count_regime_days(self, df: pd.DataFrame) -> int:
        """Count consecutive days in current regime.

        Args:
            df: DataFrame with momentum series.

        Returns:
            Number of days in current regime.
        """
        if df.empty:
            return 0

        # Get momentum history
        momentum = df[df["series_id"] == "wti_front_momentum_5d"].sort_values("timestamp")

        if len(momentum) < 2:
            return 1

        # Count consecutive days with same sign
        values = momentum["value"].dropna()
        if values.empty:
            return 0

        current_sign = np.sign(values.iloc[-1])
        count = 0

        for val in values.iloc[::-1]:
            if np.sign(val) == current_sign or current_sign == 0:
                count += 1
            else:
                break

        return count
