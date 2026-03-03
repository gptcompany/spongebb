# Research: OpenBB Platform Integration — Features & API

**Project:** Global Liquidity Monitor v5.0
**Milestone:** OpenBB Platform Integration
**Researched:** 2026-02-21
**Overall confidence:** HIGH (official docs + PyPI package + verified examples)

---

## 1. OpenBB Workspace Widgets

### 1.1 Widget Types

The `type` field in `widgets.json` (or `openapi_extra.widget_config`) sets the default visualization. Confirmed values (HIGH confidence — official docs):

| Type | Use Case | Return Type |
|------|----------|-------------|
| `"table"` | Tabular data (default) | `list[dict]` or `list[BaseModel]` |
| `"table_ssrm"` | Server-side row model for large datasets | `list[dict]` |
| `"chart"` | Plotly JSON chart | `dict` (Plotly JSON) |
| `"advanced-chart"` | TradingView advanced chart | Custom |
| `"chart-highcharts"` | Highcharts chart | Custom |
| `"markdown"` | Markdown text | `str` |
| `"metric"` | Single KPI card (label + value + delta) | `MetricResponseModel` |
| `"note"` | Static note/annotation | `str` |
| `"multi_file_viewer"` | File viewer | Custom |
| `"live_grid"` | WebSocket-driven live grid | Streaming |
| `"newsfeed"` | News list | Custom |
| `"youtube"` | YouTube embed | Custom |

**For this project, relevant types:**
- `"metric"` — Net Liquidity value, Global Liquidity total, regime badge
- `"chart"` — Plotly time series (existing dashboard exports work directly)
- `"table"` — Correlations, stress indicators, component breakdowns
- `"markdown"` — Regime narrative, Stealth QE interpretation

### 1.2 Widget Definition — Two Approaches

**Approach A: Inline via `openapi_extra` (recommended, no separate file needed)**

```python
from fastapi import FastAPI
from openbb_platform_api.response_models import MetricResponseModel

app = FastAPI()

@app.get(
    "/liquidity/net",
    openapi_extra={
        "widget_config": {
            "name": "Net Liquidity Index",
            "description": "Hayes formula: WALCL - TGA - RRP (in billions USD)",
            "category": "Macro Liquidity",
            "subCategory": "Fed",
            "refetchInterval": 900000,   # 15 minutes in ms
            "staleTime": 300000,          # 5 minutes
            "gridData": {"w": 12, "h": 4},
        }
    },
)
async def get_net_liquidity() -> MetricResponseModel:
    """Current Fed Net Liquidity (WALCL - TGA - RRP)."""
    ...
```

**Approach B: Standalone `widgets.json`** (needed only for backends NOT using `openbb-platform-api`)

```json
{
  "net_liquidity": {
    "name": "Net Liquidity Index",
    "description": "Hayes formula: WALCL - TGA - RRP",
    "category": "Macro Liquidity",
    "endpoint": "/liquidity/net",
    "type": "metric",
    "gridData": {"w": 12, "h": 4},
    "source": ["FRED"],
    "refetchInterval": 900000,
    "params": [
      {
        "paramName": "tier",
        "value": 1,
        "label": "CB Tier",
        "type": "number",
        "description": "1=Tier1 only, 2=Include BoE/SNB/BoC"
      }
    ]
  }
}
```

### 1.3 Widget JSON Schema — Complete Field Reference

**Confirmed from official docs** (HIGH confidence):

