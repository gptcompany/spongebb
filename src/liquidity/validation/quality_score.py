"""Combined quality scoring for data quality validation.

Aggregates all validation checks into a comprehensive quality report.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from .anomalies import AnomalyDetector, AnomalyReport
from .completeness import CompletenessChecker, CompletenessReport
from .config import DEFAULT_CONFIG, FreshnessStatus, QualityConfig
from .cross_validation import CrossValidator, ValidationResult
from .freshness import FreshnessChecker, FreshnessCheckResult
from .regression import RegressionSuiteResult, RegressionTester

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Comprehensive data quality report.

    Attributes:
        overall_score: Combined quality score (0-100).
        freshness_score: Freshness component score (0-100).
        completeness_score: Completeness component score (0-100).
        validation_score: Cross-validation component score (0-100).
        anomaly_count: Total number of anomalies detected.
        stale_sources: List of stale data sources.
        critical_issues: List of critical issues requiring attention.
        timestamp: When the report was generated.
        details: Detailed sub-reports.
    """

    overall_score: float
    freshness_score: float
    completeness_score: float
    validation_score: float
    anomaly_count: int
    stale_sources: list[str]
    critical_issues: list[str]
    timestamp: datetime
    details: dict[str, list] = field(default_factory=dict)


@dataclass
class QualityDetails:
    """Detailed breakdown of quality metrics.

    Attributes:
        freshness_results: Individual freshness check results.
        completeness_reports: Completeness reports per source.
        validation_results: Cross-validation results.
        anomaly_reports: Anomaly detection reports.
        regression_result: Regression test suite result.
    """

    freshness_results: list[FreshnessCheckResult] = field(default_factory=list)
    completeness_reports: list[CompletenessReport] = field(default_factory=list)
    validation_results: list[ValidationResult] = field(default_factory=list)
    anomaly_reports: list[AnomalyReport] = field(default_factory=list)
    regression_result: RegressionSuiteResult | None = None


