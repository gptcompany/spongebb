"""Tests for dashboard callbacks."""

import pytest


class TestMockDataFunctions:
    """Test mock data generation functions."""

    def test_get_mock_data_returns_valid_structure(self) -> None:
        """Test that mock data has all required keys."""
        from liquidity.dashboard.callbacks import _get_mock_data

        data = _get_mock_data()

        assert "net_liquidity_df" in data
        assert "global_liquidity_df" in data
        assert "regime" in data
        assert "net_metrics" in data
        assert "global_metrics" in data
        assert "quality_score" in data

    def test_mock_net_liquidity_df_has_required_columns(self) -> None:
        """Test that net liquidity mock DataFrame has correct columns."""
        from liquidity.dashboard.callbacks import _get_mock_data

        data = _get_mock_data()
        df = data["net_liquidity_df"]

        assert "timestamp" in df.columns
        assert "net_liquidity" in df.columns
        assert "walcl" in df.columns
        assert "tga" in df.columns
        assert "rrp" in df.columns

    def test_mock_global_liquidity_df_has_required_columns(self) -> None:
        """Test that global liquidity mock DataFrame has correct columns."""
        from liquidity.dashboard.callbacks import _get_mock_data

        data = _get_mock_data()
        df = data["global_liquidity_df"]

        assert "timestamp" in df.columns
        assert "global_liquidity" in df.columns
        assert "fed_usd" in df.columns
        assert "ecb_usd" in df.columns
        assert "boj_usd" in df.columns
        assert "pboc_usd" in df.columns

    def test_mock_regime_has_required_fields(self) -> None:
        """Test that regime mock data has all required fields."""
        from liquidity.dashboard.callbacks import _get_mock_data

        data = _get_mock_data()
        regime = data["regime"]

        assert "direction" in regime
        assert "intensity" in regime
        assert "confidence" in regime
        assert "net_liq_percentile" in regime
        assert "global_liq_percentile" in regime
        assert "stealth_qe_score" in regime

    def test_mock_regime_direction_is_valid(self) -> None:
        """Test that regime direction is EXPANSION or CONTRACTION."""
        from liquidity.dashboard.callbacks import _get_mock_data

        data = _get_mock_data()
        direction = data["regime"]["direction"]

        assert direction in ["EXPANSION", "CONTRACTION"]

    def test_mock_metrics_have_required_fields(self) -> None:
        """Test that metric dictionaries have all required fields."""
        from liquidity.dashboard.callbacks import _get_mock_data

        data = _get_mock_data()

        net = data["net_metrics"]
        assert "current" in net
        assert "weekly_delta" in net
        assert "monthly_delta" in net

        glob = data["global_metrics"]
        assert "current" in glob
        assert "weekly_delta" in glob
        assert "monthly_delta" in glob


class TestErrorResponse:
    """Test error response generation."""

    def test_error_response_returns_tuple(self) -> None:
        """Test that error response returns correct tuple length."""
        from liquidity.dashboard.callbacks import _get_error_response

        response = _get_error_response("Test error")

        # Should return 10 outputs (matching callback outputs)
        assert isinstance(response, tuple)
        assert len(response) == 10

    def test_error_response_contains_error_message(self) -> None:
        """Test that error response includes the error message."""
        from liquidity.dashboard.callbacks import _get_error_response

        response = _get_error_response("Connection failed")

        # regime-indicator (index 2) should contain error message
        regime_indicator = response[2]
        assert regime_indicator is not None

    def test_error_response_has_empty_figures(self) -> None:
        """Test that error response includes empty chart figures."""
        from liquidity.dashboard.callbacks import _get_error_response

        response = _get_error_response("Test error")

        # First two items should be figures
        net_fig = response[0]
        global_fig = response[1]

        assert hasattr(net_fig, "data")
        assert hasattr(global_fig, "data")


class TestCallbackRegistration:
    """Test callback registration."""

    def test_register_callbacks(self) -> None:
        """Test that callbacks can be registered without error."""
        from dash import Dash, html

        from liquidity.dashboard.callbacks import register_callbacks

        # Create a test app with minimal layout
        app = Dash(__name__)
        app.layout = html.Div()  # Dash requires a valid layout

        # Should not raise
        register_callbacks(app)

        # Check that callbacks were registered
        assert len(app.callback_map) > 0
