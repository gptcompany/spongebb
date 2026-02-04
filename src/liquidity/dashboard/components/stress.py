"""Stress indicators panel component.

Displays funding market stress metrics with gauge visualizations:
- SOFR-OIS Spread (bps)
- Repo Stress Ratio (%)
- Overall stress status (GREEN/YELLOW/RED)
"""

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html

# Stress regime colors
STRESS_COLORS = {
    "GREEN": "#00ff88",  # Normal
    "YELLOW": "#ffaa00",  # Elevated
    "RED": "#ff4444",  # Critical
}

# Stress thresholds (same as in StressIndicatorCollector)
STRESS_THRESHOLDS = {
    "sofr_ois": {"green": 10, "yellow": 25},  # basis points
    "repo_stress": {"green": 1, "yellow": 3},  # percent
    "sofr_width": {"green": 20, "yellow": 50},  # basis points
    "cp_spread": {"green": 40, "yellow": 100},  # basis points
}


def create_stress_panel() -> dbc.Card:
    """Create the funding stress panel.

    Contains:
    - SOFR-OIS spread gauge
    - Repo stress ratio gauge
    - Overall stress status indicator

    Returns:
        Bootstrap Card with stress indicators.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("Funding Stress"),
                    html.Small(" (Market Stress)", className="text-muted ms-2"),
                ]
            ),
            dbc.CardBody(
                [
                    # Status indicator
                    html.Div(
                        id="stress-status",
                        className="text-center mb-2",
                    ),
                    # Gauge row
                    dbc.Row(
                        [
                            dbc.Col(
                                dcc.Graph(
                                    id="sofr-ois-gauge",
                                    config={"displayModeBar": False},
                                    style={"height": "150px"},
                                ),
                                width=6,
                            ),
                            dbc.Col(
                                dcc.Graph(
                                    id="repo-stress-gauge",
                                    config={"displayModeBar": False},
                                    style={"height": "150px"},
                                ),
                                width=6,
                            ),
                        ]
                    ),
                ]
            ),
        ]
    )


def create_stress_gauge(
    value: float,
    label: str,
    thresholds: dict[str, float],
    unit: str = "bps",
    max_value: float | None = None,
) -> go.Figure:
    """Create a stress indicator gauge with green/yellow/red zones.

    Args:
        value: Current stress value.
        label: Gauge title label.
        thresholds: Dict with "green" and "yellow" threshold values.
        unit: Unit label (e.g., "bps", "%").
        max_value: Maximum gauge value. If None, auto-calculated.

    Returns:
        Plotly Figure with gauge indicator.
    """
    green_thresh = thresholds.get("green", 10)
    yellow_thresh = thresholds.get("yellow", 25)

    # Auto-calculate max value
    if max_value is None:
        max_value = max(yellow_thresh * 2, value * 1.5, 50)

    # Determine current color
    color = get_stress_color(value, thresholds)

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": label, "font": {"size": 12, "color": "#aaa"}},
            number={
                "font": {"size": 24, "color": color},
                "suffix": f" {unit}",
            },
            gauge={
                "axis": {
                    "range": [0, max_value],
                    "tickwidth": 1,
                    "tickcolor": "#444",
                    "tickfont": {"color": "#888", "size": 10},
                },
                "bar": {"color": color, "thickness": 0.7},
                "bgcolor": "#333",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, green_thresh], "color": "rgba(0, 255, 136, 0.2)"},
                    {
                        "range": [green_thresh, yellow_thresh],
                        "color": "rgba(255, 170, 0, 0.2)",
                    },
                    {
                        "range": [yellow_thresh, max_value],
                        "color": "rgba(255, 68, 68, 0.2)",
                    },
                ],
                "threshold": {
                    "line": {"color": "#fff", "width": 2},
                    "thickness": 0.8,
                    "value": value,
                },
            },
        )
    )

    fig.update_layout(
        height=150,
        margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#fff"},
    )

    return fig


def create_sofr_ois_gauge(value: float | None = None) -> go.Figure:
    """Create SOFR-OIS spread gauge.

    Normal: 0-10 bps, Elevated: 10-25 bps, Stress: >25 bps

    Args:
        value: SOFR-OIS spread in basis points.

    Returns:
        Plotly Figure with gauge.
    """
    return create_stress_gauge(
        value=value if value is not None else 0,
        label="SOFR-OIS",
        thresholds=STRESS_THRESHOLDS["sofr_ois"],
        unit="bps",
        max_value=50,
    )


def create_repo_stress_gauge(value: float | None = None) -> go.Figure:
    """Create repo stress ratio gauge.

    Normal: <1%, Elevated: 1-3%, Stress: >3%

    Args:
        value: Repo stress ratio in percent.

    Returns:
        Plotly Figure with gauge.
    """
    return create_stress_gauge(
        value=value if value is not None else 0,
        label="Repo Stress",
        thresholds=STRESS_THRESHOLDS["repo_stress"],
        unit="%",
        max_value=10,
    )


def create_stress_status(
    regime: str = "GREEN",
    sofr_ois: float | None = None,  # noqa: ARG001
    repo_stress: float | None = None,  # noqa: ARG001
) -> html.Div:
    """Create stress status indicator.

    Args:
        regime: Current stress regime ("GREEN", "YELLOW", "RED").
        sofr_ois: SOFR-OIS spread value (reserved for future use).
        repo_stress: Repo stress ratio value (reserved for future use).

    Returns:
        Div with status badge and key values.
    """
    badge_color = {
        "GREEN": "success",
        "YELLOW": "warning",
        "RED": "danger",
    }.get(regime, "secondary")

    status_text = {
        "GREEN": "Normal",
        "YELLOW": "Elevated",
        "RED": "Critical",
    }.get(regime, "Unknown")

    return html.Div(
        [
            dbc.Badge(
                [
                    html.Span(status_text, style={"fontWeight": "bold"}),
                ],
                color=badge_color,
                className="px-3 py-2",
                style={"fontSize": "1rem"},
            ),
        ],
        className="text-center",
    )


def get_stress_color(value: float, thresholds: dict[str, float]) -> str:
    """Return color based on threshold breach.

    Args:
        value: Current stress value.
        thresholds: Dict with "green" and "yellow" thresholds.

    Returns:
        Hex color string.
    """
    green_thresh = thresholds.get("green", 10)
    yellow_thresh = thresholds.get("yellow", 25)

    if value < green_thresh:
        return STRESS_COLORS["GREEN"]
    elif value < yellow_thresh:
        return STRESS_COLORS["YELLOW"]
    return STRESS_COLORS["RED"]


def get_overall_regime(
    sofr_ois: float | None = None,
    repo_stress: float | None = None,
    sofr_width: float | None = None,
    cp_spread: float | None = None,
) -> str:
    """Determine overall stress regime from indicators.

    Regime logic:
    - RED: Any indicator exceeds yellow threshold
    - YELLOW: Any indicator exceeds green threshold
    - GREEN: All indicators within green thresholds

    Args:
        sofr_ois: SOFR-OIS spread in bps.
        repo_stress: Repo stress ratio in %.
        sofr_width: SOFR distribution width in bps.
        cp_spread: CP-Treasury spread in bps.

    Returns:
        Regime string: "GREEN", "YELLOW", or "RED".
    """
    indicators = [
        (sofr_ois, STRESS_THRESHOLDS["sofr_ois"]),
        (repo_stress, STRESS_THRESHOLDS["repo_stress"]),
        (sofr_width, STRESS_THRESHOLDS["sofr_width"]),
        (cp_spread, STRESS_THRESHOLDS["cp_spread"]),
    ]

    is_yellow = False
    is_red = False

    for value, thresholds in indicators:
        if value is None:
            continue

        if value > thresholds["yellow"]:
            is_red = True
            break
        elif value > thresholds["green"]:
            is_yellow = True

    if is_red:
        return "RED"
    elif is_yellow:
        return "YELLOW"
    return "GREEN"
