"""Tests for CORS policy enforcement on the workspace app.

Verifies that the explicit CORS origins configured in settings
are correctly applied, and unknown origins are rejected.
"""


class TestCORSPolicy:
    """Tests for CORS middleware on the workspace app."""

    def test_cors_allows_openbb_workspace(self, workspace_client):
        """OPTIONS /health with Origin pro.openbb.co returns correct ACAO header."""
        resp = workspace_client.options(
            "/health",
            headers={
                "Origin": "https://pro.openbb.co",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "https://pro.openbb.co"

    def test_cors_allows_desktop_app(self, workspace_client):
        """OPTIONS with Origin localhost:1420 (OpenBB Desktop) is allowed."""
        resp = workspace_client.options(
            "/health",
            headers={
                "Origin": "http://localhost:1420",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:1420"

    def test_cors_allows_cf_domain(self, workspace_client):
        """OPTIONS with Origin liquidity.princyx.xyz is allowed."""
        resp = workspace_client.options(
            "/health",
            headers={
                "Origin": "https://liquidity.princyx.xyz",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            resp.headers.get("access-control-allow-origin")
            == "https://liquidity.princyx.xyz"
        )

    def test_cors_rejects_unknown_origin(self, workspace_client):
        """OPTIONS with unknown origin does not get ACAO header."""
        resp = workspace_client.options(
            "/health",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        acao = resp.headers.get("access-control-allow-origin")
        # Should either be absent or NOT be the evil origin or wildcard
        assert acao != "https://evil.com"
        assert acao != "*"
