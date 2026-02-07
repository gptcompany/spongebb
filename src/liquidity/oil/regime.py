"""Oil market regime classifier.

Classifies the oil market into regimes (TIGHT/BALANCED/LOOSE) based on
supply-demand fundamentals including:
- Inventory levels vs 5-year seasonal average
- Supply-demand balance
- Refinery utilization

Regime definitions:
| Regime   | Inventory       | Production  | Utilization | Signal  |
|----------|-----------------|-------------|-------------|---------|
| TIGHT    | Below 5yr avg   | Declining   | >93%        | Bullish |
| BALANCED | Near 5yr avg    | Stable      | 88-93%      | Neutral |
| LOOSE    | Above 5yr avg   | Rising      | <88%        | Bearish |
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from liquidity.collectors.eia import EIACollector
    from liquidity.oil.inventory_forecast import InventoryForecaster
    from liquidity.oil.supply_demand import SupplyDemandCalculator

logger = logging.getLogger(__name__)


class OilRegime(Enum):
    """Oil market regime classification."""

    TIGHT = "tight"  # Supply deficit, bullish
    BALANCED = "balanced"  # Supply-demand equilibrium
    LOOSE = "loose"  # Supply surplus, bearish


@dataclass
class OilRegimeState:
    """Current oil market regime state.

    Attributes:
        timestamp: When the classification was made.
        regime: Current market regime.
        confidence: Classification confidence (0-100).
        inventory_signal: Signal from inventory analysis.
        production_signal: Signal from production/balance analysis.
        utilization_signal: Signal from refinery utilization.
        balance_signal: Signal from supply-demand balance.
        composite_score: Composite score (-100 to +100, positive = bullish).
        drivers: Key factors driving the current regime.
    """

    timestamp: datetime
    regime: OilRegime
    confidence: float  # 0-100
    inventory_signal: str  # "bullish", "bearish", "neutral"
    production_signal: str
    utilization_signal: str
    balance_signal: str
    composite_score: float  # -100 to +100 (bullish to bearish)
    drivers: list[str]  # Key factors driving regime


class OilRegimeClassifier:
    """Classifies oil market regime based on fundamentals.

    Combines signals from:
    - Inventory levels (vs 5-year average)
    - Supply-demand balance
    - Refinery utilization

    Example:
        classifier = OilRegimeClassifier()
        state = await classifier.classify()

        print(f"Regime: {state.regime.value}")
        print(f"Confidence: {state.confidence:.0f}%")
        print(f"Composite: {state.composite_score:+.1f}")
        for driver in state.drivers:
            print(f"  - {driver}")
    """

    # Thresholds for inventory scoring
    INVENTORY_BULLISH_THRESHOLD = -5  # % below 5yr avg
    INVENTORY_BEARISH_THRESHOLD = 5  # % above 5yr avg

    # Thresholds for refinery utilization
    UTILIZATION_TIGHT = 93  # % - above this = tight market
    UTILIZATION_LOOSE = 88  # % - below this = loose market

    # Regime classification thresholds
    REGIME_TIGHT_THRESHOLD = 30  # composite > 30 = tight
    REGIME_LOOSE_THRESHOLD = -30  # composite < -30 = loose

    # Signal classification threshold
    SIGNAL_THRESHOLD = 20  # abs(score) > 20 = directional signal

    # Driver identification threshold
    DRIVER_THRESHOLD = 30  # abs(score) > 30 = significant driver

    def __init__(
        self,
        supply_demand: "SupplyDemandCalculator | None" = None,
        inventory: "InventoryForecaster | None" = None,
        eia: "EIACollector | None" = None,
    ) -> None:
        """Initialize the regime classifier.

        Args:
            supply_demand: Optional SupplyDemandCalculator instance.
            inventory: Optional InventoryForecaster instance.
            eia: Optional EIACollector instance for utilization data.
        """
        self._supply_demand = supply_demand
        self._inventory = inventory
        self._eia = eia

    async def _get_supply_demand(self) -> "SupplyDemandCalculator":
        """Get or create SupplyDemandCalculator instance."""
        if self._supply_demand is None:
            from liquidity.oil.supply_demand import SupplyDemandCalculator

            self._supply_demand = SupplyDemandCalculator()
        return self._supply_demand

    async def _get_inventory(self) -> "InventoryForecaster":
        """Get or create InventoryForecaster instance."""
        if self._inventory is None:
            from liquidity.oil.inventory_forecast import InventoryForecaster

            self._inventory = InventoryForecaster()
        return self._inventory

    async def _get_eia(self) -> "EIACollector":
        """Get or create EIACollector instance."""
        if self._eia is None:
            from liquidity.collectors.eia import EIACollector

            self._eia = EIACollector()
        return self._eia

    async def classify(self) -> OilRegimeState:
        """Classify current oil market regime.

        Fetches current data from EIA and calculates composite score
        from inventory, balance, and utilization components.

        Returns:
            OilRegimeState with current regime classification.

        Raises:
            ValueError: If required data is unavailable.
        """
        # Get current data
        supply_demand = await self._get_supply_demand()
        inventory = await self._get_inventory()

        balance = await supply_demand.get_current_balance()
        inv_analysis = await inventory.get_current_analysis()
        utilization = await self._get_utilization()

        # Score each component
        inventory_score = self._score_inventory(inv_analysis.vs_5yr_avg_pct)
        balance_score = self._score_balance(balance.balance)
        utilization_score = self._score_utilization(utilization)

        # Composite score (-100 to +100, positive = bullish)
        composite = (inventory_score + balance_score + utilization_score) / 3

        # Classify regime
        regime = self._classify_regime(composite)
        confidence = self._calculate_confidence(composite)

        # Identify drivers
        drivers = self._identify_drivers(
            inventory_score, balance_score, utilization_score
        )

        return OilRegimeState(
            timestamp=datetime.now(),
            regime=regime,
            confidence=confidence,
            inventory_signal=self._score_to_signal(inventory_score),
            production_signal=self._score_to_signal(balance_score),
            utilization_signal=self._score_to_signal(utilization_score),
            balance_signal=balance.signal,
            composite_score=composite,
            drivers=drivers,
        )

    def _score_inventory(self, vs_5yr_pct: float) -> float:
        """Score inventory vs 5yr avg.

        Below average = positive (bullish), above average = negative (bearish).

        Args:
            vs_5yr_pct: Percentage difference from 5-year average.
                        Positive means current inventory is above average.

        Returns:
            Score from -100 to +100 (clamped).
            Positive = bullish (inventory below average).
        """
        # Below avg = positive (bullish), above avg = negative (bearish)
        # vs_5yr_pct > 0 means inventory ABOVE average (bearish)
        # So we negate it: -vs_5yr_pct * 10
        score = -vs_5yr_pct * 10  # Scale: 10% below avg = +100
        return max(-100.0, min(100.0, score))

    def _score_balance(self, balance: float) -> float:
        """Score supply-demand balance.

        Draw (negative balance) = positive (bullish).
        Build (positive balance) = negative (bearish).

        Args:
            balance: Supply-demand balance in thousand b/d.
                     Negative = draw, Positive = build.

        Returns:
            Score from -100 to +100 (clamped).
            Positive = bullish (inventory drawing).
        """
        # Draw (negative balance) = positive (bullish)
        # Scale: 1000 kb/d draw = +100
        score = -balance / 10
        return max(-100.0, min(100.0, score))

    def _score_utilization(self, utilization: float) -> float:
        """Score refinery utilization.

        High utilization = positive (tight market).
        Low utilization = negative (loose market).

        Args:
            utilization: Refinery utilization percentage (0-100).

        Returns:
            Score from -100 to +100 (clamped).
            Positive = bullish (high utilization, tight market).
        """
        # High utilization = positive (tight market)
        midpoint = (self.UTILIZATION_TIGHT + self.UTILIZATION_LOOSE) / 2
        # Scale: 93% = +50, 88% = -50
        score = (utilization - midpoint) * 20
        return max(-100.0, min(100.0, score))

    def _classify_regime(self, composite: float) -> OilRegime:
        """Classify regime from composite score.

        Args:
            composite: Composite score from -100 to +100.

        Returns:
            OilRegime enum value.
        """
        if composite > self.REGIME_TIGHT_THRESHOLD:
            return OilRegime.TIGHT
        elif composite < self.REGIME_LOOSE_THRESHOLD:
            return OilRegime.LOOSE
        return OilRegime.BALANCED

    def _calculate_confidence(self, composite: float) -> float:
        """Calculate confidence in regime classification.

        Higher absolute score = higher confidence.

        Args:
            composite: Composite score from -100 to +100.

        Returns:
            Confidence percentage (0-100).
        """
        # Higher absolute score = higher confidence
        return min(abs(composite), 100.0)

    def _score_to_signal(self, score: float) -> str:
        """Convert score to signal string.

        Args:
            score: Score from -100 to +100.

        Returns:
            Signal string: "bullish", "bearish", or "neutral".
        """
        if score > self.SIGNAL_THRESHOLD:
            return "bullish"
        elif score < -self.SIGNAL_THRESHOLD:
            return "bearish"
        return "neutral"

    def _identify_drivers(
        self, inv_score: float, bal_score: float, util_score: float
    ) -> list[str]:
        """Identify key regime drivers.

        Args:
            inv_score: Inventory score.
            bal_score: Balance score.
            util_score: Utilization score.

        Returns:
            List of driver descriptions.
        """
        drivers = []

        if abs(inv_score) > self.DRIVER_THRESHOLD:
            direction = "below" if inv_score > 0 else "above"
            drivers.append(f"Inventory {direction} 5-year average")

        if abs(bal_score) > self.DRIVER_THRESHOLD:
            direction = "draws" if bal_score > 0 else "builds"
            drivers.append(f"Weekly {direction}")

        if abs(util_score) > self.DRIVER_THRESHOLD:
            level = "high" if util_score > 0 else "low"
            drivers.append(f"Refinery utilization {level}")

        return drivers

    async def _get_utilization(self) -> float:
        """Get current refinery utilization percentage.

        Returns:
            Refinery utilization percentage (0-100).
            Returns 90.0 as default if data unavailable.
        """
        try:
            eia = await self._get_eia()
            data = await eia.collect_refinery_utilization(
                regions=["us"], lookback_weeks=4
            )
            if not data.empty:
                # Get the most recent value
                data = data.sort_values("timestamp")
                return float(data["value"].iloc[-1])
        except Exception as e:
            logger.warning("Could not get refinery utilization: %s", e)

        return 90.0  # Default if not available

    async def close(self) -> None:
        """Close the classifier and release resources."""
        if self._supply_demand is not None:
            await self._supply_demand.close()
        if self._inventory is not None:
            await self._inventory.close()
        if self._eia is not None:
            await self._eia.close()
