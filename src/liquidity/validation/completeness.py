"""QA-02: Gap detection and completeness checking for time series data.

Detects missing values and gaps in time series, accounting for weekends
and holidays.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from .config import DEFAULT_CONFIG, CompletenessConfig, GapSeverity

logger = logging.getLogger(__name__)


@dataclass
class GapInfo:
    """Information about a gap in time series data.

    Attributes:
        source: Data source identifier.
        start_date: Start of the gap (last valid date before gap).
        end_date: End of the gap (first valid date after gap).
        gap_days: Number of days in the gap.
        severity: Gap severity classification.
    """

    source: str
    start_date: date
    end_date: date
    gap_days: int
    severity: GapSeverity


@dataclass
class MissingValueReport:
    """Report of missing values in a DataFrame.

    Attributes:
        column: Column name.
        missing_count: Number of missing values.
        missing_pct: Percentage of missing values.
        total_rows: Total number of rows.
    """

    column: str
    missing_count: int
    missing_pct: float
    total_rows: int


@dataclass
class CompletenessReport:
    """Complete report of data completeness.

    Attributes:
        source: Data source identifier.
        gaps: List of detected gaps.
        missing_values: List of missing value reports per column.
        completeness_score: Overall completeness score (0-100).
        total_rows: Total rows in dataset.
        date_range: Tuple of (min_date, max_date).
    """

    source: str
    gaps: list[GapInfo]
    missing_values: list[MissingValueReport]
    completeness_score: float
    total_rows: int
    date_range: tuple[date, date] | None


class CompletenessChecker:
    """Check data completeness and detect gaps in time series.

    QA-02: System detects missing values and gaps in time series.

    Example:
        checker = CompletenessChecker()

        # Check for gaps
        gaps = checker.find_gaps(df, "my_source")
        for gap in gaps:
            print(f"Gap: {gap.start_date} to {gap.end_date} ({gap.severity})")

        # Check missing values
        missing = checker.check_missing_values(df)
        for col, pct in missing.items():
            print(f"{col}: {pct:.1f}% missing")

        # Get overall score
        score = checker.completeness_score(df)
    """

    def __init__(self, config: CompletenessConfig | None = None) -> None:
        """Initialize the completeness checker.

        Args:
            config: Completeness configuration. Uses default if not provided.
        """
        self.config = config or DEFAULT_CONFIG.completeness

    def find_gaps(
        self,
        df: pd.DataFrame,
        source: str = "unknown",
        date_col: str = "date",
        exclude_weekends: bool = True,
    ) -> list[GapInfo]:
        """Find gaps in time series data.

        Args:
            df: DataFrame with time series data.
            source: Source identifier for reporting.
            date_col: Name of the date column.
            exclude_weekends: Whether to exclude weekend gaps (Sat-Sun).

        Returns:
            List of GapInfo objects describing each gap found.
        """
        if df.empty or date_col not in df.columns:
            return []

        # Sort by date and get unique dates
        df_sorted = df.sort_values(date_col)
        dates = pd.to_datetime(df_sorted[date_col]).drop_duplicates().sort_values()

        if len(dates) < 2:
            return []

        gaps: list[GapInfo] = []

        for i in range(1, len(dates)):
            prev_date = dates.iloc[i - 1]
            curr_date = dates.iloc[i]
            delta = (curr_date - prev_date).days

            if delta > 1:
                # Check if it's just a weekend gap
                if exclude_weekends and self._is_weekend_gap(prev_date, curr_date):
                    continue

                # Check minimum severity threshold
                if delta < self.config.min_gap_severity_days:
                    continue

                severity = self._classify_gap(delta)
                gaps.append(
                    GapInfo(
                        source=source,
                        start_date=prev_date.date(),
                        end_date=curr_date.date(),
                        gap_days=delta,
                        severity=severity,
                    )
                )

        logger.debug("Found %d gaps in %s", len(gaps), source)
        return gaps

    def _is_weekend_gap(self, start: datetime, end: datetime) -> bool:
        """Check if gap is just a normal weekend.

        Args:
            start: Start of gap (should be Friday).
            end: End of gap (should be Sunday or Monday).

        Returns:
            True if gap is a normal weekend, False otherwise.
        """
        delta = (end - start).days

        # Friday to Monday (3 days) or Friday to Sunday (2 days)
        return (delta == 2 or delta == 3) and start.weekday() == 4

    def _classify_gap(self, days: int) -> GapSeverity:
        """Classify gap severity based on duration.

        Args:
            days: Number of days in the gap.

        Returns:
            GapSeverity classification.
        """
        minor_threshold = self.config.gap_severity_thresholds.get("minor", 3)
        major_threshold = self.config.gap_severity_thresholds.get("major", 7)

        if days <= minor_threshold:
            return GapSeverity.MINOR
        elif days <= major_threshold:
            return GapSeverity.MAJOR
        return GapSeverity.CRITICAL

    def check_missing_values(self, df: pd.DataFrame) -> dict[str, float]:
        """Check percentage of missing values per column.

        Args:
            df: DataFrame to check.

        Returns:
            Dictionary mapping column names to percentage of missing values.
        """
        if df.empty:
            return {}

        result = (df.isnull().sum() / len(df) * 100).to_dict()
        # Ensure keys are strings and values are floats
        return {str(k): float(v) for k, v in result.items()}

    def get_missing_value_reports(self, df: pd.DataFrame) -> list[MissingValueReport]:
        """Get detailed missing value reports per column.

        Args:
            df: DataFrame to check.

        Returns:
            List of MissingValueReport objects.
        """
        if df.empty:
            return []

        reports = []
        total_rows = len(df)

        for col in df.columns:
            missing_count = df[col].isnull().sum()
            missing_pct = (missing_count / total_rows) * 100 if total_rows > 0 else 0

            reports.append(
                MissingValueReport(
                    column=col,
                    missing_count=int(missing_count),
                    missing_pct=missing_pct,
                    total_rows=total_rows,
                )
            )

        return reports

    def completeness_score(self, df: pd.DataFrame) -> float:
        """Calculate overall completeness score (0-100).

        Score is based on percentage of non-missing values.

        Args:
            df: DataFrame to check.

        Returns:
            Completeness score between 0 and 100.
        """
        if df.empty:
            return 100.0  # Empty data = nothing missing

        total_cells = len(df) * len(df.columns)
        if total_cells == 0:
            return 100.0

        missing_cells = df.isnull().sum().sum()
        missing_pct = (missing_cells / total_cells) * 100

        return max(0, 100 - missing_pct)

    def get_completeness_report(
        self,
        df: pd.DataFrame,
        source: str = "unknown",
        date_col: str = "date",
    ) -> CompletenessReport:
        """Generate comprehensive completeness report.

        Args:
            df: DataFrame to analyze.
            source: Source identifier.
            date_col: Name of the date column.

        Returns:
            CompletenessReport with all completeness metrics.
        """
        gaps = self.find_gaps(df, source, date_col)
        missing_values = self.get_missing_value_reports(df)
        score = self.completeness_score(df)

        # Get date range
        date_range = None
        if not df.empty and date_col in df.columns:
            dates = pd.to_datetime(df[date_col])
            date_range = (dates.min().date(), dates.max().date())

        return CompletenessReport(
            source=source,
            gaps=gaps,
            missing_values=missing_values,
            completeness_score=score,
            total_rows=len(df),
            date_range=date_range,
        )

    def has_critical_gaps(
        self,
        df: pd.DataFrame,
        source: str = "unknown",
        date_col: str = "date",
    ) -> bool:
        """Check if DataFrame has any critical gaps.

        Args:
            df: DataFrame to check.
            source: Source identifier.
            date_col: Name of the date column.

        Returns:
            True if any critical gaps exist.
        """
        gaps = self.find_gaps(df, source, date_col)
        return any(g.severity == GapSeverity.CRITICAL for g in gaps)
