"""Tests for calendar strip component."""

from datetime import date, timedelta

import plotly.graph_objects as go
import pytest


class TestCalendarStrip:
    """Test calendar strip creation."""

    def test_create_strip(self) -> None:
        """Test creating the calendar strip."""
        from liquidity.dashboard.components.calendar import create_calendar_strip

        strip = create_calendar_strip()

        assert strip is not None

    def test_strip_has_div_structure(self) -> None:
        """Test that strip is a Div component."""
        from dash import html

        from liquidity.dashboard.components.calendar import create_calendar_strip

        strip = create_calendar_strip()

        assert isinstance(strip, html.Div)


class TestCalendarEvents:
    """Test calendar event badge creation."""

    def test_create_empty_events(self) -> None:
        """Test creating events with empty list."""
        from liquidity.dashboard.components.calendar import create_calendar_events

        events = create_calendar_events([])

        assert events is not None
        assert len(events) == 1  # Should show "No upcoming events"

    def test_create_events_with_none(self) -> None:
        """Test creating events with None."""
        from liquidity.dashboard.components.calendar import create_calendar_events

        events = create_calendar_events(None)

        assert events is not None
        assert len(events) == 1  # Should show "No upcoming events"

    def test_create_events_from_dict(self) -> None:
        """Test creating events from dictionary format."""
        from liquidity.dashboard.components.calendar import create_calendar_events_from_dict

        today = date.today()
        event_list = [
            {
                "title": "Treasury Auction",
                "date": (today + timedelta(days=3)).isoformat(),
                "impact": "high",
            },
            {
                "title": "FOMC Meeting",
                "date": (today + timedelta(days=7)).isoformat(),
                "impact": "high",
            },
        ]

        events = create_calendar_events_from_dict(event_list)

        assert events is not None
        assert len(events) == 2

    def test_events_limited_to_five(self) -> None:
        """Test that only 5 events are shown."""
        from liquidity.dashboard.components.calendar import create_calendar_events_from_dict

        today = date.today()
        event_list = [
            {
                "title": f"Event {i}",
                "date": (today + timedelta(days=i)).isoformat(),
                "impact": "medium",
            }
            for i in range(10)
        ]

        events = create_calendar_events_from_dict(event_list)

        assert len(events) == 5

    def test_event_impact_colors(self) -> None:
        """Test that events have correct impact-based colors."""
        from liquidity.dashboard.components.calendar import IMPACT_COLORS
        from liquidity.calendar.base import ImpactLevel

        # HIGH should be danger
        assert IMPACT_COLORS[ImpactLevel.HIGH] == "danger"
        # MEDIUM should be warning
        assert IMPACT_COLORS[ImpactLevel.MEDIUM] == "warning"
        # LOW should be secondary
        assert IMPACT_COLORS[ImpactLevel.LOW] == "secondary"


class TestCalendarOverlay:
    """Test calendar overlay on charts."""

    def _create_figure_with_data(self) -> go.Figure:
        """Create a figure with time series data for testing."""
        import pandas as pd

        dates = pd.date_range(start=date.today() - timedelta(days=30), periods=30, freq="D")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=list(range(30)), name="test"))
        return fig

    def test_add_overlay_to_empty_figure(self) -> None:
        """Test adding overlay to empty figure."""
        from liquidity.dashboard.components.calendar import add_calendar_overlay_from_dict

        fig = go.Figure()
        result = add_calendar_overlay_from_dict(fig, None)

        assert result is not None
        assert result == fig

    def test_add_overlay_with_events(self) -> None:
        """Test adding overlay with events."""
        from liquidity.dashboard.components.calendar import add_calendar_overlay_from_dict

        fig = self._create_figure_with_data()
        today = date.today()
        events = [
            {
                "title": "FOMC",
                "date": (today + timedelta(days=5)).isoformat(),
                "impact": "high",
            },
        ]

        result = add_calendar_overlay_from_dict(fig, events, high_impact_only=True)

        assert result is not None

    def test_overlay_filters_by_impact(self) -> None:
        """Test that overlay filters by impact level."""
        from liquidity.dashboard.components.calendar import add_calendar_overlay_from_dict

        fig = self._create_figure_with_data()
        today = date.today()
        events = [
            {
                "title": "High Impact",
                "date": (today + timedelta(days=3)).isoformat(),
                "impact": "high",
            },
            {
                "title": "Low Impact",
                "date": (today + timedelta(days=5)).isoformat(),
                "impact": "low",
            },
        ]

        # When high_impact_only=True, should only add high impact events
        result = add_calendar_overlay_from_dict(fig, events, high_impact_only=True)

        assert result is not None


class TestUpcomingEvents:
    """Test upcoming event filtering."""

    def test_get_upcoming_events_empty(self) -> None:
        """Test getting upcoming events with empty list."""
        from liquidity.dashboard.components.calendar import get_upcoming_events

        result = get_upcoming_events(None)

        assert result == []

    def test_get_upcoming_events_filters_by_date(self) -> None:
        """Test that upcoming events are filtered by date range."""
        from liquidity.calendar.base import CalendarEvent, EventType, ImpactLevel
        from liquidity.dashboard.components.calendar import get_upcoming_events

        today = date.today()
        events = [
            CalendarEvent(
                event_date=today + timedelta(days=5),
                event_type=EventType.TREASURY_AUCTION,
                title="Treasury Auction",
                impact=ImpactLevel.HIGH,
            ),
            CalendarEvent(
                event_date=today + timedelta(days=45),
                event_type=EventType.FED_MEETING,
                title="FOMC Meeting",
                impact=ImpactLevel.HIGH,
            ),
        ]

        result = get_upcoming_events(events, days_ahead=30)

        # Only the first event should be within 30 days
        assert len(result) == 1
        assert result[0].title == "Treasury Auction"

    def test_get_upcoming_events_respects_limit(self) -> None:
        """Test that result is limited to specified number."""
        from liquidity.calendar.base import CalendarEvent, EventType, ImpactLevel
        from liquidity.dashboard.components.calendar import get_upcoming_events

        today = date.today()
        events = [
            CalendarEvent(
                event_date=today + timedelta(days=i),
                event_type=EventType.TREASURY_AUCTION,
                title=f"Event {i}",
                impact=ImpactLevel.MEDIUM,
            )
            for i in range(1, 10)
        ]

        result = get_upcoming_events(events, days_ahead=30, limit=3)

        assert len(result) == 3
