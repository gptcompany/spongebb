"""Regime classification endpoints.

Provides:
- GET /regime/current - Current liquidity regime (EXPANSION/CONTRACTION)
- GET /regime/combined - Combined liquidity-oil regime for macro signals
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter

from liquidity.analyzers import CombinedRegime, CombinedRegimeAnalyzer, RegimeClassifier
from liquidity.api.deps import RegimeClassifierDep
from liquidity.api.schemas import APIMetadata, CombinedRegimeResponse, RegimeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regime", tags=["regime"])


def _build_current_regime_fallback(reason: str) -> RegimeResponse:
    """Return a degraded current-regime response for widget consumers."""
    now = datetime.now(UTC)
    return RegimeResponse(
        regime="UNAVAILABLE",
        intensity=0.0,
        confidence="LOW",
        components=reason,
        as_of_date=now,
        metadata=APIMetadata(timestamp=now, source=f"spongebb ({reason})"),
    )


async def _build_combined_regime_fallback(reason: str) -> CombinedRegimeResponse:
    """Return a degraded combined regime response when oil data is unavailable."""
    try:
        liquidity = await RegimeClassifier().classify()
        liquidity_regime = liquidity.direction.value
        combined = (
            CombinedRegime.BULLISH
            if liquidity_regime == "EXPANSION"
            else CombinedRegime.BEARISH
        )
        confidence = 0.4
        drivers = [
            f"Liquidity: {liquidity_regime} (fallback-only mode)",
            "Oil regime unavailable; defaulting to BALANCED for widget continuity",
            reason,
        ]
    except Exception:
        liquidity_regime = "NEUTRAL"
        combined = CombinedRegime.NEUTRAL
        confidence = 0.2
        drivers = [
            "Liquidity regime unavailable; using neutral fallback",
            "Oil regime unavailable; defaulting to BALANCED",
            reason,
        ]

    commodity_signal = (
        "long"
        if combined == CombinedRegime.BULLISH
        else "short" if combined == CombinedRegime.BEARISH else "neutral"
    )
    return CombinedRegimeResponse(
        liquidity_regime=liquidity_regime,
        oil_regime="balanced",
        combined_regime=combined.value,
        confidence=confidence,
        commodity_signal=commodity_signal,
        drivers=drivers,
        as_of_date=datetime.now(UTC),
        metadata=APIMetadata(timestamp=datetime.now(UTC)),
    )


@router.get(
    "/current",
    response_model=RegimeResponse,
    summary="Get Current Liquidity Regime",
    description="Classifies the current liquidity environment as EXPANSION or CONTRACTION "
    "based on net liquidity, global liquidity, and stealth QE signals.",
    openapi_extra={
        "widget_config": {
            "name": "Current Regime",
            "description": "Liquidity regime classification with confidence",
            "category": "Regime",
            "type": "table",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 15, "h": 5},
            "data": {
                "table": {
                    "columnsDefs": [
                        {"field": "regime", "headerName": "Regime", "cellDataType": "text", "renderFn": "greenRed"},
                        {"field": "intensity", "headerName": "Intensity", "cellDataType": "number", "formatterFn": "int"},
                        {"field": "confidence", "headerName": "Confidence", "cellDataType": "number", "formatterFn": "percent"},
                    ]
                },
            },
        }
    },
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
        logger.warning("Current regime degraded: %s", e)
        return _build_current_regime_fallback(f"degraded: {e}")
    except Exception as e:
        logger.exception("Unexpected error in get_current_regime")
        return _build_current_regime_fallback(f"error: {e}")


@router.get(
    "/combined",
    response_model=CombinedRegimeResponse,
    summary="Get Combined Liquidity-Oil Regime",
    description="Classifies the combined liquidity-oil environment for macro commodity signals. "
    "Combines liquidity regime (EXPANSION/CONTRACTION) with oil supply-demand regime "
    "(TIGHT/BALANCED/LOOSE) to produce a unified signal.",
    openapi_extra={
        "widget_config": {
            "name": "Combined Regime",
            "description": "Liquidity + oil regime with commodity signal",
            "category": "Regime",
            "type": "table",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 15, "h": 5},
            "data": {
                "table": {
                    "columnsDefs": [
                        {"field": "liquidity_regime", "headerName": "Liquidity Regime", "cellDataType": "text", "renderFn": "greenRed"},
                        {"field": "oil_regime", "headerName": "Oil Regime", "cellDataType": "text", "renderFn": "greenRed"},
                        {"field": "combined_regime", "headerName": "Combined", "cellDataType": "text", "renderFn": "greenRed"},
                        {"field": "confidence", "headerName": "Confidence", "cellDataType": "number", "formatterFn": "percent"},
                        {"field": "commodity_signal", "headerName": "Commodity Signal", "cellDataType": "text"},
                    ]
                },
            },
        }
    },
)
async def get_combined_regime() -> CombinedRegimeResponse:
    """Get combined liquidity-oil regime classification.

    The combined regime analyzer merges two signals:
    - Liquidity regime: EXPANSION (favorable) vs CONTRACTION (unfavorable)
    - Oil supply-demand regime: TIGHT (bullish) vs LOOSE (bearish)

    Regime Matrix:
    - EXPANSION + TIGHT = VERY_BULLISH (commodities rally)
    - EXPANSION + BALANCED = BULLISH (selective longs)
    - EXPANSION + LOOSE = NEUTRAL (cross currents)
    - CONTRACTION + TIGHT = NEUTRAL (cross currents)
    - CONTRACTION + BALANCED = BEARISH (risk-off)
    - CONTRACTION + LOOSE = VERY_BEARISH (commodities sell-off)

    Returns:
        CombinedRegimeResponse with unified classification.

    Raises:
        HTTPException: If classification fails.
    """
    try:
        analyzer = CombinedRegimeAnalyzer()
        state = await analyzer.get_combined_regime()

        return CombinedRegimeResponse(
            liquidity_regime=state.liquidity_regime,
            oil_regime=state.oil_regime.value,
            combined_regime=state.combined_regime.value,
            confidence=state.confidence,
            commodity_signal=state.commodity_signal,
            drivers=state.drivers,
            as_of_date=state.timestamp,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Combined regime classification failed: %s", e)
        return await _build_combined_regime_fallback(
            f"Fallback activated: {e}"
        )
    except Exception as e:
        logger.exception("Unexpected error in get_combined_regime")
        return await _build_combined_regime_fallback(
            f"Fallback activated after unexpected error: {e}"
        )
