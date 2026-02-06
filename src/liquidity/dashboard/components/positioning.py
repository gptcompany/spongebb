"""COT Positioning panel component for CFTC positioning visualization.

Displays:
- Heatmap of current positioning percentiles by commodity and trader type
- Historical time series of net positions
- Extremes table highlighting crowded trades
"""

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

# Commodities tracked in COT
COT_COMMODITIES = ["WTI", "GOLD", "COPPER", "SILVER", "NATGAS"]

# Color palette for positioning
POSITIONING_COLORS = {
    "commercial": "#3D9970",  # Green (smart money)
    "speculator": "#FF4136",  # Red (speculators)
    "swap": "#0074D9",  # Blue (swap dealers)
    "extreme_long": "#01FF70",  # Bright green
    "extreme_short": "#FF4136",  # Bright red
}


def create_positioning_panel() -> dbc.Card:
    """Create the COT positioning panel.

    Contains:
    - Heatmap of current positioning percentiles
    - Time series of net positions
    - Table of current extremes

    Returns:
        Bootstrap Card with positioning visualization.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("📊 COT Positioning"),
                    html.Small(" (CFTC Weekly)", className="text-muted ms-2"),
                ]
            ),
            dbc.CardBody(
                [
                    # Heatmap section
                    html.Div(
                        [
                            html.H6(
                                "Current Positioning (52-Week Percentile)",
                                className="text-muted",
                            ),
                            dcc.Graph(
                                id="positioning-heatmap",
                                config={
                                    "displayModeBar": False,
                                    "displaylogo": False,
                                },
                                style={"height": "280px"},
                            ),
                        ],
                        className="mb-3",
                    ),
                    # Time series section
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H6(
                                        "Historical Net Positions",
                                        className="text-muted d-inline",
                                    ),
                                    dcc.Dropdown(
                                        id="positioning-commodity-select",
                                        options=[
                                            {"label": c, "value": c}
                                            for c in COT_COMMODITIES
                                        ],
                                        value="WTI",
                                        clearable=False,
                                        style={
                                            "width": "120px",
                                            "display": "inline-block",
                                            "marginLeft": "10px",
                                            "verticalAlign": "middle",
                                        },
                                    ),
                                ],
                                className="d-flex align-items-center mb-2",
                            ),
                            dcc.Graph(
                                id="positioning-timeseries",
                                config={
                                    "displayModeBar": False,
                                    "displaylogo": False,
                                },
                                style={"height": "250px"},
                            ),
                        ],
                        className="mb-3",
                    ),
                    # Extremes section
                    html.Div(
                        [
                            html.H6("Current Extremes", className="text-muted"),
                            html.Div(id="positioning-extremes-table"),
                        ]
                    ),
                ]
            ),
        ],
        className="h-100",
    )


def create_positioning_heatmap(data: pd.DataFrame | None = None) -> go.Figure:
    """Create heatmap showing current percentile ranks.

    Args:
        data: DataFrame with percentile series. If None, shows placeholder.

    Returns:
        Plotly figure with positioning heatmap.
    """
    commodities = COT_COMMODITIES
    categories = ["Speculator", "Commercial"]

    # Build matrix from data or use placeholder
    z = []
    if data is None or data.empty:
        # Placeholder data
        z = [[50, 50] for _ in commodities]
    else:
        for commodity in commodities:
            row = []
            for suffix in ["spec", "comm"]:
                series_id = f"cot_{commodity.lower()}_{suffix}_pctl"
                series_data = data[data["series_id"] == series_id]
                if not series_data.empty:
                    val = series_data.iloc[-1]["value"]
                else:
                    val = 50  # Default to neutral
                row.append(val)
            z.append(row)

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=categories,
            y=commodities,
            colorscale=[
                [0.0, "#FF4136"],  # Red (extreme short)
                [0.1, "#FF851B"],  # Orange
                [0.3, "#FFDC00"],  # Yellow
                [0.5, "#AAAAAA"],  # Gray (neutral)
                [0.7, "#2ECC40"],  # Light green
                [0.9, "#01FF70"],  # Lime
                [1.0, "#3D9970"],  # Dark green (extreme long)
            ],
            text=[[f"{v:.0f}%" for v in row] for row in z],
            texttemplate="%{text}",
            textfont={"size": 12, "color": "white"},
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1f}th percentile<extra></extra>",
            zmin=0,
            zmax=100,
            colorbar=dict(
                title="Percentile",
                tickvals=[0, 25, 50, 75, 100],
                ticktext=["0%", "25%", "50%", "75%", "100%"],
                len=0.8,
            ),
        )
    )

    fig.update_layout(
        xaxis_title="",
        yaxis_title="",
        margin=dict(l=70, r=20, t=10, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dee2e6"),
    )

    return fig


def create_positioning_timeseries(
    data: pd.DataFrame | None = None,
    commodity: str = "WTI",
) -> go.Figure:
    """Create time series of net positions.

    Args:
        data: DataFrame from CFTCCOTCollector.
        commodity: Commodity to display.

    Returns:
        Plotly figure with net position time series.
    """
    fig = go.Figure()

    if data is None or data.empty:
        # Empty placeholder
        fig.add_annotation(
            text="No data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color="#888888", size=14),
        )
    else:
        # Get series for this commodity
        comm_net = data[
            data["series_id"] == f"cot_{commodity.lower()}_comm_net"
        ].sort_values("timestamp")
        spec_net = data[
            data["series_id"] == f"cot_{commodity.lower()}_spec_net"
        ].sort_values("timestamp")

        if not comm_net.empty:
            fig.add_trace(
                go.Scatter(
                    x=comm_net["timestamp"],
                    y=comm_net["value"],
                    name="Commercial Net",
                    line=dict(color=POSITIONING_COLORS["commercial"], width=2),
                    fill="tozeroy",
                    fillcolor="rgba(61, 153, 112, 0.2)",
                )
            )

        if not spec_net.empty:
            fig.add_trace(
                go.Scatter(
                    x=spec_net["timestamp"],
                    y=spec_net["value"],
                    name="Speculator Net",
                    line=dict(color=POSITIONING_COLORS["speculator"], width=2),
                    fill="tozeroy",
                    fillcolor="rgba(255, 65, 54, 0.2)",
                )
            )

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)

    fig.update_layout(
        xaxis_title="",
        yaxis_title="Net Contracts",
        margin=dict(l=60, r=20, t=10, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dee2e6"),
        xaxis=dict(gridcolor="rgba(128,128,128,0.2)"),
        yaxis=dict(gridcolor="rgba(128,128,128,0.2)"),
    )

    return fig


def create_extremes_table(extremes: pd.DataFrame | None = None) -> html.Div:
    """Create table showing current extreme conditions.

    Args:
        extremes: DataFrame with extreme conditions.

    Returns:
        HTML div with extremes table or "no extremes" message.
    """
    if extremes is None or extremes.empty:
        return html.P(
            "No extreme positioning detected",
            className="text-muted fst-italic text-center",
        )

    # Build table rows
    rows = []
    for _, row in extremes.iterrows():
        spec_pctl = row.get("spec_percentile", 50)
        comm_pctl = row.get("comm_percentile", 50)

        # Determine severity color
        is_critical = spec_pctl >= 95 or spec_pctl <= 5 or comm_pctl >= 95 or comm_pctl <= 5
        badge_class = "danger" if is_critical else "warning"
        icon = "🚨" if is_critical else "⚠️"

        rows.append(
            html.Tr(
                [
                    html.Td(row.get("commodity", "N/A")),
                    html.Td(
                        dbc.Badge(
                            row.get("extreme_type", "UNKNOWN").replace("_", " "),
                            color=badge_class,
                            className="text-uppercase",
                        )
                    ),
                    html.Td(f"{spec_pctl:.1f}%"),
                    html.Td(f"{comm_pctl:.1f}%"),
                    html.Td(icon),
                ]
            )
        )

    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Commodity"),
                        html.Th("Alert Type"),
                        html.Th("Spec %ile"),
                        html.Th("Comm %ile"),
                        html.Th(""),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        bordered=True,
        hover=True,
        responsive=True,
        striped=True,
        size="sm",
        className="mb-0",
    )
