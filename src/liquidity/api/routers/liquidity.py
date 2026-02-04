"""Liquidity endpoints for Net Liquidity and Global Liquidity.

Provides:
- GET /liquidity/net - Hayes Net Liquidity Index
- GET /liquidity/global - Multi-CB Global Liquidity Index
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from liquidity.api.deps import GlobalLiquidityCalcDep, NetLiquidityCalcDep
from liquidity.api.schemas import (
    APIMetadata,
    GlobalLiquidityComponent,
    GlobalLiquidityResponse,
    NetLiquidityResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/liquidity", tags=["liquidity"])


@router.get(
    "/net",
    response_model=NetLiquidityResponse,
    summary="Get Fed Net Liquidity Index",
    description="Returns the Hayes Net Liquidity Index: WALCL - TGA - RRP. "
    "All values in billions USD.",
)
async def get_net_liquidity(
    calculator: NetLiquidityCalcDep,
) -> NetLiquidityResponse:
    """Get current Net Liquidity metrics.

    The Net Liquidity Index is calculated as:
        Net Liquidity = WALCL - TGA - RRP

    Where:
    - WALCL: Fed Total Assets
    - TGA: Treasury General Account
    - RRP: Reverse Repo

    Returns:
        NetLiquidityResponse with current values and sentiment.

    Raises:
        HTTPException: If calculation fails.
    """
    try:
        result = await calculator.get_current()

        return NetLiquidityResponse(
            value=result.net_liquidity,
            walcl=result.walcl,
            tga=result.tga,
            rrp=result.rrp,
            weekly_delta=result.weekly_delta,
            sentiment=result.sentiment.value,
            as_of_date=result.timestamp,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Net liquidity calculation failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to calculate net liquidity: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_net_liquidity")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e


@router.get(
    "/global",
    response_model=GlobalLiquidityResponse,
    summary="Get Global Liquidity Index",
    description="Returns aggregated liquidity from major central banks "
    "(Fed, ECB, BoJ, PBoC, and optionally Tier 2 CBs). All values in billions USD.",
)
async def get_global_liquidity(
    calculator: GlobalLiquidityCalcDep,
    tier: Annotated[
        int,
        Query(
            ge=1,
            le=2,
            description="Tier level: 1=Fed/ECB/BoJ/PBoC only, 2=Include BoE/SNB/BoC",
        ),
    ] = 1,
) -> GlobalLiquidityResponse:
    """Get current Global Liquidity metrics.

    Aggregates balance sheet data from major central banks:
    - Tier 1 (>95% coverage): Fed, ECB, BoJ, PBoC
    - Tier 2 (additional ~4%): BoE, SNB, BoC

    All values converted to USD using current FX rates.

    Args:
        calculator: Injected GlobalLiquidityCalculator.
        tier: 1 for Tier 1 only, 2 to include Tier 2 CBs.

    Returns:
        GlobalLiquidityResponse with aggregated values.

    Raises:
        HTTPException: If calculation fails.
    """
    try:
        result = await calculator.get_current(tier=tier)

        components = GlobalLiquidityComponent(
            fed_usd=result.fed_usd,
            ecb_usd=result.ecb_usd,
            boj_usd=result.boj_usd,
            pboc_usd=result.pboc_usd,
            boe_usd=result.boe_usd,
            snb_usd=result.snb_usd,
            boc_usd=result.boc_usd,
        )

        return GlobalLiquidityResponse(
            value=result.total_usd,
            components=components,
            weekly_delta=result.weekly_delta,
            coverage_pct=result.coverage_pct,
            as_of_date=result.timestamp,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Global liquidity calculation failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to calculate global liquidity: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_global_liquidity")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e
