"""Calendar strip component for upcoming events.

Displays:
- Horizontal strip showing next 5 upcoming events
- Impact-colored event badges
- Calendar overlay function for charts
"""

from datetime import date, timedelta

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import html

from liquidity.calendar.base import CalendarEvent, ImpactLevel

# Impact level to badge color mapping
IMPACT_COLORS = {
    ImpactLevel.HIGH: "danger",
    ImpactLevel.MEDIUM: "warning",
    ImpactLevel.LOW: "secondary",
}

# Impact level to line color mapping (for chart overlay)
IMPACT_LINE_COLORS = {
    ImpactLevel.HIGH: "rgba(255, 68, 68, 0.8)",
    ImpactLevel.MEDIUM: "rgba(255, 170, 0, 0.6)",
    ImpactLevel.LOW: "rgba(136, 136, 136, 0.4)",
}


def create_calendar_strip() -> html.Div:
    """Create the calendar events strip.

    A horizontal strip showing upcoming events with impact-coded badges.

    Returns:
        Div containing the calendar strip.
    """
    return html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Span(
                            "Upcoming Events: ",
                            className="calendar-label text-muted",
                            style={"fontWeight": "500"},
                        ),
                        width="auto",
                        className="d-flex align-items-center",
                    ),
                    dbc.Col(
                        html.Div(
                            id="calendar-events",
                            className="calendar-strip d-flex flex-wrap align-items-center",
                        ),
                    ),
                ],
                className="g-2 py-2",
            ),
        ],
        className="calendar-container",
        style={
            "backgroundColor": "#1a1a1a",
            "borderRadius": "4px",
            "padding": "0.5rem 1rem",
        },
    )


def create_calendar_events(events: list[CalendarEvent] | None = None) -> list:
    """Render event badges for the calendar strip.

    Args:
        events: List of CalendarEvent objects. Shows at most 5.

    Returns:
        List of dbc.Badge components.
    """
    if not events:
        return [
            html.Span(
                "No upcoming events",
                className="text-muted",
                style={"fontStyle": "italic"},
            )
        ]

    badges = []
    for event in events[:5]:  # Show next 5 events
        color = IMPACT_COLORS.get(event.impact, "secondary")

        # Format date
        event_date_str = event.event_date.strftime("%b %d")

        # Add days until
        days_until = event.days_until
        if days_until < 0:
            time_str = "Past"
        elif days_until == 0:
            time_str = "Today"
        elif days_until == 1:
            time_str = "Tomorrow"
        else:
            time_str = f"in {days_until}d"

        badges.append(
            dbc.Badge(
                [
                    html.Span(event.title, style={"fontWeight": "500"}),
                    html.Small(f" ({event_date_str}, {time_str})", className="ms-1"),
                ],
                color=color,
                className="me-2 mb-1",
                style={"fontSize": "0.85rem"},
            )
        )

    return badges


def create_calendar_events_from_dict(events: list[dict] | None = None) -> list:
    """Render event badges from dictionary format.

    Alternative function for when events are passed as dicts.

    Args:
        events: List of event dictionaries with keys:
            - title: Event title
            - date: Event date (date object or ISO string)
            - impact: Impact level ("high", "medium", "low")

    Returns:
        List of dbc.Badge components.
    """
    if not events:
        return [
            html.Span(
                "No upcoming events",
                className="text-muted",
                style={"fontStyle": "italic"},
            )
        ]

    badges = []
    today = date.today()

    for event in events[:5]:
        # Parse impact
        impact_str = event.get("impact", "medium").lower()
        color = {
            "high": "danger",
            "medium": "warning",
            "low": "secondary",
        }.get(impact_str, "secondary")

        # Parse date
        event_date = event.get("date")
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)
        elif not isinstance(event_date, date):
            event_date = today

        # Format date
        event_date_str = event_date.strftime("%b %d")

        # Days until
        days_until = (event_date - today).days
        if days_until == 0:
            time_str = "Today"
        elif days_until == 1:
            time_str = "Tomorrow"
        elif days_until < 0:
            time_str = "Past"
        else:
            time_str = f"in {days_until}d"

        title = event.get("title", "Event")

        badges.append(
            dbc.Badge(
                [
                    html.Span(title, style={"fontWeight": "500"}),
                    html.Small(f" ({event_date_str}, {time_str})", className="ms-1"),
                ],
                color=color,
                className="me-2 mb-1",
                style={"fontSize": "0.85rem"},
            )
        )

    return badges


