# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-21)

**Core value:** Real-time regime classification — Know instantly whether we're in Expansionary or Contractionary liquidity regime to inform trading decisions.
**Current focus:** v5.0 OpenBB Platform Integration — defining requirements

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-02-21 — Milestone v5.0 started

Progress: ░░░░░░░░░░░░░░░░░░░░░ 0%

## Milestones

| Version | Name | Phases | Status | Shipped |
|---------|------|--------|--------|---------|
| v1.0 | MVP | 1-10 | ✅ Complete | 2026-02-04 |
| v2.0 | Advanced Analytics | 11-15 | ✅ Complete | 2026-02-06 |
| v3.0 | Commodity Intelligence | 16-21 | ✅ Complete | 2026-02-07 |
| v4.0 | Consumer Credit Risk | 22 | ✅ Complete | 2026-02-20 |
| v5.0 | OpenBB Platform Integration | TBD | ◆ Active | — |

## v5.0 Scope (ACTIVE)

**Goal:** Elevate the liquidity monitor from standalone Dash app to native OpenBB ecosystem component

**Target features:**
- OpenBB Workspace custom backend (FastAPI → widget-compatible endpoints)
- OpenBB Provider Extension (`openbb-liquidity` package with ETL Fetcher classes)
- openbb-cookiecutter multi-interface generation (Workspace + MCP + CLI + Python)

## Accumulated Context

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

- Total LOC: ~52,000
- Total Tests: 2,500+
- API Endpoints: 14
- Dashboard Panels: 21
- Alert Types: 7
- Collectors: 31+
- GitHub: https://github.com/gptcompany/openbb_liquidity
- Tag: v4.0

## Session Continuity

Last session: 2026-02-21
Stopped at: v5.0 milestone initialization — defining requirements
Next steps: Research OpenBB extension ecosystem, define requirements, create roadmap

---
*Last updated: 2026-02-21 after v5.0 milestone initialization*
