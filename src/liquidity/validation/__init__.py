"""Data Quality Validation System.

Comprehensive validation for liquidity data:
- QA-01: Stale data detection (>24h for daily feeds, >48h for CBs)
- QA-02: Missing values and gaps detection
- QA-03: Cross-source validation (FRED vs direct API)
- QA-04: Anomaly flagging (>3 std dev moves, sudden jumps)
- QA-05: Hayes formula validation against historical values
- QA-06: Apps Script v3.4.1 cross-validation
- QA-07: Regression tests on data refresh

Example:
    from liquidity.validation import ValidationEngine

    # Create engine
    engine = ValidationEngine()

    # Run all validations
    report = engine.validate_all(
        data={"sofr": df_sofr, "fed": df_fed},
        last_updates={"sofr": ts_sofr, "fed": ts_fed},
    )

    print(f"Quality Score: {report.overall_score:.1f}%")
    print(f"Stale sources: {report.stale_sources}")

    # Run specific checks
    freshness = engine.freshness.check("sofr", last_update)
    gaps = engine.completeness.find_gaps(df, "my_source")
    anomalies = engine.anomaly.detect(df, "value")

    # Run regression tests
    suite_result = engine.regression.run_all_regression_tests(
        walcl=7500e9, tga=800e9, rrp=500e9,
        net_liquidity=6200e9,
    )
"""

from datetime import datetime

import pandas as pd

from .anomalies import Anomaly, AnomalyDetector, AnomalyReport, AnomalyType
from .completeness import (
    CompletenessChecker,
    CompletenessReport,
    GapInfo,
    GapSeverity,
    MissingValueReport,
)
from .config import (
    DEFAULT_CONFIG,
    AnomalyConfig,
    CompletenessConfig,
    CrossValidationConfig,
    FreshnessConfig,
    FreshnessStatus,
    QualityConfig,
    RegressionConfig,
    ValidationStatus,
)
from .cross_validation import (
    CrossValidator,
    TimeSeriesValidationResult,
    ValidationResult,
)
from .freshness import FreshnessChecker, FreshnessCheckResult
from .quality_score import QualityDetails, QualityReport, QualityScorer
from .regression import RegressionSuiteResult, RegressionTester, RegressionTestResult


