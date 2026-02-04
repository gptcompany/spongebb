"""Central bank meeting calendar.

Provides meeting dates for major central banks:
- Federal Reserve (FOMC)
- European Central Bank (ECB)
- Bank of Japan (BoJ)
- Bank of England (BoE)

Includes blackout periods for Fed (10 days before meeting).
"""

from datetime import date, timedelta

from liquidity.calendar.base import BaseCalendar, CalendarEvent, EventType, ImpactLevel

# FOMC Meeting Schedule 2026 (8 meetings per year)
# Source: Federal Reserve Board calendar
FOMC_MEETINGS_2026: list[tuple[date, date]] = [
    (date(2026, 1, 27), date(2026, 1, 28)),   # January
    (date(2026, 3, 17), date(2026, 3, 18)),   # March
    (date(2026, 5, 5), date(2026, 5, 6)),     # May
    (date(2026, 6, 16), date(2026, 6, 17)),   # June
    (date(2026, 7, 28), date(2026, 7, 29)),   # July
    (date(2026, 9, 15), date(2026, 9, 16)),   # September
    (date(2026, 11, 3), date(2026, 11, 4)),   # November
    (date(2026, 12, 15), date(2026, 12, 16)), # December
]

# ECB Governing Council Schedule 2026 (6 monetary policy meetings)
# Source: ECB calendar
ECB_MEETINGS_2026: list[date] = [
    date(2026, 1, 22),   # January
    date(2026, 3, 12),   # March
    date(2026, 4, 30),   # April
    date(2026, 6, 11),   # June
    date(2026, 9, 10),   # September
    date(2026, 10, 29),  # October
    date(2026, 12, 17),  # December
]

# Bank of Japan Monetary Policy Meetings 2026 (8 meetings)
# Source: BoJ calendar
BOJ_MEETINGS_2026: list[tuple[date, date]] = [
    (date(2026, 1, 22), date(2026, 1, 23)),   # January
    (date(2026, 3, 12), date(2026, 3, 13)),   # March
    (date(2026, 4, 30), date(2026, 5, 1)),    # April/May
    (date(2026, 6, 18), date(2026, 6, 19)),   # June
    (date(2026, 7, 30), date(2026, 7, 31)),   # July
    (date(2026, 9, 17), date(2026, 9, 18)),   # September
    (date(2026, 10, 29), date(2026, 10, 30)), # October
    (date(2026, 12, 17), date(2026, 12, 18)), # December
]

# Bank of England MPC Schedule 2026 (8 meetings)
# Source: BoE calendar
BOE_MEETINGS_2026: list[date] = [
    date(2026, 2, 5),    # February
    date(2026, 3, 19),   # March
    date(2026, 5, 7),    # May
    date(2026, 6, 18),   # June
    date(2026, 8, 6),    # August
    date(2026, 9, 17),   # September
    date(2026, 11, 5),   # November
    date(2026, 12, 17),  # December
]


