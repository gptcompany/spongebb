"""QA-03: Cross-source validation for data quality.

Validates data consistency between different sources (e.g., FRED vs direct API).
"""

import logging
from dataclasses import dataclass

import pandas as pd

from .config import DEFAULT_CONFIG, CrossValidationConfig, ValidationStatus

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of comparing values from two sources.

    Attributes:
        source_a: First data source identifier.
        source_b: Second data source identifier.
        metric: Name of the metric being compared.
        value_a: Value from source A.
        value_b: Value from source B.
        difference_pct: Percentage difference between values.
        status: Validation status (MATCH, MINOR_DIFF, MAJOR_DIFF).
        message: Human-readable description.
    """

    source_a: str
    source_b: str
    metric: str
    value_a: float
    value_b: float
    difference_pct: float
    status: ValidationStatus
    message: str


@dataclass
class TimeSeriesValidationResult:
    """Result of comparing time series from two sources.

    Attributes:
        source_a: First data source identifier.
        source_b: Second data source identifier.
        metric: Name of the metric being compared.
        total_points: Total number of comparison points.
        matching_points: Number of points within tolerance.
        avg_difference_pct: Average percentage difference.
        max_difference_pct: Maximum percentage difference.
        status: Overall validation status.
    """

    source_a: str
    source_b: str
    metric: str
    total_points: int
    matching_points: int
    avg_difference_pct: float
    max_difference_pct: float
    status: ValidationStatus


class CrossValidator:
    """Cross-validate data between different sources.

    QA-03: System cross-validates data between sources (FRED vs direct API).

    Example:
        validator = CrossValidator()

        # Compare single values
        result = validator.validate("FRED", "NY_Fed", "SOFR", 5.25, 5.26)
        print(f"Status: {result.status}")  # MATCH

        # Compare Fed data specifically
        result = validator.validate_fed_data(fred_walcl=7500, direct_walcl=7502)

        # Compare time series
        result = validator.validate_time_series(df_fred, df_direct, "close")
    """

    def __init__(self, config: CrossValidationConfig | None = None) -> None:
        """Initialize the cross-validator.

        Args:
            config: Cross-validation configuration. Uses default if not provided.
        """
        self.config = config or DEFAULT_CONFIG.cross_validation

    def validate(
        self,
        source_a: str,
        source_b: str,
        metric: str,
        value_a: float,
        value_b: float,
        tolerance_pct: float | None = None,
    ) -> ValidationResult:
        """Compare values from two sources.

        Args:
            source_a: First source identifier.
            source_b: Second source identifier.
            metric: Metric name being compared.
            value_a: Value from source A.
            value_b: Value from source B.
            tolerance_pct: Custom tolerance percentage. Uses config default if None.

        Returns:
            ValidationResult with comparison details.
        """
        # Determine tolerance
        if tolerance_pct is None:
            tolerance_pct = self.config.source_tolerances.get(
                metric.lower(), self.config.tolerance_pct
            )

        # Calculate difference
        if value_a == 0 and value_b == 0:
            diff_pct = 0.0
        elif value_a == 0:
            diff_pct = 100.0
        else:
            diff_pct = abs(value_a - value_b) / abs(value_a) * 100

        # Determine status
        if diff_pct <= tolerance_pct:
            status = ValidationStatus.MATCH
            message = (
                f"{metric}: MATCH - {source_a}={value_a:.4f}, "
                f"{source_b}={value_b:.4f} (diff={diff_pct:.3f}%)"
            )
        elif diff_pct <= tolerance_pct * 5:
            status = ValidationStatus.MINOR_DIFF
            message = (
                f"{metric}: MINOR DIFF - {source_a}={value_a:.4f}, "
                f"{source_b}={value_b:.4f} (diff={diff_pct:.3f}%)"
            )
        else:
            status = ValidationStatus.MAJOR_DIFF
            message = (
                f"{metric}: MAJOR DIFF - {source_a}={value_a:.4f}, "
                f"{source_b}={value_b:.4f} (diff={diff_pct:.3f}%)"
            )

        logger.debug(
            "Cross-validation %s: %s (diff=%.3f%%, tolerance=%.1f%%)",
            metric,
            status.value,
            diff_pct,
            tolerance_pct,
        )

        return ValidationResult(
            source_a=source_a,
            source_b=source_b,
            metric=metric,
            value_a=value_a,
            value_b=value_b,
            difference_pct=diff_pct,
            status=status,
            message=message,
        )

    def validate_fed_data(
        self,
        fred_value: float,
        direct_value: float,
        metric: str = "WALCL",
    ) -> ValidationResult:
        """Cross-validate Fed balance sheet data.

        Args:
            fred_value: Value from FRED API.
            direct_value: Value from direct Federal Reserve API.
            metric: Metric name (default: WALCL).

        Returns:
            ValidationResult for Fed data comparison.
        """
        return self.validate(
            source_a="FRED",
            source_b="FederalReserve",
            metric=metric,
            value_a=fred_value,
            value_b=direct_value,
            tolerance_pct=0.5,  # Tight tolerance for Fed data
        )

    def validate_sofr(
        self,
        nyfed_value: float,
        fred_value: float,
    ) -> ValidationResult:
        """Cross-validate SOFR rate.

        Args:
            nyfed_value: Value from NY Fed API.
            fred_value: Value from FRED API.

        Returns:
            ValidationResult for SOFR comparison.
        """
        return self.validate(
            source_a="NY_Fed",
            source_b="FRED",
            metric="SOFR",
            value_a=nyfed_value,
            value_b=fred_value,
            tolerance_pct=0.01,  # Very tight for rates
        )

    def validate_ecb_data(
        self,
        ecb_sdw_value: float,
        fred_value: float,
        metric: str = "ECB_BALANCE_SHEET",
    ) -> ValidationResult:
        """Cross-validate ECB balance sheet data.

        Args:
            ecb_sdw_value: Value from ECB Statistical Data Warehouse.
            fred_value: Value from FRED (if available).
            metric: Metric name.

        Returns:
            ValidationResult for ECB data comparison.
        """
        return self.validate(
            source_a="ECB_SDW",
            source_b="FRED",
            metric=metric,
            value_a=ecb_sdw_value,
            value_b=fred_value,
            tolerance_pct=1.0,  # Slightly looser for currency conversion differences
        )

    def validate_time_series(
        self,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        value_col: str,
        date_col: str = "date",
        tolerance_pct: float | None = None,
    ) -> TimeSeriesValidationResult:
        """Compare time series data from two sources.

        Args:
            df_a: DataFrame from source A.
            df_b: DataFrame from source B.
            value_col: Column name containing values to compare.
            date_col: Column name containing dates.
            tolerance_pct: Tolerance for matching.

        Returns:
            TimeSeriesValidationResult with aggregate comparison metrics.
        """
        if tolerance_pct is None:
            tolerance_pct = self.config.tolerance_pct

        # Merge on date
        df_a_clean = df_a[[date_col, value_col]].copy()
        df_b_clean = df_b[[date_col, value_col]].copy()

        df_a_clean.columns = [date_col, "value_a"]
        df_b_clean.columns = [date_col, "value_b"]

        merged = pd.merge(df_a_clean, df_b_clean, on=date_col, how="inner")

        if merged.empty:
            return TimeSeriesValidationResult(
                source_a="source_a",
                source_b="source_b",
                metric=value_col,
                total_points=0,
                matching_points=0,
                avg_difference_pct=0.0,
                max_difference_pct=0.0,
                status=ValidationStatus.MAJOR_DIFF,
            )

        # Calculate differences
        merged["diff_pct"] = abs(merged["value_a"] - merged["value_b"]) / abs(
            merged["value_a"].replace(0, 1)
        ) * 100

        total_points = len(merged)
        matching_points = (merged["diff_pct"] <= tolerance_pct).sum()
        avg_diff = merged["diff_pct"].mean()
        max_diff = merged["diff_pct"].max()

        # Determine overall status
        match_ratio = matching_points / total_points
        if match_ratio >= 0.95:
            status = ValidationStatus.MATCH
        elif match_ratio >= 0.80:
            status = ValidationStatus.MINOR_DIFF
        else:
            status = ValidationStatus.MAJOR_DIFF

        return TimeSeriesValidationResult(
            source_a="source_a",
            source_b="source_b",
            metric=value_col,
            total_points=total_points,
            matching_points=int(matching_points),
            avg_difference_pct=avg_diff,
            max_difference_pct=max_diff,
            status=status,
        )

    def calculate_validation_score(
        self,
        results: list[ValidationResult],
    ) -> float:
        """Calculate overall validation score from multiple results.

        Args:
            results: List of validation results.

        Returns:
            Validation score between 0 and 100.
        """
        if not results:
            return 100.0

        match_count = sum(1 for r in results if r.status == ValidationStatus.MATCH)
        minor_count = sum(1 for r in results if r.status == ValidationStatus.MINOR_DIFF)

        # MATCH = 100%, MINOR_DIFF = 50%, MAJOR_DIFF = 0%
        score = (match_count * 100 + minor_count * 50) / len(results)
        return score
