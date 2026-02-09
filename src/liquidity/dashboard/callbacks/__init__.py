"""Dashboard callbacks package.

Contains callback modules for different dashboard panels:
- callbacks_main: Main dashboard callbacks (liquidity, regime, extended panels)
- eia_callbacks: EIA Weekly Petroleum panel callbacks (Phase 16)
- inflation_callbacks: Inflation expectations panel callbacks (Phase 19)
"""

from liquidity.dashboard.callbacks.eia_callbacks import register_eia_callbacks
from liquidity.dashboard.callbacks.inflation_callbacks import register_inflation_callbacks
from liquidity.dashboard.callbacks_main import (
    _get_error_response,
    register_callbacks,
)

__all__ = [
    "register_callbacks",
    "register_eia_callbacks",
    "register_inflation_callbacks",
    "_get_error_response",
]
