"""Unit tests for calendar registry.

Run with: uv run pytest tests/unit/test_calendar/test_registry.py -v
"""

from datetime import date

import pytest

from liquidity.calendar.base import (
    BaseCalendar,
    CalendarEvent,
    EventType,
    ImpactLevel,
)
from liquidity.calendar.central_banks import CBMeetingCalendar
from liquidity.calendar.holidays import USMarketHolidays
from liquidity.calendar.registry import CalendarRegistry, calendar_registry
from liquidity.calendar.tax_dates import TaxDateCalendar
from liquidity.calendar.treasury import TreasuryAuctionCalendar


class TestCalendarRegistry:
    """Tests for CalendarRegistry class."""

    @pytest.fixture
    def registry(self) -> CalendarRegistry:
        """Create a fresh registry fixture."""
        return CalendarRegistry(year=2026)

    def test_registry_initializes(self, registry: CalendarRegistry) -> None:
        """Test registry initializes with default calendars."""
        assert registry is not None
        assert len(registry) == 4  # treasury, central_banks, tax_dates, holidays

    def test_list_calendars(self, registry: CalendarRegistry) -> None:
        """Test list_calendars returns all registered calendars."""
        calendars = registry.list_calendars()

        assert "treasury" in calendars
        assert "central_banks" in calendars
        assert "tax_dates" in calendars
        assert "holidays" in calendars

    def test_get_calendar_treasury(self, registry: CalendarRegistry) -> None:
        """Test get_calendar returns Treasury calendar."""
        calendar = registry.get_calendar("treasury")
        assert isinstance(calendar, TreasuryAuctionCalendar)

    def test_get_calendar_central_banks(self, registry: CalendarRegistry) -> None:
        """Test get_calendar returns CB meeting calendar."""
        calendar = registry.get_calendar("central_banks")
        assert isinstance(calendar, CBMeetingCalendar)

    def test_get_calendar_tax_dates(self, registry: CalendarRegistry) -> None:
        """Test get_calendar returns tax date calendar."""
        calendar = registry.get_calendar("tax_dates")
        assert isinstance(calendar, TaxDateCalendar)

    def test_get_calendar_holidays(self, registry: CalendarRegistry) -> None:
        """Test get_calendar returns holidays calendar."""
        calendar = registry.get_calendar("holidays")
        assert isinstance(calendar, USMarketHolidays)

    def test_get_calendar_not_found(self, registry: CalendarRegistry) -> None:
        """Test get_calendar raises error for unknown calendar."""
        with pytest.raises(KeyError, match="not found"):
            registry.get_calendar("unknown")

    def test_register_custom_calendar(self, registry: CalendarRegistry) -> None:
        """Test registering a custom calendar."""

        class CustomCalendar(BaseCalendar):
            def get_events(
                self, start_date: date, end_date: date
            ) -> list[CalendarEvent]:
                return []

        custom = CustomCalendar()
        registry.register("custom", custom)

        assert "custom" in registry
        assert registry.get_calendar("custom") is custom

    def test_register_duplicate_raises_error(self, registry: CalendarRegistry) -> None:
        """Test registering duplicate name raises error."""
        class CustomCalendar(BaseCalendar):
            def get_events(
                self, start_date: date, end_date: date
            ) -> list[CalendarEvent]:
                return []

        with pytest.raises(ValueError, match="already registered"):
            registry.register("treasury", CustomCalendar())

    def test_register_duplicate_with_force(self, registry: CalendarRegistry) -> None:
        """Test registering duplicate with force=True succeeds."""
        class CustomCalendar(BaseCalendar):
            def get_events(
                self, start_date: date, end_date: date
            ) -> list[CalendarEvent]:
                return []

        custom = CustomCalendar()
        registry.register("treasury", custom, force=True)

        assert registry.get_calendar("treasury") is custom

    def test_unregister_calendar(self, registry: CalendarRegistry) -> None:
        """Test unregistering a calendar."""
        registry.unregister("treasury")
        assert "treasury" not in registry

    def test_unregister_not_found_raises_error(
        self, registry: CalendarRegistry
    ) -> None:
        """Test unregistering unknown calendar raises error."""
        with pytest.raises(KeyError, match="not registered"):
            registry.unregister("unknown")


class TestCalendarRegistryGetEvents:
    """Tests for CalendarRegistry.get_events method."""

    @pytest.fixture
    def registry(self) -> CalendarRegistry:
        """Create a fresh registry fixture."""
        return CalendarRegistry(year=2026)

    def test_get_events_returns_sorted_list(
        self, registry: CalendarRegistry
    ) -> None:
        """Test get_events returns chronologically sorted events."""
        events = registry.get_events(date(2026, 1, 1), date(2026, 3, 31))

        assert len(events) > 0
        dates = [e.date for e in events]
        assert dates == sorted(dates)

    def test_get_events_includes_all_types(
        self, registry: CalendarRegistry
    ) -> None:
        """Test get_events includes events from all calendars."""
        events = registry.get_events(date(2026, 1, 1), date(2026, 12, 31))

        event_types = {e.event_type for e in events}

        # Should have events from all calendars
        assert EventType.TREASURY_AUCTION in event_types
        assert EventType.FED_MEETING in event_types
        assert EventType.TAX_DATE in event_types
        assert EventType.HOLIDAY in event_types

    def test_get_events_respects_date_range(
        self, registry: CalendarRegistry
    ) -> None:
        """Test get_events only returns events within range."""
        start = date(2026, 1, 1)
        end = date(2026, 1, 31)
        events = registry.get_events(start, end)

        for event in events:
            assert start <= event.date <= end

    def test_get_events_filter_by_calendars(
        self, registry: CalendarRegistry
    ) -> None:
        """Test get_events with calendar filter."""
        events = registry.get_events(
            date(2026, 1, 1),
            date(2026, 12, 31),
            calendars=["treasury"],
        )

        for event in events:
            assert event.event_type == EventType.TREASURY_AUCTION

    def test_get_events_multiple_calendar_filter(
        self, registry: CalendarRegistry
    ) -> None:
        """Test get_events with multiple calendar filters."""
        events = registry.get_events(
            date(2026, 1, 1),
            date(2026, 12, 31),
            calendars=["treasury", "central_banks"],
        )

        valid_types = {
            EventType.TREASURY_AUCTION,
            EventType.FED_MEETING,
            EventType.ECB_MEETING,
            EventType.BOJ_MEETING,
            EventType.BOE_MEETING,
        }

        for event in events:
            assert event.event_type in valid_types


class TestCalendarRegistryHighImpact:
    """Tests for high-impact event filtering."""

    @pytest.fixture
    def registry(self) -> CalendarRegistry:
        """Create a fresh registry fixture."""
        return CalendarRegistry(year=2026)

    def test_get_high_impact_events(
        self, registry: CalendarRegistry
    ) -> None:
        """Test get_high_impact_events returns only high impact."""
        events = registry.get_high_impact_events(
            date(2026, 1, 1), date(2026, 12, 31)
        )

        assert len(events) > 0
        for event in events:
            assert event.impact == ImpactLevel.HIGH

    def test_get_next_high_impact_event(
        self, registry: CalendarRegistry
    ) -> None:
        """Test get_next_high_impact_event returns next event."""
        event = registry.get_next_high_impact_event(from_date=date(2026, 1, 1))

        assert event is not None
        assert event.impact == ImpactLevel.HIGH
        assert event.date >= date(2026, 1, 1)

    def test_get_next_high_impact_event_none(
        self, registry: CalendarRegistry
    ) -> None:
        """Test get_next_high_impact_event returns None when no events."""
        # Far future date with no data
        event = registry.get_next_high_impact_event(from_date=date(2030, 1, 1))
        assert event is None


