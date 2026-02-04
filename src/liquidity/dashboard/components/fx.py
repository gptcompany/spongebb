"""FX panel component for DXY and major currency pairs.

Displays:
- DXY (US Dollar Index) time series chart with threshold bands
- Major currency pair metrics (EUR/USD, USD/JPY, USD/CNY)
"""

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

# Color palette for FX charts
FX_COLORS = {
    "dxy": "#4dabf7",  # Blue
    "eurusd": "#00ff88",  # Green
    "usdjpy": "#ff6b6b",  # Red
    "usdcny": "#ffd43b",  # Yellow
    "gbpusd": "#e599f7",  # Purple
}

# DXY threshold levels
DXY_THRESHOLDS = {
    "par": 100,  # USD par value
    "strong": 105,  # Strong USD threshold
    "weak": 95,  # Weak USD threshold
}


def create_fx_panel() -> dbc.Card:
    """Create the FX markets panel.

    Contains:
    - DXY time series chart with threshold bands
    - Major FX pair metrics (EUR/USD, USD/JPY, USD/CNY)

    Returns:
        Bootstrap Card with FX components.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("FX Markets"),
                    html.Small(" (DXY & Major Pairs)", className="text-muted ms-2"),
                ]
            ),
            dbc.CardBody(
                [
                    # DXY chart
                    dcc.Graph(
                        id="dxy-chart",
                        config={
                            "displayModeBar": True,
                            "displaylogo": False,
                            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                        },
                        style={"height": "200px"},
                    ),
                    # FX metrics row
                    html.Div(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        _create_fx_metric("EUR/USD", "eurusd-value"),
                                        width=4,
                                    ),
                                    dbc.Col(
                                        _create_fx_metric("USD/JPY", "usdjpy-value"),
                                        width=4,
                                    ),
                                    dbc.Col(
                                        _create_fx_metric("USD/CNY", "usdcny-value"),
                                        width=4,
                                    ),
                                ],
                                className="mt-2",
                            ),
                        ],
                        className="fx-metrics",
                    ),
                ]
            ),
        ]
    )


def _create_fx_metric(label: str, metric_id: str) -> html.Div:
    """Create a single FX metric display.

    Args:
        label: Pair label (e.g., "EUR/USD").
        metric_id: HTML id for the value element.

    Returns:
        Div with label and value.
    """
    return html.Div(
        [
            html.Small(label, className="text-muted d-block"),
            html.Span(id=metric_id, children="--", className="metric-value-sm"),
        ],
        className="text-center",
    )


def create_dxy_chart(data: pd.DataFrame | None = None) -> go.Figure:
    """Create DXY time series chart with threshold bands.

    Args:
        data: DataFrame with columns: timestamp, value.
            If None, creates an empty placeholder chart.

    Returns:
        Plotly Figure with DXY chart.
    """
    fig = go.Figure()

    if data is not None and not data.empty:
        # Determine which columns are available
        value_col = None
        for col in ["value", "dxy", "DXY", "close", "Close"]:
            if col in data.columns:
                value_col = col
                break

        timestamp_col = None
        for col in ["timestamp", "date", "Date", "index"]:
            if col in data.columns:
                timestamp_col = col
                break

        if value_col and timestamp_col:
            # Main DXY line
            fig.add_trace(
                go.Scatter(
                    x=data[timestamp_col],
                    y=data[value_col],
                    name="DXY",
                    line=dict(color=FX_COLORS["dxy"], width=2),
                    fill="tozeroy",
                    fillcolor="rgba(77, 171, 247, 0.1)",
                )
            )

    # Add threshold lines
    fig.add_hline(
        y=DXY_THRESHOLDS["par"],
        line_dash="dash",
        line_color="rgba(255,255,255,0.5)",
        annotation_text="Par (100)",
        annotation_position="right",
    )
    fig.add_hline(
        y=DXY_THRESHOLDS["strong"],
        line_dash="dot",
        line_color="rgba(255, 68, 68, 0.5)",
        annotation_text="Strong USD",
        annotation_position="right",
    )
    fig.add_hline(
        y=DXY_THRESHOLDS["weak"],
        line_dash="dot",
        line_color="rgba(0, 255, 136, 0.5)",
        annotation_text="Weak USD",
        annotation_position="right",
    )

    # Layout configuration
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=None,
        yaxis_title="Index",
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=50, r=60, t=10, b=30),
        height=200,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)

    return fig


def create_fx_metrics(
    eurusd: float | None = None,
    usdjpy: float | None = None,
    usdcny: float | None = None,
    eurusd_change: float | None = None,
    usdjpy_change: float | None = None,
    usdcny_change: float | None = None,
) -> dict[str, html.Span]:
    """Create FX pair metrics for display.

    Args:
        eurusd: EUR/USD rate.
        usdjpy: USD/JPY rate.
        usdcny: USD/CNY rate.
        eurusd_change: EUR/USD daily change (%).
        usdjpy_change: USD/JPY daily change (%).
        usdcny_change: USD/CNY daily change (%).

    Returns:
        Dictionary mapping metric IDs to Span components.
    """

    def format_rate(rate: float | None, change: float | None, decimals: int = 4) -> html.Span:
        if rate is None:
            return html.Span("--")

        rate_str = f"{rate:.{decimals}f}"
        if change is not None:
            change_class = "metric-delta-positive" if change >= 0 else "metric-delta-negative"
            change_sign = "+" if change >= 0 else ""
            return html.Span(
                [
                    f"{rate_str} ",
                    html.Small(
                        f"({change_sign}{change:.2f}%)",
                        className=change_class,
                    ),
                ]
            )
        return html.Span(rate_str)

    return {
        "eurusd-value": format_rate(eurusd, eurusd_change),
        "usdjpy-value": format_rate(usdjpy, usdjpy_change, decimals=2),
        "usdcny-value": format_rate(usdcny, usdcny_change),
    }
