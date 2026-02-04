"""Unit tests for tax date calendar.

Run with: uv run pytest tests/unit/test_calendar/test_tax_dates.py -v
"""

from datetime import date

import pytest

from liquidity.calendar.base import EventType, ImpactLevel
from liquidity.calendar.tax_dates import (
    TAX_DATES_2026,
    TaxDateCalendar,
)


class TestTaxDates2026Data:
    """Tests for static tax date data."""

    def test_tax_dates_exist(self) -> None:
        """Test that tax date data exists."""
        assert len(TAX_DATES_2026) > 0

    def test_all_tax_dates_have_required_fields(self) -> None:
        """Test all tax dates have required fields."""
        for tax_date in TAX_DATES_2026:
            assert "date" in tax_date
            assert "title" in tax_date
            assert isinstance(tax_date["date"], date)
            assert isinstance(tax_date["title"], str)

    def test_tax_dates_are_in_2026(self) -> None:
        """Test all tax dates are in 2026."""
        for tax_date in TAX_DATES_2026:
            d = tax_date["date"]
            if isinstance(d, date):
                assert d.year == 2026

    def test_includes_april_15(self) -> None:
        """Test April 15 individual tax deadline is included."""
        april_dates = [
            t for t in TAX_DATES_2026
            if isinstance(t["date"], date) and t["date"] == date(2026, 4, 15)
        ]
        assert len(april_dates) == 1
        assert "Individual" in str(april_dates[0]["title"])

    def test_includes_quarterly_estimated_payments(self) -> None:
        """Test quarterly estimated tax payments are included."""
        quarterly_dates = [date(2026, 1, 15), date(2026, 6, 15), date(2026, 9, 15)]

        for qd in quarterly_dates:
            matching = [
                t for t in TAX_DATES_2026
                if isinstance(t["date"], date) and t["date"] == qd
            ]
            assert len(matching) > 0, f"Missing estimated tax date: {qd}"