```json
{
  "widget_id": {
    "name": "string (required)",
    "description": "string (required)",
    "endpoint": "string (required — path relative to backend root)",

    "wsEndpoint": "string (WebSocket, live_grid only)",
    "category": "string",
    "subCategory": "string",
    "imgUrl": "string",
    "type": "table|chart|metric|markdown|...",
    "raw": "boolean (toggle chart/raw for Plotly)",
    "runButton": "boolean",
    "source": ["array of strings"],
    "refetchInterval": "number|false (ms, default 900000)",
    "staleTime": "number (ms, default 300000)",

    "gridData": {
      "w": "number (max 40)",
      "h": "number (max 100)",
      "minW": "number",
      "minH": "number",
      "maxW": "number",
      "maxH": "number"
    },

    "data": {
      "dataKey": "string (nested key for non-top-level arrays)",
      "table": {
        "enableCharts": "boolean",
        "showAll": "boolean",
        "transpose": "boolean",
        "enableAdvanced": "boolean",
        "columnsDefs": [
          {
            "field": "string",
            "headerName": "string",
            "cellDataType": "text|number|boolean|date|dateString|object",
            "chartDataType": "category|series|time|excluded",
            "formatterFn": "int|none|percent|normalized|normalizedPercent|dateToYear",
            "renderFn": "greenRed|titleCase|hoverCard|cellOnClick|columnColor|showCellChange",
            "width": "number",
            "hide": "boolean",
            "pinned": "left|right",
            "prefix": "string",
            "suffix": "string"
          }
        ]
      }
    },

    "params": [
      {
        "type": "date|text|ticker|number|boolean|endpoint|form|tabs",
        "paramName": "string",
        "value": "default value",
        "label": "string",
        "description": "string",
        "show": "boolean",
        "multiple": "boolean",
        "options": [{"label": "string", "value": "string"}],
        "optionsEndpoint": "string (dynamic options from endpoint)"
      }
    ],

    "mcp_tool": {
      "mcp_server": "string",
      "tool_id": "string"
    }
  }
}
```

### 1.4 Date Parameter Syntax

OpenBB Workspace supports dynamic date defaults:

```
"$currentDate"       → today
"$currentDate-2y"    → 2 years ago
"$currentDate-1M"    → 1 month ago
"$currentDate-30d"   → 30 days ago
"$currentDate+1d"    → tomorrow
```

Use modifiers: `h` (hour), `d` (day), `w` (week), `M` (month), `y` (year).

### 1.5 Metric Widget — Exact Format

```python
from openbb_platform_api.response_models import MetricResponseModel

@app.get("/liquidity/net/metric")
async def net_liquidity_metric() -> MetricResponseModel:
    """Net Liquidity (WALCL - TGA - RRP)."""
    return MetricResponseModel(
        label="Net Liquidity",
        value=6_123_456_789_000,   # raw number
        delta="+$45B WoW",          # string, shown as delta
    )
```

### 1.6 Chart Widget — Plotly JSON Format

```python
@app.get(
    "/liquidity/net/chart",
    openapi_extra={"widget_config": {"type": "chart"}},
)
async def net_liquidity_chart() -> dict:
    """Net Liquidity time series chart."""
    import plotly.graph_objects as go
    fig = go.Figure(...)
    return fig.to_plotly_json()
```

The existing dashboard's Plotly figures (`src/liquidity/dashboard/components/*.py`) return `go.Figure` objects that can be converted directly with `.to_plotly_json()`.

### 1.7 Table Widget with Column Definitions

```python
from pydantic import BaseModel, Field
import datetime

class LiquidityRow(BaseModel):
    date: datetime.date = Field(title="Date")
    net_liquidity: float = Field(
        title="Net Liquidity (B)",
        json_schema_extra={"x-widget_config": {"formatterFn": "int", "renderFn": "greenRed"}},
    )
    weekly_delta: float = Field(
        title="WoW Change (B)",
        json_schema_extra={"x-widget_config": {"formatterFn": "int", "renderFn": "greenRed"}},
    )
    regime: str = Field(title="Regime")

@app.get("/liquidity/history")
async def liquidity_history(
    days: int = 90,
) -> list[LiquidityRow]:
    """Net Liquidity history table."""
    ...
```

---

## 2. OpenBB Provider Extension Pattern

### 2.1 Architecture Overview

The provider extension uses a three-class TET (Transform-Extract-Transform) pattern. A provider does NOT create new endpoints — it adds alternative data sources to existing router commands via the `model` parameter. The router command stays the same; providers are switched via `provider=` argument.

**When to use provider extensions vs. direct FastAPI:**
- Use **provider extensions** when: exposing data as `obb.economy.*` commands, when data fits the OpenBB standard model schema, when you want multi-provider fallback.
- Use **direct FastAPI + openbb-platform-api** when: building custom Workspace widgets, exposing proprietary calculations, when you control the API from end to end (our case).

