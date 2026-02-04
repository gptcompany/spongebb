"""Unit tests for central bank meeting calendar.

Run with: uv run pytest tests/unit/test_calendar/test_central_banks.py -v
"""

from datetime import date

import pytest

from liquidity.calendar.base import EventType, ImpactLevel
from liquidity.calendar.central_banks import (
    BOE_MEETINGS_2026,
    BOJ_MEETINGS_2026,
    ECB_MEETINGS_2026,
    FOMC_MEETINGS_2026,
    CBMeetingCalendar,
)


class TestCentralBankMeetingData:
    """Tests for static central bank meeting data."""

    def test_fomc_meetings_count(self) -> None:
        """Test FOMC has 8 meetings per year."""
        assert len(FOMC_MEETINGS_2026) == 8

    def test_fomc_meetings_are_two_day(self) -> None:
        """Test FOMC meetings are 2-day meetings."""
        for day1, day2 in FOMC_MEETINGS_2026:
            days_diff = (day2 - day1).days
            assert days_diff == 1, f"FOMC meeting should be 2 consecutive days: {day1} - {day2}"

    def test_ecb_meetings_count(self) -> None:
        """Test ECB has at least 6 monetary policy meetings."""
        assert len(ECB_MEETINGS_2026) >= 6

    def test_boj_meetings_count(self) -> None:
        """Test BoJ has 8 meetings per year."""
        assert len(BOJ_MEETINGS_2026) == 8

    def test_boj_meetings_are_two_day(self) -> None:
        """Test BoJ meetings are 2-day meetings."""
        for day1, day2 in BOJ_MEETINGS_2026:
            days_diff = (day2 - day1).days
            assert days_diff == 1, f"BoJ meeting should be 2 consecutive days: {day1} - {day2}"

    def test_boe_meetings_count(self) -> None:
        """Test BoE has 8 meetings per year."""
        assert len(BOE_MEETINGS_2026) == 8

    def test_all_meetings_in_2026(self) -> None:
        """Test all meeting dates are in 2026."""
        for day1, day2 in FOMC_MEETINGS_2026:
            assert day1.year == 2026
            assert day2.year == 2026

        for d in ECB_MEETINGS_2026:
            assert d.year == 2026

        for day1, day2 in BOJ_MEETINGS_2026:
            assert day1.year == 2026
            assert day2.year == 2026

        for d in BOE_MEETINGS_2026:
            assert d.year == 2026


