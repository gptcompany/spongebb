"""NautilusTrader Macro Filter Interface.

Provides risk-based filters for trading strategies
based on liquidity regime and risk metrics.
"""

import logging
from dataclasses import dataclass
from enum import Enum

from .regime_var import REGIME_RISK_MULTIPLIERS, RegimeType

logger = logging.getLogger(__name__)


class TradingDecision(str, Enum):
    """Trading filter decision."""

    ALLOW = "ALLOW"
    REDUCE = "REDUCE"
    BLOCK = "BLOCK"


@dataclass
class FilterResult:
    """Result from macro filter evaluation."""

    decision: TradingDecision
    position_multiplier: float
    regime: RegimeType
    var_level: float
    risk_score: float
    reason: str


class LiquidityRiskFilter:
    """Macro filter for NautilusTrader strategies.

    Evaluates liquidity regime and risk metrics to determine:
    1. Whether to allow trading
    2. Position size multiplier
    3. Risk-adjusted parameters

    Integration with NautilusTrader:
    ```python
    class MyStrategy(Strategy):
        def on_bar(self, bar: Bar) -> None:
            filter_result = self.macro_filter.evaluate(
                regime=self.current_regime,
                var_level=self.current_var
            )
            if filter_result.decision == TradingDecision.BLOCK:
                return

            position_size = base_size * filter_result.position_multiplier
            # ... execute trade
    ```

    Example:
        >>> filter = LiquidityRiskFilter()
        >>> result = filter.evaluate(RegimeType.CONTRACTION, var_level=0.04)
        >>> print(f"Decision: {result.decision.value}, Multiplier: {result.position_multiplier}")
    """

    def __init__(
        self,
        var_threshold_reduce: float = 0.03,
        var_threshold_block: float = 0.05,
        contraction_reduce_factor: float = 0.5,
    ) -> None:
        """Initialize filter.

        Args:
            var_threshold_reduce: VaR level to reduce position
            var_threshold_block: VaR level to block trading
            contraction_reduce_factor: Position multiplier in contraction
        """
        self.var_threshold_reduce = var_threshold_reduce
        self.var_threshold_block = var_threshold_block
        self.contraction_reduce_factor = contraction_reduce_factor

    def evaluate(
        self,
        regime: RegimeType,
        var_level: float,
        current_drawdown: float = 0.0,
    ) -> FilterResult:
        """Evaluate trading conditions.

        Args:
            regime: Current liquidity regime
            var_level: Current VaR (95%)
            current_drawdown: Strategy drawdown (optional)

        Returns:
            FilterResult with trading decision
        """
        risk_score = self._calculate_risk_score(regime, var_level, current_drawdown)

        # Determine decision
        if var_level > self.var_threshold_block:
            decision = TradingDecision.BLOCK
            multiplier = 0.0
            reason = f"VaR {var_level:.1%} exceeds block threshold {self.var_threshold_block:.1%}"

        elif regime == RegimeType.CONTRACTION and var_level > self.var_threshold_reduce:
            decision = TradingDecision.REDUCE
            multiplier = self.contraction_reduce_factor
            reason = f"CONTRACTION regime with elevated VaR {var_level:.1%}"

        elif var_level > self.var_threshold_reduce:
            decision = TradingDecision.REDUCE
            multiplier = max(0.5, 1.0 - (var_level - self.var_threshold_reduce) * 10)
            reason = f"VaR {var_level:.1%} exceeds reduce threshold"

        elif regime == RegimeType.CONTRACTION:
            decision = TradingDecision.REDUCE
            multiplier = self.contraction_reduce_factor
            reason = "CONTRACTION regime - reduce position size"

        elif regime == RegimeType.EXPANSION:
            decision = TradingDecision.ALLOW
            multiplier = 1.2
            reason = "EXPANSION regime - favorable conditions"

        else:  # NEUTRAL
            decision = TradingDecision.ALLOW
            multiplier = 1.0
            reason = "NEUTRAL regime - normal trading"

        return FilterResult(
            decision=decision,
            position_multiplier=multiplier,
            regime=regime,
            var_level=var_level,
            risk_score=risk_score,
            reason=reason,
        )

    def _calculate_risk_score(
        self,
        regime: RegimeType,
        var_level: float,
        drawdown: float,
    ) -> float:
        """Calculate composite risk score 0-100.

        Args:
            regime: Current regime
            var_level: Current VaR
            drawdown: Current drawdown

        Returns:
            Risk score 0-100 (higher = more risk)
        """
        # Regime component (0-40)
        regime_scores = {
            RegimeType.EXPANSION: 10.0,
            RegimeType.NEUTRAL: 25.0,
            RegimeType.CONTRACTION: 40.0,
        }
        regime_score = regime_scores.get(regime, 25.0)

        # VaR component (0-40)
        var_score = min(40.0, var_level * 1000)

        # Drawdown component (0-20)
        dd_score = min(20.0, abs(drawdown) * 100)

        return regime_score + var_score + dd_score

    def should_trade(self, regime: RegimeType, var_level: float) -> bool:
        """Simple boolean check for trading.

        Args:
            regime: Current regime
            var_level: Current VaR

        Returns:
            True if trading allowed
        """
        result = self.evaluate(regime, var_level)
        return result.decision != TradingDecision.BLOCK

    def get_position_multiplier(self, regime: RegimeType) -> float:
        """Get position size multiplier for regime.

        Args:
            regime: Current regime

        Returns:
            Position size multiplier (0.5 to 1.2)
        """
        multipliers = {
            RegimeType.EXPANSION: 1.2,
            RegimeType.NEUTRAL: 1.0,
            RegimeType.CONTRACTION: 0.5,
        }
        return multipliers.get(regime, 1.0)


