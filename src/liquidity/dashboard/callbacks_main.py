"""Dashboard callbacks for interactivity.

Handles:
- Data refresh (manual and automatic)
- Chart updates for all panels
- Export functionality
"""

import asyncio
import logging
import math
import os
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, callback_context

from liquidity.dashboard.components.calendar import (
    add_calendar_overlay,
    create_calendar_events_from_dict,
)
from liquidity.dashboard.components.commodities import (
    create_commodity_chart,
    create_commodity_summary,
    create_oil_chart,
)
from liquidity.dashboard.components.consumer_credit import (
    create_axp_igv_spread_chart,
    create_consumer_credit_metrics,
    create_sensitive_stocks_table,
    create_xlp_xly_ratio_chart,
)
from liquidity.dashboard.components.correlations import (
    create_correlation_alerts,
    create_correlation_heatmap,
)
from liquidity.dashboard.components.flows import (
    create_etf_flows_chart,
    create_tic_chart,
)
from liquidity.dashboard.components.fomc_diff import (
    create_change_summary,
    create_diff_view,
    create_empty_diff_view,
    create_error_diff_view,
    get_available_dates_options,
    parse_date_value,
)
from liquidity.dashboard.components.fx import create_dxy_chart, create_fx_metrics
from liquidity.dashboard.components.liquidity import (
    create_global_liquidity_chart,
    create_liquidity_metrics,
    create_net_liquidity_chart,
)
from liquidity.dashboard.components.news import (
    create_news_items_list,
)
from liquidity.dashboard.components.quality import (
    create_quality_gauge,
    create_quality_status_bar,
    create_source_freshness_table,
)
from liquidity.dashboard.components.regime import (
    create_regime_gauge,
    create_regime_indicator,
    create_regime_metrics,
)
from liquidity.dashboard.components.stress import (
    create_repo_stress_gauge,
    create_sofr_ois_gauge,
    create_stress_status,
    get_overall_regime,
)
from liquidity.dashboard.export import HTMLExporter

logger = logging.getLogger(__name__)


