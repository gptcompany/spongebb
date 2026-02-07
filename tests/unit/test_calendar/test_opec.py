"""Unit tests for OPEC meeting calendar.

Run with: uv run pytest tests/unit/test_calendar/test_opec.py -v
"""

from datetime import date, timedelta

import pytest

from liquidity.calendar.base import EventType, ImpactLevel
from liquidity.calendar.opec import (
    OPEC_MEETINGS_2026,
    OPECCalendar,
    OPECMeeting,
)


class TestOPECMeetingData:
    """Tests for static OPEC meeting data."""

    def test_opec_meetings_exist(self) -> None:
        """Test OPEC meetings data is not empty."""
        assert len(OPEC_MEETINGS_2026) > 0

    def test_opec_has_ministerial_meetings(self) -> None:
        """Test OPEC has at least 4 ministerial meetings per year."""
        ministerial = [m for m in OPEC_MEETINGS_2026 if m.meeting_type == "Ministerial"]
        assert len(ministerial) >= 4

    def test_opec_has_jmmc_meetings(self) -> None:
        """Test OPEC has JMMC meetings."""
        jmmc = [m for m in OPEC_MEETINGS_2026 if m.meeting_type == "JMMC"]
        assert len(jmmc) >= 6

    def test_all_meetings_in_2026(self) -> None:
        """Test all meeting dates are in 2026."""
        for meeting in OPEC_MEETINGS_2026:
            assert meeting.date.year == 2026

    def test_meeting_types_are_valid(self) -> None:
        """Test all meeting types are valid."""
        valid_types = {"JMMC", "Ministerial", "Extraordinary"}
        for meeting in OPEC_MEETINGS_2026:
            assert meeting.meeting_type in valid_types

    def test_meetings_have_descriptions(self) -> None:
        """Test all meetings have descriptions."""
        for meeting in OPEC_MEETINGS_2026:
            assert meeting.description
            assert len(meeting.description) > 10

    def test_meetings_are_sorted_chronologically(self) -> None:
        """Test meetings list is sorted by date."""
        dates = [m.date for m in OPEC_MEETINGS_2026]
        assert dates == sorted(dates)


class TestOPECMeetingDataclass:
    """Tests for OPECMeeting dataclass."""

    def test_create_basic_meeting(self) -> None:
        """Test creating a basic OPEC meeting."""
        meeting = OPECMeeting(
            date=date(2026, 6, 1),
            meeting_type="Ministerial",
            description="Test meeting",
        )

        assert meeting.date == date(2026, 6, 1)
        assert meeting.meeting_type == "Ministerial"
        assert meeting.description == "Test meeting"
        assert meeting.location is None
        assert meeting.is_confirmed is True

    def test_create_meeting_with_location(self) -> None:
        """Test creating a meeting with location."""
        meeting = OPECMeeting(
            date=date(2026, 6, 1),
            meeting_type="Extraordinary",
            description="Emergency meeting",
            location="Riyadh",
        )

        assert meeting.location == "Riyadh"

    def test_create_unconfirmed_meeting(self) -> None:
        """Test creating an unconfirmed meeting."""
        meeting = OPECMeeting(
            date=date(2026, 6, 1),
            meeting_type="JMMC",
            description="Tentative meeting",
            is_confirmed=False,
        )

        assert meeting.is_confirmed is False

    def test_meeting_is_frozen(self) -> None:
        """Test OPECMeeting is immutable (frozen dataclass)."""
        meeting = OPECMeeting(
            date=date(2026, 6, 1),
            meeting_type="JMMC",
            description="Test",
        )

        with pytest.raises(AttributeError):
            meeting.date = date(2026, 7, 1)  # type: ignore


