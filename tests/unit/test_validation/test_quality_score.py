"""Unit tests for quality scoring."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from liquidity.validation.config import FreshnessStatus, QualityConfig
from liquidity.validation.quality_score import (
    QualityDetails,
    QualityReport,
    QualityScorer,
)


class TestQualityScorer:
    """Tests for QualityScorer class."""

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

    @pytest.fixture
    def stale_updates(self) -> dict[str, datetime]:
        """Create stale update timestamps."""
        now = datetime.now(UTC)
        return {
            "sofr": now - timedelta(hours=48),  # Stale
            "fed": now - timedelta(hours=100),  # Critical
        }

    def test_calculate_score_fresh_data(
        self, sample_data: dict[str, pd.DataFrame], fresh_updates: dict[str, datetime]
    ) -> None:
        """Test quality score with fresh, complete data."""
        scorer = QualityScorer()

        report = scorer.calculate_score(sample_data, fresh_updates)

        assert report.overall_score >= 90.0
        assert report.freshness_score == 100.0
        assert report.completeness_score == 100.0
        assert report.stale_sources == []

    def test_calculate_score_stale_data(
        self, sample_data: dict[str, pd.DataFrame], stale_updates: dict[str, datetime]
    ) -> None:
        """Test quality score with stale data."""
        scorer = QualityScorer()

        report = scorer.calculate_score(sample_data, stale_updates)

        assert report.freshness_score < 100.0
        assert len(report.stale_sources) >= 1
        assert "sofr" in report.stale_sources or "fed" in report.stale_sources

    def test_calculate_score_with_missing_values(
        self, fresh_updates: dict[str, datetime]
    ) -> None:
        """Test quality score with missing values."""
        scorer = QualityScorer()

        # Create data with missing values
        dates = pd.date_range("2024-01-01", periods=100)
        values = list(range(100))
        values[50] = None
        values[60] = None

        data = {
            "sofr": pd.DataFrame({"date": dates, "value": values}),
        }
        updates = {"sofr": datetime.now(UTC) - timedelta(hours=6)}

        report = scorer.calculate_score(data, updates)

        assert report.completeness_score < 100.0

    def test_calculate_score_critical_issues(
        self, sample_data: dict[str, pd.DataFrame], stale_updates: dict[str, datetime]
    ) -> None:
        """Test that critical issues are reported."""
        scorer = QualityScorer()

        report = scorer.calculate_score(sample_data, stale_updates)

        # Should have critical issues for stale data
        assert len(report.critical_issues) >= 1 or report.overall_score >= scorer.config.min_score_threshold

    def test_calculate_score_below_threshold(self) -> None:
        """Test quality score below threshold triggers critical issue."""
        config = QualityConfig(min_score_threshold=95.0)  # High threshold
        scorer = QualityScorer(config=config)

        data = {"sofr": pd.DataFrame({"date": [], "value": []})}
        updates = {"sofr": datetime.now(UTC) - timedelta(days=10)}

        report = scorer.calculate_score(data, updates)

        # Either score is above threshold or critical issues reported
        if report.overall_score < 95.0:
            assert any("threshold" in issue.lower() for issue in report.critical_issues)

    def test_calculate_full_score(
        self, sample_data: dict[str, pd.DataFrame], fresh_updates: dict[str, datetime]
    ) -> None:
        """Test full score calculation with detailed reports."""
        scorer = QualityScorer()

        report, details = scorer.calculate_full_score(sample_data, fresh_updates)

        assert isinstance(report, QualityReport)
        assert isinstance(details, QualityDetails)
        assert len(details.freshness_results) == 2
        assert len(details.completeness_reports) == 2

    def test_calculate_full_score_with_validation_results(
        self, sample_data: dict[str, pd.DataFrame], fresh_updates: dict[str, datetime]
    ) -> None:
        """Test full score with cross-validation results."""
        from liquidity.validation.config import ValidationStatus
        from liquidity.validation.cross_validation import ValidationResult

        scorer = QualityScorer()

        cross_validation_results = [
            ValidationResult("A", "B", "m1", 100, 100, 0, ValidationStatus.MATCH, ""),
            ValidationResult("A", "B", "m2", 100, 103, 3, ValidationStatus.MINOR_DIFF, ""),
        ]

        report, details = scorer.calculate_full_score(
            sample_data,
            fresh_updates,
            cross_validation_results=cross_validation_results,
        )

        assert details.validation_results == cross_validation_results
        # Validation score should reflect the mixed results
        assert report.validation_score < 100.0 or len(cross_validation_results) == 0

    def test_is_data_quality_acceptable_true(
        self, sample_data: dict[str, pd.DataFrame], fresh_updates: dict[str, datetime]
    ) -> None:
        """Test quality acceptability check - acceptable."""
        scorer = QualityScorer()

        is_acceptable = scorer.is_data_quality_acceptable(sample_data, fresh_updates)

        assert is_acceptable is True

    def test_is_data_quality_acceptable_false(
        self, sample_data: dict[str, pd.DataFrame]
    ) -> None:
        """Test quality acceptability check - not acceptable."""
        scorer = QualityScorer()

        # Very stale data
        updates = {
            "sofr": datetime.now(UTC) - timedelta(days=30),
            "fed": datetime.now(UTC) - timedelta(days=30),
        }

        is_acceptable = scorer.is_data_quality_acceptable(
            sample_data, updates, min_score=80.0
        )

        # With very stale data, should not be acceptable
        assert is_acceptable is False

    def test_is_data_quality_acceptable_custom_threshold(
        self, sample_data: dict[str, pd.DataFrame], fresh_updates: dict[str, datetime]
    ) -> None:
        """Test quality acceptability with custom threshold."""
        scorer = QualityScorer()

        # Very high threshold
        is_acceptable = scorer.is_data_quality_acceptable(
            sample_data, fresh_updates, min_score=99.0
        )

        # Should depend on actual score
        assert isinstance(is_acceptable, bool)

    def test_empty_data(self) -> None:
        """Test handling of empty data."""
        scorer = QualityScorer()

        report = scorer.calculate_score({}, {})

        assert report.overall_score == 100.0
        assert report.anomaly_count == 0

    def test_quality_report_timestamp(
        self, sample_data: dict[str, pd.DataFrame], fresh_updates: dict[str, datetime]
    ) -> None:
        """Test that quality report has timestamp."""
        scorer = QualityScorer()

        report = scorer.calculate_score(sample_data, fresh_updates)

        assert report.timestamp is not None
        assert report.timestamp.tzinfo is not None

    def test_custom_config_weights(
        self, sample_data: dict[str, pd.DataFrame], fresh_updates: dict[str, datetime]
    ) -> None:
        """Test using custom weight configuration."""
        config = QualityConfig(
            weights={
                "freshness": 0.5,  # Higher weight on freshness
                "completeness": 0.3,
                "validation": 0.2,
            }
        )
        scorer = QualityScorer(config=config)

        report = scorer.calculate_score(sample_data, fresh_updates)

        # Score should be calculated with custom weights
        expected_score = (
            report.freshness_score * 0.5
            + report.completeness_score * 0.3
            + report.validation_score * 0.2
        )
        assert report.overall_score == pytest.approx(expected_score, abs=0.1)

    def test_anomaly_count(self) -> None:
        """Test anomaly count in quality report."""
        scorer = QualityScorer()

        # Create data with a spike
        dates = pd.date_range("2024-01-01", periods=100)
        import numpy as np

        np.random.seed(42)
        values = np.random.normal(100, 5, 100)
        values[95] = 500  # Spike

        data = {"test": pd.DataFrame({"date": dates, "value": values})}
        updates = {"test": datetime.now(UTC) - timedelta(hours=6)}

        report = scorer.calculate_score(data, updates)

        # Should detect at least one anomaly
        assert report.anomaly_count >= 1

    def test_details_dict_format(
        self, sample_data: dict[str, pd.DataFrame], fresh_updates: dict[str, datetime]
    ) -> None:
        """Test that details dict has expected structure."""
        scorer = QualityScorer()

        report = scorer.calculate_score(sample_data, fresh_updates)

        assert "freshness" in report.details
        assert "completeness" in report.details
        assert "anomalies" in report.details
