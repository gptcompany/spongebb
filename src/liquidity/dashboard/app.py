"""Dash application setup and configuration.

Creates the core Dash app with dark theme (DARKLY) and proper settings
for the Global Liquidity Monitor dashboard.
"""

import dash_bootstrap_components as dbc
from dash import Dash

# Create the Dash app with Bootstrap dark theme
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Global Liquidity Monitor",
    update_title="Updating...",
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1.0"},
    ],
)

# Server instance for production deployment (WSGI)
server = app.server

# Custom CSS for dashboard styling
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Custom dashboard styles */
            body {
                background-color: #222;
            }
            .card {
                background-color: #2d2d2d;
                border: 1px solid #444;
            }
            .card-header {
                background-color: #333;
                border-bottom: 1px solid #444;
                font-weight: 600;
            }
            .regime-expansion {
                color: #00ff88;
                font-weight: bold;
            }
            .regime-contraction {
                color: #ff4444;
                font-weight: bold;
            }
            .metric-value {
                font-size: 1.5rem;
                font-weight: 600;
            }
            .metric-delta-positive {
                color: #00ff88;
            }
            .metric-delta-negative {
                color: #ff4444;
            }
            .status-bar {
                background-color: #1a1a1a;
                padding: 0.5rem 1rem;
                border-radius: 4px;
                margin-bottom: 1rem;
            }
            .navbar {
                background-color: #1a1a1a !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""
