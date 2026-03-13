"""Liquidity chart components for Net and Global Liquidity visualization.

Provides:
- Net Liquidity time series with WALCL, TGA, RRP breakdown
- Global Liquidity with Central Bank breakdown (Fed, ECB, BoJ, PBoC)
"""


import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

# Color palette for charts (dark theme compatible)
COLORS = {
    "net_liquidity": "#00ff88",  # Green
    "walcl": "#4dabf7",  # Blue
    "tga": "#ff6b6b",  # Red
    "rrp": "#ffd43b",  # Yellow
    "fed": "#00ff88",  # Green
    "ecb": "#4dabf7",  # Blue
    "boj": "#ff6b6b",  # Red
    "pboc": "#ffd43b",  # Yellow
    "global": "#ffffff",  # White for total
}


def create_net_liquidity_chart(
    data: pd.DataFrame | None = None,
    show_components: bool = True,
    show_bounds: bool = False,
) -> go.Figure:
    """Create Net Liquidity time series chart.

    Net Liquidity = WALCL - TGA - RRP (Hayes formula)

    Args:
        data: DataFrame with columns: timestamp, net_liquidity, walcl, tga, rrp.
            If None, creates an empty placeholder chart.
        show_components: Whether to show WALCL, TGA, RRP breakdown lines.
        show_bounds: Whether to show historical min/max bounds (QA-10).

    Returns:
        Plotly Figure with Net Liquidity time series.
    """
    fig = go.Figure()

    if data is not None and not data.empty:
        # Main Net Liquidity line
        fig.add_trace(
            go.Scatter(
                x=data["timestamp"],
                y=data["net_liquidity"],
                name="Net Liquidity",
                line=dict(color=COLORS["net_liquidity"], width=2),
                fill="tozeroy",
                fillcolor="rgba(0, 255, 136, 0.1)",
            )
        )

        if show_components:
            # Component lines (secondary, dashed)
            fig.add_trace(
                go.Scatter(
                    x=data["timestamp"],
                    y=data["walcl"],
                    name="WALCL (Fed Assets)",
                    line=dict(color=COLORS["walcl"], width=1, dash="dot"),
                    visible="legendonly",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=data["timestamp"],
                    y=data["tga"],
                    name="TGA (Treasury)",
                    line=dict(color=COLORS["tga"], width=1, dash="dot"),
                    visible="legendonly",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=data["timestamp"],
                    y=data["rrp"],
                    name="RRP (Reverse Repo)",
                    line=dict(color=COLORS["rrp"], width=1, dash="dot"),
                    visible="legendonly",
                )
            )

    # Layout configuration
    fig.update_layout(
        template="plotly_dark",
        title=None,  # Title is in card header
        xaxis_title=None,
        yaxis_title="USD (Billions)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=60, r=20, t=30, b=40),
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    # Grid styling
    fig.update_xaxes(
        gridcolor="rgba(255,255,255,0.1)",
        showgrid=True,
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.1)",
        showgrid=True,
        tickformat=",.0f",
    )

    # Add sanity bounds if enabled (QA-10)
    if show_bounds:
        from liquidity.dashboard.components.bounds import SanityBounds

        fig = SanityBounds.add_bounds(fig, "net_liquidity")

    return fig


