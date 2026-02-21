# Phase 25: Native Provider Extension — Context

## Phase Goal
Create an OpenBB Provider Extension so users can access liquidity data via `obb.liquidity.*` Python SDK commands.

## Gate Conditions (both met)
- Issue #7113 (OpenBB 4.4.4 import bug): CLOSED
- User demand: Explicit "Continua Phase 25" choice

## Decisions

### Provider Name
`liquidity` — maps to `obb.liquidity.*` namespace

### Fetchers (3 core)
| Command Name | Calculator | Primary Method | Return |
|---|---|---|---|
| `NetLiquidity` | NetLiquidityCalculator | `calculate()` → DataFrame | Time series |
| `GlobalLiquidity` | GlobalLiquidityCalculator | `calculate()` → DataFrame | Time series |
| `StealthQE` | StealthQECalculator | `calculate_daily()` → DataFrame | Time series |

### Excluded from Phase 25
- RegimeClassifier: Returns single classification, not time-series. Better as `obb.liquidity.regime()` in future phase.
- LiquidityValidator: Internal utility, not user-facing data.

### Credentials
None — calculators use local FRED data already configured in Settings.

### Entry Point Registration
```toml
[project.entry-points."openbb_provider_extension"]
liquidity = "liquidity.openbb_ext.provider:liquidity_provider"
```

### OpenBB Provider Pattern (TET)
1. `transform_query()` — Validate/normalize query params
2. `aextract_data()` — Call async calculator, return raw dicts
3. `transform_data()` — Wrap in `AnnotatedResult[list[Data]]`

### Key Constraints
- OpenBB 4.x uses `Fetcher[QueryParams, list[Data]]` generic
- `aextract_data` must return `dict | list[dict]` (not DataFrame)
- QueryParams must inherit from `openbb_core.provider.abstract.query_params.QueryParams`
- Data must inherit from `openbb_core.provider.abstract.data.Data`
- All fields on Data must be Optional or have defaults (OpenBB convention)

### File Structure After Phase 25
```
src/liquidity/openbb_ext/
├── __init__.py                  (existing, no changes)
├── workspace_app.py             (existing, no changes)
├── provider.py                  (NEW: Provider registration)
├── models/
│   ├── __init__.py
│   ├── net_liquidity.py         (QueryParams + Data + Fetcher)
│   ├── global_liquidity.py      (QueryParams + Data + Fetcher)
│   └── stealth_qe.py            (QueryParams + Data + Fetcher)
```

### Testing Strategy
- Unit tests mock the calculator to verify TET pipeline
- Integration test: `uv pip install -e . && python -c "from openbb import obb; print(obb.liquidity)"`
- No vcrpy cassettes needed (calculators are already tested independently)

## Data Source Frequencies
Same as Phase 24 analysis — calculators handle data freshness internally.
