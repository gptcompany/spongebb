"""Unit tests for US market holidays calendar.

Run with: uv run pytest tests/unit/test_calendar/test_holidays.py -v
"""

from datetime import date, timedelta

import pytest

from liquidity.calendar.base import EventType, ImpactLevel
from liquidity.calendar.holidays import (
    US_MARKET_HOLIDAYS_2026,
    USMarketHolidays,
)


class TestUSMarketHolidays2026Data:
    """Tests for static holiday data."""

    def test_holidays_exist(self) -> None:
        """Test that holiday data exists."""
        assert len(US_MARKET_HOLIDAYS_2026) > 0

    def test_major_holidays_included(self) -> None:
        """Test major US holidays are included."""
        holiday_names = set(US_MARKET_HOLIDAYS_2026.values())

        expected_holidays = {
            "New Year's Day",
            "Martin Luther King Jr. Day",
            "Presidents Day",
            "Good Friday",
            "Memorial Day",
            "Juneteenth",
            "Independence Day (Observed)",
            "Labor Day",
            "Thanksgiving Day",
            "Christmas Day",
        }

        assert expected_holidays.issubset(holiday_names)

    def test_all_holidays_in_2026(self) -> None:
        """Test all holiday dates are in 2026."""
        for holiday_date in US_MARKET_HOLIDAYS_2026:
            assert holiday_date.year == 2026


class TestUSMarketHolidays:
    """Tests for USMarketHolidays class."""

    @pytest.fixture
    def calendar(self) -> USMarketHolidays:
        """Create a US market holidays calendar fixture."""
        return USMarketHolidays(year=2026)

    def test_calendar_initializes(self, calendar: USMarketHolidays) -> None:
        """Test calendar initializes without error."""
        assert calendar is not None

    def test_get_events_returns_sorted_list(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test get_events returns chronologically sorted events."""
        events = calendar.get_events(date(2026, 1, 1), date(2026, 12, 31))

        assert len(events) > 0
        dates = [e.date for e in events]
        assert dates == sorted(dates)

    def test_get_events_respects_date_range(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test get_events only returns events within range."""
        start = date(2026, 1, 1)
        end = date(2026, 6, 30)
        events = calendar.get_events(start, end)

        for event in events:
            assert start <= event.date <= end

    def test_all_events_are_holiday_type(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test all events have HOLIDAY type."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            assert event.event_type == EventType.HOLIDAY

    def test_all_events_are_medium_impact(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test all holiday events are medium impact."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            assert event.impact == ImpactLevel.MEDIUM

    def test_is_market_holiday_true(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test is_market_holiday returns True for holidays."""
        # New Year's Day 2026
        assert calendar.is_market_holiday(date(2026, 1, 1)) is True
        # Christmas 2026
        assert calendar.is_market_holiday(date(2026, 12, 25)) is True

    def test_is_market_holiday_false(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test is_market_holiday returns False for non-holidays."""
        # Regular trading day
        assert calendar.is_market_holiday(date(2026, 1, 5)) is False

    def test_get_holiday_name_exists(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test get_holiday_name returns name for holidays."""
        name = calendar.get_holiday_name(date(2026, 1, 1))
        assert name is not None
        assert "New Year" in name

    def test_get_holiday_name_none(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test get_holiday_name returns None for non-holidays."""
        name = calendar.get_holiday_name(date(2026, 1, 5))
        assert name is None

    def test_is_trading_day_weekday_non_holiday(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test is_trading_day returns True for regular weekdays."""
        # Monday, Jan 5, 2026 is a regular trading day
        assert calendar.is_trading_day(date(2026, 1, 5)) is True

    def test_is_trading_day_weekend(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test is_trading_day returns False for weekends."""
        # Saturday, Jan 3, 2026
        assert calendar.is_trading_day(date(2026, 1, 3)) is False
        # Sunday, Jan 4, 2026
        assert calendar.is_trading_day(date(2026, 1, 4)) is False

    def test_is_trading_day_holiday(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test is_trading_day returns False for holidays."""
        # New Year's Day 2026 is Thursday
        assert calendar.is_trading_day(date(2026, 1, 1)) is False

    def test_count_trading_days_week(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test count_trading_days for a typical week."""
        # Jan 5-9, 2026 (Mon-Fri, no holidays)
        count = calendar.count_trading_days(date(2026, 1, 5), date(2026, 1, 9))
        assert count == 5

    def test_count_trading_days_with_weekend(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test count_trading_days excludes weekends."""
        # Jan 5-11, 2026 (Mon-Sun, 5 trading days)
        count = calendar.count_trading_days(date(2026, 1, 5), date(2026, 1, 11))
        assert count == 5

    def test_count_trading_days_with_holiday(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test count_trading_days excludes holidays."""
        # Dec 24-25, 2026 includes Christmas (Dec 25)
        # Dec 24 is Thursday, Dec 25 is Friday (Christmas)
        count = calendar.count_trading_days(date(2026, 12, 24), date(2026, 12, 25))
        assert count == 1  # Only Dec 24

    def test_events_have_metadata(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test holiday events include metadata."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            assert "holiday_name" in event.metadata
            assert "market" in event.metadata
            assert event.metadata["market"] == "NYSE"


class TestUSMarketHolidaysEdgeCases:
    """Edge case tests for US market holidays calendar."""

    @pytest.fixture
    def calendar(self) -> USMarketHolidays:
        """Create a US market holidays calendar fixture."""
        return USMarketHolidays(year=2026)

    def test_empty_date_range(self, calendar: USMarketHolidays) -> None:
        """Test empty date range returns empty list."""
        # Very narrow range with no holidays
        events = calendar.get_events(date(2026, 1, 5), date(2026, 1, 6))
        assert events == []

    def test_single_day_holiday(self, calendar: USMarketHolidays) -> None:
        """Test single day range on a holiday."""
        events = calendar.get_events(date(2026, 1, 1), date(2026, 1, 1))
        assert len(events) == 1
        assert events[0].date == date(2026, 1, 1)

    def test_get_next_trading_day_from_weekday(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test get_next_trading_day from a weekday."""
        # Monday Jan 5, 2026 is a trading day
        next_day = calendar.get_next_trading_day(date(2026, 1, 5))
        assert next_day == date(2026, 1, 5)

    def test_get_next_trading_day_from_weekend(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test get_next_trading_day from a weekend."""
        # Saturday Jan 3, 2026 -> Monday Jan 5
        next_day = calendar.get_next_trading_day(date(2026, 1, 3))
        assert next_day == date(2026, 1, 5)

    def test_get_next_trading_day_from_holiday(
        self, calendar: USMarketHolidays
    ) -> None:
        """Test get_next_trading_day from a holiday."""
        # New Year's Day Jan 1, 2026 (Thursday) -> Friday Jan 2
        next_day = calendar.get_next_trading_day(date(2026, 1, 1))
        assert next_day == date(2026, 1, 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
