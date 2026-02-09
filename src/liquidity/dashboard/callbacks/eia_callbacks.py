"""EIA Panel callbacks for dashboard interactivity.

Handles:
- Cushing inventory chart updates
- Refinery utilization chart and signal updates
- Supply (production/imports) chart updates
"""

import asyncio
import logging
from typing import Any

from dash import Dash, Input, Output

from liquidity.dashboard.components.eia_panel import (
    create_cushing_chart,
    create_cushing_utilization_badge,
    create_refinery_chart,
    create_refinery_signal_badge,
    create_supply_chart,
)

logger = logging.getLogger(__name__)


def register_eia_callbacks(app: Dash) -> None:
    """Register EIA panel callbacks.

    Args:
        app: The Dash application instance.
    """

    @app.callback(
        [
            Output("cushing-inventory-chart", "figure"),
            Output("cushing-utilization-badge", "children"),
            Output("refinery-utilization-chart", "figure"),
            Output("refinery-signal-badge", "children"),
            Output("crude-production-chart", "figure"),
            Output("crude-imports-chart", "figure"),
        ],
        [Input("refresh-interval", "n_intervals")],
        prevent_initial_call=False,
    )
    def update_eia_panel(n_intervals: int) -> tuple:  # noqa: ARG001
        """Update all EIA panel components.

        Triggered by auto-refresh interval.

        Returns:
            Tuple of updated component values for EIA panel.
        """
        logger.info("EIA panel update triggered")

        try:
            # Fetch EIA data
            data = _fetch_eia_data()

            # Cushing tab
            cushing_fig = create_cushing_chart(data.get("cushing_df"))
            cushing_badge = create_cushing_utilization_badge(
                data.get("cushing_utilization_pct")
            )

            # Refinery tab
            refinery_fig = create_refinery_chart(data.get("refinery_df"))
            refinery_badge = create_refinery_signal_badge(data.get("refinery_signal"))

            # Supply tab
            production_fig, imports_fig = create_supply_chart(
                data.get("production_df"),
                data.get("imports_df"),
            )

            return (
                cushing_fig,
                cushing_badge,
                refinery_fig,
                refinery_badge,
                production_fig,
                imports_fig,
            )

        except Exception as e:
            logger.error("EIA panel update failed: %s", e)
            return _get_eia_error_response()


def _fetch_eia_data() -> dict[str, Any]:
    """Fetch EIA data from collector.

    Returns:
        Dictionary with EIA data for all panel components.
    """
    return asyncio.run(_fetch_eia_data_async())


async def _fetch_eia_data_async() -> dict[str, Any]:
    """Async function to fetch EIA data from collector.

    Returns:
        Dictionary with real EIA data.
    """
    import importlib.util

    data: dict[str, Any] = {}

    if importlib.util.find_spec("liquidity.collectors.eia"):
        try:
            from liquidity.collectors.eia import CUSHING_CAPACITY_KB, EIACollector

            collector = EIACollector()

            # Fetch Cushing inventory
            cushing_df = await collector.collect_cushing(lookback_weeks=52)
            if not cushing_df.empty:
                data["cushing_df"] = cushing_df

                # Calculate utilization
                latest_value = cushing_df.sort_values("timestamp").iloc[-1]["value"]
                utilization_pct = (latest_value / CUSHING_CAPACITY_KB) * 100
                data["cushing_utilization_pct"] = utilization_pct

            # Fetch refinery utilization
            refinery_df = await collector.collect_refinery_utilization(lookback_weeks=52)
            if not refinery_df.empty:
                data["refinery_df"] = refinery_df

                # Calculate signal
                try:
                    signal = collector.calculate_utilization_signal(refinery_df)
                    data["refinery_signal"] = signal
                except ValueError:
                    data["refinery_signal"] = None

            # Fetch production
            production_df = await collector.collect_production()
            if not production_df.empty:
                data["production_df"] = production_df

            # Fetch imports
            imports_df = await collector.collect_imports()
            if not imports_df.empty:
                data["imports_df"] = imports_df

            await collector.close()

        except Exception as e:
            logger.warning("EIA collector failed: %s", e)

    return data


def _get_eia_error_response() -> tuple:
    """Get error response for EIA callback.

    Returns:
        Tuple with empty/default values for EIA outputs.
    """
    from dash import html

    empty_cushing = create_cushing_chart(None)
    empty_refinery = create_refinery_chart(None)
    production_fig, imports_fig = create_supply_chart(None, None)

    return (
        empty_cushing,
        html.Div("--", className="text-muted text-center"),
        empty_refinery,
        html.Div("--", className="text-muted text-center"),
        production_fig,
        imports_fig,
    )
