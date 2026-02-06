"""Tests for EIA panel component."""

from datetime import datetime

import pandas as pd
import pytest


class TestEIAPanel:
    """Test EIA panel creation."""

    def test_create_panel(self) -> None:
        """Test creating the EIA panel."""
        from liquidity.dashboard.components.eia_panel import create_eia_panel

        panel = create_eia_panel()

        assert panel is not None

    def test_panel_has_card_structure(self) -> None:
        """Test that panel is a Bootstrap Card."""
        import dash_bootstrap_components as dbc

        from liquidity.dashboard.components.eia_panel import create_eia_panel

        panel = create_eia_panel()

        assert isinstance(panel, dbc.Card)

    def test_panel_has_tabs(self) -> None:
        """Test that panel contains tabs."""
        from liquidity.dashboard.components.eia_panel import create_eia_panel

        panel = create_eia_panel()

        # Check that panel has CardBody with Tabs
        card_body = panel.children[1]  # CardBody is second child
        tabs = card_body.children[0]  # Tabs is first child of CardBody

        assert hasattr(tabs, "children")
        # Should have 3 tabs
        assert len(tabs.children) == 3


class TestCushingChart:
    """Test Cushing inventory chart creation."""

    def test_create_empty_chart(self) -> None:
        """Test creating chart with no data."""
        from liquidity.dashboard.components.eia_panel import create_cushing_chart

        fig = create_cushing_chart(None)

        assert fig is not None
        assert hasattr(fig, "data")
        assert hasattr(fig, "layout")

    def test_create_chart_with_data(self) -> None:
        """Test creating chart with inventory data."""
        from liquidity.dashboard.components.eia_panel import create_cushing_chart

        dates = pd.date_range(end=datetime.now(), periods=52, freq="D")
        df = pd.DataFrame({
            "timestamp": dates,
            "value": [35000 + i * 100 for i in range(len(dates))],
        })

        fig = create_cushing_chart(df)

        assert fig is not None
        # Should have at least 2 traces: range band + inventory line
        assert len(fig.data) >= 2

    def test_chart_has_capacity_line(self) -> None:
        """Test that chart shows capacity reference line."""
        from liquidity.dashboard.components.eia_panel import create_cushing_chart

        dates = pd.date_range(end=datetime.now(), periods=10, freq="D")
        df = pd.DataFrame({
            "timestamp": dates,
            "value": [35000 + i * 100 for i in range(len(dates))],
        })

        fig = create_cushing_chart(df)

        # Check for horizontal line (capacity)
        assert len(fig.layout.shapes) > 0 or "hline" in str(fig.to_dict())

    def test_chart_with_short_data(self) -> None:
        """Test chart with less than 52 weeks of data."""
        from liquidity.dashboard.components.eia_panel import create_cushing_chart

        dates = pd.date_range(end=datetime.now(), periods=10, freq="D")
        df = pd.DataFrame({
            "timestamp": dates,
            "value": [35000 + i * 100 for i in range(len(dates))],
        })

        fig = create_cushing_chart(df)

        assert fig is not None
        # Should still create a valid chart
        assert len(fig.data) >= 1


class TestRefineryChart:
    """Test refinery utilization chart creation."""

    def test_create_empty_chart(self) -> None:
        """Test creating chart with no data."""
        from liquidity.dashboard.components.eia_panel import create_refinery_chart

        fig = create_refinery_chart(None)

        assert fig is not None
        assert hasattr(fig, "data")

    def test_create_chart_with_data(self) -> None:
        """Test creating chart with refinery data."""
        from liquidity.dashboard.components.eia_panel import create_refinery_chart

        dates = pd.date_range(end=datetime.now(), periods=52, freq="W")
        data = []
        for series_id in ["WPULEUS3", "W_NA_YUP_R10_PER", "W_NA_YUP_R30_PER"]:
            for i, dt in enumerate(dates):
                data.append({
                    "timestamp": dt,
                    "series_id": series_id,
                    "value": 90 + (i % 5),
                })

        df = pd.DataFrame(data)
        fig = create_refinery_chart(df)

        assert fig is not None
        # Should have traces for each PADD region present
        assert len(fig.data) >= 3

    def test_chart_has_threshold_lines(self) -> None:
        """Test that chart shows threshold reference lines."""
        from liquidity.dashboard.components.eia_panel import create_refinery_chart

        fig = create_refinery_chart(None)

        # Check for horizontal lines (thresholds)
        # The chart should have threshold lines even with no data
        assert len(fig.layout.shapes) >= 2 or "hline" in str(fig.to_dict())