class QualityScorer:
    """Calculate comprehensive data quality scores.

    Aggregates freshness, completeness, cross-validation, and anomaly
    detection into a single quality score (0-100).

    Example:
        scorer = QualityScorer()

        # Calculate quality score
        report = scorer.calculate_score(
            data={"sofr": df_sofr, "fed": df_fed},
            last_updates={"sofr": datetime_sofr, "fed": datetime_fed},
        )

        print(f"Quality Score: {report.overall_score:.1f}%")
        print(f"Stale sources: {report.stale_sources}")
        print(f"Critical issues: {report.critical_issues}")
    """

    def __init__(
        self,
        config: QualityConfig | None = None,
        freshness_checker: FreshnessChecker | None = None,
        completeness_checker: CompletenessChecker | None = None,
        cross_validator: CrossValidator | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        regression_tester: RegressionTester | None = None,
    ) -> None:
        """Initialize the quality scorer.

        Args:
            config: Quality scoring configuration.
            freshness_checker: Custom freshness checker (creates default if None).
            completeness_checker: Custom completeness checker.
            cross_validator: Custom cross-validator.
            anomaly_detector: Custom anomaly detector.
            regression_tester: Custom regression tester.
        """
        self.config = config or DEFAULT_CONFIG
        self.freshness = freshness_checker or FreshnessChecker(self.config.freshness)
        self.completeness = completeness_checker or CompletenessChecker(self.config.completeness)
        self.validator = cross_validator or CrossValidator(self.config.cross_validation)
        self.anomaly = anomaly_detector or AnomalyDetector(self.config.anomaly)
        self.regression = regression_tester or RegressionTester(self.config.regression)

    def calculate_score(
        self,
        data: dict[str, pd.DataFrame],
        last_updates: dict[str, datetime],
        value_columns: dict[str, str] | None = None,
        date_col: str = "date",
    ) -> QualityReport:
        """Calculate comprehensive quality score.

        Args:
            data: Mapping of source names to DataFrames.
            last_updates: Mapping of source names to last update timestamps.
            value_columns: Mapping of source names to value column names.
                If None, defaults to "value" for all sources.
            date_col: Name of date column in DataFrames.

        Returns:
            QualityReport with overall score and detailed breakdowns.
        """
        if value_columns is None:
            value_columns = dict.fromkeys(data.keys(), "value")

        critical_issues: list[str] = []
        details: dict[str, list] = {
            "freshness": [],
            "completeness": [],
            "anomalies": [],
        }

        # 1. Freshness Score (0-100)
        freshness_results = self.freshness.check_all(last_updates)
        fresh_count = sum(
            1 for r in freshness_results.values() if r.status == FreshnessStatus.FRESH
        )
        freshness_score = (fresh_count / len(freshness_results) * 100) if freshness_results else 100

        stale_sources = [
            source
            for source, r in freshness_results.items()
            if r.status != FreshnessStatus.FRESH
        ]

        # Track critical freshness issues
        critical_freshness = [
            source
            for source, r in freshness_results.items()
            if r.status == FreshnessStatus.CRITICAL
        ]
        if critical_freshness:
            critical_issues.append(f"Critical stale data: {', '.join(critical_freshness)}")

        details["freshness"] = list(freshness_results.values())

        # 2. Completeness Score (0-100)
        completeness_scores: list[float] = []
        completeness_reports: list[CompletenessReport] = []

        for source, df in data.items():
            report = self.completeness.get_completeness_report(df, source, date_col)
            completeness_reports.append(report)
            completeness_scores.append(report.completeness_score)

            # Track critical gaps
            critical_gaps = [g for g in report.gaps if g.severity.value == "critical"]
            if critical_gaps:
                critical_issues.append(f"Critical gap in {source}: {len(critical_gaps)} gaps")

        completeness_score = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 100
        details["completeness"] = completeness_reports

        # 3. Anomaly Count
        anomaly_reports: list[AnomalyReport] = []
        total_anomalies = 0

        for source, df in data.items():
            value_col = value_columns.get(source, "value")
            if value_col in df.columns:
                report = self.anomaly.get_anomaly_report(df, value_col, source, date_col)
                anomaly_reports.append(report)
                total_anomalies += len(report.anomalies)

        details["anomalies"] = anomaly_reports

        # 4. Validation Score (default to 100 if no cross-validation data)
        # This would be populated from actual cross-validation runs
        validation_score = 100.0

        # 5. Calculate Overall Score (weighted average)
        weights = self.config.weights
        overall_score = (
            freshness_score * weights.get("freshness", 0.3)
            + completeness_score * weights.get("completeness", 0.4)
            + validation_score * weights.get("validation", 0.3)
        )

        # Check if below minimum threshold
        if overall_score < self.config.min_score_threshold:
            critical_issues.append(
                f"Overall quality score ({overall_score:.1f}) below threshold ({self.config.min_score_threshold})"
            )

        logger.info(
            "Quality score: %.1f (freshness=%.1f, completeness=%.1f, validation=%.1f)",
            overall_score,
            freshness_score,
            completeness_score,
            validation_score,
        )

        return QualityReport(
            overall_score=overall_score,
            freshness_score=freshness_score,
            completeness_score=completeness_score,
            validation_score=validation_score,
            anomaly_count=total_anomalies,
            stale_sources=stale_sources,
            critical_issues=critical_issues,
            timestamp=datetime.now(UTC),
            details=details,
        )

    def calculate_full_score(
        self,
        data: dict[str, pd.DataFrame],
        last_updates: dict[str, datetime],
        cross_validation_results: list[ValidationResult] | None = None,
        regression_result: RegressionSuiteResult | None = None,
        value_columns: dict[str, str] | None = None,
        date_col: str = "date",
    ) -> tuple[QualityReport, QualityDetails]:
        """Calculate comprehensive quality score with full details.

        Args:
            data: Mapping of source names to DataFrames.
            last_updates: Mapping of source names to last update timestamps.
            cross_validation_results: Results from cross-validation.
            regression_result: Result from regression test suite.
            value_columns: Mapping of source names to value column names.
            date_col: Name of date column in DataFrames.

        Returns:
            Tuple of (QualityReport, QualityDetails).
        """
        if value_columns is None:
            value_columns = dict.fromkeys(data.keys(), "value")

        critical_issues: list[str] = []

        # 1. Freshness
        freshness_results = self.freshness.check_all(last_updates)
        freshness_score = self.freshness.calculate_freshness_score(last_updates)

        stale_sources = [
            source
            for source, r in freshness_results.items()
            if r.status != FreshnessStatus.FRESH
        ]

        critical_freshness = [
            source
            for source, r in freshness_results.items()
            if r.status == FreshnessStatus.CRITICAL
        ]
        if critical_freshness:
            critical_issues.append(f"Critical stale: {', '.join(critical_freshness)}")

        # 2. Completeness
        completeness_reports: list[CompletenessReport] = []
        completeness_scores: list[float] = []

        for source, df in data.items():
            report = self.completeness.get_completeness_report(df, source, date_col)
            completeness_reports.append(report)
            completeness_scores.append(report.completeness_score)

        completeness_score = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 100

        # 3. Cross-validation
        if cross_validation_results:
            validation_score = self.validator.calculate_validation_score(cross_validation_results)
        else:
            validation_score = 100.0

        # 4. Anomalies
        anomaly_reports: list[AnomalyReport] = []
        total_anomalies = 0

        for source, df in data.items():
            value_col = value_columns.get(source, "value")
            if value_col in df.columns:
                report = self.anomaly.get_anomaly_report(df, value_col, source, date_col)
                anomaly_reports.append(report)
                total_anomalies += len(report.anomalies)

        # 5. Overall Score
        weights = self.config.weights
        overall_score = (
            freshness_score * weights.get("freshness", 0.3)
            + completeness_score * weights.get("completeness", 0.4)
            + validation_score * weights.get("validation", 0.3)
        )

        if overall_score < self.config.min_score_threshold:
            critical_issues.append(
                f"Quality score ({overall_score:.1f}) below threshold ({self.config.min_score_threshold})"
            )

        # Create detailed reports
        details = QualityDetails(
            freshness_results=list(freshness_results.values()),
            completeness_reports=completeness_reports,
            validation_results=cross_validation_results or [],
            anomaly_reports=anomaly_reports,
            regression_result=regression_result,
        )

        report = QualityReport(
            overall_score=overall_score,
            freshness_score=freshness_score,
            completeness_score=completeness_score,
            validation_score=validation_score,
            anomaly_count=total_anomalies,
            stale_sources=stale_sources,
            critical_issues=critical_issues,
            timestamp=datetime.now(UTC),
            details={
                "freshness": list(freshness_results.values()),
                "completeness": completeness_reports,
                "anomalies": anomaly_reports,
            },
        )

        return report, details

    def is_data_quality_acceptable(
        self,
        data: dict[str, pd.DataFrame],
        last_updates: dict[str, datetime],
        min_score: float | None = None,
    ) -> bool:
        """Quick check if data quality meets minimum threshold.

        Args:
            data: Mapping of source names to DataFrames.
            last_updates: Mapping of source names to last update timestamps.
            min_score: Minimum acceptable score (uses config default if None).

        Returns:
            True if quality score is above threshold.
        """
        min_threshold = min_score or self.config.min_score_threshold
        report = self.calculate_score(data, last_updates)
        return bool(report.overall_score >= min_threshold)
