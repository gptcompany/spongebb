# Domain Pitfalls: OpenBB Platform Integration (v5.0)

**Project:** Global Liquidity Monitor
**Domain:** OpenBB Platform extension development + Workspace custom backend
**Researched:** 2026-02-21
**Confidence:** MEDIUM (official docs + GitHub issues + release notes; no dedicated benchmark data found)

---

## Executive Summary

The v5.0 milestone (OpenBB Platform Integration) has three distinct risk profiles depending on which integration path is chosen:

1. **Full provider extension** (register new `openbb_provider_extension`): HIGH complexity, HIGH maintenance burden, moderate stability risk from minor-version churn. Not recommended for this project.
2. **FastAPI custom backend via `openbb-api --app`**: LOW complexity, LOW maintenance, the simplest path to OpenBB Workspace. This is what the project already has (FastAPI on port 8000) — adding CORS headers and `widgets.json` is literally the only required work.
3. **Full `openbb` as a data library** (using `obb.economy.*`, etc.): MEDIUM risk from version churn. The project already depends on `openbb>=4.0.0` — version pinning is the main risk.

The critical finding: **The project does not need a provider extension at all.** The existing FastAPI server can become an OpenBB Workspace backend with minimal changes. This path avoids all provider extension pitfalls.

---

## Critical Pitfalls

### Pitfall 1: Choosing the Full Provider Extension Path When It Is Not Needed

**What goes wrong:** Developer assumes "OpenBB integration" means writing a formal `openbb_provider_extension` — creates a package with `pyproject.toml` entry points, `Fetcher` classes, and `Provider()` instances. This is 10x more work than needed and ties the codebase to OpenBB's internal data model conventions.

**Why it happens:** The documentation prominently features the cookiecutter/provider pattern. It's easy to assume this is the required approach.

**Consequences:**
- Full provider extensions must be reinstalled via `pip install -e .` and then `openbb-build` must be run after every change to add/remove entries from `fetcher_dict`.
- Provider extensions "do not map to any specific endpoint by themselves" — they only work when referenced by router functions in the core, which requires additional router extension work.
- Maintenance burden every time OpenBB releases a minor version.

**Prevention:** Use the `openbb-api --app /path/to/server.py` approach instead. The existing `liquidity/api/server.py` FastAPI instance just needs CORS headers for `https://pro.openbb.co`, and `openbb-platform-api` auto-generates `widgets.json` from the OpenAPI spec. Zero new packages, zero entry points, zero `openbb-build` calls.

**Detection:** If you find yourself writing a `Fetcher` class or a `Provider()` instance for this project's data, you're on the wrong path.

**Confidence:** HIGH — confirmed in official docs (openbb-api --app pattern), PR #7016.

Sources:
- https://docs.openbb.co/python/quickstart/workspace
- https://github.com/OpenBB-finance/OpenBB/pull/7016

---

### Pitfall 2: OpenBB Minor Version Breaking Changes Break Data Consumption Code

**What goes wrong:** The project pins `openbb>=4.0.0` (current pyproject.toml). Between minor versions, endpoints are renamed, deprecated, then removed. Code using `obb.fixedincome.sofr` broke in v4.5.0 (→ `obb.fixedincome.rate.sofr`). Code using `obb.economy.short_term_interest_rate` broke in v4.5.0 (→ `obb.economy.interest_rates`). `obb.etf.holdings_date` was removed entirely.

**Why it happens:** OpenBB deprecates endpoints across one or two minor versions, then removes them. The announcement window is real but easy to miss if you're not watching release notes closely.

**Consequences:**
- Data collection fails silently (exception at runtime, not at import time)
- If this project uses `obb.fixedincome.*` for rate data (SOFR, yield curves, spreads), those calls could break on upgrade

**Known removals by version:**
| Version | Removed | Replacement |
|---------|---------|-------------|
| v4.4.0 | `obb.fixedincome.government.us_yield_curve` | `obb.fixedincome.government.yield_curve` |
| v4.4.0 | `obb.fixedincome.government.eu_yield_curve` | `obb.fixedincome.government.yield_curve` |
| v4.5.0 | `obb.economy.short_term_interest_rate` | `obb.economy.interest_rates` |
| v4.5.0 | `obb.economy.long_term_interest_rate` | `obb.economy.interest_rates` |
| v4.5.0 | `obb.fixedincome.sofr` | `obb.fixedincome.rate.sofr` |
| v4.5.0 | `obb.fixedincome.corporate.ice_bofa` | `obb.fixedincome.bond_indices` |
| v4.5.0 | `obb.etf.holdings_date` | removed (no replacement) |
| v4.5.0 | `CompanyOverview` standard model | replaced by `EquityProfile` |

