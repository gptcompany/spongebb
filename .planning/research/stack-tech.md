# Research: OpenBB Platform Extension Technology Stack

**Project:** Global Liquidity Monitor — v5.0 OpenBB Platform Integration
**Focus:** STACK/TECH — OpenBB extension architecture, provider patterns, Workspace integration
**Researched:** 2026-02-21
**Overall confidence:** HIGH (verified against official docs, GitHub source, PyPI)

---

## Executive Summary

OpenBB 4.x uses a three-layer extension architecture: **Provider extensions** (data fetching), **Router extensions** (endpoint definition), and **OBBject extensions** (response enrichment). The project already uses OpenBB as a data consumer (`obb.economy.fred_series()`). The v5.0 milestone asks a different question: can the project's own FastAPI server be exposed _as_ an OpenBB Workspace backend, and optionally register custom provider commands callable via `obb.liquidity.*`?

The answer is yes on both counts, and the two paths are largely independent:

1. **Workspace integration** (low effort): Use `openbb-platform-api` to wrap the existing FastAPI in a Workspace-compatible backend. Zero new code required — just a CLI launch and `openapi_extra` annotations on existing routes.

2. **Custom provider extension** (moderate effort): Package the existing calculators as a `openbb_provider_extension` so commands are callable via `obb.liquidity.net_liquidity()`, `obb.liquidity.regime()` etc. Requires three classes per command: `QueryParams`, `Data`, `Fetcher`.

---

## 1. OpenBB Platform 4.x Architecture

### Component Hierarchy

```
openbb (meta-package)
├── openbb-core          # Router, OBBject, ProviderInterface, build system
├── openbb-economy       # Router extension: obb.economy.*
├── openbb-fixedincome   # Router extension: obb.fixedincome.*
├── openbb-fred          # Provider extension: fred Fetchers
├── openbb-yfinance      # Provider extension: yfinance Fetchers
└── ...your extension    # openbb-liquidity-provider
```

The Python interface and the REST API share the same core logic. Both read from the same installed provider registry. Running `openbb-build` after installing extensions regenerates static files so `obb.<namespace>.<command>()` resolves correctly.

### Three Extension Types

| Extension Type | Entry Point Group | Registers | Result |
|---------------|-------------------|-----------|--------|
| Provider | `openbb_provider_extension` | Fetcher classes | Data sources callable from any router |
| Router | `openbb_core_extension` | FastAPI `Router` with `@router.command` | New `obb.<namespace>.*` commands |
| OBBject | `openbb_obbject_extension` | Methods/properties on OBBject | Extended response handling |

For the liquidity project, the relevant types are **Provider** (to expose custom calculations) and optionally **Router** (to create `obb.liquidity.*` namespace).

---

## 2. The TET Pipeline (Transform-Extract-Transform)

OpenBB calls this "TET" not "ETL". The order matters: Transform-in → Extract → Transform-out.

All three stages live inside a single `Fetcher` class as static methods, making each stage independently testable.

