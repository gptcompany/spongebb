"""Plotly Dash dashboard for Global Liquidity Monitor.

This module provides interactive visualization of:
- Net Liquidity Index (Fed balance sheet)
- Global Liquidity Index (multi-CB aggregate)
- Regime classification with color coding

Usage:
    # Start the dashboard server
    from liquidity.dashboard import run_server
    run_server(debug=True, port=8050)

    # Or via command line
    python -m liquidity.dashboard
"""

from liquidity.dashboard.app import app, server
from liquidity.dashboard.callbacks import register_callbacks
from liquidity.dashboard.export import HTMLExporter
from liquidity.dashboard.layout import create_layout

# Note: Layout and callbacks are NOT auto-registered here.
# Each script should explicitly set app.layout and register callbacks
# to avoid duplicate registration issues.


def run_server(debug: bool = False, port: int = 8050, host: str = "0.0.0.0") -> None:  # nosec B104
    """Run the Dash dashboard server.

    Args:
        debug: Enable debug mode with hot-reloading.
        port: Server port. Defaults to 8050.
        host: Server host. Defaults to 0.0.0.0.
    """
    app.run(debug=debug, port=port, host=host)


__all__ = [
    "app",
    "server",
    "run_server",
    "HTMLExporter",
    "register_callbacks",
    "create_layout",
]
