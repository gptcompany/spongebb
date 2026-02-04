"""Regime classification endpoints.

Provides:
- GET /regime/current - Current liquidity regime (EXPANSION/CONTRACTION)
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from liquidity.api.deps import RegimeClassifierDep
from liquidity.api.schemas import APIMetadata, RegimeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regime", tags=["regime"])


@router.get(
    "/current",
    response_model=RegimeResponse,
    summary="Get Current Liquidity Regime",
    description="Classifies the current liquidity environment as EXPANSION or CONTRACTION "
    "based on net liquidity, global liquidity, and stealth QE signals.",
)
async def get_current_regime(
    classifier: RegimeClassifierDep,
) -> RegimeResponse:
    """Get current liquidity regime classification.

    The regime classifier combines three signals:
    - Net Liquidity percentile (40%)
    - Global Liquidity percentile (40%)
    - Stealth QE score (20%)

    Binary classification forces decisive regime calls:
    - EXPANSION: Composite > 0.5 (favorable liquidity)
    - CONTRACTION: Composite <= 0.5 (unfavorable liquidity)

    Confidence levels based on component agreement:
    - HIGH: All 3 components agree
    - MEDIUM: 2 of 3 agree
    - LOW: Components split

    Returns:
        RegimeResponse with classification details.

    Raises:
        HTTPException: If classification fails.
    """
    try:
        result = await classifier.classify()

        return RegimeResponse(
            regime=result.direction.value,
            intensity=result.intensity,
            confidence=result.confidence,
            components=result.components,
            as_of_date=result.timestamp,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Regime classification failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to classify regime: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_current_regime")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e
