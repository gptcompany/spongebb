"""Validation configuration and thresholds.

Centralized configuration for all data quality validation checks.
"""

from dataclasses import dataclass, field
from enum import Enum


class FreshnessStatus(Enum):
    """Status of data freshness check."""

    FRESH = "fresh"
    STALE = "stale"
    CRITICAL = "critical"


class GapSeverity(Enum):
    """Severity level of data gaps."""

    MINOR = "minor"  # <3 days
    MAJOR = "major"  # 3-7 days
    CRITICAL = "critical"  # >7 days


class ValidationStatus(Enum):
    """Status of cross-validation comparison."""

    MATCH = "match"
    MINOR_DIFF = "minor_diff"
    MAJOR_DIFF = "major_diff"


class AnomalyType(Enum):
    """Type of detected anomaly."""

    SPIKE = "spike"  # Large positive z-score
    DROP = "drop"  # Large negative z-score
    JUMP = "jump"  # Sudden change between consecutive points
    OUTLIER = "outlier"  # General outlier


@dataclass
class FreshnessConfig:
    """Configuration for freshness detection thresholds.

    Thresholds are in hours. Data older than threshold is STALE,
    data older than 2x threshold is CRITICAL.

    Attributes:
        thresholds: Mapping of source name to max age in hours.
    """

    thresholds: dict[str, int] = field(
        default_factory=lambda: {
            # Central Banks - Weekly updates
            "fed_balance_sheet": 48,  # Weekly update
            "walcl": 48,
            "ecb_balance_sheet": 48,
            "boj_balance_sheet": 48,
            "pboc_balance_sheet": 168,  # Monthly update
            # Fed components - Daily/Weekly
            "tga": 24,  # Daily (with weekend buffer)
            "rrp": 24,  # Daily
            # Rates - Daily
            "sofr": 24,
            "effr": 24,
            "obfr": 24,
            "ester": 24,
            "sonia": 24,
            "tonar": 24,
            # Market data - Daily
            "dxy": 24,
            "vix": 24,
            "move": 24,
            "treasury_yields": 24,
            "gold": 24,
            "oil": 24,
            # Capital flows - Monthly
            "tic_data": 720,  # ~30 days
            "cofer": 720,
        }
    )

    def get_threshold(self, source: str) -> int:
        """Get threshold for a source, with fallback to default.

        Args:
            source: Source identifier (case-insensitive).

        Returns:
            Threshold in hours.
        """
        return self.thresholds.get(source.lower(), 24)


@dataclass
class CompletenessConfig:
    """Configuration for completeness/gap detection.

    Attributes:
        max_gap_days: Maximum acceptable gap in business days.
        min_gap_severity_days: Minimum gap days to report.
    """

    max_gap_days: int = 3
    min_gap_severity_days: int = 2
    gap_severity_thresholds: dict[str, int] = field(
        default_factory=lambda: {
            "minor": 3,  # <= 3 days
            "major": 7,  # 3-7 days
            # > 7 days = critical
        }
    )


@dataclass
class CrossValidationConfig:
    """Configuration for cross-source validation.

    Attributes:
        tolerance_pct: Default tolerance percentage for matching.
        source_tolerances: Per-source tolerance overrides.
    """

    tolerance_pct: float = 1.0  # 1% default tolerance
    source_tolerances: dict[str, float] = field(
        default_factory=lambda: {
            "fed_balance_sheet": 0.5,  # Tight tolerance for Fed data
            "sofr": 0.01,  # Very tight for rates
            "dxy": 0.1,  # Tight for FX
        }
    )


@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection.

    Attributes:
        z_threshold: Z-score threshold for anomaly detection.
        lookback_days: Number of days for rolling statistics.
        jump_threshold_pct: Percentage change threshold for jump detection.
    """

    z_threshold: float = 3.0
    lookback_days: int = 90
    jump_threshold_pct: float = 10.0
    min_data_points: int = 30  # Minimum points for reliable stats


@dataclass
class RegressionConfig:
    """Configuration for regression tests.

    Attributes:
        tolerance_pct: Tolerance for comparing against historical values.
        historical_dates: Known dates for historical validation.
    """

    tolerance_pct: float = 5.0
    # Known historical values for validation (from Apps Script v3.4.1)
    # Format: date -> (net_liquidity, global_liquidity, stealth_qe)
    # Values in billions USD
    historical_values: dict[str, tuple[float, float, float]] = field(
        default_factory=lambda: {
            "2024-01-15": (5.82e12, 28.5e12, 15.0),
            "2024-06-30": (5.95e12, 29.1e12, 22.0),
            "2024-12-31": (6.10e12, 29.8e12, 18.0),
        }
    )


@dataclass
class QualityConfig:
    """Master configuration for quality scoring.

    Attributes:
        weights: Weights for each quality component (must sum to 1.0).
        min_score_threshold: Minimum acceptable quality score.
    """

    weights: dict[str, float] = field(
        default_factory=lambda: {
            "freshness": 0.30,
            "completeness": 0.40,
            "validation": 0.30,
        }
    )
    min_score_threshold: float = 70.0  # Minimum acceptable score

    freshness: FreshnessConfig = field(default_factory=FreshnessConfig)
    completeness: CompletenessConfig = field(default_factory=CompletenessConfig)
    cross_validation: CrossValidationConfig = field(default_factory=CrossValidationConfig)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    regression: RegressionConfig = field(default_factory=RegressionConfig)


# Default configuration instance
DEFAULT_CONFIG = QualityConfig()