**Prevention:**
- Pin to a specific minor version: `openbb>=4.4.0,<4.6.0` rather than `openbb>=4.0.0`
- Add integration tests that call actual OpenBB endpoints (not mocked) so CI fails if an endpoint is renamed
- Watch the GitHub releases page: https://github.com/OpenBB-finance/OpenBB/releases

**Detection:** `AttributeError: 'App' object has no attribute 'X'` at runtime. Issue #6684 shows this exact pattern.

**Confidence:** HIGH — documented in official release notes for v4.4.0 and v4.5.0.

---

### Pitfall 3: `openbb-build` Must Run After Any Extension Change in Containerized Environments

**What goes wrong:** If the project ever installs an OpenBB extension (provider or router) inside the Docker image and does NOT run `openbb-build` before starting the app, the Python interface static files are stale. The extension appears installed but its commands do not appear on the `obb` object. Silent failure — no exception thrown.

**Why it happens:** OpenBB compiles static Python interface files post-installation. This is not standard Python packaging behavior — developers expect `pip install -e .` to be sufficient.

**Key constraint:** The build script requires **write access to the `site-packages` folder** at container build time. Read-only filesystem mounts will break this.

**Consequences:**
- `obb.my_extension.my_command` raises `AttributeError` even though the package is installed
- Debugging is non-obvious; error looks like the extension was never installed

**Prevention:**
- Add `RUN openbb-build` to the Dockerfile AFTER all extension installs, not before
- Do NOT install extensions into a read-only container layer
- For the simpler `openbb-api --app` path (recommended), this pitfall does not apply at all

**Detection:** `AttributeError: 'App' object has no attribute 'X'` despite confirmed `pip install`. Run `openbb-build` manually and retry.

**Confidence:** HIGH — explicitly documented in official OpenBB architecture docs.

---

### Pitfall 4: CORS and SSL/HTTPS Requirements Are Non-Trivial for Containerized Local Backends

**What goes wrong:** Adding CORS for `https://pro.openbb.co` is easy. But OpenBB Workspace connects from `https://pro.openbb.co` (HTTPS) to your local HTTP server. Browsers (Chrome: usually fine, Safari/Brave: always fails) block mixed content — HTTPS frontend calling HTTP backend.

**Specific failure modes:**
- Chrome blocks HTTP backends for Safari and Brave users
- OpenBB Workspace Pro runs at `https://pro.openbb.co` — it cannot make unsecured HTTP requests to `http://localhost:8000` in some browsers
- Self-signed certificates must be manually trusted in the OS trust store (not just the browser)
- Docker containers with minimal base images (Alpine/Debian-slim) do not include the self-signed CA in their trust store, causing cascading SSL verification failures if the container itself makes HTTPS calls

**If using the OpenBB Desktop App:** This bypass HTTP/HTTPS restrictions. This is the recommended path for local development — it avoids the SSL ceremony entirely.

**For browser-based Workspace Pro:** Must configure SSL:
```bash
openssl req -x509 -days 3650 -out localhost.crt -keyout localhost.key \
  -newkey rsa:4096 -nodes -sha256 \
  -subj '/CN=localhost' -extensions EXT -config <( \
  printf "[dn]\nCN=localhost\n[req]\ndistinguished_name = dn\n[EXT]\nsubjectAltName=DNS:localhost\nkeyUsage=digitalSignature\nextendedKeyUsage=serverAuth")

openbb-api --app server.py --ssl_keyfile localhost.key --ssl_certfile localhost.crt
```

**Consequences:** Workspace widgets load but immediately fail with network errors. Error is visible in browser DevTools but not in any OpenBB logs.

**Prevention:**
- Use the OpenBB Desktop App for local development (bypasses all CORS/SSL restrictions)
- For browser-based Workspace: generate self-signed cert and add to system trust store before connecting
- Expose the FastAPI server over HTTPS from the Docker container if Workspace integration is required from browsers other than Chrome

**Confidence:** HIGH — explicitly documented in OpenBB FAQs and Workspace docs.