```python
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.abstract.data import Data
from pydantic import Field
from datetime import date
from typing import Any


# Step 1: Define what the user passes in
class NetLiquidityQueryParams(QueryParams):
    """Query parameters for Hayes Net Liquidity."""
    start_date: date | None = Field(
        default=None,
        description="Start date for the series (YYYY-MM-DD).",
    )
    end_date: date | None = Field(
        default=None,
        description="End date for the series (YYYY-MM-DD).",
    )


# Step 2: Define what the response looks like
class NetLiquidityData(Data):
    """Hayes Net Liquidity Index: WALCL - TGA - RRP."""
    date: date = Field(description="Date of observation.")
    net_liquidity: float = Field(description="Net Liquidity in billions USD.")
    walcl: float = Field(description="Fed Total Assets (WALCL) in billions USD.")
    tga: float = Field(description="Treasury General Account in billions USD.")
    rrp: float = Field(description="Reverse Repo in billions USD.")
    weekly_delta: float | None = Field(
        default=None,
        description="Week-over-week change in billions USD.",
    )
    sentiment: str | None = Field(
        default=None,
        description="EXPANSION or CONTRACTION.",
    )


# Step 3: Implement the three TET stages
class NetLiquidityFetcher(
    Fetcher[
        NetLiquidityQueryParams,
        list[NetLiquidityData],
    ]
):
    """Fetcher for Hayes Net Liquidity Index."""

    @staticmethod
    def transform_query(params: dict) -> NetLiquidityQueryParams:
        """Stage 1: Transform raw dict → validated QueryParams."""
        return NetLiquidityQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: NetLiquidityQueryParams,
        credentials: dict | None,
        **kwargs,
    ) -> list[dict]:
        """Stage 2: Extract raw data from source (no transformation here)."""
        # Import existing calculator — reuse existing logic
        from liquidity.calculators import NetLiquidityCalculator
        from liquidity.config import get_settings

        calculator = NetLiquidityCalculator(settings=get_settings())
        raw = await calculator.get_history(
            start_date=query.start_date,
            end_date=query.end_date,
        )
        return raw  # list of dicts

    @staticmethod
    def transform_data(
        query: NetLiquidityQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[NetLiquidityData]:
        """Stage 3: Validate and standardize raw data → Data models."""
        return [NetLiquidityData.model_validate(record) for record in data]
```

**Key constraints:**
- `aextract_data` must be `async`; use `extract_data` (sync) if truly synchronous
- `transform_query` and `transform_data` are sync static methods
- `credentials` is passed but can be `None` if no API key needed
- All three methods are independently callable for debugging

---

## 3. Provider Extension Structure

### Directory Layout (generated by openbb-cookiecutter or manual)

```
openbb_liquidity_provider/
├── pyproject.toml
├── README.md
└── openbb_liquidity_provider/
    ├── __init__.py              # Provider registration
    └── models/
        ├── __init__.py
        ├── net_liquidity.py     # QueryParams + Data + Fetcher
        ├── global_liquidity.py
        ├── regime.py
        ├── stealth_qe.py
        └── correlations.py
```

### pyproject.toml — Entry Point Registration

**Important:** The project uses `uv` (not Poetry). Use `[project.entry-points]` not `[tool.poetry.plugins]`.

```toml
[project]
name = "openbb-liquidity-provider"
version = "0.1.0"
description = "Custom OpenBB provider for Global Liquidity Monitor"
requires-python = ">=3.11"
dependencies = [
    "openbb-core>=1.5.0",
]

[build-system]
requires = ["setuptools>=70.0.0"]
build-backend = "setuptools.backends.legacy:build"

# THIS is how OpenBB discovers the extension at import time
[project.entry-points."openbb_provider_extension"]
liquidity = "openbb_liquidity_provider:liquidity_provider"

# Optional: also register a Router extension so obb.liquidity.* namespace exists
[project.entry-points."openbb_core_extension"]
liquidity = "openbb_liquidity_provider.router:router"
```

**Contrast with Poetry syntax** (DO NOT use with uv):
```toml
# WRONG for uv projects
[tool.poetry.plugins."openbb_provider_extension"]
liquidity = "openbb_liquidity_provider:liquidity_provider"
```

### Provider `__init__.py`

The `Provider` object must be named `{name}_provider` matching the entry point value.

```python
# openbb_liquidity_provider/__init__.py
from openbb_core.provider.abstract.provider import Provider

from openbb_liquidity_provider.models.net_liquidity import NetLiquidityFetcher
from openbb_liquidity_provider.models.global_liquidity import GlobalLiquidityFetcher
from openbb_liquidity_provider.models.regime import RegimeFetcher
from openbb_liquidity_provider.models.stealth_qe import StealthQEFetcher

liquidity_provider = Provider(
    name="liquidity",
    website="https://github.com/your-org/openbb-liquidity",
    description="Global Liquidity Monitor — Hayes Net Liquidity, Global CB Liquidity, Regime Classification.",
    fetcher_dict={
        # Keys must match the `model=` parameter in @router.command
        "NetLiquidity": NetLiquidityFetcher,
        "GlobalLiquidity": GlobalLiquidityFetcher,
        "LiquidityRegime": RegimeFetcher,
        "StealthQE": StealthQEFetcher,
    },
    # No credentials required (data comes from existing calculators/QuestDB)
    credentials=None,
)
```

