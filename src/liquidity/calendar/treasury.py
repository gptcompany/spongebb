"""Treasury auction calendar.

Provides static data for US Treasury auctions in 2026.
Treasury auctions are significant liquidity events that affect TGA balances.

Data sourced from Treasury Direct auction schedule patterns.
"""

from datetime import date, timedelta

from liquidity.calendar.base import BaseCalendar, CalendarEvent, EventType, ImpactLevel

# Treasury auction schedule for 2026
# Pattern: Bills (weekly), Notes (monthly), Bonds (quarterly)
# Settlement: T+1 for bills, T+2 for notes/bonds

TREASURY_AUCTIONS_2026: list[dict[str, str | date | int]] = [
    # Q1 2026 - Weekly 4-week bills (Tuesdays)
    {"date": date(2026, 1, 7), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 1, 14), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 1, 21), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 1, 28), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 2, 4), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 2, 11), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 2, 18), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 2, 25), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 3, 4), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 3, 11), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 3, 18), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 3, 25), "type": "4-Week Bill", "settlement_days": 1},
    # Q1 2026 - Monthly 2-Year Notes (end of month)
    {"date": date(2026, 1, 27), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 2, 24), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 3, 24), "type": "2-Year Note", "settlement_days": 2},
    # Q1 2026 - Monthly 5-Year Notes
    {"date": date(2026, 1, 28), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 2, 25), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 3, 25), "type": "5-Year Note", "settlement_days": 2},
    # Q1 2026 - Monthly 10-Year Notes (HIGH IMPACT)
    {"date": date(2026, 1, 8), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    {"date": date(2026, 2, 11), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    {"date": date(2026, 3, 11), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    # Q1 2026 - Quarterly 30-Year Bonds (HIGH IMPACT)
    {"date": date(2026, 2, 12), "type": "30-Year Bond", "settlement_days": 2, "impact": "high"},
    # Q2 2026 - Weekly 4-week bills
    {"date": date(2026, 4, 7), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 4, 14), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 4, 21), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 4, 28), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 5, 5), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 5, 12), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 5, 19), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 5, 26), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 6, 2), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 6, 9), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 6, 16), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 6, 23), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 6, 30), "type": "4-Week Bill", "settlement_days": 1},
    # Q2 2026 - Monthly notes
    {"date": date(2026, 4, 28), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 5, 26), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 6, 23), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 4, 29), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 5, 27), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 6, 24), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 4, 8), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    {"date": date(2026, 5, 13), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    {"date": date(2026, 6, 10), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    # Q2 2026 - Quarterly 30-Year Bond
    {"date": date(2026, 5, 14), "type": "30-Year Bond", "settlement_days": 2, "impact": "high"},
    # Q3 2026 - Weekly 4-week bills
    {"date": date(2026, 7, 7), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 7, 14), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 7, 21), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 7, 28), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 8, 4), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 8, 11), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 8, 18), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 8, 25), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 9, 1), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 9, 8), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 9, 15), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 9, 22), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 9, 29), "type": "4-Week Bill", "settlement_days": 1},
    # Q3 2026 - Monthly notes
    {"date": date(2026, 7, 28), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 8, 25), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 9, 22), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 7, 29), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 8, 26), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 9, 23), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 7, 8), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    {"date": date(2026, 8, 12), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    {"date": date(2026, 9, 9), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    # Q3 2026 - Quarterly 30-Year Bond
    {"date": date(2026, 8, 13), "type": "30-Year Bond", "settlement_days": 2, "impact": "high"},
    # Q4 2026 - Weekly 4-week bills
    {"date": date(2026, 10, 6), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 10, 13), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 10, 20), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 10, 27), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 11, 3), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 11, 10), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 11, 17), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 11, 24), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 12, 1), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 12, 8), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 12, 15), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 12, 22), "type": "4-Week Bill", "settlement_days": 1},
    {"date": date(2026, 12, 29), "type": "4-Week Bill", "settlement_days": 1},
    # Q4 2026 - Monthly notes
    {"date": date(2026, 10, 27), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 11, 24), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 12, 22), "type": "2-Year Note", "settlement_days": 2},
    {"date": date(2026, 10, 28), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 11, 25), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 12, 23), "type": "5-Year Note", "settlement_days": 2},
    {"date": date(2026, 10, 7), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    {"date": date(2026, 11, 12), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    {"date": date(2026, 12, 9), "type": "10-Year Note", "settlement_days": 2, "impact": "high"},
    # Q4 2026 - Quarterly 30-Year Bond
    {"date": date(2026, 11, 13), "type": "30-Year Bond", "settlement_days": 2, "impact": "high"},
    # TIPS auctions (quarterly)
    {"date": date(2026, 1, 22), "type": "10-Year TIPS", "settlement_days": 2},
    {"date": date(2026, 4, 23), "type": "10-Year TIPS", "settlement_days": 2},
    {"date": date(2026, 7, 23), "type": "10-Year TIPS", "settlement_days": 2},
    {"date": date(2026, 10, 22), "type": "10-Year TIPS", "settlement_days": 2},
    # FRN auctions (monthly)
    {"date": date(2026, 1, 29), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 2, 26), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 3, 26), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 4, 30), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 5, 28), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 6, 25), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 7, 30), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 8, 27), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 9, 24), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 10, 29), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 11, 26), "type": "2-Year FRN", "settlement_days": 2},
    {"date": date(2026, 12, 24), "type": "2-Year FRN", "settlement_days": 2},
]