---

## Moderate Pitfalls

### Pitfall 5: Provider Extension Entry Point Naming Conventions Are Fragile

**Applies if:** Full provider extension path is chosen (not recommended).

**What goes wrong:** Three common naming mistakes that silently prevent extension discovery:

1. **Wrong group name:** The group key must be exactly `openbb_provider_extension`, `openbb_core_extension`, or `openbb_obbject_extension`. Any typo prevents discovery.

2. **Mismatched Python variable name:** The entry point value in `pyproject.toml` must match the actual variable name in the module:
   ```toml
   [tool.poetry.plugins."openbb_provider_extension"]
   my_provider = "openbb_my_provider:my_provider"   # must match variable name
   ```
   If the variable is named `my_provider_instance` instead of `my_provider`, it fails with `AttributeError`.

3. **Stale metadata after editable install:** After changing `pyproject.toml`, the metadata is not updated automatically. Must re-run `pip install -e .` to regenerate entry point metadata. Running `openbb-build` alone is insufficient if the entry point itself changed.

4. **Poetry vs PEP 517 table syntax:** OpenBB docs use `[tool.poetry.plugins."group"]`. Generic PEP 517 syntax `[project.entry-points."group"]` may not be discovered depending on the build backend.

**Issue #8 in openbb-cookiecutter:** The template itself had confusing `provider` naming that led to `module has no attribute 'provider'` errors. Labeled "invalid" (user error) but the confusion is real.

**Confidence:** HIGH — documented in multiple official sources and GitHub issue #8.

Sources:
- https://github.com/OpenBB-finance/openbb-cookiecutter/issues/8
- https://github.com/OpenBB-finance/openbb-cookiecutter/issues/10

---

### Pitfall 6: OpenBB Workspace Widgets Support Only GET (with Caveats)

**What goes wrong:** Widget endpoints in `widgets.json` are called via GET requests only. The project's FastAPI has POST endpoints for data submission. These cannot be directly mapped to Workspace widgets using the standard `widgets.json` mechanism.

**Current status (Feb 2026):** PR #7055 (merged March 2025) introduced a GET/POST dual-route pattern for form widgets. POST support is being added but is not universally available across widget types yet.

**Impact on this project:** All liquidity data endpoints are already GET-based (`GET /liquidity/net`, `GET /liquidity/global`, etc.) — this pitfall does not apply to the current API design. However, if alert configuration or filter settings are exposed as POST endpoints, they cannot be widgets.

**Workaround:** Create GET wrapper endpoints that proxy to internal POST handlers. The query parameters from the widget become the POST body.

**Confidence:** MEDIUM — confirmed in quickstart docs ("only GET methods supported at this time"), PR #7055 shows evolution.

---

### Pitfall 7: WebSocket / Real-Time Push Is Not Available for Standard Widgets

**What goes wrong:** Developers expect Workspace widgets to support WebSocket connections for live data push, similar to a Bloomberg terminal. This is not how Workspace works for most widget types.

**Reality:**
- WebSocket (`wsEndpoint`) is supported ONLY for the `live_grid` widget type
- All other widget types (table, chart, metric, markdown, newsfeed) use HTTP polling only
- The `staleTime` mechanism (default: 5 minutes) makes the refresh button turn orange when data is stale — the user must manually refresh or configure `refetchInterval`
- Minimum `refetchInterval` is 1000ms (1 second) — so "near real-time" is technically possible via polling but is not efficient
- HTML widgets block all JavaScript execution — no client-side WebSocket code

**Impact on this project:** The liquidity monitor tracks daily/weekly data. Polling with a 5-minute stale time is perfectly adequate. Real-time push is out of scope per REQUIREMENTS.md ("Real-time intraday updates: Daily/weekly sufficient for macro analysis"). This pitfall does not block the project but must be understood when setting expectations.

**Confidence:** HIGH — directly documented in `widgets.json` reference and Stale Time documentation.

---

### Pitfall 8: Pydantic v2 Serialization Overhead and Breaking Changes in Data Models

**What goes wrong:** The OpenBB Platform uses Pydantic v2 for all data models. If the project defines custom `Data` subclasses for OpenBB integration, several Pydantic v1 patterns break:

