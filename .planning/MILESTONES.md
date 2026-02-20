# Project Milestones: Global Liquidity Monitor

## v4.0 Consumer Credit Risk (Shipped: 2026-02-20)

**Delivered:** Consumer-credit-risk intelligence layer integrated into data collection and dashboard.

**Phases completed:** 22 (3 plans total)

**Key accomplishments:**

- Consumer credit risk collector (`consumer_credit_risk.py`)
- Tracking di consumer credit ex-student loans
- Debt-in-default proxy (delinquency-based)
- Mortgage losses + loan loss reserves metrics
- USD liquidity proxy index (Bloomberg-like)
- Dashboard panel dedicato (XLP/XLY, AXP vs IGV, sensitive stocks)
- Playwright visual regression baseline (desktop/mobile) + CI workflow
- Operational runbook GSD (container-first execution + runtime test strategy host/escalated)
- Direct container implementation (`Dockerfile` targets + compose services + Makefile runbook)

**Stats:**

- 1 phase, 3 plans
- 2 nuovi moduli core
- 2 nuovi file test dedicati
- Commit release (core): `9a229d7`
- Commit hardening (visual regression): `4d363d4`, `37d6ede`
- Commit operational docs (GSD 22-02): `1d05b86`
- Commit operational docs trace: `382b36b`

**What's next:** validazione smoke test completa dei target container o definizione v5.0 scope

---

## v3.0 Commodity Intelligence (Shipped: 2026-02-07)

**Delivered:** Oil intelligence stack completo (supply fundamentals, positioning, term structure, real rates, commodity news).

**Phases completed:** 16-21 (24 plans total)

**Key accomplishments:**

- EIA Weekly Petroleum data (inventory, production, refinery utilization)
- CFTC COT Reports (commercial vs speculator positioning, extremes detection)
- Oil term structure (contango/backwardation, roll yield signals)
- Real rates tracking (TIPS yields, oil-rates correlation)
- Commodity news intelligence (OPEC, weather, sanctions, supply disruptions)
- Supply-demand balance calculator with regime integration

**Git range:** `1280df5` → `d09caf3`

**What's next:** v4.0 Consumer Credit Risk ✅

---

## v2.0 Advanced Analytics (Shipped: 2026-02-06)

**Delivered:** Advanced analytics layer with high-frequency data, nowcasting, risk metrics, news intelligence, and backtesting engine.

**Phases completed:** 11-15 (21 plans total)

**Key accomplishments:**

- High-frequency data layer (daily TGA, China proxies, stablecoins)
- Nowcasting engine with Kalman filters and HMM regime detection
- Professional risk metrics (VaR, CVaR, Regime VaR)
- News intelligence with multi-language NLP and FOMC statement analysis
- Backtesting engine with VectorBT, Monte Carlo, and regime attribution

**Stats:**

- ~8,000 new lines of Python
- 5 phases, 21 plans
- 2 days from start to ship
- New dependencies: vectorbt, quantstats, hmmlearn, torch

**Git range:** `59f294b` → `fdfefa8`

**What's next:** v3.0 Commodity Intelligence (oil supply fundamentals, positioning, market structure)

---

## v1.0 MVP (Shipped: 2026-02-04)

**Delivered:** Complete global liquidity monitoring system with Fed balance sheet tracking, global CB coverage, regime classification, and dashboard visualization.

**Phases completed:** 1-10 (35 plans total)

**Key accomplishments:**

- Fed balance sheet data collection (Hayes formula: WALCL - TGA - RRP)
- Global CB coverage >85% (Fed, ECB, BoJ, PBoC, BoE, SNB, BoC)
- Regime classification (EXPANSION/CONTRACTION) with intensity scoring
- Cross-asset correlation engine (BTC, SPX, Gold, TLT, DXY)
- FastAPI REST server with 12 endpoints
- Plotly Dash dashboard with 10 panels
- Discord alerting for regime shifts and stress events

**Stats:**

- ~15,000 lines of Python
- 10 phases, 35 plans
- 14 days from start to ship

**Git range:** Initial commit → `bf0294b`

**What's next:** v2.0 Advanced Analytics ✅

---

*Last updated: 2026-02-20 — v4.0 Consumer Credit Risk + Plan 22-03 container implementation*