class TreasuryAuctionCalendar(BaseCalendar):
    """Calendar for US Treasury auctions.

    Provides auction dates for Bills, Notes, Bonds, TIPS, and FRNs.
    High-impact events include 10-Year Note and 30-Year Bond auctions.

    Example:
        >>> calendar = TreasuryAuctionCalendar()
        >>> events = calendar.get_events(date(2026, 1, 1), date(2026, 1, 31))
        >>> high_impact = [e for e in events if e.is_high_impact]
    """

    def __init__(self) -> None:
        """Initialize the Treasury auction calendar."""
        self._events = self._build_events()

    def _build_events(self) -> list[CalendarEvent]:
        """Build CalendarEvent objects from static auction data."""
        events: list[CalendarEvent] = []

        for auction in TREASURY_AUCTIONS_2026:
            auction_date = auction["date"]
            auction_type = str(auction["type"])
            settlement_days_val = auction["settlement_days"]
            settlement_days = int(settlement_days_val) if isinstance(settlement_days_val, (int, str)) else 1
            impact_str = auction.get("impact", "medium")

            # Map impact string to enum
            impact = ImpactLevel.HIGH if impact_str == "high" else ImpactLevel.MEDIUM

            # Bills are low impact
            if "Bill" in auction_type:
                impact = ImpactLevel.LOW

            # Calculate settlement date
            if isinstance(auction_date, date):
                settlement = auction_date + timedelta(days=settlement_days)
            else:
                settlement = None

            events.append(
                CalendarEvent(
                    event_date=auction_date if isinstance(auction_date, date) else date.today(),
                    event_type=EventType.TREASURY_AUCTION,
                    title=f"Treasury {auction_type} Auction",
                    description=f"US Treasury {auction_type} auction with T+{settlement_days} settlement",
                    settlement_date=settlement,
                    impact=impact,
                    metadata={"security_type": auction_type},
                )
            )

        return sorted(events)

    def get_events(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get Treasury auction events within a date range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of Treasury auction events within the range.
        """
        return [e for e in self._events if start_date <= e.date <= end_date]

    def get_high_impact_auctions(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Get only high-impact auctions (10Y Notes, 30Y Bonds).

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of high-impact Treasury auction events.
        """
        return [
            e
            for e in self.get_events(start_date, end_date)
            if e.impact == ImpactLevel.HIGH
        ]

    def get_settlement_dates(
        self,
        start_date: date,
        end_date: date,
    ) -> list[date]:
        """Get settlement dates for auctions in the date range.

        Settlement dates are when funds actually flow, impacting TGA.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            List of settlement dates within the range.
        """
        events = self.get_events(start_date, end_date)
        return sorted(
            [e.settlement_date for e in events if e.settlement_date is not None]
        )
