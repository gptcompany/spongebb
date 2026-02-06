"""EIA Weekly Petroleum panel component.

Displays EIA oil data with tabbed interface:
- Cushing: Inventory chart with 52-week range band + utilization badge
- Refinery: Utilization chart by PADD + signal badge
- Supply: Production and imports charts
"""

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

# Color palette for EIA charts
EIA_COLORS = {
    "cushing": "#4dabf7",  # Blue for inventory
    "capacity": "#ff6b6b",  # Red for capacity line
    "range_band": "rgba(0, 100, 80, 0.2)",  # Green semi-transparent for range
    "us_total": "#00ff88",  # Green for US total
    "padd1": "#ffaa00",  # Orange for East Coast
    "padd3": "#4dabf7",  # Blue for Gulf Coast
    "padd5": "#ff6b6b",  # Red for West Coast
    "production": "#00ff88",  # Green for production
    "imports": "#ffd43b",  # Gold for imports
}

# Cushing capacity in thousand barrels
CUSHING_CAPACITY_KB = 70_800

# Utilization signal thresholds (percent)
UTILIZATION_THRESHOLDS = {
    "TIGHT": 95.0,
    "NORMAL": 90.0,
    "SOFT": 85.0,
}


def create_eia_panel() -> dbc.Card:
    """Create EIA oil data dashboard panel.

    Contains tabs for:
    - Cushing: Inventory with capacity line and 52-week range
    - Refinery: Utilization by PADD region
    - Supply: Production and imports

    Returns:
        Bootstrap Card with tabbed EIA charts.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("EIA Weekly Petroleum"),
                    html.Small(" (Oil Market)", className="text-muted ms-2"),
                ]
            ),
            dbc.CardBody(
                [
                    dbc.Tabs(
                        [
                            dbc.Tab(
                                [
                                    dcc.Graph(
                                        id="cushing-inventory-chart",
                                        config={
                                            "displayModeBar": False,
                                            "displaylogo": False,
                                        },
                                        style={"height": "200px"},
                                    ),
                                    html.Div(
                                        id="cushing-utilization-badge",
                                        className="text-center mt-2",
                                    ),
                                ],
                                label="Cushing",
                                tab_id="tab-cushing",
                            ),
                            dbc.Tab(
                                [
                                    dcc.Graph(
                                        id="refinery-utilization-chart",
                                        config={
                                            "displayModeBar": False,
                                            "displaylogo": False,
                                        },
                                        style={"height": "200px"},
                                    ),
                                    html.Div(
                                        id="refinery-signal-badge",
                                        className="text-center mt-2",
                                    ),
                                ],
                                label="Refinery",
                                tab_id="tab-refinery",
                            ),
                            dbc.Tab(
                                [
                                    dcc.Graph(
                                        id="crude-production-chart",
                                        config={
                                            "displayModeBar": False,
                                            "displaylogo": False,
                                        },
                                        style={"height": "100px"},
                                    ),
                                    dcc.Graph(
                                        id="crude-imports-chart",
                                        config={
                                            "displayModeBar": False,
                                            "displaylogo": False,
                                        },
                                        style={"height": "100px"},
                                    ),
                                ],
                                label="Supply",
                                tab_id="tab-supply",
                            ),
                        ],
                        id="eia-tabs",
                        active_tab="tab-cushing",
                    ),
                ]
            ),
        ]
    )


def create_cushing_chart(df: pd.DataFrame | None = None) -> go.Figure:
    """Create Cushing inventory chart with 52-week range band and capacity line.

    Args:
        df: DataFrame with columns: timestamp, value (inventory in thousand barrels).
            Should contain at least 52 weeks of data for range band.

    Returns:
        Plotly Figure with Cushing inventory chart.
    """
    fig = go.Figure()

    if df is not None and not df.empty:
        # Find value and timestamp columns
        value_col = _find_column(df, ["value", "inventory", "cushing"])
        timestamp_col = _find_column(df, ["timestamp", "date", "Date", "index"])

        if value_col and timestamp_col:
            values = df[value_col]
            timestamps = df[timestamp_col]

            # Calculate 52-week rolling min/max for range band
            if len(values) >= 52:
                rolling_min = values.rolling(52, min_periods=1).min()
                rolling_max = values.rolling(52, min_periods=1).max()

                # Add range band (fill between min and max)
                fig.add_trace(
                    go.Scatter(
                        x=pd.concat([timestamps, timestamps[::-1]]),
                        y=pd.concat([rolling_max, rolling_min[::-1]]),
                        fill="toself",
                        fillcolor=EIA_COLORS["range_band"],
                        line=dict(color="rgba(0,0,0,0)"),
                        name="52-week range",
                        showlegend=True,
                        hoverinfo="skip",
                    )
                )

            # Add current inventory line
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=values,
                    name="Inventory",
                    line=dict(color=EIA_COLORS["cushing"], width=2),
                    mode="lines",
                )
            )

            # Add capacity line
            fig.add_hline(
                y=CUSHING_CAPACITY_KB,
                line_dash="dash",
                line_color=EIA_COLORS["capacity"],
                annotation_text="Capacity (70.8M bbl)",
                annotation_position="top right",
                annotation=dict(font_size=10, font_color=EIA_COLORS["capacity"]),
            )

    # Layout
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=None,
        yaxis_title="K barrels",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
        margin=dict(l=60, r=20, t=30, b=30),
        height=200,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True, tickformat=",")

    return fig


def create_refinery_chart(df: pd.DataFrame | None = None) -> go.Figure:
    """Create refinery utilization chart by PADD region.

    Shows utilization rates for US total and major PADD regions:
    - US Total (WPULEUS3)
    - PADD 1 - East Coast (W_NA_YUP_R10_PER)
    - PADD 3 - Gulf Coast (W_NA_YUP_R30_PER)
    - PADD 5 - West Coast (W_NA_YUP_R50_PER)

    Args:
        df: DataFrame with columns: timestamp, series_id, value.
            series_id should contain PADD region identifiers.

    Returns:
        Plotly Figure with refinery utilization chart.
    """
    fig = go.Figure()

    # Series ID to display name and color mapping
    series_config = {
        "WPULEUS3": ("US Total", EIA_COLORS["us_total"]),
        "W_NA_YUP_R10_PER": ("PADD 1 (East)", EIA_COLORS["padd1"]),
        "W_NA_YUP_R30_PER": ("PADD 3 (Gulf)", EIA_COLORS["padd3"]),
        "W_NA_YUP_R50_PER": ("PADD 5 (West)", EIA_COLORS["padd5"]),
    }

    if df is not None and not df.empty:
        # Find required columns
        timestamp_col = _find_column(df, ["timestamp", "date", "Date", "index"])
        value_col = _find_column(df, ["value", "utilization"])
        series_col = _find_column(df, ["series_id", "series", "region"])

        if timestamp_col and value_col and series_col:
            for series_id, (name, color) in series_config.items():
                series_df = df[df[series_col] == series_id].copy()
                if not series_df.empty:
                    series_df = series_df.sort_values(timestamp_col)
                    fig.add_trace(
                        go.Scatter(
                            x=series_df[timestamp_col],
                            y=series_df[value_col],
                            name=name,
                            line=dict(color=color, width=2),
                            mode="lines",
                        )
                    )

    # Add threshold reference lines
    fig.add_hline(
        y=UTILIZATION_THRESHOLDS["TIGHT"],
        line_dash="dot",
        line_color="rgba(255, 68, 68, 0.5)",
        annotation_text="Tight (95%)",
        annotation_position="right",
        annotation=dict(font_size=9, font_color="#ff4444"),
    )
    fig.add_hline(
        y=UTILIZATION_THRESHOLDS["NORMAL"],
        line_dash="dot",
        line_color="rgba(255, 170, 0, 0.5)",
        annotation_text="Normal (90%)",
        annotation_position="right",
        annotation=dict(font_size=9, font_color="#ffaa00"),
    )

    # Layout
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=None,
        yaxis_title="Utilization %",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
        margin=dict(l=60, r=20, t=30, b=30),
        height=200,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.1)",
        showgrid=True,
        range=[75, 100],  # Focus on relevant range
    )

    return fig


def create_supply_chart(
    production_df: pd.DataFrame | None = None,
    imports_df: pd.DataFrame | None = None,
) -> tuple[go.Figure, go.Figure]:
    """Create production and imports charts.

    Args:
        production_df: DataFrame with columns: timestamp, value (thousand b/d).
        imports_df: DataFrame with columns: timestamp, value (thousand b/d).

    Returns:
        Tuple of (production_figure, imports_figure).
    """
    production_fig = _create_single_supply_chart(
        production_df,
        title="Production",
        color=EIA_COLORS["production"],
        y_label="K b/d",
    )

    imports_fig = _create_single_supply_chart(
        imports_df,
        title="Imports",
        color=EIA_COLORS["imports"],
        y_label="K b/d",
    )

    return production_fig, imports_fig


def _create_single_supply_chart(
    df: pd.DataFrame | None,
    title: str,
    color: str,
    y_label: str,
) -> go.Figure:
    """Create a single supply metric chart.

    Args:
        df: DataFrame with timestamp and value columns.
        title: Chart title.
        color: Line color.
        y_label: Y-axis label.

    Returns:
        Plotly Figure.
    """
    fig = go.Figure()

    if df is not None and not df.empty:
        value_col = _find_column(df, ["value", "production", "imports"])
        timestamp_col = _find_column(df, ["timestamp", "date", "Date", "index"])

        if value_col and timestamp_col:
            fig.add_trace(
                go.Scatter(
                    x=df[timestamp_col],
                    y=df[value_col],
                    name=title,
                    line=dict(color=color, width=2),
                    fill="tozeroy",
                    fillcolor=f"rgba{_hex_to_rgb(color) + (0.1,)}",
                )
            )

    fig.update_layout(
        template="plotly_dark",
        title=dict(text=title, font=dict(size=12), x=0.02, y=0.95),
        xaxis_title=None,
        yaxis_title=y_label,
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=60, r=20, t=25, b=20),
        height=100,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True, tickformat=",")

    return fig


def create_cushing_utilization_badge(utilization_pct: float | None = None) -> html.Div:
    """Create Cushing storage utilization badge.

    Args:
        utilization_pct: Utilization as percentage of capacity (0-100).

    Returns:
        Div with utilization badge.
    """
    if utilization_pct is None:
        return html.Div(
            dbc.Badge("--", color="secondary", className="px-3 py-2"),
            className="text-center",
        )

    # Determine color based on utilization
    # Low utilization (<30%) = tight WTI market = bullish crude
    # High utilization (>70%) = oversupplied = bearish crude
    if utilization_pct < 30:
        color = "success"
        status = "Tight"
    elif utilization_pct < 50:
        color = "info"
        status = "Normal"
    elif utilization_pct < 70:
        color = "warning"
        status = "Elevated"
    else:
        color = "danger"
        status = "Full"

    return html.Div(
        [
            dbc.Badge(
                [
                    html.Span(f"{utilization_pct:.1f}% ", style={"fontWeight": "bold"}),
                    html.Span(status, style={"fontSize": "0.85em"}),
                ],
                color=color,
                className="px-3 py-2",
            ),
            html.Small(" of capacity", className="text-muted ms-2"),
        ],
        className="text-center",
    )


def create_refinery_signal_badge(signal: str | None = None) -> html.Div:
    """Create refinery utilization signal badge.

    Args:
        signal: Signal string: "TIGHT", "NORMAL", "SOFT", or "WEAK".

    Returns:
        Div with signal badge.
    """
    if signal is None:
        return html.Div(
            dbc.Badge("--", color="secondary", className="px-3 py-2"),
            className="text-center",
        )

    # Map signal to color and description
    signal_config = {
        "TIGHT": ("danger", "Supply Constraint"),
        "NORMAL": ("success", "Healthy"),
        "SOFT": ("warning", "Softening"),
        "WEAK": ("secondary", "Weak Demand"),
    }

    color, description = signal_config.get(signal, ("secondary", "Unknown"))

    return html.Div(
        [
            dbc.Badge(
                [
                    html.Span(signal, style={"fontWeight": "bold"}),
                    html.Span(f" - {description}", style={"fontSize": "0.85em"}),
                ],
                color=color,
                className="px-3 py-2",
            ),
        ],
        className="text-center",
    )


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find the first matching column from candidates.

    Args:
        df: DataFrame to search.
        candidates: List of possible column names.

    Returns:
        Matching column name or None.
    """
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., "#ff6b6b").

    Returns:
        Tuple of (R, G, B) values.
    """
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )
