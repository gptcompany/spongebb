"""Calendar registry for unified access to all calendars.

Provides a single interface to query events across all calendar types:
- Treasury auctions
- Central bank meetings
- Tax payment dates
- Market holidays
"""

import logging
from collections.abc import Sequence
from datetime import date

from liquidity.calendar.base import BaseCalendar, CalendarEvent, EventType, ImpactLevel
from liquidity.calendar.central_banks import CBMeetingCalendar
from liquidity.calendar.holidays import USMarketHolidays
from liquidity.calendar.tax_dates import TaxDateCalendar
from liquidity.calendar.treasury import TreasuryAuctionCalendar

logger = logging.getLogger(__name__)


class CalendarRegistry:
    """Unified registry for all liquidity-related calendars.

    Aggregates events from Treasury auctions, CB meetings, tax dates,
    and market holidays into a single queryable interface.

    Example:
        >>> registry = CalendarRegistry()
        >>> events = registry.get_events(date(2026, 1, 1), date(2026, 1, 31))
        >>> high_impact = registry.get_high_impact_events(date(2026, 1, 1), date(2026, 3, 31))
        >>> fed_events = registry.filter_by_type(events, [EventType.FED_MEETING])
    """

    def __init__(self, year: int = 2026) -> None:
        """Initialize the calendar registry with all calendars.

        Args:
            year: Year for calendar data (default 2026).
        """
        self._year = year
        self._calendars: dict[str, BaseCalendar] = {
            "treasury": TreasuryAuctionCalendar(),
            "central_banks": CBMeetingCalendar(),
            "tax_dates": TaxDateCalendar(year=year),
            "holidays": USMarketHolidays(year=year),
        }
        logger.debug("Initialized CalendarRegistry for year %d", year)

    def register(
        self,
        name: str,
        calendar: BaseCalendar,
        *,
        force: bool = False,
    ) -> None:
        """Register a custom calendar.

        Args:
            name: Unique name for the calendar.
            calendar: Calendar instance to register.
            force: If True, overwrite existing registration.

        Raises:
            ValueError: If name already exists and force is False.
        """
        if name in self._calendars and not force:
            raise ValueError(f"Calendar '{name}' already registered. Use force=True to overwrite.")
        self._calendars[name] = calendar
        logger.debug("Registered calendar: %s", name)

    def unregister(self, name: str) -> None:
        """Unregister a calendar.

        Args:
            name: Name of calendar to unregister.

        Raises:
            KeyError: If calendar is not registered.
        """
        if name not in self._calendars:
            raise KeyError(f"Calendar '{name}' is not registered")
        del self._calendars[name]
        logger.debug("Unregistered calendar: %s", name)

    def get_calendar(self, name: str) -> BaseCalendar:
        """Get a specific calendar by name.

        Args:
            name: Name of the calendar.

        Returns:
            The calendar instance.

        Raises:
            KeyError: If calendar is not registered.
        """
        if name not in self._calendars:
            available = ", ".join(self._calendars.keys())
            raise KeyError(f"Calendar '{name}' not found. Available: {available}")
        return self._calendars[name]

    def list_calendars(self) -> list[str]:
        """List all registered calendar names.

        Returns:
            Sorted list of calendar names.
        """
        return sorted(self._calendars.keys())

    def get_events(
        self,
        start_date: date,
        end_date: date,
        *,
        calendars: Sequence[str] | None = None,
    ) -> list[CalendarEvent]:
        """Get all events from all calendars within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).
            calendars: Optional list of calendar names to query.
                       If None, queries all calendars.

        Returns:
            Sorted list of CalendarEvent objects from all calendars.
        """
        all_events: list[CalendarEvent] = []

        calendars_to_query = calendars or self._calendars.keys()

        for name in calendars_to_query:
            if name not in self._calendars:
                logger.warning("Calendar '%s' not found, skipping", name)
                continue
            calendar = self._calendars[name]
            events = calendar.get_events(start_date, end_date)
            all_events.extend(events)

        return sorted(all_events)

    def get_high_impact_events(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get only high-impact events within a date range.

        High-impact events include:
        - 10Y/30Y Treasury auctions
        - Central bank meeting decisions
        - Major tax payment dates
        - Quarter-end dates

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            Sorted list of high-impact events.
        """
        all_events = self.get_events(start_date, end_date)
        return [e for e in all_events if e.impact == ImpactLevel.HIGH]

    def filter_by_type(
        self,
        events: list[CalendarEvent],
        event_types: Sequence[EventType],
    ) -> list[CalendarEvent]:
        """Filter events by type.

        Args:
            events: List of events to filter.
            event_types: Event types to include.

        Returns:
            Filtered list of events.
        """
        return [e for e in events if e.event_type in event_types]

    def filter_by_impact(
        self,
        events: list[CalendarEvent],
        impact_levels: Sequence[ImpactLevel],
    ) -> list[CalendarEvent]:
        """Filter events by impact level.

        Args:
            events: List of events to filter.
            impact_levels: Impact levels to include.

        Returns:
            Filtered list of events.
        """
        return [e for e in events if e.impact in impact_levels]

    def get_events_for_date(self, check_date: date) -> list[CalendarEvent]:
        """Get all events for a specific date.

        Args:
            check_date: Date to get events for.

        Returns:
            List of events on that date.
        """
        return self.get_events(check_date, check_date)

    def get_next_high_impact_event(
        self,
        from_date: date | None = None,
    ) -> CalendarEvent | None:
        """Get the next high-impact event.

        Args:
            from_date: Date to search from (defaults to today).

        Returns:
            The next high-impact event or None.
        """
        from_date = from_date or date.today()
        # Search up to 1 year ahead
        end_date = date(from_date.year + 1, from_date.month, from_date.day)
        events = self.get_high_impact_events(from_date, end_date)
        return events[0] if events else None

    def is_fed_blackout(self, check_date: date) -> bool:
        """Check if a date is in Fed blackout period.

        Convenience method that delegates to CBMeetingCalendar.

        Args:
            check_date: Date to check.

        Returns:
            True if in Fed blackout period.
        """
        cb_calendar = self._calendars.get("central_banks")
        if isinstance(cb_calendar, CBMeetingCalendar):
            return cb_calendar.is_fed_blackout(check_date)
        return False

    def is_market_holiday(self, check_date: date) -> bool:
        """Check if a date is a market holiday.

        Convenience method that delegates to USMarketHolidays.

        Args:
            check_date: Date to check.

        Returns:
            True if market is closed.
        """
        holidays_calendar = self._calendars.get("holidays")
        if isinstance(holidays_calendar, USMarketHolidays):
            return holidays_calendar.is_market_holiday(check_date)
        return False

    def get_daily_summary(self, check_date: date) -> dict[str, str | int | list[str] | bool]:
        """Get a summary of all events and conditions for a date.

        Args:
            check_date: Date to summarize.

        Returns:
            Dictionary with event summary and condition flags.
        """
        events = self.get_events_for_date(check_date)
        high_impact = [e for e in events if e.impact == ImpactLevel.HIGH]

        return {
            "date": check_date.isoformat(),
            "total_events": len(events),
            "high_impact_count": len(high_impact),
            "event_titles": [e.title for e in events],
            "high_impact_titles": [e.title for e in high_impact],
            "is_fed_blackout": self.is_fed_blackout(check_date),
            "is_market_holiday": self.is_market_holiday(check_date),
        }

    def __len__(self) -> int:
        """Return number of registered calendars."""
        return len(self._calendars)

    def __contains__(self, name: str) -> bool:
        """Check if a calendar is registered."""
        return name in self._calendars

    def __repr__(self) -> str:
        """Return string representation."""
        calendars = ", ".join(self._calendars.keys())
        return f"CalendarRegistry(year={self._year}, calendars=[{calendars}])"


# Global singleton instance
calendar_registry = CalendarRegistry()
