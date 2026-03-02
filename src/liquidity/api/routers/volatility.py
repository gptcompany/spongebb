"""Volatility endpoints for MOVE Z-Score, VIX Term Structure, and composite signal.

Provides:
- GET /volatility/move-zscore - MOVE Bond Volatility Z-Score
- GET /volatility/vix-term-structure - VIX/VIX3M term structure
- GET /volatility/signal - Composite volatility signal
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter

from liquidity.api.deps import MOVEZScoreCalcDep, VIXTermCalcDep, VolatilitySignalCalcDep
from liquidity.api.schemas import (
    APIMetadata,
    MOVEZScoreResponse,
    VIXTermStructureResponse,
    VolatilitySignalResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/volatility", tags=["volatility"])


def _fallback_move_zscore_response(reason: str) -> MOVEZScoreResponse:
    """Return a degraded MOVE payload for widget consumers."""
    now = datetime.now(UTC)
    return MOVEZScoreResponse(
        current_move=0.0,
        mean_move=0.0,
        std_move=0.0,
        zscore=0.0,
        percentile=50.0,
        signal="UNKNOWN",
        as_of_date=now,
        metadata=APIMetadata(timestamp=now, source=f"spongebb ({reason})"),
    )


def _fallback_vix_term_structure_response(reason: str) -> VIXTermStructureResponse:
    """Return a degraded VIX-term payload for widget consumers."""
    now = datetime.now(UTC)
    return VIXTermStructureResponse(
        vix=0.0,
        vix3m=0.0,
        ratio=0.0,
        spread=0.0,
        structure="UNKNOWN",
        as_of_date=now,
        metadata=APIMetadata(timestamp=now, source=f"spongebb ({reason})"),
    )


def _fallback_volatility_signal_response(reason: str) -> VolatilitySignalResponse:
    """Return a degraded composite-volatility payload for widget consumers."""
    now = datetime.now(UTC)
    return VolatilitySignalResponse(
        composite_score=0.0,
        regime="NEUTRAL",
        move_zscore=0.0,
        move_signal="UNKNOWN",
        vix=0.0,
        vix3m=0.0,
        vix_ratio=0.0,
        vix_structure="UNKNOWN",
        move_component=0.0,
        term_component=0.0,
        level_component=0.0,
        as_of_date=now,
        metadata=APIMetadata(timestamp=now, source=f"spongebb ({reason})"),
    )


@router.get(
    "/move-zscore",
    response_model=MOVEZScoreResponse,
    summary="Get MOVE Z-Score",
    description="Rolling 20-day Z-Score for the MOVE Bond Volatility Index. "
    "High MOVE = bond stress = potential liquidity drain.",
    openapi_extra={
        "widget_config": {
            "name": "MOVE Z-Score",
            "description": "Bond volatility Z-Score with signal classification",
            "category": "Macro Liquidity",
            "subCategory": "Volatility",
            "type": "table",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 20, "h": 5},
            "data": {
                "table": {
                    "columnsDefs": [
                        {"field": "current_move", "headerName": "MOVE", "cellDataType": "number", "formatterFn": "int"},
                        {"field": "zscore", "headerName": "Z-Score", "cellDataType": "number"},
                        {"field": "percentile", "headerName": "Percentile", "cellDataType": "number", "formatterFn": "percent"},
                        {"field": "signal", "headerName": "Signal", "cellDataType": "text", "renderFn": "greenRed"},
                        {"field": "mean_move", "headerName": "Mean (20d)", "cellDataType": "number", "formatterFn": "int"},
                        {"field": "std_move", "headerName": "Std Dev", "cellDataType": "number"},
                    ]
                },
            },
        }
    },
)
async def get_move_zscore(
    calculator: MOVEZScoreCalcDep,
) -> MOVEZScoreResponse:
    """Get current MOVE Z-Score with signal classification.

    Signal interpretation:
    - EXTREME_HIGH (Z > 2.0): Severe bond stress, liquidity drain risk
    - HIGH (1.0 < Z <= 2.0): Elevated volatility, cautious
    - NORMAL (-1.0 <= Z <= 1.0): Normal conditions
    - LOW (-2.0 <= Z < -1.0): Calm markets
    - EXTREME_LOW (Z < -2.0): Complacency risk
    """
    try:
        result = await calculator.get_current()
        return MOVEZScoreResponse(
            current_move=round(result.current_move, 2),
            mean_move=round(result.mean_move, 2),
            std_move=round(result.std_move, 2),
            zscore=round(result.zscore, 3),
            percentile=round(result.percentile, 1),
            signal=result.signal.value,
            as_of_date=result.timestamp,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("MOVE Z-Score degraded: %s", e)
        return _fallback_move_zscore_response(f"degraded: {e}")
    except Exception as e:
        logger.exception("Unexpected error in get_move_zscore")
        return _fallback_move_zscore_response(f"error: {e}")


@router.get(
    "/vix-term-structure",
    response_model=VIXTermStructureResponse,
    summary="Get VIX Term Structure",
    description="VIX/VIX3M ratio and term structure classification. "
    "Contango (< 0.90) = bullish. Backwardation (> 1.05) = bearish.",
    openapi_extra={
        "widget_config": {
            "name": "VIX Term Structure",
            "description": "VIX/VIX3M ratio with contango/backwardation classification",
            "category": "Macro Liquidity",
            "subCategory": "Volatility",
            "type": "table",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 20, "h": 5},
            "data": {
                "table": {
                    "columnsDefs": [
                        {"field": "vix", "headerName": "VIX", "cellDataType": "number"},
                        {"field": "vix3m", "headerName": "VIX3M", "cellDataType": "number"},
                        {"field": "ratio", "headerName": "Ratio", "cellDataType": "number"},
                        {"field": "spread", "headerName": "Spread", "cellDataType": "number", "renderFn": "greenRed"},
                        {"field": "structure", "headerName": "Structure", "cellDataType": "text", "renderFn": "greenRed"},
                    ]
                },
            },
        }
    },
)
async def get_vix_term_structure(
    calculator: VIXTermCalcDep,
) -> VIXTermStructureResponse:
    """Get current VIX term structure classification.

    Term structure interpretation:
    - CONTANGO (ratio < 0.90): Near-term vol lower than 3-month, bullish
    - FLAT (0.90 <= ratio <= 1.05): Neutral
    - BACKWARDATION (ratio > 1.05): Near-term vol spike, bearish/stress
    """
    try:
        result = await calculator.get_current()
        return VIXTermStructureResponse(
            vix=round(result.vix, 2),
            vix3m=round(result.vix3m, 2),
            ratio=round(result.ratio, 4),
            spread=round(result.spread, 2),
            structure=result.structure.value,
            as_of_date=result.timestamp,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("VIX term structure degraded: %s", e)
        return _fallback_vix_term_structure_response(f"degraded: {e}")
    except Exception as e:
        logger.exception("Unexpected error in get_vix_term_structure")
        return _fallback_vix_term_structure_response(f"error: {e}")


@router.get(
    "/signal",
    response_model=VolatilitySignalResponse,
    summary="Get Composite Volatility Signal",
    description="Combined MOVE + VIX signal for liquidity regime analysis. "
    "Score: -100 (extreme stress) to +100 (extreme calm).",
    openapi_extra={
        "widget_config": {
            "name": "Volatility Signal",
            "description": "Composite bond + equity volatility signal (-100 to +100)",
            "category": "Macro Liquidity",
            "subCategory": "Volatility",
            "type": "table",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 20, "h": 5},
            "data": {
                "table": {
                    "columnsDefs": [
                        {"field": "composite_score", "headerName": "Score", "cellDataType": "number", "renderFn": "greenRed"},
                        {"field": "regime", "headerName": "Regime", "cellDataType": "text", "renderFn": "greenRed"},
                        {"field": "move_zscore", "headerName": "MOVE Z", "cellDataType": "number"},
                        {"field": "move_signal", "headerName": "MOVE Signal", "cellDataType": "text"},
                        {"field": "vix", "headerName": "VIX", "cellDataType": "number"},
                        {"field": "vix_ratio", "headerName": "VIX Ratio", "cellDataType": "number"},
                        {"field": "vix_structure", "headerName": "VIX Struct", "cellDataType": "text"},
                    ]
                },
            },
        }
    },
)
async def get_volatility_signal(
    calculator: VolatilitySignalCalcDep,
) -> VolatilitySignalResponse:
    """Get current composite volatility signal.

    Regime interpretation:
    - RISK_ON (score > 30): Favorable for risk assets
    - NEUTRAL (-30 <= score <= 30): Mixed signals
    - RISK_OFF (score < -30): Reduce exposure

    Components (weights):
    - MOVE Z-Score: 40% (bond volatility)
    - VIX Term Structure: 40% (equity vol curve)
    - VIX Level: 20% (absolute equity vol)
    """
    try:
        result = await calculator.get_current()
        return VolatilitySignalResponse(
            composite_score=result.composite_score,
            regime=result.regime.value,
            move_zscore=round(result.move_zscore.zscore, 3),
            move_signal=result.move_zscore.signal.value,
            vix=round(result.vix_term.vix, 2),
            vix3m=round(result.vix_term.vix3m, 2),
            vix_ratio=round(result.vix_term.ratio, 4),
            vix_structure=result.vix_term.structure.value,
            move_component=result.move_component,
            term_component=result.term_component,
            level_component=result.level_component,
            as_of_date=result.timestamp,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Volatility signal degraded: %s", e)
        return _fallback_volatility_signal_response(f"degraded: {e}")
    except Exception as e:
        logger.exception("Unexpected error in get_volatility_signal")
        return _fallback_volatility_signal_response(f"error: {e}")
