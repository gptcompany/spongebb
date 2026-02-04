"""Unit tests for completeness validation (QA-02)."""

from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from liquidity.validation.completeness import (
    CompletenessChecker,
    CompletenessReport,
    GapInfo,
    GapSeverity,
    MissingValueReport,
)
from liquidity.validation.config import CompletenessConfig


class TestCompletenessChecker:
    """Tests for CompletenessChecker class."""

    @pytest.fixture
    def sample_df(self) -> pd.DataFrame:
        """Create a sample DataFrame with dates."""
        dates = pd.date_range(start="2024-01-01", end="2024-01-10", freq="D")
        return pd.DataFrame(
            {
                "date": dates,
                "value": range(len(dates)),
            }
        )

    @pytest.fixture
    def df_with_gaps(self) -> pd.DataFrame:
        """Create a DataFrame with gaps in dates."""
        # Create dates with a gap from Jan 3 to Jan 8 (5 day gap)
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            # Gap here
            datetime(2024, 1, 8),
            datetime(2024, 1, 9),
            datetime(2024, 1, 10),
        ]
        return pd.DataFrame(
            {
                "date": dates,
                "value": range(len(dates)),
            }
        )

    @pytest.fixture
    def df_with_missing_values(self) -> pd.DataFrame:
        """Create a DataFrame with missing values."""
        dates = pd.date_range(start="2024-01-01", end="2024-01-10", freq="D")
        values = list(range(10))
        values[3] = None  # Missing value
        values[7] = None  # Missing value
        return pd.DataFrame(
            {
                "date": dates,
                "value": values,
                "other": [1, 2, None, 4, 5, None, 7, 8, 9, 10],
            }
        )

    def test_find_gaps_no_gaps(self, sample_df: pd.DataFrame) -> None:
        """Test that no gaps are found in continuous data."""
        checker = CompletenessChecker()

        gaps = checker.find_gaps(sample_df, "test_source")

        assert len(gaps) == 0

    def test_find_gaps_with_gap(self, df_with_gaps: pd.DataFrame) -> None:
        """Test that gaps are detected correctly."""
        checker = CompletenessChecker()

        gaps = checker.find_gaps(df_with_gaps, "test_source")

        assert len(gaps) == 1
        assert gaps[0].gap_days == 5
        assert gaps[0].source == "test_source"
        assert gaps[0].start_date == date(2024, 1, 3)
        assert gaps[0].end_date == date(2024, 1, 8)

    def test_find_gaps_weekend_excluded(self) -> None:
        """Test that weekend gaps are excluded by default."""
        # Friday to Monday (3-day gap, but weekend)
        dates = [
            datetime(2024, 1, 5),  # Friday
            datetime(2024, 1, 8),  # Monday
        ]
        df = pd.DataFrame({"date": dates, "value": [1, 2]})
        checker = CompletenessChecker()

        gaps = checker.find_gaps(df, "test_source", exclude_weekends=True)

        assert len(gaps) == 0

    def test_find_gaps_weekend_included(self) -> None:
        """Test that weekend gaps are included when configured."""
        # Friday to Monday (3-day gap)
        dates = [
            datetime(2024, 1, 5),  # Friday
            datetime(2024, 1, 8),  # Monday
        ]
        df = pd.DataFrame({"date": dates, "value": [1, 2]})
        checker = CompletenessChecker()

        gaps = checker.find_gaps(df, "test_source", exclude_weekends=False)

        assert len(gaps) == 1

    def test_gap_severity_minor(self) -> None:
        """Test that minor gaps are classified correctly."""
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 4),  # 3 day gap
        ]
        df = pd.DataFrame({"date": dates, "value": [1, 2]})
        checker = CompletenessChecker()

        gaps = checker.find_gaps(df, "test_source")

        assert len(gaps) == 1
        assert gaps[0].severity == GapSeverity.MINOR

    def test_gap_severity_major(self) -> None:
        """Test that major gaps are classified correctly."""
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 7),  # 6 day gap
        ]
        df = pd.DataFrame({"date": dates, "value": [1, 2]})
        checker = CompletenessChecker()

        gaps = checker.find_gaps(df, "test_source")

        assert len(gaps) == 1
        assert gaps[0].severity == GapSeverity.MAJOR

    def test_gap_severity_critical(self) -> None:
        """Test that critical gaps are classified correctly."""
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 15),  # 14 day gap
        ]
        df = pd.DataFrame({"date": dates, "value": [1, 2]})
        checker = CompletenessChecker()

        gaps = checker.find_gaps(df, "test_source")

        assert len(gaps) == 1
        assert gaps[0].severity == GapSeverity.CRITICAL

    def test_check_missing_values(self, df_with_missing_values: pd.DataFrame) -> None:
        """Test missing value detection."""
        checker = CompletenessChecker()

        missing = checker.check_missing_values(df_with_missing_values)

        assert "value" in missing
        assert missing["value"] == pytest.approx(20.0)  # 2/10 = 20%
        assert missing["other"] == pytest.approx(20.0)

    def test_check_missing_values_empty_df(self) -> None:
        """Test missing value detection on empty DataFrame."""
        checker = CompletenessChecker()
        df = pd.DataFrame()

        missing = checker.check_missing_values(df)

        assert missing == {}

    def test_get_missing_value_reports(self, df_with_missing_values: pd.DataFrame) -> None:
        """Test detailed missing value reports."""
        checker = CompletenessChecker()

        reports = checker.get_missing_value_reports(df_with_missing_values)

        assert len(reports) == 3  # date, value, other columns
        value_report = next(r for r in reports if r.column == "value")
        assert value_report.missing_count == 2
        assert value_report.missing_pct == pytest.approx(20.0)
        assert value_report.total_rows == 10

    def test_completeness_score_full(self, sample_df: pd.DataFrame) -> None:
        """Test completeness score for complete data."""
        checker = CompletenessChecker()

        score = checker.completeness_score(sample_df)

        assert score == 100.0

    def test_completeness_score_with_missing(
        self, df_with_missing_values: pd.DataFrame
    ) -> None:
        """Test completeness score with missing values."""
        checker = CompletenessChecker()

        score = checker.completeness_score(df_with_missing_values)

        # 4 missing out of 30 cells = 13.33% missing = 86.67% complete
        assert score == pytest.approx(86.67, abs=0.1)

    def test_completeness_score_empty_df(self) -> None:
        """Test completeness score for empty DataFrame."""
        checker = CompletenessChecker()
        df = pd.DataFrame()

        score = checker.completeness_score(df)

        assert score == 100.0

    def test_get_completeness_report(self, df_with_gaps: pd.DataFrame) -> None:
        """Test comprehensive completeness report."""
        checker = CompletenessChecker()

        report = checker.get_completeness_report(df_with_gaps, "test_source")

        assert report.source == "test_source"
        assert len(report.gaps) == 1
        assert report.total_rows == 6
        assert report.date_range is not None
        assert report.date_range[0] == date(2024, 1, 1)
        assert report.date_range[1] == date(2024, 1, 10)

    def test_has_critical_gaps_true(self) -> None:
        """Test detecting critical gaps."""
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 15),  # 14 day gap = critical
        ]
        df = pd.DataFrame({"date": dates, "value": [1, 2]})
        checker = CompletenessChecker()

        has_critical = checker.has_critical_gaps(df, "test_source")

        assert has_critical is True

    def test_has_critical_gaps_false(self, df_with_gaps: pd.DataFrame) -> None:
        """Test that non-critical gaps return False."""
        checker = CompletenessChecker()

        has_critical = checker.has_critical_gaps(df_with_gaps, "test_source")

        # 5 day gap is MAJOR, not CRITICAL
        assert has_critical is False

    def test_empty_dataframe(self) -> None:
        """Test handling of empty DataFrame."""
        checker = CompletenessChecker()
        df = pd.DataFrame()

        gaps = checker.find_gaps(df, "test_source")
        reports = checker.get_missing_value_reports(df)

        assert gaps == []
        assert reports == []

    def test_custom_config(self) -> None:
        """Test using custom configuration."""
        config = CompletenessConfig(
            min_gap_severity_days=5,  # Only report gaps > 5 days
        )
        checker = CompletenessChecker(config=config)

        # 3 day gap should not be reported
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 4),
        ]
        df = pd.DataFrame({"date": dates, "value": [1, 2]})

        gaps = checker.find_gaps(df, "test_source")

        assert len(gaps) == 0
