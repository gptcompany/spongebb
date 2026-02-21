"""Test Cloudflare Access middleware in isolation.

Tests the CloudflareAccessMiddleware behavior using a minimal Starlette
app (NOT the main workspace app) to avoid middleware-stack immutability
issues and test the middleware logic directly.
"""

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from liquidity.api.middleware import CloudflareAccessMiddleware


def homepage(request):
    return PlainTextResponse("OK")


def health(request):
    return PlainTextResponse("healthy")


# Build minimal test app with CF Access middleware
_test_app = Starlette(
    routes=[
        Route("/test", homepage),
        Route("/health", health),
        Route("/", homepage),
    ]
)
_test_app.add_middleware(CloudflareAccessMiddleware)
_cf_client = TestClient(_test_app)


def test_cf_middleware_blocks_without_header():
    """Requests to protected paths without CF header get 403."""
    resp = _cf_client.get("/test")
    assert resp.status_code == 403
    assert "authentication required" in resp.json()["error"].lower()


def test_cf_middleware_allows_with_header():
    """Requests with valid CF-Access header pass through."""
    resp = _cf_client.get(
        "/test",
        headers={"Cf-Access-Authenticated-User-Email": "user@example.com"},
    )
    assert resp.status_code == 200
    assert resp.text == "OK"


def test_cf_middleware_exempts_health():
    """Health endpoint is exempt from CF Access verification."""
    resp = _cf_client.get("/health")
    assert resp.status_code == 200


def test_cf_middleware_exempts_root():
    """Root endpoint is exempt from CF Access verification."""
    resp = _cf_client.get("/")
    assert resp.status_code == 200