class TestOPECCalendar:
    """Tests for OPECCalendar class."""

    @pytest.fixture
    def calendar(self) -> OPECCalendar:
        """Create an OPEC calendar fixture."""
        return OPECCalendar()

    def test_calendar_initializes(self, calendar: OPECCalendar) -> None:
        """Test calendar initializes without error."""
        assert calendar is not None

    def test_get_events_returns_sorted_list(self, calendar: OPECCalendar) -> None:
        """Test get_events returns chronologically sorted events."""
        events = calendar.get_events(date(2026, 1, 1), date(2026, 12, 31))

        assert len(events) > 0
        dates = [e.date for e in events]
        assert dates == sorted(dates)

    def test_get_events_respects_date_range(self, calendar: OPECCalendar) -> None:
        """Test get_events only returns events within range."""
        start = date(2026, 3, 1)
        end = date(2026, 6, 30)
        events = calendar.get_events(start, end)

        for event in events:
            assert start <= event.date <= end

    def test_event_types_are_opec_meeting(self, calendar: OPECCalendar) -> None:
        """Test all events have OPEC_MEETING type."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            assert event.event_type == EventType.OPEC_MEETING

    def test_ministerial_meetings_are_high_impact(
        self, calendar: OPECCalendar
    ) -> None:
        """Test Ministerial meetings are high impact."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            if event.metadata.get("meeting_type") == "Ministerial":
                assert event.impact == ImpactLevel.HIGH

    def test_jmmc_meetings_are_medium_impact(self, calendar: OPECCalendar) -> None:
        """Test JMMC meetings are medium impact."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            if event.metadata.get("meeting_type") == "JMMC":
                assert event.impact == ImpactLevel.MEDIUM

    def test_events_have_metadata(self, calendar: OPECCalendar) -> None:
        """Test events include meeting metadata."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            assert "meeting_type" in event.metadata
            assert "location" in event.metadata
            assert "is_confirmed" in event.metadata


class TestOPECCalendarMeetingMethods:
    """Tests for OPECCalendar meeting-specific methods."""

    @pytest.fixture
    def calendar(self) -> OPECCalendar:
        """Create an OPEC calendar fixture."""
        return OPECCalendar()

    def test_get_next_meeting_returns_meeting(self, calendar: OPECCalendar) -> None:
        """Test get_next_meeting returns an OPECMeeting."""
        # Use a date we know is before meetings
        next_meeting = calendar.get_next_meeting(from_date=date(2026, 1, 1))

        assert next_meeting is not None
        assert isinstance(next_meeting, OPECMeeting)
        assert next_meeting.date >= date(2026, 1, 1)

    def test_get_next_meeting_respects_from_date(
        self, calendar: OPECCalendar
    ) -> None:
        """Test get_next_meeting finds meeting after from_date."""
        from_date = date(2026, 4, 1)
        next_meeting = calendar.get_next_meeting(from_date=from_date)

        assert next_meeting is not None
        assert next_meeting.date >= from_date

    def test_get_next_meeting_returns_none_after_all_meetings(
        self, calendar: OPECCalendar
    ) -> None:
        """Test get_next_meeting returns None if no meetings left."""
        # Use a date after all meetings
        next_meeting = calendar.get_next_meeting(from_date=date(2027, 1, 1))

        assert next_meeting is None

    def test_get_meetings_in_range(self, calendar: OPECCalendar) -> None:
        """Test get_meetings_in_range returns OPECMeeting objects."""
        meetings = calendar.get_meetings_in_range(
            date(2026, 1, 1), date(2026, 6, 30)
        )

        assert len(meetings) > 0
        for meeting in meetings:
            assert isinstance(meeting, OPECMeeting)
            assert date(2026, 1, 1) <= meeting.date <= date(2026, 6, 30)

    def test_is_meeting_soon_true(self, calendar: OPECCalendar) -> None:
        """Test is_meeting_soon returns True when meeting is within days."""
        # Find a meeting and check a few days before
        first_meeting = OPEC_MEETINGS_2026[0]
        check_date = first_meeting.date - timedelta(days=3)

        result = calendar.is_meeting_soon(days=7, from_date=check_date)
        assert result is True

    def test_is_meeting_soon_false(self, calendar: OPECCalendar) -> None:
        """Test is_meeting_soon returns False when no meeting within days."""
        # Use a date well before any meeting
        result = calendar.is_meeting_soon(days=3, from_date=date(2026, 1, 1))

        # Jan 15 is first meeting, so Jan 1 with 3 days should be False
        assert result is False

    def test_is_meeting_soon_default_days(self, calendar: OPECCalendar) -> None:
        """Test is_meeting_soon uses default 7 days."""
        first_meeting = OPEC_MEETINGS_2026[0]
        check_date = first_meeting.date - timedelta(days=6)

        result = calendar.is_meeting_soon(from_date=check_date)
        assert result is True

    def test_get_ministerial_meetings(self, calendar: OPECCalendar) -> None:
        """Test get_ministerial_meetings returns only ministerial."""
        meetings = calendar.get_ministerial_meetings(
            date(2026, 1, 1), date(2026, 12, 31)
        )

        assert len(meetings) >= 4
        for meeting in meetings:
            assert meeting.meeting_type == "Ministerial"

    def test_get_jmmc_meetings(self, calendar: OPECCalendar) -> None:
        """Test get_jmmc_meetings returns only JMMC."""
        meetings = calendar.get_jmmc_meetings(date(2026, 1, 1), date(2026, 12, 31))

        assert len(meetings) >= 6
        for meeting in meetings:
            assert meeting.meeting_type == "JMMC"

    def test_days_until_next_meeting(self, calendar: OPECCalendar) -> None:
        """Test days_until_next_meeting returns correct days."""
        first_meeting = OPEC_MEETINGS_2026[0]
        from_date = first_meeting.date - timedelta(days=5)

        days = calendar.days_until_next_meeting(from_date=from_date)
        assert days == 5

    def test_days_until_next_meeting_none(self, calendar: OPECCalendar) -> None:
        """Test days_until_next_meeting returns None if no meetings."""
        days = calendar.days_until_next_meeting(from_date=date(2027, 1, 1))
        assert days is None


