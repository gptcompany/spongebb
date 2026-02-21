# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-21)

**Core value:** Real-time regime classification — Know instantly whether we're in Expansionary or Contractionary liquidity regime to inform trading decisions.
**Current focus:** v5.0 OpenBB Platform Integration — complete

## Current Position

Phase: 25 (Native Provider Extension) — COMPLETE
Plan: 3 of 3 complete
Status: All v5.0 phases complete (23, 24, 25)
Last activity: 2026-02-21 — Phase 25 executed (provider scaffold + 3 fetchers + 17 tests)

Progress: ============================== 100%

## Milestones

| Version | Name | Phases | Status | Shipped |
|---------|------|--------|--------|---------|
| v1.0 | MVP | 1-10 | ✅ Complete | 2026-02-04 |
| v2.0 | Advanced Analytics | 11-15 | ✅ Complete | 2026-02-06 |
| v3.0 | Commodity Intelligence | 16-21 | ✅ Complete | 2026-02-07 |
| v4.0 | Consumer Credit Risk | 22 | ✅ Complete | 2026-02-20 |
| v5.0 | OpenBB Platform Integration | 23-25 | ✅ Complete | 2026-02-21 |

## v5.0 Summary (COMPLETE)

**Goal:** Elevate the liquidity monitor from standalone Dash app to native OpenBB ecosystem component

**Delivered:**
- Phase 23: OpenBB Workspace custom backend (12 widget-annotated endpoints, CF Access middleware, Docker service)
- Phase 24: Widget polish (refetchInterval/staleTime optimization, columnsDefs + formatterFn/renderFn, params arrays)
- Phase 25: Native Provider Extension (`obb.liquidity.*` SDK with 3 Fetcher adapters: NetLiquidity, GlobalLiquidity, StealthQE)

## Accumulated Context

### From v5.0 Phase 25
- OpenBB Provider extension registered via `[project.entry-points."openbb_provider_extension"]`
- Lazy imports in `aextract_data()` to avoid circular dependency: provider → calculators → collectors → `from openbb import obb` → provider
- `date as dateType` alias pattern avoids Pydantic field name clash with type annotation
- 3 Fetcher classes in `src/liquidity/openbb_ext/models/` (TET pipeline pattern)
- 17 unit tests: 6 discovery + 11 fetcher TET

### From v5.0 Phase 24
- refetchInterval/staleTime tuned per data source frequency (FRED weekly, NY Fed daily, PBoC monthly)
- columnsDefs (with 's') is the correct OpenBB Workspace key (NOT columnDefs)
- formatterFn: int, none, percent, normalized, normalizedPercent, dateToYear
- renderFn: greenRed, titleCase, columnColor, hoverCard, cellOnClick, showCellChange

### From v5.0 Phase 23
- 12 API endpoints annotated with openapi_extra widget_config for OpenBB Workspace auto-discovery
- Flat Pydantic models need no dataKey; nested models use dataKey to point at array/dict field
- Calendar events uses columnsDefs for structured table display (date pinned, renderFn for type/impact)
- Docker workspace service on port 6900 (profiles: [workspace], host.docker.internal defaults)
- Makefile: workspace, workspace-dev, workspace-logs targets added

### From v4.0
- `dbc.Table` `dark=True` deprecated in dbc 2.0.4 → use `className="table-dark"` (fixed 2026-02-21)
- OpenBB SDK used as library only (not always-on service)
- Dashboard separate from OpenBB SDK boundary (confirmed in Phase 22-02)
- Container runtime operational (Dockerfile + compose + Makefile)
- Playwright visual regression baseline (desktop + mobile)
- Claude Code supervision protocol documented

### From v3.0
- Oil intelligence fully integrated with liquidity regime
- CFTC COT, EIA petroleum, term structure all operational

### From v2.0
- Nowcasting, risk metrics, news NLP all operational
- Backtesting engine with VectorBT validated

### From v1.0
- 31+ collectors, 14 API endpoints, 21 dashboard panels
- >85% global CB coverage confirmed
- Hayes formula (WALCL - TGA - RRP) validated

## Project Stats

- Total LOC: ~53,000
- Total Tests: 2,550+
- API Endpoints: 18 (14 original + 4 workspace)
- Dashboard Panels: 21
- Alert Types: 7
- Collectors: 31+
- OpenBB Provider Fetchers: 3
- GitHub: https://github.com/gptcompany/openbb_liquidity
- Tag: v5.0

## Session Continuity

Last session: 2026-02-21
Stopped at: Phase 25 complete — v5.0 milestone complete
Next steps: `/gsd:complete-milestone` to archive v5.0

---
*Last updated: 2026-02-21 after Phase 25 execution*
