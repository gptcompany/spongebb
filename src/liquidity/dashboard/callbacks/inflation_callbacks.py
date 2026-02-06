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

import pandas as pd
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
        """Update all inflation panel components.

        Triggered by auto-refresh interval.

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
    try:
        return asyncio.run(_fetch_inflation_data_async())
    except Exception as e:
        logger.warning("Inflation async fetch failed: %s, using mock data", e)
        return _get_mock_inflation_data()


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

    # Merge with mock data for any missing fields
    mock_data = _get_mock_inflation_data()
    return {**mock_data, **data}


def _get_mock_inflation_data() -> dict[str, Any]:
    """Get mock inflation data for testing/demo.

    Returns:
        Dictionary with sample inflation data.
    """
    from datetime import UTC, datetime

    import numpy as np

    # Generate 365 days of data
    dates = pd.date_range(
        end=datetime.now(UTC),
        periods=365,
        freq="D",
    )

    # TIPS yields - simulate realistic patterns
    # 10Y TIPS: around 2% with some variation
    tips_10y_base = 2.0
    tips_10y_trend = np.cumsum(np.random.randn(365) * 0.02)
    tips_10y = tips_10y_base + tips_10y_trend
    tips_10y = np.clip(tips_10y, 0.5, 3.5)

    # 5Y TIPS: slightly lower, correlated with 10Y
    tips_5y = tips_10y - 0.3 + np.random.randn(365) * 0.1
    tips_5y = np.clip(tips_5y, 0.3, 3.2)

    # Nominal yields (for BEI calculation)
    # Nominal = TIPS + breakeven, assume ~2.2% breakeven
    bei_base = 2.2
    bei_noise = np.cumsum(np.random.randn(365) * 0.01)
    bei_10y = bei_base + bei_noise
    bei_10y = np.clip(bei_10y, 1.5, 3.0)

    bei_5y = bei_10y + np.random.randn(365) * 0.1 - 0.1
    bei_5y = np.clip(bei_5y, 1.4, 3.1)

    # 5Y5Y forward: 2 * bei_10y - bei_5y
    forward_5y5y = 2 * bei_10y - bei_5y

    nominal_10y = tips_10y + bei_10y
    nominal_5y = tips_5y + bei_5y

    breakeven_df = pd.DataFrame(
        {
            "timestamp": dates,
            "tips_10y": tips_10y,
            "tips_5y": tips_5y,
            "nominal_10y": nominal_10y,
            "nominal_5y": nominal_5y,
            "bei_10y": bei_10y,
            "bei_5y": bei_5y,
            "forward_5y5y": forward_5y5y,
        }
    )

    # Oil-rates correlation data
    # Oil price returns
    oil_prices = 75 + np.cumsum(np.random.randn(365) * 0.5)
    oil_prices = np.clip(oil_prices, 50, 100)
    oil_ret = np.diff(oil_prices) / oil_prices[:-1]
    oil_ret = np.insert(oil_ret, 0, 0)

    # Rates diff (first difference of TIPS yields)
    rates_diff = np.diff(tips_10y)
    rates_diff = np.insert(rates_diff, 0, 0)

    # Assign regimes based on rolling correlation
    regimes = []
    window = 30
    for i in range(len(oil_ret)):
        if i < window:
            regimes.append("unknown")
        else:
            corr = np.corrcoef(oil_ret[i - window : i], rates_diff[i - window : i])[0, 1]
            if np.isnan(corr):
                regimes.append("unknown")
            elif corr < -0.7:
                regimes.append("surge")
            elif corr > -0.3:
                regimes.append("breakdown")
            else:
                regimes.append("normal")

    oil_rates_df = pd.DataFrame(
        {
            "timestamp": dates,
            "oil_price": oil_prices,
            "real_10y": tips_10y,
            "oil_ret": oil_ret,
            "rates_diff": rates_diff,
            "regime": regimes,
        }
    )

    # Calculate rolling correlations for mock data
    oil_rates_df["corr_30d"] = (
        oil_rates_df["oil_ret"].rolling(window=30, min_periods=15).corr(oil_rates_df["rates_diff"])
    )

    oil_rates_df["corr_90d"] = (
        oil_rates_df["oil_ret"].rolling(window=90, min_periods=45).corr(oil_rates_df["rates_diff"])
    )

    # Get latest values
    latest_bei_10y = bei_10y[-1]
    latest_bei_5y = bei_5y[-1]
    latest_forward_5y5y = forward_5y5y[-1]
    latest_tips_10y = tips_10y[-1]

    # Get latest correlation
    valid_corr = oil_rates_df["corr_30d"].dropna()
    latest_oil_corr = valid_corr.iloc[-1] if len(valid_corr) > 0 else None
    latest_regime = regimes[-1]

    return {
        "breakeven_df": breakeven_df,
        "oil_rates_df": oil_rates_df,
        "bei_10y": float(latest_bei_10y),
        "bei_5y": float(latest_bei_5y),
        "forward_5y5y": float(latest_forward_5y5y),
        "tips_10y": float(latest_tips_10y),
        "oil_corr": float(latest_oil_corr) if latest_oil_corr is not None else None,
        "regime": latest_regime,
    }


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