**Recommendation for this project:** Direct FastAPI + `openbb-platform-api` is simpler and faster. Provider extensions require `openbb-build` after every change and pyproject.toml plugin registration. The project already has a working FastAPI server — this is the integration target.

### 2.2 Provider Extension Pattern (for reference)

If exposing data as `obb.economy.custom_liquidity`:

**Directory structure:**
```
spongebb_provider/
├── pyproject.toml
├── spongebb_provider/
│   ├── __init__.py          # Provider instance
│   └── models/
│       └── net_liquidity.py # QueryParams + Data + Fetcher
```

**QueryParams:**
```python
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field
from datetime import date as dateType

class NetLiquidityQueryParams(QueryParams):
    """Net Liquidity Query Parameters."""
    start_date: dateType | None = Field(default=None, description="Start date")
    end_date: dateType | None = Field(default=None, description="End date")
```

**Data Model:**
```python
from openbb_core.provider.abstract.data import Data
from pydantic import Field
from datetime import date as dateType

class NetLiquidityData(Data):
    """Net Liquidity Data."""
    date: dateType = Field(description="Data date")
    net_liquidity: float = Field(description="Net Liquidity (WALCL - TGA - RRP) in billions USD")
    walcl: float = Field(description="Fed Total Assets")
    tga: float = Field(description="Treasury General Account")
    rrp: float = Field(description="Reverse Repo")
    regime: str = Field(description="EXPANSION|CONTRACTION")
```

**Fetcher (async):**
```python
from openbb_core.provider.abstract.fetcher import Fetcher
from typing import Any

class NetLiquidityFetcher(Fetcher[NetLiquidityQueryParams, list[NetLiquidityData]]):
    """Net Liquidity Fetcher."""

    require_credentials = False  # No external API key needed

    @staticmethod
    def transform_query(params: dict[str, Any]) -> NetLiquidityQueryParams:
        return NetLiquidityQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: NetLiquidityQueryParams,
        credentials: dict | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch from our internal FastAPI or directly from calculator."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "http://localhost:8000/liquidity/net",
                params={"start_date": query.start_date, "end_date": query.end_date},
            )
        return resp.json()

    @staticmethod
    def transform_data(
        query: NetLiquidityQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[NetLiquidityData]:
        return [NetLiquidityData.model_validate(item) for item in data]
```

**Provider registration (`__init__.py`):**
```python
from openbb_core.provider.abstract.provider import Provider
from spongebb_provider.models.net_liquidity import NetLiquidityFetcher

liquidity_provider = Provider(
    name="liquidity",
    website="http://localhost:8000",
    description="Global Liquidity Monitor custom data provider",
    credentials=[],  # No credentials needed for local
    fetcher_dict={
        "NetLiquidity": NetLiquidityFetcher,
    },
)
```

**pyproject.toml:**
```toml
[tool.poetry.plugins."openbb_provider_extension"]
liquidity = "spongebb_provider:liquidity_provider"
```

**After installing:** Run `openbb-build` to rebuild static assets.

**Usage:**
```python
from openbb import obb
result = obb.economy.net_liquidity(provider="liquidity", start_date="2024-01-01")
df = result.to_df()
```

### 2.3 Async Support — HIGH Confidence

OpenBB 4.x fully supports async Fetcher classes. Use `aextract_data` (not `extract_data`) for async:

```python
@staticmethod
async def aextract_data(
    query: CustomQueryParams,
    credentials: dict | None,
    **kwargs: Any,
) -> list[dict]:
    # Use openbb_core helpers for concurrent requests
    from openbb_core.provider.utils.helpers import amake_requests, get_querystring

    urls = [f"https://api.example.com/data?{get_querystring(vars(query), [])}" ]
    return await amake_requests(urls)  # Uses asyncio.gather internally
```

`amake_requests` calls `asyncio.gather` internally for concurrent multi-URL fetching. This is the recommended pattern for fetchers that need multiple API calls (e.g., fetching multiple FRED series concurrently).

**For `asyncio.to_thread` patterns:** These work inside `aextract_data` for CPU-bound work but are not needed for IO-bound tasks if using `amake_requests`.

