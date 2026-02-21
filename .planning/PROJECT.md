# Global Liquidity Monitor (OpenBB)

## What This Is

A FAANG-grade global liquidity monitoring system based on Arthur Hayes' framework. Tracks >85% of global monetary flows from central banks, overnight markets, and institutional investors using OpenBB as unified data platform. Integrates with NautilusTrader for macro-filtered trading strategies. Exposes data through FastAPI REST endpoints and an interactive Plotly Dash dashboard.

## Core Value

**Real-time regime classification** — Know instantly whether we're in Expansionary, Neutral, or Contractionary liquidity regime to inform trading decisions.

## Current State: v5.0 Shipped

**Last shipped:** v5.0 OpenBB Platform Integration (2026-02-21)

**Delivered in v5.0:**
- OpenBB Workspace custom backend (12 widget-annotated endpoints, CF Access middleware, Docker service)
- Widget polish (refetchInterval/staleTime optimization, columnsDefs + formatterFn/renderFn, params arrays)
- Native Provider Extension (`obb.liquidity.*` SDK with 3 Fetcher adapters: NetLiquidity, GlobalLiquidity, StealthQE)

**Next milestone:** TBD — run `/gsd:new-milestone` to define v6.0

## Requirements

### Validated

- ✓ Net Liquidity Index (Hayes formula: WALCL - TGA - RRP) — v1.0
- ✓ Global Liquidity Index (Fed + ECB + BoJ + PBoC in USD) — v1.0
- ✓ Tier 1 CB collectors (Fed, ECB, BoJ, PBoC, BoE, SNB, BoC) — v1.0
- ✓ Overnight rates monitoring (SOFR, €STR, SONIA, CORRA) — v1.0
- ✓ Bonds & volatility tracking (MOVE, VIX, yield curve, credit spreads) — v1.0
- ✓ Stealth QE Score calculation (port from Apps Script) — v1.0
- ✓ Regime classifier (Expansionary/Contractionary) — v1.0
- ✓ FastAPI REST server for data access — v1.0
- ✓ Discord webhook alerts for regime changes — v1.0
- ✓ Plotly dashboards (HTML exportable) — v1.0
- ✓ Double-entry validation for data consistency — v1.0
- ✓ >85% global monetary flow coverage — v1.0
- ✓ High-frequency data layer (daily TGA, China proxies, stablecoins) — v2.0
- ✓ Nowcasting engine (Kalman filter, HMM, PBoC estimator) — v2.0
- ✓ Risk metrics (VaR, CVaR, Regime VaR) — v2.0
- ✓ News intelligence (RSS, NLP, FOMC diff) — v2.0
- ✓ Backtesting engine (VectorBT, Monte Carlo, regime attribution) — v2.0
- ✓ Oil intelligence stack (EIA, CFTC, term structure, supply-demand) — v3.0
- ✓ Consumer credit risk layer (credit stress, XLP/XLY, sensitive stocks) — v4.0
- ✓ Container runtime (Dockerfile, compose, Makefile) — v4.0
- ✓ Claude Code supervision protocol — v4.0
- ✓ OpenBB Workspace custom backend (12 widget endpoints, Docker service) — v5.0
- ✓ Widget polish (refetchInterval, columnsDefs, formatters) — v5.0
- ✓ OpenBB Provider Extension (`obb.liquidity.*` SDK, 3 Fetcher adapters) — v5.0

### Active

None — all milestones v1.0-v5.0 complete. Run `/gsd:new-milestone` for v6.0.

### Out of Scope

- Real-time intraday updates — daily/weekly sufficient for macro analysis
- Bloomberg Terminal integration — too expensive ($24k/year), use free APIs
- Shadow banking tracking — opaque, unreliable data
- NautilusTrader macro filter integration — deferred, separate repo concern
- OpenBB Terminal (legacy CLI) integration — focus on Workspace + SDK

## Context

**Reference implementation:** `.planning/reference/appscript_v3.4.1.md` — Apps Script da portare (Stealth QE formula, thresholds, FRED series codes)

**Origin:** Arthur Hayes "Frowny Cloud" article analysis showing Bitcoin correlation with dollar liquidity (0.7-0.8).

**Current state (v5.0 shipped):**
- ~53,000 LOC Python across 174+ source files
- 31+ data collectors, 18 API endpoints, 21 dashboard panels
- OpenBB Workspace backend with 12 widget-annotated endpoints
- OpenBB Provider Extension with 3 Fetcher adapters (`obb.liquidity.*`)
- 2,550+ tests, Docker Compose runtime
- OpenBB SDK 4.x (pinned >=4.4.0,<4.7.0)

**Data sources confirmed:**
- FRED API (Fed, ECB, BoJ, rates, bonds) — free, reliable
- ECB SDW API — free, reliable
- BIS SDMX API — free, quarterly lag
- Yahoo Finance (MOVE, VIX) — free
- NY Fed Data Hub (RMP, repo) — free
- EIA API — petroleum data
- CFTC API — positioning data
- PBoC — monthly lag, scraping required

## Constraints

- **Tech stack**: Python 3.11+, OpenBB SDK 4.x, uv package manager
- **Storage**: QuestDB for time-series
- **Visualization**: Plotly Dash (standalone) + OpenBB Workspace (integrated)
- **Data lag**: Accept 1-day lag for Tier 1 CB, 10-15 days for PBoC
- **Coverage target**: >85% global monetary flows
- **OpenBB compatibility**: Must work with OpenBB 4.6.0+ and cookiecutter template

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Standalone repo `/media/sam/1TB/openbb_liquidity` | Separation of concerns (macro ≠ trading) | ✓ Good |
| OpenBB as data platform | 100+ providers, Python native, LLM-ready | ✓ Good |
| Plotly over Grafana | Simpler deployment, HTML export, no extra service | ✓ Good |
| Port Apps Script to Python | Remove Google limitations, enable backtest/integration | ✓ Good |
| Double-entry validation | Ensure data consistency via accounting checks | ✓ Good |
| Strategy B→A→C for OpenBB integration | Workspace backend (quick win) → Provider (reusable) → cookiecutter (full) | ✓ B+A done, C deferred |
| Dashboard stays standalone + OpenBB | Keep Dash app, add OpenBB as additional interface | ✓ Good |

---
*Last updated: 2026-02-21 after v5.0 milestone archived*
