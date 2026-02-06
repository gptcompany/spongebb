"""Dashboard callbacks package.

Contains callback modules for different dashboard panels:
- callbacks_main: Main dashboard callbacks (liquidity, regime, extended panels)
- eia_callbacks: EIA Weekly Petroleum panel callbacks (Phase 16)
"""

from liquidity.dashboard.callbacks_main import (
    register_callbacks,
    _get_error_response,
    _get_mock_data,
    _get_mock_extended_data,
)
from liquidity.dashboard.callbacks.eia_callbacks import register_eia_callbacks

__all__ = [
    "register_callbacks",
    "register_eia_callbacks",
    "_get_error_response",
    "_get_mock_data",
    "_get_mock_extended_data",
]