| V1 Pattern (broken) | V2 Replacement |
|---------------------|----------------|
| `.json()` | `model_dump_json()` |
| `parse_raw()` | `model_validate_json()` |
| `from_orm()` | `model_validate()` + `from_attributes=True` |
| `GenericModel` | `BaseModel + Generic[T]` |
| `__get_validators__` | `__get_pydantic_core_schema__` |
| `class Config:` | `model_config = ConfigDict(...)` |

**Performance consideration:** Pydantic v2 (Rust-based) is significantly faster than v1 for serialization. However, for the provider extension ETL pipeline, every row of data goes through Pydantic validation. For large datasets (5+ years of daily CB data), this adds measurable serialization overhead compared to raw pandas.

**No benchmark data found** for the specific overhead of OpenBB's provider ETL vs direct pandas. The "no overhead" assumption cannot be confirmed with current evidence.

**Prevention:**
- If building `Data` subclasses, use Pydantic v2 patterns from day one
- For high-volume data (BIS statistics, TIC data), consider the `no_validate=True` option on router commands (introduced in v4.4.0) to skip output validation when performance matters
- Use `OBBject.to_df()` rather than manual deserialization — it bypasses the dict-to-dataframe overhead

**Confidence:** MEDIUM — Pydantic v2 changes are HIGH confidence; performance overhead is LOW confidence (no benchmark data found).

---

### Pitfall 9: OpenBB Hub Retirement Breaks Credential Management

**What goes wrong:** OpenBB Hub (hub.openbb.co) is being retired. The `obb.account` module will be removed in a future version. Any code using `obb.account.login()` or Hub-based credential management will break.

**Current state (Feb 2026):** Hub retirement announced but not yet completed. The Account module still works but shows deprecation warnings.

**Impact on this project:** The project sets credentials via environment variables (`OPENBB_FRED_API_KEY`, `OPENBB_EIA_API_KEY` — visible in docker-compose.yml). This is already the correct pattern for the new approach. No migration needed.

**Prevention:**
- Set all OpenBB API keys via environment variables (prefix `OPENBB_`) or `~/.openbb/user_settings.json`
- Never use `obb.account.login()` in new code
- The environment variable approach already used in this project is the right one

**Confidence:** HIGH — explicitly documented in v4.5.0 release notes.

---

## Minor Pitfalls

### Pitfall 10: `openbb-cookiecutter` Still Requires Manual Tweaks

**Applies only if the full provider extension path is chosen.**

Official docs explicitly warn: "The cookiecutter tool will get you most of the way there, but it still requires some tweaks to the file names and initializations."

Issue #14 (openbb-cookiecutter): Cookiecutter has not been migrated to `uv` — it still uses `pip`/`poetry`. If the project uses `uv` (which it does, per CLAUDE.md), there is a workflow mismatch. The generated project will have `pyproject.toml` with Poetry-style tooling that needs conversion.

Issue #11 (openbb-cookiecutter): Open since February 2024 — `cruft` integration for template updates was never implemented. If OpenBB releases a new cookiecutter template version, there is no automated way to apply the update to an existing extension.

**Confidence:** HIGH — documented in issues #11 and #14 of openbb-cookiecutter.

---

### Pitfall 11: `PackageBuilder` Has Known Import Discovery Bugs

**What goes wrong:** The `PackageBuilder` (the internal tool behind `openbb-build`) has had multiple bugs around import discovery:

- PR #7066 (Jan 2025): `PackageBuilder` incorrectly imported `Dict` and `List` from `typing`, causing `ImportError` when Ruff reformatted the generated code. The generated static files could contain invalid Python after a code style check.
- Issue #7113 (May 2025): `ImportError: cannot import name 'EquityInfo' from 'typing'` in Python 3.12 environments with `uv` virtual environments. Open at time of research.
- PR #6477: Custom extensions could not add charting views without modifying `openbb-charting` source code directly.

**Impact:** These bugs affect developers extending OpenBB, not users of the existing providers. However, if the project creates a router extension with custom endpoints, it may trigger similar `PackageBuilder` edge cases.

**Prevention:** Use the `openbb-api --app` path. This entirely bypasses `PackageBuilder` since `widgets.json` is auto-generated from the FastAPI OpenAPI spec.

**Confidence:** MEDIUM — specific bugs are HIGH confidence (confirmed GitHub issues), frequency of occurrence is LOW confidence.

---

### Pitfall 12: `widgets.json` Auto-generation Does Not Handle All Parameter Types