### Router Extension (optional — creates `obb.liquidity.*`)

```python
# openbb_liquidity_provider/router.py
from openbb_core.app.router import Router

router = Router(prefix="/liquidity", description="Global Liquidity Monitor endpoints.")

@router.command(model="NetLiquidity")
def net_liquidity(
    cc,               # CommandContext — injected automatically
    provider_choices, # ProviderChoices — injected automatically
    standard_params,  # StandardParams (from QueryParams)
    extra_params,     # ExtraParams (provider-specific)
):
    """Hayes Net Liquidity Index: WALCL - TGA - RRP."""
    return Query(**locals()).execute()
```

After installing this package and running `openbb-build`, `obb.liquidity.net_liquidity()` becomes available.

---

## 4. Installing and Activating Extensions

### With uv (project's package manager)

```bash
# Option A: Install extension as editable dependency within same repo
uv add --editable ./openbb_liquidity_provider

# Option B: Install as separate package
uv pip install -e ./openbb_liquidity_provider

# Rebuild static assets — REQUIRED after any extension install/change
uv run openbb-build
```

### Verify Registration

```python
from openbb import obb

# Check provider is visible
print(obb.coverage.providers)
# {'liquidity': {...}}

# Check commands are registered
print(obb.coverage.commands)
# {'.liquidity.net_liquidity': ['liquidity'], ...}

# Use it
result = obb.liquidity.net_liquidity(provider="liquidity")
df = result.to_df()
```

### When to Run `openbb-build`

Run after:
- Installing the extension package for the first time
- Adding/removing entries in `fetcher_dict`
- Changing `@router.command` parameters
- Changing `QueryParams` or `Data` field names

---

## 5. openbb-platform-api — Workspace Integration

This is the **lowest-effort** integration path. It converts the existing FastAPI (`src/liquidity/api/server.py`) into an OpenBB Workspace-compatible backend with no code changes.

### Installation

```bash
uv add openbb-platform-api
```

### Launch Existing FastAPI as Workspace Backend

```bash
# Launch the existing liquidity API as OpenBB Workspace backend
# Default port: 6900 (auto-increments if occupied)
openbb-api \
  --app /media/sam/1TB/openbb_liquidity/src/liquidity/api/server.py \
  --name app \
  --host 0.0.0.0 \
  --port 6900 \
  --reload

# Or via Makefile/Docker:
# docker run ... uvicorn liquidity.api:app ... then point openbb-api at it
```

The tool reads the FastAPI's OpenAPI schema and auto-generates `widgets.json`. Every GET endpoint becomes a Workspace widget automatically.

### Required: CORS Configuration

The existing `server.py` already has CORS middleware. Verify it includes OpenBB Workspace origins:

```python
# In server.py — verify these origins are present
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pro.openbb.co",      # OpenBB Workspace production
        "http://localhost:1420",       # ODP Desktop app
        "http://localhost:3000",       # Local dev
        "*",                          # Dev only — restrict in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Widget Configuration via `openapi_extra`

No separate `widgets.json` needed. Annotate existing routes inline:

```python
# BEFORE (existing route):
@router.get("/liquidity/net", response_model=NetLiquidityResponse)
async def get_net_liquidity(...):
    """Get Hayes Net Liquidity Index."""
    ...

# AFTER (add openapi_extra for Workspace widget config):
@router.get(
    "/liquidity/net",
    response_model=NetLiquidityResponse,
    openapi_extra={
        "widget_config": {
            "name": "Net Liquidity Index",
            "description": "Hayes Net Liquidity: WALCL - TGA - RRP (billions USD)",
            "category": "Central Bank Liquidity",
            "type": "table",
            "gridData": {"w": 16, "h": 8},
            "source": "FRED / Federal Reserve",
        }
    }
)
async def get_net_liquidity(...):
    ...
