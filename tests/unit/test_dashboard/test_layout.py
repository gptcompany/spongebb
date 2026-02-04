"""Tests for dashboard layout composition."""

import pytest


class TestLayoutCreation:
    """Test main layout creation."""

    def test_create_layout_returns_div(self) -> None:
        """Test that create_layout returns a valid Dash component."""
        from dash import html

        from liquidity.dashboard.layout import create_layout

        layout = create_layout()

        assert layout is not None
        assert isinstance(layout, html.Div)

    def test_layout_contains_refresh_interval(self) -> None:
        """Test that layout includes auto-refresh interval component."""
        from dash import dcc

        from liquidity.dashboard.layout import create_layout

        layout = create_layout()

        # Find the Interval component
        def find_component(component, component_id: str) -> bool:
            """Recursively search for component by id."""
            if hasattr(component, "id") and component.id == component_id:
                return True
            if hasattr(component, "children"):
                children = component.children
                if children is None:
                    return False
                if not isinstance(children, list):
                    children = [children]
                return any(find_component(c, component_id) for c in children)
            return False

        assert find_component(layout, "refresh-interval")

    def test_layout_contains_charts(self) -> None:
        """Test that layout includes chart placeholders."""
        from liquidity.dashboard.layout import create_layout

        layout = create_layout()

        def find_component(component, component_id: str) -> bool:
            if hasattr(component, "id") and component.id == component_id:
                return True
            if hasattr(component, "children"):
                children = component.children
                if children is None:
                    return False
                if not isinstance(children, list):
                    children = [children]
                return any(find_component(c, component_id) for c in children)
            return False

        assert find_component(layout, "net-liquidity-chart")
        assert find_component(layout, "global-liquidity-chart")
        assert find_component(layout, "regime-indicator")
        assert find_component(layout, "regime-gauge")

    def test_layout_contains_refresh_button(self) -> None:
        """Test that layout includes manual refresh button."""
        from liquidity.dashboard.layout import create_layout

        layout = create_layout()

        def find_component(component, component_id: str) -> bool:
            if hasattr(component, "id") and component.id == component_id:
                return True
            if hasattr(component, "children"):
                children = component.children
                if children is None:
                    return False
                if not isinstance(children, list):
                    children = [children]
                return any(find_component(c, component_id) for c in children)
            return False

        assert find_component(layout, "refresh-btn")

    def test_layout_contains_export_button(self) -> None:
        """Test that layout includes export button."""
        from liquidity.dashboard.layout import create_layout

        layout = create_layout()

        def find_component(component, component_id: str) -> bool:
            if hasattr(component, "id") and component.id == component_id:
                return True
            if hasattr(component, "children"):
                children = component.children
                if children is None:
                    return False
                if not isinstance(children, list):
                    children = [children]
                return any(find_component(c, component_id) for c in children)
            return False

        assert find_component(layout, "export-btn")


class TestRefreshInterval:
    """Test auto-refresh configuration."""

    def test_refresh_interval_is_5_minutes(self) -> None:
        """Test that refresh interval is set to 5 minutes."""
        from liquidity.dashboard.layout import create_layout

        layout = create_layout()

        def find_interval(component):
            """Find Interval component and return its interval value."""
            from dash import dcc

            if isinstance(component, dcc.Interval) and component.id == "refresh-interval":
                return component.interval
            if hasattr(component, "children"):
                children = component.children
                if children is None:
                    return None
                if not isinstance(children, list):
                    children = [children]
                for c in children:
                    result = find_interval(c)
                    if result is not None:
                        return result
            return None

        interval = find_interval(layout)
        assert interval == 5 * 60 * 1000  # 5 minutes in milliseconds
