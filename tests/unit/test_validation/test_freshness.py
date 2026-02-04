"""Unit tests for freshness validation (QA-01)."""

from datetime import UTC, datetime, timedelta

import pytest

from liquidity.validation.config import FreshnessConfig, FreshnessStatus
from liquidity.validation.freshness import FreshnessCheckResult, FreshnessChecker


class TestFreshnessChecker:
    """Tests for FreshnessChecker class."""

    def test_check_fresh_data(self) -> None:
        """Test that fresh data is detected correctly."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_update = now - timedelta(hours=12)  # 12 hours ago

        result = checker.check("sofr", last_update, now=now)

        assert result.status == FreshnessStatus.FRESH
        assert result.source == "sofr"
        assert result.age_hours == pytest.approx(12, abs=0.1)
        assert result.threshold_hours == 24

    def test_check_stale_daily_data(self) -> None:
        """Test that stale daily data (>24h) is detected."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_update = now - timedelta(hours=30)  # 30 hours ago

        result = checker.check("sofr", last_update, now=now)

        assert result.status == FreshnessStatus.STALE
        assert "STALE" in result.message

    def test_check_critical_data(self) -> None:
        """Test that critical data (>2x threshold) is detected."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_update = now - timedelta(hours=50)  # 50 hours ago (>48h = 2x24h)

        result = checker.check("sofr", last_update, now=now)

        assert result.status == FreshnessStatus.CRITICAL
        assert "CRITICAL" in result.message

    def test_check_central_bank_data_fresh(self) -> None:
        """Test that CB data with 48h threshold is handled correctly."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_update = now - timedelta(hours=40)  # 40 hours ago

        result = checker.check("fed_balance_sheet", last_update, now=now)

        assert result.status == FreshnessStatus.FRESH
        assert result.threshold_hours == 48

    def test_check_central_bank_data_stale(self) -> None:
        """Test that CB data with 48h threshold detects stale correctly."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_update = now - timedelta(hours=60)  # 60 hours ago

        result = checker.check("fed_balance_sheet", last_update, now=now)

        assert result.status == FreshnessStatus.STALE

    def test_check_all_sources(self) -> None:
        """Test checking multiple sources at once."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_updates = {
            "sofr": now - timedelta(hours=12),  # Fresh
            "dxy": now - timedelta(hours=30),  # Stale
            "fed_balance_sheet": now - timedelta(hours=40),  # Fresh (48h threshold)
        }

        results = checker.check_all(last_updates, now=now)

        assert len(results) == 3
        assert results["sofr"].status == FreshnessStatus.FRESH
        assert results["dxy"].status == FreshnessStatus.STALE
        assert results["fed_balance_sheet"].status == FreshnessStatus.FRESH

    def test_get_stale_sources(self) -> None:
        """Test getting list of stale sources."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_updates = {
            "sofr": now - timedelta(hours=12),  # Fresh
            "dxy": now - timedelta(hours=30),  # Stale
            "vix": now - timedelta(hours=50),  # Critical
        }

        stale = checker.get_stale_sources(last_updates, now=now)

        assert "sofr" not in stale
        assert "dxy" in stale
        assert "vix" in stale

    def test_get_critical_sources(self) -> None:
        """Test getting list of critical sources only."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_updates = {
            "sofr": now - timedelta(hours=12),  # Fresh
            "dxy": now - timedelta(hours=30),  # Stale
            "vix": now - timedelta(hours=50),  # Critical
        }

        critical = checker.get_critical_sources(last_updates, now=now)

        assert "sofr" not in critical
        assert "dxy" not in critical
        assert "vix" in critical

    def test_calculate_freshness_score(self) -> None:
        """Test freshness score calculation."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_updates = {
            "sofr": now - timedelta(hours=12),  # Fresh
            "dxy": now - timedelta(hours=12),  # Fresh
            "vix": now - timedelta(hours=30),  # Stale
            "move": now - timedelta(hours=12),  # Fresh
        }

        score = checker.calculate_freshness_score(last_updates, now=now)

        # 3 out of 4 are fresh = 75%
        assert score == pytest.approx(75.0)

    def test_empty_updates_returns_perfect_score(self) -> None:
        """Test that empty updates returns 100% score."""
        checker = FreshnessChecker()

        score = checker.calculate_freshness_score({})

        assert score == 100.0

    def test_custom_config(self) -> None:
        """Test using custom freshness configuration."""
        config = FreshnessConfig(
            thresholds={
                "custom_source": 6,  # 6 hours threshold
            }
        )
        checker = FreshnessChecker(config=config)
        now = datetime.now(UTC)
        last_update = now - timedelta(hours=8)

        result = checker.check("custom_source", last_update, now=now)

        assert result.status == FreshnessStatus.STALE
        assert result.threshold_hours == 6

    def test_unknown_source_uses_default_threshold(self) -> None:
        """Test that unknown sources use default 24h threshold."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_update = now - timedelta(hours=12)

        result = checker.check("unknown_source_xyz", last_update, now=now)

        assert result.status == FreshnessStatus.FRESH
        assert result.threshold_hours == 24

    def test_timezone_naive_datetime_handling(self) -> None:
        """Test that timezone-naive datetimes are handled correctly."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)
        last_update = datetime.utcnow() - timedelta(hours=12)  # Naive datetime

        result = checker.check("sofr", last_update, now=now)

        assert result.status == FreshnessStatus.FRESH

    def test_monthly_data_threshold(self) -> None:
        """Test monthly data sources have appropriate thresholds."""
        checker = FreshnessChecker()
        now = datetime.now(UTC)

        # TIC data - 720 hours (30 days) threshold
        last_update = now - timedelta(days=25)  # 25 days ago

        result = checker.check("tic_data", last_update, now=now)

        assert result.status == FreshnessStatus.FRESH
        assert result.threshold_hours == 720