**What goes wrong:** The `openbb-api` tool auto-generates `widgets.json` from the FastAPI OpenAPI spec. This works well for simple parameter types (str, int, float, Literal, Optional). Complex types fail silently or generate incorrect widget controls:

- Nested Pydantic models as parameters are not supported — they become a single untyped text input
- `datetime` parameters must be explicitly annotated with `Query(description="...")` to get date pickers
- `List[str]` parameters generate a single text field, not a multi-select — users must enter comma-separated values manually

**Impact on this project:** The existing `/liquidity/net`, `/liquidity/global`, `/regime/current` endpoints use simple date range parameters. This pitfall applies only to more complex filter endpoints.

**Prevention:** Keep widget endpoint parameters simple: dates as `str` (ISO format), enums as `Literal`, flags as `bool`. Use `openapi_extra` in the router decorator to override auto-generated widget configuration when needed.

**Confidence:** MEDIUM — confirmed through official docs behavior descriptions; no explicit bug tracker entry found.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| OpenBB as data library | Endpoint name changes in future minor versions | Pin `openbb>=4.4.0,<4.6.0` in pyproject.toml |
| Workspace backend setup | CORS configuration for `pro.openbb.co` | Add `CORSMiddleware` with explicit origin; use Desktop App for local dev |
| Workspace backend setup | GET-only widget limitation | Audit existing endpoints — all are GET; no action needed |
| Provider extension (if pursued) | Entry point naming, `openbb-build` ritual | Avoid this path; use `openbb-api --app` instead |
| Docker deployment | `openbb-build` requires write access to site-packages | Only applies if using provider extensions; irrelevant for `--app` path |
| SSL for Workspace | Browser mixed-content blocking | Use Desktop App locally; generate self-signed cert for browser Workspace |
| Data model subclasses | Pydantic v2 breaking changes | Use v2 patterns from start; avoid `from_orm`, `.json()`, `GenericModel` |
| OpenBB version upgrade | Breaking endpoint renames | Pin minor version; add integration tests that call real endpoints |

---

## Alternative Approach: Recommended Path

Given the project constraints (production system, existing FastAPI on port 8000, Docker Compose, stability requirement), the correct integration path for v5.0 is:

**Path: FastAPI custom backend via `openbb-api --app`**

This requires:
1. Add `CORSMiddleware` to the existing FastAPI app allowing `https://pro.openbb.co`
2. Install `openbb-platform-api` package (already part of `openbb>=4.0.0`)
3. Launch via `openbb-api --app /path/to/server.py` (or keep using uvicorn directly for the existing service + serve `widgets.json` and `/api/v1/` manually)
4. Connect in OpenBB Workspace via Data Connectors → Add Data