### 2.4 Multi-Provider Queries — Confirmed Pattern

OpenBB does NOT natively aggregate data from multiple providers in a single call. Each call selects ONE provider. To aggregate:

**Pattern 1: In the Fetcher (recommended for our use case)**
```python
@staticmethod
async def aextract_data(query, credentials, **kwargs):
    # Fetch FRED data + custom calculator concurrently
    import asyncio
    fred_data, calc_data = await asyncio.gather(
        fetch_fred_series(["WALCL", "WTREGEN", "RRPONTSYD"]),
        fetch_calculator_result()
    )
    return merge(fred_data, calc_data)
```

**Pattern 2: In FastAPI endpoint (our current architecture)**
```python
@app.get("/liquidity/global")
async def get_global_liquidity():
    # Our existing calculator already aggregates FRED + PBoC + ECB
    result = await global_liquidity_calculator.get_current()
    return result
```

**The second pattern is already what this project does.** The FastAPI endpoints already call multiple collectors internally.

---

## 3. Authentication

### 3.1 Custom Backend Authentication

OpenBB Workspace authenticates with custom backends via **API key in header or query parameter**. Configured once in the Workspace UI when adding the backend.

**FastAPI implementation:**
```python
import os
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

app = FastAPI()
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

VALID_API_KEYS = set(os.environ.get("LIQUIDITY_API_KEYS", "").split(","))

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

@app.get("/liquidity/net")
async def get_net_liquidity(api_key: str = Security(verify_api_key)):
    ...
```

**Workspace configuration:** User adds backend URL in the UI and specifies:
- Header name: `X-API-KEY`
- Header value: `<your-key>`

These are sent on every subsequent request automatically.

### 3.2 PAT Tokens (OpenBB Hub)

PAT tokens authenticate the **Python SDK** with OpenBB Hub for storing credentials. This is separate from custom backend auth. For local/self-hosted backends, PAT tokens are NOT needed.

```python
from openbb import obb
obb.account.login(pat="<HUB_PAT>")  # Only if using OpenBB Hub credential storage
```

**For this project:** Our FastAPI backend uses its own API key auth. No Hub PAT needed.

### 3.3 CORS Requirements

Custom backends MUST allow CORS from `https://pro.openbb.co`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pro.openbb.co",
        "https://excel.openbb.co",
        "http://localhost:1420",  # Local Workspace app
    ],
    allow_credentials=True,
    allow_methods=["GET"],  # Workspace only uses GET (except POST for forms/omni)
    allow_headers=["*"],
)
```

The project's existing CORS config (`allow_origins=["*"]`) is fine for development. Tighten for production.

**HTTPS note:** Safari and Brave require HTTPS for local connections. Use the `openssl` self-signed cert approach or run Workspace from Chrome/Firefox during development.

---

## 4. Caching and Rate Limiting

### 4.1 OpenBB Platform — No Native Provider-Level TTL Cache

Confirmed (HIGH confidence): `openbb-core` does NOT provide a built-in TTL caching layer for provider responses. The in-session OBBject registry (CLI stack cache) is session-only.

**Caching must be implemented in the FastAPI layer or inside Fetcher classes.**

### 4.2 Workspace-Side Caching (Frontend)

Two widget-level controls (from `widgets.json` or `openapi_extra`):

| Field | Default | Description |
|-------|---------|-------------|
| `staleTime` | 300,000 ms (5 min) | When to show orange refresh indicator |
| `refetchInterval` | 900,000 ms (15 min) | Auto-refresh interval; `false` to disable |

**Recommended settings for this project:**

```python
# Daily data (FRED weekly/daily series) — refresh every 4 hours
openapi_extra={"widget_config": {"refetchInterval": 14400000, "staleTime": 3600000}}

# Near-real-time data (regime, stress indicators) — refresh every 15 min
openapi_extra={"widget_config": {"refetchInterval": 900000, "staleTime": 300000}}

