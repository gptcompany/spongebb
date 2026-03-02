"""Inflation Panel callbacks for dashboard interactivity.

Handles:
- Real rates chart updates (TIPS yields)
- Breakeven inflation chart updates
- Oil vs real rates scatter updates
- Summary metrics updates
"""

import asyncio
import logging
from typing import Any

from dash import Dash, Input, Output

from liquidity.dashboard.components.inflation import (
    create_breakeven_chart,
    create_inflation_summary,
    create_oil_rates_scatter,
    create_real_rates_chart,
)

logger = logging.getLogger(__name__)


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
