"""Tests for quality indicator components."""

from datetime import UTC, datetime, timedelta


class TestFormatRelativeTime:
    """Test relative time formatting."""

    def test_just_now(self) -> None:
        """Test formatting for very recent timestamps."""
        from liquidity.dashboard.components.quality import format_relative_time

        now = datetime.now(UTC)
        result = format_relative_time(now)

        assert result == "just now"

    def test_minutes_ago(self) -> None:
        """Test formatting for timestamps minutes ago."""
        from liquidity.dashboard.components.quality import format_relative_time

        ts = datetime.now(UTC) - timedelta(minutes=15)
        result = format_relative_time(ts)

        assert result == "15 min ago"

    def test_hours_ago(self) -> None:
        """Test formatting for timestamps hours ago."""
        from liquidity.dashboard.components.quality import format_relative_time

        ts = datetime.now(UTC) - timedelta(hours=5)
        result = format_relative_time(ts)

        assert result == "5h ago"

    def test_days_ago(self) -> None:
        """Test formatting for timestamps days ago."""
        from liquidity.dashboard.components.quality import format_relative_time

        ts = datetime.now(UTC) - timedelta(days=3)
        result = format_relative_time(ts)

        assert result == "3d ago"

    def test_naive_timestamp_handled(self) -> None:
        """Test that naive (no timezone) timestamps are handled."""
        from liquidity.dashboard.components.quality import format_relative_time

        # Naive timestamp
        ts = datetime.now() - timedelta(minutes=30)
        result = format_relative_time(ts)

        assert "min ago" in result


class TestCreateQualityStatusBar:
    """Test quality status bar component."""

    def test_status_bar_with_none(self) -> None:
        """Test creating status bar with no report."""
        from liquidity.dashboard.components.quality import create_quality_status_bar

        result = create_quality_status_bar(None)

        assert result is not None
        assert hasattr(result, "children")

    def test_status_bar_high_score(self) -> None:
        """Test status bar with high quality score (>= 90)."""
        from liquidity.dashboard.components.quality import create_quality_status_bar
        from liquidity.validation import QualityReport

        report = QualityReport(
            overall_score=95,
            freshness_score=100,
            completeness_score=90,
            validation_score=95,
            anomaly_count=0,
            stale_sources=[],
            critical_issues=[],
            timestamp=datetime.now(UTC),
        )

        result = create_quality_status_bar(report)

        assert result is not None
        # Score should be displayed
        assert "95%" in str(result)

    def test_status_bar_medium_score(self) -> None:
        """Test status bar with medium quality score (70-90)."""
        from liquidity.dashboard.components.quality import create_quality_status_bar
        from liquidity.validation import QualityReport

        report = QualityReport(
            overall_score=75,
            freshness_score=70,
            completeness_score=80,
            validation_score=75,
            anomaly_count=2,
            stale_sources=["source1"],
            critical_issues=[],
            timestamp=datetime.now(UTC),
        )

        result = create_quality_status_bar(report)

        assert result is not None

    def test_status_bar_low_score(self) -> None:
        """Test status bar with low quality score (< 70)."""
        from liquidity.dashboard.components.quality import create_quality_status_bar
        from liquidity.validation import QualityReport

        report = QualityReport(
            overall_score=50,
            freshness_score=40,
            completeness_score=60,
            validation_score=50,
            anomaly_count=5,
            stale_sources=["source1", "source2", "source3"],
            critical_issues=["Critical issue 1"],
            timestamp=datetime.now(UTC),
        )

        result = create_quality_status_bar(report)

        assert result is not None


class TestCreateFreshnessIndicators:
    """Test freshness indicator components."""

    def test_all_fresh(self) -> None:
        """Test indicator when all sources are fresh."""
        from liquidity.dashboard.components.quality import create_freshness_indicators

        result = create_freshness_indicators([])

        assert result is not None
        assert "fresh" in str(result).lower()

    def test_some_stale(self) -> None:
        """Test indicator with some stale sources."""
        from liquidity.dashboard.components.quality import create_freshness_indicators

        stale = ["source1", "source2"]
        result = create_freshness_indicators(stale)

        assert result is not None
        assert "source1" in str(result)
        assert "source2" in str(result)

    def test_many_stale_truncated(self) -> None:
        """Test that many stale sources are truncated."""
        from liquidity.dashboard.components.quality import create_freshness_indicators

        stale = ["s1", "s2", "s3", "s4", "s5"]
        result = create_freshness_indicators(stale)

        assert result is not None
        # Should show "+2 more" for sources beyond first 3
        assert "+2 more" in str(result)