class TestCalendarRegistryFiltering:
    """Tests for event filtering methods."""

    @pytest.fixture
    def registry(self) -> CalendarRegistry:
        """Create a fresh registry fixture."""
        return CalendarRegistry(year=2026)

    def test_filter_by_type(self, registry: CalendarRegistry) -> None:
        """Test filter_by_type returns only matching types."""
        all_events = registry.get_events(date(2026, 1, 1), date(2026, 12, 31))
        filtered = registry.filter_by_type(all_events, [EventType.FED_MEETING])

        for event in filtered:
            assert event.event_type == EventType.FED_MEETING

    def test_filter_by_type_multiple(self, registry: CalendarRegistry) -> None:
        """Test filter_by_type with multiple types."""
        all_events = registry.get_events(date(2026, 1, 1), date(2026, 12, 31))
        filtered = registry.filter_by_type(
            all_events,
            [EventType.FED_MEETING, EventType.ECB_MEETING],
        )

        for event in filtered:
            assert event.event_type in (EventType.FED_MEETING, EventType.ECB_MEETING)

    def test_filter_by_impact(self, registry: CalendarRegistry) -> None:
        """Test filter_by_impact returns only matching levels."""
        all_events = registry.get_events(date(2026, 1, 1), date(2026, 12, 31))
        filtered = registry.filter_by_impact(all_events, [ImpactLevel.HIGH])

        for event in filtered:
            assert event.impact == ImpactLevel.HIGH

    def test_filter_by_impact_multiple(
        self, registry: CalendarRegistry
    ) -> None:
        """Test filter_by_impact with multiple levels."""
        all_events = registry.get_events(date(2026, 1, 1), date(2026, 12, 31))
        filtered = registry.filter_by_impact(
            all_events,
            [ImpactLevel.HIGH, ImpactLevel.MEDIUM],
        )

        for event in filtered:
            assert event.impact in (ImpactLevel.HIGH, ImpactLevel.MEDIUM)


class TestCalendarRegistryConvenienceMethods:
    """Tests for convenience methods."""

    @pytest.fixture
    def registry(self) -> CalendarRegistry:
        """Create a fresh registry fixture."""
        return CalendarRegistry(year=2026)

    def test_get_events_for_date(self, registry: CalendarRegistry) -> None:
        """Test get_events_for_date returns all events on a date."""
        # Pick a date with known events (FOMC decision Jan 28)
        events = registry.get_events_for_date(date(2026, 1, 28))

        for event in events:
            assert event.date == date(2026, 1, 28)

    def test_is_fed_blackout(self, registry: CalendarRegistry) -> None:
        """Test is_fed_blackout delegates correctly."""
        # During FOMC blackout
        assert registry.is_fed_blackout(date(2026, 1, 20)) is True
        # Not during blackout
        assert registry.is_fed_blackout(date(2026, 1, 5)) is False

    def test_is_market_holiday(self, registry: CalendarRegistry) -> None:
        """Test is_market_holiday delegates correctly."""
        # New Year's Day
        assert registry.is_market_holiday(date(2026, 1, 1)) is True
        # Regular trading day
        assert registry.is_market_holiday(date(2026, 1, 5)) is False

    def test_get_daily_summary(self, registry: CalendarRegistry) -> None:
        """Test get_daily_summary returns correct structure."""
        summary = registry.get_daily_summary(date(2026, 1, 28))

        assert "date" in summary
        assert "total_events" in summary
        assert "high_impact_count" in summary
        assert "event_titles" in summary
        assert "high_impact_titles" in summary
        assert "is_fed_blackout" in summary
        assert "is_market_holiday" in summary


class TestGlobalCalendarRegistry:
    """Tests for global singleton registry."""

    def test_global_registry_exists(self) -> None:
        """Test global calendar_registry exists."""
        assert calendar_registry is not None

    def test_global_registry_has_default_calendars(self) -> None:
        """Test global registry has default calendars."""
        assert "treasury" in calendar_registry
        assert "central_banks" in calendar_registry
        assert "tax_dates" in calendar_registry
        assert "holidays" in calendar_registry

    def test_global_registry_repr(self) -> None:
        """Test global registry has useful repr."""
        repr_str = repr(calendar_registry)
        assert "CalendarRegistry" in repr_str
        assert "treasury" in repr_str


class TestCalendarRegistryContains:
    """Tests for __contains__ method."""

    @pytest.fixture
    def registry(self) -> CalendarRegistry:
        """Create a fresh registry fixture."""
        return CalendarRegistry(year=2026)

    def test_contains_true(self, registry: CalendarRegistry) -> None:
        """Test __contains__ returns True for registered calendars."""
        assert "treasury" in registry
        assert "central_banks" in registry

    def test_contains_false(self, registry: CalendarRegistry) -> None:
        """Test __contains__ returns False for unknown calendars."""
        assert "unknown" not in registry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
