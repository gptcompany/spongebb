"""Stress indicator endpoints for funding market stress signals.

Provides:
- GET /stress/indicators - Funding market stress metrics
"""

import logging
from datetime import UTC, datetime

import pandas as pd
from fastapi import APIRouter, HTTPException

from liquidity.api.deps import StressCollectorDep
from liquidity.api.schemas import (
    APIMetadata,
    StressIndicatorsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stress", tags=["stress"])


@router.get(
    "/indicators",
    response_model=StressIndicatorsResponse,
    summary="Get Funding Stress Indicators",
    description="Returns funding market stress metrics including SOFR-OIS spread, "
    "SOFR distribution width, repo stress ratio, and CP-Treasury spread.",
    openapi_extra={
        "widget_config": {
            "name": "Funding Stress Indicators",
            "description": "SOFR-OIS spread, repo stress, CP spread, and overall stress regime",
            "category": "Macro Liquidity",
            "subCategory": "Stress",
            "type": "table",
            "refetchInterval": 900000,
            "gridData": {"w": 20, "h": 6},
        }
    },
)
async def get_stress_indicators(
    collector: StressCollectorDep,
) -> StressIndicatorsResponse:
    """Get current funding market stress indicators.

    Four key stress metrics:
    1. SOFR-OIS Spread: Funding premium over policy rate (bps)
       - Normal: 0-10, Elevated: 10-25, Stress: >25
    2. SOFR Distribution Width: 99th-1st percentile dispersion (bps)
       - Normal: <20, Elevated: 20-50, Crisis: >50
    3. Repo Stress Ratio: RRP as % of Fed balance sheet
       - Normal: <1%, Elevated: 1-3%, High: >3%
    4. CP-Treasury Spread: Commercial paper funding stress (bps)
       - Normal: 20-40, Elevated: 40-100, Stress: >100

    Returns:
        StressIndicatorsResponse with all stress metrics.

    Raises:
        HTTPException: If data fetch fails.
    """
    try:
        df = await collector.collect()

        if df.empty:
            raise ValueError("No stress indicator data available")

        # Get latest value for each indicator
        latest_values: dict[str, float | None] = {}
        for series_id in [
            "stress_sofr_ois",
            "stress_sofr_width",
            "stress_repo",
            "stress_cp",
        ]:
            series_df = df[df["series_id"] == series_id]
            if not series_df.empty:
                latest = series_df.sort_values("timestamp").iloc[-1]
                latest_values[series_id] = float(latest["value"])
            else:
                latest_values[series_id] = None

        # Get SOFR percentile (relative to historical range)
        sofr_percentile = _calculate_sofr_percentile(
            latest_values.get("stress_sofr_ois"),
            df[df["series_id"] == "stress_sofr_ois"],
        )

        # Determine overall stress regime
        regime = collector.get_current_regime(df)

        # Map regime to overall_stress string
        stress_map = {
            "GREEN": "normal",
            "YELLOW": "elevated",
            "RED": "critical",
        }
        overall_stress = stress_map.get(regime, "normal")

        # Map repo stress to string
        repo_stress = _get_repo_stress_level(latest_values.get("stress_repo"))

        # Get latest timestamp
        latest_ts = df["timestamp"].max()
        if hasattr(latest_ts, "to_pydatetime"):
            as_of = latest_ts.to_pydatetime().replace(tzinfo=UTC)
        else:
            as_of = datetime.now(UTC)

        return StressIndicatorsResponse(
            sofr_ois_spread=latest_values.get("stress_sofr_ois"),
            sofr_percentile=sofr_percentile,
            repo_stress=repo_stress,
            cp_spread=latest_values.get("stress_cp"),
            sofr_width=latest_values.get("stress_sofr_width"),
            repo_ratio=latest_values.get("stress_repo"),
            overall_stress=overall_stress,
            as_of_date=as_of,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Stress indicators fetch failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to fetch stress indicators: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_stress_indicators")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e


def _calculate_sofr_percentile(
    current_value: float | None,
    historical_df: "pd.DataFrame",
) -> int | None:
    """Calculate SOFR-OIS spread percentile vs 60-day history.

    Args:
        current_value: Current SOFR-OIS spread.
        historical_df: Historical SOFR-OIS data.

    Returns:
        Percentile (0-100) or None if insufficient data.
    """
    if current_value is None:
        return None

    if historical_df.empty:
        return 50  # Default to median

    values = historical_df["value"].dropna()
    if len(values) < 5:
        return 50

    # Calculate percentile
    rank = (values < current_value).sum()
    percentile = int((rank / len(values)) * 100)
    return max(0, min(100, percentile))


def _get_repo_stress_level(repo_ratio: float | None) -> str:
    """Map repo stress ratio to level string.

    Args:
        repo_ratio: RRP as % of Fed balance sheet.

    Returns:
        "low", "medium", or "high"
    """
    if repo_ratio is None:
        return "unknown"

    if repo_ratio < 1.0:
        return "low"
    elif repo_ratio < 3.0:
        return "medium"
    else:
        return "high"
