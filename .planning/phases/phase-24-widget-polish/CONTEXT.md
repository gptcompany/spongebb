# Phase 24: Widget Polish & Optimization — Context

## Goal
Optimize widget metadata, refresh intervals, column formatting, and renderers for production UX in OpenBB Workspace.

## User Decisions

### WC-05: X-API-KEY Auth
**Decision: SKIP** — CF Access with Google OAuth (Phase 23) is sufficient. No additional API key middleware needed.

### columnDefs Strategy
**Decision: ALL 12 table endpoints** — Add explicit `columnDefs` to all table endpoints (including single-row scalar endpoints) for consistent field ordering, human-readable headers, and formatter attachment.

### formatterFn Strategy
**Decision: ALL numeric fields** — Add `formatterFn` to all numeric columns:
- USD values → currency/number format with "B USD" suffix
- Percentages → percent format
- Spreads → "bps" suffix
- Correlations → 3-decimal precision
- Dates → dateString type

### renderFn Strategy
**Existing:** 2 instances in calendar.py (titleCase, greenRed)
**New additions:**
- Regime direction → greenRed (EXPANSION=green, CONTRACTION=red)
- Stress levels → greenRed (normal=green, elevated=yellow, critical=red)
- Sentiment → greenRed (BULLISH=green, BEARISH=red)

## Current State (from Phase 23)

### Widget Config Inventory
- **18 total endpoints** with widget_config
  - 12 table endpoints (main routers)
  - 4 metric endpoints (workspace routes)
  - 2 chart endpoints (workspace routes)
- **columnDefs:** 1/12 table endpoints (calendar/events only)
- **renderFn:** 2 instances (calendar.py only)
- **formatterFn:** 0 instances
- **staleTime:** Only on metric/chart endpoints, missing from table endpoints

### refetchInterval Alignment (WC-01)
Current intervals need review against data source update frequencies:
- FRED daily data → 4h (14,400,000ms) appropriate
- Real-time (SOFR, regime, stress) → 15m (900,000ms) appropriate
- BIS quarterly → much longer or disabled
- Calendar → daily events, 1h appropriate
- Correlations → computed from historical, 1h appropriate

### staleTime Alignment (WC-02)
Missing from all 12 table endpoints. Should be ~50-75% of refetchInterval.

## Scope

### In Scope (3 Plans)
1. **24-01**: refetchInterval + staleTime optimization for all 18 endpoints
2. **24-02**: columnDefs + formatterFn + renderFn for all 12 table endpoints
3. **24-03**: Dynamic date defaults in widget params

### Out of Scope
- X-API-KEY auth (WC-05) — skipped per user decision
- CF JWT signature verification — deferred, separate concern
- New endpoint creation — no new routes needed
