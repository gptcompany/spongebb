"""QA-04: Anomaly detection for data quality validation.

Detects anomalies in time series data using z-score and jump detection methods.
Flags >3 standard deviation moves and sudden value jumps.
"""

import logging
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from .config import DEFAULT_CONFIG, AnomalyConfig, AnomalyType

logger = logging.getLogger(__name__)


@dataclass
class Anomaly:
    """Detected anomaly in time series data.

    Attributes:
        date: Date of the anomaly.
        metric: Name of the metric.
        value: Actual value at the anomaly point.
        z_score: Z-score (for statistical anomalies) or relative change.
        anomaly_type: Type of anomaly (SPIKE, DROP, JUMP, OUTLIER).
        message: Human-readable description.
    """

    date: date
    metric: str
    value: float
    z_score: float
    anomaly_type: AnomalyType
    message: str


@dataclass
class AnomalyReport:
    """Report of all anomalies detected in a dataset.

    Attributes:
        source: Data source identifier.
        metric: Metric analyzed.
        anomalies: List of detected anomalies.
        total_points: Total data points analyzed.
        anomaly_rate: Percentage of data points that are anomalies.
    """

    source: str
    metric: str
    anomalies: list[Anomaly]
    total_points: int
    anomaly_rate: float


class AnomalyDetector:
    """Detect anomalies in time series data.

    QA-04: System flags anomalies (>3 std dev moves, sudden jumps).

    Methods:
    - Z-score based detection: Flags values >3 std dev from rolling mean
    - Jump detection: Flags sudden percentage changes between consecutive points

    Example:
        detector = AnomalyDetector()

        # Detect statistical anomalies
        anomalies = detector.detect(df, "close")
        for a in anomalies:
            print(f"{a.date}: {a.anomaly_type} (z={a.z_score:.2f})")

        # Detect jumps
        jumps = detector.detect_jumps(df, "close")

        # Combined detection
        all_anomalies = detector.detect_all(df, "close")
    """

    def __init__(self, config: AnomalyConfig | None = None) -> None:
        """Initialize the anomaly detector.

        Args:
            config: Anomaly detection configuration. Uses default if not provided.
        """
        self.config = config or DEFAULT_CONFIG.anomaly

    def detect(
        self,
        df: pd.DataFrame,
        value_col: str,
        date_col: str = "date",
        z_threshold: float | None = None,
        lookback_days: int | None = None,
    ) -> list[Anomaly]:
        """Detect anomalies using z-score method.

        Uses a rolling window to calculate mean and standard deviation,
        then flags points where |z-score| > threshold.

        Args:
            df: DataFrame with time series data.
            value_col: Column containing values to analyze.
            date_col: Column containing dates.
            z_threshold: Z-score threshold (default from config).
            lookback_days: Rolling window size in days (default from config).

        Returns:
            List of detected Anomaly objects.
        """
        if df.empty or value_col not in df.columns:
            return []

        z_threshold = z_threshold or self.config.z_threshold
        lookback = lookback_days or self.config.lookback_days

        # Ensure we have enough data
        if len(df) < self.config.min_data_points:
            logger.debug(
                "Not enough data for anomaly detection: %d < %d",
                len(df),
                self.config.min_data_points,
            )
            return []

        # Sort by date
        df_sorted = df.sort_values(date_col).reset_index(drop=True)
        anomalies: list[Anomaly] = []

        for i in range(lookback, len(df_sorted)):
            # Get window
            window = df_sorted[value_col].iloc[i - lookback : i]
            current = df_sorted[value_col].iloc[i]
            current_date = df_sorted[date_col].iloc[i]

            mean = window.mean()
            std = window.std()

            # Skip if no variance
            if std == 0 or np.isnan(std):
                continue

            z_score = (current - mean) / std

            if abs(z_score) > z_threshold:
                if z_score > 0:
                    anomaly_type = AnomalyType.SPIKE
                else:
                    anomaly_type = AnomalyType.DROP

                # Handle date conversion
                if isinstance(current_date, pd.Timestamp):
                    anomaly_date = current_date.date()
                elif isinstance(current_date, date):
                    anomaly_date = current_date
                else:
                    anomaly_date = pd.to_datetime(current_date).date()

                anomalies.append(
                    Anomaly(
                        date=anomaly_date,
                        metric=value_col,
                        value=float(current),
                        z_score=float(z_score),
                        anomaly_type=anomaly_type,
                        message=f"{value_col} {anomaly_type.value}: z={z_score:.2f} (value={current:.2f}, mean={mean:.2f})",
                    )
                )

        logger.debug(
            "Detected %d z-score anomalies in %s (threshold=%.1f)",
            len(anomalies),
            value_col,
            z_threshold,
        )
        return anomalies

    def detect_jumps(
        self,
        df: pd.DataFrame,
        value_col: str,
        date_col: str = "date",
        jump_threshold_pct: float | None = None,
    ) -> list[Anomaly]:
        """Detect sudden jumps in values.

        Flags points where the percentage change from the previous point
        exceeds the threshold.

        Args:
            df: DataFrame with time series data.
            value_col: Column containing values to analyze.
            date_col: Column containing dates.
            jump_threshold_pct: Percentage change threshold (default from config).

        Returns:
            List of detected jump Anomaly objects.
        """
        if df.empty or value_col not in df.columns:
            return []

        jump_threshold = jump_threshold_pct or self.config.jump_threshold_pct

        # Sort by date
        df_sorted = df.sort_values(date_col).reset_index(drop=True)
        anomalies: list[Anomaly] = []

        values = df_sorted[value_col]
        dates = df_sorted[date_col]

        for i in range(1, len(values)):
            prev = values.iloc[i - 1]
            curr = values.iloc[i]
            current_date = dates.iloc[i]

            # Skip if previous value is zero
            if prev == 0 or np.isnan(prev) or np.isnan(curr):
                continue

            change_pct = abs(curr - prev) / abs(prev) * 100

            if change_pct > jump_threshold:
                # Calculate direction-aware z-score analog
                relative_change = (curr - prev) / abs(prev)

                # Handle date conversion
                if isinstance(current_date, pd.Timestamp):
                    anomaly_date = current_date.date()
                elif isinstance(current_date, date):
                    anomaly_date = current_date
                else:
                    anomaly_date = pd.to_datetime(current_date).date()

                anomalies.append(
                    Anomaly(
                        date=anomaly_date,
                        metric=value_col,
                        value=float(curr),
                        z_score=change_pct / jump_threshold,  # Normalized score
                        anomaly_type=AnomalyType.JUMP,
                        message=f"{value_col} JUMP: {change_pct:.1f}% change (from {prev:.2f} to {curr:.2f})",
                    )
                )

        logger.debug(
            "Detected %d jumps in %s (threshold=%.1f%%)",
            len(anomalies),
            value_col,
            jump_threshold,
        )
        return anomalies

    def detect_all(
        self,
        df: pd.DataFrame,
        value_col: str,
        date_col: str = "date",
    ) -> list[Anomaly]:
        """Detect all types of anomalies (z-score + jumps).

        Args:
            df: DataFrame with time series data.
            value_col: Column containing values to analyze.
            date_col: Column containing dates.

        Returns:
            Combined list of all detected anomalies, sorted by date.
        """
        z_anomalies = self.detect(df, value_col, date_col)
        jump_anomalies = self.detect_jumps(df, value_col, date_col)

        # Combine and deduplicate by date (keep the more severe)
        all_anomalies = z_anomalies + jump_anomalies

        # Sort by date
        all_anomalies.sort(key=lambda a: a.date)

        return all_anomalies

    def get_anomaly_report(
        self,
        df: pd.DataFrame,
        value_col: str,
        source: str = "unknown",
        date_col: str = "date",
    ) -> AnomalyReport:
        """Generate comprehensive anomaly report.

        Args:
            df: DataFrame with time series data.
            value_col: Column containing values to analyze.
            source: Source identifier.
            date_col: Column containing dates.

        Returns:
            AnomalyReport with all detected anomalies and statistics.
        """
        anomalies = self.detect_all(df, value_col, date_col)
        total_points = len(df)

        anomaly_rate = (len(anomalies) / total_points * 100) if total_points > 0 else 0

        return AnomalyReport(
            source=source,
            metric=value_col,
            anomalies=anomalies,
            total_points=total_points,
            anomaly_rate=anomaly_rate,
        )

    def calculate_anomaly_score(
        self,
        anomaly_reports: list[AnomalyReport],
        max_acceptable_rate: float = 5.0,
    ) -> float:
        """Calculate anomaly score for quality assessment.

        Lower anomaly rate = higher score.

        Args:
            anomaly_reports: List of anomaly reports to aggregate.
            max_acceptable_rate: Maximum acceptable anomaly rate (100% penalty).

        Returns:
            Score between 0 and 100 (100 = no anomalies).
        """
        if not anomaly_reports:
            return 100.0

        avg_rate = sum(r.anomaly_rate for r in anomaly_reports) / len(anomaly_reports)

        # Linear penalty up to max_acceptable_rate
        if avg_rate >= max_acceptable_rate:
            return 0.0

        return 100 * (1 - avg_rate / max_acceptable_rate)