# Quarterly data (BIS, COFER) — disable auto-refresh
openapi_extra={"widget_config": {"refetchInterval": False, "staleTime": 86400000}}
```

### 4.3 Backend-Side Caching (FastAPI Layer)

Implement caching in the FastAPI endpoints or in the collectors. Since data is already persisted in QuestDB, the FastAPI endpoints should query QuestDB (fast, <10ms) rather than re-fetching from FRED on every request.

**Pattern for API-level response caching (if QuestDB not available):**
```python
from functools import lru_cache
from datetime import datetime, timedelta
from typing import Any

_cache: dict[str, tuple[datetime, Any]] = {}

async def cached_fetch(key: str, ttl_seconds: int, fetch_fn):
    now = datetime.utcnow()
    if key in _cache:
        cached_time, cached_value = _cache[key]
        if now - cached_time < timedelta(seconds=ttl_seconds):
            return cached_value
    result = await fetch_fn()
    _cache[key] = (now, result)
    return result
```

For production, use `cachetools.TTLCache` or Redis. The QuestDB storage layer already provides effective caching since collectors write to QuestDB and the API reads from it.

### 4.4 Rate Limiting

No built-in rate limiting in `openbb-core`. For the custom FastAPI backend, add `slowapi` if needed:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/liquidity/net")
@limiter.limit("60/minute")
async def get_net_liquidity(request: Request):
    ...
```

For an internal tool with one user, rate limiting is not needed.

---

## 5. Async Support in OpenBB 4.x

### 5.1 Fetcher Async — Confirmed HIGH Confidence

Both sync and async extraction are supported. One of `extract_data` OR `aextract_data` must be implemented (not both).

```python
class SomeFetcher(Fetcher[SomeQueryParams, list[SomeData]]):
    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> SomeQueryParams:
        return SomeQueryParams(**params)

    # Use aextract_data for IO-bound (API calls, multiple requests)
    @staticmethod
    async def aextract_data(
        query: SomeQueryParams,
        credentials: dict | None,
        **kwargs: Any,
    ) -> list[dict]:
        from openbb_core.provider.utils.helpers import amake_requests
        urls = [build_url(query)]
        return await amake_requests(urls)

    @staticmethod
    def transform_data(
        query: SomeQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[SomeData]:
        return [SomeData.model_validate(item) for item in data]
```

### 5.2 FastAPI Async — Already Implemented

The project's FastAPI endpoints are already fully async (`async def`). The calculators use `await calculator.get_current()` patterns. This is correct and fully compatible with OpenBB Workspace.

### 5.3 asyncio.to_thread Pattern

For synchronous IO (e.g., pandas FRED fetch via `fredapi`, which is sync):
```python
import asyncio
from fredapi import Fred

@staticmethod
async def aextract_data(query, credentials, **kwargs):
    fred = Fred(api_key=credentials.get("fred_api_key"))
    # Run sync call in thread pool
    data = await asyncio.to_thread(
        fred.get_series, "WALCL", observation_start=query.start_date
    )
    return data.reset_index().to_dict("records")
```

The project's existing collectors already use this pattern correctly.

---

## 6. Integration Strategy — FastAPI + openbb-platform-api

### 6.1 Recommended Integration Approach

**Do NOT rebuild as a provider extension.** The cleanest path for v5.0 is:

1. Install `openbb-platform-api` alongside existing dependencies
2. Add `widget_config` annotations to existing FastAPI endpoints via `openapi_extra`
3. Add `openbb-api` as a launch command pointing to `server.py`
4. Add required endpoints: `/widgets.json` (auto-generated), `/apps.json` (optional)

```bash
pip install openbb-platform-api

# Launch existing app as OpenBB Workspace backend:
openbb-api --app src/liquidity/api/server.py --host 0.0.0.0 --port 6900 --reload
```

### 6.2 Required Endpoints

`openbb-platform-api` auto-generates these — no manual implementation needed:

| Endpoint | Generated by | Purpose |
|----------|-------------|---------|
| `GET /widgets.json` | `openbb-platform-api` | Widget configurations |
| `GET /apps.json` | `openbb-platform-api` | App layout templates |
| `GET /agents.json` | `openbb-platform-api` | MCP/AI agent config |

The existing endpoints (`/liquidity/net`, `/regime/current`, etc.) map directly to widgets based on their return type annotations.

### 6.3 Return Type to Widget Type Mapping

