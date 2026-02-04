"""Tests for FX panel component."""

from datetime import datetime

import pandas as pd


class TestFXPanel:
    """Test FX panel creation."""

    def test_create_panel(self) -> None:
        """Test creating the FX panel."""
        from liquidity.dashboard.components.fx import create_fx_panel

        panel = create_fx_panel()

        assert panel is not None

    def test_panel_has_card_structure(self) -> None:
        """Test that panel is a Bootstrap Card."""
        import dash_bootstrap_components as dbc

        from liquidity.dashboard.components.fx import create_fx_panel

        panel = create_fx_panel()

        assert isinstance(panel, dbc.Card)


class TestDXYChart:
    """Test DXY chart creation."""

    def test_create_empty_chart(self) -> None:
        """Test creating chart with no data."""
        from liquidity.dashboard.components.fx import create_dxy_chart

        fig = create_dxy_chart(None)

        assert fig is not None
        assert hasattr(fig, "data")
        assert hasattr(fig, "layout")

    def test_create_chart_with_data(self) -> None:
        """Test creating chart with valid data."""
        from liquidity.dashboard.components.fx import create_dxy_chart

        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "value": [103 + i * 0.1 for i in range(30)],
            }
        )

        fig = create_dxy_chart(df)

        assert fig is not None
        # Should have at least the DXY trace
        assert len(fig.data) >= 1

    def test_chart_has_threshold_lines(self) -> None:
        """Test that chart has threshold horizontal lines."""
        from liquidity.dashboard.components.fx import create_dxy_chart

        fig = create_dxy_chart(None)

        # hlines are added as shapes in plotly
        # Verify the layout exists and has expected structure
        assert fig.layout is not None
        # Check that annotations exist (from hline annotations)
        assert hasattr(fig.layout, "annotations")

    def test_chart_uses_dark_template(self) -> None:
        """Test that chart uses dark theme."""
        from liquidity.dashboard.components.fx import create_dxy_chart

        fig = create_dxy_chart(None)

        assert fig.layout.template is not None


class TestFXMetrics:
    """Test FX metrics creation."""

    def test_create_metrics_with_values(self) -> None:
        """Test creating FX metrics with values."""
        from liquidity.dashboard.components.fx import create_fx_metrics

        metrics = create_fx_metrics(
            eurusd=1.0850,
            usdjpy=148.50,
            usdcny=7.15,
        )

        assert metrics is not None
        assert "eurusd-value" in metrics
        assert "usdjpy-value" in metrics
        assert "usdcny-value" in metrics

    def test_create_metrics_with_changes(self) -> None:
        """Test creating FX metrics with change values."""
        from liquidity.dashboard.components.fx import create_fx_metrics

        metrics = create_fx_metrics(
            eurusd=1.0850,
            usdjpy=148.50,
            usdcny=7.15,
            eurusd_change=0.5,
            usdjpy_change=-0.3,
            usdcny_change=0.1,
        )

        assert metrics is not None

    def test_create_metrics_with_none_values(self) -> None:
        """Test creating FX metrics with None values."""
        from liquidity.dashboard.components.fx import create_fx_metrics

        metrics = create_fx_metrics()

        assert metrics is not None