This path:
- Requires no new Python packages
- Requires no entry point registration
- Requires no `openbb-build`
- Does not touch existing functionality
- Is stable across OpenBB minor versions (it's just a REST API)

The only maintenance burden: keep `widgets.json` updated when adding new endpoints. This can be automated by running `openbb-api --editable` in development.

**Confidence in this recommendation:** HIGH — officially documented and confirmed via multiple sources.

---

## Community Examples: What Works in Production

Real-world custom backends found on GitHub (2024-2025):

1. **cap_comp_openbb_example** (wshobson): OpenBB Terminal Pro Custom Backend Integration — FastAPI-based, updated into 2025/2026. Demonstrates the `backends-for-openbb` pattern.

2. **Databento-CME extension** for OpenBB ODP: Market data provider extension using the full `openbb_provider_extension` pattern. Shows the complexity of the formal extension path vs the simpler backend approach.

3. **ORATS options provider extension**: Community extension for implied volatility data. Required manual tweaks beyond what the cookiecutter generated. Demonstrates the entry point naming issues documented in Issue #8.

**Key lesson from community examples:** Production-quality examples that work reliably all use either (a) the simple FastAPI backend approach or (b) are maintained by teams with deep OpenBB internals knowledge. The cookiecutter/provider path is doable but has a steep learning curve and ongoing maintenance cost.

---

## Risk Register Summary

| Risk | Severity | Probability | Mitigation |
|------|----------|-------------|------------|
| Choosing wrong integration path (full provider extension) | HIGH | MEDIUM | Use `openbb-api --app` path |
| OpenBB minor version breaks `obb.*` calls | HIGH | MEDIUM | Pin minor version; integration tests |
| CORS/SSL blocks Workspace connection | HIGH | HIGH | Use Desktop App locally; configure SSL for browser Workspace |
| `openbb-build` silently fails in Docker | MEDIUM | LOW | Only relevant if using provider extensions |
| Entry point naming breaks provider discovery | MEDIUM | LOW | Only relevant if using provider extensions |
| Pydantic v2 breaking changes in custom models | MEDIUM | LOW | Use v2 patterns; avoid deprecated methods |
| GET-only widget limitation | LOW | LOW | All existing endpoints are GET; no action needed |
| WebSocket unavailable for standard widgets | LOW | NONE | Project uses daily/weekly data; polling is sufficient |
| OpenBB Hub retirement breaks credentials | LOW | NONE | Already using env vars — correct approach |

---

## Sources

- [OpenBB GitHub Releases](https://github.com/OpenBB-finance/OpenBB/releases) — MEDIUM confidence (official)
- [OpenBB v4.5.0 Release Notes](https://github.com/OpenBB-finance/OpenBB/releases/tag/v4.5.0) — HIGH confidence (official)
- [OpenBB v4.4.0 Release Notes](https://github.com/OpenBB-finance/OpenBB/releases/tag/v4.4.0) — HIGH confidence (official)
- [OpenBB Workspace Data Integration Docs](https://docs.openbb.co/workspace/developers/data-integration) — HIGH confidence (official)
- [OpenBB Workspace Custom Backend Quickstart](https://docs.openbb.co/odp/python/quickstart/workspace) — HIGH confidence (official)
- [OpenBB widgets.json Reference](https://docs.openbb.co/workspace/developers/json-specs/widgets-json-reference) — HIGH confidence (official)
- [OpenBB Workspace Stale Time Docs](https://docs.openbb.co/workspace/developers/widget-configuration/stale-time) — HIGH confidence (official)
- [OpenBB Workspace FAQs](https://docs.openbb.co/workspace/getting-started/faqs) — HIGH confidence (official)
- [OpenBB Provider Extension Docs](https://docs.openbb.co/odp/python/developer/extension_types/provider) — HIGH confidence (official)
- [openbb-cookiecutter Issue #8: Provider naming confusion](https://github.com/OpenBB-finance/openbb-cookiecutter/issues/8) — HIGH confidence (GitHub)
- [openbb-cookiecutter Issue #10: API key setup not working](https://github.com/OpenBB-finance/openbb-cookiecutter/issues/10) — HIGH confidence (GitHub)
- [openbb-cookiecutter Issue #14: Migrate to uv](https://github.com/OpenBB-finance/openbb-cookiecutter/issues/14) — HIGH confidence (GitHub)
- [OpenBB Issue #7113: ImportError with Python 3.12 + uv](https://github.com/OpenBB-finance/OpenBB/issues/7113) — HIGH confidence (GitHub)
- [OpenBB Issue #6684: AttributeError commodity extension](https://github.com/OpenBB-finance/OpenBB/issues/6684) — HIGH confidence (GitHub)
- [OpenBB PR #7066: PackageBuilder import fix](https://github.com/OpenBB-finance/OpenBB/pull/7066) — HIGH confidence (GitHub)
- [OpenBB PR #7055: POST params discovery for Workspace forms](https://github.com/OpenBB-finance/OpenBB/pull/7055) — HIGH confidence (GitHub)
- [OpenBB PR #7016: Allow custom FastAPI instance to openbb-api](https://github.com/OpenBB-finance/OpenBB/pull/7016) — HIGH confidence (GitHub)
- [OpenBB Architecture Overview](https://docs.openbb.co/odp/python/developer/architecture_overview) — HIGH confidence (official)
- [OpenBB backends-for-openbb GitHub](https://github.com/OpenBB-finance/backends-for-openbb) — HIGH confidence (official)
- [OpenBB Platform blog: Architecture exploration](https://openbb.co/blog/exploring-the-architecture-behind-the-openbb-platform) — MEDIUM confidence (official blog)
- [cap_comp_openbb_example (wshobson)](https://github.com/wshobson/cap_comp_openbb_example) — MEDIUM confidence (community)
- [openbb-platform topics on GitHub](https://github.com/topics/openbb-platform) — MEDIUM confidence (community)

---

*Research completed: 2026-02-21*
*Researcher: GSD Phase 6 Research Agent*
