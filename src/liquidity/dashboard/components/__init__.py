"""Dashboard components for Global Liquidity Monitor.

This package contains individual UI components:
- header: Navigation header with title, refresh, export buttons
- liquidity: Net Liquidity and Global Liquidity chart panels
- regime: Regime classification panel with color coding
- fx: FX markets panel (DXY, major pairs)
- commodities: Commodities panel (Gold, Copper, Oil)
- stress: Funding stress indicators panel
- flows: Capital flows panel (TIC, ETF flows)
- correlations: Correlation heatmap panel
- calendar: Calendar events strip and overlay
- quality: Data quality indicators (QA-08, QA-09)
- bounds: Sanity bounds for charts (QA-10)
- news: Central bank news panel (Phase 14)
- fomc_diff: FOMC statement diff panel (Plan 14-08)
- eia_panel: EIA Weekly Petroleum panel (Phase 16)
- inflation: Inflation expectations panel (Phase 19)
"""

from liquidity.dashboard.components.bounds import (
    BoundInfo,
    BoundStatus,
    SanityBounds,
)
from liquidity.dashboard.components.calendar import (
    add_calendar_overlay,
    create_calendar_events,
    create_calendar_strip,
)
from liquidity.dashboard.components.commodities import (
    create_commodities_panel,
    create_commodity_chart,
    create_commodity_summary,
    create_oil_chart,
)
from liquidity.dashboard.components.correlations import (
    create_correlation_alerts,
    create_correlation_heatmap,
    create_correlation_panel,
)
from liquidity.dashboard.components.flows import (
    create_etf_flows_chart,
    create_flows_panel,
    create_flows_summary,
    create_tic_chart,
)
from liquidity.dashboard.components.fomc_diff import (
    create_change_summary,
    create_diff_view,
    create_empty_diff_view,
    create_error_diff_view,
    create_fomc_diff_panel,
    create_loading_diff_view,
    format_date_option,
    get_available_dates_options,
    parse_date_value,
)
from liquidity.dashboard.components.fx import (
    create_dxy_chart,
    create_fx_metrics,
    create_fx_panel,
)
from liquidity.dashboard.components.header import create_header, create_status_bar
from liquidity.dashboard.components.liquidity import (
    create_global_liquidity_chart,
    create_liquidity_metrics,
    create_liquidity_panel,
    create_net_liquidity_chart,
)
from liquidity.dashboard.components.news import (
    create_news_item,
    create_news_items_list,
    create_news_panel,
    format_time_ago,
    get_mock_news_items,
    news_items_from_newsitem_objects,
)
from liquidity.dashboard.components.quality import (
    create_freshness_indicators,
    create_quality_detail_panel,
    create_quality_gauge,
    create_quality_status_bar,
    create_quality_summary_card,
    create_source_freshness_table,
    format_relative_time,
    get_quality_status_for_export,
)
from liquidity.dashboard.components.regime import (
    create_regime_gauge,
    create_regime_indicator,
    create_regime_metrics,
    create_regime_panel,
)
from liquidity.dashboard.components.stress import (
    create_repo_stress_gauge,
    create_sofr_ois_gauge,
    create_stress_gauge,
    create_stress_panel,
    create_stress_status,
    get_overall_regime,
)
from liquidity.dashboard.components.eia_panel import (
    create_cushing_chart,
    create_cushing_utilization_badge,
    create_eia_panel,
    create_refinery_chart,
    create_refinery_signal_badge,
    create_supply_chart,
)
from liquidity.dashboard.components.positioning import (
    COT_COMMODITIES,
    create_extremes_table,
    create_positioning_heatmap,
    create_positioning_panel,
    create_positioning_timeseries,
)
from liquidity.dashboard.components.oil_term_structure import (
    create_curve_gauge,
    create_oil_term_structure_panel,
    create_price_chart,
    create_roll_yield_bars,
)
from liquidity.dashboard.components.inflation import (
    create_breakeven_chart,
    create_inflation_panel,
    create_inflation_summary,
    create_oil_rates_scatter,
    create_real_rates_chart,
)

__all__ = [
    # Header
    "create_header",
    "create_status_bar",
    # Liquidity
    "create_liquidity_panel",
    "create_net_liquidity_chart",
    "create_global_liquidity_chart",
    "create_liquidity_metrics",
    # Regime
    "create_regime_panel",
    "create_regime_indicator",
    "create_regime_gauge",
    "create_regime_metrics",
    # FX
    "create_fx_panel",
    "create_dxy_chart",
    "create_fx_metrics",
    # Commodities
    "create_commodities_panel",
    "create_commodity_chart",
    "create_oil_chart",
    "create_commodity_summary",
    # Stress
    "create_stress_panel",
    "create_stress_gauge",
    "create_sofr_ois_gauge",
    "create_repo_stress_gauge",
    "create_stress_status",
    "get_overall_regime",
    # Flows
    "create_flows_panel",
    "create_tic_chart",
    "create_etf_flows_chart",
    "create_flows_summary",
    # Correlations
    "create_correlation_panel",
    "create_correlation_heatmap",
    "create_correlation_alerts",
    # Calendar
    "create_calendar_strip",
    "create_calendar_events",
    "add_calendar_overlay",
    # Quality (QA-08, QA-09)
    "create_quality_status_bar",
    "create_freshness_indicators",
    "create_quality_detail_panel",
    "create_quality_gauge",
    "create_source_freshness_table",
    "create_quality_summary_card",
    "format_relative_time",
    "get_quality_status_for_export",
    # Bounds (QA-10)
    "SanityBounds",
    "BoundInfo",
    "BoundStatus",
    # News (Phase 14)
    "create_news_panel",
    "create_news_item",
    "create_news_items_list",
    "format_time_ago",
    "get_mock_news_items",
    "news_items_from_newsitem_objects",
    # FOMC Diff (Plan 14-08)
    "create_fomc_diff_panel",
    "create_change_summary",
    "create_diff_view",
    "create_empty_diff_view",
    "create_loading_diff_view",
    "create_error_diff_view",
    "format_date_option",
    "get_available_dates_options",
    "parse_date_value",
    # EIA Panel (Phase 16)
    "create_eia_panel",
    "create_cushing_chart",
    "create_refinery_chart",
    "create_supply_chart",
    "create_cushing_utilization_badge",
    "create_refinery_signal_badge",
    # Positioning Panel (Phase 17)
    "create_positioning_panel",
    "create_positioning_heatmap",
    "create_positioning_timeseries",
    "create_extremes_table",
    "COT_COMMODITIES",
    # Oil Term Structure Panel (Phase 18)
    "create_oil_term_structure_panel",
    "create_curve_gauge",
    "create_price_chart",
    "create_roll_yield_bars",
    # Inflation Panel (Phase 19)
    "create_inflation_panel",
    "create_real_rates_chart",
    "create_breakeven_chart",
    "create_oil_rates_scatter",
    "create_inflation_summary",
]
