"""Correlation endpoints for asset-liquidity relationships.

Provides:
- GET /correlations - Asset vs net liquidity correlations
- GET /correlations/matrix - Full cross-asset correlation matrix
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from liquidity.api.deps import CorrelationEngineDep
from liquidity.api.schemas import (
    APIMetadata,
    AssetCorrelation,
    CorrelationMatrixResponse,
    CorrelationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/correlations", tags=["correlations"])


@router.get(
    "",
    response_model=CorrelationResponse,
    summary="Get Asset-Liquidity Correlations",
    description="Returns correlations between asset returns and net liquidity changes.",
)
async def get_correlations(
    engine: CorrelationEngineDep,
    window: Annotated[
        str,
        Query(
            description="Correlation window: 30d or 90d",
            pattern="^(30d|90d)$",
        ),
    ] = "30d",
) -> CorrelationResponse:
    """Get correlations between assets and net liquidity.

    Calculates rolling correlations between daily returns of major assets
    (BTC, SPX, GOLD, TLT, DXY, COPPER, HYG) and net liquidity changes.

    Interpretation:
    - High positive (>0.6): Asset tracks liquidity closely (risk-on)
    - High negative (<-0.4): Asset inversely tracks liquidity (safe-haven)
    - Low (-0.3 to 0.3): Weak relationship with liquidity

    Args:
        engine: Injected CorrelationEngine.
        window: Correlation window period.

    Returns:
        CorrelationResponse with per-asset correlations.

    Raises:
        HTTPException: If calculation fails.
    """
    try:
        # Fetch asset prices
        asset_prices = await engine._fetch_asset_prices()

        if asset_prices.empty:
            raise ValueError("No asset price data available")

        # Calculate asset returns
        asset_returns = engine._calculate_returns(asset_prices)

        # For liquidity returns, we need to synthesize from asset behavior
        # In a real scenario, this would come from NetLiquidityCalculator history
        # For now, we use market-implied liquidity (inverse of DXY as proxy)
        if "DXY" in asset_returns.columns:
            # Inverse DXY returns as liquidity proxy
            liquidity_returns = -asset_returns["DXY"]
        else:
            # Fall back to SPX as market liquidity proxy
            liquidity_returns = asset_returns.get("SPX", asset_returns.iloc[:, 0])

        # Calculate correlations
        results = engine.calculate_correlations(asset_returns, liquidity_returns)

        corr_df = results.get("corr_30d") if window == "30d" else results.get("corr_90d")

        if corr_df is None or corr_df.empty:
            raise ValueError(f"No correlation data for window {window}")

        # Build correlation response
        correlations: dict[str, AssetCorrelation] = {}

        for asset in corr_df.columns:
            series = corr_df[asset].dropna()
            if series.empty:
                continue

            # Get latest correlation and calculate p-value
            latest_corr = float(series.iloc[-1])
            result = engine.calculate_single_correlation(
                asset_returns[asset], liquidity_returns
            )

            p_value = result.p_value_30d if window == "30d" else result.p_value_90d

            correlations[asset] = AssetCorrelation(
                value=round(latest_corr, 3) if not _is_nan(latest_corr) else None,
                p_value=round(p_value, 4) if p_value is not None and not _is_nan(p_value) else None,
            )

        return CorrelationResponse(
            window=window,
            correlations=correlations,
            as_of_date=datetime.now(UTC),
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Correlations calculation failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to calculate correlations: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_correlations")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e


@router.get(
    "/matrix",
    response_model=CorrelationMatrixResponse,
    summary="Get Correlation Matrix",
    description="Returns full cross-asset correlation matrix.",
)
async def get_correlation_matrix(
    engine: CorrelationEngineDep,
) -> CorrelationMatrixResponse:
    """Get cross-asset correlation matrix.

    Calculates pairwise correlations between all tracked assets:
    BTC, SPX, GOLD, TLT, DXY, COPPER, HYG

    Useful for understanding:
    - Risk diversification (low correlations)
    - Contagion risk (high correlations)
    - Regime shifts (correlation changes)

    Args:
        engine: Injected CorrelationEngine.

    Returns:
        CorrelationMatrixResponse with full matrix.

    Raises:
        HTTPException: If calculation fails.
    """
    try:
        # Fetch asset prices
        asset_prices = await engine._fetch_asset_prices()

        if asset_prices.empty:
            raise ValueError("No asset price data available")

        # Calculate asset returns
        asset_returns = engine._calculate_returns(asset_prices)

        # Calculate correlation matrix
        result = engine.calculate_correlation_matrix(asset_returns)

        # Convert to nested dict format for JSON serialization
        assets = result.assets
        matrix: dict[str, dict[str, float | None]] = {}

        for asset in assets:
            matrix[asset] = {}
            for other in assets:
                # Access correlation value and convert safely
                raw_val = result.correlations.loc[asset, other]
                try:
                    float_val = float(raw_val)  # type: ignore[arg-type]
                    matrix[asset][other] = round(float_val, 3) if not _is_nan(float_val) else None
                except (TypeError, ValueError):
                    matrix[asset][other] = None

        return CorrelationMatrixResponse(
            assets=assets,
            matrix=matrix,
            as_of_date=result.timestamp,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Correlation matrix calculation failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Unable to calculate correlation matrix: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_correlation_matrix")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e


def _is_nan(value: float | None) -> bool:
    """Check if value is NaN."""
    import math
    if value is None:
        return True
    try:
        return math.isnan(value)
    except (TypeError, ValueError):
        return False
