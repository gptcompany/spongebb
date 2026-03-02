"""OpenBB Workspace dedicated endpoints for metric and chart widgets.

Provides /workspace/metrics/* and /workspace/charts/* routes with
response shapes optimized for OpenBB Workspace rendering:
- Metrics: Simple KPI cards (value + label + delta)
- Charts: Plotly JSON figures rendered natively by Workspace

These routes wrap existing calculators (zero business logic duplication).
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import plotly.graph_objects as go
from fastapi import APIRouter, HTTPException, Query

from liquidity.api.deps import (
    GlobalLiquidityCalcDep,
    MOVEZScoreCalcDep,
    NetLiquidityCalcDep,
    RegimeClassifierDep,
    StealthQECalcDep,
    VolatilitySignalCalcDep,
)
from liquidity.api.workspace_schemas import WorkspaceMetric

logger = logging.getLogger(__name__)

workspace_router = APIRouter(prefix="/workspace", tags=["workspace"])


def _fallback_workspace_metric(
    *,
    value: float,
    label: str,
    unit: str | None = None,
    sentiment: str | None = None,
    delta: float | None = None,
) -> WorkspaceMetric:
    """Return a valid degraded metric payload for widget consumers."""
    return WorkspaceMetric(
        value=value,
        label=label,
        delta=delta,
        unit=unit,
        sentiment=sentiment,
    )


def _fallback_workspace_chart(title: str, message: str) -> dict:
    """Return a simple placeholder Plotly figure for degraded chart widgets."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        showarrow=False,
        font=dict(size=16),
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
    )
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=400,
    )
    return fig.to_plotly_json()


# =============================================================================
# Metric Endpoints
# =============================================================================


@workspace_router.get(
    "/metrics/net-liquidity",
    response_model=WorkspaceMetric,
    summary="Net Liquidity KPI",
    openapi_extra={
        "widget_config": {
            "name": "Net Liquidity Index",
            "description": "Hayes formula: WALCL - TGA - RRP (billions USD)",
            "category": "Macro Liquidity",
            "subCategory": "Fed",
            "type": "metric",
            "refetchInterval": 900000,
            "staleTime": 300000,
            "gridData": {"w": 10, "h": 4},
        }
    },
)
async def workspace_metric_net_liquidity(
    calculator: NetLiquidityCalcDep,
) -> WorkspaceMetric:
    """Net Liquidity as Workspace metric widget."""
    try:
        result = await calculator.get_current()
        return WorkspaceMetric(
            value=round(result.net_liquidity, 1),
            label="Net Liquidity (B USD)",
            delta=round(result.weekly_delta, 1) if result.weekly_delta is not None else None,
            unit="B USD",
            sentiment=result.sentiment.value,
        )
    except ValueError as e:
        logger.warning("Workspace net liquidity metric degraded: %s", e)
        return _fallback_workspace_metric(
            value=0.0,
            label="Net Liquidity unavailable",
            unit="B USD",
            sentiment="DEGRADED",
        )
    except Exception:
        logger.exception("Workspace net liquidity metric failed")
        return _fallback_workspace_metric(
            value=0.0,
            label="Net Liquidity unavailable",
            unit="B USD",
            sentiment="ERROR",
        )


@workspace_router.get(
    "/metrics/global-liquidity",
    response_model=WorkspaceMetric,
    summary="Global Liquidity KPI",
    openapi_extra={
        "widget_config": {
            "name": "Global Liquidity",
            "description": "Total global CB liquidity (Fed + ECB + BoJ + PBoC) in USD",
            "category": "Macro Liquidity",
            "subCategory": "Global",
            "type": "metric",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 10, "h": 4},
        }
    },
)
async def workspace_metric_global_liquidity(
    calculator: GlobalLiquidityCalcDep,
) -> WorkspaceMetric:
    """Global Liquidity as Workspace metric widget."""
    try:
        result = await calculator.get_current(tier=1)
        return WorkspaceMetric(
            value=round(result.total_usd, 1),
            label="Global Liquidity (B USD)",
            delta=round(result.weekly_delta, 1) if result.weekly_delta is not None else None,
            unit="B USD",
        )
    except ValueError as e:
        logger.warning("Workspace global liquidity metric degraded: %s", e)
        return _fallback_workspace_metric(
            value=0.0,
            label="Global Liquidity unavailable",
            unit="B USD",
            sentiment="DEGRADED",
        )
    except Exception:
        logger.exception("Workspace global liquidity metric failed")
        return _fallback_workspace_metric(
            value=0.0,
            label="Global Liquidity unavailable",
            unit="B USD",
            sentiment="ERROR",
        )