```

### Response Schema Requirements

| Widget Type | Return Format | Notes |
|-------------|---------------|-------|
| `table` | `list[dict]` or `list[BaseModel]` | Pydantic models generate column defs |
| `chart` | Plotly JSON dict | Must match Plotly JSON schema |
| `metric` | `{"label": str, "value": float, "delta": float}` | Single KPI display |
| `markdown` | `str` | Markdown-formatted string |
| `html` | `HTMLResponse` | Full HTML content |

**Current API schemas need no changes for table widgets.** The existing `NetLiquidityResponse`, `GlobalLiquidityResponse`, etc. Pydantic models will auto-generate column definitions.

For metric widgets (single KPI panels), the format is:
```python
from fastapi.responses import JSONResponse

@router.get("/liquidity/net/metric")
async def get_net_liquidity_metric() -> JSONResponse:
    return JSONResponse({"label": "Net Liquidity", "value": 5842.3, "delta": -23.1})
```

### Required Endpoints Auto-Generated by openbb-platform-api

When using `openbb-api --app`, these are automatically added:
- `GET /widgets.json` — Widget configuration manifest
- `GET /apps.json` — Dashboard layout definitions (optional)
- `GET /agents.json` — AI agent configurations (optional, new in 4.6)

### Connecting to OpenBB Workspace

1. Launch: `openbb-api --app ./src/liquidity/api/server.py`
2. Navigate to `pro.openbb.co` → Data Connectors → Add Data
3. Enter `http://localhost:6900` as backend URL
4. Name the connection "Global Liquidity Monitor"
5. All GET endpoints appear as draggable widgets

---

## 6. OpenBB 4.6.0 Specifics

**Version confirmed installed:** OpenBB 4.x (meta-package, confirmed via `obb.coverage.commands` output above)

### Breaking Changes in 4.6.0 (January 2025)

| Change | Impact on This Project |
|--------|----------------------|
| Python 3.9 support removed | No impact (project requires 3.11+) |
| Account module / HubService removed | Credentials now via env vars or `.openbb/` config files. No impact (project uses FRED which is credentialed via FRED_API_KEY env var) |
| `obb.economy.interest_rates` consolidates 3 endpoints | Low impact — project uses `obb.economy.fred_series()` directly |
| Python 3.13 support added | No immediate action needed |

### New in 4.6.0 Relevant to v5.0

1. **FastAPI EntryPoint Builder**: `openbb-platform-api` now accepts existing FastAPI instances via `--app` flag. This is the primary enabler for v5.0.

2. **MCP server tools via `openapi_extra`**: Can expose endpoints as AI agent tools. Future capability.

3. **Cookiecutter template update**: Now supports generating Workspace, MCP, CLI, and Python interfaces from a single FastAPI app definition.

4. **Plugin Extensions**: New `on_command_output` hook pattern for intercepting OBBject results.

### OBBject Response Model

Every `obb.*` call returns an `OBBject`. The custom provider Fetchers must return data that gets wrapped in this:

```python
# OBBject structure — what callers receive
{
    "id": "uuid",
    "results": [...],  # list[Data] from transform_data()
    "provider": "liquidity",
    "warnings": [],
    "chart": None,
    "extra": {
        "metadata": {
            "arguments": {...},
            "duration": 0.123,
            "route": "/liquidity/net_liquidity",
            "timestamp": "2026-02-21T..."
        }
    }
}
```

Conversion helpers available: `result.to_df()`, `result.to_dict()`, `result.to_polars()`.

---

## 7. openbb-cookiecutter — Usage

The cookiecutter generates a provider skeleton. Since a working project already exists, use it as a reference rather than scaffolding from scratch.

```bash
pip install cookiecutter poetry
cookiecutter https://github.com/OpenBB-finance/openbb-cookiecutter
```

Prompts:
- Your Name
- Your Email
- Extension Name → `liquidity`
- Package Name → `openbb_liquidity_provider`