class TestCBMeetingCalendar:
    """Tests for CBMeetingCalendar class."""

    @pytest.fixture
    def calendar(self) -> CBMeetingCalendar:
        """Create a CB meeting calendar fixture."""
        return CBMeetingCalendar()

    def test_calendar_initializes(self, calendar: CBMeetingCalendar) -> None:
        """Test calendar initializes without error."""
        assert calendar is not None

    def test_get_events_returns_sorted_list(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test get_events returns chronologically sorted events."""
        events = calendar.get_events(date(2026, 1, 1), date(2026, 6, 30))

        assert len(events) > 0
        dates = [e.date for e in events]
        assert dates == sorted(dates)

    def test_get_events_respects_date_range(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test get_events only returns events within range."""
        start = date(2026, 1, 1)
        end = date(2026, 3, 31)
        events = calendar.get_events(start, end)

        for event in events:
            assert start <= event.date <= end

    def test_all_events_are_high_impact(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test all CB meetings are high impact."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            assert event.impact == ImpactLevel.HIGH

    def test_event_types_are_correct(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test events have correct CB meeting types."""
        events = calendar.get_events_for_year(2026)

        valid_types = {
            EventType.FED_MEETING,
            EventType.ECB_MEETING,
            EventType.BOJ_MEETING,
            EventType.BOE_MEETING,
        }

        for event in events:
            assert event.event_type in valid_types

    def test_get_fed_meetings(self, calendar: CBMeetingCalendar) -> None:
        """Test get_fed_meetings returns only FOMC events."""
        events = calendar.get_fed_meetings(date(2026, 1, 1), date(2026, 12, 31))

        assert len(events) == 8  # 8 FOMC meetings per year
        for event in events:
            assert event.event_type == EventType.FED_MEETING

    def test_is_fed_blackout_during_blackout(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test is_fed_blackout returns True during blackout period."""
        # First FOMC decision is Jan 28, 2026
        # Blackout starts 10 days before = Jan 18
        blackout_date = date(2026, 1, 20)  # During blackout
        decision_date = date(2026, 1, 28)  # Decision day

        assert calendar.is_fed_blackout(blackout_date) is True
        assert calendar.is_fed_blackout(decision_date) is True

    def test_is_fed_blackout_outside_blackout(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test is_fed_blackout returns False outside blackout period."""
        # Well before any FOMC meeting
        non_blackout_date = date(2026, 1, 1)

        assert calendar.is_fed_blackout(non_blackout_date) is False

    def test_get_fed_blackout_periods(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test get_fed_blackout_periods returns correct periods."""
        periods = calendar.get_fed_blackout_periods(
            date(2026, 1, 1), date(2026, 3, 31)
        )

        # Should have 2 blackout periods in Q1 (Jan and March FOMC)
        assert len(periods) == 2

        for start, end in periods:
            # End should be a decision day
            days_diff = (end - start).days
            assert days_diff == 10  # 10-day blackout

    def test_get_events_by_bank_fed(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test get_events_by_bank for Fed."""
        events = calendar.get_events_by_bank(
            date(2026, 1, 1), date(2026, 12, 31), "fed"
        )

        assert len(events) == 8
        for event in events:
            assert event.event_type == EventType.FED_MEETING

    def test_get_events_by_bank_ecb(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test get_events_by_bank for ECB."""
        events = calendar.get_events_by_bank(
            date(2026, 1, 1), date(2026, 12, 31), "ecb"
        )

        assert len(events) >= 6
        for event in events:
            assert event.event_type == EventType.ECB_MEETING

    def test_get_events_by_bank_boj(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test get_events_by_bank for BoJ."""
        events = calendar.get_events_by_bank(
            date(2026, 1, 1), date(2026, 12, 31), "boj"
        )

        assert len(events) == 8
        for event in events:
            assert event.event_type == EventType.BOJ_MEETING

    def test_get_events_by_bank_boe(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test get_events_by_bank for BoE."""
        events = calendar.get_events_by_bank(
            date(2026, 1, 1), date(2026, 12, 31), "boe"
        )

        assert len(events) == 8
        for event in events:
            assert event.event_type == EventType.BOE_MEETING

    def test_get_events_by_bank_invalid(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test get_events_by_bank raises error for invalid bank."""
        with pytest.raises(ValueError, match="Unknown bank"):
            calendar.get_events_by_bank(
                date(2026, 1, 1), date(2026, 12, 31), "invalid"
            )

    def test_get_events_by_bank_case_insensitive(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test get_events_by_bank is case insensitive."""
        events_lower = calendar.get_events_by_bank(
            date(2026, 1, 1), date(2026, 12, 31), "fed"
        )
        events_upper = calendar.get_events_by_bank(
            date(2026, 1, 1), date(2026, 12, 31), "FED"
        )
        events_mixed = calendar.get_events_by_bank(
            date(2026, 1, 1), date(2026, 12, 31), "Fed"
        )

        assert len(events_lower) == len(events_upper) == len(events_mixed)

    def test_fomc_events_have_meeting_dates_metadata(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test FOMC events include meeting start/end dates in metadata."""
        events = calendar.get_fed_meetings(date(2026, 1, 1), date(2026, 12, 31))

        for event in events:
            assert "meeting_start" in event.metadata
            assert "meeting_end" in event.metadata
            assert "central_bank" in event.metadata
            assert event.metadata["central_bank"] == "Federal Reserve"


class TestCBMeetingCalendarEdgeCases:
    """Edge case tests for CB meeting calendar."""

    @pytest.fixture
    def calendar(self) -> CBMeetingCalendar:
        """Create a CB meeting calendar fixture."""
        return CBMeetingCalendar()

    def test_empty_date_range(self, calendar: CBMeetingCalendar) -> None:
        """Test empty date range returns empty list."""
        events = calendar.get_events(date(2025, 1, 1), date(2025, 1, 2))
        assert events == []

    def test_single_day_with_multiple_banks(
        self, calendar: CBMeetingCalendar
    ) -> None:
        """Test days with multiple CB meetings return all."""
        # Find a day with multiple meetings (if any overlap)
        events = calendar.get_events_for_year(2026)

        # Group by date
        dates_with_events: dict[date, int] = {}
        for event in events:
            dates_with_events[event.date] = dates_with_events.get(event.date, 0) + 1

        # Check that we handle multiple events per date correctly
        for d, count in dates_with_events.items():
            day_events = calendar.get_events(d, d)
            assert len(day_events) == count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
