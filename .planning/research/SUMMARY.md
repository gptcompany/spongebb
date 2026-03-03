# Research Summary: Global Liquidity Monitor — v5.0 OpenBB Platform Integration

**Project:** Global Liquidity Monitor
**Milestone:** v5.0 — OpenBB Platform Integration
**Domain:** Financial data platform extension + Workspace custom backend
**Researched:** 2026-02-21
**Synthesized:** 2026-02-21
**Confidence:** HIGH

---

## Executive Summary

The Global Liquidity Monitor already has a production-grade FastAPI server (14 endpoints), Plotly Dash dashboard (21 panels), and OpenBB SDK as a data consumer. The v5.0 milestone asks how to expose this system _into_ the OpenBB ecosystem — both as an OpenBB Workspace UI backend and optionally as a native Python SDK provider. All 4 researchers converge on the same conclusion: the correct primary integration path is the FastAPI custom backend via `openbb-platform-api`, not a full provider extension. This path takes the existing `server.py` and makes it an OpenBB Workspace data connector with minimal code changes (CORS headers, `openapi_extra` widget annotations, and one CLI launch command). The Workspace auto-generates `widgets.json` from the existing OpenAPI schema — no new data models, no entry point registration, no `openbb-build`.

The secondary path — a native OpenBB provider extension (`obb.liquidity.*`) — is architecturally sound and well-documented, but carries significant maintenance overhead: `openbb-build` must run after every model change, entry point naming is fragile, and `PackageBuilder` has known bugs in Python 3.12 + uv environments. Research strongly recommends treating the provider extension as an optional Phase 2 deliverable, not a Phase 1 requirement. The project does not need provider extensions to appear in OpenBB Workspace — the backend path is sufficient and independent.

The key risk is CORS/SSL complexity when connecting from browser-based OpenBB Workspace (pro.openbb.co) to a local HTTP server. Browsers enforce mixed-content blocking, and Safari/Brave always fail. The mitigation is straightforward: use the OpenBB Desktop App for local development (bypasses all SSL restrictions), or generate a self-signed certificate for browser-based Workspace. OpenBB version pinning (`openbb>=4.4.0,<4.6.0`) is also critical — the project currently pins `openbb>=4.0.0`, which exposes it to endpoint rename breakage across minor versions.

---

## Consensus Findings

All 4 researchers agree on the following:

1. **Primary path is `openbb-api --app`**, not a provider extension. STACK, FEATURES, ARCHITECTURE, and PITFALLS researchers all independently arrive at this conclusion.
2. **Provider extension is optional Phase 2.** It adds real value (`obb.liquidity.*` SDK access, AI agent tool exposure) but is not required for Workspace widget integration.
3. **Zero duplication of business logic.** Calculators (`src/liquidity/calculators/`) are the single source of truth. The OpenBB layer wraps them via thin adapters (Fetchers for provider extension) or re-exports the existing FastAPI app (Workspace backend).
4. **CORS for `https://pro.openbb.co` is required.** The existing permissive CORS config (`allow_origins=["*"]`) works for development but must explicitly include the OpenBB Workspace origin.
5. **`openbb-build` is a mandatory ritual after any provider extension change.** Multiple researchers flag this as the most common silent-failure mode in containerized environments.

---

## Divergences and Resolutions

### Divergence 1: Monorepo vs separate package for provider extension

- **STACK.md:** Suggests a separate `spongebb_provider/` directory as an independent package with its own `pyproject.toml`.
- **ARCHITECTURE.md:** Recommends a monorepo subfolder (`src/liquidity/openbb_ext/`) within the existing package, using the root `pyproject.toml` entry points.

**Resolution: Monorepo subfolder (ARCHITECTURE.md wins).** The project has 174 files and 52K LOC. A separate package requires separate versioning, separate CI, and separate installation steps. The monorepo approach keeps business logic co-located and avoids the circular dependency trap. Extract to a standalone package in v6.0 when the API surface is stable.

### Divergence 2: `credentials=None` vs `credentials=[]` in Provider registration

- **STACK.md:** Uses `credentials=None` for the Provider instance.
- **ARCHITECTURE.md (features-api.md):** Uses `credentials=[]`.
- **ARCHITECTURE.md (architecture.md):** Uses `credentials=["fred_api_key"]`.

