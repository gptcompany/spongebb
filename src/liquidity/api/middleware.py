"""Cloudflare Access header verification middleware.

Defense-in-depth: CF Access handles primary auth at the edge.
This middleware verifies both Cf-Access-Authenticated-User-Email and
Cf-Access-Jwt-Assertion headers exist when LIQUIDITY_CF_ACCESS_ENABLED=true,
preventing bypass if tunnel misconfigured or internal network compromised.

Enable via: LIQUIDITY_CF_ACCESS_ENABLED=true
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Exact paths exempt from CF Access verification
_EXEMPT_EXACT = frozenset({"/", "/health", "/openapi.json", "/widgets.json"})

# Path prefixes exempt (match prefix + "/" to prevent traversal: /docs but not /documents)
_EXEMPT_PREFIXES = ("/docs/", "/redoc/", "/health/")


def _is_exempt(path: str) -> bool:
    """Check if path is exempt from CF Access verification."""
    return path in _EXEMPT_EXACT or path.startswith(_EXEMPT_PREFIXES)


class CloudflareAccessMiddleware(BaseHTTPMiddleware):
    """Verify Cloudflare Access authenticated user headers.

    When enabled, rejects requests missing the
    Cf-Access-Authenticated-User-Email or Cf-Access-Jwt-Assertion
    headers with 403.
    Health, docs, and widget discovery endpoints are exempt.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if _is_exempt(request.url.path):
            return await call_next(request)

        cf_email = request.headers.get("Cf-Access-Authenticated-User-Email")
        cf_jwt = request.headers.get("Cf-Access-Jwt-Assertion")
        if not cf_email or not cf_jwt:
            logger.warning(
                "CF Access: missing auth headers for %s %s from %s",
                request.method,
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=403,
                content={"error": "Cloudflare Access authentication required"},
            )

        return await call_next(request)
