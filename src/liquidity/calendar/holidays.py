"""US market holidays calendar.

Provides NYSE market holidays using the `holidays` package.
Market holidays reduce liquidity as trading is halted.
"""

from datetime import date

try:
    import holidays as holidays_lib
except ImportError:
    holidays_lib = None

from liquidity.calendar.base import BaseCalendar, CalendarEvent, EventType, ImpactLevel

# Fallback static holidays for 2026 if holidays package unavailable
US_MARKET_HOLIDAYS_2026: dict[date, str] = {
    date(2026, 1, 1): "New Year's Day",
    date(2026, 1, 19): "Martin Luther King Jr. Day",
    date(2026, 2, 16): "Presidents Day",
    date(2026, 4, 3): "Good Friday",
    date(2026, 5, 25): "Memorial Day",
    date(2026, 6, 19): "Juneteenth",
    date(2026, 7, 3): "Independence Day (Observed)",
    date(2026, 9, 7): "Labor Day",
    date(2026, 11, 26): "Thanksgiving Day",
    date(2026, 12, 25): "Christmas Day",
}


class USMarketHolidays(BaseCalendar):
    """Calendar for US stock market holidays.

    Uses the `holidays` package for NYSE holiday calendar.
    Falls back to static data if package is unavailable.

    Market holidays have medium impact as they reduce liquidity
    and can cause position adjustments before/after.

    Example:
        >>> calendar = USMarketHolidays()
        >>> holidays = calendar.get_events(date(2026, 1, 1), date(2026, 12, 31))
        >>> print(f"Market closed {len(holidays)} days in 2026")
    """

    def __init__(self, year: int = 2026) -> None:
        """Initialize the US market holidays calendar.

        Args:
            year: Year to get holidays for (default 2026).
        """
        self._year = year
        self._holidays = self._load_holidays()
        self._events = self._build_events()

    def _load_holidays(self) -> dict[date, str]:
        """Load holidays from package or fallback to static data.

        Returns:
            Dictionary mapping dates to holiday names.
        """
        if holidays_lib is not None:
            try:
                # NYSE holidays
                nyse_holidays = holidays_lib.financial_holidays("NYSE", years=self._year)
                return dict(nyse_holidays.items())
            except Exception:
                # Fall back to static data
                pass

        # Use static data for the requested year if available
        if self._year == 2026:
            return US_MARKET_HOLIDAYS_2026.copy()

        # Empty dict for unsupported years without holidays package
        return {}

    def _build_events(self) -> list[CalendarEvent]:
        """Build CalendarEvent objects from holiday data."""
        events: list[CalendarEvent] = []

        for holiday_date, holiday_name in self._holidays.items():
            events.append(
                CalendarEvent(
                    event_date=holiday_date,
                    event_type=EventType.HOLIDAY,
                    title=f"Market Closed: {holiday_name}",
                    description=f"NYSE closed for {holiday_name}. No US equity trading.",
                    impact=ImpactLevel.MEDIUM,
                    metadata={"holiday_name": holiday_name, "market": "NYSE"},
                )
            )

        return sorted(events)

    def get_events(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get market holiday events within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of market holiday events within the range.
        """
        return [e for e in self._events if start_date <= e.date <= end_date]

    def is_market_holiday(self, check_date: date) -> bool:
        """Check if a date is a market holiday.

        Args:
            check_date: Date to check.

        Returns:
            True if the date is a market holiday.
        """
        return check_date in self._holidays

    def get_holiday_name(self, check_date: date) -> str | None:
        """Get the holiday name for a date.

        Args:
            check_date: Date to check.

        Returns:
            Holiday name if the date is a holiday, None otherwise.
        """
        return self._holidays.get(check_date)

    def is_trading_day(self, check_date: date) -> bool:
        """Check if a date is a trading day.

        A trading day is a weekday that is not a market holiday.

        Args:
            check_date: Date to check.

        Returns:
            True if the date is a trading day.
        """
        # Weekend check (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            return False
        return not self.is_market_holiday(check_date)

    def get_next_trading_day(self, from_date: date) -> date:
        """Get the next trading day from a given date.

        Args:
            from_date: Date to search from.

        Returns:
            The next trading day (may be from_date if it's a trading day).
        """
        current = from_date
        # Limit search to avoid infinite loop
        for _ in range(30):
            if self.is_trading_day(current):
                return current
            current = date(
                current.year,
                current.month,
                current.day + 1 if current.day < 28 else 1,
            )
            # Handle month/year rollover properly
            from datetime import timedelta
            current = from_date + timedelta(days=(_ + 1))
        return from_date  # Fallback

    def count_trading_days(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        """Count the number of trading days in a range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            Number of trading days in the range.
        """
        from datetime import timedelta

        count = 0
        current = start_date
        while current <= end_date:
            if self.is_trading_day(current):
                count += 1
            current += timedelta(days=1)
        return count