**Resolution: `credentials=["fred_api_key"]`.** FRED API key is a real credential used by the FredCollector. Passing it through the OpenBB credential system (via `OPENBB_FRED_API_KEY` env var) is the correct pattern. `credentials=None` causes validation errors; `credentials=[]` drops the credential silently.

### Divergence 3: Poetry vs uv entry-point syntax

- **STACK.md:** Uses `[project.entry-points."openbb_provider_extension"]` (PEP 517/uv).
- **FEATURES.md (features-api.md):** Uses `[tool.poetry.plugins."openbb_provider_extension"]` (Poetry).
- **PITFALLS.md:** Flags Poetry-style as potentially non-discoverable with non-Poetry build backends.

**Resolution: Use `[project.entry-points."openbb_provider_extension"]`.** The project uses `uv` with setuptools. PEP 517 `[project.entry-points]` is the correct table. Poetry plugin syntax is backend-specific and not guaranteed to work with setuptools.

### Divergence 4: Whether to add dedicated `/workspace/*` routes vs annotate existing routes

- **FEATURES.md:** Recommends dedicated `/workspace/*` Workspace-optimized routes (Option B) to preserve existing endpoint schemas for NautilusTrader integration.
- **STACK.md / ARCHITECTURE.md:** Suggests annotating existing routes with `openapi_extra` is sufficient.

**Resolution: Dedicated `/workspace/*` routes for shape-divergent responses.** Existing endpoints (`/liquidity/net`, etc.) return `NetLiquidityResponse` Pydantic models suited for machine consumption. Workspace needs `MetricResponseModel` for metric widgets and Plotly JSON for chart widgets. These shapes are incompatible. Add `openapi_extra` to existing table endpoints (compatible), but add dedicated `/workspace/*` endpoints for metric and chart widgets to avoid breaking existing consumers.

---

## Revised Strategy Recommendation

The original strategy was B (Workspace backend) → A (Provider extension) → C (cookiecutter). Research supports a revised strategy:

### Revised Strategy: B-only for v5.0, A as optional Phase 2

**Phase 1: Workspace Backend (B-only, low risk)**
Use `openbb-api --app` to expose the existing FastAPI as an OpenBB Workspace custom backend. This is the entire v5.0 scope. No provider extension, no cookiecutter.

