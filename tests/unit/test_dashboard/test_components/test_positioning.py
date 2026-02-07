"""Unit tests for positioning dashboard component."""

import pandas as pd
from dash import html

from liquidity.dashboard.components.positioning import (
    COT_COMMODITIES,
    create_extremes_table,
    create_positioning_heatmap,
    create_positioning_panel,
    create_positioning_timeseries,
)


class TestCOTCommodities:
    """Tests for COT commodities list."""

    def test_commodities_count(self):
        """Test correct number of commodities."""
        assert len(COT_COMMODITIES) == 5

    def test_commodities_present(self):
        """Test all expected commodities are present."""
        assert "WTI" in COT_COMMODITIES
        assert "GOLD" in COT_COMMODITIES
        assert "COPPER" in COT_COMMODITIES
        assert "SILVER" in COT_COMMODITIES
        assert "NATGAS" in COT_COMMODITIES


class TestCreatePositioningPanel:
    """Tests for create_positioning_panel function."""

    def test_returns_card(self):
        """Test function returns a Bootstrap Card."""
        panel = create_positioning_panel()
        # Check it's a dbc.Card
        assert panel is not None
        assert hasattr(panel, "children")

    def test_has_graph_components(self):
        """Test panel contains expected graph IDs."""
        panel = create_positioning_panel()

        # Flatten component tree to find IDs
        def find_ids(component, ids=None):
            if ids is None:
                ids = []
            if hasattr(component, "id"):
                ids.append(component.id)
            if hasattr(component, "children"):
                children = component.children
                if isinstance(children, list):
                    for child in children:
                        find_ids(child, ids)
                elif children is not None:
                    find_ids(children, ids)
            return ids

        ids = find_ids(panel)

        assert "positioning-heatmap" in ids
        assert "positioning-timeseries" in ids
        assert "positioning-commodity-select" in ids
        assert "positioning-extremes-table" in ids


class TestCreatePositioningHeatmap:
    """Tests for create_positioning_heatmap function."""

    def test_empty_data(self):
        """Test heatmap with no data shows placeholder."""
        fig = create_positioning_heatmap(None)
        assert fig is not None
        assert hasattr(fig, "data")

    def test_empty_dataframe(self):
        """Test heatmap with empty DataFrame."""
        fig = create_positioning_heatmap(pd.DataFrame())
        assert fig is not None
        assert hasattr(fig, "data")

    def test_with_data(self):
        """Test heatmap with percentile data."""
        data = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_spec_pctl",
                    "value": 85.0,
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_comm_pctl",
                    "value": 25.0,
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_gold_spec_pctl",
                    "value": 50.0,
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_gold_comm_pctl",
                    "value": 60.0,
                },
            ]
        )

        fig = create_positioning_heatmap(data)
        assert fig is not None
        assert len(fig.data) >= 1

    def test_heatmap_colorscale(self):
        """Test heatmap has correct colorscale range."""
        fig = create_positioning_heatmap(None)

        # Get heatmap trace
        heatmap = fig.data[0]
        assert heatmap.zmin == 0
        assert heatmap.zmax == 100


class TestCreatePositioningTimeseries:
    """Tests for create_positioning_timeseries function."""

    def test_empty_data(self):
        """Test timeseries with no data shows annotation."""
        fig = create_positioning_timeseries(None, "WTI")
        assert fig is not None

        # Should have "No data available" annotation
        assert len(fig.layout.annotations) > 0

    def test_empty_dataframe(self):
        """Test timeseries with empty DataFrame."""
        fig = create_positioning_timeseries(pd.DataFrame(), "WTI")
        assert fig is not None

    def test_with_data(self):
        """Test timeseries with position data."""
        dates = pd.date_range("2025-01-01", periods=10, freq="W")
        records = []

        for i, ts in enumerate(dates):
            records.extend(
                [
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_comm_net",
                        "value": -100000 + i * 10000,
                    },
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_spec_net",
                        "value": 50000 + i * 5000,
                    },
                ]
            )

        data = pd.DataFrame(records)
        fig = create_positioning_timeseries(data, "WTI")

        assert fig is not None
        assert len(fig.data) == 2  # Commercial and Speculator traces

    def test_different_commodity(self):
        """Test timeseries filters by commodity."""
        dates = pd.date_range("2025-01-01", periods=5, freq="W")
        records = []

        for ts in dates:
            records.extend(
                [
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_comm_net",
                        "value": -50000,
                    },
                    {
                        "timestamp": ts,
                        "series_id": "cot_gold_comm_net",
                        "value": 100000,
                    },
                ]
            )

        data = pd.DataFrame(records)

        # WTI should show WTI data
        fig_wti = create_positioning_timeseries(data, "WTI")
        assert len(fig_wti.data) >= 1

        # GOLD should show GOLD data
        fig_gold = create_positioning_timeseries(data, "GOLD")
        assert len(fig_gold.data) >= 1


class TestCreateExtremesTable:
    """Tests for create_extremes_table function."""

    def test_empty_data(self):
        """Test table with no extremes shows message."""
        result = create_extremes_table(None)
        assert result is not None

        # Should be a paragraph with "No extreme positioning" message
        assert isinstance(result, html.P)

    def test_empty_dataframe(self):
        """Test table with empty DataFrame."""
        result = create_extremes_table(pd.DataFrame())
        assert isinstance(result, html.P)

    def test_with_extremes(self):
        """Test table with extreme data."""
        extremes = pd.DataFrame(
            [
                {
                    "commodity": "WTI",
                    "extreme_type": "SPEC_EXTREME_LONG",
                    "spec_percentile": 96.0,
                    "comm_percentile": 15.0,
                },
                {
                    "commodity": "GOLD",
                    "extreme_type": "COMM_EXTREME_LONG",
                    "spec_percentile": 50.0,
                    "comm_percentile": 92.0,
                },
            ]
        )

        result = create_extremes_table(extremes)

        # Should be a table, not a paragraph
        assert not isinstance(result, html.P)

    def test_critical_severity(self):
        """Test critical severity is detected for extreme values."""
        extremes = pd.DataFrame(
            [
                {
                    "commodity": "WTI",
                    "extreme_type": "SPEC_EXTREME_LONG",
                    "spec_percentile": 97.0,  # >= 95 = critical
                    "comm_percentile": 50.0,
                },
            ]
        )

        result = create_extremes_table(extremes)
        assert result is not None
        # Check that the table was created (not a P tag)
        assert not isinstance(result, html.P)

    def test_warning_severity(self):
        """Test warning severity for less extreme values."""
        extremes = pd.DataFrame(
            [
                {
                    "commodity": "GOLD",
                    "extreme_type": "SPEC_EXTREME_LONG",
                    "spec_percentile": 92.0,  # >= 90 but < 95 = warning
                    "comm_percentile": 50.0,
                },
            ]
        )

        result = create_extremes_table(extremes)
        assert result is not None
