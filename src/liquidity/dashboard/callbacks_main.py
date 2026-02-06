"""Dashboard callbacks for interactivity.

Handles:
- Data refresh (manual and automatic)
- Chart updates for all panels
- Export functionality
"""

import asyncio
import logging
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
    get_mock_news_items,
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
                label="Current",
            )

            global_metrics = data.get("global_metrics", {})
            global_liq_metrics = create_liquidity_metrics(
                current_value=global_metrics.get("current", 0),
                weekly_delta=global_metrics.get("weekly_delta", 0),
                monthly_delta=global_metrics.get("monthly_delta", 0),
                label="Current",
            )

            # Update status
            last_update = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
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
            commodity_summary = create_commodity_summary(
                gold_price=data.get("commodities", {}).get("gold"),
                copper_price=data.get("commodities", {}).get("copper"),
                wti_price=data.get("commodities", {}).get("wti"),
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
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M")
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
                <p>Exported at: {datetime.now(UTC).isoformat()}</p>
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
        ],
        Input("refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def load_fomc_dates(n_intervals: int) -> tuple:  # noqa: ARG001
        """Load available FOMC statement dates.

        Triggered on startup and by refresh interval.

        Returns:
            Tuple of (date1_options, date2_options, dates_store).
        """
        try:
            dates = _fetch_fomc_statement_dates()
            options = get_available_dates_options(dates)

            # Store dates as ISO strings
            dates_store = [d.isoformat() for d in dates]

            return options, options, dates_store

        except Exception as e:
            logger.error("Failed to load FOMC dates: %s", e)
            return [], [], []

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
                return (
                    html.Div("Failed to load statements", className="text-danger"),
                    create_error_diff_view("Could not fetch FOMC statements"),
                )

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


def _fetch_fomc_statement_dates() -> list[date]:
    """Fetch available FOMC statement dates.

    Returns:
        List of dates for which statements are available.
    """
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

    # Return mock dates for demo
    return _get_mock_fomc_dates()


def _get_mock_fomc_dates() -> list[date]:
    """Get mock FOMC statement dates for testing.

    Returns:
        List of sample FOMC meeting dates.
    """
    # Sample FOMC meeting dates (2024)
    return [
        date(2024, 12, 18),
        date(2024, 11, 7),
        date(2024, 9, 18),
        date(2024, 7, 31),
        date(2024, 6, 12),
        date(2024, 5, 1),
        date(2024, 3, 20),
        date(2024, 1, 31),
        date(2023, 12, 13),
        date(2023, 11, 1),
    ]


def _fetch_and_diff_statements(old_date: date, new_date: date) -> Any:
    """Fetch two FOMC statements and compute diff.

    Args:
        old_date: Date of older statement.
        new_date: Date of newer statement.

    Returns:
        StatementDiff object or None if fetch fails.
    """
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

    # Return mock diff for demo
    return _get_mock_fomc_diff(old_date, new_date)


def _get_mock_fomc_diff(old_date: date, new_date: date) -> Any:
    """Get mock FOMC statement diff for testing.

    Args:
        old_date: Date of older statement.
        new_date: Date of newer statement.

    Returns:
        StatementDiff with sample data.
    """
    from liquidity.news.fomc.diff import StatementDiffEngine

    # Sample FOMC statement excerpts
    old_text = """
    The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent
    over the longer run. The Committee judges that the risks to achieving its employment and
    inflation goals are moving into better balance. The economic outlook is uncertain, and the
    Committee remains highly attentive to inflation risks.

    In support of its goals, the Committee decided to maintain the target range for the federal
    funds rate at 5-1/4 to 5-1/2 percent. In considering any adjustments to the target range for
    the federal funds rate, the Committee will carefully assess incoming data, the evolving
    outlook, and the balance of risks.
    """

    new_text = """
    The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent
    over the longer run. The Committee judges that the risks to achieving its employment and
    inflation goals are moving into better balance. The economic outlook is uncertain, and the
    Committee remains attentive to inflation risks.

    In support of its goals, the Committee decided to maintain the target range for the federal
    funds rate at 5-1/4 to 5-1/2 percent. In considering any adjustments to the target range for
    the federal funds rate, the Committee will carefully assess incoming data, the evolving
    outlook, and the balance of risks. The Committee does not expect it will be appropriate to
    reduce the target range until it has gained greater confidence that inflation is moving
    sustainably toward 2 percent.
    """

    engine = StatementDiffEngine()
    return engine.diff(
        old_text=old_text,
        new_text=new_text,
        old_date=old_date,
        new_date=new_date,
    )


def _fetch_news_data() -> list[dict]:
    """Fetch news data from the news module.

    Returns:
        List of news item dictionaries.
    """
    try:
        import importlib.util

        if importlib.util.find_spec("liquidity.news"):
            # News module available - in production, data would be fetched
            # from a cache/database populated by a background NewsPoller task
            logger.debug("News module available, using mock data for now")

    except ImportError as e:
        logger.warning("Could not import news module: %s", e)

    # Return mock news data
    return get_mock_news_items()


def _fetch_quality_data() -> dict[str, Any]:
    """Fetch quality validation data.

    Returns:
        Dictionary with quality metrics and reports.
    """
    try:
        import importlib.util

        if importlib.util.find_spec("liquidity.validation"):
            from liquidity.validation import ValidationEngine

            # Try to get real data
            try:
                engine = ValidationEngine()

                # Get last updates from collectors (mock for now)
                last_updates = _get_mock_last_updates()

                # Create mock data for validation
                data = _get_mock_validation_data()

                # Run validation
                report = engine.validate_all(data, last_updates)

                # Get freshness status
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

            except Exception as e:
                logger.warning("Validation engine failed: %s, using mock data", e)

    except ImportError as e:
        logger.warning("Could not import validation module: %s", e)

    # Return mock quality data
    return _get_mock_quality_data()


def _get_mock_last_updates() -> dict[str, datetime]:
    """Get mock last update timestamps.

    Returns:
        Dictionary of source names to timestamps.
    """
    now = datetime.now(UTC)
    return {
        "fed_balance_sheet": now - timedelta(hours=12),
        "sofr": now - timedelta(hours=6),
        "tga": now - timedelta(hours=18),
        "rrp": now - timedelta(hours=4),
        "dxy": now - timedelta(hours=2),
        "ecb": now - timedelta(hours=36),
        "boj": now - timedelta(hours=48),
        "pboc": now - timedelta(hours=72),
    }


def _get_mock_validation_data() -> dict[str, pd.DataFrame]:
    """Get mock data for validation.

    Returns:
        Dictionary of source names to DataFrames.
    """
    import numpy as np

    dates = pd.date_range(end=datetime.now(UTC), periods=30, freq="D")

    return {
        "fed_balance_sheet": pd.DataFrame({
            "date": dates,
            "value": 7800 + np.random.randn(30) * 50,
        }),
        "sofr": pd.DataFrame({
            "date": dates,
            "value": 5.3 + np.random.randn(30) * 0.1,
        }),
        "tga": pd.DataFrame({
            "date": dates,
            "value": 800 + np.random.randn(30) * 30,
        }),
        "rrp": pd.DataFrame({
            "date": dates,
            "value": 500 + np.random.randn(30) * 20,
        }),
    }


def _get_mock_quality_data() -> dict[str, Any]:
    """Get mock quality data when validation module unavailable.

    Returns:
        Dictionary with mock quality metrics.
    """

    last_updates = _get_mock_last_updates()

    # Mock freshness status
    from liquidity.validation import FreshnessStatus

    freshness_status = {
        "fed_balance_sheet": FreshnessStatus.FRESH,
        "sofr": FreshnessStatus.FRESH,
        "tga": FreshnessStatus.FRESH,
        "rrp": FreshnessStatus.FRESH,
        "dxy": FreshnessStatus.FRESH,
        "ecb": FreshnessStatus.STALE,
        "boj": FreshnessStatus.STALE,
        "pboc": FreshnessStatus.CRITICAL,
    }

    return {
        "quality_report": None,
        "freshness_score": 85.0,
        "completeness_score": 92.0,
        "validation_score": 100.0,
        "last_updates": last_updates,
        "freshness_status": freshness_status,
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
        logger.warning("Could not import calculators: %s", e)
        return _get_mock_data()

    # Try async data fetch
    try:
        return asyncio.run(_fetch_data_async())
    except Exception as e:
        logger.warning("Async data fetch failed: %s, using mock data", e)
        return _get_mock_data()


async def _fetch_data_async() -> dict[str, Any]:
    """Async function to fetch all calculator data.

    Returns:
        Dictionary with real data from calculators.
    """
    from liquidity.analyzers.regime_classifier import RegimeClassifier
    from liquidity.calculators.global_liquidity import GlobalLiquidityCalculator
    from liquidity.calculators.net_liquidity import NetLiquidityCalculator

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
        },
        "global_metrics": {
            "current": global_result.total_usd,
            "weekly_delta": global_result.weekly_delta,
            "monthly_delta": global_result.delta_30d,
        },
        "quality_score": 100,
        "calendar_events": [],
    }


