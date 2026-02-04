"""Correlation heatmap panel component.

Displays 7x7 correlation matrix for major assets:
BTC, SPX, GOLD, TLT, DXY, COPPER, HYG
"""

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

# Default assets for correlation matrix
DEFAULT_ASSETS = ["BTC", "SPX", "GOLD", "TLT", "DXY", "COPPER", "HYG"]

# Correlation interpretation thresholds
CORRELATION_THRESHOLDS = {
    "strong_positive": 0.7,
    "moderate_positive": 0.4,
    "weak": 0.2,
    "moderate_negative": -0.4,
    "strong_negative": -0.7,
}


def create_correlation_panel() -> dbc.Card:
    """Create the correlation analysis panel.

    Contains:
    - 7x7 correlation heatmap (BTC, SPX, GOLD, TLT, DXY, COPPER, HYG)
    - Correlation regime shift alerts

    Returns:
        Bootstrap Card with correlation heatmap.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("Correlation Analysis"),
                    html.Small(
                        " (Asset Correlations vs Net Liquidity)",
                        className="text-muted ms-2",
                    ),
                ]
            ),
            dbc.CardBody(
                [
                    # Correlation heatmap
                    dcc.Graph(
                        id="correlation-heatmap",
                        config={
                            "displayModeBar": True,
                            "displaylogo": False,
                            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                        },
                        style={"height": "300px"},
                    ),
                    # Correlation alerts
                    html.Div(
                        id="correlation-alerts",
                        className="mt-2",
                    ),
                ]
            ),
        ]
    )


def create_correlation_heatmap(
    corr_matrix: pd.DataFrame | None = None,
    assets: list[str] | None = None,
) -> go.Figure:
    """Create correlation heatmap figure.

    Args:
        corr_matrix: DataFrame with pairwise correlations.
            Index and columns should be asset names.
        assets: List of asset names in display order.
            If None, uses DEFAULT_ASSETS.

    Returns:
        Plotly Figure with heatmap.
    """
    if assets is None:
        assets = DEFAULT_ASSETS

    # Create default identity matrix if no data
    if corr_matrix is None or corr_matrix.empty:
        corr_matrix = pd.DataFrame(
            data=[[1.0 if i == j else 0.0 for j in range(len(assets))] for i in range(len(assets))],
            index=pd.Index(assets),
            columns=pd.Index(assets),
        )

    # Ensure proper order
    try:
        corr_matrix = corr_matrix.loc[assets, assets]
    except KeyError:
        # Use whatever assets are available
        available = [a for a in assets if a in corr_matrix.index and a in corr_matrix.columns]
        if available:
            corr_matrix = corr_matrix.loc[available, available]

    # Create heatmap
    fig = go.Figure(
        data=go.Heatmap(
            z=corr_matrix.values,
            x=list(corr_matrix.columns),
            y=list(corr_matrix.index),
            colorscale="RdBu",
            zmid=0,  # Center colorscale at 0
            zmin=-1,
            zmax=1,
            text=corr_matrix.round(2).astype(str).values,
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
            colorbar=dict(
                title=dict(text="Corr", side="right"),
                tickvals=[-1, -0.5, 0, 0.5, 1],
                ticktext=["-1", "-0.5", "0", "0.5", "1"],
                len=0.9,
                thickness=15,
            ),
        )
    )

    # Layout
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=None,
        yaxis_title=None,
        margin=dict(l=60, r=80, t=30, b=60),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_xaxes(
        side="bottom",
        tickangle=45,
        tickfont=dict(size=10),
    )
    fig.update_yaxes(
        tickfont=dict(size=10),
        autorange="reversed",  # Put first asset at top
    )

    return fig


def create_correlation_alerts(
    current_corrs: dict[str, float] | None = None,
    previous_corrs: dict[str, float] | None = None,
    threshold: float = 0.3,
) -> html.Div:
    """Create correlation regime shift alerts.

    Alerts when correlation between any asset pair changes by > threshold.

    Args:
        current_corrs: Dict of current correlations {asset_pair: corr}.
        previous_corrs: Dict of previous correlations {asset_pair: corr}.
        threshold: Change threshold to trigger alert (default 0.3).

    Returns:
        Div with alert badges or empty div.
    """
    if current_corrs is None or previous_corrs is None:
        return html.Div()

    alerts = []
    for pair, current_val in current_corrs.items():
        prev_val = previous_corrs.get(pair)
        if prev_val is None:
            continue

        change = current_val - prev_val
        if abs(change) >= threshold:
            direction = "strengthened" if change > 0 else "weakened"
            color = "warning" if abs(change) < 0.5 else "danger"

            alerts.append(
                dbc.Badge(
                    f"{pair}: {direction} ({change:+.2f})",
                    color=color,
                    className="me-1 mb-1",
                )
            )

    if not alerts:
        return html.Div(
            html.Small("No significant correlation shifts", className="text-muted"),
            className="text-center",
        )

    return html.Div(
        [
            html.Small("Correlation Shifts: ", className="text-muted"),
            html.Div(alerts, style={"display": "inline"}),
        ]
    )


def interpret_correlation(corr: float) -> str:
    """Interpret a correlation value.

    Args:
        corr: Correlation coefficient (-1 to 1).

    Returns:
        Human-readable interpretation.
    """
    if corr >= CORRELATION_THRESHOLDS["strong_positive"]:
        return "Strong positive"
    elif corr >= CORRELATION_THRESHOLDS["moderate_positive"]:
        return "Moderate positive"
    elif corr >= CORRELATION_THRESHOLDS["weak"]:
        return "Weak positive"
    elif corr >= -CORRELATION_THRESHOLDS["weak"]:
        return "No correlation"
    elif corr >= CORRELATION_THRESHOLDS["moderate_negative"]:
        return "Weak negative"
    elif corr >= CORRELATION_THRESHOLDS["strong_negative"]:
        return "Moderate negative"
    else:
        return "Strong negative"


def get_liquidity_sensitive_assets(
    corr_vs_liquidity: dict[str, float] | None = None,
    threshold: float = 0.5,
) -> list[str]:
    """Identify assets most sensitive to liquidity changes.

    Args:
        corr_vs_liquidity: Dict mapping asset to correlation with net liquidity.
        threshold: Minimum absolute correlation to be considered sensitive.

    Returns:
        List of asset names with abs(correlation) >= threshold.
    """
    if corr_vs_liquidity is None:
        return []

    sensitive = []
    for asset, corr in corr_vs_liquidity.items():
        if abs(corr) >= threshold:
            sensitive.append(asset)

    return sensitive