@workspace_router.get(
    "/metrics/stealth-qe",
    response_model=WorkspaceMetric,
    summary="Stealth QE Score",
    openapi_extra={
        "widget_config": {
            "name": "Stealth QE Score",
            "description": "Hidden liquidity injection detection (0-100)",
            "category": "Macro Liquidity",
            "subCategory": "Stealth",
            "type": "metric",
            "refetchInterval": 900000,
            "staleTime": 300000,
            "gridData": {"w": 10, "h": 4},
        }
    },
)
async def workspace_metric_stealth_qe(
    calculator: StealthQECalcDep,
) -> WorkspaceMetric:
    """Stealth QE score as Workspace metric widget."""
    try:
        result = await calculator.get_current()
        return WorkspaceMetric(
            value=round(result.score_daily, 1),
            label="Stealth QE Score",
            delta=None,
            unit="/100",
            sentiment=result.status,
        )
    except ValueError as e:
        logger.warning("Workspace stealth QE metric degraded: %s", e)
        return _fallback_workspace_metric(
            value=0.0,
            label="Stealth QE unavailable",
            unit="/100",
            sentiment="DEGRADED",
        )
    except Exception:
        logger.exception("Workspace stealth QE metric failed")
        return _fallback_workspace_metric(
            value=0.0,
            label="Stealth QE unavailable",
            unit="/100",
            sentiment="ERROR",
        )


@workspace_router.get(
    "/metrics/regime",
    response_model=WorkspaceMetric,
    summary="Regime Classification",
    openapi_extra={
        "widget_config": {
            "name": "Liquidity Regime",
            "description": "Binary regime: EXPANSION or CONTRACTION with intensity",
            "category": "Macro Liquidity",
            "subCategory": "Regime",
            "type": "metric",
            "refetchInterval": 900000,
            "staleTime": 300000,
            "gridData": {"w": 10, "h": 4},
        }
    },
)
async def workspace_metric_regime(
    classifier: RegimeClassifierDep,
) -> WorkspaceMetric:
    """Regime classification as Workspace metric widget."""
    try:
        result = await classifier.classify()
        return WorkspaceMetric(
            value=result.intensity,
            label=f"Regime: {result.direction.value}",
            delta=None,
            unit="%",
            sentiment=result.direction.value,
        )
    except ValueError as e:
        logger.warning("Workspace regime metric degraded: %s", e)
        return _fallback_workspace_metric(
            value=0.0,
            label="Regime unavailable",
            unit="%",
            sentiment="DEGRADED",
        )
    except Exception:
        logger.exception("Workspace regime metric failed")
        return _fallback_workspace_metric(
            value=0.0,
            label="Regime unavailable",
            unit="%",
            sentiment="ERROR",
        )


# =============================================================================
# Chart Endpoints
# =============================================================================

# Default chart lookback period
_DEFAULT_CHART_DAYS = 730


@workspace_router.get(
    "/charts/net-liquidity",
    summary="Net Liquidity Chart",
    openapi_extra={
        "widget_config": {
            "name": "Net Liquidity Time Series",
            "description": "Fed Net Liquidity (WALCL - TGA - RRP) over time",
            "category": "Macro Liquidity",
            "subCategory": "Fed",
            "type": "chart",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 20, "h": 8},
            "params": [
                {"paramName": "days", "value": "730", "label": "Lookback (days)", "type": "number", "show": True, "description": "Number of days of history to display (30-3650)"},
            ],
        }
    },
)
async def workspace_chart_net_liquidity(
    calculator: NetLiquidityCalcDep,
    days: Annotated[
        int,
        Query(ge=30, le=3650, description="Lookback period in days"),
    ] = _DEFAULT_CHART_DAYS,
) -> dict:
    """Net Liquidity time series as Plotly chart widget."""
    try:
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)
        history = await calculator.calculate(
            start_date=start_date, end_date=end_date
        )

        if history.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", showarrow=False, font=dict(size=20))
        else:
            clean = history["net_liquidity"].dropna()
            x_values = (
                history.loc[clean.index, "timestamp"].dt.strftime("%Y-%m-%d").tolist()
                if "timestamp" in history.columns
                else clean.index.tolist()
            )
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=clean.tolist(),
                    mode="lines",
                    name="Net Liquidity",
                    line=dict(color="#00d4aa", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(0, 212, 170, 0.1)",
                )
            )
            fig.update_layout(
                title="Fed Net Liquidity Index (B USD)",
                xaxis_title="Date",
                yaxis_title="Billions USD",
                template="plotly_dark",
                height=400,
            )

        return fig.to_plotly_json()
    except ValueError as e:
        logger.warning("Workspace net liquidity chart degraded: %s", e)
        return _fallback_workspace_chart(
            "Fed Net Liquidity Index (B USD)",
            f"Net Liquidity unavailable: {e}",
        )
    except Exception:
        logger.exception("Workspace net liquidity chart failed")
        return _fallback_workspace_chart(
            "Fed Net Liquidity Index (B USD)",
            "Net Liquidity unavailable",
        )