`openbb-platform-api` infers widget type from return annotation:

| Return Type | Widget Type Generated |
|-------------|----------------------|
| `-> str` | `"markdown"` |
| `-> list[dict]` or `-> list[Model]` | `"table"` |
| `-> MetricResponseModel` | `"metric"` |
| `-> dict` + `widget_config.type="chart"` | `"chart"` |
| `-> OmniWidgetResponseModel` (POST) | `"omni"` |

### 6.4 Adapting Existing Endpoints

The existing API returns Pydantic models (`NetLiquidityResponse`, `GlobalLiquidityResponse`, etc.). These need minimal adaptation:

**Option A — Keep existing Pydantic models, add `openapi_extra`:**
```python
@router.get(
    "/net",
    response_model=NetLiquidityResponse,
    openapi_extra={
        "widget_config": {
            "name": "Net Liquidity Index",
            "category": "Macro Liquidity",
            "type": "metric",
            "refetchInterval": 900000,
        }
    },
)
async def get_net_liquidity(calculator: NetLiquidityCalcDep) -> NetLiquidityResponse:
    ...
```

**Option B — Add dedicated Workspace endpoints returning native types:**
```python
# Dedicated workspace endpoint for metric widget
@app.get(
    "/workspace/liquidity/net/metric",
    openapi_extra={"widget_config": {"type": "metric", "name": "Net Liquidity"}},
)
async def net_liquidity_metric() -> MetricResponseModel:
    result = await net_liquidity_calc.get_current()
    return MetricResponseModel(
        label="Net Liquidity",
        value=result.net_liquidity,
        delta=f"{result.weekly_delta:+.0f}B WoW",
    )
```

Option B is cleaner — existing endpoints preserve their schema for NautilusTrader integration (API-05 requirement), and new Workspace-specific endpoints serve the UI.

### 6.5 Endpoint-to-Widget Mapping for This Project

| Existing Endpoint | Widget Type | Widget Name | Refresh |
|-------------------|-------------|-------------|---------|
| `/liquidity/net` | metric | Net Liquidity Index | 15 min |
| `/liquidity/global` | metric | Global Liquidity Index | 15 min |
| `/regime/current` | markdown | Liquidity Regime | 15 min |
| `/metrics/stealth-qe` | metric | Stealth QE Score | 15 min |
| `/stress/indicators` | table | Funding Stress Indicators | 15 min |
| `/correlations` | table | Cross-Asset Correlations | 1 hour |
| `/fx` | table | FX Monitor | 15 min |
| `/calendar/events` | table | Macro Calendar | 4 hours |
| New: `/charts/net-liquidity` | chart | Net Liquidity Chart | 15 min |
| New: `/charts/global-liquidity` | chart | Global Liquidity Chart | 15 min |
| New: `/charts/correlation-heatmap` | chart | Correlation Heatmap | 1 hour |

---

## 7. Complete Working Example

Minimal working custom backend serving a Net Liquidity metric widget to OpenBB Workspace:

```python
"""
src/liquidity/api/workspace.py
Workspace-compatible API layer wrapping existing endpoints.
"""
import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openbb_platform_api.response_models import MetricResponseModel, Data
from pydantic import Field

app = FastAPI(title="Global Liquidity Monitor — OpenBB Workspace Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pro.openbb.co", "http://localhost:1420"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class StressIndicatorRow(Data):
    """Funding market stress indicators."""
    indicator: str = Field(title="Indicator")
    value: float | None = Field(title="Value (bps or %)", default=None)
    level: str = Field(title="Level")
    threshold_normal: float = Field(title="Normal Threshold")
    threshold_stress: float = Field(title="Stress Threshold")


@app.get(
    "/workspace/liquidity/net",
    openapi_extra={
        "widget_config": {
            "name": "Net Liquidity Index",
            "description": "Hayes formula: WALCL - TGA - RRP (Fed balance sheet minus drains)",
            "category": "Macro Liquidity",
            "subCategory": "Fed",
            "refetchInterval": 900000,
            "staleTime": 300000,
            "gridData": {"w": 8, "h": 4},
        }
    },
)
async def net_liquidity_metric() -> MetricResponseModel:
    """Current Fed Net Liquidity in billions USD."""
    # Call existing calculator
    from liquidity.api.deps import get_net_liquidity_calculator
    calc = get_net_liquidity_calculator()
    result = await calc.get_current()
    return MetricResponseModel(
        label="Net Liquidity",
        value=round(result.net_liquidity, 1),
        delta=f"{result.weekly_delta:+.1f}B WoW",
    )


@app.get(
    "/workspace/stress",
    openapi_extra={
        "widget_config": {
            "name": "Funding Stress Indicators",
            "category": "Stress",
            "refetchInterval": 900000,
            "data": {
                "table": {
                    "columnsDefs": [
                        {"field": "indicator", "headerName": "Indicator", "pinned": "left"},
                        {"field": "value", "headerName": "Value", "formatterFn": "int"},
                        {"field": "level", "headerName": "Level", "renderFn": "titleCase"},
                    ]
                }
            }
        }
    },
)
async def stress_indicators() -> list[StressIndicatorRow]:
    """Funding market stress indicators table."""
    ...
```

