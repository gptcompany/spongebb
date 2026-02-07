"""Base classes for calendar events.

Provides the foundational dataclasses and enums for the calendar module.
"""

from dataclasses import dataclass, field
from datetime import date as date_type
from enum import Enum


class EventType(Enum):
    """Types of calendar events that impact liquidity."""

    TREASURY_AUCTION = "treasury_auction"
    FED_MEETING = "fed_meeting"
    ECB_MEETING = "ecb_meeting"
    BOJ_MEETING = "boj_meeting"
    BOE_MEETING = "boe_meeting"
    OPEC_MEETING = "opec_meeting"
    TAX_DATE = "tax_date"
    QUARTER_END = "quarter_end"
    MONTH_END = "month_end"
    HOLIDAY = "holiday"


class ImpactLevel(Enum):
    """Impact level of an event on liquidity."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, order=True)
class CalendarEvent:
    """A calendar event that may impact liquidity.

    Attributes:
        date: The date of the event.
        event_type: The type of event (from EventType enum).
        title: Short title describing the event.
        description: Optional longer description.
        settlement_date: Settlement date for auctions (T+1 or T+2).
        impact: Impact level on liquidity (low/medium/high).
        metadata: Additional event-specific data.

    Example:
        >>> event = CalendarEvent(
        ...     date=date(2026, 1, 29),
        ...     event_type=EventType.FED_MEETING,
        ...     title="FOMC Meeting",
        ...     impact=ImpactLevel.HIGH,
        ... )
    """

    # Sort by date first, then by impact (reversed for high priority first)
    event_date: date_type
    _impact_sort: int = field(init=False, repr=False, compare=True)
    event_type: EventType = field(compare=False)
    title: str = field(compare=False)
    description: str | None = field(default=None, compare=False)
    settlement_date: date_type | None = field(default=None, compare=False)
    impact: ImpactLevel = field(default=ImpactLevel.MEDIUM, compare=False)
    metadata: dict[str, str] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        """Set sort key for impact level (HIGH=0, MEDIUM=1, LOW=2)."""
        impact_order = {ImpactLevel.HIGH: 0, ImpactLevel.MEDIUM: 1, ImpactLevel.LOW: 2}
        object.__setattr__(self, "_impact_sort", impact_order[self.impact])

    @property
    def date(self) -> date_type:
        """Alias for event_date for backward compatibility."""
        return self.event_date

    @property
    def is_high_impact(self) -> bool:
        """Check if this is a high-impact event."""
        return self.impact == ImpactLevel.HIGH

    @property
    def days_until(self) -> int:
        """Return days until this event from today."""
        return (self.event_date - date_type.today()).days

    def to_dict(self) -> dict[str, str | None]:
        """Convert event to dictionary representation."""
        return {
            "date": self.event_date.isoformat(),
            "event_type": self.event_type.value,
            "title": self.title,
            "description": self.description,
            "settlement_date": self.settlement_date.isoformat() if self.settlement_date else None,
            "impact": self.impact.value,
            "metadata": str(self.metadata) if self.metadata else None,
        }


class BaseCalendar:
    """Abstract base class for calendar providers.

    Subclasses must implement the `get_events` method to return
    events for a given date range.
    """

    def get_events(
        self,
        start_date: date_type,
        end_date: date_type,
    ) -> list[CalendarEvent]:
        """Get events within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of CalendarEvent objects within the range.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement get_events")

    def get_events_for_year(self, year: int) -> list[CalendarEvent]:
        """Get all events for a given year.

        Args:
            year: The year to get events for.

        Returns:
            List of CalendarEvent objects for the year.
        """
        return self.get_events(date_type(year, 1, 1), date_type(year, 12, 31))

    def get_next_event(
        self,
        from_date: date_type | None = None,
        event_type: EventType | None = None,
    ) -> CalendarEvent | None:
        """Get the next upcoming event.

        Args:
            from_date: Date to search from (defaults to today).
            event_type: Optional filter by event type.

        Returns:
            The next CalendarEvent or None if no events found.
        """
        from_date = from_date or date_type.today()
        # Search up to 1 year ahead
        events = self.get_events(from_date, date_type(from_date.year + 1, from_date.month, from_date.day))

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[0] if events else None
