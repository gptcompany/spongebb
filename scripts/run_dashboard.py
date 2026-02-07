#!/usr/bin/env python3
"""Run the dashboard with real data.

Usage:
    # With dotenvx (recommended):
    dotenvx run -f /media/sam/1TB/.env -- python scripts/run_dashboard.py

    # Or with env vars:
    FRED_API_KEY=xxx python scripts/run_dashboard.py
"""

import logging
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run the dashboard."""
    # Configure OpenBB credentials first
    from liquidity.config import configure_openbb_credentials

    if configure_openbb_credentials():
        logger.info("OpenBB credentials configured successfully")
    else:
        logger.warning("OpenBB credentials not configured - will use mock data")

    # Import and create app
    from dash import Dash

    from liquidity.dashboard.callbacks import register_callbacks
    from liquidity.dashboard.layout import create_layout

    app = Dash(__name__)
    app.layout = create_layout()

    # Register all callbacks (includes EIA and Inflation callbacks)
    register_callbacks(app)

    logger.info("Dashboard starting on http://localhost:8050")
    app.run(debug=False, port=8050, host="0.0.0.0")


if __name__ == "__main__":
    main()
