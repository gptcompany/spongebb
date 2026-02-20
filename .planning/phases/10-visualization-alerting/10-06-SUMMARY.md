# Plan 10-06 Summary: Dashboard Visual Regression

**Status:** ✅ Complete  
**Date:** 2026-02-20  
**Scope:** Visual regression + CI + deterministic dashboard mode + MCP workflow

## Delivered

### 1) Playwright Visual Test Stack
- `package.json` + `package-lock.json` con `@playwright/test`
- `playwright.config.js` con:
  - progetti `chromium-desktop`, `chromium-mobile`
  - `webServer` integrato su dashboard
  - env deterministici (`LIQUIDITY_DASHBOARD_FORCE_FALLBACK`, `LIQUIDITY_DASHBOARD_FIXED_NOW`)
- test: `tests/visual/dashboard.visual.spec.js`
- baseline snapshots Linux:
  - `dashboard-above-fold-chromium-desktop-linux.png`
  - `dashboard-above-fold-chromium-mobile-linux.png`

### 2) CI Visual Regression
- Nuovo workflow: `.github/workflows/visual-regression.yml`
- Trigger su PR/push e manual dispatch
- Steps:
  - `uv sync --frozen --dev`
  - `npm ci`
  - `npx playwright install --with-deps chromium`
  - `npm run test:visual`
- Artifact upload sempre attivo: `playwright-report`, `test-results`

### 3) Dashboard Deterministic Mode
- `src/liquidity/dashboard/callbacks_main.py`:
  - helper `_env_flag()`
  - helper `_dashboard_now()`
  - fallback forzato con `LIQUIDITY_DASHBOARD_FORCE_FALLBACK`
  - timestamp fisso con `LIQUIDITY_DASHBOARD_FIXED_NOW`
- Risultato: snapshot stabili e indipendenti da API live.

### 4) Developer Documentation
- `README.md` aggiornato con comandi visual E2E.
- `.gitignore` aggiornato per output Playwright e `node_modules`.

## Validation Results

- `npm run test:visual:update` → ✅ 2 test pass, baseline generati
- `npm run test:visual` → ✅ 2 test pass
- `PYTHONPATH=src .venv/bin/pytest tests/unit/test_dashboard/test_callbacks.py -q` → ✅ 4 test pass

## Commits

- `4d363d4` — Add Playwright visual regression tests with CI workflow
- `37d6ede` — Trigger visual workflow on package lock updates

## Operational Notes

- Playwright MCP è stato aggiunto alla configurazione globale Codex.
- Per usare MCP in sessione tool corrente è necessario restart della sessione Codex.