def create_global_liquidity_chart(
    data: pd.DataFrame | None = None,
    show_breakdown: bool = True,
    show_bounds: bool = False,
) -> go.Figure:
    """Create Global Liquidity time series chart with CB breakdown.

    Global Liquidity = Fed + ECB + BoJ + PBoC (in USD)

    Args:
        data: DataFrame with columns: timestamp, global_liquidity, fed_usd,
            ecb_usd, boj_usd, pboc_usd. If None, creates placeholder.
        show_breakdown: Whether to show individual CB contributions.
        show_bounds: Whether to show historical min/max bounds (QA-10).

    Returns:
        Plotly Figure with stacked area or line chart.
    """
    fig = go.Figure()

    if data is not None and not data.empty:
        if show_breakdown:
            # Stacked area chart for CB breakdown
            cb_cols = ["fed_usd", "ecb_usd", "boj_usd", "pboc_usd"]
            cb_names = ["Fed (US)", "ECB (EU)", "BoJ (Japan)", "PBoC (China)"]
            cb_colors = [COLORS["fed"], COLORS["ecb"], COLORS["boj"], COLORS["pboc"]]

            for col, name, color in zip(cb_cols, cb_names, cb_colors, strict=False):
                if col in data.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=data["timestamp"],
                            y=data[col],
                            name=name,
                            stackgroup="cbs",
                            fillcolor=_hex_to_rgba(color, 0.4),
                            line=dict(color=color, width=1),
                        )
                    )
        else:
            # Simple line for total
            fig.add_trace(
                go.Scatter(
                    x=data["timestamp"],
                    y=data["global_liquidity"],
                    name="Global Liquidity",
                    line=dict(color=COLORS["global"], width=2),
                    fill="tozeroy",
                    fillcolor="rgba(255,255,255,0.1)",
                )
            )

    # Layout configuration
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=None,
        yaxis_title="USD (Billions)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=60, r=20, t=30, b=40),
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    # Grid styling
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.1)",
        showgrid=True,
        tickformat=",.0f",
    )

    # Add sanity bounds if enabled (QA-10)
    if show_bounds:
        from liquidity.dashboard.components.bounds import SanityBounds

        fig = SanityBounds.add_bounds(fig, "global_liquidity")

    return fig


def create_liquidity_panel() -> dbc.Row:
    """Create the liquidity panel with Net and Global Liquidity charts.

    Returns:
        Bootstrap Row with two Card components containing charts.
    """
    return dbc.Row(
        [
            # Net Liquidity Card
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.Span("Net Liquidity Index"),
                                html.Small(
                                    " (WALCL - TGA - RRP)",
                                    className="text-muted ms-2",
                                ),
                            ]
                        ),
                        dbc.CardBody(
                            [
                                dcc.Graph(
                                    id="net-liquidity-chart",
                                    config={
                                        "displayModeBar": True,
                                        "displaylogo": False,
                                        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                                    },
                                ),
                                html.Div(id="net-liquidity-metrics", className="mt-2"),
                            ]
                        ),
                    ]
                ),
                xs=12,
                md=6,
            ),
            # Global Liquidity Card
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(
                            [
                                html.Span("Global Liquidity Index"),
                                html.Small(
                                    " (Fed + ECB + BoJ + PBoC)",
                                    className="text-muted ms-2",
                                ),
                            ]
                        ),
                        dbc.CardBody(
                            [
                                dcc.Graph(
                                    id="global-liquidity-chart",
                                    config={
                                        "displayModeBar": True,
                                        "displaylogo": False,
                                        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                                    },
                                ),
                                html.Div(id="global-liquidity-metrics", className="mt-2"),
                            ]
                        ),
                    ]
                ),
                xs=12,
                md=6,
            ),
        ],
        className="mb-4",
    )


def _delta_col(label: str, value: float, width: int = 2) -> dbc.Col:
    """Create a single delta column."""
    sign = "+" if value >= 0 else ""
    cls = "metric-delta-positive" if value >= 0 else "metric-delta-negative"
    return dbc.Col(
        [
            html.Small(label, className="text-muted d-block"),
            html.Span(f"{sign}${value:,.0f}B", className=cls),
        ],
        width=width,
    )


def create_liquidity_metrics(
    current_value: float,
    weekly_delta: float,
    monthly_delta: float,
    delta_60d: float = 0.0,
    delta_90d: float = 0.0,
    label: str = "Current",
) -> html.Div:
    """Create metrics display for liquidity values.

    Args:
        current_value: Current liquidity value in billions.
        weekly_delta: Weekly change in billions.
        monthly_delta: Monthly change in billions.
        delta_60d: 60-day change in billions.
        delta_90d: 90-day change in billions.
        label: Label for the current value.

    Returns:
        Div with formatted metrics.
    """
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Small(label, className="text-muted d-block"),
                            html.Span(
                                f"${current_value:,.0f}B",
                                className="metric-value",
                            ),
                        ],
                        width=4,
                    ),
                    _delta_col("7d Δ", weekly_delta),
                    _delta_col("30d Δ", monthly_delta),
                    _delta_col("60d Δ", delta_60d),
                    _delta_col("90d Δ", delta_90d),
                ]
            ),
        ]
    )


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert hex color to rgba string.

    Args:
        hex_color: Hex color string (e.g., "#00ff88").
        alpha: Alpha transparency (0-1).

    Returns:
        RGBA color string.
    """
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"
