"""Tests for OpenAPI schema widget_config annotations.

Verifies that openapi_extra widget_config is correctly applied
to all workspace and table endpoints for OpenBB Workspace auto-discovery.
"""

from fastapi.testclient import TestClient

from liquidity.openbb_ext.workspace_app import app

EXPECTED_CATEGORIES = {
    "Macro Liquidity",
    "FX",
    "Stress",
    "Correlations",
    "Calendar",
    "Regime",
    "Stealth QE",
}


def _get_openapi_schema() -> dict:
    """Fetch and return the OpenAPI schema from the workspace app."""
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    return resp.json()


class TestOpenAPISchema:
    """Tests for the OpenAPI schema structure."""

    def test_openapi_schema_valid(self):
        """GET /openapi.json returns valid schema with required top-level keys."""
        schema = _get_openapi_schema()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

    def test_all_workspace_endpoints_have_widget_config(self):
        """All /workspace/* paths have widget_config in openapi_extra."""
        schema = _get_openapi_schema()
        workspace_paths = [
            p for p in schema["paths"] if p.startswith("/workspace")
        ]
        assert len(workspace_paths) >= 6, (
            f"Expected at least 6 workspace paths, found {len(workspace_paths)}: {workspace_paths}"
        )
        for path in workspace_paths:
            methods = schema["paths"][path]
            for method, spec in methods.items():
                if method in ("get", "post", "put", "delete"):
                    assert "widget_config" in spec, (
                        f"{path} {method} missing widget_config"
                    )


class TestWidgetConfig:
    """Tests for widget_config content and structure."""

    def _collect_widget_configs(self) -> list[tuple[str, dict]]:
        """Return list of (path, widget_config) for all annotated endpoints.

        FastAPI merges openapi_extra directly into the operation object,
        so widget_config appears at spec["widget_config"] (not under x-openapi-extra).
        """
        schema = _get_openapi_schema()
        configs = []
        for path, methods in schema["paths"].items():
            for method, spec in methods.items():
                if method not in ("get", "post", "put", "delete"):
                    continue
                wc = spec.get("widget_config")
                if wc:
                    configs.append((path, wc))
        return configs

    def test_existing_endpoints_have_widget_config(self):
        """Non-utility endpoints (not / or /health) have widget_config."""
        schema = _get_openapi_schema()
        skip = {"/", "/health", "/docs", "/openapi.json", "/redoc"}
        missing = []
        for path, methods in schema["paths"].items():
            if path in skip:
                continue
            for method, spec in methods.items():
                if method not in ("get", "post", "put", "delete"):
                    continue
                wc = spec.get("widget_config")
                if not wc:
                    missing.append(f"{method.upper()} {path}")
        assert not missing, f"Endpoints missing widget_config: {missing}"

    def test_widget_config_has_required_fields(self):
        """Each widget_config has name, description, category, type."""
        configs = self._collect_widget_configs()
        assert len(configs) > 0, "No widget_configs found"
        for path, wc in configs:
            for field in ("name", "description", "category", "type"):
                assert field in wc, f"{path} widget_config missing '{field}'"
                assert isinstance(wc[field], str), (
                    f"{path} widget_config['{field}'] should be str, got {type(wc[field])}"
                )

    def test_widget_categories_are_expected(self):
        """All widget_config categories come from the expected set."""
        configs = self._collect_widget_configs()
        assert len(configs) > 0
        found_categories = {wc["category"] for _, wc in configs}
        unexpected = found_categories - EXPECTED_CATEGORIES
        assert not unexpected, (
            f"Unexpected categories: {unexpected}. Expected subset of {EXPECTED_CATEGORIES}"
        )

    def test_widget_types_are_valid(self):
        """All widget_config types are metric, chart, or table."""
        valid_types = {"metric", "chart", "table"}
        configs = self._collect_widget_configs()
        for path, wc in configs:
            assert wc["type"] in valid_types, (
                f"{path} has invalid type '{wc['type']}', expected one of {valid_types}"
            )
