"""FX endpoints for DXY and currency pairs.

Provides:
- GET /fx/dxy - DXY index with recent history
- GET /fx/pairs - Major FX pairs vs USD
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from liquidity.api.deps import FXCollectorDep
from liquidity.api.schemas import (
    APIMetadata,
    DXYResponse,
    FXPairData,
    FXPairsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get(
    "/dxy",
    response_model=DXYResponse,
    summary="Get DXY Index",
    description="Returns the US Dollar Index (DXY) with current value and recent history.",
    openapi_extra={
        "widget_config": {
            "name": "DXY Index",
            "description": "US Dollar Index with recent history",
            "category": "FX",
            "type": "table",
            "refetchInterval": 900000,
            "gridData": {"w": 15, "h": 6},
            "data": {"dataKey": "data"},
        }
    },
)
async def get_dxy(
    collector: FXCollectorDep,
    period: Annotated[
        str,
        Query(
            description="Historical period for data: 5d, 7d, 30d, 60d, 90d",
            pattern="^(5d|7d|30d|60d|90d)$",
        ),
    ] = "30d",
) -> DXYResponse:
    """Get DXY index data.

    The US Dollar Index measures the dollar's strength against a basket
    of major currencies (EUR, JPY, GBP, CAD, SEK, CHF).

    Args:
        collector: Injected FXCollector.
        period: Historical period for data fetch.

    Returns:
        DXYResponse with current value and historical data.

    Raises:
        HTTPException: If data fetch fails.
    """
    try:
        df = await collector.collect_dxy(period=period)

        if df.empty:
            raise ValueError("No DXY data available")

        # Sort by timestamp and get latest
        df = df.sort_values("timestamp")
        current = float(df.iloc[-1]["value"])
        current_date = pd.to_datetime(df.iloc[-1]["timestamp"])

        # Calculate changes
        change_1d = _calculate_change(df, days=1)
        change_1w = _calculate_change(df, days=7)

        # Prepare historical data (last 30 points max)
        from liquidity.api.schemas import DXYDataPoint
        history = df.tail(30)[["timestamp", "value"]].to_dict("records")
        data_points = [
            DXYDataPoint(timestamp=str(row["timestamp"]), value=float(row["value"]))
            for row in history
        ]

        return DXYResponse(
            current=current,
            change_1d=change_1d,
            change_1w=change_1w,
            data=data_points,
            as_of_date=current_date.to_pydatetime().replace(tzinfo=UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("DXY fetch failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to fetch DXY data: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_dxy")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e


@router.get(
    "/pairs",
    response_model=FXPairsResponse,
    summary="Get Major FX Pairs",
    description="Returns major FX pairs vs USD with current values and changes.",
    openapi_extra={
        "widget_config": {
            "name": "Major FX Pairs",
            "description": "Major currency pairs vs USD",
            "category": "FX",
            "type": "table",
            "refetchInterval": 900000,
            "gridData": {"w": 15, "h": 6},
            "data": {"dataKey": "pairs"},
        }
    },
)
async def get_fx_pairs(
    collector: FXCollectorDep,
    period: Annotated[
        str,
        Query(
            description="Historical period for change calculations: 5d, 7d, 30d",
            pattern="^(5d|7d|30d)$",
        ),
    ] = "7d",
) -> FXPairsResponse:
    """Get major FX pairs data.

    Returns current values and recent changes for major USD pairs:
    - EUR/USD, USD/JPY, GBP/USD, USD/CHF, USD/CAD, USD/CNY, AUD/USD

    Args:
        collector: Injected FXCollector.
        period: Historical period for change calculations.

    Returns:
        FXPairsResponse with all major pairs data.

    Raises:
        HTTPException: If data fetch fails.
    """
    try:
        df = await collector.collect_pairs(period=period)

        if df.empty:
            raise ValueError("No FX pairs data available")

        # Get unique series and their latest values
        pairs: dict[str, FXPairData] = {}

        # Map Yahoo symbols to display names
        symbol_map = {
            "EURUSD=X": "EUR/USD",
            "USDJPY=X": "USD/JPY",
            "GBPUSD=X": "GBP/USD",
            "USDCHF=X": "USD/CHF",
            "USDCAD=X": "USD/CAD",
            "USDCNY=X": "USD/CNY",
            "AUDUSD=X": "AUD/USD",
        }

        for series_id in df["series_id"].unique():
            series_df = df[df["series_id"] == series_id].sort_values("timestamp")
            if series_df.empty:
                continue

            current = float(series_df.iloc[-1]["value"])
            change_1d = _calculate_change(series_df, days=1)

            display_name = symbol_map.get(series_id)
            if display_name is None:
                display_name = str(series_id) if series_id is not None else "UNKNOWN"
            pairs[display_name] = FXPairData(
                current=current,
                change_1d=change_1d,
            )

        if not pairs:
            raise ValueError("No valid FX pair data found")

        # Get the latest timestamp across all pairs
        latest_ts = pd.to_datetime(df["timestamp"]).max()
        as_of = latest_ts.to_pydatetime().replace(tzinfo=UTC)

        return FXPairsResponse(
            pairs=pairs,
            as_of_date=as_of,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("FX pairs fetch failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to fetch FX pairs data: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_fx_pairs")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e


def _calculate_change(df: pd.DataFrame, days: int) -> float | None:
    """Calculate percentage change over N days.

    Args:
        df: DataFrame with timestamp and value columns.
        days: Number of days for change calculation.

    Returns:
        Percentage change or None if insufficient data.
    """
    if len(df) < 2:
        return None

    df = df.sort_values("timestamp")
    current = float(df.iloc[-1]["value"])

    # Find value N days ago
    current_ts = pd.to_datetime(df.iloc[-1]["timestamp"])
    target_ts = current_ts - timedelta(days=days)

    # Find closest value on or before target date
    older_df = df[pd.to_datetime(df["timestamp"]) <= target_ts]

    # Use oldest available if not enough history
    older = float(df.iloc[0]["value"]) if older_df.empty else float(older_df.iloc[-1]["value"])

    if older == 0:
        return None

    return round((current - older) / older * 100, 2)
