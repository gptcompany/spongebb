"""QA-01: Stale data detection for data quality validation.

Detects stale data based on configurable thresholds per data source.
Daily feeds should not be older than 24h, central bank data 48h, etc.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .config import DEFAULT_CONFIG, FreshnessConfig, FreshnessStatus

logger = logging.getLogger(__name__)


@dataclass
class FreshnessCheckResult:
    """Result of a freshness check for a single source.

    Attributes:
        source: Data source identifier.
        last_update: Timestamp of last data update.
        age_hours: Age of data in hours.
        threshold_hours: Configured threshold for this source.
        status: Freshness status (FRESH, STALE, CRITICAL).
        message: Human-readable description.
    """

    source: str
    last_update: datetime
    age_hours: float
    threshold_hours: int
    status: FreshnessStatus
    message: str


class FreshnessChecker:
    """Check data freshness against configurable thresholds.

    QA-01: System detects stale data (>24h for daily feeds, >48h for CBs).

    Example:
        checker = FreshnessChecker()

        # Check single source
        result = checker.check("sofr", datetime.now(UTC) - timedelta(hours=30))
        print(f"SOFR status: {result.status}")  # STALE

        # Check all sources
        last_updates = {
            "sofr": datetime.now(UTC) - timedelta(hours=12),
            "fed_balance_sheet": datetime.now(UTC) - timedelta(hours=60),
        }
        statuses = checker.check_all(last_updates)
        stale = checker.get_stale_sources(last_updates)
    """

    def __init__(self, config: FreshnessConfig | None = None) -> None:
        """Initialize the freshness checker.

        Args:
            config: Freshness configuration. Uses default if not provided.
        """
        self.config = config or DEFAULT_CONFIG.freshness

    def check(
        self,
        source: str,
        last_update: datetime,
        now: datetime | None = None,
    ) -> FreshnessCheckResult:
        """Check if a data source is fresh, stale, or critical.

        Args:
            source: Data source identifier.
            last_update: Timestamp of last data update.
            now: Current time (for testing). Defaults to UTC now.

        Returns:
            FreshnessCheckResult with status and details.
        """
        if now is None:
            now = datetime.now(UTC)

        # Ensure timezone-aware
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        threshold_hours = self.config.get_threshold(source)
        age = now - last_update
        age_hours = age.total_seconds() / 3600

        # Determine status
        if age < timedelta(hours=threshold_hours):
            status = FreshnessStatus.FRESH
            message = f"{source}: FRESH - updated {age_hours:.1f}h ago (threshold: {threshold_hours}h)"
        elif age < timedelta(hours=threshold_hours * 2):
            status = FreshnessStatus.STALE
            message = f"{source}: STALE - updated {age_hours:.1f}h ago (threshold: {threshold_hours}h)"
        else:
            status = FreshnessStatus.CRITICAL
            message = f"{source}: CRITICAL - updated {age_hours:.1f}h ago (threshold: {threshold_hours}h)"

        logger.debug(
            "Freshness check %s: %s (age=%.1fh, threshold=%dh)",
            source,
            status.value,
            age_hours,
            threshold_hours,
        )

        return FreshnessCheckResult(
            source=source,
            last_update=last_update,
            age_hours=age_hours,
            threshold_hours=threshold_hours,
            status=status,
            message=message,
        )

    def check_all(
        self,
        last_updates: dict[str, datetime],
        now: datetime | None = None,
    ) -> dict[str, FreshnessCheckResult]:
        """Check freshness for all sources.

        Args:
            last_updates: Mapping of source names to last update timestamps.
            now: Current time (for testing).

        Returns:
            Mapping of source names to check results.
        """
        return {source: self.check(source, ts, now) for source, ts in last_updates.items()}

    def get_stale_sources(
        self,
        last_updates: dict[str, datetime],
        now: datetime | None = None,
    ) -> list[str]:
        """Get list of stale or critical sources.

        Args:
            last_updates: Mapping of source names to last update timestamps.
            now: Current time (for testing).

        Returns:
            List of source names that are not FRESH.
        """
        results = self.check_all(last_updates, now)
        return [
            source
            for source, result in results.items()
            if result.status != FreshnessStatus.FRESH
        ]

    def get_critical_sources(
        self,
        last_updates: dict[str, datetime],
        now: datetime | None = None,
    ) -> list[str]:
        """Get list of critical sources only.

        Args:
            last_updates: Mapping of source names to last update timestamps.
            now: Current time (for testing).

        Returns:
            List of source names that are CRITICAL.
        """
        results = self.check_all(last_updates, now)
        return [
            source
            for source, result in results.items()
            if result.status == FreshnessStatus.CRITICAL
        ]

    def calculate_freshness_score(
        self,
        last_updates: dict[str, datetime],
        now: datetime | None = None,
    ) -> float:
        """Calculate overall freshness score (0-100).

        Score is percentage of FRESH sources.

        Args:
            last_updates: Mapping of source names to last update timestamps.
            now: Current time (for testing).

        Returns:
            Freshness score between 0 and 100.
        """
        if not last_updates:
            return 100.0  # No data to check = perfect score

        results = self.check_all(last_updates, now)
        fresh_count = sum(
            1 for r in results.values() if r.status == FreshnessStatus.FRESH
        )

        return (fresh_count / len(results)) * 100
