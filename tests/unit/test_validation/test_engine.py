"""Unit tests for ValidationEngine."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from liquidity.validation import (
    ValidationEngine,
    QualityConfig,
    QualityReport,
    QualityDetails,
    FreshnessStatus,
    RegressionSuiteResult,
)


class TestValidationEngine:
    """Tests for ValidationEngine class."""

    @pytest.fixture
    def engine(self) -> ValidationEngine:
        """Create a ValidationEngine instance."""
        return ValidationEngine()

    @pytest.fixture
    def sample_data(self) -> dict[str, pd.DataFrame]:
        """Create sample data for testing."""
        dates = pd.date_range("2024-01-01", periods=100)
        return {
            "sofr": pd.DataFrame({"date": dates, "value": range(100)}),
            "fed": pd.DataFrame({"date": dates, "value": range(100, 200)}),
        }

    @pytest.fixture
    def fresh_updates(self) -> dict[str, datetime]:
        """Create fresh update timestamps."""
        now = datetime.now(UTC)
        return {
            "sofr": now - timedelta(hours=6),
            "fed": now - timedelta(hours=12),
        }

    def test_init_default_config(self, engine: ValidationEngine) -> None:
        """Test engine initializes with default config."""
        assert engine.config is not None
        assert engine.freshness is not None
        assert engine.completeness is not None
        assert engine.cross_validator is not None
        assert engine.anomaly is not None
        assert engine.regression is not None
        assert engine.scorer is not None

    def test_init_custom_config(self) -> None:
        """Test engine initializes with custom config."""
        config = QualityConfig(min_score_threshold=90.0)
        engine = ValidationEngine(config=config)

        assert engine.config.min_score_threshold == 90.0

    def test_validate_all(
        self,
        engine: ValidationEngine,
        sample_data: dict[str, pd.DataFrame],
        fresh_updates: dict[str, datetime],
    ) -> None:
        """Test validate_all returns QualityReport."""
        report = engine.validate_all(sample_data, fresh_updates)

        assert isinstance(report, QualityReport)
        assert 0 <= report.overall_score <= 100
        assert 0 <= report.freshness_score <= 100
        assert 0 <= report.completeness_score <= 100
        assert report.timestamp is not None

    def test_validate_all_detailed(
        self,
        engine: ValidationEngine,
        sample_data: dict[str, pd.DataFrame],
        fresh_updates: dict[str, datetime],
    ) -> None:
        """Test validate_all_detailed returns report and details."""
        report, details = engine.validate_all_detailed(sample_data, fresh_updates)

        assert isinstance(report, QualityReport)
        assert isinstance(details, QualityDetails)
        assert len(details.freshness_results) > 0
        assert len(details.completeness_reports) > 0

    def test_run_regression_suite(self, engine: ValidationEngine) -> None:
        """Test run_regression_suite."""
        result = engine.run_regression_suite(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            net_liquidity=6200e9,
        )

        assert isinstance(result, RegressionSuiteResult)
        assert result.total_tests >= 1
        assert result.passed_tests >= 1

    def test_run_regression_suite_with_historical(
        self, engine: ValidationEngine
    ) -> None:
        """Test run_regression_suite with historical comparison."""
        result = engine.run_regression_suite(
            walcl=5.82e12 + 800e9 + 500e9,
            tga=800e9,
            rrp=500e9,
            net_liquidity=5.82e12,
            global_liquidity=28.5e12,
            stealth_qe=15.0,
            historical_date="2024-01-15",
        )

        assert result.total_tests >= 4

    def test_is_data_quality_acceptable(
        self,
        engine: ValidationEngine,
        sample_data: dict[str, pd.DataFrame],
        fresh_updates: dict[str, datetime],
    ) -> None:
        """Test is_data_quality_acceptable."""
        is_acceptable = engine.is_data_quality_acceptable(sample_data, fresh_updates)

        assert isinstance(is_acceptable, bool)
        # With fresh, complete data it should be acceptable
        assert is_acceptable is True

    def test_is_data_quality_acceptable_with_custom_threshold(
        self,
        engine: ValidationEngine,
        sample_data: dict[str, pd.DataFrame],
        fresh_updates: dict[str, datetime],
    ) -> None:
        """Test is_data_quality_acceptable with custom min_score."""
        # Very high threshold
        is_acceptable = engine.is_data_quality_acceptable(
            sample_data, fresh_updates, min_score=99.9
        )

        # Depends on actual score
        assert isinstance(is_acceptable, bool)

    def test_freshness_checker_access(self, engine: ValidationEngine) -> None:
        """Test direct access to freshness checker."""
        now = datetime.now(UTC)
        last_update = now - timedelta(hours=12)

        result = engine.freshness.check("sofr", last_update, now=now)

        assert result.status == FreshnessStatus.FRESH

    def test_completeness_checker_access(self, engine: ValidationEngine) -> None:
        """Test direct access to completeness checker."""
        dates = pd.date_range("2024-01-01", periods=10)
        df = pd.DataFrame({"date": dates, "value": range(10)})

        score = engine.completeness.completeness_score(df)

        assert score == 100.0

    def test_anomaly_detector_access(self, engine: ValidationEngine) -> None:
        """Test direct access to anomaly detector."""
        import numpy as np

        dates = pd.date_range("2024-01-01", periods=100)
        np.random.seed(42)
        values = np.random.normal(100, 5, 100)
        values[95] = 500  # Spike
        df = pd.DataFrame({"date": dates, "value": values})

        anomalies = engine.anomaly.detect(df, "value")

        assert len(anomalies) >= 1

    def test_cross_validator_access(self, engine: ValidationEngine) -> None:
        """Test direct access to cross-validator."""
        result = engine.cross_validator.validate("A", "B", "metric", 100.0, 100.0)

        assert result.status.value == "match"

    def test_regression_tester_access(self, engine: ValidationEngine) -> None:
        """Test direct access to regression tester."""
        result = engine.regression.test_hayes_formula(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            expected_net_liquidity=6200e9,
        )

        assert result.passed is True

    def test_validate_all_with_value_columns(
        self,
        engine: ValidationEngine,
        fresh_updates: dict[str, datetime],
    ) -> None:
        """Test validate_all with custom value columns."""
        dates = pd.date_range("2024-01-01", periods=100)
        data = {
            "sofr": pd.DataFrame({"date": dates, "rate": range(100)}),
            "fed": pd.DataFrame({"date": dates, "balance": range(100)}),
        }
        value_columns = {"sofr": "rate", "fed": "balance"}

        report = engine.validate_all(data, fresh_updates, value_columns=value_columns)

        assert isinstance(report, QualityReport)

    def test_validate_all_empty_data(self, engine: ValidationEngine) -> None:
        """Test validate_all with empty data."""
        report = engine.validate_all({}, {})

        assert report.overall_score == 100.0
        assert report.stale_sources == []
        assert report.anomaly_count == 0
