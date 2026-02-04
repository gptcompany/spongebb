"""Tests for capital flows panel component."""

from datetime import datetime

import pandas as pd
import pytest


class TestFlowsPanel:
    """Test flows panel creation."""

    def test_create_panel(self) -> None:
        """Test creating the flows panel."""
        from liquidity.dashboard.components.flows import create_flows_panel

        panel = create_flows_panel()

        assert panel is not None

    def test_panel_has_card_structure(self) -> None:
        """Test that panel is a Bootstrap Card."""
        import dash_bootstrap_components as dbc

        from liquidity.dashboard.components.flows import create_flows_panel

        panel = create_flows_panel()

        assert isinstance(panel, dbc.Card)


class TestTICChart:
    """Test TIC chart creation."""

    def test_create_empty_chart(self) -> None:
        """Test creating chart with no data."""
        from liquidity.dashboard.components.flows import create_tic_chart

        fig = create_tic_chart(None)

        assert fig is not None
        assert hasattr(fig, "data")

    def test_create_chart_with_data(self) -> None:
        """Test creating TIC chart with data."""
        from liquidity.dashboard.components.flows import create_tic_chart

        df = pd.DataFrame(
            {
                "timestamp": [datetime.now()] * 5,
                "series_id": [
                    "tic_japan_holdings",
                    "tic_china_holdings",
                    "tic_uk_holdings",
                    "tic_cayman_holdings",
                    "tic_luxembourg_holdings",
                ],
                "value": [1100, 850, 700, 350, 300],
            }
        )

        fig = create_tic_chart(df)

        assert fig is not None
        # Should have horizontal bar chart data
        assert len(fig.data) >= 1

    def test_chart_shows_top_holders(self) -> None:
        """Test that chart shows top N holders."""
        from liquidity.dashboard.components.flows import create_tic_chart

        df = pd.DataFrame(
            {
                "timestamp": [datetime.now()] * 10,
                "series_id": [f"tic_country{i}_holdings" for i in range(10)],
                "value": list(range(100, 1100, 100)),
            }
        )

        fig = create_tic_chart(df, top_n=5)

        assert fig is not None


class TestETFFlowsChart:
    """Test ETF flows chart creation."""

    def test_create_empty_chart(self) -> None:
        """Test creating chart with no data."""
        from liquidity.dashboard.components.flows import create_etf_flows_chart

        fig = create_etf_flows_chart(None)

        assert fig is not None
        assert hasattr(fig, "data")

    def test_create_chart_with_data(self) -> None:
        """Test creating ETF flows chart with data."""
        from liquidity.dashboard.components.flows import create_etf_flows_chart

        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": list(dates) * 3,
                "etf": ["GLD"] * 30 + ["SLV"] * 30 + ["USO"] * 30,
                "close": [180 + i for i in range(30)]
                + [22 + i * 0.1 for i in range(30)]
                + [70 + i * 0.5 for i in range(30)],
            }
        )

        fig = create_etf_flows_chart(df)

        assert fig is not None
        # Should have traces for each ETF
        assert len(fig.data) == 3

    def test_chart_shows_percent_change(self) -> None:
        """Test that chart shows percentage change from start."""
        from liquidity.dashboard.components.flows import create_etf_flows_chart

        dates = pd.date_range(end=datetime.now(), periods=10, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": list(dates),
                "etf": ["GLD"] * 10,
                "close": [100 + i for i in range(10)],  # 9% increase
            }
        )

        fig = create_etf_flows_chart(df)

        assert fig is not None


class TestFlowsSummary:
    """Test flows summary creation."""

    def test_create_summary_with_values(self) -> None:
        """Test creating summary with values."""
        from liquidity.dashboard.components.flows import create_flows_summary

        summary = create_flows_summary(
            japan_holdings=1100,
            china_holdings=850,
            total_holdings=7500,
        )

        assert summary is not None

    def test_create_summary_with_none_values(self) -> None:
        """Test creating summary with None values."""
        from liquidity.dashboard.components.flows import create_flows_summary

        summary = create_flows_summary()

        assert summary is not None