def _env_flag(name: str) -> bool:
    """Return True if environment variable is set to a truthy value."""
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _dashboard_now() -> datetime:
    """Return deterministic UTC now when fixed timestamp is configured."""
    fixed_now = os.getenv("LIQUIDITY_DASHBOARD_FIXED_NOW", "").strip()
    if fixed_now:
        try:
            parsed = datetime.fromisoformat(fixed_now.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            logger.warning(
                "Invalid LIQUIDITY_DASHBOARD_FIXED_NOW=%s, using realtime clock",
                fixed_now,
            )
    return datetime.now(UTC)


def register_callbacks(app: Dash) -> None:
    """Register all dashboard callbacks.

    Args:
        app: The Dash application instance.
    """

    # Main dashboard update callback
    @app.callback(
        [
            # Liquidity outputs
            Output("net-liquidity-chart", "figure"),
            Output("global-liquidity-chart", "figure"),
            Output("net-liquidity-metrics", "children"),
            Output("global-liquidity-metrics", "children"),
            # Regime outputs
            Output("regime-indicator", "children"),
            Output("regime-gauge", "figure"),
            Output("regime-metrics", "children"),
            # Status outputs
            Output("last-update-time", "children"),
            Output("data-quality-score", "children"),
            Output("dashboard-data-store", "data"),
        ],
        [
            Input("refresh-interval", "n_intervals"),
            Input("refresh-btn", "n_clicks"),
        ],
        [State("dashboard-data-store", "data")],
        prevent_initial_call=False,
    )
    def update_main_dashboard(
        n_intervals: int,  # noqa: ARG001
        n_clicks: int | None,  # noqa: ARG001
        stored_data: dict[str, Any] | None,  # noqa: ARG001
    ) -> tuple:
        """Refresh main dashboard panels (liquidity + regime).

        Triggered by auto-refresh interval or manual refresh button.

        Returns:
            Tuple of updated component values.
        """
        ctx = callback_context
        trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else "initial"

        logger.info("Main dashboard update triggered by: %s", trigger)

        try:
            # Fetch fresh data
            data = _fetch_dashboard_data()

            # Create chart figures
            net_liq_fig = create_net_liquidity_chart(data.get("net_liquidity_df"))
            global_liq_fig = create_global_liquidity_chart(data.get("global_liquidity_df"))

            # Add calendar overlay if events are available
            calendar_events = data.get("calendar_events", [])
            if calendar_events:
                net_liq_fig = add_calendar_overlay(
                    net_liq_fig,
                    [e for e in calendar_events if e.get("impact") == "high"],
                    high_impact_only=True,
                )

            # Create regime components
            regime = data.get("regime", {})
            regime_indicator = create_regime_indicator(
                regime=regime.get("direction", "EXPANSION"),
                intensity=regime.get("intensity", 50),
                confidence=regime.get("confidence", "MEDIUM"),
            )
            regime_gauge = create_regime_gauge(
                intensity=regime.get("intensity", 50),
                regime=regime.get("direction", "EXPANSION"),
            )
            regime_metrics = create_regime_metrics(
                net_liq_percentile=regime.get("net_liq_percentile", 0.5),
                global_liq_percentile=regime.get("global_liq_percentile", 0.5),
                stealth_qe_score=regime.get("stealth_qe_score", 0.5),
            )

            # Create liquidity metrics
            net_metrics = data.get("net_metrics", {})
            net_liq_metrics = create_liquidity_metrics(
                current_value=net_metrics.get("current", 0),
                weekly_delta=net_metrics.get("weekly_delta", 0),
                monthly_delta=net_metrics.get("monthly_delta", 0),
                delta_60d=net_metrics.get("delta_60d", 0),
                delta_90d=net_metrics.get("delta_90d", 0),
                label="Current",
            )

            global_metrics = data.get("global_metrics", {})
            global_liq_metrics = create_liquidity_metrics(
                current_value=global_metrics.get("current", 0),
                weekly_delta=global_metrics.get("weekly_delta", 0),
                monthly_delta=global_metrics.get("monthly_delta", 0),
                delta_60d=global_metrics.get("delta_60d", 0),
                delta_90d=global_metrics.get("delta_90d", 0),
                label="Current",
            )

            # Update status
            last_update = _dashboard_now().strftime("%Y-%m-%d %H:%M UTC")
            quality_score = f"{data.get('quality_score', 100):.0f}%"

            # Store data for potential export
            store_data = {
                "last_update": last_update,
                "regime": regime,
                "net_metrics": net_metrics,
                "global_metrics": global_metrics,
            }

            return (
                net_liq_fig,
                global_liq_fig,
                net_liq_metrics,
                global_liq_metrics,
                regime_indicator,
                regime_gauge,
                regime_metrics,
                last_update,
                quality_score,
                store_data,
            )

        except Exception as e:
            logger.error("Main dashboard update failed: %s", e)
            return _get_error_response(str(e))

    # Extended panels update callback
    @app.callback(
        [
            # FX outputs
            Output("dxy-chart", "figure"),
            Output("eurusd-value", "children"),
            Output("usdjpy-value", "children"),
            Output("usdcny-value", "children"),
            # Commodities outputs
            Output("gold-chart", "figure"),
            Output("copper-chart", "figure"),
            Output("oil-chart", "figure"),
            Output("commodity-summary", "children"),
            # Stress outputs
            Output("sofr-ois-gauge", "figure"),
            Output("repo-stress-gauge", "figure"),
            Output("stress-status", "children"),
            # Flows outputs
            Output("tic-flows-chart", "figure"),
            Output("etf-flows-chart", "figure"),
            # Correlation outputs
            Output("correlation-heatmap", "figure"),
            Output("correlation-alerts", "children"),
            # Consumer credit risk outputs
            Output("xlp-xly-ratio-chart", "figure"),
            Output("axp-igv-spread-chart", "figure"),
            Output("consumer-credit-metrics", "children"),
            Output("consumer-credit-sensitive-stocks", "children"),
            # Calendar outputs
            Output("calendar-events", "children"),
        ],
        [Input("refresh-interval", "n_intervals")],
        prevent_initial_call=False,
    )
    def update_extended_panels(n_intervals: int) -> tuple:  # noqa: ARG001
        """Update all extended dashboard panels.

        Triggered by auto-refresh interval.

        Returns:
            Tuple of updated component values for extended panels.
        """
        logger.info("Extended panels update triggered")

        try:
            # Fetch extended panel data
            data = _fetch_extended_data()

            # FX panel
            dxy_fig = create_dxy_chart(data.get("dxy_df"))
            fx_metrics = create_fx_metrics(
                eurusd=data.get("fx", {}).get("eurusd"),
                usdjpy=data.get("fx", {}).get("usdjpy"),
                usdcny=data.get("fx", {}).get("usdcny"),
            )

            # Commodities panel
            gold_fig = create_commodity_chart(data.get("gold_df"), "gold")
            copper_fig = create_commodity_chart(data.get("copper_df"), "copper")
            oil_fig = create_oil_chart(data.get("wti_df"), data.get("brent_df"))
            commodities_dict = data.get("commodities", {})
            commodity_summary = create_commodity_summary(
                gold_price=commodities_dict.get("gold"),
                copper_price=commodities_dict.get("copper"),
                wti_price=commodities_dict.get("wti"),
            )

            # Stress panel
            stress_data = data.get("stress", {})
            sofr_ois_gauge = create_sofr_ois_gauge(stress_data.get("sofr_ois"))
            repo_stress_gauge = create_repo_stress_gauge(stress_data.get("repo_stress"))
            stress_regime = get_overall_regime(
                sofr_ois=stress_data.get("sofr_ois"),
                repo_stress=stress_data.get("repo_stress"),
            )
            stress_status = create_stress_status(
                regime=stress_regime,
                sofr_ois=stress_data.get("sofr_ois"),
                repo_stress=stress_data.get("repo_stress"),
            )

            # Flows panel
            tic_fig = create_tic_chart(data.get("tic_df"))
            etf_fig = create_etf_flows_chart(data.get("etf_df"))

            # Correlation panel
            corr_heatmap = create_correlation_heatmap(data.get("correlation_matrix"))
            corr_alerts = create_correlation_alerts(
                data.get("current_correlations"),
                data.get("previous_correlations"),
            )

            # Consumer credit risk panel
            xlp_xly_fig = create_xlp_xly_ratio_chart(data.get("xlp_xly_df"))
            axp_igv_fig = create_axp_igv_spread_chart(data.get("axp_igv_df"))
            credit_metrics = create_consumer_credit_metrics(
                data.get("consumer_credit_metrics")
            )
            sensitive_stocks = create_sensitive_stocks_table(
                data.get("sensitive_stocks_df"),
            )

            # Calendar panel
            calendar_events = create_calendar_events_from_dict(data.get("calendar_events", []))

            return (
                dxy_fig,
                fx_metrics.get("eurusd-value", "--"),
                fx_metrics.get("usdjpy-value", "--"),
                fx_metrics.get("usdcny-value", "--"),
                gold_fig,
                copper_fig,
                oil_fig,
                commodity_summary,
                sofr_ois_gauge,
                repo_stress_gauge,
                stress_status,
                tic_fig,
                etf_fig,
                corr_heatmap,
                corr_alerts,
                xlp_xly_fig,
                axp_igv_fig,
                credit_metrics,
                sensitive_stocks,
                calendar_events,
            )

        except Exception as e:
            logger.error("Extended panels update failed: %s", e)
            return _get_extended_error_response()

    # Export callback - full HTML export with all charts
    @app.callback(
        Output("download-html", "data"),
        Input("export-btn", "n_clicks"),
        [
            State("net-liquidity-chart", "figure"),
            State("global-liquidity-chart", "figure"),
            State("regime-gauge", "figure"),
            State("dxy-chart", "figure"),
            State("correlation-heatmap", "figure"),
            State("dashboard-data-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def export_dashboard(
        n_clicks: int | None,
        net_liq_fig: dict | None,
        global_liq_fig: dict | None,
        regime_fig: dict | None,
        dxy_fig: dict | None,
        corr_fig: dict | None,
        stored_data: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Export dashboard as standalone HTML file with all charts.

        Args:
            n_clicks: Number of export button clicks.
            net_liq_fig: Net Liquidity chart figure dict.
            global_liq_fig: Global Liquidity chart figure dict.
            regime_fig: Regime gauge figure dict.
            dxy_fig: DXY chart figure dict.
            corr_fig: Correlation heatmap figure dict.
            stored_data: Dashboard data store.

        Returns:
            Download data for HTML file, or None.
        """
        if not n_clicks:
            return None  # type: ignore[return-value]

        try:
            exporter = HTMLExporter()

            # Convert figure dicts to Figure objects
            figures: dict[str, go.Figure] = {}

            if net_liq_fig:
                figures["Net Liquidity Index"] = go.Figure(net_liq_fig)
            if global_liq_fig:
                figures["Global Liquidity Index"] = go.Figure(global_liq_fig)
            if regime_fig:
                figures["Regime Indicator"] = go.Figure(regime_fig)
            if dxy_fig:
                figures["Dollar Index (DXY)"] = go.Figure(dxy_fig)
            if corr_fig:
                figures["Correlation Heatmap"] = go.Figure(corr_fig)

            # Get quality metadata
            metadata = {
                "quality_score": stored_data.get("quality_score", "N/A") if stored_data else "N/A",
                "stale_sources": stored_data.get("stale_sources", []) if stored_data else [],
            }

            # Generate HTML content
            timestamp = _dashboard_now().strftime("%Y%m%d_%H%M")
            filename = f"liquidity_dashboard_{timestamp}.html"

            if figures:
                content = exporter.get_export_content(
                    figures=figures,
                    title="Global Liquidity Monitor",
                    metadata=metadata,
                )
            else:
                # Fallback if no figures available
                content = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Global Liquidity Monitor Export - {timestamp}</title></head>
                <body style="background:#1a1a2e;color:#eee;font-family:sans-serif;padding:20px;">
                <h1 style="color:#00ff88;">Global Liquidity Monitor</h1>
                <p>Exported at: {_dashboard_now().isoformat()}</p>
                <p>No chart data available for export.</p>
                </body>
                </html>
                """

            return {"content": content, "filename": filename}

        except Exception as e:
            logger.error("Export failed: %s", e)
            return None  # type: ignore[return-value]

    # Quality indicators callback
    @app.callback(
        [
            Output("quality-status-bar", "children"),
            Output("freshness-gauge", "figure"),
            Output("completeness-gauge", "figure"),
            Output("validation-gauge", "figure"),
            Output("source-freshness-table", "children"),
        ],
        Input("refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_quality_indicators(n_intervals: int) -> tuple:  # noqa: ARG001
        """Update all quality indicators.

        Triggered by auto-refresh interval.

        Returns:
            Tuple of updated quality components.
        """
        try:
            # Fetch quality data
            quality_data = _fetch_quality_data()

            # Create quality status bar
            quality_report = quality_data.get("quality_report")
            status_bar = create_quality_status_bar(quality_report)

            # Create gauge figures
            freshness_gauge = create_quality_gauge(
                quality_data.get("freshness_score", 100),
                "Freshness",
            )
            completeness_gauge = create_quality_gauge(
                quality_data.get("completeness_score", 100),
                "Completeness",
            )
            validation_gauge = create_quality_gauge(
                quality_data.get("validation_score", 100),
                "Validation",
            )

            # Create source freshness table
            last_updates = quality_data.get("last_updates", {})
            freshness_status = quality_data.get("freshness_status", {})
            source_table = create_source_freshness_table(last_updates, freshness_status)

            return (
                status_bar,
                freshness_gauge,
                completeness_gauge,
                validation_gauge,
                source_table,
            )

        except Exception as e:
            logger.error("Quality indicators update failed: %s", e)
            return _get_quality_error_response()

    # Quality detail panel collapse callback
    @app.callback(
        [
            Output("quality-collapse", "is_open"),
            Output("quality-collapse-icon", "className"),
        ],
        Input("quality-collapse-toggle", "n_clicks"),
        State("quality-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_quality_panel(
        n_clicks: int | None,
        is_open: bool,
    ) -> tuple[bool, str]:
        """Toggle the quality detail panel collapse state.

        Args:
            n_clicks: Number of toggle button clicks.
            is_open: Current collapse state.

        Returns:
            Tuple of (new_is_open, icon_class).
        """
        if not n_clicks:
            return (is_open, "bi bi-chevron-down ms-2")  # Return current state

        new_is_open = not is_open
        icon_class = "bi bi-chevron-up ms-2" if new_is_open else "bi bi-chevron-down ms-2"

        return new_is_open, icon_class

    # News panel update callback
    @app.callback(
        Output("news-items-container", "children"),
        [
            Input("refresh-interval", "n_intervals"),
            Input("news-filter-all", "n_clicks"),
            Input("news-filter-fed", "n_clicks"),
            Input("news-filter-ecb", "n_clicks"),
            Input("news-filter-boj", "n_clicks"),
        ],
        prevent_initial_call=False,
    )
    def update_news_panel(
        n_intervals: int,  # noqa: ARG001
        all_clicks: int,  # noqa: ARG001
        fed_clicks: int,  # noqa: ARG001
        ecb_clicks: int,  # noqa: ARG001
        boj_clicks: int,  # noqa: ARG001
    ) -> Any:
        """Update news panel with latest items and apply filter.

        Triggered by auto-refresh interval or filter button clicks.

        Returns:
            Div containing filtered news items.
        """
        ctx = callback_context

        # Determine which filter is active based on trigger
        filter_source = "all"
        if ctx.triggered:
            trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
            if trigger_id == "news-filter-fed":
                filter_source = "fed"
            elif trigger_id == "news-filter-ecb":
                filter_source = "ecb"
            elif trigger_id == "news-filter-boj":
                filter_source = "boj"

        try:
            # Fetch news data
            news_items = _fetch_news_data()

            # Create news items list with filter
            return create_news_items_list(news_items, filter_source=filter_source)

        except Exception as e:
            logger.error("News panel update failed: %s", e)
            from dash import html

            return html.Div(
                html.Small("News unavailable", className="text-muted"),
                className="text-center py-3",
            )

    # News filter button active state callback
    @app.callback(
        [
            Output("news-filter-all", "active"),
            Output("news-filter-fed", "active"),
            Output("news-filter-ecb", "active"),
            Output("news-filter-boj", "active"),
        ],
        [
            Input("news-filter-all", "n_clicks"),
            Input("news-filter-fed", "n_clicks"),
            Input("news-filter-ecb", "n_clicks"),
            Input("news-filter-boj", "n_clicks"),
        ],
        prevent_initial_call=False,
    )
    def update_news_filter_active(
        all_clicks: int,  # noqa: ARG001
        fed_clicks: int,  # noqa: ARG001
        ecb_clicks: int,  # noqa: ARG001
        boj_clicks: int,  # noqa: ARG001
    ) -> tuple[bool, bool, bool, bool]:
        """Update active state of filter buttons.

        Returns:
            Tuple of active states for (All, Fed, ECB, BoJ) buttons.
        """
        ctx = callback_context

        # Default: All is active
        if not ctx.triggered:
            return (True, False, False, False)

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Map trigger IDs to button active states (All, Fed, ECB, BoJ)
        button_states = {
            "news-filter-fed": (False, True, False, False),
            "news-filter-ecb": (False, False, True, False),
            "news-filter-boj": (False, False, False, True),
        }
        return button_states.get(trigger_id, (True, False, False, False))

    # ==========================================================================
    # FOMC Statement Diff Callbacks (Plan 14-08)
    # ==========================================================================

    # Load available FOMC statement dates on startup
    @app.callback(
        [
            Output("fomc-date-1", "options"),
            Output("fomc-date-2", "options"),
            Output("fomc-dates-store", "data"),
            Output("fomc-date-1", "value"),
            Output("fomc-date-2", "value"),
        ],
        Input("refresh-interval", "n_intervals"),
        [
            State("fomc-date-1", "value"),
            State("fomc-date-2", "value"),
        ],
        prevent_initial_call=False,
    )
    def load_fomc_dates(
        n_intervals: int,  # noqa: ARG001
        current_date1_value: str | None,
        current_date2_value: str | None,
    ) -> tuple:
        """Load available FOMC statement dates.

        Triggered on startup and by refresh interval.

        Returns:
            Tuple of (date1_options, date2_options, dates_store, date1_value, date2_value).
        """
        try:
            dates = _fetch_fomc_statement_dates()
            if not dates:
                logger.warning("No FOMC statement dates available in cache; using fallback dates")
                dates = _build_mock_fomc_dates()

            options = get_available_dates_options(dates)

            # Store dates as ISO strings
            dates_store = [d.isoformat() for d in dates]

            if not options:
                return [], [], [], None, None

            valid_values = {opt["value"] for opt in options}
            default_current_value = options[0]["value"]
            default_previous_value = options[1]["value"] if len(options) > 1 else options[0]["value"]

            # Preserve user selection if still available after refresh.
            current_value = (
                current_date2_value
                if current_date2_value in valid_values
                else default_current_value
            )
            previous_value = (
                current_date1_value
                if current_date1_value in valid_values
                else default_previous_value
            )

            return options, options, dates_store, previous_value, current_value

        except Exception as e:
            logger.error("Failed to load FOMC dates: %s", e)
            return [], [], [], None, None

    # FOMC diff comparison callback
    @app.callback(
        [
            Output("fomc-change-summary", "children"),
            Output("fomc-diff-view", "children"),
        ],
        Input("fomc-compare-btn", "n_clicks"),
        [
            State("fomc-date-1", "value"),
            State("fomc-date-2", "value"),
        ],
        prevent_initial_call=True,
    )
    def compare_fomc_statements(
        n_clicks: int | None,
        date1_value: str | None,
        date2_value: str | None,
    ) -> tuple:
        """Compare two FOMC statements and display diff.

        Args:
            n_clicks: Number of compare button clicks.
            date1_value: First date ISO string.
            date2_value: Second date ISO string.

        Returns:
            Tuple of (change_summary, diff_view) components.
        """
        from dash import html

        if not n_clicks:
            return (
                html.Div(),
                create_empty_diff_view(),
            )

        # Parse dates
        date1 = parse_date_value(date1_value)
        date2 = parse_date_value(date2_value)

        if not date1 or not date2:
            return (
                html.Div("Please select both dates", className="text-warning"),
                create_empty_diff_view("Select two statement dates to compare"),
            )

        if date1 == date2:
            return (
                html.Div("Please select different dates", className="text-warning"),
                create_empty_diff_view("Select two different statement dates"),
            )

        try:
            # Fetch statements and compute diff
            diff = _fetch_and_diff_statements(date1, date2)

            if diff is None:
                logger.warning("FOMC statement fetch failed; falling back to mock diff output")
                diff = _build_mock_fomc_diff(date1, date2)

            # Create summary and diff view
            change_summary = create_change_summary(diff.change_score, diff.phrase_shifts)
            diff_view = create_diff_view(diff)

            return change_summary, diff_view

        except Exception as e:
            logger.error("FOMC diff comparison failed: %s", e)
            return (
                html.Div(f"Error: {e}", className="text-danger"),
                create_error_diff_view(str(e)),
            )

    # Register EIA panel callbacks (Phase 16)
    from liquidity.dashboard.callbacks.eia_callbacks import register_eia_callbacks
    register_eia_callbacks(app)

    # Register Inflation panel callbacks (Phase 19)
    from liquidity.dashboard.callbacks.inflation_callbacks import register_inflation_callbacks
    register_inflation_callbacks(app)


def _build_mock_fomc_dates() -> list[date]:
    """Return deterministic FOMC dates for fallback mode."""
    return [
        date(2024, 12, 18),
        date(2025, 1, 29),
    ]


def _build_mock_fomc_diff(old_date: date, new_date: date) -> Any:
    """Return a deterministic mock FOMC diff for fallback mode."""
    from liquidity.news.fomc.diff import ChangeScore, PhraseShift, StatementDiff

    return StatementDiff(
        old_date=old_date,
        new_date=new_date,
        operations=[],
        additions=[
            "remains attentive to liquidity conditions",
            "policy will stay sufficiently restrictive",
        ],
        deletions=[
            "risks to inflation have eased materially",
        ],
        unchanged_ratio=0.72,
        change_score=ChangeScore(
            direction="hawkish",
            magnitude=0.35,
            key_changes=["+attentive", "+restrictive", "-eased"],
        ),
        phrase_shifts=[
            PhraseShift(phrase="attentive to liquidity conditions", change="added", policy_signal="hawkish"),
            PhraseShift(phrase="risks to inflation have eased materially", change="removed", policy_signal="dovish"),
        ],
        html=(
            "<html><body style='background:#1a1a2e;color:#eee;font-family:sans-serif;padding:12px;'>"
            "<h4 style='margin:0 0 8px;'>Mock FOMC Statement Diff</h4>"
            "<p>The Committee judges that liquidity conditions remain "
            "<span style='color:#ff4444;font-weight:bold'>attentive</span> and policy "
            "must remain <span style='color:#ff4444;font-weight:bold'>sufficiently restrictive</span>.</p>"
            "<p style='color:#adb5bd;'>Generated in fallback mode for deterministic dashboard validation.</p>"
            "</body></html>"
        ),
    )


def _build_mock_news_items() -> list[dict[str, Any]]:
    """Return deterministic news items for fallback mode."""
    now = _dashboard_now()
    return [
        {
            "title": "Fed officials say liquidity conditions remain supportive for risk assets",
            "source": "Fed",
            "sentiment": "dovish",
            "published": now - timedelta(minutes=45),
            "link": "https://example.com/fed-liquidity",
        },
        {
            "title": "ECB signals a gradual pace for balance-sheet normalization",
            "source": "ECB",
            "sentiment": "neutral",
            "published": now - timedelta(hours=3),
            "link": "https://example.com/ecb-balance-sheet",
        },
        {
            "title": "BoJ monitors funding-market pressure and imported inflation risk",
            "source": "BoJ",
            "sentiment": "hawkish",
            "published": now - timedelta(hours=6),
            "link": "https://example.com/boj-funding",
        },
    ]


def _fetch_fomc_statement_dates() -> list[date]:
    """Fetch available FOMC statement dates.

    Returns:
        List of dates for which statements are available.
    """
    if _env_flag("LIQUIDITY_DASHBOARD_FORCE_FALLBACK"):
        return _build_mock_fomc_dates()

    try:
        import importlib.util

        if importlib.util.find_spec("liquidity.news.fomc"):
            from liquidity.news.fomc import FOMCStatementScraper

            # Get cached dates from scraper
            scraper = FOMCStatementScraper()
            cached_dates = scraper.list_cached()

            if cached_dates:
                return cached_dates

    except ImportError as e:
        logger.warning("Could not import FOMC scraper: %s", e)

    return []


def _fetch_and_diff_statements(old_date: date, new_date: date) -> Any:
    """Fetch two FOMC statements and compute diff.

    Args:
        old_date: Date of older statement.
        new_date: Date of newer statement.

    Returns:
        StatementDiff object or None if fetch fails.
    """
    if _env_flag("LIQUIDITY_DASHBOARD_FORCE_FALLBACK"):
        return _build_mock_fomc_diff(old_date, new_date)

    try:
        import importlib.util

        if importlib.util.find_spec("liquidity.news.fomc"):
            from liquidity.news.fomc import FOMCStatementScraper, StatementDiffEngine

            # Try to fetch from scraper (sync wrapper)
            try:
                scraper = FOMCStatementScraper()

                # Load from cache if available
                old_statement = scraper._load_from_cache(old_date)
                new_statement = scraper._load_from_cache(new_date)

                if old_statement and new_statement:
                    engine = StatementDiffEngine()
                    return engine.diff(
                        old_text=old_statement.raw_text,
                        new_text=new_statement.raw_text,
                        old_date=old_date,
                        new_date=new_date,
                    )

            except Exception as e:
                logger.warning("Failed to fetch statements from scraper: %s", e)

    except ImportError as e:
        logger.warning("Could not import FOMC modules: %s", e)

    return None


def _fetch_news_data() -> list[dict]:
    """Fetch news data from the news module.

    Returns:
        List of news item dictionaries.
    """
    if _env_flag("LIQUIDITY_DASHBOARD_FORCE_FALLBACK"):
        return _build_mock_news_items()

    try:
        import importlib.util

        if importlib.util.find_spec("liquidity.news"):
            from liquidity.news import poll_feeds_once

            items = asyncio.run(poll_feeds_once())
            return [
                {
                    "title": item.title,
                    "source": item.source.value,
                    "sentiment": "neutral",
                    "published": item.published,
                    "link": str(item.link),
                }
                for item in items[:12]
            ]

    except Exception as e:
        logger.warning("Could not load news feeds: %s", e)

    return []


def _fetch_quality_data() -> dict[str, Any]:
    """Fetch quality validation data.

    Returns:
        Dictionary with quality metrics and reports.
    """
    try:
        import importlib.util

        if not importlib.util.find_spec("liquidity.validation"):
            raise ImportError("Validation module not available")

        from liquidity.validation import ValidationEngine

        engine = ValidationEngine()

        # Get real last updates from dashboard data store
        # For now use empty dict — real freshness comes from collectors
        last_updates: dict[str, datetime] = {}
        data: dict[str, pd.DataFrame] = {}

        report = engine.validate_all(data, last_updates)

        freshness_results = engine.freshness.check_all(last_updates)
        freshness_status = {
            source: result.status
            for source, result in freshness_results.items()
        }

        return {
            "quality_report": report,
            "freshness_score": report.freshness_score,
            "completeness_score": report.completeness_score,
            "validation_score": report.validation_score,
            "last_updates": last_updates,
            "freshness_status": freshness_status,
        }

    except (ImportError, Exception) as e:
        logger.error("Quality data unavailable: %s", e)
        return {
            "quality_report": None,
            "freshness_score": 0.0,
            "completeness_score": 0.0,
            "validation_score": 0.0,
            "last_updates": {},
            "freshness_status": {},
            "error": str(e),
        }



def _get_quality_error_response() -> tuple:
    """Get error response for quality indicators callback.

    Returns:
        Tuple with empty/default values for quality outputs.
    """
    from dash import html

    empty_gauge = create_quality_gauge(0, "N/A")

    return (
        html.Div("Quality data unavailable", className="text-warning"),
        empty_gauge,
        empty_gauge,
        empty_gauge,
        html.Div("No data", className="text-muted"),
    )


def _fetch_dashboard_data() -> dict[str, Any]:
    """Fetch all data needed for main dashboard from calculators.

    Returns:
        Dictionary with main dashboard data.
    """
    if _env_flag("LIQUIDITY_DASHBOARD_FORCE_FALLBACK"):
        logger.info("Dashboard fallback mode forced by environment")
        return _build_mock_dashboard_data(reason="Forced fallback mode")

    # Try to import calculators to check availability
    try:
        import importlib.util

        if not all(
            importlib.util.find_spec(mod)
            for mod in [
                "liquidity.analyzers.regime_classifier",
                "liquidity.calculators.global_liquidity",
                "liquidity.calculators.net_liquidity",
            ]
        ):
            raise ImportError("Calculator modules not available")
    except ImportError as e:
        logger.error("Could not import calculators: %s", e)
        return _build_mock_dashboard_data(reason=f"Import error: {e}")

    try:
        return asyncio.run(_fetch_data_async())
    except Exception as e:
        logger.warning("Falling back to mock dashboard data: %s", e)
        return _build_mock_dashboard_data(reason=str(e))


def _build_mock_dashboard_data(reason: str | None = None) -> dict[str, Any]:
    """Build resilient fallback data for dashboard rendering.

    This prevents empty/error panels when credentials or upstream data are unavailable.
    """
    dates = pd.date_range(end=_dashboard_now(), periods=180, freq="D")
    idx = list(range(len(dates)))

    net_values = pd.Series(
        [5800.0 + (i * 0.6) + 110.0 * math.sin(i / 16.0) for i in idx],
        index=dates,
    )
    walcl_values = pd.Series(
        [9000.0 + (i * 0.2) for i in idx],
        index=dates,
    )
    tga_values = pd.Series(
        [650.0 + 45.0 * (1 + math.sin(i / 14.0)) for i in idx],
        index=dates,
    )
    rrp_values = pd.Series(
        [280.0 + 50.0 * (1 + math.cos(i / 18.0)) for i in idx],
        index=dates,
    )

    global_values = pd.Series(
        [28000.0 + (i * 1.2) + 180.0 * math.sin(i / 20.0) for i in idx],
        index=dates,
    )
    fed_values = global_values * 0.30
    ecb_values = global_values * 0.28
    boj_values = global_values * 0.25
    pboc_values = global_values * 0.17

    net_df = pd.DataFrame(
        {
            "timestamp": dates,
            "net_liquidity": net_values.values,
            "walcl": walcl_values.values,
            "tga": tga_values.values,
            "rrp": rrp_values.values,
        }
    )
    global_df = pd.DataFrame(
        {
            "timestamp": dates,
            "global_liquidity": global_values.values,
            "fed_usd": fed_values.values,
            "ecb_usd": ecb_values.values,
            "boj_usd": boj_values.values,
            "pboc_usd": pboc_values.values,
        }
    )

    def _delta(series: pd.Series, periods: int) -> float:
        if len(series) <= periods:
            return 0.0
        return float(series.iloc[-1] - series.iloc[-(periods + 1)])

    weekly_delta = _delta(net_values, 7)
    monthly_delta = _delta(net_values, 30)
    net_direction = "EXPANSION" if weekly_delta >= 0 else "CONTRACTION"

    return {
        "net_liquidity_df": net_df,
        "global_liquidity_df": global_df,
        "regime": {
            "direction": net_direction,
            "intensity": min(100.0, max(0.0, abs(weekly_delta) / 4.0)),
            "confidence": "LOW" if reason else "MEDIUM",
            "net_liq_percentile": 0.5,
            "global_liq_percentile": 0.5,
            "stealth_qe_score": 0.5,
        },
        "net_metrics": {
            "current": float(net_values.iloc[-1]),
            "weekly_delta": weekly_delta,
            "monthly_delta": monthly_delta,
            "delta_60d": _delta(net_values, 60),
            "delta_90d": _delta(net_values, 90),
        },
        "global_metrics": {
            "current": float(global_values.iloc[-1]),
            "weekly_delta": _delta(global_values, 7),
            "monthly_delta": _delta(global_values, 30),
            "delta_60d": _delta(global_values, 60),
            "delta_90d": _delta(global_values, 90),
        },
        "quality_score": 70 if not reason else 55,
        "calendar_events": [],
        "fallback_reason": reason or "",
    }


async def _fetch_data_async() -> dict[str, Any]:
    """Async function to fetch all calculator data.

    Returns:
        Dictionary with real data from calculators.
    """
    from liquidity.analyzers.regime_classifier import RegimeClassifier
    from liquidity.calculators.global_liquidity import GlobalLiquidityCalculator
    from liquidity.calculators.net_liquidity import NetLiquidityCalculator
    from liquidity.config import configure_openbb_credentials

    if _env_flag("LIQUIDITY_DASHBOARD_FORCE_FALLBACK"):
        logger.info("Dashboard fallback mode forced by environment")
        return _build_mock_dashboard_data(reason="Forced fallback mode")

    # Configure OpenBB credentials before using calculators
    if not configure_openbb_credentials():
        logger.warning("OpenBB credentials not configured, using fallback dashboard data")
        return _build_mock_dashboard_data(reason="OpenBB credentials not configured")

    try:
        # Initialize calculators
        net_calc = NetLiquidityCalculator()
        global_calc = GlobalLiquidityCalculator()
        regime_classifier = RegimeClassifier()

        # Fetch data
        net_df = await net_calc.calculate()
        global_df = await global_calc.calculate()

        # Get current values
        net_result = await net_calc.get_current()
        global_result = await global_calc.get_current()
        regime_result = await regime_classifier.classify()

        return {
            "net_liquidity_df": net_df,
            "global_liquidity_df": global_df,
            "regime": {
                "direction": regime_result.direction.value,
                "intensity": regime_result.intensity,
                "confidence": regime_result.confidence,
                "net_liq_percentile": regime_result.net_liq_percentile,
                "global_liq_percentile": regime_result.global_liq_percentile,
                "stealth_qe_score": regime_result.stealth_qe_score,
            },
            "net_metrics": {
                "current": net_result.net_liquidity,
                "weekly_delta": net_result.weekly_delta,
                "monthly_delta": net_result.monthly_delta,
                "delta_60d": net_result.delta_60d,
                "delta_90d": net_result.delta_90d,
            },
            "global_metrics": {
                "current": global_result.total_usd,
                "weekly_delta": global_result.weekly_delta,
                "monthly_delta": global_result.delta_30d,
                "delta_60d": global_result.delta_60d,
                "delta_90d": global_result.delta_90d,
            },
            "quality_score": 100,
            "calendar_events": [],
        }
    except Exception as e:
        logger.warning("Primary dashboard fetch failed, using fallback data: %s", e)
        return _build_mock_dashboard_data(reason=str(e))


def _fetch_extended_data() -> dict[str, Any]:
    """Fetch data for extended panels.

    Returns:
        Dictionary with extended panel data.
    """
    return asyncio.run(_fetch_extended_async())


def _build_mock_extended_data() -> dict[str, Any]:
    """Build deterministic fallback data for extended dashboard panels."""
    dates = pd.date_range(end=_dashboard_now(), periods=90, freq="D")
    idx = list(range(len(dates)))

    xlp_xly_ratio = pd.Series(
        [0.98 + 0.02 * math.sin(i / 10.0) + (i * 0.0004) for i in idx],
        index=dates,
    )
    axp_rebased = pd.Series(
        [100.0 + (i * 0.12) + 1.5 * math.sin(i / 8.0) for i in idx],
        index=dates,
    )
    igv_rebased = pd.Series(
        [100.0 + (i * 0.18) + 2.0 * math.cos(i / 9.0) for i in idx],
        index=dates,
    )
    relative_spread = axp_rebased - igv_rebased

    xlp_xly_df = pd.DataFrame(
        {
            "timestamp": dates,
            "xlp_xly_ratio": xlp_xly_ratio.values,
        }
    )
    axp_igv_df = pd.DataFrame(
        {
            "timestamp": dates,
            "axp_rebased": axp_rebased.values,
            "igv_rebased": igv_rebased.values,
            "relative_spread_pct": relative_spread.values,
        }
    )

    consumer_credit_metrics = {
        "consumer_credit_total_b": 5200.0,
        "student_loans_b": 1780.0,
        "consumer_credit_ex_students_b": 3420.0,
        "debt_in_default_est_b": 145.0,
        "debt_default_rate_pct": 3.8,
        "mortgage_chargeoff_rate_pct": 0.7,
        "loan_loss_reserves_b": 128.0,
        "usd_liquidity_index": 58.4,
    }

    sensitive_stocks_df = pd.DataFrame(
        {
            "symbol": ["AXP", "COF", "DFS", "ALLY"],
            "corr_to_stress": [0.72, 0.68, 0.61, 0.58],
            "beta_to_stress": [1.20, 1.11, 0.97, 0.94],
            "sensitivity_score": [0.88, 0.81, 0.74, 0.69],
        }
    )

    return {
        "xlp_xly_df": xlp_xly_df,
        "axp_igv_df": axp_igv_df,
        "consumer_credit_metrics": consumer_credit_metrics,
        "sensitive_stocks_df": sensitive_stocks_df,
        "calendar_events": [],
    }


async def _fetch_extended_async() -> dict[str, Any]:
    """Async function to fetch extended panel data.

    Returns:
        Dictionary with real data from collectors.
    """
    import importlib.util

    if _env_flag("LIQUIDITY_DASHBOARD_FORCE_FALLBACK"):
        logger.info("Extended panel fallback mode forced by environment")
        return _build_mock_extended_data()

    data: dict[str, Any] = {}

    # Try FX collector
    if importlib.util.find_spec("liquidity.collectors.fx"):
        try:
            from liquidity.collectors.fx import FXCollector

            fx_collector = FXCollector()
            dxy_df = await fx_collector.collect_dxy(period="30d")
            fx_df = await fx_collector.collect_pairs(period="5d")

            data["dxy_df"] = dxy_df
            data["fx"] = {
                "eurusd": _get_latest_value(fx_df, "EURUSD=X"),
                "usdjpy": _get_latest_value(fx_df, "USDJPY=X"),
                "usdcny": _get_latest_value(fx_df, "USDCNY=X"),
            }
        except Exception as e:
            logger.warning("FX collector failed: %s", e)

    # Try Commodity collector
    if importlib.util.find_spec("liquidity.collectors.commodities"):
        try:
            from liquidity.collectors.commodities import CommodityCollector

            commodity_collector = CommodityCollector()
            commodity_df = await commodity_collector.collect_all(period="30d")

            data["gold_df"] = commodity_df[commodity_df["series_id"] == "GC=F"]
            data["copper_df"] = commodity_df[commodity_df["series_id"] == "HG=F"]
            data["wti_df"] = commodity_df[commodity_df["series_id"] == "CL=F"]
            data["brent_df"] = commodity_df[commodity_df["series_id"] == "BZ=F"]
            data["commodities"] = {
                "gold": _get_latest_value(commodity_df, "GC=F"),
                "copper": _get_latest_value(commodity_df, "HG=F"),
                "wti": _get_latest_value(commodity_df, "CL=F"),
            }
        except Exception as e:
            logger.warning("Commodity collector failed: %s", e)

    # Try Stress collector
    if importlib.util.find_spec("liquidity.collectors.stress"):
        try:
            from liquidity.collectors.stress import StressIndicatorCollector

            stress_collector = StressIndicatorCollector()
            stress_df = await stress_collector.collect_all()

            data["stress"] = {
                "sofr_ois": _get_latest_value(stress_df, "stress_sofr_ois"),
                "repo_stress": _get_latest_value(stress_df, "stress_repo"),
            }
        except Exception as e:
            logger.warning("Stress collector failed: %s", e)

    # Try TIC collector
    if importlib.util.find_spec("liquidity.collectors.tic"):
        try:
            from liquidity.collectors.tic import TICCollector

            tic_collector = TICCollector()
            tic_df = await tic_collector.collect_major_holders()
            data["tic_df"] = tic_df
        except Exception as e:
            logger.warning("TIC collector failed: %s", e)

    # Try ETF flows collector
    if importlib.util.find_spec("liquidity.collectors.etf_flows"):
        try:
            from liquidity.collectors.etf_flows import ETFFlowCollector

            etf_collector = ETFFlowCollector()
            etf_df = await etf_collector.collect_all(period="30d")
            data["etf_df"] = etf_df
        except Exception as e:
            logger.warning("ETF collector failed: %s", e)

    # Try Correlation engine
    if importlib.util.find_spec("liquidity.analyzers.correlation_engine"):
        try:
            from liquidity.analyzers.correlation_engine import CorrelationEngine

            engine = CorrelationEngine()
            prices = await engine._fetch_asset_prices()
            if not prices.empty:
                returns = engine._calculate_returns(prices)
                matrix = engine.calculate_correlation_matrix(returns)
                data["correlation_matrix"] = matrix.correlations
        except Exception as e:
            logger.warning("Correlation engine failed: %s", e)

    # Try Consumer Credit Risk collector
    if importlib.util.find_spec("liquidity.collectors.consumer_credit_risk"):
        try:
            from liquidity.collectors.consumer_credit_risk import (
                DEFAULT_SENSITIVE_STOCKS,
                ConsumerCreditRiskCollector,
            )

            cc_collector = ConsumerCreditRiskCollector()
            start_date = datetime.now(UTC) - timedelta(days=365 * 5)

            credit_df = await cc_collector.collect_credit_risk(start_date=start_date)
            tracking_df = cc_collector.build_tracking_series(credit_df)

            market_symbols = list(
                dict.fromkeys(
                    cc_collector.MARKET_PAIR_SYMBOLS + DEFAULT_SENSITIVE_STOCKS
                )
            )
            market_df = await cc_collector.collect_market_prices(
                symbols=market_symbols,
                start_date=start_date,
                period="2y",
            )

            data["xlp_xly_df"] = cc_collector.calculate_xlp_xly_ratio(market_df)
            data["axp_igv_df"] = cc_collector.calculate_axp_igv_relative(market_df)
            data["consumer_credit_metrics"] = cc_collector.get_latest_tracking_metrics(
                tracking_df
            )
            data["sensitive_stocks_df"] = cc_collector.rank_credit_sensitive_stocks(
                market_df=market_df,
                tracking_df=tracking_df,
                symbols=DEFAULT_SENSITIVE_STOCKS,
            )
        except Exception as e:
            logger.warning("Consumer credit risk collector failed: %s", e)

    # Try Calendar registry
    if importlib.util.find_spec("liquidity.calendar.registry"):
        try:
            from liquidity.calendar.registry import CalendarRegistry

            registry = CalendarRegistry()
            events = registry.get_events(
                date.today(),
                date.today() + timedelta(days=30),
            )
            data["calendar_events"] = [
                {
                    "title": e.title,
                    "date": e.event_date.isoformat(),
                    "impact": e.impact.value,
                }
                for e in events[:10]
            ]
        except Exception as e:
            logger.warning("Calendar registry failed: %s", e)

    return data


def _get_latest_value(df: pd.DataFrame, series_id: str) -> float | None:
    """Get the latest value for a series from DataFrame.

    Args:
        df: DataFrame with series_id and value columns.
        series_id: Series identifier.

    Returns:
        Latest value or None.
    """
    if df is None or df.empty:
        return None

    series_df = df[df["series_id"] == series_id]
    if series_df.empty:
        return None

    if "timestamp" in series_df.columns:
        series_df = series_df.sort_values("timestamp")

    return float(series_df["value"].iloc[-1])


def _get_error_response(error_msg: str) -> tuple:
    """Get error response for main callback.

    Args:
        error_msg: Error message to display.

    Returns:
        Tuple with empty/error values for all outputs.
    """
    from dash import html

    empty_fig = create_net_liquidity_chart(None)

    return (
        empty_fig,  # net-liquidity-chart
        empty_fig,  # global-liquidity-chart
        html.Div(),  # net-liquidity-metrics
        html.Div(),  # global-liquidity-metrics
        html.Div(f"Error: {error_msg}", className="text-danger"),  # regime-indicator
        create_regime_gauge(0, "EXPANSION"),  # regime-gauge
        html.Div(),  # regime-metrics
        "Error",  # last-update-time
        "N/A",  # data-quality-score
        {},  # dashboard-data-store
    )


def _get_extended_error_response() -> tuple:
    """Get error response for extended panels callback.

    Returns:
        Tuple with empty/default values for extended panel outputs.
    """
    from dash import html

    empty_fig = create_dxy_chart(None)

    return (
        empty_fig,  # dxy-chart
        "--",  # eurusd-value
        "--",  # usdjpy-value
        "--",  # usdcny-value
        create_commodity_chart(None, "gold"),  # gold-chart
        create_commodity_chart(None, "copper"),  # copper-chart
        create_oil_chart(None, None),  # oil-chart
        html.Div(),  # commodity-summary
        create_sofr_ois_gauge(0),  # sofr-ois-gauge
        create_repo_stress_gauge(0),  # repo-stress-gauge
        create_stress_status("GREEN"),  # stress-status
        create_tic_chart(None),  # tic-flows-chart
        create_etf_flows_chart(None),  # etf-flows-chart
        create_correlation_heatmap(None),  # correlation-heatmap
        html.Div(),  # correlation-alerts
        create_xlp_xly_ratio_chart(None),  # xlp-xly-ratio-chart
        create_axp_igv_spread_chart(None),  # axp-igv-spread-chart
        html.Div(),  # consumer-credit-metrics
        html.Div(),  # consumer-credit-sensitive-stocks
        [],  # calendar-events
    )
