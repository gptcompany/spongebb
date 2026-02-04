"""Unit tests for anomaly detection (QA-04)."""

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from liquidity.validation.anomalies import (
    Anomaly,
    AnomalyDetector,
    AnomalyReport,
    AnomalyType,
)
from liquidity.validation.config import AnomalyConfig


class TestAnomalyDetector:
    """Tests for AnomalyDetector class."""

    @pytest.fixture
    def normal_df(self) -> pd.DataFrame:
        """Create DataFrame with normal data (no anomalies)."""
        dates = pd.date_range("2024-01-01", periods=100)
        np.random.seed(42)
        values = np.random.normal(100, 5, 100)  # Mean 100, std 5
        return pd.DataFrame({"date": dates, "value": values})

    @pytest.fixture
    def df_with_spike(self) -> pd.DataFrame:
        """Create DataFrame with a spike anomaly."""
        dates = pd.date_range("2024-01-01", periods=100)
        np.random.seed(42)
        values = np.random.normal(100, 5, 100)
        values[95] = 200  # Insert spike (~20 std devs above mean)
        return pd.DataFrame({"date": dates, "value": values})

    @pytest.fixture
    def df_with_drop(self) -> pd.DataFrame:
        """Create DataFrame with a drop anomaly."""
        dates = pd.date_range("2024-01-01", periods=100)
        np.random.seed(42)
        values = np.random.normal(100, 5, 100)
        values[95] = 0  # Insert drop (~20 std devs below mean)
        return pd.DataFrame({"date": dates, "value": values})

    @pytest.fixture
    def df_with_jump(self) -> pd.DataFrame:
        """Create DataFrame with a sudden jump."""
        dates = pd.date_range("2024-01-01", periods=100)
        values = [100] * 50 + [150] * 50  # 50% jump at midpoint
        return pd.DataFrame({"date": dates, "value": values})

    def test_detect_no_anomalies(self, normal_df: pd.DataFrame) -> None:
        """Test that no anomalies are detected in normal data."""
        detector = AnomalyDetector()

        anomalies = detector.detect(normal_df, "value")

        # Should have very few or no anomalies in random normal data
        assert len(anomalies) <= 2  # Allow for some statistical noise

    def test_detect_spike(self, df_with_spike: pd.DataFrame) -> None:
        """Test spike detection."""
        detector = AnomalyDetector()

        anomalies = detector.detect(df_with_spike, "value")

        # Should detect the spike at index 95
        spike_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.SPIKE]
        assert len(spike_anomalies) >= 1

        # Find the spike at our inserted position
        spike = next((a for a in spike_anomalies if a.value == 200), None)
        assert spike is not None
        assert spike.z_score > 3.0

    def test_detect_drop(self, df_with_drop: pd.DataFrame) -> None:
        """Test drop detection."""
        detector = AnomalyDetector()

        anomalies = detector.detect(df_with_drop, "value")

        # Should detect the drop
        drop_anomalies = [a for a in anomalies if a.anomaly_type == AnomalyType.DROP]
        assert len(drop_anomalies) >= 1

    def test_detect_jumps(self, df_with_jump: pd.DataFrame) -> None:
        """Test jump detection."""
        detector = AnomalyDetector()

        anomalies = detector.detect_jumps(df_with_jump, "value")

        assert len(anomalies) >= 1
        jump = anomalies[0]
        assert jump.anomaly_type == AnomalyType.JUMP
        assert jump.value == 150

    def test_detect_jumps_threshold(self) -> None:
        """Test jump detection with custom threshold."""
        dates = pd.date_range("2024-01-01", periods=10)
        values = [100, 105, 110, 115, 120, 200, 205, 210, 215, 220]  # 67% jump
        df = pd.DataFrame({"date": dates, "value": values})

        detector = AnomalyDetector()

        # Default 10% threshold - should detect
        anomalies = detector.detect_jumps(df, "value", jump_threshold_pct=10.0)
        assert len(anomalies) >= 1

        # 100% threshold - should not detect 67% jump
        anomalies = detector.detect_jumps(df, "value", jump_threshold_pct=100.0)
        assert len(anomalies) == 0

    def test_detect_all_combined(
        self, df_with_spike: pd.DataFrame, df_with_jump: pd.DataFrame
    ) -> None:
        """Test combined detection of all anomaly types."""
        detector = AnomalyDetector()

        anomalies = detector.detect_all(df_with_spike, "value")

        # Should detect at least the spike
        assert len(anomalies) >= 1

    def test_detect_empty_df(self) -> None:
        """Test handling of empty DataFrame."""
        detector = AnomalyDetector()
        df = pd.DataFrame()

        anomalies = detector.detect(df, "value")

        assert anomalies == []

    def test_detect_insufficient_data(self) -> None:
        """Test handling of insufficient data points."""
        detector = AnomalyDetector()
        dates = pd.date_range("2024-01-01", periods=10)
        df = pd.DataFrame({"date": dates, "value": range(10)})

        # Default min_data_points is 30
        anomalies = detector.detect(df, "value")

        assert anomalies == []

    def test_get_anomaly_report(self, df_with_spike: pd.DataFrame) -> None:
        """Test anomaly report generation."""
        detector = AnomalyDetector()

        report = detector.get_anomaly_report(df_with_spike, "value", "test_source")

        assert report.source == "test_source"
        assert report.metric == "value"
        assert report.total_points == 100
        assert len(report.anomalies) >= 1
        assert report.anomaly_rate >= 0

    def test_calculate_anomaly_score_no_anomalies(self) -> None:
        """Test anomaly score with no anomalies."""
        detector = AnomalyDetector()

        reports = [
            AnomalyReport(
                source="test", metric="value", anomalies=[], total_points=100, anomaly_rate=0.0
            )
        ]

        score = detector.calculate_anomaly_score(reports)

        assert score == 100.0

    def test_calculate_anomaly_score_with_anomalies(self) -> None:
        """Test anomaly score with some anomalies."""
        detector = AnomalyDetector()

        # 2.5% anomaly rate (half of 5% max acceptable)
        reports = [
            AnomalyReport(
                source="test",
                metric="value",
                anomalies=[],  # Anomalies list not used for score
                total_points=100,
                anomaly_rate=2.5,
            )
        ]

        score = detector.calculate_anomaly_score(reports)

        # 2.5% of 5% max = 50% penalty = 50% score
        assert score == pytest.approx(50.0)

    def test_calculate_anomaly_score_high_rate(self) -> None:
        """Test anomaly score with high anomaly rate."""
        detector = AnomalyDetector()

        # 10% anomaly rate (above 5% max)
        reports = [
            AnomalyReport(
                source="test",
                metric="value",
                anomalies=[],
                total_points=100,
                anomaly_rate=10.0,
            )
        ]

        score = detector.calculate_anomaly_score(reports)

        assert score == 0.0

    def test_custom_config(self) -> None:
        """Test using custom configuration."""
        config = AnomalyConfig(
            z_threshold=2.0,  # Lower threshold
            lookback_days=30,
            min_data_points=20,
        )
        detector = AnomalyDetector(config=config)

        # Create data with moderate deviation
        dates = pd.date_range("2024-01-01", periods=50)
        np.random.seed(42)
        values = np.random.normal(100, 5, 50)
        values[45] = 115  # 3 std dev above mean
        df = pd.DataFrame({"date": dates, "value": values})

        anomalies = detector.detect(df, "value")

        # Should detect with lower threshold
        assert len(anomalies) >= 1

    def test_anomaly_date_conversion(self, df_with_spike: pd.DataFrame) -> None:
        """Test that anomaly dates are properly converted."""
        detector = AnomalyDetector()

        anomalies = detector.detect(df_with_spike, "value")

        for anomaly in anomalies:
            assert isinstance(anomaly.date, date)

    def test_detect_with_zeros(self) -> None:
        """Test handling of zeros in data."""
        detector = AnomalyDetector()
        dates = pd.date_range("2024-01-01", periods=100)
        values = [0] * 50 + [100] * 50  # Half zeros
        df = pd.DataFrame({"date": dates, "value": values})

        # Should not crash
        anomalies = detector.detect_all(df, "value")

        assert isinstance(anomalies, list)

    def test_detect_with_nan(self) -> None:
        """Test handling of NaN values."""
        detector = AnomalyDetector()
        dates = pd.date_range("2024-01-01", periods=100)
        values = list(range(100))
        values[50] = np.nan
        df = pd.DataFrame({"date": dates, "value": values})

        # Should not crash
        anomalies = detector.detect_jumps(df, "value")

        assert isinstance(anomalies, list)

    def test_message_content(self, df_with_spike: pd.DataFrame) -> None:
        """Test that anomaly messages contain useful information."""
        detector = AnomalyDetector()

        anomalies = detector.detect(df_with_spike, "value")

        for anomaly in anomalies:
            assert "value" in anomaly.message.lower()
            assert anomaly.anomaly_type.value in anomaly.message.lower()
