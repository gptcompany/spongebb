---
phase: 23-workspace-backend
plan: 03
subsystem: api, infra
tags: [openbb, workspace, openapi, widget_config, docker, fastapi]

# Dependency graph
requires:
  - phase: 23-01
    provides: workspace_app.py entry point, CORS config, version pinning
  - phase: 23-02
    provides: /workspace/* metric and chart endpoints
provides:
  - openapi_extra widget_config annotations on 12 existing table endpoints
  - Docker Compose liquidity-workspace service on port 6900
  - Makefile workspace/workspace-dev/workspace-logs targets
affects: [23-04, workspace deployment, OpenBB Workspace dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [openapi_extra widget_config for OpenBB Workspace auto-discovery, dataKey for nested response fields, columnsDefs for calendar table layout]

key-files:
  created: []
  modified:
    - src/liquidity/api/routers/stress.py
    - src/liquidity/api/routers/fx.py
    - src/liquidity/api/routers/correlations.py
    - src/liquidity/api/routers/calendar.py
    - src/liquidity/api/routers/liquidity.py
    - src/liquidity/api/routers/regime.py
    - src/liquidity/api/routers/metrics.py
    - docker-compose.yml
    - Makefile

key-decisions:
  - "Used user-specified widget names and descriptions for clarity in Workspace"
  - "Flat models (stress, regime, metrics, liquidity) get no dataKey -- Workspace renders as single-row table"
  - "Nested models (fx pairs, correlations, calendar events) get dataKey pointing at array/dict field"
  - "Calendar events endpoint includes columnsDefs for structured display (date pinned left, impact with greenRed render)"
  - "Docker workspace service uses host.docker.internal for QuestDB/Redis connectivity"
  - "Workspace profile keeps service opt-in, consistent with existing profile patterns"

patterns-established:
  - "widget_config annotation pattern: place openapi_extra after description= in @router.get() decorator"
  - "dataKey for nested Pydantic responses, omit for flat top-level models"

requirements-completed: [WS-06, WS-07]

# Metrics
duration: 10min
completed: 2026-02-21
---

# Phase 23 Plan 03: Table Endpoint Annotations + Docker Workspace Service Summary

**12 existing API endpoints annotated with openapi_extra widget_config for OpenBB Workspace auto-discovery, plus Docker Compose service and Makefile targets for workspace backend on port 6900**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-21T15:13:17Z
- **Completed:** 2026-02-21T15:23:26Z
- **Tasks:** 9/9
- **Files modified:** 9

## Accomplishments
- Annotated all 12 existing table-compatible API endpoints with OpenBB Workspace widget_config metadata
- Added Docker Compose liquidity-workspace service (port 6900, workspace profile, 20s start_period)
- Added Makefile targets: workspace, workspace-dev, workspace-logs; updated down to include workspace profile
- Calendar events endpoint includes columnsDefs for structured display (date pinned left, type/impact with renderFn)

## Task Commits

Each task was committed atomically:

1. **Task 1: stress indicators annotation** - `250b52f` (feat)
2. **Task 2: FX endpoints annotation (dxy, pairs)** - `a4407ea` (feat)
3. **Task 3: correlations endpoints annotation** - `0916783` (feat)
4. **Task 4: calendar endpoints annotation (events, next)** - `1129277` (feat)
5. **Task 5: liquidity endpoints annotation (net, global)** - `1e1bfa2` (feat)
6. **Task 6: regime endpoints annotation (current, combined)** - `8d1ccb1` (feat)
7. **Task 7: metrics stealth-qe annotation** - `96f99a3` (feat)
8. **Task 8: Docker Compose workspace service** - `a72b53d` (feat)
9. **Task 9: Makefile workspace targets** - `fad4a0c` (feat)

## Files Created/Modified
- `src/liquidity/api/routers/stress.py` - Added widget_config to /indicators (Funding Stress Indicators)
- `src/liquidity/api/routers/fx.py` - Added widget_config to /dxy (DXY Index) and /pairs (Major FX Pairs)
- `src/liquidity/api/routers/correlations.py` - Added widget_config to / (Liquidity Correlations) and /matrix (Correlation Matrix)
- `src/liquidity/api/routers/calendar.py` - Added widget_config to /events (Macro Calendar with columnsDefs) and /next (Next Events)
- `src/liquidity/api/routers/liquidity.py` - Added widget_config to /net (Net Liquidity Detail) and /global (Global Liquidity Detail)
- `src/liquidity/api/routers/regime.py` - Added widget_config to /current (Current Regime) and /combined (Combined Regime)
- `src/liquidity/api/routers/metrics.py` - Added widget_config to /stealth-qe (Stealth QE Detail)
- `docker-compose.yml` - Added liquidity-workspace service (port 6900, workspace profile)
- `Makefile` - Added workspace, workspace-dev, workspace-logs targets; updated down and .PHONY

## Decisions Made
- Used user-specified widget names and descriptions verbatim for Workspace clarity
- Flat Pydantic models (stress, regime, metrics, liquidity) need no dataKey -- Workspace auto-renders as single-row table
- Nested models (fx.pairs, correlations, calendar.events) use dataKey to point Workspace at the array/dict field
- Calendar events includes columnsDefs for structured display: date pinned left, event_type with titleCase renderFn, impact with greenRed renderFn
- Docker workspace service defaults to host.docker.internal for QuestDB/Redis (host networking to existing infrastructure)
- Workspace profile keeps service opt-in, consistent with dashboard/dev/test/isolated pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 12 existing endpoints now discoverable by OpenBB Workspace as table widgets
- Docker service ready for `make workspace` to launch backend on port 6900
- Plan 23-04 (testing/validation) can verify widget_config annotations in OpenAPI schema

## Self-Check: PASSED

- All 9 modified files exist on disk
- All 9 task commit hashes verified in git log

---
*Phase: 23-workspace-backend*
*Completed: 2026-02-21*
