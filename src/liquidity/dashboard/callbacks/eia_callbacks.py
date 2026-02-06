"""EIA Panel callbacks for dashboard interactivity.

Handles:
- Cushing inventory chart updates
- Refinery utilization chart and signal updates
- Supply (production/imports) chart updates
"""

import asyncio
import logging
from typing import Any

import pandas as pd
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
    try:
        return asyncio.run(_fetch_eia_data_async())
    except Exception as e:
        logger.warning("EIA async fetch failed: %s, using mock data", e)
        return _get_mock_eia_data()


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

    # Merge with mock data for any missing fields
    mock_data = _get_mock_eia_data()
    return {**mock_data, **data}


def _get_mock_eia_data() -> dict[str, Any]:
    """Get mock EIA data for testing/demo.

    Returns:
        Dictionary with sample EIA data.
    """
    from datetime import UTC, datetime

    import numpy as np

    # Generate 52 weeks of data
    dates = pd.date_range(
        end=datetime.now(UTC),
        periods=52,
        freq="W",
    )

    # Cushing inventory (thousand barrels)
    # Normal range: 20,000 - 50,000 KB
    cushing_base = 35000
    cushing_values = cushing_base + np.cumsum(np.random.randn(52) * 500)
    cushing_values = np.clip(cushing_values, 20000, 60000)

    cushing_df = pd.DataFrame({
        "timestamp": dates,
        "series_id": "W_EPC0_SAX_YCUOK_MBBL",
        "source": "mock",
        "value": cushing_values,
        "unit": "thousand_barrels",
    })

    # Refinery utilization (percent)
    # Generate for US total and PADDs
    refinery_data = []
    for series_id, base_util in [
        ("WPULEUS3", 92),  # US total
        ("W_NA_YUP_R10_PER", 88),  # PADD 1
        ("W_NA_YUP_R30_PER", 95),  # PADD 3
        ("W_NA_YUP_R50_PER", 90),  # PADD 5
    ]:
        util_values = base_util + np.random.randn(52) * 2
        util_values = np.clip(util_values, 75, 100)
        for i, dt in enumerate(dates):
            refinery_data.append({
                "timestamp": dt,
                "series_id": series_id,
                "source": "mock",
                "value": util_values[i],
                "unit": "percent",
            })

    refinery_df = pd.DataFrame(refinery_data)

    # Production (thousand b/d)
    production_base = 13000
    production_values = production_base + np.cumsum(np.random.randn(52) * 50)

    production_df = pd.DataFrame({
        "timestamp": dates,
        "series_id": "WCRFPUS2",
        "source": "mock",
        "value": production_values,
        "unit": "thousand_bpd",
    })

    # Imports (thousand b/d)
    imports_base = 6000
    imports_values = imports_base + np.random.randn(52) * 200

    imports_df = pd.DataFrame({
        "timestamp": dates,
        "series_id": "WCRIMUS2",
        "source": "mock",
        "value": imports_values,
        "unit": "thousand_bpd",
    })

    # Calculate utilization percentage
    latest_cushing = cushing_values[-1]
    cushing_utilization_pct = (latest_cushing / 70800) * 100

    # Calculate refinery signal based on US total
    us_util = refinery_df[refinery_df["series_id"] == "WPULEUS3"]["value"].iloc[-1]
    if us_util > 95:
        refinery_signal = "TIGHT"
    elif us_util > 90:
        refinery_signal = "NORMAL"
    elif us_util > 85:
        refinery_signal = "SOFT"
    else:
        refinery_signal = "WEAK"

    return {
        "cushing_df": cushing_df,
        "cushing_utilization_pct": cushing_utilization_pct,
        "refinery_df": refinery_df,
        "refinery_signal": refinery_signal,
        "production_df": production_df,
        "imports_df": imports_df,
    }


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
