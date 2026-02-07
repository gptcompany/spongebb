"""Oil term structure dashboard component.

Provides visualization for:
- Curve shape gauge (Backwardation <-> Contango)
- WTI price chart with momentum
- Roll yield bar chart by horizon
"""


import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from liquidity.analyzers.term_structure import (
    CurveShape,
    RollYieldMetrics,
    TermStructureSignal,
)


def create_oil_term_structure_panel(
    signal: TermStructureSignal | None = None,
    roll_yield: RollYieldMetrics | None = None,
    price_history: pd.DataFrame | None = None,
) -> dbc.Card:
    """Create oil term structure dashboard panel.

    Args:
        signal: Current term structure signal.
        roll_yield: Current roll yield metrics.
        price_history: Historical price data for chart.

    Returns:
        Dash Bootstrap Card component.
    """
    return dbc.Card([
        dbc.CardHeader([
            html.H5("Oil Term Structure", className="mb-0"),
            html.Small("Contango/Backwardation Analysis", className="text-muted"),
        ]),
        dbc.CardBody([
            dbc.Tabs([
                dbc.Tab(
                    _create_signal_tab(signal, roll_yield),
                    label="Signal",
                    tab_id="signal",
                ),
                dbc.Tab(
                    _create_price_tab(price_history),
                    label="Price",
                    tab_id="price",
                ),
                dbc.Tab(
                    _create_roll_yield_tab(roll_yield),
                    label="Roll Yield",
                    tab_id="roll",
                ),
            ], id="term-structure-tabs", active_tab="signal"),
        ]),
    ], className="h-100")


def _create_signal_tab(
    signal: TermStructureSignal | None,
    roll_yield: RollYieldMetrics | None,
) -> html.Div:
    """Create signal gauge and metrics tab."""
    if signal is None:
        return html.Div(
            "No signal data available",
            className="text-muted p-3 text-center",
        )

    return html.Div([
        dbc.Row([
            dbc.Col([
                dcc.Graph(
                    figure=create_curve_gauge(signal),
                    config={"displayModeBar": False},
                    style={"height": "200px"},
                ),
            ], width=6),
            dbc.Col([
                _create_signal_metrics(signal, roll_yield),
            ], width=6),
        ]),
    ])


def create_curve_gauge(signal: TermStructureSignal) -> go.Figure:
    """Create gauge chart for curve shape.

    Left = Backwardation (bullish), Right = Contango (bearish)

    Args:
        signal: Term structure signal.

    Returns:
        Plotly Figure.
    """
    # Map curve shape to gauge value
    # Backwardation = negative (left), Contango = positive (right)
    if signal.curve_shape == CurveShape.BACKWARDATION:
        value = -signal.intensity
    elif signal.curve_shape == CurveShape.CONTANGO:
        value = signal.intensity
    else:
        value = 0

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": signal.curve_shape.value, "font": {"size": 14}},
        number={"suffix": "", "font": {"size": 20}},
        gauge={
            "axis": {"range": [-100, 100], "tickwidth": 1, "tickcolor": "darkblue"},
            "bar": {"color": "rgba(50, 50, 50, 0.8)"},
            "bgcolor": "white",
            "borderwidth": 2,
            "bordercolor": "gray",
            "steps": [
                {"range": [-100, -50], "color": "#1a9641"},   # Strong backwardation
                {"range": [-50, 0], "color": "#a6d96a"},      # Mild backwardation
                {"range": [0, 50], "color": "#fdae61"},       # Mild contango
                {"range": [50, 100], "color": "#d7191c"},     # Strong contango
            ],
            "threshold": {
                "line": {"color": "black", "width": 4},
                "thickness": 0.75,
                "value": value,
            },
        },
    ))

    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#333"},
    )

    # Add annotations for backwardation/contango labels
    fig.add_annotation(
        x=0.1, y=0.05,
        text="Backwardation",
        showarrow=False,
        font=dict(size=10, color="#1a9641"),
    )
    fig.add_annotation(
        x=0.9, y=0.05,
        text="Contango",
        showarrow=False,
        font=dict(size=10, color="#d7191c"),
    )

    return fig


def _create_signal_metrics(
    signal: TermStructureSignal,
    roll_yield: RollYieldMetrics | None,
) -> html.Div:
    """Create metrics display for signal tab."""
    metrics = [
        ("Curve Shape", signal.curve_shape.value, _get_shape_badge(signal.curve_shape)),
        ("Intensity", f"{signal.intensity:.0f}/100", None),
        ("Confidence", f"{signal.confidence * 100:.0f}%", None),
        ("5D Momentum", f"{signal.momentum_5d:+.2f}%", None),
        ("20D Momentum", f"{signal.momentum_20d:+.2f}%", None),
    ]

    if roll_yield:
        metrics.append(("Roll Yield (Ann.)", f"{roll_yield.annual_yield:+.1f}%", None))
        metrics.append(("Regime Days", str(roll_yield.days_in_current_regime), None))

    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Small(label, className="text-muted d-block"),
                    html.Span([
                        html.Span(value, className="fs-6 fw-bold"),
                        badge if badge else None,
                    ]),
                ], className="mb-2")
            ], width=6)
            for label, value, badge in metrics
        ]),
    ], className="p-2")


def _get_shape_badge(shape: CurveShape) -> dbc.Badge | None:
    """Get colored badge for curve shape."""
    color_map = {
        CurveShape.BACKWARDATION: "success",
        CurveShape.FLAT: "secondary",
        CurveShape.CONTANGO: "warning",
    }
    return dbc.Badge(
        shape.value,
        color=color_map.get(shape, "secondary"),
        className="ms-2",
    )


