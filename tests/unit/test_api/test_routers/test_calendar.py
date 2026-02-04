"""Unit tests for calendar router endpoints."""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from liquidity.api.server import app
from liquidity.calendar.base import CalendarEvent, EventType, ImpactLevel


class TestCalendarEventsEndpoint:
    """Tests for GET /calendar/events endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_events(self):
        """Create mock calendar events."""
        today = date.today()
        return [
            CalendarEvent(
                event_date=today + timedelta(days=1),
                event_type=EventType.FED_MEETING,
                title="FOMC Meeting",
                description="Federal Reserve policy decision",
                impact=ImpactLevel.HIGH,
            ),
            CalendarEvent(
                event_date=today + timedelta(days=5),
                event_type=EventType.TREASURY_AUCTION,
                title="10Y Treasury Auction",
                description="10-year note auction",
                settlement_date=today + timedelta(days=7),
                impact=ImpactLevel.HIGH,
            ),
            CalendarEvent(
                event_date=today + timedelta(days=10),
                event_type=EventType.TAX_DATE,
                title="Corporate Tax Payment",
                impact=ImpactLevel.MEDIUM,
            ),
        ]

    def test_get_calendar_events_success(self, client, mock_events):
        """Test successful calendar events response."""
        mock_registry = MagicMock()
        mock_registry.get_events.return_value = mock_events

        from liquidity.api.deps import get_calendar_registry

        app.dependency_overrides[get_calendar_registry] = lambda: mock_registry

        try:
            response = client.get("/calendar/events")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert "start" in data
        assert "end" in data
        assert "count" in data
        assert "events" in data
        assert "metadata" in data

        assert data["count"] == 3
        assert len(data["events"]) == 3

        # Check event structure
        event = data["events"][0]
        assert "date" in event
        assert "event_type" in event
        assert "title" in event
        assert "impact" in event

    def test_get_calendar_events_with_date_range(self, client, mock_events):
        """Test calendar events with custom date range."""
        mock_registry = MagicMock()
        mock_registry.get_events.return_value = mock_events[:1]

        from liquidity.api.deps import get_calendar_registry

        app.dependency_overrides[get_calendar_registry] = lambda: mock_registry

        today = date.today()
        start_str = today.isoformat()
        end_str = (today + timedelta(days=7)).isoformat()

        try:
            response = client.get(f"/calendar/events?start={start_str}&end={end_str}")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["start"] == start_str
        assert data["end"] == end_str

    def test_get_calendar_events_filter_by_type(self, client, mock_events):
        """Test calendar events filtered by event type."""
        [e for e in mock_events if e.event_type == EventType.FED_MEETING]

        mock_registry = MagicMock()
        mock_registry.get_events.return_value = mock_events

        from liquidity.api.deps import get_calendar_registry

        app.dependency_overrides[get_calendar_registry] = lambda: mock_registry

        try:
            response = client.get("/calendar/events?event_type=fed_meeting")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert all(e["event_type"] == "fed_meeting" for e in data["events"])

    def test_get_calendar_events_filter_by_impact(self, client, mock_events):
        """Test calendar events filtered by impact level."""
        mock_registry = MagicMock()
        mock_registry.get_events.return_value = mock_events

        from liquidity.api.deps import get_calendar_registry

        app.dependency_overrides[get_calendar_registry] = lambda: mock_registry

        try:
            response = client.get("/calendar/events?impact=high")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert all(e["impact"] == "high" for e in data["events"])

    def test_get_calendar_events_invalid_event_type(self, client, mock_events):
        """Test calendar events with invalid event type."""
        mock_registry = MagicMock()
        mock_registry.get_events.return_value = mock_events

        from liquidity.api.deps import get_calendar_registry

        app.dependency_overrides[get_calendar_registry] = lambda: mock_registry

        try:
            response = client.get("/calendar/events?event_type=invalid_type")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "Invalid event_type" in response.json()["detail"]

    def test_get_calendar_events_invalid_date_range(self, client, mock_events):
        """Test calendar events with end before start."""
        mock_registry = MagicMock()
        mock_registry.get_events.return_value = mock_events

        from liquidity.api.deps import get_calendar_registry

        app.dependency_overrides[get_calendar_registry] = lambda: mock_registry

        today = date.today()
        start_str = (today + timedelta(days=10)).isoformat()
        end_str = today.isoformat()

        try:
            response = client.get(f"/calendar/events?start={start_str}&end={end_str}")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "End date must be after start date" in response.json()["detail"]


class TestCalendarNextEndpoint:
    """Tests for GET /calendar/next endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_events(self):
        """Create mock calendar events."""
        today = date.today()
        return [
            CalendarEvent(
                event_date=today + timedelta(days=1),
                event_type=EventType.FED_MEETING,
                title="FOMC Meeting",
                impact=ImpactLevel.HIGH,
            ),
            CalendarEvent(
                event_date=today + timedelta(days=5),
                event_type=EventType.TREASURY_AUCTION,
                title="10Y Treasury Auction",
                impact=ImpactLevel.HIGH,
            ),
            CalendarEvent(
                event_date=today + timedelta(days=10),
                event_type=EventType.TAX_DATE,
                title="Corporate Tax Payment",
                impact=ImpactLevel.MEDIUM,
            ),
        ]

    def test_get_next_events_default(self, client, mock_events):
        """Test get next events with default parameters."""
        high_impact = [e for e in mock_events if e.impact == ImpactLevel.HIGH]

        mock_registry = MagicMock()
        mock_registry.get_high_impact_events.return_value = high_impact

        from liquidity.api.deps import get_calendar_registry

        app.dependency_overrides[get_calendar_registry] = lambda: mock_registry

        try:
            response = client.get("/calendar/next")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()

        assert "count" in data
        assert "events" in data
        assert data["count"] == 2  # Only high-impact events

    def test_get_next_events_with_limit(self, client, mock_events):
        """Test get next events with custom limit."""
        mock_registry = MagicMock()
        mock_registry.get_high_impact_events.return_value = mock_events[:1]

        from liquidity.api.deps import get_calendar_registry

        app.dependency_overrides[get_calendar_registry] = lambda: mock_registry

        try:
            response = client.get("/calendar/next?limit=1")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["count"] <= 1

    def test_get_next_events_all_impact(self, client, mock_events):
        """Test get next events including all impact levels."""
        mock_registry = MagicMock()
        mock_registry.get_events.return_value = mock_events

        from liquidity.api.deps import get_calendar_registry

        app.dependency_overrides[get_calendar_registry] = lambda: mock_registry

        try:
            response = client.get("/calendar/next?high_impact_only=false")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3  # All events

    def test_get_next_events_limit_validation(self, client):
        """Test limit parameter validation."""
        # Limit too high
        response = client.get("/calendar/next?limit=100")
        assert response.status_code == 422

        # Limit too low
        response = client.get("/calendar/next?limit=0")
        assert response.status_code == 422