class CBMeetingCalendar(BaseCalendar):
    """Calendar for central bank monetary policy meetings.

    Tracks FOMC, ECB, BoJ, and BoE meetings. All CB meetings are
    high-impact events as they can significantly affect liquidity
    and market conditions.

    Fed meetings include blackout period tracking (10 days before).

    Example:
        >>> calendar = CBMeetingCalendar()
        >>> events = calendar.get_events(date(2026, 1, 1), date(2026, 3, 31))
        >>> fomc = [e for e in events if e.event_type == EventType.FED_MEETING]
    """

    # Fed blackout period: 10 calendar days before and including decision day
    FED_BLACKOUT_DAYS = 10

    def __init__(self) -> None:
        """Initialize the central bank meeting calendar."""
        self._events = self._build_events()
        self._fed_blackouts = self._build_fed_blackouts()

    def _build_events(self) -> list[CalendarEvent]:
        """Build CalendarEvent objects from static meeting data."""
        events: list[CalendarEvent] = []

        # FOMC meetings (2-day meetings, decision on day 2)
        for day1, day2 in FOMC_MEETINGS_2026:
            events.append(
                CalendarEvent(
                    event_date=day2,  # Decision day
                    event_type=EventType.FED_MEETING,
                    title="FOMC Meeting Decision",
                    description=f"Federal Reserve FOMC meeting ({day1.strftime('%b %d')}-{day2.strftime('%d')})",
                    impact=ImpactLevel.HIGH,
                    metadata={
                        "meeting_start": day1.isoformat(),
                        "meeting_end": day2.isoformat(),
                        "central_bank": "Federal Reserve",
                    },
                )
            )

        # ECB meetings (single day)
        for meeting_date in ECB_MEETINGS_2026:
            events.append(
                CalendarEvent(
                    event_date=meeting_date,
                    event_type=EventType.ECB_MEETING,
                    title="ECB Governing Council Decision",
                    description="European Central Bank monetary policy decision",
                    impact=ImpactLevel.HIGH,
                    metadata={"central_bank": "European Central Bank"},
                )
            )

        # BoJ meetings (2-day meetings)
        for day1, day2 in BOJ_MEETINGS_2026:
            events.append(
                CalendarEvent(
                    event_date=day2,  # Decision day
                    event_type=EventType.BOJ_MEETING,
                    title="BoJ MPM Decision",
                    description=f"Bank of Japan Monetary Policy Meeting ({day1.strftime('%b %d')}-{day2.strftime('%d')})",
                    impact=ImpactLevel.HIGH,
                    metadata={
                        "meeting_start": day1.isoformat(),
                        "meeting_end": day2.isoformat(),
                        "central_bank": "Bank of Japan",
                    },
                )
            )

        # BoE meetings (single day)
        for meeting_date in BOE_MEETINGS_2026:
            events.append(
                CalendarEvent(
                    event_date=meeting_date,
                    event_type=EventType.BOE_MEETING,
                    title="BoE MPC Decision",
                    description="Bank of England Monetary Policy Committee decision",
                    impact=ImpactLevel.HIGH,
                    metadata={"central_bank": "Bank of England"},
                )
            )

        return sorted(events)

    def _build_fed_blackouts(self) -> list[tuple[date, date]]:
        """Build list of Fed blackout periods.

        Returns:
            List of (start, end) tuples for each blackout period.
        """
        blackouts: list[tuple[date, date]] = []

        for _, decision_day in FOMC_MEETINGS_2026:
            blackout_start = decision_day - timedelta(days=self.FED_BLACKOUT_DAYS)
            blackouts.append((blackout_start, decision_day))

        return blackouts

    def get_events(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get central bank meeting events within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of central bank meeting events within the range.
        """
        return [e for e in self._events if start_date <= e.date <= end_date]

    def get_fed_meetings(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get only FOMC meetings within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of FOMC meeting events.
        """
        return [
            e
            for e in self.get_events(start_date, end_date)
            if e.event_type == EventType.FED_MEETING
        ]

    def is_fed_blackout(self, check_date: date) -> bool:
        """Check if a date falls within a Fed blackout period.

        During blackout, Fed officials cannot publicly discuss
        monetary policy, which affects market communication.

        Args:
            check_date: Date to check.

        Returns:
            True if the date is within a Fed blackout period.
        """
        for blackout_start, blackout_end in self._fed_blackouts:
            if blackout_start <= check_date <= blackout_end:
                return True
        return False

    def get_fed_blackout_periods(
        self,
        start_date: date,
        end_date: date,
    ) -> list[tuple[date, date]]:
        """Get Fed blackout periods that overlap with a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of (start, end) tuples for blackout periods.
        """
        return [
            (blackout_start, blackout_end)
            for blackout_start, blackout_end in self._fed_blackouts
            if blackout_start <= end_date and blackout_end >= start_date
        ]

    def get_events_by_bank(
        self,
        start_date: date,
        end_date: date,
        bank: str,
    ) -> list[CalendarEvent]:
        """Get meetings for a specific central bank.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).
            bank: Central bank name ('fed', 'ecb', 'boj', 'boe').

        Returns:
            List of meeting events for the specified bank.

        Raises:
            ValueError: If bank name is not recognized.
        """
        bank_to_type = {
            "fed": EventType.FED_MEETING,
            "ecb": EventType.ECB_MEETING,
            "boj": EventType.BOJ_MEETING,
            "boe": EventType.BOE_MEETING,
        }

        bank_lower = bank.lower()
        if bank_lower not in bank_to_type:
            valid_banks = ", ".join(bank_to_type.keys())
            raise ValueError(f"Unknown bank '{bank}'. Valid options: {valid_banks}")

        event_type = bank_to_type[bank_lower]
        return [
            e
            for e in self.get_events(start_date, end_date)
            if e.event_type == event_type
        ]
