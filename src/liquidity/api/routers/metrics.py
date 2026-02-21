"""Metrics endpoints for Stealth QE and other indicators.

Provides:
- GET /metrics/stealth-qe - Stealth QE Score (hidden liquidity injections)
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from liquidity.api.deps import StealthQECalcDep
from liquidity.api.schemas import APIMetadata, StealthQEResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "/stealth-qe",
    response_model=StealthQEResponse,
    summary="Get Stealth QE Score",
    description="Detects hidden liquidity injections through RRP velocity, "
    "TGA spending, and Fed balance sheet changes.",
    openapi_extra={
        "widget_config": {
            "name": "Stealth QE Detail",
            "description": "Hidden liquidity injection components (RRP, TGA, Fed)",
            "category": "Macro Liquidity",
            "subCategory": "Stealth QE",
            "type": "table",
            "refetchInterval": 900000,
            "gridData": {"w": 20, "h": 5},
        }
    },
)
async def get_stealth_qe(
    calculator: StealthQECalcDep,
) -> StealthQEResponse:
    """Get current Stealth QE metrics.

    The Stealth QE Score combines three signals:
    - RRP Velocity (40%): Declining RRP releases liquidity
    - TGA Spending (40%): Treasury spending adds liquidity
    - Fed Changes (20%): Direct balance sheet expansion

    Score interpretation:
    - 70-100: VERY_ACTIVE - Major liquidity injection in progress
    - 50-70:  ACTIVE - Stealth QE detected, bullish
    - 30-50:  MODERATE - Some injection signals, neutral
    - 10-30:  LOW - Minimal activity
    - 0-10:   MINIMAL - No hidden injection

    Returns:
        StealthQEResponse with score and component breakdown.

    Raises:
        HTTPException: If calculation fails.
    """
    try:
        result = await calculator.get_current()

        return StealthQEResponse(
            score=result.score_daily,
            status=result.status,
            rrp_level=result.rrp_level,
            rrp_velocity=result.rrp_velocity,
            tga_level=result.tga_level,
            tga_spending=result.tga_spending,
            fed_total=result.fed_total,
            fed_change=result.fed_change,
            components=result.components,
            as_of_date=result.timestamp,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Stealth QE calculation failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to calculate stealth QE: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_stealth_qe")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e
