# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-22)

**Core value:** Real-time regime classification — Know instantly whether we're in Expansionary or Contractionary liquidity regime to inform trading decisions.
**Current focus:** v2.0 Milestone - Advanced Analytics

## Current Position

Phase: 11 of 15 (High-Frequency Data Layer) - COMPLETE
Plan: 6 of 6 in current phase
Status: Phase 11 complete, ready for Phase 12
Last activity: 2026-02-05 — Completed Phase 11 (HF collectors via /pipeline.gsd)

Progress: ███████████░░░░ 73% (11/15 phases)

## Performance Metrics

**Velocity:**
- Total plans completed: 11
- Average duration: ~7 min
- Total execution time: ~1h 25min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3/3 | 29 min | 9.7 min |
| 2 | 5/5 | ~35 min | ~7 min |
| 3 | 3/3 | ~21 min | ~7 min |
| 4 | 2/2 | ~10 min | ~5 min |

**Recent Trend:**
- Phase 3 plans ran in parallel (3 concurrent agents)
- All overnight rate collectors + FX collectors complete

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

| Plan | Decision | Rationale |
|------|----------|-----------|
| 01-01 | purgatory 0.7.x not 1.x | Version 1.0+ doesn't exist yet |
| 01-01 | Added setuptools runtime dep | Required by purgatory for pkg_resources |
| 01-01 | Generic[T] for BaseCollector | Type-safe collector implementations |
| 01-02 | psycopg2-binary for PGWire | Standard PostgreSQL driver for QuestDB |
| 01-02 | MONTH partitioning | Optimal for macro data (daily/weekly) |
| 01-02 | asyncio.to_thread() for OpenBB | OpenBB SDK is sync-only |
| 01-03 | MOVE via Yahoo Finance | Not available in FRED, used OpenBB yfinance |
| 01-03 | Credit spreads in bps | Matches ICE BofA OAS index conventions |
| 02-01 | ECB/BoJ via FRED | ECBASSETSW and JPNASSETS available on FRED |
| 02-02 | BoC Valet API direct | pyvalet wrapper less reliable than direct HTTP |
| 02-03 | BoE multi-tier fallback | Scraping + FRED proxy + cached baseline |
| 02-04 | SNB CSV direct download | No auth required, semicolon-separated CSV |
| 02-05 | PBoC FRED fallback | TRESEGCNM052N as proxy (same as Apps Script) |
| 03-01 | NY Fed Markets API for SOFR | No auth required, real-time data |
| 03-01 | SOFR 3-tier fallback | NY Fed -> FRED -> baseline (4.35%) |
| 03-02 | estr.dev for €STR | Simpler than ECB API, clean JSON |
| 03-02 | FRED for SONIA | BoE API unreliable (returns HTML) |
| 03-02 | BoC Valet for CORRA | Most reliable CB API, no fallback needed |
| 03-03 | yfinance for FX data | Free, no provider fees, batch download |
| 03-03 | ffill for DXY gaps | DXY doesn't trade Sunday, FX pairs do |

### Pending Todos

- Configure FRED API key (LIQUIDITY_FRED_API_KEY) to run integration tests

### Blockers/Concerns

- purgatory shows deprecation warning for pkg_resources (library issue, not ours)
- FRED API key not yet configured (tests skip gracefully)
- BoE scraping returns 403 (fallback working)
- PBoC scraping fragile (FRED fallback reliable)

## Session Continuity

Last session: 2026-02-04
Stopped at: PROJECT COMPLETE
Resume command: N/A - All phases complete

### Project Summary
- Phase 1 Foundation: uv project, collectors, QuestDB storage
- Phase 2 Global CB: ECB, BoJ, PBoC, BoE, SNB, BoC collectors
- Phase 3 Rates & FX: SOFR, €STR, SONIA, CORRA + FX collectors
- Phase 4 Markets: Commodities + ETF flows collectors
- Phase 5 Capital Flows: TIC, Fed custody, COFER, stress indicators
- Phase 6 Credit & BIS: Credit markets, BIS international banking
- Phase 7 Calculations: Net Liquidity, Global Liquidity, Stealth QE Score
- Phase 8 Analysis: RegimeClassifier, CorrelationEngine, AlertEngine
- Phase 9 Calendar & API: Calendar module, FastAPI server, Docker
- Phase 10 Visualization: Plotly Dash dashboard, Discord alerts, QA validation

### Final Stats
- Total LOC: ~15,000+
- Total Tests: 650+
- API Endpoints: 12
- Dashboard Panels: 10
- Alert Types: 4
- GitHub: https://github.com/gptprojectmanager/openbb_liquidity

### Key Features
- Binary regime (EXPANSION/CONTRACTION) with intensity 0-100
- Correlation: 30d + 90d fixed windows + EWMA
- Alert threshold: 0.3 absolute change OR 2σ deviation
- Collectors with robust multi-tier fallbacks
- Full data quality validation system