Generated output matches the directory structure in Section 3 above. The main value is the pre-configured `pyproject.toml` with correct entry points.

**Adaptation strategy**: Generate the skeleton in a temporary directory, then cherry-pick the `pyproject.toml` template and adapt the `__init__.py` pattern. Do not use the generated model files — port existing code instead.

---

## 8. Integration Path Decision: Two Approaches

### Path A: Workspace Backend Only (Recommended for v5.0 Phase 1)

**What**: Expose existing FastAPI as OpenBB Workspace data connector.
**Effort**: LOW — no new code, only `openapi_extra` annotations on 14 existing endpoints.
**Result**: All 14 endpoints become draggable widgets in OpenBB Workspace. The existing Plotly Dash dashboard continues to work unchanged.

```bash
# Install
uv add openbb-platform-api

# Launch (can replace uvicorn in docker-compose)
openbb-api --app /app/src/liquidity/api/server.py --host 0.0.0.0 --port 6900
```

### Path B: Native Provider Extension (Phase 2)

**What**: Package calculators as `openbb_provider_extension` so `obb.liquidity.*` works.
**Effort**: MODERATE — ~5 Fetcher classes, one `pyproject.toml`, entry point registration, `openbb-build`.
**Result**: Commands callable from Python SDK, OpenBB CLI, and as MCP tools.

### Path C: Both (Full v5.0)

Run Paths A and B in parallel. The Workspace backend (Path A) can serve while the provider extension (Path B) is being built. No conflict.

---

## 9. Existing FastAPI Compatibility Assessment

**Current server.py analysis:**

| Aspect | Current State | v5.0 Compatibility |
|--------|--------------|-------------------|
| FastAPI instance named `app` | Yes | Direct `--name app` works |
| CORS middleware | Yes (permissive) | Add `pro.openbb.co` origin |
| GET endpoints | 14 endpoints | All auto-become widgets |
| Response models | Pydantic `BaseModel` subclasses | Auto-generate column defs |
| Async handlers | Yes | Required by `aextract_data` |
| QuestDB dependency | Yes | Need QUESTDB available at launch |
| Environment variables | FRED_API_KEY via dotenvx | Compatible |

**Routes that map well to Workspace widget types:**

| Route | Widget Type | Notes |
|-------|-------------|-------|
| `GET /liquidity/net` | `table` or `metric` | Single snapshot → metric; history → table |
| `GET /liquidity/global` | `table` | Multi-CB breakdown |
| `GET /regime/current` | `metric` | EXPANSION/CONTRACTION with intensity |
| `GET /regime/history` | `table` | Regime history |
| `GET /metrics/stealth-qe` | `metric` | Score 0-100 |
| `GET /fx/*` | `table` | FX pairs |
| `GET /stress/*` | `table` | Stress indicators |
| `GET /correlations/*` | `table` | Correlation matrix |
| `GET /calendar/*` | `table` | Upcoming events |

---

## 10. Stack Summary

### For Workspace Integration (Path A)

```toml
# Add to pyproject.toml dependencies
dependencies = [
    ...existing...,
    "openbb-platform-api>=0.2.0",
]
```

```bash
# Launch command (replaces or supplements uvicorn)
openbb-api --app src/liquidity/api/server.py --host 0.0.0.0 --port 6900 --reload
```

### For Provider Extension (Path B)

```
New package: openbb_liquidity_provider/
├── pyproject.toml         # entry-points."openbb_provider_extension"
└── openbb_liquidity_provider/
    ├── __init__.py        # liquidity_provider = Provider(fetcher_dict={...})
    └── models/
        ├── net_liquidity.py   # QueryParams + Data + Fetcher
        ├── global_liquidity.py
        ├── regime.py
        └── stealth_qe.py
```

```bash
# Install extension (editable, within monorepo)
uv add --editable ./openbb_liquidity_provider

# Rebuild (required after install or any fetcher_dict change)
uv run openbb-build
```

---

## Confidence Assessment

