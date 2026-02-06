"""Unit tests for oil term structure dashboard component."""

from datetime import datetime, UTC

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import pytest

from liquidity.analyzers.term_structure import (
    CurveShape,
    RollYieldMetrics,
    TermStructureSignal,
)
from liquidity.dashboard.components.oil_term_structure import (
    create_curve_gauge,
    create_oil_term_structure_panel,
    create_price_chart,
    create_roll_yield_bars,
)


@pytest.fixture
def sample_signal():
    """Sample term structure signal."""
    return TermStructureSignal(
        timestamp=datetime.now(UTC),
        curve_shape=CurveShape.BACKWARDATION,
        intensity=65,
        roll_yield_proxy=12.5,
        momentum_5d=3.5,
        momentum_20d=2.8,
        confidence=0.75,
    )


@pytest.fixture
def sample_roll_yield():
    """Sample roll yield metrics."""
    return RollYieldMetrics(
        monthly_yield=15.0,
        quarterly_yield=12.0,
        annual_yield=10.0,
        yield_trend="IMPROVING",
        days_in_current_regime=8,
    )


@pytest.fixture
def sample_price_history():
    """Sample price history DataFrame."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    return pd.DataFrame([
        {"timestamp": d, "series_id": "wti_front", "value": 70 + i * 0.5, "source": "yf", "unit": "usd"}
        for i, d in enumerate(dates)
    ])


class TestCreatePanel:
    """Test main panel creation."""

    def test_returns_card(self, sample_signal, sample_roll_yield, sample_price_history):
        """Panel should return a Card component."""
        panel = create_oil_term_structure_panel(
            signal=sample_signal,
            roll_yield=sample_roll_yield,
            price_history=sample_price_history,
        )
        assert isinstance(panel, dbc.Card)

    def test_handles_none_inputs(self):
        """Panel should handle None inputs gracefully."""
        panel = create_oil_term_structure_panel()
        assert isinstance(panel, dbc.Card)

    def test_handles_partial_inputs(self, sample_signal):
        """Panel should handle partial inputs."""
        panel = create_oil_term_structure_panel(signal=sample_signal)
        assert isinstance(panel, dbc.Card)

    def test_panel_has_tabs(self, sample_signal):
        """Panel should contain tabs."""
        panel = create_oil_term_structure_panel(signal=sample_signal)
        # Check structure: Card -> [Header, Body]
        assert len(panel.children) == 2
        # Body should contain Tabs
        card_body = panel.children[1]
        assert isinstance(card_body, dbc.CardBody)


class TestCurveGauge:
    """Test gauge chart creation."""

    def test_returns_figure(self, sample_signal):
        """Should return a Plotly Figure."""
        fig = create_curve_gauge(sample_signal)
        assert isinstance(fig, go.Figure)

    def test_gauge_has_indicator(self, sample_signal):
        """Figure should have an indicator trace."""
        fig = create_curve_gauge(sample_signal)
        assert len(fig.data) == 1
        assert fig.data[0].type == "indicator"

    @pytest.mark.parametrize("shape,expected_sign", [
        (CurveShape.BACKWARDATION, -1),
        (CurveShape.CONTANGO, 1),
        (CurveShape.FLAT, 0),
    ])
    def test_gauge_value_direction(self, shape, expected_sign):
        """Gauge value should match curve shape direction."""
        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=shape,
            intensity=50,
            roll_yield_proxy=0,
            momentum_5d=0,
            momentum_20d=0,
            confidence=0.5,
        )
        fig = create_curve_gauge(signal)
        value = fig.data[0].value

        if expected_sign == 0:
            assert value == 0
        elif expected_sign > 0:
            assert value > 0
        else:
            assert value < 0

    def test_backwardation_negative_value(self):
        """Backwardation should show on left (negative value)."""
        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.BACKWARDATION,
            intensity=75,
            roll_yield_proxy=15,
            momentum_5d=5,
            momentum_20d=4,
            confidence=0.8,
        )
        fig = create_curve_gauge(signal)
        assert fig.data[0].value == -75

    def test_contango_positive_value(self):
        """Contango should show on right (positive value)."""
        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.CONTANGO,
            intensity=60,
            roll_yield_proxy=-10,
            momentum_5d=-4,
            momentum_20d=-3,
            confidence=0.7,
        )
        fig = create_curve_gauge(signal)
        assert fig.data[0].value == 60


class TestPriceChart:
    """Test price chart creation."""

    def test_returns_figure(self, sample_price_history):
        """Should return a Plotly Figure."""
        fig = create_price_chart(sample_price_history)
        assert isinstance(fig, go.Figure)

    def test_has_price_trace(self, sample_price_history):
        """Should have at least one trace for prices."""
        fig = create_price_chart(sample_price_history)
        assert len(fig.data) >= 1

    def test_has_moving_average(self, sample_price_history):
        """Should have moving average trace."""
        fig = create_price_chart(sample_price_history)
        # Two traces: price + MA
        assert len(fig.data) == 2
        assert "MA" in fig.data[1].name

    def test_empty_data_returns_empty_figure(self):
        """Empty DataFrame should return empty figure."""
        fig = create_price_chart(pd.DataFrame())
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0

    def test_missing_column_returns_empty(self):
        """DataFrame without series_id should return empty."""
        df = pd.DataFrame({"timestamp": [datetime.now()], "value": [75.0]})
        fig = create_price_chart(df)
        assert len(fig.data) == 0


class TestRollYieldBars:
    """Test roll yield bar chart."""

    def test_returns_figure(self, sample_roll_yield):
        """Should return a Plotly Figure."""
        fig = create_roll_yield_bars(sample_roll_yield)
        assert isinstance(fig, go.Figure)

    def test_has_bar_trace(self, sample_roll_yield):
        """Should have a bar trace."""
        fig = create_roll_yield_bars(sample_roll_yield)
        assert fig.data[0].type == "bar"

    def test_has_three_bars(self, sample_roll_yield):
        """Should have three bars for 1M, 3M, 12M."""
        fig = create_roll_yield_bars(sample_roll_yield)
        assert len(fig.data[0].x) == 3

    def test_positive_values_green(self, sample_roll_yield):
        """Positive values should be green."""
        fig = create_roll_yield_bars(sample_roll_yield)
        colors = fig.data[0].marker.color
        # All positive = all green
        assert all(c == "#2ca02c" for c in colors)

    def test_negative_values_red(self):
        """Negative values should be red."""
        roll_yield = RollYieldMetrics(
            monthly_yield=-10.0,
            quarterly_yield=-8.0,
            annual_yield=-12.0,
            yield_trend="DETERIORATING",
            days_in_current_regime=5,
        )
        fig = create_roll_yield_bars(roll_yield)
        colors = fig.data[0].marker.color
        assert all(c == "#d62728" for c in colors)

    def test_mixed_values_colors(self):
        """Mixed values should have mixed colors."""
        roll_yield = RollYieldMetrics(
            monthly_yield=10.0,
            quarterly_yield=-5.0,
            annual_yield=3.0,
            yield_trend="STABLE",
            days_in_current_regime=10,
        )
        fig = create_roll_yield_bars(roll_yield)
        colors = fig.data[0].marker.color
        assert colors[0] == "#2ca02c"  # Positive
        assert colors[1] == "#d62728"  # Negative
        assert colors[2] == "#2ca02c"  # Positive


class TestIntegration:
    """Test component integration."""

    def test_full_panel_with_all_data(
        self, sample_signal, sample_roll_yield, sample_price_history
    ):
        """Full panel with all data should work."""
        panel = create_oil_term_structure_panel(
            signal=sample_signal,
            roll_yield=sample_roll_yield,
            price_history=sample_price_history,
        )

        # Should be a complete Card
        assert isinstance(panel, dbc.Card)
        assert len(panel.children) == 2  # Header + Body

    def test_contango_signal_display(self):
        """Contango signal should display correctly."""
        signal = TermStructureSignal(
            timestamp=datetime.now(UTC),
            curve_shape=CurveShape.CONTANGO,
            intensity=80,
            roll_yield_proxy=-15.0,
            momentum_5d=-5.0,
            momentum_20d=-6.0,
            confidence=0.85,
        )

        panel = create_oil_term_structure_panel(signal=signal)
        assert isinstance(panel, dbc.Card)

        # Check gauge
        gauge = create_curve_gauge(signal)
        assert gauge.data[0].value == 80  # Positive for contango
