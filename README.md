<p align="center">
  <img src="https://img.shields.io/badge/🧽-SpongeBB-yellow?style=for-the-badge&labelColor=blue" alt="SpongeBB"/>
</p>

<h1 align="center">SpongeBB</h1>
<p align="center"><em>Who lives in a pineapple under the sea of liquidity?</em></p>

<p align="center">
  <a href="https://github.com/gptcompany/spongebb/actions/workflows/ci.yml"><img src="https://github.com/gptcompany/spongebb/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/gptprojectmanager/2f424df721ea43fb25188b03df5a8317/raw/spongebb-coverage.json" alt="Coverage">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square&logo=python" alt="Python">
  <a href="https://github.com/gptcompany/spongebb/blob/main/LICENSE"><img src="https://img.shields.io/github/license/gptcompany/spongebb?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/github/last-commit/gptcompany/spongebb?style=flat-square" alt="Last Commit">
  <img src="https://img.shields.io/github/issues/gptcompany/spongebb?style=flat-square" alt="Issues">
</p>

---

**SpongeBB** soaks up global central bank liquidity so you don't have to.

FAANG-grade macro liquidity tracker based on [Arthur Hayes' framework](https://cryptohayes.medium.com/). Tracks the Fed, ECB, BoJ, and PBoC balance sheets, then squeezes out regime signals, stealth QE scores, and net liquidity indicators — all in real-time. Think of it as your Bikini Bottom early warning system for when the money printer goes brrr (or stops).

## What's in the Krabby Patty?

- **Net Liquidity Index** — `WALCL - TGA - RRP` (the secret formula)
- **Global Liquidity Index** — Fed + ECB + BoJ + PBoC aggregated in USD
- **Stealth QE Score** — detects hidden liquidity injections (sneaky, like Plankton)
- **Regime Classification** — EXPANSION / CONTRACTION with confidence scoring
- **Risk Metrics** — VaR, CVaR, funding stress indicators
- **Nowcasting & Forecasting** — HMM regime detection, Kalman filtering, LSTM
- **News Intelligence** — RSS feeds + NLP sentiment from central bank communications
- **NautilusTrader Integration** — macro filter for algorithmic trading strategies

## Quick Start

```bash
# Install dependencies
uv sync

# Run API server (port 8003)
uv run uvicorn liquidity.api:app --reload --port 8003

# Docker (production)
docker compose up -d
curl http://localhost:8003/health
```

## Dashboard

```bash
# Build and run dashboard container
make build
make up
# Open http://localhost:8050

# Development mode with hot reload
make up-dev
```

## Testing

```bash
# Unit tests (local)
uv run pytest tests/unit -v

# Unit tests (containerized — avoids sandbox limits)
make test-python

# Visual regression (Playwright)
make test-visual

# Coverage
uv run pytest tests/unit --cov=src --cov-report=html
```

## Architecture

```
src/liquidity/
  api/          # FastAPI REST server (port 8003)
  collectors/   # Data collectors (FRED, ECB, BoJ, PBoC, Yahoo)
  core/         # Net liquidity, global liquidity, stealth QE engines
  dashboard/    # Plotly Dash interactive dashboard
  models/       # Pydantic models and data schemas
  openbb_ext/   # OpenBB Provider extension (3 Fetcher adapters)
  risk/         # VaR, CVaR, portfolio risk analytics
  storage/      # QuestDB time-series storage
  forecast/     # HMM, Kalman, LSTM nowcasting
  news/         # RSS + NLP central bank news intelligence
```

## Data Sources

| Source | Data | Frequency |
|--------|------|-----------|
| FRED API | Fed, ECB, BoJ, rates, bonds | Daily/Weekly |
| ECB SDW | ECB balance sheet | Weekly |
| NY Fed | SOFR, RRP, repo | Daily |
| Yahoo Finance | MOVE, VIX, FX | Real-time |
| BIS SDMX | Eurodollar, intl banking | Quarterly |

## CI/CD

Push to `main` triggers:
1. **CI** (ubuntu-latest) — lint, test, coverage badge update
2. **Deploy** (self-hosted) — Docker build + rolling restart on Workstation

## API Docs

With the server running, visit:
- Swagger UI: `http://localhost:8003/docs`
- ReDoc: `http://localhost:8003/redoc`

## License

MIT

---

<p align="center"><em>"I'm ready! I'm ready!" — SpongeBB, every time the Fed prints money</em></p>
