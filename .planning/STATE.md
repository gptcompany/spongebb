# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-22)

**Core value:** Real-time regime classification — Know instantly whether we're in Expansionary, Neutral, or Contractionary liquidity regime to inform trading decisions.
**Current focus:** Phase 3 — Overnight Rates & FX (in progress)

## Current Position

Phase: 3 of 10 (Overnight Rates & FX)
Plan: 1 of 3 in current phase
Status: In progress
Last activity: 2026-01-23 — Completed 03-01-PLAN.md (SOFR collector)

Progress: ████▓░░░░░ 27%

## Performance Metrics

**Velocity:**
- Total plans completed: 9
- Average duration: ~8 min
- Total execution time: ~1h 10min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3/3 | 29 min | 9.7 min |
| 2 | 5/5 | ~35 min | ~7 min |
| 3 | 1/3 | 8 min | 8 min |

**Recent Trend:**
- Phase 3 plans can run in parallel (no dependencies)
- SOFR collector pattern established for other overnight rates

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

### Pending Todos

- Configure FRED API key (LIQUIDITY_FRED_API_KEY) to run integration tests

### Blockers/Concerns

- purgatory shows deprecation warning for pkg_resources (library issue, not ours)
- FRED API key not yet configured (tests skip gracefully)
- BoE scraping returns 403 (fallback working)
- PBoC scraping fragile (FRED fallback reliable)

## Session Continuity

Last session: 2026-01-23
Stopped at: Completed 03-01-PLAN.md (SOFR collector)
Resume command: `/gsd:execute-plan .planning/phases/03-overnight-rates-fx/03-02-PLAN.md`

### Resume Context
- Phase 1 Foundation complete: uv project, collectors, QuestDB storage
- Phase 2 Global CB complete: ECB, BoJ, PBoC, BoE, SNB, BoC collectors
- Phase 3 in progress: SOFR collector complete (NY Fed primary API)
- GitHub: https://github.com/gptprojectmanager/openbb_liquidity
- Next: 03-02-PLAN.md (€STR, SONIA, CORRA collectors)
- Collectors with robust fallbacks: BoE (3-tier), PBoC (3-tier), SOFR (3-tier)
