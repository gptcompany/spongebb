# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-07)

**Core value:** Real-time regime classification — Know instantly whether we're in Expansionary or Contractionary liquidity regime to inform trading decisions.
**Current focus:** v4.0 Complete + visual regression hardening — Ready for v5.0 planning

## Current Position

Phase: 22 of 22 (Consumer Credit Risk Intelligence)
Plan: 1/1 Complete
Status: ✅ Milestone Complete
Last activity: 2026-02-20 — Playwright visual regression + CI workflow shipped

Progress: █████████████████████ 100% (22/22 phases, 81/81 plans)

## Milestones

| Version | Name | Phases | Status | Shipped |
|---------|------|--------|--------|---------|
| v1.0 | MVP | 1-10 | ✅ Complete | 2026-02-04 |
| v2.0 | Advanced Analytics | 11-15 | ✅ Complete | 2026-02-06 |
| v3.0 | Commodity Intelligence | 16-21 | ✅ Complete | 2026-02-07 |
| v4.0 | Consumer Credit Risk | 22 | ✅ Complete | 2026-02-20 |

## v4.0 Scope (SHIPPED)

**Goal:** Add a dedicated consumer-credit-risk monitoring layer and dashboard intelligence

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 22 | Consumer Credit Risk Intelligence | 1/1 | ✅ Complete |

**Key Additions:**
- Consumer credit total / student loans / ex-student tracking
- Debt-in-default proxy estimate
- Mortgage losses and loan loss reserves monitoring
- XLP/XLY relative chart
- AXP vs IGV relative spread chart
- Credit-sensitive stocks ranking panel

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
- Dashboard Panels: 14
- Alert Types: 7
- Collectors: 31+
- GitHub: https://github.com/gptcompany/openbb_liquidity
- Tag: v4.0

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

### v4.0 Consumer Credit Risk
- Consumer credit risk collector (FRED + Yahoo)
- Ex-student loan credit tracking and debt-in-default proxy
- Mortgage loss rates and bank loan loss reserves
- USD liquidity proxy index
- Dashboard panel: XLP/XLY + AXP/IGV + sensitive stock ranking

## Session Continuity

Last session: 2026-02-20
Stopped at: Visual regression pipeline documented and integrated (Plan 10-06)
Next steps: Define v5.0 scope with `/gsd:new-milestone` or `/gsd:discuss-milestone`

---
*Last updated: 2026-02-20 after visual regression hardening (10-06)*
