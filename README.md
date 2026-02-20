# Global Liquidity Monitor

FAANG-grade macro liquidity tracking using OpenBB SDK, based on Arthur Hayes' framework.

## Quick Start

```bash
# Development
uv run uvicorn liquidity.api:app --reload

# Docker (API)
docker compose up -d
curl http://localhost:8000/health
```

## Dashboard Container (Step-by-Step)

```bash
# 1) Build immagini necessarie
make build

# 2) Avvia dashboard container
make up

# 3) Apri dashboard
# http://localhost:8050

# 4) Log runtime
make logs

# 5) Stop
make down
```

## Runtime Tests in Container (Step-by-Step)

```bash
# Python unit tests (inside test-runtime image)
make test-python

# Visual regression (Playwright + dashboard test deterministica)
make test-visual

# Aggiorna baseline visual (quando cambi UI intenzionalmente)
make test-visual-update
```

Note: questo workflow evita i limiti runtime del sandbox (`/dev/urandom`) eseguendo i test in container.

## Features

- Net Liquidity Index (WALCL - TGA - RRP)
- Global Liquidity Index (Fed + ECB + BoJ + PBoC)
- Stealth QE Score detection
- Regime Classification (EXPANSION/CONTRACTION)

## Visual E2E (Playwright)

```bash
# Install JS test dependencies
npm install

# Install browser binaries
npx playwright install chromium

# Create/refresh visual baselines
npm run test:visual:update

# Run visual regression checks
npm run test:visual
```

Playwright tests run the dashboard in deterministic fallback mode (fixed timestamp, no live API dependency) to reduce snapshot flakiness in CI.
