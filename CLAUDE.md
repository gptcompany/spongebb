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
| ECB SDW | ECB balance sheet, €STR | Weekly |
| NY Fed | SOFR, RRP, repo data | Daily |
| Yahoo Finance | MOVE, VIX, FX | Real-time |
| BIS SDMX | Eurodollar, intl banking | Quarterly |

## Development Rules

### ALWAYS
- Use `uv` for package management
- Type hints on all functions
- Async for IO-bound operations
- Validate data freshness before calculations

### NEVER
- Hardcode API keys (use SOPS)
- Block event loop with sync IO
- Trust external data without validation
- Skip error handling on API calls

## Testing

```bash
uv run pytest tests/ -v
uv run pytest tests/ --cov=src --cov-report=html
```

## Reference

- **Apps Script v3.4.1**: `.planning/reference/appscript_v3.4.1.md`
- **Requirements**: `.planning/REQUIREMENTS.md`
- **Roadmap**: `.planning/ROADMAP.md`
