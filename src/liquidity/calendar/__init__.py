"""Calendar module for tracking liquidity-impacting events.

Provides calendars for:
- Treasury auctions (TreasuryAuctionCalendar)
- Central bank meetings (CBMeetingCalendar)
- Tax payment dates (TaxDateCalendar)
- US market holidays (USMarketHolidays)

Use CalendarRegistry for unified access to all calendars.

Example:
    >>> from liquidity.calendar import calendar_registry, EventType, ImpactLevel
    >>> from datetime import date
    >>>
    >>> # Get all high-impact events for Q1 2026
    >>> events = calendar_registry.get_high_impact_events(
    ...     date(2026, 1, 1),
    ...     date(2026, 3, 31)
    ... )
    >>>
    >>> # Filter to just Fed meetings
    >>> fed_events = calendar_registry.filter_by_type(events, [EventType.FED_MEETING])
    >>>
    >>> # Check specific date conditions
    >>> is_blackout = calendar_registry.is_fed_blackout(date(2026, 1, 20))
"""

from liquidity.calendar.base import (
    BaseCalendar,
    CalendarEvent,
    EventType,
    ImpactLevel,
)
from liquidity.calendar.central_banks import (
    BOE_MEETINGS_2026,
    BOJ_MEETINGS_2026,
    ECB_MEETINGS_2026,
    FOMC_MEETINGS_2026,
    CBMeetingCalendar,
)
from liquidity.calendar.holidays import (
    US_MARKET_HOLIDAYS_2026,
    USMarketHolidays,
)
from liquidity.calendar.registry import (
    CalendarRegistry,
    calendar_registry,
)
from liquidity.calendar.tax_dates import (
    TAX_DATES_2026,
    TaxDateCalendar,
)
from liquidity.calendar.treasury import (
    TREASURY_AUCTIONS_2026,
    TreasuryAuctionCalendar,
)

__all__ = [
    # Base classes
    "BaseCalendar",
    "CalendarEvent",
    "EventType",
    "ImpactLevel",
    # Calendars
    "TreasuryAuctionCalendar",
    "CBMeetingCalendar",
    "TaxDateCalendar",
    "USMarketHolidays",
    # Registry
    "CalendarRegistry",
    "calendar_registry",
    # Static data
    "TREASURY_AUCTIONS_2026",
    "FOMC_MEETINGS_2026",
    "ECB_MEETINGS_2026",
    "BOJ_MEETINGS_2026",
    "BOE_MEETINGS_2026",
    "TAX_DATES_2026",
    "US_MARKET_HOLIDAYS_2026",
]
