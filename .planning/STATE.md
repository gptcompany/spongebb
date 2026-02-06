# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-06)

**Core value:** Real-time regime classification — Know instantly whether we're in Expansionary or Contractionary liquidity regime to inform trading decisions.
**Current focus:** v3.0 Commodity Intelligence — Oil supply fundamentals and market structure

## Current Position

Phase: 16 of 21 (EIA Oil Data)
Plan: Not started
Status: Ready to plan
Last activity: 2026-02-06 — Milestone v3.0 created

Progress: ███████████████░░░░░░ 71% (15/21 phases, 56/80 plans)

## Milestones

| Version | Name | Phases | Status | Shipped |
|---------|------|--------|--------|---------|
| v1.0 | MVP | 1-10 | ✅ Complete | 2026-02-04 |
| v2.0 | Advanced Analytics | 11-15 | ✅ Complete | 2026-02-06 |
| v3.0 | Commodity Intelligence | 16-21 | 🚧 In Progress | - |

## v3.0 Scope

**Goal:** Transform oil from "price tracker" to "macro liquidity indicator"

| Phase | Name | Plans | Status |
|-------|------|-------|--------|
| 16 | EIA Oil Data | 4 | Not started |
| 17 | CFTC Positioning | 4 | Not started |
| 18 | Oil Term Structure | 4 | Not started |
| 19 | Real Rates | 4 | Not started |
| 20 | Commodity News | 4 | Not started |
| 21 | Supply-Demand Model | 4 | Not started |

**Key Additions:**
- EIA Weekly Petroleum (inventory, production, refinery)
- CFTC COT Reports (commercial vs speculator positioning)
- Oil term structure (contango/backwardation signals)
- Real rates tracking (oil-rates correlation)
- Commodity news intelligence (OPEC, weather, sanctions)
- Supply-demand balance calculator

## Project Stats

- Total LOC: ~43,000
- Total Tests: 2100+
- API Endpoints: 12
- Dashboard Panels: 10
- Alert Types: 4
- Collectors: 25+
- GitHub: https://github.com/gptcompany/openbb_liquidity

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

## Session Continuity

Last session: 2026-02-06
Stopped at: Milestone v3.0 Commodity Intelligence created
Next steps: `/gsd:plan-phase 16` or `/pipeline.gsd` for Phase 16

---
*Last updated: 2026-02-06 after v3.0 milestone creation*
