"""Unit tests for Treasury auction calendar.

Run with: uv run pytest tests/unit/test_calendar/test_treasury.py -v
"""

from datetime import date, timedelta

import pytest

from liquidity.calendar.base import EventType, ImpactLevel
from liquidity.calendar.treasury import (
    TREASURY_AUCTIONS_2026,
    TreasuryAuctionCalendar,
)


class TestTreasuryAuctions2026Data:
    """Tests for static Treasury auction data."""

    def test_auctions_exist(self) -> None:
        """Test that auction data exists."""
        assert len(TREASURY_AUCTIONS_2026) > 0

    def test_all_auctions_have_required_fields(self) -> None:
        """Test all auctions have required fields."""
        for auction in TREASURY_AUCTIONS_2026:
            assert "date" in auction
            assert "type" in auction
            assert "settlement_days" in auction
            assert isinstance(auction["date"], date)
            assert isinstance(auction["type"], str)
            assert isinstance(auction["settlement_days"], int)

    def test_auctions_are_in_2026(self) -> None:
        """Test all auctions are in 2026."""
        for auction in TREASURY_AUCTIONS_2026:
            auction_date = auction["date"]
            if isinstance(auction_date, date):
                assert auction_date.year == 2026

    def test_has_weekly_bills(self) -> None:
        """Test weekly 4-week bills are included."""
        bills = [a for a in TREASURY_AUCTIONS_2026 if "Bill" in str(a["type"])]
        # Should have ~52 weekly bill auctions
        assert len(bills) >= 48  # Allow some variance

    def test_has_monthly_notes(self) -> None:
        """Test monthly note auctions are included."""
        two_year = [a for a in TREASURY_AUCTIONS_2026 if "2-Year Note" in str(a["type"])]
        five_year = [a for a in TREASURY_AUCTIONS_2026 if "5-Year Note" in str(a["type"])]
        ten_year = [a for a in TREASURY_AUCTIONS_2026 if "10-Year Note" in str(a["type"])]

        assert len(two_year) >= 11  # Monthly
        assert len(five_year) >= 11  # Monthly
        assert len(ten_year) >= 11  # Monthly

    def test_has_quarterly_bonds(self) -> None:
        """Test quarterly 30-Year bond auctions are included."""
        bonds = [a for a in TREASURY_AUCTIONS_2026 if "30-Year Bond" in str(a["type"])]
        assert len(bonds) >= 4  # Quarterly

    def test_has_tips_auctions(self) -> None:
        """Test TIPS auctions are included."""
        tips = [a for a in TREASURY_AUCTIONS_2026 if "TIPS" in str(a["type"])]
        assert len(tips) >= 4  # Quarterly

    def test_has_frn_auctions(self) -> None:
        """Test FRN auctions are included."""
        frn = [a for a in TREASURY_AUCTIONS_2026 if "FRN" in str(a["type"])]
        assert len(frn) >= 11  # Monthly

    def test_high_impact_auctions_marked(self) -> None:
        """Test 10Y and 30Y auctions are marked as high impact."""
        high_impact = [
            a for a in TREASURY_AUCTIONS_2026
            if a.get("impact") == "high"
        ]
        assert len(high_impact) > 0

        for auction in high_impact:
            auction_type = str(auction["type"])
            assert "10-Year" in auction_type or "30-Year" in auction_type


