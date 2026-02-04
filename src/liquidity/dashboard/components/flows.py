"""Capital flows panel component.

Displays:
- TIC (Treasury International Capital) data - foreign holdings
- ETF flows - commodity ETF tracking (GLD, SLV, USO)
"""

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

# Color palette for flows charts
FLOWS_COLORS = {
    "japan": "#ff6b6b",  # Red
    "china": "#ffd43b",  # Yellow
    "uk": "#4dabf7",  # Blue
    "total": "#00ff88",  # Green
    "gld": "#ffd43b",  # Gold
    "slv": "#c0c0c0",  # Silver
    "uso": "#4dabf7",  # Oil blue
}


def create_flows_panel() -> dbc.Card:
    """Create the capital flows panel.

    Contains:
    - TIC flows bar chart (top foreign holders)
    - ETF flows chart (commodity ETF positions)

    Returns:
        Bootstrap Card with capital flows components.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("Capital Flows"),
                    html.Small(" (TIC & ETF)", className="text-muted ms-2"),
                ]
            ),
            dbc.CardBody(
                [
                    # TIC flows chart
                    html.Div(
                        [
                            html.Small("Foreign Treasury Holdings", className="text-muted"),
                            dcc.Graph(
                                id="tic-flows-chart",
                                config={
                                    "displayModeBar": False,
                                    "displaylogo": False,
                                },
                                style={"height": "120px"},
                            ),
                        ],
                        className="mb-2",
                    ),
                    # ETF flows chart
                    html.Div(
                        [
                            html.Small("Commodity ETF Prices", className="text-muted"),
                            dcc.Graph(
                                id="etf-flows-chart",
                                config={
                                    "displayModeBar": False,
                                    "displaylogo": False,
                                },
                                style={"height": "120px"},
                            ),
                        ],
                    ),
                ]
            ),
        ]
    )


def create_tic_chart(data: pd.DataFrame | None = None, top_n: int = 5) -> go.Figure:
    """Create TIC foreign holdings bar chart.

    Shows top N foreign holders of US Treasury securities.

    Args:
        data: DataFrame with columns: series_id, value.
            series_id format: tic_{country}_holdings
        top_n: Number of top holders to show.

    Returns:
        Plotly Figure with horizontal bar chart.
    """
    fig = go.Figure()

    if data is not None and not data.empty:
        # Filter to country holdings only (exclude total)
        country_data = data[
            data["series_id"].str.startswith("tic_")
            & ~data["series_id"].str.contains("total")
            & ~data["series_id"].str.contains("official")
            & ~data["series_id"].str.contains("private")
        ].copy()

        if not country_data.empty:
            # Extract country names and sort by value
            country_data["country"] = country_data["series_id"].str.replace(
                r"tic_(.+)_holdings", r"\1", regex=True
            )
            country_data = country_data.sort_values("value", ascending=True).tail(top_n)

            # Assign colors
            colors = []
            for country in country_data["country"]:
                colors.append(FLOWS_COLORS.get(country, "#888888"))

            fig.add_trace(
                go.Bar(
                    x=country_data["value"],
                    y=country_data["country"].str.upper(),
                    orientation="h",
                    marker_color=colors,
                    text=country_data["value"].apply(lambda x: f"${x:,.0f}B"),
                    textposition="outside",
                    textfont=dict(size=10),
                )
            )

    # Layout
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title="USD Billions",
        yaxis_title=None,
        showlegend=False,
        margin=dict(l=60, r=60, t=5, b=25),
        height=120,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_xaxes(
        gridcolor="rgba(255,255,255,0.1)",
        showgrid=True,
        tickformat=",.0f",
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.05)",
        showgrid=False,
        tickfont=dict(size=10),
    )

    return fig


def create_etf_flows_chart(data: pd.DataFrame | None = None) -> go.Figure:
    """Create ETF flows heatmap for commodity ETFs.

    Shows price changes for SPY, TLT, GLD, HYG style.

    Args:
        data: DataFrame with columns: etf, close, timestamp.

    Returns:
        Plotly Figure with ETF price chart.
    """
    fig = go.Figure()

    if data is not None and not data.empty:
        # Group by ETF and plot each
        for etf in data["etf"].unique():
            etf_data = data[data["etf"] == etf].sort_values("timestamp")

            if len(etf_data) < 2:
                continue

            # Calculate % change from start
            first_price = etf_data["close"].iloc[0]
            pct_change = ((etf_data["close"] - first_price) / first_price) * 100

            color = FLOWS_COLORS.get(etf.lower(), "#888888")

            fig.add_trace(
                go.Scatter(
                    x=etf_data["timestamp"],
                    y=pct_change,
                    name=etf,
                    line=dict(color=color, width=1.5),
                    hovertemplate=f"{etf}: %{{y:.1f}}%<extra></extra>",
                )
            )

    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")

    # Layout
    fig.update_layout(
        template="plotly_dark",
        title=None,
        xaxis_title=None,
        yaxis_title="% Change",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=9),
        ),
        margin=dict(l=40, r=10, t=25, b=25),
        height=120,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.update_xaxes(gridcolor="rgba(255,255,255,0.1)", showgrid=True)
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.1)",
        showgrid=True,
        ticksuffix="%",
    )

    return fig


def create_flows_summary(
    japan_holdings: float | None = None,
    china_holdings: float | None = None,
    total_holdings: float | None = None,
) -> html.Div:
    """Create TIC holdings summary.

    Args:
        japan_holdings: Japan's Treasury holdings (billions).
        china_holdings: China's Treasury holdings (billions).
        total_holdings: Total foreign holdings (billions).

    Returns:
        Div with holdings summary.
    """
    return html.Div(
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Small("Japan", className="text-muted d-block"),
                        html.Span(
                            f"${japan_holdings:,.0f}B" if japan_holdings else "--",
                            style={"color": FLOWS_COLORS["japan"], "fontSize": "0.9rem"},
                        ),
                    ],
                    width=4,
                    className="text-center",
                ),
                dbc.Col(
                    [
                        html.Small("China", className="text-muted d-block"),
                        html.Span(
                            f"${china_holdings:,.0f}B" if china_holdings else "--",
                            style={"color": FLOWS_COLORS["china"], "fontSize": "0.9rem"},
                        ),
                    ],
                    width=4,
                    className="text-center",
                ),
                dbc.Col(
                    [
                        html.Small("Total", className="text-muted d-block"),
                        html.Span(
                            f"${total_holdings:,.0f}B" if total_holdings else "--",
                            style={"color": FLOWS_COLORS["total"], "fontSize": "0.9rem"},
                        ),
                    ],
                    width=4,
                    className="text-center",
                ),
            ]
        ),
        className="mt-1",
    )