**Launch command:**
```bash
openbb-api --app src/liquidity/api/workspace.py --host 0.0.0.0 --port 6900 --reload
```

**Connect in OpenBB Workspace:**
1. Right-click dashboard → "Add data"
2. Backend URL: `http://localhost:6900`
3. Optional: Header `X-API-KEY: <key>`
4. Click "Test" → "Add"

---

## 8. Sources

| Source | Confidence | URL |
|--------|-----------|-----|
| widgets.json Reference | HIGH | https://docs.openbb.co/workspace/developers/json-specs/widgets-json-reference |
| Data Integration Guide | HIGH | https://docs.openbb.co/workspace/developers/data-integration |
| openbb-platform-api PyPI | HIGH | https://pypi.org/project/openbb-platform-api/ |
| ODP Provider Extension Docs | HIGH | https://docs.openbb.co/odp/python/developer/extension_types/provider |
| ODP Quickstart Workspace | HIGH | https://docs.openbb.co/odp/python/quickstart/workspace |
| Architecture Overview | HIGH | https://docs.openbb.co/odp/python/developer/architecture_overview |
| openbb-api Interface Docs | HIGH | https://docs.openbb.co/odp/python/extensions/interface/openbb-api |
| HTTP Requests Guide | MEDIUM | https://docs.openbb.co/platform/developer_guide/http_requests (404 — content retrieved via search) |
| OpenBB GitHub Backends Repo | MEDIUM | https://github.com/OpenBB-finance/backend-examples-for-openbb-workspace |
| Stale Time Docs | HIGH | https://docs.openbb.co/workspace/developers/widget-configuration/stale-time |
| openbb-platform-api v1.3.0 | HIGH | Released 2026-02-17 (current) |

---

## 9. Key Decisions for v5.0 Implementation

### Use direct FastAPI + openbb-platform-api (not provider extensions)

**Rationale:** Provider extensions require:
- `openbb-build` CLI step after every model change
- pyproject.toml plugin registration
- Separate package installation
- Full OpenBB Python SDK in production

The existing FastAPI server already works. `openbb-platform-api` wraps it with zero overhead. Workspace widgets are configured inline via `openapi_extra`.

### Do not implement native TTL caching in OpenBB layer

**Rationale:** No built-in TTL caching in `openbb-core`. QuestDB is the effective cache — collectors write there, API reads from it. Frontend `refetchInterval` controls UI update frequency.

### Separate Workspace endpoints from existing API endpoints

**Rationale:** Existing endpoints have schemas designed for NautilusTrader (`API-05`). Adding `openapi_extra` to them is fine, but dedicated `/workspace/*` routes allow different response shapes optimized for the Workspace UI (e.g., `MetricResponseModel`, Plotly JSON) without breaking existing consumers.

### Authentication: optional API key header

**Rationale:** Internal tool, single user. Implement `X-API-KEY` header validation as optional middleware that can be enabled for remote access. CORS is the primary protection for local development.

---

*Generated: 2026-02-21*
*openbb-platform-api version verified: 1.3.0 (released 2026-02-17)*
*openbb version verified: 4.6.0 (released 2026-01-02)*