class TestTaxDateCalendar:
    """Tests for TaxDateCalendar class."""

    @pytest.fixture
    def calendar(self) -> TaxDateCalendar:
        """Create a tax date calendar fixture."""
        return TaxDateCalendar(year=2026)

    def test_calendar_initializes(self, calendar: TaxDateCalendar) -> None:
        """Test calendar initializes without error."""
        assert calendar is not None

    def test_get_events_returns_sorted_list(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test get_events returns chronologically sorted events."""
        events = calendar.get_events(date(2026, 1, 1), date(2026, 12, 31))

        assert len(events) > 0
        dates = [e.date for e in events]
        assert dates == sorted(dates)

    def test_get_events_respects_date_range(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test get_events only returns events within range."""
        start = date(2026, 4, 1)
        end = date(2026, 4, 30)
        events = calendar.get_events(start, end)

        for event in events:
            assert start <= event.date <= end

    def test_get_tax_dates_only(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test get_tax_dates_only excludes period ends."""
        tax_events = calendar.get_tax_dates_only(date(2026, 1, 1), date(2026, 12, 31))

        for event in tax_events:
            assert event.event_type == EventType.TAX_DATE

    def test_get_quarter_ends(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test get_quarter_ends returns Q1-Q4 quarter ends."""
        quarter_ends = calendar.get_quarter_ends(date(2026, 1, 1), date(2026, 12, 31))

        # Should have 4 quarter ends
        assert len(quarter_ends) == 4

        for event in quarter_ends:
            assert event.event_type == EventType.QUARTER_END
            assert event.impact == ImpactLevel.HIGH

    def test_get_month_ends(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test get_month_ends returns non-quarter month ends."""
        month_ends = calendar.get_month_ends(date(2026, 1, 1), date(2026, 12, 31))

        # Should have 8 month ends (12 - 4 quarter ends)
        assert len(month_ends) == 8

        for event in month_ends:
            assert event.event_type == EventType.MONTH_END
            assert event.impact == ImpactLevel.MEDIUM

    def test_april_15_is_high_impact(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test April 15 is marked as high impact."""
        events = calendar.get_events(date(2026, 4, 15), date(2026, 4, 15))
        tax_events = [e for e in events if e.event_type == EventType.TAX_DATE]

        assert len(tax_events) == 1
        assert tax_events[0].impact == ImpactLevel.HIGH

    def test_is_high_liquidity_drain_day_true(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test is_high_liquidity_drain_day returns True for major tax days."""
        # April 15 is a major tax day
        assert calendar.is_high_liquidity_drain_day(date(2026, 4, 15)) is True

    def test_is_high_liquidity_drain_day_false(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test is_high_liquidity_drain_day returns False for non-tax days."""
        # Random day with no tax events
        assert calendar.is_high_liquidity_drain_day(date(2026, 7, 4)) is False

    def test_quarter_end_dates_are_correct(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test quarter end dates are last days of Q1-Q4."""
        quarter_ends = calendar.get_quarter_ends(date(2026, 1, 1), date(2026, 12, 31))

        expected_dates = [
            date(2026, 3, 31),   # Q1
            date(2026, 6, 30),   # Q2
            date(2026, 9, 30),   # Q3
            date(2026, 12, 31),  # Q4
        ]

        actual_dates = sorted([e.date for e in quarter_ends])
        assert actual_dates == expected_dates

    def test_month_end_dates_are_correct(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test month end dates are last days of non-quarter months."""
        month_ends = calendar.get_month_ends(date(2026, 1, 1), date(2026, 12, 31))

        expected_months = {1, 2, 4, 5, 7, 8, 10, 11}  # Non-quarter months
        actual_months = {e.date.month for e in month_ends}

        assert actual_months == expected_months


class TestTaxDateCalendarPeriodEnds:
    """Tests for period end date generation."""

    @pytest.fixture
    def calendar(self) -> TaxDateCalendar:
        """Create a tax date calendar fixture."""
        return TaxDateCalendar(year=2026)

    def test_all_months_have_period_end(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test all 12 months have a period end event."""
        all_events = calendar.get_events(date(2026, 1, 1), date(2026, 12, 31))
        period_ends = [
            e for e in all_events
            if e.event_type in (EventType.MONTH_END, EventType.QUARTER_END)
        ]

        # Should have 12 period ends (one per month)
        assert len(period_ends) == 12

        # Check all months covered
        months = {e.date.month for e in period_ends}
        assert months == set(range(1, 13))

    def test_february_end_is_correct(
        self, calendar: TaxDateCalendar
    ) -> None:
        """Test February end date handles non-leap year."""
        # 2026 is not a leap year
        events = calendar.get_events(date(2026, 2, 1), date(2026, 2, 28))
        feb_end = [
            e for e in events
            if e.event_type == EventType.MONTH_END
        ]

        assert len(feb_end) == 1
        assert feb_end[0].date == date(2026, 2, 28)


class TestTaxDateCalendarEdgeCases:
    """Edge case tests for tax date calendar."""

    @pytest.fixture
    def calendar(self) -> TaxDateCalendar:
        """Create a tax date calendar fixture."""
        return TaxDateCalendar(year=2026)

    def test_empty_date_range(self, calendar: TaxDateCalendar) -> None:
        """Test date range with no events returns empty list."""
        # Use date range before any tax dates
        events = calendar.get_events(date(2025, 1, 1), date(2025, 1, 2))
        assert events == []

    def test_single_day_range(self, calendar: TaxDateCalendar) -> None:
        """Test single day range works correctly."""
        events = calendar.get_events(date(2026, 4, 15), date(2026, 4, 15))

        for event in events:
            assert event.date == date(2026, 4, 15)

    def test_year_parameter(self) -> None:
        """Test calendar respects year parameter for period ends."""
        calendar_2026 = TaxDateCalendar(year=2026)
        events = calendar_2026.get_events(date(2026, 1, 1), date(2026, 12, 31))

        # Should have period ends for 2026
        period_ends = [
            e for e in events
            if e.event_type in (EventType.MONTH_END, EventType.QUARTER_END)
        ]
        for event in period_ends:
            assert event.date.year == 2026


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
