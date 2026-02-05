"""Risk metrics module for portfolio risk management.

Provides VaR, CVaR, regime-conditional risk metrics, and NautilusTrader integration.
"""

from .cvar import CVaRResult, ExpectedShortfall
from .liquidity_adjusted import (
    DEFAULT_LIQUIDITY_PARAMS,
    LAVaRResult,
    LiquidityAdjustedRisk,
    LiquidityParams,
)
from .macro_filter import (
    AdaptiveRiskManager,
    FilterResult,
    LiquidityRiskFilter,
    TradingDecision,
)
from .regime_var import (
    REGIME_RISK_MULTIPLIERS,
    RegimeConditionalVaR,
    RegimeType,
    RegimeVaRResult,
    WeightedVaRResult,
)
from .var.historical import HistoricalVaR, VaRResult
from .var.parametric import Distribution, ParametricVaR, ParametricVaRResult

__all__ = [
    # VaR
    "HistoricalVaR",
    "VaRResult",
    "ParametricVaR",
    "ParametricVaRResult",
    "Distribution",
    # CVaR
    "ExpectedShortfall",
    "CVaRResult",
    # Liquidity-Adjusted
    "LiquidityAdjustedRisk",
    "LiquidityParams",
    "LAVaRResult",
    "DEFAULT_LIQUIDITY_PARAMS",
    # Regime-Conditional
    "RegimeConditionalVaR",
    "RegimeType",
    "RegimeVaRResult",
    "WeightedVaRResult",
    "REGIME_RISK_MULTIPLIERS",
    # Macro Filter
    "LiquidityRiskFilter",
    "AdaptiveRiskManager",
    "TradingDecision",
    "FilterResult",
]
