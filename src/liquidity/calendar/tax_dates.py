"""Tax payment date calendar.

Provides US tax payment dates that significantly impact TGA balances.
Major tax dates cause large inflows to TGA, draining liquidity.

Key dates:
- April 15: Individual tax deadline
- Quarterly estimated payments: Jan 15, April 15, June 15, Sept 15
- Corporate tax dates: March 15, June 15, Sept 15, Dec 15
"""

from datetime import date

from liquidity.calendar.base import BaseCalendar, CalendarEvent, EventType, ImpactLevel

# US Tax Payment Dates 2026
TAX_DATES_2026: list[dict[str, date | str | ImpactLevel]] = [
    # Q1 2026
    {
        "date": date(2026, 1, 15),
        "title": "Q4 2025 Estimated Tax Payment Due",
        "description": "Quarterly estimated tax payment for Q4 2025. Major TGA inflow.",
        "impact": ImpactLevel.HIGH,
        "tax_type": "estimated_quarterly",
    },
    {
        "date": date(2026, 3, 15),
        "title": "Corporate Tax Returns Due (S-Corps, Partnerships)",
        "description": "S-Corporation and Partnership tax returns due. Moderate TGA impact.",
        "impact": ImpactLevel.MEDIUM,
        "tax_type": "corporate",
    },
    # Q2 2026
    {
        "date": date(2026, 4, 15),
        "title": "Individual Tax Returns Due + Q1 Estimated Payment",
        "description": "Federal income tax deadline. Largest TGA inflow of the year.",
        "impact": ImpactLevel.HIGH,
        "tax_type": "individual_annual",
    },
    {
        "date": date(2026, 6, 15),
        "title": "Q2 Estimated Tax Payment Due + Corporate Extensions",
        "description": "Quarterly estimated payment and extended corporate returns due.",
        "impact": ImpactLevel.HIGH,
        "tax_type": "estimated_quarterly",
    },
    # Q3 2026
    {
        "date": date(2026, 9, 15),
        "title": "Q3 Estimated Tax Payment Due + Extended Partnership Returns",
        "description": "Quarterly estimated payment. Significant TGA inflow.",
        "impact": ImpactLevel.HIGH,
        "tax_type": "estimated_quarterly",
    },
    # Q4 2026
    {
        "date": date(2026, 10, 15),
        "title": "Extended Individual Tax Returns Due",
        "description": "Extended individual tax returns deadline. Moderate TGA impact.",
        "impact": ImpactLevel.MEDIUM,
        "tax_type": "individual_extended",
    },
    {
        "date": date(2026, 12, 15),
        "title": "Corporate Estimated Tax Payment",
        "description": "Corporate quarterly estimated tax payment. Large TGA inflow.",
        "impact": ImpactLevel.HIGH,
        "tax_type": "corporate_estimated",
    },
]


# Month-end and Quarter-end dates (window dressing, rebalancing)
def _generate_period_end_dates(year: int) -> list[dict[str, date | str | ImpactLevel]]:
    """Generate month-end and quarter-end dates for a year.

    Args:
        year: The year to generate dates for.

    Returns:
        List of period end date definitions.
    """
    from calendar import monthrange

    period_ends: list[dict[str, date | str | ImpactLevel]] = []
    quarter_months = {3, 6, 9, 12}

    for month in range(1, 13):
        last_day = monthrange(year, month)[1]
        end_date = date(year, month, last_day)

        if month in quarter_months:
            period_ends.append({
                "date": end_date,
                "title": f"Q{month // 3} Quarter End",
                "description": "Quarter-end rebalancing and window dressing. Elevated volatility.",
                "impact": ImpactLevel.HIGH,
                "period_type": "quarter_end",
            })
        else:
            period_ends.append({
                "date": end_date,
                "title": f"{end_date.strftime('%B')} Month End",
                "description": "Month-end rebalancing. Moderate liquidity impact.",
                "impact": ImpactLevel.MEDIUM,
                "period_type": "month_end",
            })

    return period_ends


class TaxDateCalendar(BaseCalendar):
    """Calendar for US tax payment dates and period ends.

    Tax payments cause significant TGA inflows, draining market liquidity.
    April 15 is typically the highest impact day of the year.

    Also tracks month-end and quarter-end dates which affect
    portfolio rebalancing and window dressing flows.

    Example:
        >>> calendar = TaxDateCalendar()
        >>> events = calendar.get_events(date(2026, 4, 1), date(2026, 4, 30))
        >>> tax_day = [e for e in events if "Individual Tax" in e.title]
    """

    def __init__(self, year: int = 2026) -> None:
        """Initialize the tax date calendar.

        Args:
            year: Year for period-end dates (default 2026).
        """
        self._year = year
        self._events = self._build_events()

    def _build_events(self) -> list[CalendarEvent]:
        """Build CalendarEvent objects from static tax date data."""
        events: list[CalendarEvent] = []

        # Tax payment dates
        for tax_date in TAX_DATES_2026:
            event_date = tax_date["date"]
            if not isinstance(event_date, date):
                continue

            impact = tax_date.get("impact", ImpactLevel.MEDIUM)
            if not isinstance(impact, ImpactLevel):
                impact = ImpactLevel.MEDIUM

            events.append(
                CalendarEvent(
                    event_date=event_date,
                    event_type=EventType.TAX_DATE,
                    title=str(tax_date["title"]),
                    description=str(tax_date.get("description", "")),
                    impact=impact,
                    metadata={"tax_type": str(tax_date.get("tax_type", ""))},
                )
            )

        # Period end dates
        for period_end in _generate_period_end_dates(self._year):
            event_date = period_end["date"]
            if not isinstance(event_date, date):
                continue

            impact = period_end.get("impact", ImpactLevel.MEDIUM)
            if not isinstance(impact, ImpactLevel):
                impact = ImpactLevel.MEDIUM

            period_type = str(period_end.get("period_type", "month_end"))
            event_type = (
                EventType.QUARTER_END
                if period_type == "quarter_end"
                else EventType.MONTH_END
            )

            events.append(
                CalendarEvent(
                    event_date=event_date,
                    event_type=event_type,
                    title=str(period_end["title"]),
                    description=str(period_end.get("description", "")),
                    impact=impact,
                    metadata={"period_type": period_type},
                )
            )

        return sorted(events)

    def get_events(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get tax and period-end events within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of tax and period-end events within the range.
        """
        return [e for e in self._events if start_date <= e.date <= end_date]

    def get_tax_dates_only(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get only tax payment dates (excludes period ends).

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of tax payment date events.
        """
        return [
            e
            for e in self.get_events(start_date, end_date)
            if e.event_type == EventType.TAX_DATE
        ]

    def get_quarter_ends(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get only quarter-end dates.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of quarter-end events.
        """
        return [
            e
            for e in self.get_events(start_date, end_date)
            if e.event_type == EventType.QUARTER_END
        ]

    def get_month_ends(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get only month-end dates (excludes quarter ends).

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of month-end events.
        """
        return [
            e
            for e in self.get_events(start_date, end_date)
            if e.event_type == EventType.MONTH_END
        ]

    def is_high_liquidity_drain_day(self, check_date: date) -> bool:
        """Check if a date is a high liquidity drain day.

        High drain days are major tax dates that cause significant
        TGA inflows, draining market liquidity.

        Args:
            check_date: Date to check.

        Returns:
            True if the date is a high liquidity drain day.
        """
        events = self.get_tax_dates_only(check_date, check_date)
        return any(e.impact == ImpactLevel.HIGH for e in events)
