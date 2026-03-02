"""API routers for SpongeBB.

Provides modular endpoint organization:
- liquidity: Net and Global liquidity endpoints
- regime: Regime classification endpoints
- metrics: Stealth QE and other metrics
- volatility: MOVE Z-Score, VIX Term Structure, composite signal
- fx: DXY and FX pairs
- stress: Funding market stress indicators
- correlations: Asset-liquidity correlations
- calendar: Liquidity-impacting events
"""

from liquidity.api.routers.calendar import router as calendar_router
from liquidity.api.routers.correlations import router as correlations_router
from liquidity.api.routers.fx import router as fx_router
from liquidity.api.routers.liquidity import router as liquidity_router
from liquidity.api.routers.metrics import router as metrics_router
from liquidity.api.routers.regime import router as regime_router
from liquidity.api.routers.stress import router as stress_router
from liquidity.api.routers.volatility import router as volatility_router

__all__ = [
    "liquidity_router",
    "regime_router",
    "metrics_router",
    "volatility_router",
    "fx_router",
    "stress_router",
    "correlations_router",
    "calendar_router",
]
