"""Commodities panel component for precious metals and energy.

Displays tabbed interface with:
- Gold: GC=F chart with % change
- Copper: HG=F chart (risk-on indicator)
- Oil: CL=F (WTI) and BZ=F (Brent) charts
"""

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

# Color palette for commodity charts
COMMODITY_COLORS = {
    "gold": "#ffd43b",  # Gold
    "copper": "#ff6b6b",  # Copper red
    "wti": "#4dabf7",  # WTI blue
    "brent": "#00ff88",  # Brent green
    "silver": "#c0c0c0",  # Silver
}


def create_commodities_panel() -> dbc.Card:
    """Create the commodities panel with tabbed interface.

    Contains tabs for:
    - Gold: Precious metal safe haven
    - Copper: Industrial/economic indicator
    - Oil: WTI and Brent crude

    Returns:
        Bootstrap Card with tabbed commodity charts.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("Commodities"),
                    html.Small(" (Real Assets)", className="text-muted ms-2"),
                ]
            ),
            dbc.CardBody(
                [
                    dbc.Tabs(
                        [
                            dbc.Tab(
                                dcc.Graph(
                                    id="gold-chart",
                                    config={
                                        "displayModeBar": False,
                                        "displaylogo": False,
                                    },
                                    style={"height": "200px"},
                                ),
                                label="Gold",
                                tab_id="tab-gold",
                            ),
                            dbc.Tab(
                                dcc.Graph(
                                    id="copper-chart",
                                    config={
                                        "displayModeBar": False,
                                        "displaylogo": False,
                                    },
                                    style={"height": "200px"},
                                ),
                                label="Copper",
                                tab_id="tab-copper",
                            ),
                            dbc.Tab(
                                dcc.Graph(
                                    id="oil-chart",
                                    config={
                                        "displayModeBar": False,
                                        "displaylogo": False,
                                    },
                                    style={"height": "200px"},
                                ),
                                label="Oil",
                                tab_id="tab-oil",
                            ),
                        ],
                        id="commodity-tabs",
                        active_tab="tab-gold",
                    ),
                    # Current prices summary
                    html.Div(id="commodity-summary", className="mt-2"),
                ]
            ),
        ]
    )


def create_commodity_chart(
    data: pd.DataFrame | None = None,
    commodity: str = "gold",
    show_change_annotation: bool = True,
) -> go.Figure:
    """Create a commodity price chart.

    Args:
        data: DataFrame with columns: timestamp, value.
        commodity: Commodity type ("gold", "copper", "wti", "brent").
        show_change_annotation: Whether to show % change annotation.

    Returns:
        Plotly Figure with commodity chart.
    """
    fig = go.Figure()
    color = COMMODITY_COLORS.get(commodity, "#ffffff")

    if data is not None and not data.empty:
        # Find value and timestamp columns
        value_col = _find_column(data, ["value", "close", "Close", commodity])
        timestamp_col = _find_column(data, ["timestamp", "date", "Date", "index"])

        if value_col and timestamp_col:
            values = data[value_col]
            timestamps = data[timestamp_col]

            # Main price line
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=values,
                    name=commodity.upper(),
                    line=dict(color=color, width=2),
                    fill="tozeroy",
                    fillcolor=f"rgba{_hex_to_rgb(color) + (0.1,)}",
                )
            )

            # Add % change annotation if requested
            if show_change_annotation and len(values) >= 2:
                first_val = values.iloc[0]
                last_val = values.iloc[-1]
                if first_val and first_val != 0:
                    pct_change = ((last_val - first_val) / first_val) * 100
                    change_color = "#00ff88" if pct_change >= 0 else "#ff4444"
                    change_sign = "+" if pct_change >= 0 else ""

                    fig.add_annotation(
                        x=timestamps.iloc[-1],
                        y=last_val,
                        text=f"{change_sign}{pct_change:.1f}%",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=1,
                        arrowcolor=change_color,
                        font=dict(size=12, color=change_color),
                        bgcolor="rgba(0,0,0,0.6)",
                        borderpad=4,
                    )

    # Layout
    commodity_labels = {
        "gold": "Gold ($/oz)",
        "copper": "Copper ($/lb)",
        "wti": "WTI Crude ($/bbl)",
        "brent": "Brent Crude ($/bbl)",
        "silver": "Silver ($/oz)",
    }

    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=None,
        yaxis_title=commodity_labels.get(commodity, commodity),
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=50, r=20, t=10, b=30),
        height=200,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True, tickformat=",.0f")

    return fig


def create_oil_chart(
    wti_data: pd.DataFrame | None = None,
    brent_data: pd.DataFrame | None = None,
) -> go.Figure:
    """Create oil chart showing both WTI and Brent.

    Args:
        wti_data: DataFrame with WTI data (timestamp, value).
        brent_data: DataFrame with Brent data (timestamp, value).

    Returns:
        Plotly Figure with dual oil price lines.
    """
    fig = go.Figure()

    # Add WTI
    if wti_data is not None and not wti_data.empty:
        value_col = _find_column(wti_data, ["value", "close", "Close", "wti"])
        timestamp_col = _find_column(wti_data, ["timestamp", "date", "Date", "index"])

        if value_col and timestamp_col:
            fig.add_trace(
                go.Scatter(
                    x=wti_data[timestamp_col],
                    y=wti_data[value_col],
                    name="WTI",
                    line=dict(color=COMMODITY_COLORS["wti"], width=2),
                )
            )

    # Add Brent
    if brent_data is not None and not brent_data.empty:
        value_col = _find_column(brent_data, ["value", "close", "Close", "brent"])
        timestamp_col = _find_column(brent_data, ["timestamp", "date", "Date", "index"])

        if value_col and timestamp_col:
            fig.add_trace(
                go.Scatter(
                    x=brent_data[timestamp_col],
                    y=brent_data[value_col],
                    name="Brent",
                    line=dict(color=COMMODITY_COLORS["brent"], width=2),
                )
            )

    # Layout
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=None,
        yaxis_title="$/barrel",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=50, r=20, t=30, b=30),
        height=200,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True, tickformat=",.0f")

    return fig


def create_commodity_summary(
    gold_price: float | None = None,
    copper_price: float | None = None,
    wti_price: float | None = None,
) -> html.Div:
    """Create commodity price summary row.

    Args:
        gold_price: Current gold price ($/oz).
        copper_price: Current copper price ($/lb).
        wti_price: Current WTI price ($/bbl).

    Returns:
        Div with price summary.
    """
    return html.Div(
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Small("Gold", className="text-muted d-block"),
                        html.Span(
                            f"${gold_price:,.0f}" if gold_price else "--",
                            style={"color": COMMODITY_COLORS["gold"]},
                        ),
                    ],
                    width=4,
                    className="text-center",
                ),
                dbc.Col(
                    [
                        html.Small("Copper", className="text-muted d-block"),
                        html.Span(
                            f"${copper_price:.2f}" if copper_price else "--",
                            style={"color": COMMODITY_COLORS["copper"]},
                        ),
                    ],
                    width=4,
                    className="text-center",
                ),
                dbc.Col(
                    [
                        html.Small("WTI", className="text-muted d-block"),
                        html.Span(
                            f"${wti_price:.2f}" if wti_price else "--",
                            style={"color": COMMODITY_COLORS["wti"]},
                        ),
                    ],
                    width=4,
                    className="text-center",
                ),
            ]
        )
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