| Area | Confidence | Source |
|------|------------|--------|
| TET pipeline (QueryParams/Data/Fetcher) | HIGH | Official docs + code examples verified |
| pyproject.toml entry points (uv format) | HIGH | Python packaging spec + OpenBB docs confirm `[project.entry-points]` |
| Provider `__init__.py` structure | HIGH | Alpha Vantage provider source + official docs |
| openbb-platform-api `--app` flag | HIGH | PR #7016, official docs, PyPI |
| `openapi_extra` widget_config | HIGH | Official docs + PR #7014 |
| OBBject response structure | HIGH | Official docs + live `obb.coverage.commands` output |
| `openbb-build` requirement | HIGH | Official docs, multiple sources |
| Poetry vs uv entry-point format | MEDIUM | Official Python packaging spec confirms `[project.entry-points]`; one source explicitly calls this out for uv users. Test required. |
| Exact `openbb-platform-api` version | LOW | Not confirmed which minor version introduced `--app` flag (known in 4.4.0+) |

---

## Pitfalls to Avoid

1. **Using `[tool.poetry.plugins]` with uv**: Use `[project.entry-points."openbb_provider_extension"]` instead. Poetry-style plugins are not recognized by setuptools/uv.

2. **Forgetting `openbb-build`**: After installing or modifying the provider extension, static assets must be rebuilt. Without this, `obb.liquidity.*` commands will not exist. This step is easy to miss in CI/CD.

3. **Circular imports**: The Fetcher's `aextract_data` imports from `liquidity.calculators`. This introduces a dependency on the full liquidity stack at provider import time. Consider lazy imports inside the method to avoid startup failures if QuestDB is unreachable.

4. **QuestDB dependency in Fetcher**: The Workspace backend (`openbb-api`) starts a separate process. If QuestDB is not running, all Fetcher calls fail. The Workspace integration must run against a live stack, not standalone.

5. **`credentials=None` for internal provider**: The `Provider` class accepts `credentials=None` when no external API key is needed. Do not pass an empty dict — it will cause credential validation errors.

6. **Static assets cache**: If `obb.liquidity.*` commands appear stale after changes, delete the `~/.openbb/` static cache directory and re-run `openbb-build`.

7. **OpenBB Workspace CORS**: The existing CORS config may not include `https://pro.openbb.co`. This causes silent failures in the Workspace UI (widget connects but returns no data).

---

## Sources

- [OpenBB Build Provider Extensions — Developer Docs](https://docs.openbb.co/odp/python/developer/extension_types/provider)
- [OpenBB TET Pipeline Blog Post](https://openbb.co/blog/the-openbb-platform-data-pipeline)
- [openbb-cookiecutter GitHub](https://github.com/OpenBB-finance/openbb-cookiecutter)
- [Build New Provider Extension — How-To](https://docs.openbb.co/platform/user_guides/add_data_provider_extension)
- [openbb-platform-api PyPI](https://pypi.org/project/openbb-platform-api/)
- [openbb-api Extension Docs](https://docs.openbb.co/python/extensions/interface/openbb-api)
- [OpenBB Workspace Data Integration](https://docs.openbb.co/workspace/developers/data-integration)
- [OpenBB Workspace Quickstart](https://docs.openbb.co/python/quickstart/workspace)
- [Alpha Vantage pyproject.toml — Entry Point Reference](https://github.com/OpenBB-finance/OpenBB/blob/develop/openbb_platform/providers/alpha_vantage/pyproject.toml)
- [Architecture Overview](https://docs.openbb.co/odp/python/developer/architecture_overview)
- [GitHub PR #7014 — Widget Config in Router Decorator](https://github.com/OpenBB-finance/OpenBB/pull/7014)
- [GitHub PR #7016 — Custom FastAPI Instance](https://github.com/OpenBB-finance/OpenBB/pull/7016)
- [OpenBB Releases](https://github.com/OpenBB-finance/OpenBB/releases)
- [OBBject Response Model](https://docs.openbb.co/python/basic_usage/response_model)
