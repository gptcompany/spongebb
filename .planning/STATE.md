# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-22)

**Core value:** Real-time regime classification — Know instantly whether we're in Expansionary or Contractionary liquidity regime to inform trading decisions.
**Current focus:** Phase 9 — Dashboard & Visualization (next)

## Current Position

Phase: 8 of 10 (Analysis & Correlations) - COMPLETE
Plan: 3 of 3 in current phase
Status: Phase 8 complete, ready for Phase 9
Last activity: 2026-01-26 — Completed Phase 8 (regime classifier, correlation engine, alert engine)

Progress: ████████░░ 80%

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

Last session: 2026-01-26
Stopped at: Completed Phase 8 (Analysis & Correlations)
Resume command: `/gsd:execute-phase 9` (after planning)

### Resume Context
- Phase 1 Foundation complete: uv project, collectors, QuestDB storage
- Phase 2 Global CB complete: ECB, BoJ, PBoC, BoE, SNB, BoC collectors
- Phase 3 complete: SOFR, €STR, SONIA, CORRA collectors + FX (DXY, major pairs)
- Phase 4 complete: CommodityCollector (gold, silver, copper, oil), ETFFlowCollector (GLD, SLV, USO, CPER, DBA)
- Phase 5 complete: TIC, Fed custody, COFER, stress indicators, risk ETFs
- Phase 6 research complete: Credit markets (HY OAS, SLOOS, CP rates), BIS international banking (LBS/CBS bulk CSV)
- Phase 7 complete: Net Liquidity, Global Liquidity, Stealth QE Score calculators
- Phase 8 complete: RegimeClassifier, CorrelationEngine, AlertEngine (94 tests)
- GitHub: https://github.com/gptprojectmanager/openbb_liquidity
- Next: Plan and execute Phase 9 (Dashboard & Visualization)
- Key insight: Binary regime (EXPANSION/CONTRACTION) with intensity 0-100, no "neutral" cop-out
- Correlation: 30d + 90d fixed windows + EWMA (halflife=21) for faster regime shift detection
- Alert threshold: 0.3 absolute change OR 2σ statistical deviation
- Collectors with robust fallbacks: BoE (3-tier), PBoC (3-tier), SOFR (3-tier), overnight rates (multi-tier)
