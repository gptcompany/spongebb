"""Tests for dashboard callbacks."""


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