def _create_price_tab(price_history: pd.DataFrame | None) -> html.Div:
    """Create price chart tab."""
    if price_history is None or price_history.empty:
        return html.Div(
            "No price data available",
            className="text-muted p-3 text-center",
        )

    return html.Div([
        dcc.Graph(
            figure=create_price_chart(price_history),
            config={"displayModeBar": True},
            style={"height": "300px"},
        ),
    ])


def create_price_chart(df: pd.DataFrame) -> go.Figure:
    """Create WTI price chart with moving average.

    Args:
        df: DataFrame with price data.

    Returns:
        Plotly Figure.
    """
    # Filter to WTI front month
    if "series_id" not in df.columns:
        return go.Figure()

    wti = df[df["series_id"] == "wti_front"].sort_values("timestamp")

    if wti.empty:
        return go.Figure()

    fig = go.Figure()

    # Price line
    fig.add_trace(go.Scatter(
        x=wti["timestamp"],
        y=wti["value"],
        mode="lines",
        name="WTI Front",
        line=dict(color="#1f77b4", width=2),
        hovertemplate="$%{y:.2f}<extra></extra>",
    ))

    # 20-day moving average
    wti_ma = wti["value"].rolling(20, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=wti["timestamp"],
        y=wti_ma,
        mode="lines",
        name="20D MA",
        line=dict(color="#ff7f0e", width=1, dash="dash"),
        hovertemplate="MA: $%{y:.2f}<extra></extra>",
    ))

    fig.update_layout(
        title={"text": "WTI Crude Oil Price", "font": {"size": 14}},
        xaxis_title="Date",
        yaxis_title="$/barrel",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=20, t=60, b=40),
        hovermode="x unified",
    )

    return fig


def _create_roll_yield_tab(roll_yield: RollYieldMetrics | None) -> html.Div:
    """Create roll yield visualization tab."""
    if roll_yield is None:
        return html.Div(
            "No roll yield data available",
            className="text-muted p-3 text-center",
        )

    return html.Div([
        dbc.Row([
            dbc.Col([
                dcc.Graph(
                    figure=create_roll_yield_bars(roll_yield),
                    config={"displayModeBar": False},
                    style={"height": "250px"},
                ),
            ], width=8),
            dbc.Col([
                _create_roll_yield_summary(roll_yield),
            ], width=4),
        ]),
    ])


def create_roll_yield_bars(roll_yield: RollYieldMetrics) -> go.Figure:
    """Create bar chart for roll yields at different horizons.

    Args:
        roll_yield: Roll yield metrics.

    Returns:
        Plotly Figure.
    """
    horizons = ["1 Month", "3 Month", "12 Month"]
    values = [
        roll_yield.monthly_yield,
        roll_yield.quarterly_yield,
        roll_yield.annual_yield,
    ]

    colors = ["#2ca02c" if v > 0 else "#d62728" for v in values]

    fig = go.Figure(go.Bar(
        x=horizons,
        y=values,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in values],
        textposition="outside",
        hovertemplate="%{x}: %{y:+.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title={"text": "Roll Yield by Horizon", "font": {"size": 14}},
        yaxis_title="Annualized %",
        showlegend=False,
        margin=dict(l=50, r=20, t=60, b=40),
    )

    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)

    return fig


def _create_roll_yield_summary(roll_yield: RollYieldMetrics) -> html.Div:
    """Create roll yield summary text."""
    trend_icons = {
        "IMPROVING": "📈",
        "STABLE": "➡️",
        "DETERIORATING": "📉",
    }

    if roll_yield.annual_yield > 0:
        interpretation = "Positive roll yield (backwardation) — commodity longs benefit from rolling."
        interpretation_class = "text-success"
    else:
        interpretation = "Negative roll yield (contango) — commodity longs pay cost to roll."
        interpretation_class = "text-danger"

    return html.Div([
        html.H6("Summary", className="mb-3"),
        html.P([
            html.Strong("Trend: "),
            html.Span(
                f"{trend_icons.get(roll_yield.yield_trend, '❓')} {roll_yield.yield_trend}",
            ),
        ], className="mb-2"),
        html.P([
            html.Strong("Regime Duration: "),
            html.Span(f"{roll_yield.days_in_current_regime} days"),
        ], className="mb-2"),
        html.Hr(className="my-2"),
        html.Small(interpretation, className=f"{interpretation_class}"),
    ], className="p-2")


# Callback helper for integration
def update_term_structure_panel_data(
    collector,
    analyzer,
) -> dict:
    """Helper to fetch data and create panel inputs.

    This is a utility function for dashboard callbacks.

    Args:
        collector: OilTermStructureCollector instance.
        analyzer: TermStructureAnalyzer instance.

    Returns:
        Dict with signal, roll_yield, and price_history keys.
    """
    import asyncio

    async def _fetch():
        return await collector.collect_with_momentum()

    # Run async in sync context
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, can't use run_until_complete
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _fetch())
                price_data = future.result(timeout=30)
        else:
            price_data = loop.run_until_complete(_fetch())
    except Exception:
        # Fallback for various async edge cases
        price_data = asyncio.run(_fetch())

    if price_data.empty:
        return {"signal": None, "roll_yield": None, "price_history": None}

    signal = analyzer.analyze(price_data)
    roll_yield = analyzer.calculate_roll_yield(price_data)

    return {
        "signal": signal,
        "roll_yield": roll_yield,
        "price_history": price_data,
    }
