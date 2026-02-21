# Phase 23: Workspace Backend Integration — Context

**Created:** 2026-02-21
**Phase Goal:** Expose the existing FastAPI as an OpenBB Workspace custom backend via `openbb-api --app`

## Decisions

### Workspace Target
- **Desktop App** (`localhost:1420`) + **Browser** (`pro.openbb.co`) + **Remote** (custom subdomain)
- CORS origins: `https://pro.openbb.co`, `http://localhost:1420`, `https://liquidity.princyx.xyz`

### Remote Access & Security
- Cloudflare Tunnel + Cloudflare Access (Google OAuth)
- Subdomain: `liquidity.princyx.xyz` (or similar, to be configured in CF)
- Allowlist: gptprojectmanager@gmail.com, gptcoderassistant@gmail.com
- **Defense in depth**: CF Access handles primary auth at edge. Additionally, verify `Cf-Access-Authenticated-User-Email` header in middleware when `LIQUIDITY_CF_ACCESS_ENABLED=true` — prevents bypass if tunnel misconfigured or internal network compromised
- No X-API-KEY middleware — CF Access + header verification is sufficient

### Version Pinning
- Change `openbb>=4.0.0` to `openbb>=4.4.0,<4.7.0`
- `openbb-platform-api` currently at 1.2.3 — evaluate if upgrade to >=1.3.0 needed

### Docker — Single Enhanced Service
- **Single service approach**: The existing `liquidity-api` service is enhanced to include workspace routes. `openbb-api --app` wraps the same app object that already serves the existing 14 endpoints.
- New Docker service `liquidity-workspace` on port **6900** runs `openbb-api --app` pointing to `workspace_app.py`
- This is NOT two separate API services — it's the same FastAPI `app` with workspace routes added, launched via `openbb-api --app` which adds Workspace widget discovery (`/widgets.json`)
- Existing `liquidity-api` on port 8000 remains for direct REST API consumers (backward compat)

## Current State

### Installed Versions
- openbb: 4.6.0
- openbb-platform-api: 1.2.3
- openbb-core: 1.5.8
- Python: 3.11

### Existing Infrastructure
- FastAPI server: `src/liquidity/api/server.py` (14 endpoints)
- CORS: `allow_origins=["*"]` (permissive, needs tightening)
- Docker: Multi-stage Dockerfile, docker-compose.yml (19 services, 4 profiles)
- Makefile with build/test/deploy targets
- Dependency injection via `src/liquidity/api/deps.py`

### Endpoints to Expose as Widgets
| Router | Prefix | Endpoints | Widget Type |
|--------|--------|-----------|-------------|
| liquidity | /liquidity | /net, /global | metric + chart |
| regime | /regime | /current, /combined | metric (badge) |
| metrics | /metrics | /stealth-qe | metric |
| fx | /fx | /dxy, /pairs | table |
| stress | /stress | /indicators | table |
| correlations | /correlations | /, /matrix | table + chart |
| calendar | /calendar | /events | table |
| core | / | /, /health | (not exposed) |

### No Existing Code
- No `openbb_ext/` directory
- No `workspace_app.py`
- No `/workspace/*` routes
- Clean slate for Phase 23

## Architecture (from Research)

### Integration Path
- Primary: `openbb-api --app` (Workspace backend, wraps existing FastAPI)
- `/workspace/*` dedicated routes for metric + chart widgets (different response shape from existing REST endpoints)
- `openapi_extra` annotations on table endpoints (compatible shapes)
- `workspace_app.py` imports the existing `app`, registers workspace router, then re-exports the augmented app

### App Assembly Flow (clarified)
1. `server.py` creates FastAPI `app` with existing 14 endpoints
2. `workspace_routes.py` defines a new `workspace_router` (APIRouter with `/workspace` prefix)
3. `workspace_app.py` imports `app` from `server.py`, includes `workspace_router`, configures CORS origins, and exports `app` for `openbb-api --app`
4. `openbb-api --app workspace_app:app` launches the augmented app with Workspace widget discovery

### Response Shape Strategy
- **Table widgets** (existing endpoints): Flatten Pydantic responses to `list[dict]` format. OpenBB Workspace expects flat list of dictionaries for tabular data. Use `openapi_extra` with `widget_config` for column definitions.
- **Metric widgets** (new `/workspace/*`): Simple `{"value": N, "label": "...", "delta": D}` format
- **Chart widgets** (new `/workspace/*`): Plotly JSON via `.to_plotly_json()` — Workspace renders Plotly natively

### File Structure (new)
```
src/liquidity/
├── api/
│   ├── workspace_routes.py    # NEW — /workspace/* metric + chart endpoints
│   └── routers/ (unchanged)
└── openbb_ext/
    └── workspace_app.py       # NEW — imports app, adds workspace router, re-exports
```

## Constraints
- Zero duplication of business logic — workspace routes wrap existing calculators
- Existing API consumers (NautilusTrader) must not break
- GET-only widgets (all existing endpoints are GET)
- Daily/weekly macro data — polling sufficient, no WebSocket needed

## Research References
- `.planning/research/SUMMARY.md` — strategy + risk matrix
- `.planning/research/stack-tech.md` — TET pipeline, pyproject templates
- `.planning/research/features-api.md` — widget config reference
- `.planning/research/architecture.md` — package structure, adapter pattern
- `.planning/research/pitfalls-risks.md` — CORS/SSL, version churn
