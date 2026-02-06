"""Inflation Expectations Dashboard Panel.

Visualizes real rates and breakeven inflation data:
- TIPS 10Y and 5Y real yields
- Breakeven inflation rates (10Y, 5Y, 5Y5Y forward)
- Oil vs Real Rates scatter with regime classification
- Fed 2% target reference lines
"""

import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from scipy import stats

# Color palette for inflation charts
INFLATION_COLORS = {
    "tips_10y": "#4dabf7",  # Blue for 10Y TIPS
    "tips_5y": "#74c0fc",  # Light blue for 5Y TIPS
    "bei_10y": "#ff6b6b",  # Red for 10Y breakeven
    "bei_5y": "#ffa8a8",  # Light red for 5Y breakeven
    "forward_5y5y": "#ffd43b",  # Gold for 5Y5Y forward
    "fed_target": "#00ff88",  # Green for Fed target
    "zero_line": "#868e96",  # Gray for zero line
    # Regime colors for scatter
    "normal": "#4dabf7",  # Blue
    "breakdown": "#ff6b6b",  # Red
    "surge": "#00ff88",  # Green
    "unknown": "#868e96",  # Gray
}

# Warning zone thresholds
INFLATION_CONCERN_THRESHOLD = 2.5  # Above this = inflation concern
DEFLATION_RISK_THRESHOLD = 1.5  # Below this = deflation risk
FED_TARGET = 2.0  # Fed's 2% target


