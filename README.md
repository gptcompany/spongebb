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
