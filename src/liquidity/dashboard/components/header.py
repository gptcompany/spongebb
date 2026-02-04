"""Header component for the dashboard.

Provides navigation bar with:
- Dashboard title
- Refresh button (manual data refresh)
- Export HTML button
"""

import dash_bootstrap_components as dbc
from dash import html


def create_header() -> dbc.Navbar:
    """Create the dashboard header/navigation bar.

    Returns:
        Bootstrap Navbar component with title and action buttons.
    """
    return dbc.Navbar(
        dbc.Container(
            [
                # Brand/Title
                dbc.Row(
                    [
                        dbc.Col(
                            html.I(className="bi bi-graph-up-arrow me-2"),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.NavbarBrand(
                                "Global Liquidity Monitor",
                                className="ms-2",
                                style={"fontWeight": "600", "fontSize": "1.25rem"},
                            ),
                        ),
                    ],
                    align="center",
                    className="g-0",
                ),
                # Action buttons
                dbc.Nav(
                    [
                        dbc.NavItem(
                            dbc.Button(
                                [
                                    html.I(className="bi bi-arrow-clockwise me-1"),
                                    "Refresh",
                                ],
                                id="refresh-btn",
                                color="primary",
                                size="sm",
                                className="me-2",
                            ),
                        ),
                        dbc.NavItem(
                            dbc.Button(
                                [
                                    html.I(className="bi bi-download me-1"),
                                    "Export",
                                ],
                                id="export-btn",
                                color="secondary",
                                size="sm",
                                outline=True,
                            ),
                        ),
                    ],
                    className="ms-auto",
                    navbar=True,
                ),
            ],
            fluid=True,
        ),
        color="dark",
        dark=True,
        sticky="top",
        className="mb-3",
    )


def create_status_bar() -> html.Div:
    """Create the status bar showing data quality and last update time.

    Returns:
        Div containing status indicators.
    """
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Span(
                            [
                                html.Strong("Last Update: ", className="text-muted"),
                                html.Span(id="last-update-time", children="--"),
                            ]
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        html.Span(
                            [
                                html.Strong("Data Quality: ", className="text-muted"),
                                html.Span(id="data-quality-score", children="--"),
                            ]
                        ),
                        width="auto",
                    ),
                    dbc.Col(
                        html.Span(
                            [
                                html.Strong("Auto-refresh: ", className="text-muted"),
                                html.Span("5 min", className="text-info"),
                            ]
                        ),
                        width="auto",
                    ),
                ],
                className="g-3",
            ),
        ],
        className="status-bar",
        id="status-bar",
    )