def create_inflation_panel() -> dbc.Card:
    """Create the main inflation expectations panel.

    Contains tabs for:
    - Real Rates: TIPS yields chart
    - Breakeven: BEI with Fed target
    - Oil-Rates: Scatter with regression

    Returns:
        Bootstrap Card with tabbed inflation charts.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("Inflation Expectations"),
                    html.Small(" (TIPS & Breakeven)", className="text-muted ms-2"),
                ]
            ),
            dbc.CardBody(
                [
                    dbc.Tabs(
                        [
                            dbc.Tab(
                                dcc.Graph(
                                    id="real-rates-chart",
                                    config={
                                        "displayModeBar": False,
                                        "displaylogo": False,
                                    },
                                    style={"height": "250px"},
                                ),
                                label="Real Rates",
                                tab_id="tab-real-rates",
                            ),
                            dbc.Tab(
                                dcc.Graph(
                                    id="breakeven-chart",
                                    config={
                                        "displayModeBar": False,
                                        "displaylogo": False,
                                    },
                                    style={"height": "250px"},
                                ),
                                label="Breakeven",
                                tab_id="tab-breakeven",
                            ),
                            dbc.Tab(
                                dcc.Graph(
                                    id="oil-rates-scatter",
                                    config={
                                        "displayModeBar": False,
                                        "displaylogo": False,
                                    },
                                    style={"height": "250px"},
                                ),
                                label="Oil-Rates",
                                tab_id="tab-oil-rates",
                            ),
                        ],
                        id="inflation-tabs",
                        active_tab="tab-real-rates",
                    ),
                    # Current values summary
                    html.Div(id="inflation-summary", className="mt-2"),
                ]
            ),
        ]
    )


def create_real_rates_chart(
    df: pd.DataFrame | None = None,
) -> go.Figure:
    """Create a line chart showing TIPS 10Y and 5Y yields.

    Args:
        df: DataFrame with columns: timestamp, tips_10y, tips_5y.
            Output from RealRatesAnalyzer.calculate_breakeven().

    Returns:
        Plotly Figure with real rates chart.
    """
    fig = go.Figure()

    if df is not None and not df.empty:
        # Find timestamp column
        ts_col = _find_column(df, ["timestamp", "date", "Date", "index"])
        if ts_col is None:
            ts_col = df.index.name if df.index.name else "index"
            if ts_col == "index":
                df = df.reset_index()
                ts_col = df.columns[0]

        timestamps = df[ts_col] if ts_col in df.columns else df.index

        # 10-Year TIPS yield
        if "tips_10y" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=df["tips_10y"],
                    name="10Y TIPS",
                    line=dict(color=INFLATION_COLORS["tips_10y"], width=2),
                    hovertemplate="%{y:.2f}%<extra>10Y TIPS</extra>",
                )
            )

        # 5-Year TIPS yield
        if "tips_5y" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=df["tips_5y"],
                    name="5Y TIPS",
                    line=dict(color=INFLATION_COLORS["tips_5y"], width=2, dash="dash"),
                    hovertemplate="%{y:.2f}%<extra>5Y TIPS</extra>",
                )
            )

        # Add zero reference line
        fig.add_hline(
            y=0,
            line_dash="dot",
            line_color=INFLATION_COLORS["zero_line"],
            line_width=1,
            annotation_text="Zero",
            annotation_position="right",
            annotation_font_size=10,
            annotation_font_color=INFLATION_COLORS["zero_line"],
        )

    # Layout
    fig.update_layout(
        template="plotly_white",
        title=None,
        xaxis_title=None,
        yaxis_title="Yield (%)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=50, r=20, t=30, b=30),
        height=250,
    )

    fig.update_xaxes(gridcolor="rgba(0,0,0,0.1)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.1)", showgrid=True, tickformat=".2f")

    return fig


def create_breakeven_chart(
    df: pd.DataFrame | None = None,
) -> go.Figure:
    """Create a chart showing breakeven inflation with Fed target and warning zones.

    Displays BEI 10Y, 5Y, and 5Y5Y forward with:
    - Fed 2% target line
    - Shading for warning zones (>2.5% inflation concern, <1.5% deflation risk)

    Args:
        df: DataFrame with columns: timestamp, bei_10y, bei_5y, forward_5y5y.
            Output from RealRatesAnalyzer.calculate_breakeven().

    Returns:
        Plotly Figure with breakeven inflation chart.
    """
    fig = go.Figure()

    if df is not None and not df.empty:
        # Find timestamp column
        ts_col = _find_column(df, ["timestamp", "date", "Date", "index"])
        if ts_col is None:
            ts_col = df.index.name if df.index.name else "index"
            if ts_col == "index":
                df = df.reset_index()
                ts_col = df.columns[0]

        timestamps = df[ts_col] if ts_col in df.columns else df.index

        # Determine y-axis range for shading
        bei_cols = ["bei_10y", "bei_5y", "forward_5y5y"]
        all_values = []
        for col in bei_cols:
            if col in df.columns:
                all_values.extend(df[col].dropna().tolist())

        if all_values:
            y_min = min(min(all_values), DEFLATION_RISK_THRESHOLD - 0.5)
            y_max = max(max(all_values), INFLATION_CONCERN_THRESHOLD + 0.5)
        else:
            y_min, y_max = 0, 4

        # Add inflation concern zone (>2.5%)
        fig.add_hrect(
            y0=INFLATION_CONCERN_THRESHOLD,
            y1=y_max + 0.5,
            fillcolor="rgba(255, 107, 107, 0.1)",
            line_width=0,
            annotation_text="Inflation Concern",
            annotation_position="top left",
            annotation_font_size=9,
            annotation_font_color="rgba(255, 107, 107, 0.7)",
        )

        # Add deflation risk zone (<1.5%)
        fig.add_hrect(
            y0=y_min - 0.5,
            y1=DEFLATION_RISK_THRESHOLD,
            fillcolor="rgba(77, 171, 247, 0.1)",
            line_width=0,
            annotation_text="Deflation Risk",
            annotation_position="bottom left",
            annotation_font_size=9,
            annotation_font_color="rgba(77, 171, 247, 0.7)",
        )

        # Fed 2% target line
        fig.add_hline(
            y=FED_TARGET,
            line_dash="solid",
            line_color=INFLATION_COLORS["fed_target"],
            line_width=2,
            annotation_text="Fed 2% Target",
            annotation_position="right",
            annotation_font_size=10,
            annotation_font_color=INFLATION_COLORS["fed_target"],
        )

        # 10-Year Breakeven
        if "bei_10y" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=df["bei_10y"],
                    name="10Y BEI",
                    line=dict(color=INFLATION_COLORS["bei_10y"], width=2),
                    hovertemplate="%{y:.2f}%<extra>10Y BEI</extra>",
                )
            )

        # 5-Year Breakeven
        if "bei_5y" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=df["bei_5y"],
                    name="5Y BEI",
                    line=dict(color=INFLATION_COLORS["bei_5y"], width=2, dash="dash"),
                    hovertemplate="%{y:.2f}%<extra>5Y BEI</extra>",
                )
            )

        # 5Y5Y Forward
        if "forward_5y5y" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=df["forward_5y5y"],
                    name="5Y5Y Fwd",
                    line=dict(color=INFLATION_COLORS["forward_5y5y"], width=2, dash="dot"),
                    hovertemplate="%{y:.2f}%<extra>5Y5Y Forward</extra>",
                )
            )

    # Layout
    fig.update_layout(
        template="plotly_white",
        title=None,
        xaxis_title=None,
        yaxis_title="Breakeven (%)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=50, r=20, t=30, b=30),
        height=250,
    )

    fig.update_xaxes(gridcolor="rgba(0,0,0,0.1)", showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.1)", showgrid=True, tickformat=".2f")

    return fig


def create_oil_rates_scatter(
    df: pd.DataFrame | None = None,
) -> go.Figure:
    """Create scatter plot of oil returns vs real rates changes with regression.

    Points are colored by regime (normal=blue, breakdown=red, surge=green).
    Includes regression line and R-squared annotation.

    Args:
        df: DataFrame with columns: oil_ret, rates_diff, regime.
            Output from OilRealRatesAnalyzer.compute_correlation().

    Returns:
        Plotly Figure with scatter plot and regression.
    """
    fig = go.Figure()

    if df is not None and not df.empty:
        # Filter out NaN values
        plot_df = df.dropna(subset=["oil_ret", "rates_diff"])

        if not plot_df.empty:
            # Separate by regime
            regimes = ["normal", "breakdown", "surge", "unknown"]

            for regime in regimes:
                regime_df = plot_df[plot_df.get("regime", "unknown") == regime]

                if len(regime_df) > 0:
                    fig.add_trace(
                        go.Scatter(
                            x=regime_df["rates_diff"],
                            y=regime_df["oil_ret"],
                            mode="markers",
                            name=regime.capitalize(),
                            marker=dict(
                                color=INFLATION_COLORS.get(regime, "#868e96"),
                                size=6,
                                opacity=0.7,
                            ),
                            hovertemplate=(
                                "Rates: %{x:.3f}%<br>"
                                "Oil Ret: %{y:.2%}<br>"
                                f"Regime: {regime.capitalize()}"
                                "<extra></extra>"
                            ),
                        )
                    )

            # Add regression line
            x = plot_df["rates_diff"].values
            y = plot_df["oil_ret"].values

            # Filter out any remaining NaN/inf values
            mask = np.isfinite(x) & np.isfinite(y)
            x_clean = x[mask]
            y_clean = y[mask]

            if len(x_clean) > 2:
                slope, intercept, r_value, p_value, _ = stats.linregress(x_clean, y_clean)
                r_squared = r_value**2

                # Create regression line
                x_line = np.linspace(x_clean.min(), x_clean.max(), 100)
                y_line = slope * x_line + intercept

                fig.add_trace(
                    go.Scatter(
                        x=x_line,
                        y=y_line,
                        mode="lines",
                        name="Regression",
                        line=dict(color="#868e96", width=2, dash="dash"),
                        hoverinfo="skip",
                    )
                )

                # Add R-squared annotation
                fig.add_annotation(
                    x=0.95,
                    y=0.95,
                    xref="paper",
                    yref="paper",
                    text=f"R² = {r_squared:.3f}<br>p = {p_value:.3f}",
                    showarrow=False,
                    font=dict(size=10),
                    bgcolor="rgba(255,255,255,0.8)",
                    borderpad=4,
                )

    # Layout
    fig.update_layout(
        template="plotly_white",
        title=None,
        xaxis_title="Rates Change (%)",
        yaxis_title="Oil Return",
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        margin=dict(l=50, r=20, t=30, b=40),
        height=250,
    )

    fig.update_xaxes(gridcolor="rgba(0,0,0,0.1)", showgrid=True, tickformat=".2f")
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.1)", showgrid=True, tickformat=".1%")

    return fig


def create_inflation_summary(
    bei_10y: float | None = None,
    forward_5y5y: float | None = None,
    tips_10y: float | None = None,
    oil_corr: float | None = None,
    regime: str | None = None,
) -> html.Div:
    """Create inflation expectations summary row.

    Args:
        bei_10y: 10-year breakeven inflation rate.
        forward_5y5y: 5Y5Y forward inflation rate.
        tips_10y: 10-year TIPS yield (real rate).
        oil_corr: Oil-rates correlation (30d).
        regime: Oil-rates regime (normal/breakdown/surge).

    Returns:
        Div with summary values.
    """
    # Determine colors based on values
    bei_color = "#00ff88"  # Green (normal)
    if bei_10y is not None:
        if bei_10y > INFLATION_CONCERN_THRESHOLD:
            bei_color = "#ff6b6b"  # Red (concern)
        elif bei_10y < DEFLATION_RISK_THRESHOLD:
            bei_color = "#4dabf7"  # Blue (deflation risk)

    forward_color = "#00ff88"
    if forward_5y5y is not None:
        if forward_5y5y > INFLATION_CONCERN_THRESHOLD:
            forward_color = "#ff6b6b"
        elif forward_5y5y < 1.8:  # More sensitive threshold for long-term
            forward_color = "#4dabf7"

    regime_color = INFLATION_COLORS.get(regime or "unknown", "#868e96")

    return html.Div(
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Small("10Y BEI", className="text-muted d-block"),
                        html.Span(
                            f"{bei_10y:.2f}%" if bei_10y is not None else "--",
                            style={"color": bei_color},
                        ),
                    ],
                    width=3,
                    className="text-center",
                ),
                dbc.Col(
                    [
                        html.Small("5Y5Y Fwd", className="text-muted d-block"),
                        html.Span(
                            f"{forward_5y5y:.2f}%" if forward_5y5y is not None else "--",
                            style={"color": forward_color},
                        ),
                    ],
                    width=3,
                    className="text-center",
                ),
                dbc.Col(
                    [
                        html.Small("10Y TIPS", className="text-muted d-block"),
                        html.Span(
                            f"{tips_10y:.2f}%" if tips_10y is not None else "--",
                            style={"color": INFLATION_COLORS["tips_10y"]},
                        ),
                    ],
                    width=3,
                    className="text-center",
                ),
                dbc.Col(
                    [
                        html.Small("Oil Corr", className="text-muted d-block"),
                        html.Span(
                            f"{oil_corr:.2f}" if oil_corr is not None else "--",
                            style={"color": regime_color},
                        ),
                        html.Small(
                            f" ({regime})" if regime else "",
                            className="text-muted",
                        ),
                    ],
                    width=3,
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