**Rationale for dropping A from v5.0:**
- Provider extension adds `obb.liquidity.*` SDK access, but the project has no current consumer of this (NautilusTrader uses the REST API directly via HTTP).
- Provider extension requires `openbb-build` ritual + entry point registration — maintenance cost is real.
- `PackageBuilder` has open bugs in Python 3.12 + uv (Issue #7113).
- FEATURES.md and PITFALLS.md both conclude the provider extension is "not needed for this project" in v5.0.

**Phase 2 (optional, v5.5 or v6.0): Native Provider Extension (A)**
Build `src/liquidity/openbb_ext/` with thin Fetcher adapters wrapping existing calculators. This enables `obb.liquidity.net()` in Python SDK, OpenBB CLI, and future AI agent tool exposure. Low urgency — the Workspace backend already delivers all visible v5.0 value.

**Cookiecutter (C): Reference only**
Generate skeleton in a temp directory, cherry-pick the `pyproject.toml` template pattern. Do not use generated model files — port existing code instead. Cookiecutter has not been migrated to uv (Issue #14) and requires manual tweaks.

---

## Key Findings

### Recommended Stack

The v5.0 integration requires minimal new dependencies. The primary addition is `openbb-platform-api` (v1.3.0, released 2026-02-17), which wraps the existing FastAPI and auto-generates `widgets.json`. The existing stack (Python 3.11+, FastAPI, uv, QuestDB, Docker Compose) remains unchanged.

**Core technologies for v5.0:**
- `openbb-platform-api>=1.3.0`: Wraps existing FastAPI as Workspace backend — enables `openbb-api --app` launch command.
- `openapi_extra` (FastAPI built-in): Inline widget configuration annotations — replaces need for manual `widgets.json` for most endpoints.
- `openbb-core` (implicit, via `openbb>=4.0.0`): Provides `Fetcher`, `QueryParams`, `Data`, `Provider` base classes for Phase 2 provider extension.
- `vcrpy + pytest-recorder` (Phase 2 testing): HTTP cassette recording for hermetic Fetcher tests.

**Version constraint change required:**
Current: `openbb>=4.0.0` — MUST change to `openbb>=4.4.0,<4.7.0` to prevent silent breakage from endpoint renames across minor versions.

See `.planning/research/stack-tech.md` for full TET pipeline examples and pyproject.toml templates.

### Expected Features

**Must have (table stakes for v5.0):**
- All 14 existing GET endpoints exposed as OpenBB Workspace widgets (auto-generated via `openbb-api --app`).
- CORS configured for `https://pro.openbb.co` and `http://localhost:1420` (Desktop App).
- Widget metadata via `openapi_extra`: name, category, refresh intervals, grid dimensions.
- Metric widgets for: Net Liquidity (current value + WoW delta), Global Liquidity total, Stealth QE score, Regime badge.
- Chart widgets for: Net Liquidity time series, Global Liquidity breakdown — existing Plotly figures converted via `.to_plotly_json()`.
- Table widgets for: Stress indicators, correlations, FX monitor, macro calendar.
- `/workspace/*` dedicated routes for metric and chart shapes (separate from existing REST endpoints).

**Should have (differentiators for v5.0):**
- `refetchInterval` per widget type: daily FRED data at 4h, regime/stress at 15m, quarterly BIS data disabled.
- `staleTime` configured to match data update frequencies.
- Dynamic date defaults in widget params (`$currentDate-2y` for history).
- `data.table.columnsDefs` with `formatterFn: "int"` and `renderFn: "greenRed"` for liquidity delta columns.
- Optional `X-API-KEY` header auth middleware (disabled by default, enable for remote access).

**Defer to Phase 2 / v5.5+:**
- Native provider extension (`obb.liquidity.*` Python SDK access).
- Router extension creating `obb.liquidity` namespace.
- MCP tool exposure via `agents.json`.
- `live_grid` WebSocket widget (not needed — daily/weekly macro data).
- Public PyPI publication as `openbb-liquidity`.

See `.planning/research/features-api.md` for complete `widgets.json` field reference and endpoint-to-widget mapping table.

### Architecture Approach

The architecture follows a strict one-way dependency: `openbb_ext → calculators` (never the reverse). The OpenBB integration layer is a thin adapter that wraps existing calculators without duplicating any business logic. The Workspace backend path re-exports the existing FastAPI `app` object directly via `workspace_app.py` — a one-line file. The provider extension path (Phase 2) adds Fetcher classes inside `src/liquidity/openbb_ext/models/` that import calculators lazily (inside `aextract_data`) to prevent circular imports.

**Major components and responsibilities:**

| Component | Path | v5.0 Change |
|-----------|------|-------------|
| Collectors | `src/liquidity/collectors/` | No change |
| Calculators | `src/liquidity/calculators/` | No change |
| FastAPI API | `src/liquidity/api/` | Add CORS origin + `openapi_extra` on table endpoints |
| Workspace App | `src/liquidity/openbb_ext/workspace_app.py` | NEW — re-export `app` from `server.py` |
| Workspace Routes | `src/liquidity/api/workspace_routes.py` | NEW — `/workspace/*` metric + chart endpoints |
| OpenBB Ext (Phase 2) | `src/liquidity/openbb_ext/` | NEW — Fetcher adapters |
| Tests (ext) | `tests/openbb_ext/` | NEW — cassette tests + adapter unit tests |

**Docker Compose change:** Add a `workspace` service running `openbb-api --app src/liquidity/openbb_ext/workspace_app.py --host 0.0.0.0 --port 6900`. The existing `api` service on port 8000 remains unchanged.

See `.planning/research/architecture.md` for full dual-integration diagram and data model mapping table.

### Critical Pitfalls

1. **Wrong integration path (full provider extension as v5.0 scope)** — Use `openbb-api --app` as the primary path. Provider extension is Phase 2 optional. Detection signal: if you're writing `Fetcher` classes or `Provider()` instances before the Workspace backend is working, you're in the wrong order.

2. **CORS/SSL blocking Workspace connection** — Browsers (especially Safari/Brave) block HTTPS frontend calling HTTP backend. Use the OpenBB Desktop App (`localhost:1420`) for local development — it bypasses all SSL restrictions. For browser-based Workspace: `openbb-api --ssl_keyfile localhost.key --ssl_certfile localhost.crt`.

3. **OpenBB minor version breaks `obb.*` calls** — The project pins `openbb>=4.0.0`. Between v4.4.0 and v4.5.0, 7+ endpoints were renamed or removed. Pin to `openbb>=4.4.0,<4.7.0` immediately. Add integration tests that call real OpenBB endpoints (not mocked) so CI fails when endpoints change.

4. **`openbb-build` silent failure in Docker** — If provider extension path is chosen in Phase 2, `openbb-build` must run AFTER all `pip install` steps in Dockerfile, requires write access to `site-packages`. Silent failure: extension installed but `obb.liquidity.*` commands don't exist. Add `RUN openbb-build` to Dockerfile and `make build` to Makefile.

5. **`openapi_extra` auto-generation doesn't handle complex parameter types** — Nested Pydantic models and `List[str]` parameters generate incorrect widget controls. Keep widget endpoint params simple: `str` dates (ISO), `Literal` enums, `bool` flags. Use `openapi_extra` overrides explicitly rather than relying on inference for complex types.

---

## Risk Matrix (Probability x Impact)

| Risk | Probability | Impact | Priority | Mitigation |
|------|-------------|--------|----------|------------|
| CORS/SSL blocks Workspace connection | HIGH | HIGH | P0 | Use Desktop App locally; configure SSL for browser Workspace |
| OpenBB minor version breaks `obb.*` calls | MEDIUM | HIGH | P1 | Pin `openbb>=4.4.0,<4.7.0`; add integration tests |
| Choosing full provider extension path prematurely | MEDIUM | HIGH | P1 | Follow phase order: Workspace backend first, provider extension second |
| `openbb-build` silently fails in Docker (Phase 2) | LOW | MEDIUM | P2 | Only relevant if provider extension pursued; add to Dockerfile post-install |
| Entry point naming breaks provider discovery (Phase 2) | LOW | MEDIUM | P2 | Use `[project.entry-points]` PEP 517 syntax; verify with `obb.coverage.providers` |
| `PackageBuilder` bugs with Python 3.12 + uv (Phase 2) | LOW | MEDIUM | P2 | Issue #7113 open; monitor OpenBB releases; test before committing to provider path |
| Pydantic v2 breaking changes in custom Data models | LOW | LOW | P3 | Use v2 patterns from start; avoid `.json()`, `from_orm()`, `GenericModel` |
| `widgets.json` auto-generation mishandles complex params | LOW | LOW | P3 | Keep widget endpoint params simple; override with explicit `openapi_extra` |
| GET-only widget limitation | NONE | NONE | — | All existing endpoints are GET; no action needed |
| WebSocket unavailable for standard widgets | NONE | NONE | — | Daily/weekly macro data; polling is sufficient |
| OpenBB Hub retirement | NONE | NONE | — | Already using env vars — correct approach |

---

## Implications for Roadmap

### Suggested Phase Structure for v5.0

The research supports a 3-phase structure within v5.0, ordered by dependency and risk:

#### Phase 1: Foundation and Workspace Backend

**Rationale:** This is the entire v5.0 deliverable. It requires no new packages beyond `openbb-platform-api`, no entry point registration, and no `openbb-build`. It proves the integration works before any additional complexity is added.

**Delivers:**
- `openbb-platform-api` added to `pyproject.toml`
- CORS updated in `server.py` (add `https://pro.openbb.co`, `http://localhost:1420`)
- `workspace_app.py` created (one-line re-export of existing `app`)
- `workspace_routes.py` with `/workspace/*` metric + chart endpoints
- `openapi_extra` annotations on table endpoints
- Docker Compose `workspace` service on port 6900
- Self-signed SSL cert (optional, for browser-based Workspace)
- All 14 existing endpoints available as Workspace widgets
- Integration test: `TestClient` confirms `/widgets.json` is served and `/liquidity/net` responds

**Pitfalls addressed:** CORS, SSL, GET-only limitation (pre-confirmed as non-issue), widget parameter complexity.

**Research flag:** Standard pattern — no additional research needed. `openbb-api --app` is well-documented with code examples in all 4 research files.

#### Phase 2: Widget Polish and Optimization

**Rationale:** Once the baseline integration works, optimize widget metadata, refresh intervals, and column definitions for the best UX in OpenBB Workspace.

**Delivers:**
- `refetchInterval` per widget type (FRED daily: 4h, regime/stress: 15m, BIS quarterly: disabled)
- `staleTime` aligned to data update frequencies
- `data.table.columnsDefs` with `formatterFn: "int"`, `renderFn: "greenRed"` for delta columns
- Dynamic date defaults in widget params (`$currentDate-2y`)
- `apps.json` layout template (optional — pre-configured dashboard layout)
- Optional `X-API-KEY` header middleware

**Pitfalls addressed:** `openapi_extra` parameter type limitations (simple params only).

**Research flag:** Standard pattern — widget config field reference is fully documented in `features-api.md`.

#### Phase 3 (Optional): Native Provider Extension

**Rationale:** Only pursue after Phase 1 and Phase 2 are stable. Adds `obb.liquidity.*` Python SDK access for potential NautilusTrader integration and future AI agent tooling. Not required for Workspace widget delivery.

**Delivers:**
- `src/liquidity/openbb_ext/` scaffold
- `NetLiquidityFetcher`, `GlobalLiquidityFetcher`, `StealthQEFetcher` (thin adapters over calculators)
- `pyproject.toml` entry point: `[project.entry-points."openbb_provider_extension"]`
- `openbb-build` added to Makefile and Dockerfile
- vcrpy cassette tests for each Fetcher
- Verification: `obb.coverage.providers` shows `liquidity`; `obb.liquidity.net()` returns data

**Pitfalls addressed:** Circular imports (lazy imports in `aextract_data`), `credentials=["fred_api_key"]` correct syntax, `[project.entry-points]` PEP 517 syntax, `openbb-build` Docker placement.

**Research flag:** Needs verification of Issue #7113 (`PackageBuilder` + Python 3.12 + uv) before committing. If open and unresolved, defer to v6.0.

### Phase Ordering Rationale

- Phase 1 before Phase 2: Workspace backend must work end-to-end before optimizing widget metadata.
- Phase 1 before Phase 3: Provider extension adds no Workspace-visible value if the backend is not already connected.
- Phase 3 is optional: NautilusTrader currently consumes the REST API directly. The trigger for Phase 3 is explicit demand for `obb.liquidity.*` Python SDK access (e.g., NautilusTrader strategy code wanting `obb.liquidity.net()` instead of `httpx.get("/liquidity/net")`).

### Research Flags

**No additional research needed:**
- Phase 1 (Workspace Backend): Fully documented. Code examples exist in all 4 research files.
- Phase 2 (Widget Polish): `widgets.json` field reference is complete in `features-api.md`.

**Verify before executing:**
- Phase 3 (Provider Extension): Check Issue #7113 status (PackageBuilder + Python 3.12 + uv). If open and affecting this environment, defer Phase 3.
- OpenBB version pin: Verify current installed version against `<4.7.0` ceiling before pinning.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (openbb-platform-api, `--app` flag) | HIGH | Verified via official docs, PR #7016, PyPI v1.3.0 confirmed |
| Widget configuration (`openapi_extra`, widget types) | HIGH | Official docs + complete field reference; `widgets.json` spec confirmed |
| Architecture (monorepo subfolder, one-way dependency) | HIGH | Official docs + community pattern consensus |
| Workspace backend path (Phase 1 + 2) | HIGH | Multiple official sources, production examples on GitHub |
| Provider extension path (Phase 3) | MEDIUM | Official docs HIGH; uv-specific issues MEDIUM (Issue #7113 open) |
| Version pinning strategy | HIGH | Official release notes confirm specific endpoint changes by version |
| CORS/SSL requirements | HIGH | Explicitly documented in OpenBB FAQs |
| `openbb-build` requirement and failure modes | HIGH | Multiple official sources; confirmed Docker implications |
| Performance overhead of Pydantic v2 in TET pipeline | LOW | No benchmark data found; assumption: negligible for macro data volumes |

**Overall confidence:** HIGH for Phase 1 and Phase 2. MEDIUM for Phase 3 (provider extension) due to open uv compatibility bug.

### Open Questions for Resolution During Planning

1. **Is Issue #7113 (`PackageBuilder` + Python 3.12 + uv) resolved?** Check `https://github.com/OpenBB-finance/OpenBB/issues/7113` before committing to Phase 3. If open, Phase 3 becomes a v6.0 item.

2. **Current OpenBB version installed.** Run `uv run python -c "from openbb import obb; print(obb.__version__)"` to confirm. If < 4.4.0, upgrade before pinning ceiling.

3. **Does NautilusTrader integration (API-05 requirement) need `obb.liquidity.*` SDK access or is REST sufficient?** Answer determines whether Phase 3 is urgent or deferred.

4. **OpenBB Desktop App availability.** Confirm whether `localhost:1420` (Desktop App) or browser-based `pro.openbb.co` is the target Workspace surface. This determines whether SSL self-signed cert work is required in Phase 1 or can be deferred.

5. **`widgets.json` auto-generation vs manual for existing endpoint response shapes.** Validate that `NetLiquidityResponse` Pydantic model generates usable column defs automatically, or whether explicit `columnsDefs` overrides are needed for all 14 endpoints. This affects Phase 2 scope.

---

## Gaps to Address

- **No benchmark data on Pydantic v2 TET overhead** for large time series (5+ years daily CB data). Assumption: negligible at current data volumes. Monitor if Phase 3 provider extension is pursued for historical bulk queries.
- **`openbb-cookiecutter` not migrated to uv** (Issue #14 open). Cookiecutter is reference-only — cherry-pick `pyproject.toml` template, don't run it against the live project.
- **Minor version ceiling (`<4.7.0`)** needs revisiting when OpenBB 4.7.0 is released. Set a calendar reminder or add a Dependabot alert.

---

## Sources

### Primary (HIGH confidence)
- OpenBB Architecture Docs — TET pipeline, provider extension structure: `https://docs.openbb.co/odp/python/developer/architecture_overview`
- OpenBB Workspace Data Integration: `https://docs.openbb.co/workspace/developers/data-integration`
- openbb-platform-api PyPI v1.3.0: `https://pypi.org/project/openbb-platform-api/`
- widgets.json Reference: `https://docs.openbb.co/workspace/developers/json-specs/widgets-json-reference`
- OpenBB v4.4.0 Release Notes: `https://github.com/OpenBB-finance/OpenBB/releases/tag/v4.4.0`
- OpenBB v4.5.0 Release Notes: `https://github.com/OpenBB-finance/OpenBB/releases/tag/v4.5.0`
- OpenBB PR #7016 (Custom FastAPI instance): `https://github.com/OpenBB-finance/OpenBB/pull/7016`
- OpenBB Workspace Quickstart: `https://docs.openbb.co/odp/python/quickstart/workspace`
- OpenBB Workspace FAQs (CORS/SSL): `https://docs.openbb.co/workspace/getting-started/faqs`
- OpenBB Stale Time Docs: `https://docs.openbb.co/workspace/developers/widget-configuration/stale-time`
- OpenBB Contributor Tests Guide (vcrpy): `https://docs.openbb.co/odp/python/developer/how-to/tests`
- Alpha Vantage provider pyproject.toml reference: `https://github.com/OpenBB-finance/OpenBB/blob/develop/openbb_platform/providers/alpha_vantage/pyproject.toml`

### Secondary (MEDIUM confidence)
- openbb-cookiecutter Issue #8 (naming confusion): `https://github.com/OpenBB-finance/openbb-cookiecutter/issues/8`
- openbb-cookiecutter Issue #14 (uv migration): `https://github.com/OpenBB-finance/openbb-cookiecutter/issues/14`
- OpenBB Issue #7113 (PackageBuilder + Python 3.12 + uv): `https://github.com/OpenBB-finance/OpenBB/issues/7113`
- OpenBB PR #7066 (PackageBuilder import fix): `https://github.com/OpenBB-finance/OpenBB/pull/7066`
- Community example — cap_comp_openbb_example (wshobson): `https://github.com/wshobson/cap_comp_openbb_example`
- OpenBB backends-for-openbb examples: `https://github.com/OpenBB-finance/backends-for-openbb`

### Tertiary (LOW confidence)
- Pydantic v2 serialization overhead for TET pipeline: no benchmark source found; runtime validation required.

---

*Research completed: 2026-02-21*
*Synthesized: 2026-02-21*
*Research files: stack-tech.md, features-api.md, architecture.md, pitfalls-risks.md*
*Ready for roadmap: yes*
