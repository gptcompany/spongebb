"""Inflation Panel callbacks for dashboard interactivity.

Handles:
- Real rates chart updates (TIPS yields)
- Breakeven inflation chart updates
- Oil vs real rates scatter updates
- Summary metrics updates
"""

import asyncio
import logging
import os
from typing import Any

import pandas as pd
from dash import Dash, Input, Output

from liquidity.dashboard.components.inflation import (
    create_breakeven_chart,
    create_inflation_summary,
    create_oil_rates_scatter,
    create_real_rates_chart,
)

logger = logging.getLogger(__name__)


def _env_flag(name: str) -> bool:
    """Return True if environment variable is set to a truthy value."""
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _build_mock_inflation_data() -> dict[str, Any]:
    """Return deterministic inflation data for fallback mode."""
    dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=60, freq="D")
    breakeven_df = pd.DataFrame(
        {
            "timestamp": dates,
            "bei_10y": [2.05 + (i % 7) * 0.03 for i in range(len(dates))],
            "bei_5y": [2.15 + (i % 6) * 0.025 for i in range(len(dates))],
            "forward_5y5y": [2.25 + (i % 5) * 0.02 for i in range(len(dates))],
            "tips_10y": [1.55 + (i % 4) * 0.02 for i in range(len(dates))],
            "tips_5y": [1.35 + (i % 4) * 0.02 for i in range(len(dates))],
        }
    )
    oil_rates_df = pd.DataFrame(
        {
            "rates_diff": [(-0.3 + (i * 0.02)) for i in range(30)] + [(0.05 + (i * 0.015)) for i in range(30)],
            "oil_ret": [(-0.08 + (i * 0.004)) for i in range(30)] + [(0.01 + (i * 0.003)) for i in range(30)],
            "regime": ["normal"] * 30 + ["breakdown"] * 30,
        }
    )

    latest = breakeven_df.iloc[-1]
    return {
        "breakeven_df": breakeven_df,
        "oil_rates_df": oil_rates_df,
        "bei_10y": float(latest["bei_10y"]),
        "forward_5y5y": float(latest["forward_5y5y"]),
        "tips_10y": float(latest["tips_10y"]),
        "oil_corr": 0.42,
        "regime": "Normal",
    }


def register_inflation_callbacks(app: Dash) -> None:
    """Register inflation panel callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        [
            Output("real-rates-chart", "figure"),
            Output("breakeven-chart", "figure"),
            Output("oil-rates-scatter", "figure"),
            Output("inflation-summary", "children"),
        ],
        [Input("refresh-interval", "n_intervals")],
        prevent_initial_call=False,
    )
    def update_inflation_panel(n_intervals: int) -> tuple:  # noqa: ARG001
        """Update all inflation panel components."""
        return update_inflation_panel_logic()


def update_inflation_panel_logic() -> tuple:
    """Logic for updating all inflation panel components.

    Separated from callback registration for testability.

    Returns:
        Tuple of updated component values for inflation panel.
    """
    logger.info("Inflation panel update triggered")

    try:
        # Fetch inflation data
        data = _fetch_inflation_data()

        # Real rates chart
        real_rates_fig = create_real_rates_chart(data.get("breakeven_df"))

        # Breakeven chart
        breakeven_fig = create_breakeven_chart(data.get("breakeven_df"))

        # Oil-rates scatter
        scatter_fig = create_oil_rates_scatter(data.get("oil_rates_df"))

        # Summary
        summary = create_inflation_summary(
            bei_10y=data.get("bei_10y"),
            forward_5y5y=data.get("forward_5y5y"),
            tips_10y=data.get("tips_10y"),
            oil_corr=data.get("oil_corr"),
            regime=data.get("regime"),
        )

        return (
            real_rates_fig,
            breakeven_fig,
            scatter_fig,
            summary,
        )

    except Exception as e:
        logger.error("Inflation panel update failed: %s", e)
        return _get_inflation_error_response()


def _fetch_inflation_data() -> dict[str, Any]:
    """Fetch inflation data from analyzers.

    Returns:
        Dictionary with inflation data for all panel components.
    """
    return asyncio.run(_fetch_inflation_data_async())


async def _fetch_inflation_data_async() -> dict[str, Any]:
    """Async function to fetch inflation data from analyzers.

    Returns:
        Dictionary with real inflation data.
    """
    import importlib.util

    if _env_flag("LIQUIDITY_DASHBOARD_FORCE_FALLBACK"):
        return _build_mock_inflation_data()

    data: dict[str, Any] = {}

    # Try to fetch from RealRatesAnalyzer
    if importlib.util.find_spec("liquidity.analyzers.real_rates"):
        try:
            from liquidity.analyzers.real_rates import RealRatesAnalyzer

            analyzer = RealRatesAnalyzer()

            # Fetch breakeven data (last 365 days)
            breakeven_df = await analyzer.calculate_breakeven()

            if not breakeven_df.empty:
                data["breakeven_df"] = breakeven_df

                # Get latest values
                latest = breakeven_df.iloc[-1]
                data["bei_10y"] = float(latest["bei_10y"])
                data["bei_5y"] = float(latest["bei_5y"])
                data["forward_5y5y"] = float(latest["forward_5y5y"])
                data["tips_10y"] = float(latest["tips_10y"])
                data["tips_5y"] = float(latest["tips_5y"])

        except Exception as e:
            logger.warning("RealRatesAnalyzer failed: %s", e)

    # Try to fetch from OilRealRatesAnalyzer
    if importlib.util.find_spec("liquidity.analyzers.oil_real_rates"):
        try:
            from liquidity.analyzers.oil_real_rates import OilRealRatesAnalyzer

            oil_analyzer = OilRealRatesAnalyzer()

            # Fetch correlation data
            oil_rates_df = await oil_analyzer.compute_correlation()

            if not oil_rates_df.empty:
                data["oil_rates_df"] = oil_rates_df

                # Get current state
                try:
                    state = await oil_analyzer.get_current_state()
                    data["oil_corr"] = state.corr_30d
                    data["regime"] = state.regime
                except ValueError:
                    # Not enough data for current state
                    pass

        except Exception as e:
            logger.warning("OilRealRatesAnalyzer failed: %s", e)

    return data


def _get_inflation_error_response() -> tuple:
    """Get error response for inflation callback.

    Returns:
        Tuple with empty/default values for inflation outputs.
    """
    from dash import html

    empty_real_rates = create_real_rates_chart(None)
    empty_breakeven = create_breakeven_chart(None)
    empty_scatter = create_oil_rates_scatter(None)
    empty_summary = html.Div("Data unavailable", className="text-muted text-center")

    return (
        empty_real_rates,
        empty_breakeven,
        empty_scatter,
        empty_summary,
    )
