"""Quality indicators UI components for the dashboard.

Provides visual indicators for data quality status:
- QA-08: Dashboard shows data freshness indicator per source
- QA-09: Dashboard shows data quality score (completeness %)

Components:
- Quality status bar with overall score
- Freshness indicators (badges for stale sources)
- Collapsible detail panel with gauges
- Source freshness table
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html

from liquidity.validation import FreshnessStatus, QualityReport


def format_relative_time(timestamp: datetime) -> str:
    """Format a timestamp as relative time (e.g., '5 min ago').

    Args:
        timestamp: The timestamp to format.

    Returns:
        Human-readable relative time string.
    """
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    delta = now - timestamp

    if delta < timedelta(minutes=1):
        return "just now"
    elif delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} min ago"
    elif delta < timedelta(days=1):
        hours = int(delta.total_seconds() / 3600)
        return f"{hours}h ago"
    else:
        days = delta.days
        return f"{days}d ago"


def create_quality_status_bar(
    quality_report: QualityReport | None = None,
) -> dbc.Row:
    """Create status bar with quality indicators.

    Args:
        quality_report: Quality report from ValidationEngine.
            If None, shows placeholder values.

    Returns:
        Bootstrap Row with quality badges and freshness indicators.
    """
    if quality_report is None:
        return dbc.Row(
            [
                dbc.Col(
                    dbc.Badge("Quality: --", color="secondary", className="me-2"),
                    width="auto",
                ),
                dbc.Col(
                    html.Span("Loading...", className="text-muted"),
                    width="auto",
                ),
            ],
            className="mb-3 align-items-center",
            id="quality-status-row",
        )

    # Determine score color
    if quality_report.overall_score >= 90:
        score_color = "success"
    elif quality_report.overall_score >= 70:
        score_color = "warning"
    else:
        score_color = "danger"

    return dbc.Row(
        [
            # Quality score badge
            dbc.Col(
                dbc.Badge(
                    f"Quality: {quality_report.overall_score:.0f}%",
                    color=score_color,
                    className="me-2",
                    style={"fontSize": "0.9rem"},
                ),
                width="auto",
            ),
            # Last update time
            dbc.Col(
                html.Span(
                    [
                        html.I(className="bi bi-clock me-1"),
                        format_relative_time(quality_report.timestamp),
                    ],
                    className="text-muted",
                ),
                width="auto",
            ),
            # Freshness indicators
            dbc.Col(
                create_freshness_indicators(quality_report.stale_sources),
                width="auto",
            ),
            # Critical issues warning
            dbc.Col(
                _create_critical_issues_badge(quality_report.critical_issues),
                width="auto",
            ) if quality_report.critical_issues else None,
        ],
        className="mb-3 align-items-center g-3",
        id="quality-status-row",
    )


def create_freshness_indicators(stale_sources: list[str]) -> html.Div:
    """Show freshness status badges for stale sources.

    Args:
        stale_sources: List of stale data source names.

    Returns:
        Div containing freshness status and badges.
    """
    if not stale_sources:
        return html.Div(
            html.Span(
                [
                    html.I(className="bi bi-check-circle me-1"),
                    "All data fresh",
                ],
                className="text-success",
            )
        )

    # Show first 3 stale sources as badges
    badges: list[Any] = [
        dbc.Badge(source, color="warning", className="me-1", pill=True)
        for source in stale_sources[:3]
    ]

    # If more than 3, show count
    if len(stale_sources) > 3:
        badges.append(
            html.Span(
                f"+{len(stale_sources) - 3} more",
                className="text-muted ms-1",
                style={"fontSize": "0.8rem"},
            )
        )

    return html.Div(
        [
            html.Span(
                [html.I(className="bi bi-exclamation-triangle me-1"), "Stale: "],
                className="text-warning",
            ),
            *badges,
        ],
        className="d-flex align-items-center",
    )


def _create_critical_issues_badge(critical_issues: list[str]) -> html.Span:
    """Create a badge for critical issues.

    Args:
        critical_issues: List of critical issue descriptions.

    Returns:
        Badge component or None.
    """
    if not critical_issues:
        return html.Span()

    return html.Span(
        [
            dbc.Badge(
                [
                    html.I(className="bi bi-exclamation-octagon me-1"),
                    f"{len(critical_issues)} Critical",
                ],
                color="danger",
                className="me-2",
            ),
        ],
        id="critical-issues-badge",
        style={"cursor": "pointer"},
    )


def create_quality_detail_panel() -> dbc.Card:
    """Create detailed quality metrics panel (collapsible).

    Returns:
        Card component with collapsible body containing gauges and table.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                dbc.Button(
                    [
                        html.I(className="bi bi-graph-up me-2"),
                        "Data Quality Details",
                        html.I(
                            className="bi bi-chevron-down ms-2",
                            id="quality-collapse-icon",
                        ),
                    ],
                    id="quality-collapse-toggle",
                    color="link",
                    className="p-0 text-decoration-none",
                    style={"color": "#aaa"},
                ),
                className="py-2",
            ),
            dbc.Collapse(
                dbc.CardBody(
                    [
                        # Gauge row
                        dbc.Row(
                            [
                                dbc.Col(
                                    dcc.Graph(
                                        id="freshness-gauge",
                                        config={"displayModeBar": False},
                                        style={"height": "150px"},
                                    ),
                                    width=4,
                                ),
                                dbc.Col(
                                    dcc.Graph(
                                        id="completeness-gauge",
                                        config={"displayModeBar": False},
                                        style={"height": "150px"},
                                    ),
                                    width=4,
                                ),
                                dbc.Col(
                                    dcc.Graph(
                                        id="validation-gauge",
                                        config={"displayModeBar": False},
                                        style={"height": "150px"},
                                    ),
                                    width=4,
                                ),
                            ],
                            className="mb-3",
                        ),
                        html.Hr(className="my-3"),
                        # Source freshness table
                        html.H6("Source Freshness", className="text-muted mb-2"),
                        html.Div(id="source-freshness-table"),
                    ]
                ),
                id="quality-collapse",
                is_open=False,
            ),
        ],
        className="mb-3",
        id="quality-detail-card",
    )


