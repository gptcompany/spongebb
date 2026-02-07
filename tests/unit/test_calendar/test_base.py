"""Unit tests for calendar base classes.

Run with: uv run pytest tests/unit/test_calendar/test_base.py -v
"""

from datetime import date

import pytest

from liquidity.calendar.base import (
    BaseCalendar,
    CalendarEvent,
    EventType,
    ImpactLevel,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_exist(self) -> None:
        """Test all expected event types exist."""
        assert EventType.TREASURY_AUCTION.value == "treasury_auction"
        assert EventType.FED_MEETING.value == "fed_meeting"
        assert EventType.ECB_MEETING.value == "ecb_meeting"
        assert EventType.BOJ_MEETING.value == "boj_meeting"
        assert EventType.BOE_MEETING.value == "boe_meeting"
        assert EventType.OPEC_MEETING.value == "opec_meeting"
        assert EventType.TAX_DATE.value == "tax_date"
        assert EventType.QUARTER_END.value == "quarter_end"
        assert EventType.MONTH_END.value == "month_end"
        assert EventType.HOLIDAY.value == "holiday"

    def test_all_event_types_count(self) -> None:
        """Test total number of event types."""
        assert len(EventType) == 10


class TestImpactLevel:
    """Tests for ImpactLevel enum."""

    def test_impact_levels_exist(self) -> None:
        """Test all impact levels exist."""
        assert ImpactLevel.LOW.value == "low"
        assert ImpactLevel.MEDIUM.value == "medium"
        assert ImpactLevel.HIGH.value == "high"

    def test_all_impact_levels_count(self) -> None:
        """Test total number of impact levels."""
        assert len(ImpactLevel) == 3


class TestCalendarEvent:
    """Tests for CalendarEvent dataclass."""

    def test_create_basic_event(self) -> None:
        """Test creating a basic calendar event."""
        event = CalendarEvent(
            event_date=date(2026, 1, 28),
            event_type=EventType.FED_MEETING,
            title="FOMC Meeting",
        )

        assert event.date == date(2026, 1, 28)
        assert event.event_type == EventType.FED_MEETING
        assert event.title == "FOMC Meeting"
        assert event.description is None
        assert event.settlement_date is None
        assert event.impact == ImpactLevel.MEDIUM  # Default
        assert event.metadata == {}

    def test_create_full_event(self) -> None:
        """Test creating an event with all fields."""
        event = CalendarEvent(
            event_date=date(2026, 1, 8),
            event_type=EventType.TREASURY_AUCTION,
            title="10-Year Note Auction",
            description="US Treasury 10-Year Note auction",
            settlement_date=date(2026, 1, 10),
            impact=ImpactLevel.HIGH,
            metadata={"security_type": "10-Year Note"},
        )

        assert event.date == date(2026, 1, 8)
        assert event.settlement_date == date(2026, 1, 10)
        assert event.impact == ImpactLevel.HIGH
        assert event.metadata["security_type"] == "10-Year Note"

    def test_is_high_impact(self) -> None:
        """Test is_high_impact property."""
        high = CalendarEvent(
            event_date=date(2026, 1, 1),
            event_type=EventType.FED_MEETING,
            title="High",
            impact=ImpactLevel.HIGH,
        )
        medium = CalendarEvent(
            event_date=date(2026, 1, 1),
            event_type=EventType.FED_MEETING,
            title="Medium",
            impact=ImpactLevel.MEDIUM,
        )
        low = CalendarEvent(
            event_date=date(2026, 1, 1),
            event_type=EventType.FED_MEETING,
            title="Low",
            impact=ImpactLevel.LOW,
        )

        assert high.is_high_impact is True
        assert medium.is_high_impact is False
        assert low.is_high_impact is False

    def test_days_until(self) -> None:
        """Test days_until property returns correct value."""
        # Use a fixed future date for consistent testing
        future_date = date(2030, 1, 1)
        event = CalendarEvent(
            event_date=future_date,
            event_type=EventType.FED_MEETING,
            title="Future Event",
        )

        # Should be positive for future dates
        assert event.days_until > 0

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        event = CalendarEvent(
            event_date=date(2026, 1, 8),
            event_type=EventType.TREASURY_AUCTION,
            title="10-Year Note Auction",
            description="Test description",
            settlement_date=date(2026, 1, 10),
            impact=ImpactLevel.HIGH,
            metadata={"key": "value"},
        )

        result = event.to_dict()

        assert result["date"] == "2026-01-08"
        assert result["event_type"] == "treasury_auction"
        assert result["title"] == "10-Year Note Auction"
        assert result["description"] == "Test description"
        assert result["settlement_date"] == "2026-01-10"
        assert result["impact"] == "high"
        assert "key" in str(result["metadata"])

    def test_events_are_sortable_by_date(self) -> None:
        """Test that events sort by date."""
        event1 = CalendarEvent(
            event_date=date(2026, 3, 1),
            event_type=EventType.FED_MEETING,
            title="March",
        )
        event2 = CalendarEvent(
            event_date=date(2026, 1, 1),
            event_type=EventType.FED_MEETING,
            title="January",
        )
        event3 = CalendarEvent(
            event_date=date(2026, 2, 1),
            event_type=EventType.FED_MEETING,
            title="February",
        )

        sorted_events = sorted([event1, event2, event3])

        assert sorted_events[0].title == "January"
        assert sorted_events[1].title == "February"
        assert sorted_events[2].title == "March"

    def test_events_sort_by_impact_within_same_date(self) -> None:
        """Test that events with same date sort by impact (high first)."""
        low = CalendarEvent(
            event_date=date(2026, 1, 1),
            event_type=EventType.HOLIDAY,
            title="Low Impact",
            impact=ImpactLevel.LOW,
        )
        high = CalendarEvent(
            event_date=date(2026, 1, 1),
            event_type=EventType.FED_MEETING,
            title="High Impact",
            impact=ImpactLevel.HIGH,
        )
        medium = CalendarEvent(
            event_date=date(2026, 1, 1),
            event_type=EventType.TAX_DATE,
            title="Medium Impact",
            impact=ImpactLevel.MEDIUM,
        )

        sorted_events = sorted([low, high, medium])

        assert sorted_events[0].title == "High Impact"
        assert sorted_events[1].title == "Medium Impact"
        assert sorted_events[2].title == "Low Impact"

    def test_event_is_frozen(self) -> None:
        """Test that events are immutable (frozen dataclass)."""
        event = CalendarEvent(
            event_date=date(2026, 1, 1),
            event_type=EventType.FED_MEETING,
            title="Test",
        )

        with pytest.raises(AttributeError):
            event.title = "Modified"  # type: ignore[misc]


class TestBaseCalendar:
    """Tests for BaseCalendar abstract class."""

    def test_get_events_not_implemented(self) -> None:
        """Test that get_events raises NotImplementedError."""
        calendar = BaseCalendar()

        with pytest.raises(NotImplementedError):
            calendar.get_events(date(2026, 1, 1), date(2026, 12, 31))

    def test_get_events_for_year(self) -> None:
        """Test get_events_for_year delegates correctly."""

        class TestCalendar(BaseCalendar):
            def get_events(
                self, start_date: date, end_date: date
            ) -> list[CalendarEvent]:
                return [
                    CalendarEvent(
                        event_date=date(2026, 6, 15),
                        event_type=EventType.TAX_DATE,
                        title="Test Event",
                    )
                ]

        calendar = TestCalendar()
        events = calendar.get_events_for_year(2026)

        assert len(events) == 1
        assert events[0].date == date(2026, 6, 15)

    def test_get_next_event(self) -> None:
        """Test get_next_event finds next event."""

        class TestCalendar(BaseCalendar):
            def get_events(
                self, start_date: date, end_date: date
            ) -> list[CalendarEvent]:
                events = [
                    CalendarEvent(
                        event_date=date(2026, 1, 15),
                        event_type=EventType.TAX_DATE,
                        title="Event 1",
                    ),
                    CalendarEvent(
                        event_date=date(2026, 6, 15),
                        event_type=EventType.FED_MEETING,
                        title="Event 2",
                    ),
                ]
                return [e for e in events if start_date <= e.date <= end_date]

        calendar = TestCalendar()
        next_event = calendar.get_next_event(from_date=date(2026, 1, 1))

        assert next_event is not None
        assert next_event.title == "Event 1"

    def test_get_next_event_with_type_filter(self) -> None:
        """Test get_next_event with event type filter."""

        class TestCalendar(BaseCalendar):
            def get_events(
                self, start_date: date, end_date: date
            ) -> list[CalendarEvent]:
                events = [
                    CalendarEvent(
                        event_date=date(2026, 1, 15),
                        event_type=EventType.TAX_DATE,
                        title="Tax Event",
                    ),
                    CalendarEvent(
                        event_date=date(2026, 6, 15),
                        event_type=EventType.FED_MEETING,
                        title="Fed Event",
                    ),
                ]
                return [e for e in events if start_date <= e.date <= end_date]

        calendar = TestCalendar()
        next_fed = calendar.get_next_event(
            from_date=date(2026, 1, 1),
            event_type=EventType.FED_MEETING,
        )

        assert next_fed is not None
        assert next_fed.title == "Fed Event"

    def test_get_next_event_returns_none_when_no_events(self) -> None:
        """Test get_next_event returns None when no matching events."""

        class EmptyCalendar(BaseCalendar):
            def get_events(
                self, start_date: date, end_date: date
            ) -> list[CalendarEvent]:
                return []

        calendar = EmptyCalendar()
        result = calendar.get_next_event(from_date=date(2026, 1, 1))

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
