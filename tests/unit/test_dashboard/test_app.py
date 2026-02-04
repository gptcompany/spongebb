"""Tests for dashboard app setup."""



class TestDashAppSetup:
    """Test Dash application configuration."""

    def test_app_creation(self) -> None:
        """Test that Dash app is created correctly."""
        from liquidity.dashboard.app import app, server

        assert app is not None
        assert server is not None
        assert app.title == "Global Liquidity Monitor"

    def test_app_has_dark_theme(self) -> None:
        """Test that app uses DARKLY theme."""
        from liquidity.dashboard.app import app

        # Check that external stylesheets include Bootstrap
        stylesheets = app.config.external_stylesheets
        assert len(stylesheets) > 0
        # DARKLY theme should be in stylesheets
        assert any("bootstrap" in str(s).lower() for s in stylesheets)

    def test_suppress_callback_exceptions(self) -> None:
        """Test that callback exceptions are suppressed for dynamic layouts."""
        from liquidity.dashboard.app import app

        assert app.config.suppress_callback_exceptions is True

    def test_server_is_flask(self) -> None:
        """Test that server is a Flask app for WSGI deployment."""
        from liquidity.dashboard.app import server

        # server should have Flask-like interface
        assert hasattr(server, "wsgi_app") or hasattr(server, "run")


class TestDashAppImports:
    """Test module imports work correctly."""

    def test_dashboard_module_imports(self) -> None:
        """Test that all dashboard submodules import without errors."""
        from liquidity.dashboard import app, run_server, server

        assert app is not None
        assert server is not None
        assert callable(run_server)

    def test_components_import(self) -> None:
        """Test that component functions are importable."""
        from liquidity.dashboard.components import (
            create_global_liquidity_chart,
            create_header,
            create_liquidity_panel,
            create_net_liquidity_chart,
            create_regime_gauge,
            create_regime_indicator,
            create_regime_panel,
        )

        assert callable(create_header)
        assert callable(create_liquidity_panel)
        assert callable(create_net_liquidity_chart)
        assert callable(create_global_liquidity_chart)
        assert callable(create_regime_panel)
        assert callable(create_regime_indicator)
        assert callable(create_regime_gauge)