class AdaptiveRiskManager:
    """Adaptive risk management based on regime and VaR.

    Provides continuous risk parameters for strategy optimization.

    Example:
        >>> manager = AdaptiveRiskManager()
        >>> risk_pct = manager.get_risk_per_trade(RegimeType.EXPANSION, var_level=0.02)
        >>> print(f"Risk per trade: {risk_pct:.2%}")
    """

    def __init__(
        self,
        base_risk_pct: float = 0.02,
        max_risk_pct: float = 0.05,
        min_risk_pct: float = 0.005,
    ) -> None:
        """Initialize risk manager.

        Args:
            base_risk_pct: Base risk percentage per trade
            max_risk_pct: Maximum risk percentage
            min_risk_pct: Minimum risk percentage
        """
        self.base_risk_pct = base_risk_pct
        self.max_risk_pct = max_risk_pct
        self.min_risk_pct = min_risk_pct

    def get_risk_per_trade(
        self,
        regime: RegimeType,
        var_level: float,
        portfolio_var: float = 0.02,  # noqa: ARG002 - reserved for future use
    ) -> float:
        """Calculate risk per trade based on conditions.

        In favorable regimes (EXPANSION), we can risk more.
        In adverse regimes (CONTRACTION), we should risk less.

        Args:
            regime: Current regime
            var_level: Asset VaR
            portfolio_var: Portfolio VaR (reserved for future)

        Returns:
            Risk percentage per trade
        """
        # Invert multiplier: EXPANSION (0.8 risk) -> 1.25x position
        # CONTRACTION (1.5 risk) -> 0.67x position
        raw_multiplier = REGIME_RISK_MULTIPLIERS.get(regime, 1.0)
        regime_multiplier = 1.0 / raw_multiplier if raw_multiplier > 0 else 1.0

        # VaR-based adjustment
        var_multiplier = min(1.5, max(0.5, 0.02 / var_level)) if var_level > 0 else 1.0

        # Calculate adjusted risk
        adjusted_risk = self.base_risk_pct * regime_multiplier * var_multiplier

        # Clamp to bounds
        return max(self.min_risk_pct, min(self.max_risk_pct, adjusted_risk))

    def get_stop_loss(
        self,
        regime: RegimeType,
        var_level: float,
        base_stop: float = 0.02,
    ) -> float:
        """Calculate stop loss based on conditions.

        Args:
            regime: Current regime
            var_level: Asset VaR
            base_stop: Base stop loss percentage

        Returns:
            Stop loss percentage
        """
        # Wider stops in high volatility
        vol_adjustment = max(1.0, var_level / 0.02)

        # Tighter stops in contraction (protect capital)
        regime_adjustment = {
            RegimeType.EXPANSION: 1.2,
            RegimeType.NEUTRAL: 1.0,
            RegimeType.CONTRACTION: 0.8,
        }.get(regime, 1.0)

        return base_stop * vol_adjustment * regime_adjustment
