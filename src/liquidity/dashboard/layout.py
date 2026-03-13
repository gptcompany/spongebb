"""Main dashboard layout composition.

Assembles all components into the complete dashboard layout:
- Header with navigation
- Status bar
- Liquidity panels (Net + Global)
- Analysis panels (Regime + Correlations)
- Extended panels (FX, Stress, Commodities, Flows)
- News panel (Central Bank communications)
- FOMC Statement Diff panel (Phase 14)
- EIA Weekly Petroleum panel (Phase 16)
- Inflation Expectations panel (Phase 19)
- Calendar strip
- Auto-refresh interval
"""

import dash_bootstrap_components as dbc
from dash import dcc, html

from liquidity.dashboard.components.calendar import create_calendar_strip
from liquidity.dashboard.components.commodities import create_commodities_panel
from liquidity.dashboard.components.consumer_credit import create_consumer_credit_panel
from liquidity.dashboard.components.correlations import create_correlation_panel
from liquidity.dashboard.components.eia_panel import create_eia_panel
from liquidity.dashboard.components.flows import create_flows_panel
from liquidity.dashboard.components.fomc_diff import create_fomc_diff_panel
from liquidity.dashboard.components.fx import create_fx_panel
from liquidity.dashboard.components.header import create_header, create_status_bar
from liquidity.dashboard.components.inflation import create_inflation_panel
from liquidity.dashboard.components.liquidity import create_liquidity_panel
from liquidity.dashboard.components.news import create_news_panel
from liquidity.dashboard.components.quality import create_quality_detail_panel
from liquidity.dashboard.components.regime import create_regime_panel
from liquidity.dashboard.components.stress import create_stress_panel


def create_layout() -> html.Div:
    """Create the main dashboard layout.

    Layout structure:
    +---------------------------------------------------------+
    | Header: Global Liquidity Monitor   [Refresh] [Export]    |
    +---------------------------------------------------------+
    | Data Quality: 98% | Last Update: 5 min ago | Regime: UP  |
    +---------------------------------------------------------+
    | +------------------+  +------------------+               |
    | | Net Liquidity    |  | Global Liquidity |               |
    | | [Chart]          |  | [Chart]          |               |
    | +------------------+  +------------------+               |
    +---------------------------------------------------------+
    | +------------------+  +------------------+               |
    | | Regime Panel     |  | Correlation Heat |               |
    | | [EXPANSION]      |  | [Heatmap]        |               |
    | +------------------+  +------------------+               |
    +---------------------------------------------------------+
    | +--------+ +--------+ +--------+ +--------+              |
    | |  FX    | | Stress | | Cmdty  | | Flows  |              |
    | | [DXY]  | | [SOFR] | | [Gold] | | [TIC]  |              |
    | +--------+ +--------+ +--------+ +--------+              |
    +---------------------------------------------------------+
    | +----------------------+ +----------------------+        |
    | | Central Bank News    | | FOMC Statement Diff  |        |
    | | [Fed] [ECB] [BoJ]    | | [Dec 2024] [Jan 2025]|        |
    | | * Headlines...       | | HAWKISH (+0.35)      |        |
    | +----------------------+ +----------------------+        |
    +---------------------------------------------------------+
    | Calendar: [Treasury Auction Feb 10] [FOMC Feb 28]        |
    +---------------------------------------------------------+

    Returns:
        Root Div containing the complete dashboard layout.
    """
    return html.Div(
        [
            # Header
            create_header(),
            # Main content container
            dbc.Container(
                [
                    # Status bar
                    create_status_bar(),
                    # Quality status bar (QA-08, QA-09)
                    html.Div(id="quality-status-bar", className="mb-2"),
                    # Quality detail panel (collapsible)
                    create_quality_detail_panel(),
                    # Main liquidity charts row
                    create_liquidity_panel(),
                    # Separator
                    html.Hr(className="my-3"),
                    # Analysis panels row (Regime + Correlations)
                    dbc.Row(
                        [
                            # Regime panel
                            dbc.Col(
                                create_regime_panel(),
                                xs=12,
                                md=6,
                            ),
                            # Correlation heatmap panel
                            dbc.Col(
                                create_correlation_panel(),
                                xs=12,
                                md=6,
                            ),
                        ],
                        className="mb-4",
                    ),
                    # Consumer credit risk panel (Phase 20)
                    dbc.Row(
                        [
                            dbc.Col(
                                create_consumer_credit_panel(),
                                width=12,
                            ),
                        ],
                        className="mb-4",
                    ),
                    # Separator
                    html.Hr(className="my-3"),
                    # Extended panels row (FX, Stress, Commodities, Flows)
                    dbc.Row(
                        [
                            # FX panel
                            dbc.Col(
                                create_fx_panel(),
                                xs=12,
                                md=6,
                                lg=3,
                            ),
                            # Stress panel
                            dbc.Col(
                                create_stress_panel(),
                                xs=12,
                                md=6,
                                lg=3,
                            ),
                            # Commodities panel
                            dbc.Col(
                                create_commodities_panel(),
                                xs=12,
                                md=6,
                                lg=3,
                            ),
                            # Capital flows panel
                            dbc.Col(
                                create_flows_panel(),
                                xs=12,
                                md=6,
                                lg=3,
                            ),
                        ],
                        className="mb-4",
                    ),
                    # Separator
                    html.Hr(className="my-3"),
                    # News and FOMC Diff row (Phase 14)
                    dbc.Row(
                        [
                            # Central Bank News panel
                            dbc.Col(
                                create_news_panel(),
                                xs=12,
                                md=6,
                            ),
                            # FOMC Statement Diff panel (Plan 14-08)
                            dbc.Col(
                                create_fomc_diff_panel(),
                                xs=12,
                                md=6,
                            ),
                        ],
                        className="mb-4",
                    ),
                    # Separator
                    html.Hr(className="my-3"),
                    # EIA Weekly Petroleum and Inflation row (Phase 16, 19)
                    dbc.Row(
                        [
                            # EIA Oil Data panel
                            dbc.Col(
                                create_eia_panel(),
                                xs=12,
                                md=6,
                            ),
                            # Inflation Expectations panel (Phase 19)
                            dbc.Col(
                                create_inflation_panel(),
                                xs=12,
                                md=6,
                            ),
                        ],
                        className="mb-4",
                    ),
                    # Separator
                    html.Hr(className="my-3"),
                    # Calendar strip
                    create_calendar_strip(),
                    # Loading indicator
                    dbc.Spinner(
                        html.Div(id="loading-output"),
                        color="primary",
                        type="border",
                        fullscreen=False,
                    ),
                ],
                fluid=True,
                className="px-4",
            ),
            # Auto-refresh interval (5 minutes = 300000ms)
            dcc.Interval(
                id="refresh-interval",
                interval=5 * 60 * 1000,  # 5 minutes in milliseconds
                n_intervals=0,
            ),
            # Store for data caching
            dcc.Store(id="dashboard-data-store"),
            # Store for FOMC statement dates (Phase 14)
            dcc.Store(id="fomc-dates-store"),
            # Download component for HTML export
            dcc.Download(id="download-html"),
            # Download component for export button (export-download)
            dcc.Download(id="export-download"),
        ]
    )