class TestOPECCalendarCustomMeetings:
    """Tests for OPECCalendar with custom meeting data."""

    def test_calendar_with_custom_meetings(self) -> None:
        """Test calendar accepts custom meetings list."""
        custom_meetings = [
            OPECMeeting(
                date=date(2026, 5, 1),
                meeting_type="Extraordinary",
                description="Emergency session",
                location="Riyadh",
            ),
            OPECMeeting(
                date=date(2026, 6, 1),
                meeting_type="Ministerial",
                description="Regular meeting",
            ),
        ]

        calendar = OPECCalendar(meetings=custom_meetings)
        events = calendar.get_events_for_year(2026)

        assert len(events) == 2

    def test_extraordinary_meetings_are_high_impact(self) -> None:
        """Test Extraordinary meetings are high impact."""
        custom_meetings = [
            OPECMeeting(
                date=date(2026, 5, 1),
                meeting_type="Extraordinary",
                description="Emergency production cut",
            ),
        ]

        calendar = OPECCalendar(meetings=custom_meetings)
        events = calendar.get_events_for_year(2026)

        assert events[0].impact == ImpactLevel.HIGH


class TestOPECCalendarEdgeCases:
    """Edge case tests for OPEC calendar."""

    @pytest.fixture
    def calendar(self) -> OPECCalendar:
        """Create an OPEC calendar fixture."""
        return OPECCalendar()

    def test_empty_date_range(self, calendar: OPECCalendar) -> None:
        """Test empty date range returns empty list."""
        events = calendar.get_events(date(2025, 1, 1), date(2025, 1, 2))
        assert events == []

    def test_single_day_range(self, calendar: OPECCalendar) -> None:
        """Test single day range returns meeting if exists."""
        first_meeting = OPEC_MEETINGS_2026[0]
        events = calendar.get_events(first_meeting.date, first_meeting.date)

        assert len(events) == 1
        assert events[0].date == first_meeting.date

    def test_get_next_meeting_from_meeting_day(self, calendar: OPECCalendar) -> None:
        """Test get_next_meeting from the day of a meeting."""
        first_meeting = OPEC_MEETINGS_2026[0]
        next_meeting = calendar.get_next_meeting(from_date=first_meeting.date)

        # Should return the meeting on that day (>= comparison)
        assert next_meeting is not None
        assert next_meeting.date == first_meeting.date

    def test_empty_meetings_list(self) -> None:
        """Test calendar with empty meetings list."""
        calendar = OPECCalendar(meetings=[])

        events = calendar.get_events_for_year(2026)
        assert events == []

        next_meeting = calendar.get_next_meeting()
        assert next_meeting is None

        is_soon = calendar.is_meeting_soon()
        assert is_soon is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
