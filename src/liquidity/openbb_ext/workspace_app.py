"""OpenBB Workspace backend application.

Re-exports the existing FastAPI app with workspace configuration.
Launch: openbb-api --app liquidity.openbb_ext.workspace_app:app --host 0.0.0.0 --port 6900

The app object already contains all 14 existing endpoints with:
- Explicit CORS origins (pro.openbb.co, localhost:1420, liquidity.princyx.xyz)
- GET-only read API
"""

import logging

from liquidity.api.server import app  # noqa: F401
from liquidity.api.workspace_routes import workspace_router
from liquidity.config import get_settings

logger = logging.getLogger(__name__)

# Conditionally add Cloudflare Access middleware (defense-in-depth)
_settings = get_settings()
if _settings.cf_access_enabled:
    from liquidity.api.middleware import CloudflareAccessMiddleware  # noqa: E402

    app.add_middleware(CloudflareAccessMiddleware)
    logger.info("Cloudflare Access header verification enabled")

# Register workspace routes (metric + chart endpoints)
app.include_router(workspace_router)