def add_calendar_overlay(
    fig: go.Figure,
    events: list[CalendarEvent] | None = None,
    high_impact_only: bool = True,
) -> go.Figure:
    """Add vertical lines for events on a time series chart.

    Args:
        fig: Plotly Figure to add overlay to.
        events: List of CalendarEvent objects.
        high_impact_only: If True, only show HIGH impact events.

    Returns:
        Modified Plotly Figure with event lines.
    """
    if not events:
        return fig

    for event in events:
        # Filter by impact if requested
        if high_impact_only and event.impact != ImpactLevel.HIGH:
            continue

        line_color = IMPACT_LINE_COLORS.get(event.impact, IMPACT_LINE_COLORS[ImpactLevel.LOW])

        # Add vertical line as shape (more compatible)
        fig.add_shape(
            type="line",
            x0=event.event_date.isoformat(),
            x1=event.event_date.isoformat(),
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color=line_color, width=1, dash="dash"),
        )

        # Add annotation separately
        fig.add_annotation(
            x=event.event_date.isoformat(),
            y=1,
            yref="paper",
            text=event.title[:20],  # Truncate long titles
            showarrow=False,
            font=dict(size=9, color=line_color),
            bgcolor="rgba(0,0,0,0.6)",
            borderpad=2,
        )

    return fig


def add_calendar_overlay_from_dict(
    fig: go.Figure,
    events: list[dict] | None = None,
    high_impact_only: bool = True,
) -> go.Figure:
    """Add event overlay from dictionary format.

    Args:
        fig: Plotly Figure to add overlay to.
        events: List of event dictionaries.
        high_impact_only: If True, only show HIGH impact events.

    Returns:
        Modified Plotly Figure.
    """
    if not events:
        return fig

    for event in events:
        impact_str = event.get("impact", "medium").lower()

        # Filter by impact if requested
        if high_impact_only and impact_str != "high":
            continue

        # Parse date
        event_date = event.get("date")
        if isinstance(event_date, str):
            event_date = date.fromisoformat(event_date)
        elif not isinstance(event_date, date):
            continue

        # Get line color
        line_color = {
            "high": "rgba(255, 68, 68, 0.8)",
            "medium": "rgba(255, 170, 0, 0.6)",
            "low": "rgba(136, 136, 136, 0.4)",
        }.get(impact_str, "rgba(136, 136, 136, 0.4)")

        title = event.get("title", "Event")

        # Add vertical line as shape (more compatible)
        fig.add_shape(
            type="line",
            x0=event_date.isoformat(),
            x1=event_date.isoformat(),
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color=line_color, width=1, dash="dash"),
        )

        # Add annotation separately
        fig.add_annotation(
            x=event_date.isoformat(),
            y=1,
            yref="paper",
            text=title[:20],
            showarrow=False,
            font=dict(size=9, color=line_color),
            bgcolor="rgba(0,0,0,0.6)",
            borderpad=2,
        )

    return fig


def get_upcoming_events(
    events: list[CalendarEvent] | None = None,
    days_ahead: int = 30,
    limit: int = 5,
) -> list[CalendarEvent]:
    """Filter events to upcoming ones within date range.

    Args:
        events: List of all CalendarEvent objects.
        days_ahead: Number of days to look ahead.
        limit: Maximum number of events to return.

    Returns:
        Filtered and sorted list of upcoming events.
    """
    if not events:
        return []

    today = date.today()
    end_date = today + timedelta(days=days_ahead)

    upcoming = [
        e for e in events
        if today <= e.event_date <= end_date
    ]

    # Sort by date
    upcoming.sort(key=lambda e: e.event_date)

    return upcoming[:limit]
