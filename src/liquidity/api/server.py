"""FastAPI server for the Global Liquidity Monitor API.

Provides REST endpoints for:
- Net Liquidity Index (Hayes formula)
- Global Liquidity Index (multi-CB aggregation)
- Regime Classification (EXPANSION/CONTRACTION)
- Stealth QE Score (hidden liquidity detection)

Run with: uvicorn liquidity.api:app --reload
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from liquidity.api.deps import get_storage
from liquidity.api.routers import (
    calendar_router,
    correlations_router,
    fx_router,
    liquidity_router,
    metrics_router,
    regime_router,
    stress_router,
)
from liquidity.api.schemas import ErrorResponse, HealthResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Performs startup and shutdown tasks:
    - Startup: Log server start, optionally verify QuestDB connection
    - Shutdown: Clean up resources

    Args:
        app: FastAPI application instance.

    Yields:
        None during application lifetime.
    """
    # Startup
    logger.info("Starting Global Liquidity Monitor API")

    # Optionally verify QuestDB connection
    try:
        storage = get_storage()
        if storage.health_check():
            logger.info("QuestDB connection verified")
        else:
            logger.warning("QuestDB health check failed - storage may be unavailable")
    except Exception as e:
        logger.warning("Could not verify QuestDB connection: %s", e)

    yield

    # Shutdown
    logger.info("Shutting down Global Liquidity Monitor API")


app = FastAPI(
    title="Global Liquidity Monitor API",
    description=(
        "Real-time liquidity regime classification based on Arthur Hayes' framework. "
        "Tracks Fed, ECB, BoJ, PBoC balance sheets and calculates Net Liquidity, "
        "Global Liquidity, and Stealth QE indicators."
    ),
    version="1.0.0",
    lifespan=lifespan,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)

# CORS middleware - permissive for internal use
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Internal use - restrict in production
    allow_credentials=True,
    allow_methods=["GET"],  # Read-only API
    allow_headers=["*"],
)

# Include routers
app.include_router(liquidity_router)
app.include_router(regime_router)
app.include_router(metrics_router)
app.include_router(fx_router)
app.include_router(stress_router)
app.include_router(correlations_router)
app.include_router(calendar_router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health Check",
    description="Returns service health status including QuestDB connectivity.",
)
async def health_check() -> HealthResponse:
    """Check API and QuestDB health.

    Returns:
        HealthResponse with service status.
    """
    try:
        storage = get_storage()
        questdb_ok = storage.health_check()
    except Exception:
        questdb_ok = False

    return HealthResponse(
        status="healthy" if questdb_ok else "degraded",
        questdb_connected=questdb_ok,
        version="1.0.0",
    )


@app.get(
    "/",
    include_in_schema=False,
)
async def root() -> JSONResponse:
    """Root endpoint redirecting to documentation."""
    return JSONResponse(
        content={
            "message": "Global Liquidity Monitor API",
            "docs": "/docs",
            "health": "/health",
        }
    )


def main() -> None:
    """Run the API server using uvicorn.

    This is the entry point for running the server directly:
        python -m liquidity.api.server

    For production, use uvicorn directly:
        uvicorn liquidity.api:app --host 0.0.0.0 --port 8000
    """
    import uvicorn

    uvicorn.run(
        "liquidity.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
