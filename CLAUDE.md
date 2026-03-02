# CLAUDE.md

## Project Overview

**SpongeBB** — FAANG-grade macro liquidity tracking using OpenBB SDK.

Based on Arthur Hayes' framework for tracking central bank liquidity flows.
Formerly `openbb_liquidity`, now `spongebb` — soaking up central bank flows like a sponge.

## Tech Stack

- **Python**: 3.11+
- **Package Manager**: uv
- **Data Platform**: OpenBB SDK
- **Storage**: QuestDB (time-series)
- **Visualization**: Plotly Dash
- **API**: FastAPI
- **Frontend**: OpenBB Terminal Pro (SaaS at pro.openbb.co)

## Services

| Service | Porta | Comando | Descrizione |
|---------|-------|---------|-------------|
| SpongeBB API | 8003 | `make api-local` | REST API FastAPI (14 endpoint) |
| Workspace | 6900 | `make workspace-local` | OpenBB Workspace backend (19 widget) |
| Dashboard | 8050 | `make up` | Plotly Dash (Docker) |

### Avvio locale (sviluppo)

```bash
# PREREQUISITO: setup credenziali OpenBB (una tantum)
make setup-credentials

# API locale (foreground, con dotenvx per decifrazione .env)
make api-local

# Workspace locale (foreground)
make workspace-local

# Background (append & e redirect log)
dotenvx run -- uv run uvicorn liquidity.api:app --host 0.0.0.0 --port 8003 > /tmp/spongebb-api.log 2>&1 &
dotenvx run -- uv run openbb-api --app liquidity.openbb_ext.workspace_app:app --host 0.0.0.0 --port 6900 > /tmp/spongebb-workspace.log 2>&1 &
```

### Avvio Docker (produzione)

```bash
make api          # API Docker su porta 8003
make workspace    # Workspace Docker su porta 6900
make deploy       # Build + restart API
```

## Credenziali

### FRED API Key (obbligatoria)

La FRED API key e' cifrata con dotenvx nel `.env` del progetto.
Due modi per renderla disponibile a OpenBB:

1. **dotenvx run** (runtime): `dotenvx run -- uv run ...` decifra al volo
2. **user_settings.json** (persistente): `make setup-credentials` scrive in `~/.openbb_platform/user_settings.json`

Entrambi necessari per copertura completa:
- `dotenvx run` serve ai collector SpongeBB (via `get_settings()`)
- `user_settings.json` serve a OpenBB Platform internamente (query_executor)

### Variabili in `.env`

| Variabile | Uso |
|-----------|-----|
| `OPENBB_FRED_API_KEY` | FRED API key (letta da OpenBB e da Settings) |
| `LIQUIDITY_FRED_API_KEY` | Alias per Settings pydantic |

## OpenBB Terminal Pro

Terminal Pro NON e' self-hostable. E' il frontend SaaS di OpenBB.

### Connessione al Workspace

1. Accedi a `pro.openbb.co`
2. Settings > Data Connectors > Custom Backend
3. URL: `http://<WORKSTATION_IP>:6900` (es. `http://192.168.1.111:6900`)
4. I 19 widget vengono scoperti automaticamente da `/widgets.json`

### Widget disponibili

| Widget | Endpoint | Tipo |
|--------|----------|------|
| Net Liquidity Detail | `/liquidity/net` | table |
| Global Liquidity | `/liquidity/global` | table |
| Regime Current | `/regime/current` | table |
| Regime Combined | `/regime/combined` | table |
| Stealth QE | `/metrics/stealth-qe` | table |
| Stress Indicators | `/stress/indicators` | table |
| + 13 workspace metrics/charts | `/workspace/...` | vari |

## Key Formulas

### Net Liquidity Index (Hayes)
```
Net Liquidity = WALCL - TGA - RRP
```
- WALCL: Fed Total Assets
- TGA: Treasury General Account
- RRP: Reverse Repo

### Global Liquidity Index
```
Global = Fed + ECB + BoJ + PBoC (all in USD)
```

### Stealth QE Score
See: `.planning/reference/appscript_v3.4.1.md` for weights and thresholds.

## Data Sources

| Source | Data | Update Frequency |
|--------|------|------------------|
| FRED API | Fed, ECB, BoJ, rates, bonds | Daily/Weekly |
| ECB SDW | ECB balance sheet | Weekly |
| NY Fed | SOFR, RRP, repo data | Daily |
| Yahoo Finance | MOVE, VIX, FX | Real-time |
| BIS SDMX | Eurodollar, intl banking | Quarterly |

## Porte riservate

| Porta | Servizio |
|-------|----------|
| 8000 | UTXOracle API (riservata) |
| 8001 | LiquidationHeatmap |
| 8002 | LiquidationHeatmap |
| **8003** | **SpongeBB API** |
| 8050 | SpongeBB Dashboard |
| **6900** | **SpongeBB Workspace** |

## Development Rules

### ALWAYS
- Use `uv` for package management
- Type hints on all functions
- Async for IO-bound operations
- Validate data freshness before calculations
- Run with `dotenvx run --` for credential decryption

### NEVER
- Hardcode API keys (use dotenvx)
- Block event loop with sync IO
- Trust external data without validation
- Skip error handling on API calls
- Use port 8000, 8001, 8002 (reserved)

## CI/CD

```
Push to main --> CI (ubuntu-latest) --> Deploy (self-hosted)
```

- **CI** (`.github/workflows/ci.yml`): lint (ruff) + test (pytest) + coverage badge
- **Deploy** (`.github/workflows/deploy.yml`): Docker build + rolling restart
- **Coverage badge**: Gist `2f424df721ea43fb25188b03df5a8317`
- **Self-hosted runner**: `sam-workstation` (ID 47)

## Testing

```bash
# Unit tests (local)
uv run pytest tests/unit -v

# Unit tests (containerized)
make test-python

# Visual regression (Playwright)
make test-visual

# Coverage
uv run pytest tests/unit --cov=src --cov-report=html
```

## Reference

- **Apps Script v3.4.1**: `.planning/reference/appscript_v3.4.1.md`
- **Requirements**: `.planning/REQUIREMENTS.md`
- **Roadmap**: `.planning/ROADMAP.md`