class TestSupplyChart:
    """Test supply (production/imports) chart creation."""

    def test_create_empty_charts(self) -> None:
        """Test creating charts with no data."""
        from liquidity.dashboard.components.eia_panel import create_supply_chart

        production_fig, imports_fig = create_supply_chart(None, None)

        assert production_fig is not None
        assert imports_fig is not None

    def test_create_charts_with_data(self) -> None:
        """Test creating charts with production and imports data."""
        from liquidity.dashboard.components.eia_panel import create_supply_chart

        dates = pd.date_range(end=datetime.now(), periods=52, freq="D")
        production_df = pd.DataFrame({
            "timestamp": dates,
            "value": [13000 + i * 10 for i in range(len(dates))],
        })
        imports_df = pd.DataFrame({
            "timestamp": dates,
            "value": [6000 + i * 5 for i in range(len(dates))],
        })

        production_fig, imports_fig = create_supply_chart(production_df, imports_df)

        assert production_fig is not None
        assert imports_fig is not None
        assert len(production_fig.data) >= 1
        assert len(imports_fig.data) >= 1


class TestCushingUtilizationBadge:
    """Test Cushing utilization badge creation."""

    def test_create_badge_with_none(self) -> None:
        """Test creating badge with None value."""
        from liquidity.dashboard.components.eia_panel import (
            create_cushing_utilization_badge,
        )

        badge = create_cushing_utilization_badge(None)

        assert badge is not None

    def test_create_badge_low_utilization(self) -> None:
        """Test badge for low utilization (tight market)."""
        from liquidity.dashboard.components.eia_panel import (
            create_cushing_utilization_badge,
        )

        badge = create_cushing_utilization_badge(25.0)

        assert badge is not None
        # Check that badge text reflects tight market

    def test_create_badge_high_utilization(self) -> None:
        """Test badge for high utilization (oversupplied)."""
        from liquidity.dashboard.components.eia_panel import (
            create_cushing_utilization_badge,
        )

        badge = create_cushing_utilization_badge(75.0)

        assert badge is not None

    @pytest.mark.parametrize(
        "utilization,expected_status",
        [
            (25.0, "Tight"),
            (45.0, "Normal"),
            (60.0, "Elevated"),
            (80.0, "Full"),
        ],
    )
    def test_badge_status_classification(
        self, utilization: float, expected_status: str
    ) -> None:
        """Test that badge correctly classifies utilization levels."""
        from liquidity.dashboard.components.eia_panel import (
            create_cushing_utilization_badge,
        )

        badge = create_cushing_utilization_badge(utilization)

        # The status text should be in the badge
        badge_str = str(badge)
        assert expected_status in badge_str


class TestRefinerySignalBadge:
    """Test refinery signal badge creation."""

    def test_create_badge_with_none(self) -> None:
        """Test creating badge with None signal."""
        from liquidity.dashboard.components.eia_panel import (
            create_refinery_signal_badge,
        )

        badge = create_refinery_signal_badge(None)

        assert badge is not None

    @pytest.mark.parametrize(
        "signal,expected_description",
        [
            ("TIGHT", "Supply Constraint"),
            ("NORMAL", "Healthy"),
            ("SOFT", "Softening"),
            ("WEAK", "Weak Demand"),
        ],
    )
    def test_badge_signal_description(
        self, signal: str, expected_description: str
    ) -> None:
        """Test that badge shows correct description for each signal."""
        from liquidity.dashboard.components.eia_panel import (
            create_refinery_signal_badge,
        )

        badge = create_refinery_signal_badge(signal)

        badge_str = str(badge)
        assert expected_description in badge_str


class TestEIAPanelIntegration:
    """Integration tests for EIA panel with components __init__."""

    def test_imports_from_components_init(self) -> None:
        """Test that all exports are available from components __init__."""
        from liquidity.dashboard.components import (
            create_cushing_chart,
            create_cushing_utilization_badge,
            create_eia_panel,
            create_refinery_chart,
            create_refinery_signal_badge,
            create_supply_chart,
        )

        # All imports should be available
        assert create_eia_panel is not None
        assert create_cushing_chart is not None
        assert create_refinery_chart is not None
        assert create_supply_chart is not None
        assert create_cushing_utilization_badge is not None
        assert create_refinery_signal_badge is not None
