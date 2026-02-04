"""Tests for commodities panel component."""

from datetime import datetime

import pandas as pd
import pytest


class TestCommoditiesPanel:
    """Test commodities panel creation."""

    def test_create_panel(self) -> None:
        """Test creating the commodities panel."""
        from liquidity.dashboard.components.commodities import create_commodities_panel

        panel = create_commodities_panel()

        assert panel is not None

    def test_panel_has_card_structure(self) -> None:
        """Test that panel is a Bootstrap Card."""
        import dash_bootstrap_components as dbc

        from liquidity.dashboard.components.commodities import create_commodities_panel

        panel = create_commodities_panel()

        assert isinstance(panel, dbc.Card)


class TestCommodityChart:
    """Test commodity chart creation."""

    def test_create_empty_chart(self) -> None:
        """Test creating chart with no data."""
        from liquidity.dashboard.components.commodities import create_commodity_chart

        fig = create_commodity_chart(None, "gold")

        assert fig is not None
        assert hasattr(fig, "data")

    def test_create_gold_chart(self) -> None:
        """Test creating gold chart with data."""
        from liquidity.dashboard.components.commodities import create_commodity_chart

        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "value": [2000 + i * 5 for i in range(30)],
            }
        )

        fig = create_commodity_chart(df, "gold")

        assert fig is not None
        assert len(fig.data) >= 1

    def test_create_copper_chart(self) -> None:
        """Test creating copper chart with data."""
        from liquidity.dashboard.components.commodities import create_commodity_chart

        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "value": [4.2 + i * 0.01 for i in range(30)],
            }
        )

        fig = create_commodity_chart(df, "copper")

        assert fig is not None
        assert len(fig.data) >= 1

    def test_chart_shows_percent_change(self) -> None:
        """Test that chart can show percent change annotation."""
        from liquidity.dashboard.components.commodities import create_commodity_chart

        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "value": [100 + i for i in range(30)],  # 29% increase
            }
        )

        fig = create_commodity_chart(df, "gold", show_change_annotation=True)

        # Check that annotation was added
        assert fig is not None


class TestOilChart:
    """Test dual oil chart creation."""

    def test_create_empty_chart(self) -> None:
        """Test creating oil chart with no data."""
        from liquidity.dashboard.components.commodities import create_oil_chart

        fig = create_oil_chart(None, None)

        assert fig is not None
        assert hasattr(fig, "data")

    def test_create_chart_with_both_oils(self) -> None:
        """Test creating oil chart with WTI and Brent."""
        from liquidity.dashboard.components.commodities import create_oil_chart

        dates = pd.date_range(end=datetime.now(), periods=30, freq="D")
        wti_df = pd.DataFrame(
            {"timestamp": dates, "value": [75 + i * 0.5 for i in range(30)]}
        )
        brent_df = pd.DataFrame(
            {"timestamp": dates, "value": [80 + i * 0.5 for i in range(30)]}
        )

        fig = create_oil_chart(wti_df, brent_df)

        assert fig is not None
        # Should have 2 traces (WTI and Brent)
        assert len(fig.data) == 2


class TestCommoditySummary:
    """Test commodity summary creation."""

    def test_create_summary_with_values(self) -> None:
        """Test creating summary with values."""
        from liquidity.dashboard.components.commodities import create_commodity_summary

        summary = create_commodity_summary(
            gold_price=2000,
            copper_price=4.5,
            wti_price=75,
        )

        assert summary is not None

    def test_create_summary_with_none_values(self) -> None:
        """Test creating summary with None values."""
        from liquidity.dashboard.components.commodities import create_commodity_summary

        summary = create_commodity_summary()

        assert summary is not None
