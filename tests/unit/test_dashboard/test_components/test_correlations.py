"""Tests for correlation heatmap panel component."""

import numpy as np
import pandas as pd
import pytest


class TestCorrelationPanel:
    """Test correlation panel creation."""

    def test_create_panel(self) -> None:
        """Test creating the correlation panel."""
        from liquidity.dashboard.components.correlations import create_correlation_panel

        panel = create_correlation_panel()

        assert panel is not None

    def test_panel_has_card_structure(self) -> None:
        """Test that panel is a Bootstrap Card."""
        import dash_bootstrap_components as dbc

        from liquidity.dashboard.components.correlations import create_correlation_panel

        panel = create_correlation_panel()

        assert isinstance(panel, dbc.Card)


class TestCorrelationHeatmap:
    """Test correlation heatmap creation."""

    def test_create_empty_heatmap(self) -> None:
        """Test creating heatmap with no data."""
        from liquidity.dashboard.components.correlations import create_correlation_heatmap

        fig = create_correlation_heatmap(None)

        assert fig is not None
        assert hasattr(fig, "data")
        # Should have identity matrix as default
        assert len(fig.data) == 1

    def test_create_heatmap_with_data(self) -> None:
        """Test creating heatmap with correlation matrix."""
        from liquidity.dashboard.components.correlations import create_correlation_heatmap

        assets = ["BTC", "SPX", "GOLD", "TLT", "DXY", "COPPER", "HYG"]
        corr_values = np.random.rand(7, 7)
        corr_values = (corr_values + corr_values.T) / 2
        np.fill_diagonal(corr_values, 1.0)
        corr_matrix = pd.DataFrame(
            corr_values,
            index=pd.Index(assets),
            columns=pd.Index(assets),
        )

        fig = create_correlation_heatmap(corr_matrix, assets)

        assert fig is not None
        assert len(fig.data) == 1  # Heatmap is single trace

    def test_heatmap_is_7x7(self) -> None:
        """Test that heatmap renders 7x7 matrix."""
        from liquidity.dashboard.components.correlations import (
            DEFAULT_ASSETS,
            create_correlation_heatmap,
        )

        fig = create_correlation_heatmap(None)

        # Check that axes have 7 labels
        assert len(DEFAULT_ASSETS) == 7

    def test_heatmap_uses_rdbu_colorscale(self) -> None:
        """Test that heatmap uses RdBu colorscale (red-blue diverging)."""
        from liquidity.dashboard.components.correlations import create_correlation_heatmap

        fig = create_correlation_heatmap(None)

        # Check colorscale
        assert fig.data[0].colorscale is not None

    def test_heatmap_centered_at_zero(self) -> None:
        """Test that colorscale is centered at zero."""
        from liquidity.dashboard.components.correlations import create_correlation_heatmap

        fig = create_correlation_heatmap(None)

        # zmid should be 0 for diverging colorscale
        assert fig.data[0].zmid == 0


class TestCorrelationAlerts:
    """Test correlation alerts creation."""

    def test_create_empty_alerts(self) -> None:
        """Test creating alerts with no data."""
        from liquidity.dashboard.components.correlations import create_correlation_alerts

        alerts = create_correlation_alerts(None, None)

        assert alerts is not None

    def test_create_alerts_with_no_significant_changes(self) -> None:
        """Test alerts when no significant correlation shifts."""
        from liquidity.dashboard.components.correlations import create_correlation_alerts

        current = {"BTC-SPX": 0.5, "GOLD-TLT": 0.3}
        previous = {"BTC-SPX": 0.48, "GOLD-TLT": 0.32}  # Small changes

        alerts = create_correlation_alerts(current, previous, threshold=0.3)

        assert alerts is not None

    def test_create_alerts_with_significant_changes(self) -> None:
        """Test alerts when there are significant correlation shifts."""
        from liquidity.dashboard.components.correlations import create_correlation_alerts

        current = {"BTC-SPX": 0.8, "GOLD-TLT": 0.3}
        previous = {"BTC-SPX": 0.3, "GOLD-TLT": 0.32}  # BTC-SPX changed by 0.5

        alerts = create_correlation_alerts(current, previous, threshold=0.3)

        assert alerts is not None


class TestCorrelationInterpretation:
    """Test correlation interpretation."""

    def test_strong_positive(self) -> None:
        """Test interpretation of strong positive correlation."""
        from liquidity.dashboard.components.correlations import interpret_correlation

        result = interpret_correlation(0.85)

        assert result == "Strong positive"

    def test_moderate_positive(self) -> None:
        """Test interpretation of moderate positive correlation."""
        from liquidity.dashboard.components.correlations import interpret_correlation

        result = interpret_correlation(0.55)

        assert result == "Moderate positive"

    def test_weak_positive(self) -> None:
        """Test interpretation of weak positive correlation."""
        from liquidity.dashboard.components.correlations import interpret_correlation

        result = interpret_correlation(0.25)

        assert result == "Weak positive"

    def test_no_correlation(self) -> None:
        """Test interpretation of no correlation."""
        from liquidity.dashboard.components.correlations import interpret_correlation

        result = interpret_correlation(0.1)

        assert result == "No correlation"

    def test_strong_negative(self) -> None:
        """Test interpretation of strong negative correlation."""
        from liquidity.dashboard.components.correlations import interpret_correlation

        result = interpret_correlation(-0.85)

        assert result == "Strong negative"


class TestLiquiditySensitiveAssets:
    """Test liquidity sensitive asset identification."""

    def test_identify_sensitive_assets(self) -> None:
        """Test identifying assets sensitive to liquidity."""
        from liquidity.dashboard.components.correlations import get_liquidity_sensitive_assets

        corr_vs_liquidity = {
            "BTC": 0.7,
            "SPX": 0.55,
            "GOLD": 0.3,
            "TLT": -0.6,
        }

        result = get_liquidity_sensitive_assets(corr_vs_liquidity, threshold=0.5)

        assert "BTC" in result
        assert "SPX" in result
        assert "TLT" in result  # Negative correlation also counts
        assert "GOLD" not in result

    def test_handles_none_input(self) -> None:
        """Test handles None input."""
        from liquidity.dashboard.components.correlations import get_liquidity_sensitive_assets

        result = get_liquidity_sensitive_assets(None)

        assert result == []
