"""Unit tests for cross-source validation (QA-03)."""

import pandas as pd
import pytest

from liquidity.validation.config import CrossValidationConfig, ValidationStatus
from liquidity.validation.cross_validation import (
    CrossValidator,
    ValidationResult,
)


class TestCrossValidator:
    """Tests for CrossValidator class."""

    def test_validate_matching_values(self) -> None:
        """Test validation of matching values."""
        validator = CrossValidator()

        result = validator.validate("FRED", "NY_Fed", "SOFR", 5.25, 5.25)

        assert result.status == ValidationStatus.MATCH
        assert result.difference_pct == 0.0
        assert result.source_a == "FRED"
        assert result.source_b == "NY_Fed"
        assert result.metric == "SOFR"

    def test_validate_within_tolerance(self) -> None:
        """Test validation within tolerance."""
        validator = CrossValidator()

        # Default tolerance is 1%
        result = validator.validate("A", "B", "metric", 100.0, 100.5)  # 0.5% diff

        assert result.status == ValidationStatus.MATCH
        assert result.difference_pct == pytest.approx(0.5)

    def test_validate_minor_difference(self) -> None:
        """Test validation with minor difference (1-5x tolerance)."""
        validator = CrossValidator()

        # Default tolerance is 1%, 3% diff should be MINOR_DIFF
        result = validator.validate("A", "B", "metric", 100.0, 103.0)

        assert result.status == ValidationStatus.MINOR_DIFF
        assert result.difference_pct == pytest.approx(3.0)

    def test_validate_major_difference(self) -> None:
        """Test validation with major difference (>5x tolerance)."""
        validator = CrossValidator()

        # Default tolerance is 1%, 10% diff should be MAJOR_DIFF
        result = validator.validate("A", "B", "metric", 100.0, 110.0)

        assert result.status == ValidationStatus.MAJOR_DIFF
        assert result.difference_pct == pytest.approx(10.0)

    def test_validate_zero_values(self) -> None:
        """Test validation with zero values."""
        validator = CrossValidator()

        # Both zero
        result = validator.validate("A", "B", "metric", 0.0, 0.0)
        assert result.status == ValidationStatus.MATCH
        assert result.difference_pct == 0.0

        # First zero, second non-zero
        result = validator.validate("A", "B", "metric", 0.0, 100.0)
        assert result.status == ValidationStatus.MAJOR_DIFF
        assert result.difference_pct == 100.0

    def test_validate_custom_tolerance(self) -> None:
        """Test validation with custom tolerance."""
        validator = CrossValidator()

        # 5% tolerance
        result = validator.validate(
            "A", "B", "metric", 100.0, 104.0, tolerance_pct=5.0
        )

        assert result.status == ValidationStatus.MATCH

    def test_validate_fed_data(self) -> None:
        """Test Fed data cross-validation."""
        validator = CrossValidator()

        # Tight tolerance for Fed data
        result = validator.validate_fed_data(fred_value=7500.0, direct_value=7502.5)

        assert result.source_a == "FRED"
        assert result.source_b == "FederalReserve"
        assert result.metric == "WALCL"
        assert result.status == ValidationStatus.MATCH

    def test_validate_fed_data_mismatch(self) -> None:
        """Test Fed data cross-validation with mismatch."""
        validator = CrossValidator()

        # More than 0.5% difference
        result = validator.validate_fed_data(fred_value=7500.0, direct_value=7600.0)

        assert result.status in [ValidationStatus.MINOR_DIFF, ValidationStatus.MAJOR_DIFF]

    def test_validate_sofr(self) -> None:
        """Test SOFR cross-validation."""
        validator = CrossValidator()

        # Very tight tolerance for rates
        result = validator.validate_sofr(nyfed_value=5.25, fred_value=5.25)

        assert result.source_a == "NY_Fed"
        assert result.source_b == "FRED"
        assert result.metric == "SOFR"
        assert result.status == ValidationStatus.MATCH

    def test_validate_ecb_data(self) -> None:
        """Test ECB data cross-validation."""
        validator = CrossValidator()

        result = validator.validate_ecb_data(ecb_sdw_value=8000.0, fred_value=7995.0)

        assert result.source_a == "ECB_SDW"
        assert result.source_b == "FRED"

    def test_validate_time_series_matching(self) -> None:
        """Test time series validation with matching data."""
        validator = CrossValidator()

        dates = pd.date_range("2024-01-01", periods=10)
        df_a = pd.DataFrame({"date": dates, "close": [100 + i for i in range(10)]})
        df_b = pd.DataFrame(
            {"date": dates, "close": [100 + i + 0.1 for i in range(10)]}
        )

        result = validator.validate_time_series(df_a, df_b, "close")

        assert result.total_points == 10
        assert result.status == ValidationStatus.MATCH

    def test_validate_time_series_divergent(self) -> None:
        """Test time series validation with divergent data."""
        validator = CrossValidator()

        dates = pd.date_range("2024-01-01", periods=10)
        df_a = pd.DataFrame({"date": dates, "close": [100] * 10})
        df_b = pd.DataFrame({"date": dates, "close": [150] * 10})  # 50% diff

        result = validator.validate_time_series(df_a, df_b, "close")

        assert result.total_points == 10
        assert result.matching_points == 0
        assert result.status == ValidationStatus.MAJOR_DIFF

    def test_validate_time_series_no_overlap(self) -> None:
        """Test time series validation with no overlapping dates."""
        validator = CrossValidator()

        df_a = pd.DataFrame(
            {"date": pd.date_range("2024-01-01", periods=5), "close": [100] * 5}
        )
        df_b = pd.DataFrame(
            {"date": pd.date_range("2024-02-01", periods=5), "close": [100] * 5}
        )

        result = validator.validate_time_series(df_a, df_b, "close")

        assert result.total_points == 0
        assert result.status == ValidationStatus.MAJOR_DIFF

    def test_calculate_validation_score_all_match(self) -> None:
        """Test validation score calculation with all matching."""
        validator = CrossValidator()

        results = [
            ValidationResult("A", "B", "m1", 100, 100, 0, ValidationStatus.MATCH, ""),
            ValidationResult("A", "B", "m2", 100, 100, 0, ValidationStatus.MATCH, ""),
            ValidationResult("A", "B", "m3", 100, 100, 0, ValidationStatus.MATCH, ""),
        ]

        score = validator.calculate_validation_score(results)

        assert score == 100.0

    def test_calculate_validation_score_mixed(self) -> None:
        """Test validation score calculation with mixed results."""
        validator = CrossValidator()

        results = [
            ValidationResult("A", "B", "m1", 100, 100, 0, ValidationStatus.MATCH, ""),
            ValidationResult("A", "B", "m2", 100, 103, 3, ValidationStatus.MINOR_DIFF, ""),
            ValidationResult("A", "B", "m3", 100, 120, 20, ValidationStatus.MAJOR_DIFF, ""),
        ]

        score = validator.calculate_validation_score(results)

        # 1 match (100) + 1 minor (50) + 1 major (0) = 150 / 3 = 50
        assert score == pytest.approx(50.0)

    def test_calculate_validation_score_empty(self) -> None:
        """Test validation score with no results."""
        validator = CrossValidator()

        score = validator.calculate_validation_score([])

        assert score == 100.0

    def test_custom_config(self) -> None:
        """Test using custom configuration."""
        config = CrossValidationConfig(
            tolerance_pct=5.0,  # 5% default tolerance
        )
        validator = CrossValidator(config=config)

        result = validator.validate("A", "B", "metric", 100.0, 104.0)

        assert result.status == ValidationStatus.MATCH

    def test_source_specific_tolerance(self) -> None:
        """Test that source-specific tolerances are used."""
        config = CrossValidationConfig(
            tolerance_pct=1.0,
            source_tolerances={
                "special_metric": 10.0,  # 10% tolerance for this metric
            },
        )
        validator = CrossValidator(config=config)

        result = validator.validate("A", "B", "special_metric", 100.0, 108.0)

        assert result.status == ValidationStatus.MATCH

    def test_message_content(self) -> None:
        """Test that validation messages contain useful information."""
        validator = CrossValidator()

        result = validator.validate("FRED", "NY_Fed", "SOFR", 5.25, 5.30)

        assert "SOFR" in result.message
        assert "FRED" in result.message or "5.25" in result.message
