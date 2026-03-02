# Dashboard Panel Health Plan

## Scope

This plan covers the dashboard panels currently reported as visually broken or degraded:

- Central Bank News (CB Communications)
- FOMC Statement Comparison
- EIA Weekly Petroleum (Oil Market)
- Inflation Expectations (TIPS & Breakeven)
- Consumer Credit Risk
- Liquidity Regime

The goal is to make panel failures observable, diagnosable, and testable across three layers:

1. browser-visible behavior
2. scriptable data/fetch health
3. callback/data-quality contracts

## Health Contract

Each panel should expose one of three effective states:

- `ok`: real data loaded, figures/metrics populated, panel interactive
- `degraded`: fallback content is explicitly shown, no hidden exception
- `broken`: callback exception, empty shell, stuck loading state, or silent empty figure

Silent degradation is not acceptable. If a panel falls back, the UI and tests must be able to detect that state directly.

## Validation Layers

### 1. Browser E2E

Playwright should validate semantic panel health, not only container visibility.

Required browser checks:

- container renders
- loading state clears
- expected controls exist (buttons, tabs, dropdowns)
- user interaction changes visible state
- panel content is non-empty or explicitly marked `degraded`

Recommended test file:

- `tests/e2e_ui/dashboard.panel-health.e2e.spec.js`

### 2. Script Probe

Add a probe script that can be run locally or in CI to inspect panel fetchers/callback helpers without opening the browser.

Recommended script:

- `scripts/dashboard_panel_probe.py`

Recommended JSON output per panel:

- `panel`
- `status`
- `rows`
- `latest_timestamp`
- `trace_count`
- `placeholder_text`
- `error`

### 3. Data Quality Checks

Each panel should validate its own minimum viable dataset before rendering.

Minimum checks:

- required columns present
- `rows > 0` for live mode
- latest timestamp not stale
- figure has at least one trace in live mode
- fallback path emits explicit degraded marker

## Panel-Specific Assertions

### Central Bank News

- `#news-items-container` must not remain in `Loading news...`
- Live mode: at least one `.news-item`
- Fallback mode: explicit empty/degraded message is acceptable
- News filter clicks must change visible content, not just keep the page alive

### FOMC Statement Comparison

- `#fomc-date-1` and `#fomc-date-2` should expose usable options
- `#fomc-compare-btn` must produce a non-empty summary
- `#fomc-diff-view` must render actual diff content, not an empty shell

### EIA Weekly Petroleum

- Key charts should render real traces in live mode:
  - `#cushing-inventory-chart`
  - `#refinery-utilization-chart`
  - `#crude-production-chart`
  - `#crude-imports-chart`
- KPI badges should not stay on placeholders like `--` in live mode
- If EIA data is unavailable, the panel should surface `degraded` instead of raising

### Inflation Expectations

- `#real-rates-chart`, `#breakeven-chart`, and `#oil-rates-scatter` should have traces
- `#inflation-summary` should be populated in live mode
- Missing TIPS/breakeven data should render an explicit degraded summary

### Consumer Credit Risk

- `#xlp-xly-ratio-chart` and `#axp-igv-spread-chart` should have traces
- `#consumer-credit-metrics` should contain non-placeholder values
- Sensitive-stocks table should contain rows or an explicit degraded state

### Liquidity Regime

- `#regime-indicator` should resolve to a semantic value (`EXPANSION` or `CONTRACTION`)
- `#regime-gauge` should render a numeric value
- `#regime-metrics` should contain the expected core rows
- Combined regime paths must degrade cleanly if EIA is unavailable

## Fix Workflow

1. Reproduce in live mode and fallback mode.
2. Run the probe script to identify whether failure is in data fetch, transformation, or rendering.
3. Fix the fetch/callback path first.
4. Add or update a focused unit/integration test for that callback/helper.
5. Add or update a browser assertion that detects the user-visible failure mode.
6. Re-run targeted pytest and Playwright suites.

## CI Gate

Minimum regression gate after fixes:

- targeted unit tests for affected callbacks/routes
- `npm run test:e2e`
- visual regression only when expected UI output changes

## Immediate Priority

Given the current failures observed in OpenBB Terminal Pro widget validation, prioritize:

1. combined regime fallback when EIA data is missing
2. workspace metric/chart endpoints returning degraded payloads instead of 500s
3. explicit degraded-state signaling for dashboard panels that currently render empty shells
