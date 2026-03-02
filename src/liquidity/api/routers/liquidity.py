"""Liquidity endpoints for Net Liquidity and Global Liquidity.

Provides:
- GET /liquidity/net - Hayes Net Liquidity Index
- GET /liquidity/global - Multi-CB Global Liquidity Index
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from liquidity.api.deps import GlobalLiquidityCalcDep, NetLiquidityCalcDep
from liquidity.api.schemas import (
    APIMetadata,
    GlobalLiquidityComponent,
    GlobalLiquidityResponse,
    NetLiquidityResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/liquidity", tags=["liquidity"])


def _fallback_net_liquidity_response(reason: str) -> NetLiquidityResponse:
    """Return a degraded net-liquidity payload for widget consumers."""
    now = datetime.now(UTC)
    return NetLiquidityResponse(
        value=0.0,
        walcl=0.0,
        tga=0.0,
        rrp=0.0,
        weekly_delta=0.0,
        sentiment="DEGRADED",
        as_of_date=now,
        metadata=APIMetadata(timestamp=now, source=f"spongebb ({reason})"),
    )


def _fallback_global_liquidity_response(reason: str) -> GlobalLiquidityResponse:
    """Return a degraded global-liquidity payload for widget consumers."""
    now = datetime.now(UTC)
    return GlobalLiquidityResponse(
        value=0.0,
        components=GlobalLiquidityComponent(
            fed_usd=0.0,
            ecb_usd=0.0,
            boj_usd=0.0,
            pboc_usd=0.0,
            boe_usd=None,
            snb_usd=None,
            boc_usd=None,
        ),
        weekly_delta=0.0,
        coverage_pct=0.0,
        as_of_date=now,
        metadata=APIMetadata(timestamp=now, source=f"spongebb ({reason})"),
    )


@router.get(
    "/net",
    response_model=NetLiquidityResponse,
    summary="Get Fed Net Liquidity Index",
    description="Returns the Hayes Net Liquidity Index: WALCL - TGA - RRP. "
    "All values in billions USD.",
    openapi_extra={
        "widget_config": {
            "name": "Net Liquidity Detail",
            "description": "Hayes formula components: WALCL, TGA, RRP, delta",
            "category": "Macro Liquidity",
            "subCategory": "Fed",
            "type": "table",
            "refetchInterval": 14400000,
            "staleTime": 7200000,
            "gridData": {"w": 20, "h": 5},
            "data": {
                "table": {
                    "columnsDefs": [
                        {"field": "value", "headerName": "Net Liquidity", "cellDataType": "number", "formatterFn": "int"},
                        {"field": "walcl", "headerName": "WALCL", "cellDataType": "number", "formatterFn": "int"},
                        {"field": "tga", "headerName": "TGA", "cellDataType": "number", "formatterFn": "int"},
                        {"field": "rrp", "headerName": "RRP", "cellDataType": "number", "formatterFn": "int"},
                        {"field": "weekly_delta", "headerName": "Weekly Delta", "cellDataType": "number", "formatterFn": "int", "renderFn": "greenRed"},
                        {"field": "sentiment", "headerName": "Sentiment", "cellDataType": "text", "renderFn": "greenRed"},
                    ]
                },
            },
        }
    },
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
        logger.warning("Net liquidity degraded: %s", e)
        return _fallback_net_liquidity_response(f"degraded: {e}")
    except Exception as e:
        logger.exception("Unexpected error in get_net_liquidity")
        return _fallback_net_liquidity_response(f"error: {e}")


@router.get(
    "/global",
    response_model=GlobalLiquidityResponse,
    summary="Get Global Liquidity Index",
    description="Returns aggregated liquidity from major central banks "
    "(Fed, ECB, BoJ, PBoC, and optionally Tier 2 CBs). All values in billions USD.",
    openapi_extra={
        "widget_config": {
            "name": "Global Liquidity Detail",
            "description": "Central bank balance sheet breakdown in USD",
            "category": "Macro Liquidity",
            "subCategory": "Global",
            "type": "table",
            "refetchInterval": 14400000,
            "staleTime": 7200000,
            "gridData": {"w": 20, "h": 5},
            "data": {
                "table": {
                    "columnsDefs": [
                        {"field": "value", "headerName": "Total (B USD)", "cellDataType": "number", "formatterFn": "int"},
                        {"field": "weekly_delta", "headerName": "Weekly Delta", "cellDataType": "number", "formatterFn": "int", "renderFn": "greenRed"},
                        {"field": "coverage_pct", "headerName": "Coverage", "cellDataType": "number", "formatterFn": "percent"},
                    ]
                },
            },
            "params": [
                {"paramName": "tier", "value": "1", "label": "Tier", "type": "number", "show": True, "description": "1=Fed/ECB/BoJ/PBoC, 2=Include BoE/SNB/BoC"},
            ],
        }
    },
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
        logger.warning("Global liquidity degraded: %s", e)
        return _fallback_global_liquidity_response(f"degraded: {e}")
    except Exception as e:
        logger.exception("Unexpected error in get_global_liquidity")
        return _fallback_global_liquidity_response(f"error: {e}")
