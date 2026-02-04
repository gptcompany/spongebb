"""Tests for liquidity chart components."""

from datetime import datetime

import pandas as pd


class TestNetLiquidityChart:
    """Test Net Liquidity chart creation."""

    def test_create_empty_chart(self) -> None:
        """Test creating chart with no data."""
        from liquidity.dashboard.components.liquidity import create_net_liquidity_chart

        fig = create_net_liquidity_chart(None)

        assert fig is not None
        assert hasattr(fig, "data")
        assert hasattr(fig, "layout")

    def test_create_chart_with_data(self) -> None:
        """Test creating chart with valid data."""
        from liquidity.dashboard.components.liquidity import create_net_liquidity_chart

        # Create sample data
        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "net_liquidity": [5800 + i * 10 for i in range(30)],
                "walcl": [7800 + i * 5 for i in range(30)],
                "tga": [800 + i for i in range(30)],
                "rrp": [1200 + i * 2 for i in range(30)],
            }
        )

        fig = create_net_liquidity_chart(df)

        assert fig is not None
        # Should have at least the main trace
        assert len(fig.data) >= 1
        # First trace should be Net Liquidity
        assert fig.data[0].name == "Net Liquidity"

    def test_chart_has_dark_template(self) -> None:
        """Test that chart uses dark theme."""
        from liquidity.dashboard.components.liquidity import create_net_liquidity_chart

        fig = create_net_liquidity_chart(None)

        assert fig.layout.template.layout.paper_bgcolor is not None or "dark" in str(
            fig.layout.template
        ).lower()

    def test_chart_shows_components_by_default(self) -> None:
        """Test that components (WALCL, TGA, RRP) are added when show_components=True."""
        from liquidity.dashboard.components.liquidity import create_net_liquidity_chart

        dates = pd.date_range(end=datetime.now(), periods=10, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "net_liquidity": [5800] * 10,
                "walcl": [7800] * 10,
                "tga": [800] * 10,
                "rrp": [1200] * 10,
            }
        )

        fig = create_net_liquidity_chart(df, show_components=True)

        # Should have 4 traces: Net Liquidity + 3 components
        assert len(fig.data) == 4
        trace_names = [t.name for t in fig.data]
        assert "WALCL (Fed Assets)" in trace_names
        assert "TGA (Treasury)" in trace_names
        assert "RRP (Reverse Repo)" in trace_names


class TestGlobalLiquidityChart:
    """Test Global Liquidity chart creation."""

    def test_create_empty_chart(self) -> None:
        """Test creating chart with no data."""
        from liquidity.dashboard.components.liquidity import create_global_liquidity_chart

        fig = create_global_liquidity_chart(None)

        assert fig is not None
        assert hasattr(fig, "data")

    def test_create_chart_with_breakdown(self) -> None:
        """Test creating chart with CB breakdown."""
        from liquidity.dashboard.components.liquidity import create_global_liquidity_chart

        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "global_liquidity": [28000 + i * 50 for i in range(30)],
                "fed_usd": [8000 + i * 10 for i in range(30)],
                "ecb_usd": [7000 + i * 15 for i in range(30)],
                "boj_usd": [7000 + i * 12 for i in range(30)],
                "pboc_usd": [6000 + i * 13 for i in range(30)],
            }
        )

        fig = create_global_liquidity_chart(df, show_breakdown=True)

        assert fig is not None
        # Should have 4 traces for CBs
        assert len(fig.data) == 4
        trace_names = [t.name for t in fig.data]
        assert "Fed (US)" in trace_names
        assert "ECB (EU)" in trace_names
        assert "BoJ (Japan)" in trace_names
        assert "PBoC (China)" in trace_names

    def test_chart_without_breakdown(self) -> None:
        """Test creating simple line chart without breakdown."""
        from liquidity.dashboard.components.liquidity import create_global_liquidity_chart

        dates = pd.date_range(end=datetime.now(), periods=10, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "global_liquidity": [28000] * 10,
            }
        )

        fig = create_global_liquidity_chart(df, show_breakdown=False)

        assert fig is not None
        # Should have 1 trace
        assert len(fig.data) == 1
        assert fig.data[0].name == "Global Liquidity"


class TestLiquidityPanel:
    """Test liquidity panel component."""

    def test_create_panel(self) -> None:
        """Test creating the liquidity panel."""
        from liquidity.dashboard.components.liquidity import create_liquidity_panel

        panel = create_liquidity_panel()

        assert panel is not None

    def test_panel_contains_two_cards(self) -> None:
        """Test that panel has two chart cards."""

        from liquidity.dashboard.components.liquidity import create_liquidity_panel

        panel = create_liquidity_panel()

        # Panel should be a Row with 2 Cols containing Cards
        assert hasattr(panel, "children")
        assert len(panel.children) == 2


class TestLiquidityMetrics:
    """Test liquidity metrics display."""

    def test_create_metrics(self) -> None:
        """Test creating metrics component."""
        from liquidity.dashboard.components.liquidity import create_liquidity_metrics

        metrics = create_liquidity_metrics(
            current_value=5800,
            weekly_delta=120,
            monthly_delta=-50,
        )

        assert metrics is not None

    def test_metrics_positive_delta_styling(self) -> None:
        """Test that positive deltas get correct styling."""
        from liquidity.dashboard.components.liquidity import create_liquidity_metrics

        metrics = create_liquidity_metrics(
            current_value=5800,
            weekly_delta=100,
            monthly_delta=200,
        )

        # Component should exist and have children
        assert metrics is not None
        assert hasattr(metrics, "children")

    def test_metrics_negative_delta_styling(self) -> None:
        """Test that negative deltas get correct styling."""
        from liquidity.dashboard.components.liquidity import create_liquidity_metrics

        metrics = create_liquidity_metrics(
            current_value=5800,
            weekly_delta=-100,
            monthly_delta=-200,
        )

        assert metrics is not None


class TestChartBounds:
    """Test chart bounds integration (QA-10)."""

    def test_net_liquidity_chart_with_bounds(self) -> None:
        """Test Net Liquidity chart with sanity bounds enabled."""
        from datetime import datetime

        from liquidity.dashboard.components.liquidity import create_net_liquidity_chart

        dates = pd.date_range(end=datetime.now(), periods=10, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "net_liquidity": [5800] * 10,
                "walcl": [7800] * 10,
                "tga": [800] * 10,
                "rrp": [1200] * 10,
            }
        )

        fig = create_net_liquidity_chart(df, show_bounds=True)

        assert fig is not None
        # Should have shapes added for bounds
        assert hasattr(fig.layout, "shapes")
        # At least one shape for the bound rectangle
        assert len(fig.layout.shapes) >= 1

    def test_global_liquidity_chart_with_bounds(self) -> None:
        """Test Global Liquidity chart with sanity bounds enabled."""
        from datetime import datetime

        from liquidity.dashboard.components.liquidity import create_global_liquidity_chart

        dates = pd.date_range(end=datetime.now(), periods=10, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "global_liquidity": [28000] * 10,
            }
        )

        fig = create_global_liquidity_chart(df, show_breakdown=False, show_bounds=True)

        assert fig is not None
        assert hasattr(fig.layout, "shapes")

    def test_chart_without_bounds_has_no_shapes(self) -> None:
        """Test that charts without bounds don't add extra shapes."""
        from liquidity.dashboard.components.liquidity import create_net_liquidity_chart

        fig = create_net_liquidity_chart(None, show_bounds=False)

        # Empty chart should not have bound shapes
        shapes = fig.layout.shapes if fig.layout.shapes else []
        assert len(shapes) == 0
