"""Tests for stress indicators panel component."""



class TestStressPanel:
    """Test stress panel creation."""

    def test_create_panel(self) -> None:
        """Test creating the stress panel."""
        from liquidity.dashboard.components.stress import create_stress_panel

        panel = create_stress_panel()

        assert panel is not None

    def test_panel_has_card_structure(self) -> None:
        """Test that panel is a Bootstrap Card."""
        import dash_bootstrap_components as dbc

        from liquidity.dashboard.components.stress import create_stress_panel

        panel = create_stress_panel()

        assert isinstance(panel, dbc.Card)


class TestStressGauge:
    """Test stress gauge creation."""

    def test_create_gauge_with_value(self) -> None:
        """Test creating gauge with value."""
        from liquidity.dashboard.components.stress import create_stress_gauge

        fig = create_stress_gauge(
            value=15,
            label="Test",
            thresholds={"green": 10, "yellow": 25},
        )

        assert fig is not None
        assert hasattr(fig, "data")
        assert len(fig.data) == 1
        assert fig.data[0].value == 15

    def test_create_sofr_ois_gauge(self) -> None:
        """Test creating SOFR-OIS gauge."""
        from liquidity.dashboard.components.stress import create_sofr_ois_gauge

        fig = create_sofr_ois_gauge(value=8.5)

        assert fig is not None
        assert fig.data[0].value == 8.5

    def test_create_repo_stress_gauge(self) -> None:
        """Test creating repo stress gauge."""
        from liquidity.dashboard.components.stress import create_repo_stress_gauge

        fig = create_repo_stress_gauge(value=1.5)

        assert fig is not None
        assert fig.data[0].value == 1.5

    def test_gauge_with_none_value(self) -> None:
        """Test creating gauge with None value."""
        from liquidity.dashboard.components.stress import create_sofr_ois_gauge

        fig = create_sofr_ois_gauge(value=None)

        assert fig is not None
        assert fig.data[0].value == 0


class TestStressColor:
    """Test stress color determination."""

    def test_green_when_below_green_threshold(self) -> None:
        """Test returns green color when value is below green threshold."""
        from liquidity.dashboard.components.stress import STRESS_COLORS, get_stress_color

        color = get_stress_color(5, {"green": 10, "yellow": 25})

        assert color == STRESS_COLORS["GREEN"]

    def test_yellow_when_between_thresholds(self) -> None:
        """Test returns yellow color when value is between thresholds."""
        from liquidity.dashboard.components.stress import STRESS_COLORS, get_stress_color

        color = get_stress_color(15, {"green": 10, "yellow": 25})

        assert color == STRESS_COLORS["YELLOW"]

    def test_red_when_above_yellow_threshold(self) -> None:
        """Test returns red color when value is above yellow threshold."""
        from liquidity.dashboard.components.stress import STRESS_COLORS, get_stress_color

        color = get_stress_color(30, {"green": 10, "yellow": 25})

        assert color == STRESS_COLORS["RED"]


class TestStressStatus:
    """Test stress status creation."""

    def test_create_green_status(self) -> None:
        """Test creating green stress status."""
        from liquidity.dashboard.components.stress import create_stress_status

        status = create_stress_status(regime="GREEN")

        assert status is not None

    def test_create_yellow_status(self) -> None:
        """Test creating yellow stress status."""
        from liquidity.dashboard.components.stress import create_stress_status

        status = create_stress_status(regime="YELLOW")

        assert status is not None

    def test_create_red_status(self) -> None:
        """Test creating red stress status."""
        from liquidity.dashboard.components.stress import create_stress_status

        status = create_stress_status(regime="RED")

        assert status is not None


class TestOverallRegime:
    """Test overall stress regime determination."""

    def test_green_when_all_indicators_normal(self) -> None:
        """Test returns GREEN when all indicators are below green thresholds."""
        from liquidity.dashboard.components.stress import get_overall_regime

        regime = get_overall_regime(
            sofr_ois=5,  # Below 10 (green threshold)
            repo_stress=0.5,  # Below 1 (green threshold)
        )

        assert regime == "GREEN"

    def test_yellow_when_any_indicator_elevated(self) -> None:
        """Test returns YELLOW when any indicator is between green and yellow."""
        from liquidity.dashboard.components.stress import get_overall_regime

        regime = get_overall_regime(
            sofr_ois=15,  # Between 10 and 25
            repo_stress=0.5,  # Below 1
        )

        assert regime == "YELLOW"

    def test_red_when_any_indicator_critical(self) -> None:
        """Test returns RED when any indicator exceeds yellow threshold."""
        from liquidity.dashboard.components.stress import get_overall_regime

        regime = get_overall_regime(
            sofr_ois=30,  # Above 25
            repo_stress=0.5,  # Below 1
        )

        assert regime == "RED"

    def test_handles_none_values(self) -> None:
        """Test handles None values gracefully."""
        from liquidity.dashboard.components.stress import get_overall_regime

        regime = get_overall_regime(
            sofr_ois=None,
            repo_stress=None,
        )

        # Should return GREEN when no data (default)
        assert regime == "GREEN"
