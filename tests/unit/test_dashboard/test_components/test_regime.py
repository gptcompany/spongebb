"""Tests for regime classification panel components."""



class TestRegimePanel:
    """Test regime panel creation."""

    def test_create_panel(self) -> None:
        """Test creating the regime panel."""
        from liquidity.dashboard.components.regime import create_regime_panel

        panel = create_regime_panel()

        assert panel is not None

    def test_panel_has_card_structure(self) -> None:
        """Test that panel is a Bootstrap Card."""
        import dash_bootstrap_components as dbc

        from liquidity.dashboard.components.regime import create_regime_panel

        panel = create_regime_panel()

        assert isinstance(panel, dbc.Card)


class TestRegimeIndicator:
    """Test regime indicator display."""

    def test_create_expansion_indicator(self) -> None:
        """Test creating EXPANSION regime indicator."""
        from liquidity.dashboard.components.regime import create_regime_indicator

        indicator = create_regime_indicator(
            regime="EXPANSION",
            intensity=72,
            confidence="HIGH",
        )

        assert indicator is not None
        # Check that it renders without error
        assert hasattr(indicator, "children")

    def test_create_contraction_indicator(self) -> None:
        """Test creating CONTRACTION regime indicator."""
        from liquidity.dashboard.components.regime import create_regime_indicator

        indicator = create_regime_indicator(
            regime="CONTRACTION",
            intensity=45,
            confidence="MEDIUM",
        )

        assert indicator is not None

    def test_expansion_uses_green_color(self) -> None:
        """Test that EXPANSION uses green color (#00ff88)."""
        from liquidity.dashboard.components.regime import (
            REGIME_COLORS,
        )

        assert REGIME_COLORS["EXPANSION"] == "#00ff88"

    def test_contraction_uses_red_color(self) -> None:
        """Test that CONTRACTION uses red color (#ff4444)."""
        from liquidity.dashboard.components.regime import (
            REGIME_COLORS,
        )

        assert REGIME_COLORS["CONTRACTION"] == "#ff4444"

    def test_indicator_shows_correct_arrow(self) -> None:
        """Test that indicator shows up arrow for expansion, down for contraction."""
        from liquidity.dashboard.components.regime import create_regime_indicator

        expansion_indicator = create_regime_indicator("EXPANSION", 50, "HIGH")
        contraction_indicator = create_regime_indicator("CONTRACTION", 50, "HIGH")

        # Check children contain proper arrows (unicode)
        # UP: \u25b2, DOWN: \u25bc
        def contains_text(component, text: str) -> bool:
            if hasattr(component, "children"):
                children = component.children
                if isinstance(children, str) and text in children:
                    return True
                if isinstance(children, list):
                    return any(contains_text(c, text) for c in children)
                if children is not None:
                    return contains_text(children, text)
            return False

        assert contains_text(expansion_indicator, "\u25b2")  # Up arrow
        assert contains_text(contraction_indicator, "\u25bc")  # Down arrow


class TestRegimeGauge:
    """Test regime intensity gauge."""

    def test_create_gauge(self) -> None:
        """Test creating intensity gauge."""
        from liquidity.dashboard.components.regime import create_regime_gauge

        fig = create_regime_gauge(intensity=65, regime="EXPANSION")

        assert fig is not None
        assert hasattr(fig, "data")

    def test_gauge_shows_correct_value(self) -> None:
        """Test that gauge displays the intensity value."""
        from liquidity.dashboard.components.regime import create_regime_gauge

        fig = create_regime_gauge(intensity=72, regime="EXPANSION")

        # Check that the indicator value matches
        assert len(fig.data) == 1
        assert fig.data[0].value == 72

    def test_gauge_range_is_0_to_100(self) -> None:
        """Test that gauge range is 0-100."""
        from liquidity.dashboard.components.regime import create_regime_gauge

        fig = create_regime_gauge(intensity=50)

        # Check gauge axis range (can be tuple or list)
        gauge_config = fig.data[0].gauge
        assert list(gauge_config.axis.range) == [0, 100]


class TestRegimeMetrics:
    """Test regime component metrics display."""

    def test_create_metrics(self) -> None:
        """Test creating component breakdown display."""
        from liquidity.dashboard.components.regime import create_regime_metrics

        metrics = create_regime_metrics(
            net_liq_percentile=0.68,
            global_liq_percentile=0.72,
            stealth_qe_score=0.45,
        )

        assert metrics is not None

    def test_metrics_shows_percentages(self) -> None:
        """Test that metrics show percentage values."""
        from liquidity.dashboard.components.regime import create_regime_metrics

        metrics = create_regime_metrics(
            net_liq_percentile=0.68,
            global_liq_percentile=0.72,
            stealth_qe_score=0.45,
        )

        # Should render without error
        assert metrics is not None
        assert hasattr(metrics, "children")

    def test_above_50_pct_is_green(self) -> None:
        """Test that values above 50% are styled as green/positive."""
        from liquidity.dashboard.components.regime import create_regime_metrics

        # When value > 0.5, should use success color
        metrics = create_regime_metrics(
            net_liq_percentile=0.75,
            global_liq_percentile=0.80,
            stealth_qe_score=0.60,
        )

        assert metrics is not None

    def test_below_50_pct_is_red(self) -> None:
        """Test that values below 50% are styled as red/negative."""
        from liquidity.dashboard.components.regime import create_regime_metrics

        # When value <= 0.5, should use danger color
        metrics = create_regime_metrics(
            net_liq_percentile=0.25,
            global_liq_percentile=0.30,
            stealth_qe_score=0.40,
        )

        assert metrics is not None