def create_quality_gauge(
    value: float,
    label: str,
    _gauge_id: str | None = None,
) -> go.Figure:
    """Create a gauge figure for a quality metric.

    Args:
        value: Metric value (0-100).
        label: Gauge label.
        gauge_id: Optional ID for the gauge (not used in figure).

    Returns:
        Plotly Figure with gauge indicator.
    """
    # Determine color based on value
    if value >= 90:
        color = "#00ff88"  # Green
    elif value >= 70:
        color = "#ffaa00"  # Yellow/Orange
    else:
        color = "#ff4444"  # Red

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": label, "font": {"size": 14, "color": "#aaa"}},
            number={"suffix": "%", "font": {"color": "#eee"}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "#555",
                },
                "bar": {"color": color},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 70], "color": "rgba(255, 68, 68, 0.2)"},
                    {"range": [70, 90], "color": "rgba(255, 170, 0, 0.2)"},
                    {"range": [90, 100], "color": "rgba(0, 255, 136, 0.2)"},
                ],
                "threshold": {
                    "line": {"color": "#fff", "width": 2},
                    "thickness": 0.75,
                    "value": value,
                },
            },
        )
    )

    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=20, r=20, t=50, b=20),
        height=150,
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#eee"},
    )

    return fig


def create_source_freshness_table(
    last_updates: dict[str, datetime],
    freshness_status: dict[str, FreshnessStatus] | None = None,
) -> dbc.Table:
    """Create a table showing freshness per data source.

    Args:
        last_updates: Mapping of source names to last update timestamps.
        freshness_status: Optional mapping of source names to FreshnessStatus.

    Returns:
        Bootstrap Table with source freshness information.
    """
    if not last_updates:
        return dbc.Table(
            [html.Tbody([html.Tr([html.Td("No data sources available")])])],
            className="text-muted",
        )

    rows = []
    now = datetime.now(UTC)

    for source, ts in sorted(last_updates.items()):
        # Ensure timezone awareness
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        age = now - ts
        age_str = format_relative_time(ts)

        # Determine status
        if freshness_status and source in freshness_status:
            status = freshness_status[source]
        else:
            # Default: <24h = fresh, <48h = stale, else critical
            if age < timedelta(hours=24):
                status = FreshnessStatus.FRESH
            elif age < timedelta(hours=48):
                status = FreshnessStatus.STALE
            else:
                status = FreshnessStatus.CRITICAL

        # Status icon and color
        if status == FreshnessStatus.FRESH:
            status_icon = html.I(className="bi bi-check-circle text-success")
        elif status == FreshnessStatus.STALE:
            status_icon = html.I(className="bi bi-exclamation-triangle text-warning")
        else:
            status_icon = html.I(className="bi bi-x-circle text-danger")

        rows.append(
            html.Tr(
                [
                    html.Td(source, style={"fontFamily": "monospace"}),
                    html.Td(age_str),
                    html.Td(status_icon, className="text-center"),
                ]
            )
        )

    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Source"),
                        html.Th("Last Update"),
                        html.Th("Status", className="text-center"),
                    ]
                )
            ),
            html.Tbody(rows),
        ],
        striped=True,
        bordered=True,
        hover=True,
        size="sm",
        className="mb-0",
    )


def create_quality_summary_card(
    quality_report: QualityReport | None = None,
) -> dbc.Card:
    """Create a compact quality summary card for the sidebar or header.

    Args:
        quality_report: Quality report from ValidationEngine.

    Returns:
        Card component with quality summary.
    """
    if quality_report is None:
        return dbc.Card(
            dbc.CardBody(
                [
                    html.H6("Data Quality", className="card-title text-muted"),
                    html.H3("--", className="text-center"),
                ]
            ),
            className="text-center",
        )

    # Score color
    if quality_report.overall_score >= 90:
        color_class = "text-success"
    elif quality_report.overall_score >= 70:
        color_class = "text-warning"
    else:
        color_class = "text-danger"

    return dbc.Card(
        dbc.CardBody(
            [
                html.H6("Data Quality", className="card-title text-muted mb-1"),
                html.H3(
                    f"{quality_report.overall_score:.0f}%",
                    className=f"text-center {color_class} mb-1",
                ),
                html.Small(
                    f"{len(quality_report.stale_sources)} stale"
                    if quality_report.stale_sources
                    else "All fresh",
                    className="text-muted",
                ),
            ]
        ),
        className="text-center",
    )


def get_quality_status_for_export(
    quality_report: QualityReport | None,
) -> dict[str, Any]:
    """Get quality status as a dictionary for HTML export.

    Args:
        quality_report: Quality report from ValidationEngine.

    Returns:
        Dictionary with quality metadata for export.
    """
    if quality_report is None:
        return {
            "quality_score": "N/A",
            "stale_sources": [],
            "timestamp": datetime.now(UTC).isoformat(),
        }

    return {
        "quality_score": quality_report.overall_score,
        "freshness_score": quality_report.freshness_score,
        "completeness_score": quality_report.completeness_score,
        "validation_score": quality_report.validation_score,
        "stale_sources": quality_report.stale_sources,
        "critical_issues": quality_report.critical_issues,
        "anomaly_count": quality_report.anomaly_count,
        "timestamp": quality_report.timestamp.isoformat(),
    }