class TestCreateQualityDetailPanel:
    """Test quality detail panel component."""

    def test_panel_created(self) -> None:
        """Test that detail panel is created."""
        from liquidity.dashboard.components.quality import create_quality_detail_panel

        result = create_quality_detail_panel()

        assert result is not None
        # Should have collapse toggle
        assert "quality-collapse-toggle" in str(result)

    def test_panel_has_gauges(self) -> None:
        """Test that panel has gauge placeholders."""
        from liquidity.dashboard.components.quality import create_quality_detail_panel

        result = create_quality_detail_panel()

        # Should have gauge IDs
        panel_str = str(result)
        assert "freshness-gauge" in panel_str
        assert "completeness-gauge" in panel_str
        assert "validation-gauge" in panel_str

    def test_panel_has_table_placeholder(self) -> None:
        """Test that panel has table placeholder."""
        from liquidity.dashboard.components.quality import create_quality_detail_panel

        result = create_quality_detail_panel()

        assert "source-freshness-table" in str(result)


class TestCreateQualityGauge:
    """Test quality gauge chart creation."""

    def test_gauge_created(self) -> None:
        """Test that gauge figure is created."""
        from liquidity.dashboard.components.quality import create_quality_gauge

        fig = create_quality_gauge(85, "Test Gauge")

        assert fig is not None
        assert hasattr(fig, "data")
        assert hasattr(fig, "layout")

    def test_gauge_high_value_green(self) -> None:
        """Test that high values use green color."""
        from liquidity.dashboard.components.quality import create_quality_gauge

        fig = create_quality_gauge(95, "High")

        # The gauge should exist and have indicator data
        assert len(fig.data) > 0
        assert fig.data[0].type == "indicator"

    def test_gauge_medium_value(self) -> None:
        """Test gauge with medium value."""
        from liquidity.dashboard.components.quality import create_quality_gauge

        fig = create_quality_gauge(75, "Medium")

        assert fig is not None
        assert len(fig.data) > 0

    def test_gauge_low_value(self) -> None:
        """Test gauge with low value."""
        from liquidity.dashboard.components.quality import create_quality_gauge

        fig = create_quality_gauge(50, "Low")

        assert fig is not None


class TestCreateSourceFreshnessTable:
    """Test source freshness table component."""

    def test_empty_sources(self) -> None:
        """Test table with no sources."""
        from liquidity.dashboard.components.quality import create_source_freshness_table

        result = create_source_freshness_table({})

        assert result is not None
        assert "No data" in str(result) or "available" in str(result)

    def test_table_with_sources(self) -> None:
        """Test table with multiple sources."""
        from liquidity.dashboard.components.quality import create_source_freshness_table

        now = datetime.now(UTC)
        last_updates = {
            "source1": now - timedelta(hours=6),
            "source2": now - timedelta(hours=30),
            "source3": now - timedelta(hours=72),
        }

        result = create_source_freshness_table(last_updates)

        assert result is not None
        result_str = str(result)
        assert "source1" in result_str
        assert "source2" in result_str
        assert "source3" in result_str

    def test_table_with_status(self) -> None:
        """Test table with explicit freshness status."""
        from liquidity.dashboard.components.quality import create_source_freshness_table
        from liquidity.validation import FreshnessStatus

        now = datetime.now(UTC)
        last_updates = {
            "fresh_source": now - timedelta(hours=1),
            "stale_source": now - timedelta(hours=30),
        }
        freshness_status = {
            "fresh_source": FreshnessStatus.FRESH,
            "stale_source": FreshnessStatus.STALE,
        }

        result = create_source_freshness_table(last_updates, freshness_status)

        assert result is not None


class TestGetQualityStatusForExport:
    """Test quality status export helper."""

    def test_export_with_none(self) -> None:
        """Test export helper with no report."""
        from liquidity.dashboard.components.quality import get_quality_status_for_export

        result = get_quality_status_for_export(None)

        assert result is not None
        assert "quality_score" in result
        assert result["quality_score"] == "N/A"

    def test_export_with_report(self) -> None:
        """Test export helper with quality report."""
        from liquidity.dashboard.components.quality import get_quality_status_for_export
        from liquidity.validation import QualityReport

        report = QualityReport(
            overall_score=90,
            freshness_score=95,
            completeness_score=85,
            validation_score=90,
            anomaly_count=1,
            stale_sources=["source1"],
            critical_issues=[],
            timestamp=datetime.now(UTC),
        )

        result = get_quality_status_for_export(report)

        assert result["quality_score"] == 90
        assert result["freshness_score"] == 95
        assert result["completeness_score"] == 85
        assert result["stale_sources"] == ["source1"]
        assert "timestamp" in result
