"""Cloudflare Access header verification middleware.

Defense-in-depth: CF Access handles primary auth at the edge.
This middleware verifies the Cf-Access-Authenticated-User-Email header
exists when LIQUIDITY_CF_ACCESS_ENABLED=true, preventing bypass if
tunnel misconfigured or internal network compromised.

Enable via: LIQUIDITY_CF_ACCESS_ENABLED=true
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Path prefixes that bypass CF Access verification (health checks, docs, widget discovery)
EXEMPT_PATH_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc", "/widgets.json")


class CloudflareAccessMiddleware(BaseHTTPMiddleware):
    """Verify Cloudflare Access authenticated user header.

    When enabled, rejects requests missing the
    Cf-Access-Authenticated-User-Email header with 403.
    Health, docs, and widget discovery endpoints are exempt.
    Uses prefix matching to handle sub-paths (e.g. /docs/ redirects).
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if path == "/" or path.startswith(EXEMPT_PATH_PREFIXES):
            return await call_next(request)

        cf_email = request.headers.get("Cf-Access-Authenticated-User-Email")
        if not cf_email:
            logger.warning(
                "CF Access: missing authenticated user header for %s %s from %s",
                request.method,
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=403,
                content={"error": "Cloudflare Access authentication required"},
            )

        return await call_next(request)
