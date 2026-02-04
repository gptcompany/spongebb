"""Regime classification panel component.

Displays the current liquidity regime (EXPANSION/CONTRACTION) with:
- Color-coded regime indicator
- Intensity gauge (0-100)
- Confidence level
- Component breakdown
"""

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html

# Regime color mapping
REGIME_COLORS = {
    "EXPANSION": "#00ff88",
    "CONTRACTION": "#ff4444",
}


def create_regime_panel() -> dbc.Card:
    """Create the regime classification panel.

    Returns:
        Bootstrap Card with regime indicator, gauge, and metrics.
    """
    return dbc.Card(
        [
            dbc.CardHeader("Liquidity Regime"),
            dbc.CardBody(
                [
                    # Main regime indicator
                    html.Div(
                        id="regime-indicator",
                        className="text-center mb-3",
                    ),
                    # Intensity gauge
                    dcc.Graph(
                        id="regime-gauge",
                        config={"displayModeBar": False},
                        style={"height": "200px"},
                    ),
                    # Component breakdown
                    html.Div(id="regime-metrics", className="mt-3"),
                ]
            ),
        ]
    )


def create_regime_indicator(
    regime: str,
    intensity: float,
    confidence: str,
) -> html.Div:
    """Create the color-coded regime display.

    Args:
        regime: "EXPANSION" or "CONTRACTION".
        intensity: Signal strength 0-100.
        confidence: "HIGH", "MEDIUM", or "LOW".

    Returns:
        Div with styled regime indicator.
    """
    color = REGIME_COLORS.get(regime, "#888888")
    arrow = "\u25b2" if regime == "EXPANSION" else "\u25bc"  # Up/down triangle

    confidence_badge_color = {
        "HIGH": "success",
        "MEDIUM": "warning",
        "LOW": "danger",
    }.get(confidence, "secondary")

    return html.Div(
        [
            # Regime direction with arrow
            html.H2(
                [
                    html.Span(arrow, style={"marginRight": "10px"}),
                    regime,
                ],
                style={"color": color, "fontWeight": "bold", "marginBottom": "10px"},
            ),
            # Intensity
            html.P(
                [
                    html.Strong("Intensity: "),
                    html.Span(
                        f"{intensity:.0f}/100",
                        style={"color": color},
                    ),
                ],
                className="mb-1",
            ),
            # Confidence badge
            html.P(
                [
                    html.Strong("Confidence: "),
                    dbc.Badge(
                        confidence,
                        color=confidence_badge_color,
                        className="ms-1",
                    ),
                ],
            ),
        ],
        className="text-center",
    )


def create_regime_gauge(
    intensity: float,
    regime: str = "EXPANSION",
) -> go.Figure:
    """Create an intensity gauge chart.

    Args:
        intensity: Current intensity value (0-100).
        regime: Current regime for color selection.

    Returns:
        Plotly Figure with gauge indicator.
    """
    color = REGIME_COLORS.get(regime, "#888888")

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=intensity,
            title={"text": "Intensity", "font": {"size": 14, "color": "#aaa"}},
            number={"font": {"size": 40, "color": color}, "suffix": ""},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "#444",
                    "tickfont": {"color": "#888"},
                },
                "bar": {"color": color, "thickness": 0.7},
                "bgcolor": "#333",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 30], "color": "rgba(255,255,255,0.05)"},
                    {"range": [30, 70], "color": "rgba(255,255,255,0.1)"},
                    {"range": [70, 100], "color": "rgba(255,255,255,0.15)"},
                ],
                "threshold": {
                    "line": {"color": "#fff", "width": 2},
                    "thickness": 0.8,
                    "value": intensity,
                },
            },
        )
    )

    fig.update_layout(
        height=180,
        margin=dict(l=30, r=30, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#fff"},
    )

    return fig


def create_regime_metrics(
    net_liq_percentile: float,
    global_liq_percentile: float,
    stealth_qe_score: float,
) -> html.Div:
    """Create component breakdown display.

    Args:
        net_liq_percentile: Net liquidity percentile (0-1).
        global_liq_percentile: Global liquidity percentile (0-1).
        stealth_qe_score: Normalized stealth QE score (0-1).

    Returns:
        Div with component contribution bars.
    """
    components = [
        ("Net Liquidity", net_liq_percentile, 0.40),
        ("Global Liquidity", global_liq_percentile, 0.40),
        ("Stealth QE", stealth_qe_score, 0.20),
    ]

    rows = []
    for name, value, weight in components:
        pct = value * 100
        color = "#00ff88" if value > 0.5 else "#ff4444"

        rows.append(
            dbc.Row(
                [
                    dbc.Col(
                        html.Small(f"{name} ({weight:.0%})", className="text-muted"),
                        width=5,
                    ),
                    dbc.Col(
                        dbc.Progress(
                            value=pct,
                            max=100,
                            color="success" if value > 0.5 else "danger",
                            style={"height": "8px"},
                        ),
                        width=5,
                    ),
                    dbc.Col(
                        html.Small(f"{pct:.0f}%", style={"color": color}),
                        width=2,
                        className="text-end",
                    ),
                ],
                className="mb-2 align-items-center",
            )
        )

    return html.Div(
        [
            html.Hr(className="my-2"),
            html.Small("Component Contributions:", className="text-muted d-block mb-2"),
            *rows,
        ]
    )