def _fetch_extended_data() -> dict[str, Any]:
    """Fetch data for extended panels.

    Returns:
        Dictionary with extended panel data.
    """
    # Try async fetch
    try:
        return asyncio.run(_fetch_extended_async())
    except Exception as e:
        logger.warning("Extended data fetch failed: %s, using mock data", e)
        return _get_mock_extended_data()


async def _fetch_extended_async() -> dict[str, Any]:
    """Async function to fetch extended panel data.

    Returns:
        Dictionary with real data from collectors.
    """
    import importlib.util

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

    return {**_get_mock_extended_data(), **data}


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


def _get_mock_data() -> dict[str, Any]:
    """Get mock data for testing/demo when calculators unavailable.

    Returns:
        Dictionary with sample data.
    """
    import numpy as np

    # Generate sample time series
    dates = pd.date_range(end=datetime.now(UTC), periods=90, freq="D")

    # Sample Net Liquidity data
    base_net = 5800
    net_values = base_net + np.cumsum(np.random.randn(90) * 20)

    net_df = pd.DataFrame(
        {
            "timestamp": dates,
            "net_liquidity": net_values,
            "walcl": net_values + 2000 + np.random.randn(90) * 10,
            "tga": 800 + np.random.randn(90) * 50,
            "rrp": 1400 + np.random.randn(90) * 30,
        }
    )

    # Sample Global Liquidity data
    base_global = 28000
    global_values = base_global + np.cumsum(np.random.randn(90) * 50)

    global_df = pd.DataFrame(
        {
            "timestamp": dates,
            "global_liquidity": global_values,
            "fed_usd": global_values * 0.3,
            "ecb_usd": global_values * 0.25,
            "boj_usd": global_values * 0.25,
            "pboc_usd": global_values * 0.2,
        }
    )

    return {
        "net_liquidity_df": net_df,
        "global_liquidity_df": global_df,
        "regime": {
            "direction": "EXPANSION",
            "intensity": 65,
            "confidence": "MEDIUM",
            "net_liq_percentile": 0.68,
            "global_liq_percentile": 0.72,
            "stealth_qe_score": 0.45,
        },
        "net_metrics": {
            "current": net_values[-1],
            "weekly_delta": net_values[-1] - net_values[-7],
            "monthly_delta": net_values[-1] - net_values[-30],
        },
        "global_metrics": {
            "current": global_values[-1],
            "weekly_delta": global_values[-1] - global_values[-7],
            "monthly_delta": global_values[-1] - global_values[-30],
        },
        "quality_score": 95,
        "calendar_events": [],
    }


