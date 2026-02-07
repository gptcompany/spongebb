"""OPEC meeting calendar.

Provides meeting dates for OPEC+ meetings including:
- JMMC (Joint Ministerial Monitoring Committee) - monitors compliance
- Ministerial (Full OPEC+ meeting) - major production decisions
- Extraordinary meetings - emergency sessions

OPEC+ meetings significantly impact oil prices and energy sector liquidity.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from liquidity.calendar.base import BaseCalendar, CalendarEvent, EventType, ImpactLevel


@dataclass(frozen=True)
class OPECMeeting:
    """Represents an OPEC+ meeting.

    Attributes:
        date: The date of the meeting.
        meeting_type: Type of meeting (JMMC, Ministerial, Extraordinary).
        description: Description of the meeting purpose.
        location: Optional meeting location (Vienna is default HQ).
        is_confirmed: Whether the meeting date is confirmed.

    Example:
        >>> meeting = OPECMeeting(
        ...     date=date(2026, 3, 1),
        ...     meeting_type="Ministerial",
        ...     description="OPEC+ full ministerial meeting"
        ... )
    """

    date: date
    meeting_type: str  # "JMMC", "Ministerial", "Extraordinary"
    description: str
    location: str | None = None
    is_confirmed: bool = True


# OPEC+ Meeting Schedule 2026
# JMMC typically meets monthly, Ministerial quarterly
# Based on typical OPEC+ scheduling patterns
OPEC_MEETINGS_2026: list[OPECMeeting] = [
    # Q1 2026
    OPECMeeting(
        date=date(2026, 1, 15),
        meeting_type="JMMC",
        description="Joint Ministerial Monitoring Committee - Q1 compliance review",
        location="Vienna",
    ),
    OPECMeeting(
        date=date(2026, 2, 12),
        meeting_type="JMMC",
        description="Joint Ministerial Monitoring Committee - monthly review",
        location="Vienna",
    ),
    OPECMeeting(
        date=date(2026, 3, 5),
        meeting_type="Ministerial",
        description="OPEC+ Full Ministerial Meeting - Q1 production decision",
        location="Vienna",
    ),
    # Q2 2026
    OPECMeeting(
        date=date(2026, 4, 9),
        meeting_type="JMMC",
        description="Joint Ministerial Monitoring Committee - monthly review",
        location="Vienna",
    ),
    OPECMeeting(
        date=date(2026, 5, 14),
        meeting_type="JMMC",
        description="Joint Ministerial Monitoring Committee - monthly review",
        location="Vienna",
    ),
    OPECMeeting(
        date=date(2026, 6, 4),
        meeting_type="Ministerial",
        description="OPEC+ Full Ministerial Meeting - H1 review and H2 outlook",
        location="Vienna",
    ),
    # Q3 2026
    OPECMeeting(
        date=date(2026, 7, 16),
        meeting_type="JMMC",
        description="Joint Ministerial Monitoring Committee - monthly review",
        location="Vienna",
    ),
    OPECMeeting(
        date=date(2026, 8, 13),
        meeting_type="JMMC",
        description="Joint Ministerial Monitoring Committee - monthly review",
        location="Vienna",
    ),
    OPECMeeting(
        date=date(2026, 9, 3),
        meeting_type="Ministerial",
        description="OPEC+ Full Ministerial Meeting - Q3 production decision",
        location="Vienna",
    ),
    # Q4 2026
    OPECMeeting(
        date=date(2026, 10, 8),
        meeting_type="JMMC",
        description="Joint Ministerial Monitoring Committee - monthly review",
        location="Vienna",
    ),
    OPECMeeting(
        date=date(2026, 11, 12),
        meeting_type="JMMC",
        description="Joint Ministerial Monitoring Committee - monthly review",
        location="Vienna",
    ),
    OPECMeeting(
        date=date(2026, 12, 3),
        meeting_type="Ministerial",
        description="OPEC+ Full Ministerial Meeting - annual review and 2027 outlook",
        location="Vienna",
    ),
]


class OPECCalendar(BaseCalendar):
    """Calendar for OPEC+ meetings.

    Provides meeting dates for JMMC and Full Ministerial meetings.
    Ministerial meetings are high-impact events as they determine
    production quotas that directly affect oil prices.

    Example:
        >>> calendar = OPECCalendar()
        >>> next_meeting = calendar.get_next_meeting()
        >>> if next_meeting:
        ...     print(f"Next: {next_meeting.meeting_type} on {next_meeting.date}")
        >>> is_soon = calendar.is_meeting_soon(days=7)
    """

    def __init__(self, meetings: list[OPECMeeting] | None = None) -> None:
        """Initialize the OPEC calendar.

        Args:
            meetings: Optional list of OPECMeeting objects.
                     Defaults to OPEC_MEETINGS_2026.
        """
        self._meetings = meetings if meetings is not None else OPEC_MEETINGS_2026
        self._events = self._build_events()

    def _build_events(self) -> list[CalendarEvent]:
        """Build CalendarEvent objects from OPEC meeting data."""
        events: list[CalendarEvent] = []

        for meeting in self._meetings:
            # Ministerial meetings are high impact (production decisions)
            # JMMC meetings are medium impact (compliance monitoring)
            impact = (
                ImpactLevel.HIGH
                if meeting.meeting_type == "Ministerial"
                else ImpactLevel.MEDIUM
            )

            # Extraordinary meetings are always high impact
            if meeting.meeting_type == "Extraordinary":
                impact = ImpactLevel.HIGH

            events.append(
                CalendarEvent(
                    event_date=meeting.date,
                    event_type=EventType.OPEC_MEETING,
                    title=f"OPEC+ {meeting.meeting_type} Meeting",
                    description=meeting.description,
                    impact=impact,
                    metadata={
                        "meeting_type": meeting.meeting_type,
                        "location": meeting.location or "Vienna",
                        "is_confirmed": str(meeting.is_confirmed),
                    },
                )
            )

        return sorted(events)

    def get_events(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get OPEC meeting events within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of OPEC meeting events within the range.
        """
        return [e for e in self._events if start_date <= e.date <= end_date]

    def get_next_meeting(
        self,
        from_date: date | None = None,
    ) -> OPECMeeting | None:
        """Get the next upcoming OPEC meeting.

        Args:
            from_date: Date to search from (defaults to today).

        Returns:
            The next OPECMeeting or None if no meetings found.
        """
        from_date = from_date or date.today()

        future_meetings = [m for m in self._meetings if m.date >= from_date]
        if not future_meetings:
            return None

        return min(future_meetings, key=lambda m: m.date)

    def get_meetings_in_range(
        self,
        start_date: date,
        end_date: date,
    ) -> list[OPECMeeting]:
        """Get OPEC meetings within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of OPECMeeting objects within the range.
        """
        return [
            m for m in self._meetings if start_date <= m.date <= end_date
        ]

    def is_meeting_soon(
        self,
        days: int = 7,
        from_date: date | None = None,
    ) -> bool:
        """Check if an OPEC meeting is happening within the specified days.

        Args:
            days: Number of days to look ahead (default 7).
            from_date: Date to check from (defaults to today).

        Returns:
            True if a meeting is scheduled within the specified days.
        """
        from_date = from_date or date.today()
        end_date = from_date + timedelta(days=days)

        return any(
            from_date <= m.date <= end_date for m in self._meetings
        )

    def get_ministerial_meetings(
        self,
        start_date: date,
        end_date: date,
    ) -> list[OPECMeeting]:
        """Get only Ministerial (full) meetings.

        These are the highest impact meetings where production
        quotas are set.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of Ministerial OPECMeeting objects.
        """
        return [
            m
            for m in self.get_meetings_in_range(start_date, end_date)
            if m.meeting_type == "Ministerial"
        ]

    def get_jmmc_meetings(
        self,
        start_date: date,
        end_date: date,
    ) -> list[OPECMeeting]:
        """Get only JMMC meetings.

        JMMC monitors compliance but doesn't typically change quotas.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of JMMC OPECMeeting objects.
        """
        return [
            m
            for m in self.get_meetings_in_range(start_date, end_date)
            if m.meeting_type == "JMMC"
        ]

    def days_until_next_meeting(
        self,
        from_date: date | None = None,
    ) -> int | None:
        """Get the number of days until the next OPEC meeting.

        Args:
            from_date: Date to count from (defaults to today).

        Returns:
            Number of days until the next meeting, or None if no meetings.
        """
        next_meeting = self.get_next_meeting(from_date)
        if not next_meeting:
            return None

        from_date = from_date or date.today()
        return (next_meeting.date - from_date).days