@workspace_router.get(
    "/charts/global-liquidity",
    summary="Global Liquidity Chart",
    openapi_extra={
        "widget_config": {
            "name": "Global Liquidity Breakdown",
            "description": "Central bank balance sheet contributions over time",
            "category": "Macro Liquidity",
            "subCategory": "Global",
            "type": "chart",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 20, "h": 8},
            "params": [
                {"paramName": "days", "value": "730", "label": "Lookback (days)", "type": "number", "show": True, "description": "Number of days of history to display (30-3650)"},
            ],
        }
    },
)
async def workspace_chart_global_liquidity(
    calculator: GlobalLiquidityCalcDep,
    days: Annotated[
        int,
        Query(ge=30, le=3650, description="Lookback period in days"),
    ] = _DEFAULT_CHART_DAYS,
) -> dict:
    """Global Liquidity breakdown as Plotly stacked area chart widget."""
    try:
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)
        history = await calculator.calculate(
            start_date=start_date, end_date=end_date, tier=1
        )

        if history.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available", showarrow=False, font=dict(size=20))
        else:
            cb_colors = {
                "fed_usd": ("#1f77b4", "Fed"),
                "ecb_usd": ("#ff7f0e", "ECB"),
                "boj_usd": ("#2ca02c", "BoJ"),
                "pboc_usd": ("#d62728", "PBoC"),
            }
            fig = go.Figure()
            for col, (color, name) in cb_colors.items():
                if col in history.columns:
                    clean = history[col].dropna()
                    fig.add_trace(
                        go.Scatter(
                            x=clean.index.tolist(),
                            y=clean.tolist(),
                            mode="lines",
                            name=name,
                            stackgroup="cb",
                            line=dict(color=color, width=1),
                        )
                    )
            fig.update_layout(
                title="Global Liquidity by Central Bank (B USD)",
                xaxis_title="Date",
                yaxis_title="Billions USD",
                template="plotly_dark",
                height=400,
            )

        return fig.to_plotly_json()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.exception("Workspace global liquidity chart failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# =============================================================================
# Volatility Metric Endpoints
# =============================================================================


@workspace_router.get(
    "/metrics/move-zscore",
    response_model=WorkspaceMetric,
    summary="MOVE Z-Score KPI",
    openapi_extra={
        "widget_config": {
            "name": "MOVE Z-Score",
            "description": "Bond volatility Z-Score (20-day rolling)",
            "category": "Macro Liquidity",
            "subCategory": "Volatility",
            "type": "metric",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 10, "h": 4},
        }
    },
)
async def workspace_metric_move_zscore(
    calculator: MOVEZScoreCalcDep,
) -> WorkspaceMetric:
    """MOVE Z-Score as Workspace metric widget."""
    try:
        result = await calculator.get_current()
        return WorkspaceMetric(
            value=round(result.zscore, 2),
            label=f"MOVE Z-Score ({result.signal.value})",
            delta=round(result.current_move, 1),
            unit="Z",
            sentiment=result.signal.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.exception("Workspace MOVE Z-Score metric failed")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@workspace_router.get(
    "/metrics/volatility-signal",
    response_model=WorkspaceMetric,
    summary="Volatility Signal KPI",
    openapi_extra={
        "widget_config": {
            "name": "Volatility Signal",
            "description": "Composite MOVE + VIX signal (-100 to +100)",
            "category": "Macro Liquidity",
            "subCategory": "Volatility",
            "type": "metric",
            "refetchInterval": 3600000,
            "staleTime": 1800000,
            "gridData": {"w": 10, "h": 4},
        }
    },
)
async def workspace_metric_volatility_signal(
    calculator: VolatilitySignalCalcDep,
) -> WorkspaceMetric:
    """Composite volatility signal as Workspace metric widget."""
    try:
        result = await calculator.get_current()
        return WorkspaceMetric(
            value=round(result.composite_score, 1),
            label=f"Vol Signal ({result.regime.value})",
            delta=None,
            unit="/100",
            sentiment=result.regime.value,
        )
    except ValueError as e:
        logger.warning("Workspace volatility signal metric degraded: %s", e)
        return _fallback_workspace_metric(
            value=0.0,
            label="Vol Signal unavailable",
            unit="/100",
            sentiment="DEGRADED",
        )
    except Exception:
        logger.exception("Workspace volatility signal metric failed")
        return _fallback_workspace_metric(
            value=0.0,
            label="Vol Signal unavailable",
            unit="/100",
            sentiment="ERROR",
        )