class TestTreasuryAuctionCalendar:
    """Tests for TreasuryAuctionCalendar class."""

    @pytest.fixture
    def calendar(self) -> TreasuryAuctionCalendar:
        """Create a Treasury auction calendar fixture."""
        return TreasuryAuctionCalendar()

    def test_calendar_initializes(self, calendar: TreasuryAuctionCalendar) -> None:
        """Test calendar initializes without error."""
        assert calendar is not None

    def test_get_events_returns_sorted_list(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test get_events returns chronologically sorted events."""
        events = calendar.get_events(date(2026, 1, 1), date(2026, 3, 31))

        assert len(events) > 0
        # Check events are sorted by date
        dates = [e.date for e in events]
        assert dates == sorted(dates)

    def test_get_events_respects_date_range(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test get_events only returns events within range."""
        start = date(2026, 2, 1)
        end = date(2026, 2, 28)
        events = calendar.get_events(start, end)

        for event in events:
            assert start <= event.date <= end

    def test_all_events_are_treasury_type(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test all events have TREASURY_AUCTION type."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            assert event.event_type == EventType.TREASURY_AUCTION

    def test_events_have_settlement_dates(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test all events have settlement dates."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            assert event.settlement_date is not None
            # Settlement should be after auction date
            assert event.settlement_date > event.date

    def test_bill_settlement_is_t_plus_1(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test bill auctions have T+1 settlement."""
        events = calendar.get_events_for_year(2026)
        bills = [e for e in events if "Bill" in e.title]

        for bill in bills:
            if bill.settlement_date:
                days_to_settle = (bill.settlement_date - bill.date).days
                assert days_to_settle == 1

    def test_note_bond_settlement_is_t_plus_2(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test note/bond auctions have T+2 settlement."""
        events = calendar.get_events_for_year(2026)
        notes_bonds = [
            e for e in events
            if "Note" in e.title or "Bond" in e.title or "TIPS" in e.title or "FRN" in e.title
        ]

        for nb in notes_bonds:
            if nb.settlement_date:
                days_to_settle = (nb.settlement_date - nb.date).days
                assert days_to_settle == 2

    def test_bills_are_low_impact(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test bill auctions are low impact."""
        events = calendar.get_events_for_year(2026)
        bills = [e for e in events if "Bill" in e.title]

        for bill in bills:
            assert bill.impact == ImpactLevel.LOW

    def test_ten_year_bonds_are_high_impact(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test 10-Year note auctions are high impact."""
        events = calendar.get_events_for_year(2026)
        ten_year = [e for e in events if "10-Year Note" in e.title]

        assert len(ten_year) > 0
        for event in ten_year:
            assert event.impact == ImpactLevel.HIGH

    def test_thirty_year_bonds_are_high_impact(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test 30-Year bond auctions are high impact."""
        events = calendar.get_events_for_year(2026)
        thirty_year = [e for e in events if "30-Year Bond" in e.title]

        assert len(thirty_year) > 0
        for event in thirty_year:
            assert event.impact == ImpactLevel.HIGH

    def test_get_high_impact_auctions(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test get_high_impact_auctions returns only high impact."""
        events = calendar.get_high_impact_auctions(
            date(2026, 1, 1), date(2026, 12, 31)
        )

        assert len(events) > 0
        for event in events:
            assert event.impact == ImpactLevel.HIGH

    def test_get_settlement_dates(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test get_settlement_dates returns sorted dates."""
        settlements = calendar.get_settlement_dates(
            date(2026, 1, 1), date(2026, 1, 31)
        )

        assert len(settlements) > 0
        assert settlements == sorted(settlements)

    def test_events_have_metadata(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test events have security_type in metadata."""
        events = calendar.get_events_for_year(2026)

        for event in events:
            assert "security_type" in event.metadata


class TestTreasuryAuctionCalendarEdgeCases:
    """Edge case tests for Treasury auction calendar."""

    @pytest.fixture
    def calendar(self) -> TreasuryAuctionCalendar:
        """Create a Treasury auction calendar fixture."""
        return TreasuryAuctionCalendar()

    def test_empty_date_range(self, calendar: TreasuryAuctionCalendar) -> None:
        """Test empty date range returns empty list."""
        # Date range with no auctions (unlikely but test the logic)
        events = calendar.get_events(date(2025, 1, 1), date(2025, 1, 2))
        assert events == []

    def test_single_day_range(self, calendar: TreasuryAuctionCalendar) -> None:
        """Test single day range works correctly."""
        # January 7, 2026 should have a 4-Week Bill auction
        events = calendar.get_events(date(2026, 1, 7), date(2026, 1, 7))

        for event in events:
            assert event.date == date(2026, 1, 7)

    def test_q1_has_all_auction_types(
        self, calendar: TreasuryAuctionCalendar
    ) -> None:
        """Test Q1 2026 has all auction types."""
        events = calendar.get_events(date(2026, 1, 1), date(2026, 3, 31))

        types_found = set()
        for event in events:
            security_type = event.metadata.get("security_type", "")
            if "Bill" in security_type:
                types_found.add("bill")
            elif "2-Year Note" in security_type:
                types_found.add("2y_note")
            elif "5-Year Note" in security_type:
                types_found.add("5y_note")
            elif "10-Year Note" in security_type:
                types_found.add("10y_note")
            elif "30-Year Bond" in security_type:
                types_found.add("30y_bond")
            elif "TIPS" in security_type:
                types_found.add("tips")
            elif "FRN" in security_type:
                types_found.add("frn")

        expected = {"bill", "2y_note", "5y_note", "10y_note", "30y_bond", "tips", "frn"}
        assert types_found == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
