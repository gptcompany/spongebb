# Global Liquidity Monitor

FAANG-grade macro liquidity tracking using OpenBB SDK, based on Arthur Hayes' framework.

## Quick Start

```bash
# Development
uv run uvicorn liquidity.api:app --reload

# Docker
docker compose up -d
curl http://localhost:8000/health
```

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