class ValidationEngine:
    """Unified validation engine for data quality checks.

    Provides a single entry point for all validation functionality.

    Example:
        engine = ValidationEngine()

        # Run full validation
        report = engine.validate_all(data, last_updates)

        # Access individual checkers
        freshness_result = engine.freshness.check("sofr", last_update)
        gaps = engine.completeness.find_gaps(df, "source")
    """

    def __init__(self, config: QualityConfig | None = None) -> None:
        """Initialize the validation engine.

        Args:
            config: Quality configuration. Uses defaults if not provided.
        """
        self.config = config or DEFAULT_CONFIG

        # Initialize all checkers
        self.freshness = FreshnessChecker(self.config.freshness)
        self.completeness = CompletenessChecker(self.config.completeness)
        self.cross_validator = CrossValidator(self.config.cross_validation)
        self.anomaly = AnomalyDetector(self.config.anomaly)
        self.regression = RegressionTester(self.config.regression)

        # Quality scorer aggregates all checks
        self.scorer = QualityScorer(
            config=self.config,
            freshness_checker=self.freshness,
            completeness_checker=self.completeness,
            cross_validator=self.cross_validator,
            anomaly_detector=self.anomaly,
            regression_tester=self.regression,
        )

    def validate_all(
        self,
        data: dict[str, pd.DataFrame],
        last_updates: dict[str, datetime],
        value_columns: dict[str, str] | None = None,
        date_col: str = "date",
    ) -> QualityReport:
        """Run all validation checks and return quality report.

        Args:
            data: Mapping of source names to DataFrames.
            last_updates: Mapping of source names to last update timestamps.
            value_columns: Mapping of source names to value column names.
            date_col: Name of date column in DataFrames.

        Returns:
            QualityReport with overall score and detailed breakdowns.
        """
        return self.scorer.calculate_score(
            data=data,
            last_updates=last_updates,
            value_columns=value_columns,
            date_col=date_col,
        )

    def validate_all_detailed(
        self,
        data: dict[str, pd.DataFrame],
        last_updates: dict[str, datetime],
        cross_validation_results: list[ValidationResult] | None = None,
        regression_result: RegressionSuiteResult | None = None,
        value_columns: dict[str, str] | None = None,
        date_col: str = "date",
    ) -> tuple[QualityReport, QualityDetails]:
        """Run all validation checks with full detail reports.

        Args:
            data: Mapping of source names to DataFrames.
            last_updates: Mapping of source names to last update timestamps.
            cross_validation_results: Pre-computed cross-validation results.
            regression_result: Pre-computed regression test result.
            value_columns: Mapping of source names to value column names.
            date_col: Name of date column in DataFrames.

        Returns:
            Tuple of (QualityReport, QualityDetails).
        """
        return self.scorer.calculate_full_score(
            data=data,
            last_updates=last_updates,
            cross_validation_results=cross_validation_results,
            regression_result=regression_result,
            value_columns=value_columns,
            date_col=date_col,
        )

    def run_regression_suite(
        self,
        walcl: float | None = None,
        tga: float | None = None,
        rrp: float | None = None,
        net_liquidity: float | None = None,
        fed_usd: float | None = None,
        ecb_usd: float | None = None,
        boj_usd: float | None = None,
        pboc_usd: float | None = None,
        global_liquidity: float | None = None,
        stealth_qe: float | None = None,
        historical_date: str | None = None,
    ) -> RegressionSuiteResult:
        """Run regression test suite.

        Args:
            walcl: Fed Total Assets.
            tga: Treasury General Account.
            rrp: Reverse Repo.
            net_liquidity: Calculated Net Liquidity.
            fed_usd: Fed balance sheet in USD.
            ecb_usd: ECB balance sheet in USD.
            boj_usd: BoJ balance sheet in USD.
            pboc_usd: PBoC balance sheet in USD.
            global_liquidity: Calculated Global Liquidity.
            stealth_qe: Calculated Stealth QE score.
            historical_date: Date for historical comparison.

        Returns:
            RegressionSuiteResult with all test outcomes.
        """
        return self.regression.run_all_regression_tests(
            walcl=walcl,
            tga=tga,
            rrp=rrp,
            net_liquidity=net_liquidity,
            fed_usd=fed_usd,
            ecb_usd=ecb_usd,
            boj_usd=boj_usd,
            pboc_usd=pboc_usd,
            global_liquidity=global_liquidity,
            stealth_qe=stealth_qe,
            historical_date=historical_date,
        )

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
            min_score: Minimum acceptable score.

        Returns:
            True if quality score is above threshold.
        """
        return self.scorer.is_data_quality_acceptable(data, last_updates, min_score)


__all__ = [
    # Main engine
    "ValidationEngine",
    # Config
    "QualityConfig",
    "FreshnessConfig",
    "CompletenessConfig",
    "CrossValidationConfig",
    "AnomalyConfig",
    "RegressionConfig",
    "DEFAULT_CONFIG",
    # Enums
    "FreshnessStatus",
    "GapSeverity",
    "ValidationStatus",
    "AnomalyType",
    # Freshness
    "FreshnessChecker",
    "FreshnessCheckResult",
    # Completeness
    "CompletenessChecker",
    "CompletenessReport",
    "GapInfo",
    "MissingValueReport",
    # Cross-validation
    "CrossValidator",
    "ValidationResult",
    "TimeSeriesValidationResult",
    # Anomalies
    "AnomalyDetector",
    "Anomaly",
    "AnomalyReport",
    # Regression
    "RegressionTester",
    "RegressionTestResult",
    "RegressionSuiteResult",
    # Quality scoring
    "QualityScorer",
    "QualityReport",
    "QualityDetails",
]