def _get_mock_extended_data() -> dict[str, Any]:
    """Get mock data for extended panels.

    Returns:
        Dictionary with sample extended panel data.
    """
    import numpy as np

    dates = pd.date_range(end=datetime.now(UTC), periods=30, freq="D")

    # DXY data
    dxy_values = 103 + np.cumsum(np.random.randn(30) * 0.3)
    dxy_df = pd.DataFrame(
        {
            "timestamp": dates,
            "series_id": "DX-Y.NYB",
            "value": dxy_values,
            "source": "mock",
        }
    )

    # Commodity data
    gold_values = 2000 + np.cumsum(np.random.randn(30) * 10)
    copper_values = 4.2 + np.cumsum(np.random.randn(30) * 0.05)
    wti_values = 75 + np.cumsum(np.random.randn(30) * 1)
    brent_values = 80 + np.cumsum(np.random.randn(30) * 1)

    gold_df = pd.DataFrame(
        {"timestamp": dates, "series_id": "GC=F", "value": gold_values}
    )
    copper_df = pd.DataFrame(
        {"timestamp": dates, "series_id": "HG=F", "value": copper_values}
    )
    wti_df = pd.DataFrame({"timestamp": dates, "series_id": "CL=F", "value": wti_values})
    brent_df = pd.DataFrame(
        {"timestamp": dates, "series_id": "BZ=F", "value": brent_values}
    )

    # TIC data
    tic_df = pd.DataFrame(
        {
            "timestamp": [datetime.now(UTC)] * 5,
            "series_id": [
                "tic_japan_holdings",
                "tic_china_holdings",
                "tic_uk_holdings",
                "tic_cayman_holdings",
                "tic_luxembourg_holdings",
            ],
            "value": [1100, 850, 700, 350, 300],
            "source": "mock",
        }
    )

    # ETF data
    etf_dates = pd.date_range(end=datetime.now(UTC), periods=30, freq="D")
    etf_df = pd.DataFrame(
        {
            "timestamp": list(etf_dates) * 3,
            "etf": ["GLD"] * 30 + ["SLV"] * 30 + ["USO"] * 30,
            "close": list(180 + np.cumsum(np.random.randn(30) * 1))
            + list(22 + np.cumsum(np.random.randn(30) * 0.2))
            + list(70 + np.cumsum(np.random.randn(30) * 0.5)),
        }
    )

    # Correlation matrix (mock)
    assets = ["BTC", "SPX", "GOLD", "TLT", "DXY", "COPPER", "HYG"]
    corr_values = np.random.rand(7, 7)
    corr_values = (corr_values + corr_values.T) / 2
    np.fill_diagonal(corr_values, 1.0)
    corr_values = corr_values * 2 - 1  # Scale to [-1, 1]
    correlation_matrix = pd.DataFrame(
        corr_values, index=pd.Index(assets), columns=pd.Index(assets)
    )

    # Calendar events (mock)
    today = date.today()
    calendar_events = [
        {"title": "Treasury Auction", "date": (today + timedelta(days=3)).isoformat(), "impact": "high"},
        {"title": "FOMC Meeting", "date": (today + timedelta(days=7)).isoformat(), "impact": "high"},
        {"title": "ECB Meeting", "date": (today + timedelta(days=10)).isoformat(), "impact": "medium"},
        {"title": "BoJ Meeting", "date": (today + timedelta(days=14)).isoformat(), "impact": "medium"},
        {"title": "Tax Date", "date": (today + timedelta(days=20)).isoformat(), "impact": "low"},
    ]

    return {
        "dxy_df": dxy_df,
        "fx": {"eurusd": 1.0850, "usdjpy": 148.50, "usdcny": 7.15},
        "gold_df": gold_df,
        "copper_df": copper_df,
        "wti_df": wti_df,
        "brent_df": brent_df,
        "commodities": {"gold": gold_values[-1], "copper": copper_values[-1], "wti": wti_values[-1]},
        "stress": {"sofr_ois": 5.0, "repo_stress": 0.5},
        "tic_df": tic_df,
        "etf_df": etf_df,
        "correlation_matrix": correlation_matrix,
        "calendar_events": calendar_events,
    }


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
        [],  # calendar-events
    )
