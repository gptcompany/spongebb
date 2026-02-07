# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-07)

**Core value:** Real-time regime classification — Know instantly whether we're in Expansionary or Contractionary liquidity regime to inform trading decisions.
**Current focus:** v3.0 Complete — Ready for v4.0 planning

## Current Position

Phase: 21 of 21 (Supply-Demand Model)
Plan: 4/4 Complete
Status: ✅ Milestone Complete
Last activity: 2026-02-07 — v3.0 Commodity Intelligence shipped

Progress: █████████████████████ 100% (21/21 phases, 80/80 plans)

## Milestones

| Version | Name | Phases | Status | Shipped |
|---------|------|--------|--------|---------|
| v1.0 | MVP | 1-10 | ✅ Complete | 2026-02-04 |
| v2.0 | Advanced Analytics | 11-15 | ✅ Complete | 2026-02-06 |
| v3.0 | Commodity Intelligence | 16-21 | ✅ Complete | 2026-02-07 |

## v3.0 Scope (SHIPPED)

**Goal:** Transform oil from "price tracker" to "macro liquidity indicator"

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 16 | EIA Oil Data | 4/4 | ✅ Complete |
| 17 | CFTC Positioning | 4/4 | ✅ Complete |
| 18 | Oil Term Structure | 4/4 | ✅ Complete |
| 19 | Real Rates | 4/4 | ✅ Complete |
| 20 | Commodity News | 4/4 | ✅ Complete |
| 21 | Supply-Demand Model | 4/4 | ✅ Complete |

**Key Additions:**
- EIA Weekly Petroleum (inventory, production, refinery)
- CFTC COT Reports (commercial vs speculator positioning)
- Oil term structure (contango/backwardation signals)
- Real rates tracking (oil-rates correlation)
- Commodity news intelligence (OPEC, weather, sanctions)
- Supply-demand balance calculator
- Combined Liquidity×Oil regime integration

## Project Stats

- Total LOC: ~48,000
- Total Tests: 2,500+
- API Endpoints: 14
- Dashboard Panels: 13
- Alert Types: 7
- Collectors: 30+
- GitHub: https://github.com/gptcompany/openbb_liquidity
- Tag: v3.0

## Key Features

### v1.0 MVP
- Fed balance sheet tracking (Hayes formula: WALCL - TGA - RRP)
- Global CB coverage >85% (Fed, ECB, BoJ, PBoC, BoE, SNB, BoC)
- Binary regime (EXPANSION/CONTRACTION) with intensity 0-100
- Correlation engine: 30d + 90d windows + EWMA
- FastAPI server with 12 endpoints
- Plotly Dash dashboard with 10 panels
- Discord alerting

### v2.0 Advanced Analytics
- High-frequency data (daily TGA, China DR007/SHIBOR, stablecoins)
- Nowcasting (Kalman filters, HMM regime detection, PBoC estimator)
- Risk metrics (VaR, CVaR, Regime VaR)
- News intelligence (RSS, NLP translation, FOMC diff)
- Backtesting (VectorBT, Monte Carlo, regime attribution)

### v3.0 Commodity Intelligence
- EIA Weekly Petroleum collector
- CFTC COT positioning analytics
- Oil term structure (contango/backwardation)
- Real rates engine (TIPS, BEI, oil correlation)
- Commodity news (oil RSS, OPEC calendar, NOAA hurricane)
- Supply-demand model (balance, forecast, regime)
- Combined Liquidity×Oil regime matrix

## Session Continuity

Last session: 2026-02-07
Stopped at: v3.0 milestone complete and shipped
Next steps: Define v4.0 scope with `/gsd:new-milestone` or `/gsd:discuss-milestone`

---
*Last updated: 2026-02-07 after v3.0 shipped*
