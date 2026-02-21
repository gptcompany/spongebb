"""Consumer credit dashboard panel component.

Displays:
- XLP/XLY ratio chart (defensive vs discretionary leadership)
- AXP vs IGV relative spread chart (consumer-financial vs software growth)
- Credit stress metric summary
- Stocks most sensitive to consumer credit losses
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

COLORS = {
    "xlp_xly": "#ffd43b",
    "axp": "#4dabf7",
    "igv": "#00ff88",
    "spread": "#ff6b6b",
}


def create_consumer_credit_panel() -> dbc.Card:
    """Create consumer-credit monitoring panel."""
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("Consumer Credit Risk"),
                    html.Small(
                        " (XLP/XLY, AXP vs IGV, defaults/losses/reserves)",
                        className="text-muted ms-2",
                    ),
                ]
            ),
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                dcc.Graph(
                                    id="xlp-xly-ratio-chart",
                                    config={
                                        "displayModeBar": True,
                                        "displaylogo": False,
                                        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                                    },
                                    style={"height": "220px"},
                                ),
                                width=6,
                            ),
                            dbc.Col(
                                dcc.Graph(
                                    id="axp-igv-spread-chart",
                                    config={
                                        "displayModeBar": True,
                                        "displaylogo": False,
                                        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                                    },
                                    style={"height": "220px"},
                                ),
                                width=6,
                            ),
                        ],
                        className="mb-3",
                    ),
                    html.Div(id="consumer-credit-metrics", className="mb-2"),
                    html.Div(id="consumer-credit-sensitive-stocks"),
                ]
            ),
        ]
    )


def create_xlp_xly_ratio_chart(data: pd.DataFrame | None = None) -> go.Figure:
    """Create XLP/XLY ratio chart."""
    fig = go.Figure()

    if data is not None and not data.empty and "xlp_xly_ratio" in data.columns:
        ratio = data["xlp_xly_ratio"]
        fig.add_trace(
            go.Scatter(
                x=data["timestamp"],
                y=ratio,
                name="XLP / XLY",
                line=dict(color=COLORS["xlp_xly"], width=2),
            )
        )

        ma_50 = ratio.rolling(50, min_periods=10).mean()
        fig.add_trace(
            go.Scatter(
                x=data["timestamp"],
                y=ma_50,
                name="50D MA",
                line=dict(color="rgba(255,255,255,0.6)", width=1, dash="dot"),
            )
        )

    fig.update_layout(
        template="plotly_dark",
        title="XLP/XLY Ratio",
        title_font_size=12,
        xaxis_title=None,
        yaxis_title="Ratio",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=1, xanchor="right"),
        margin=dict(l=50, r=20, t=35, b=30),
        height=220,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)

    return fig


def create_axp_igv_spread_chart(data: pd.DataFrame | None = None) -> go.Figure:
    """Create AXP vs IGV relative performance chart."""
    fig = go.Figure()

    if data is not None and not data.empty:
        if {"axp_rebased", "igv_rebased"}.issubset(data.columns):
            fig.add_trace(
                go.Scatter(
                    x=data["timestamp"],
                    y=data["axp_rebased"],
                    name="AXP (Rebased=100)",
                    line=dict(color=COLORS["axp"], width=1.8),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=data["timestamp"],
                    y=data["igv_rebased"],
                    name="IGV (Rebased=100)",
                    line=dict(color=COLORS["igv"], width=1.8),
                )
            )

        if "relative_spread_pct" in data.columns:
            fig.add_trace(
                go.Scatter(
                    x=data["timestamp"],
                    y=data["relative_spread_pct"],
                    name="Spread %",
                    line=dict(color=COLORS["spread"], width=2),
                    visible="legendonly",
                )
            )

    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="rgba(255,255,255,0.3)",
    )

    fig.update_layout(
        template="plotly_dark",
        title="AXP vs IGV (Relative)",
        title_font_size=12,
        xaxis_title=None,
        yaxis_title="Rebased / Spread %",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=1, xanchor="right"),
        margin=dict(l=55, r=20, t=35, b=30),
        height=220,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)

    return fig


def create_consumer_credit_metrics(metrics: dict[str, float | None] | None = None) -> html.Div:
    """Create metric badges for consumer-credit tracking."""
    if not metrics:
        return html.Div(html.Small("No consumer credit metrics available", className="text-muted"))

    def _fmt_trn(value_b: float | None) -> str:
        if value_b is None:
            return "--"
        return f"${value_b / 1000:.2f}T"

    def _fmt_bn(value_b: float | None) -> str:
        if value_b is None:
            return "--"
        return f"${value_b:,.0f}B"

    def _fmt_pct(value: float | None) -> str:
        if value is None:
            return "--"
        return f"{value:.2f}%"

    items = [
        ("Consumer Credit", _fmt_trn(metrics.get("consumer_credit_total_b"))),
        ("Student Loans", _fmt_trn(metrics.get("student_loans_b"))),
        ("Ex-Student", _fmt_trn(metrics.get("consumer_credit_ex_students_b"))),
        ("Debt in Default (proxy)", _fmt_bn(metrics.get("debt_in_default_est_b"))),
        ("Default Rate", _fmt_pct(metrics.get("debt_default_rate_pct"))),
        ("Mortgage Loss Rate", _fmt_pct(metrics.get("mortgage_chargeoff_rate_pct"))),
        ("Loan Loss Reserves", _fmt_bn(metrics.get("loan_loss_reserves_b"))),
        ("USD Liquidity Index", f"{metrics.get('usd_liquidity_index', float('nan')):.1f}"
         if metrics.get("usd_liquidity_index") is not None else "--"),
    ]

    return dbc.Row(
        [
            dbc.Col(
                [
                    html.Small(label, className="text-muted d-block"),
                    html.Span(value, className="metric-value-sm"),
                ],
                width=3,
                className="mb-2",
            )
            for label, value in items
        ]
    )


def create_sensitive_stocks_table(
    sensitivity_df: pd.DataFrame | None = None,
    top_n: int = 8,
) -> html.Div:
    """Create a compact table of credit-stress-sensitive stocks."""
    if sensitivity_df is None or sensitivity_df.empty:
        return html.Div(html.Small("No stock sensitivity results", className="text-muted"))

    df = sensitivity_df.head(top_n).copy()
    cols = [c for c in ["symbol", "corr_to_stress", "beta_to_stress", "sensitivity_score"] if c in df.columns]
    df = df[cols]

    headers = [
        html.Thead(
            html.Tr([html.Th("Stock"), html.Th("Corr"), html.Th("Beta"), html.Th("Score")])
        )
    ]

    rows = []
    for _, row in df.iterrows():
        rows.append(
            html.Tr(
                [
                    html.Td(str(row.get("symbol", ""))),
                    html.Td(f"{float(row.get('corr_to_stress', float('nan'))):+.2f}"),
                    html.Td(f"{float(row.get('beta_to_stress', float('nan'))):+.2f}"),
                    html.Td(f"{float(row.get('sensitivity_score', float('nan'))):+.2f}"),
                ]
            )
        )

    return html.Div(
        [
            html.Small("Most Sensitive To Consumer Credit Loss Stress", className="text-muted"),
            dbc.Table(headers + [html.Tbody(rows)], bordered=False, hover=True, size="sm", className="table-dark"),
        ]
    )
