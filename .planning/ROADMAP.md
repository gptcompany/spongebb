# Roadmap: Global Liquidity Monitor (OpenBB)

## Overview

Build a FAANG-grade global liquidity monitoring system from the ground up. Start with Fed data (Hayes formula core), expand to global CBs, add market indicators, implement liquidity calculations and regime classification, then deliver via API and dashboards with alerting.

## Domain Expertise

None

## Milestones

- ✅ [v1.0 MVP](milestones/v1.0-ROADMAP.md) (Phases 1-10) — SHIPPED 2026-02-04
- ✅ [v2.0 Advanced Analytics](milestones/v2.0-ROADMAP.md) (Phases 11-15) — SHIPPED 2026-02-06
- 🚧 **v3.0 Commodity Intelligence** (Phases 16-21) — IN PROGRESS

## Phases Summary

**v1.0 MVP (Phases 1-10):** Foundation, Global CB Collectors, Rates & FX, Market Indicators, Capital Flows, Credit & BIS, Liquidity Calculations, Analysis, Calendar & API, Visualization

**v2.0 Advanced Analytics (Phases 11-15):** High-Frequency Data, Nowcasting, Risk Metrics, News Intelligence, Backtesting

**v3.0 Commodity Intelligence (Phases 16-21):** EIA Oil Data, CFTC Positioning, Oil Term Structure, Real Rates, Commodity News, Supply-Demand Model

## Phase Details

### Phase 1: Foundation & Core Data
**Goal**: Project scaffolding and Fed balance sheet data collection (Hayes formula inputs)
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-12, DATA-13, DATA-14, DATA-15
**Research**: Unlikely (FRED API well-documented, standard Python patterns)
**Plans**: TBD

Plans:
- [x] 01-01: Project scaffolding (uv, OpenBB, QuestDB, structure)
- [x] 01-02: FRED API collector base + Fed balance sheet (WALCL, TGA, RRP)
- [x] 01-03: MOVE, VIX, yield curve, credit spreads collectors

### Phase 2: Global CB Collectors
**Goal**: Complete Tier 1 central bank coverage (>85% global flows)
**Depends on**: Phase 1
**Requirements**: DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07
**Research**: Likely (ECB SDW API, BoJ API, PBoC scraping patterns)
**Research topics**: ECB SDW API authentication, BoJ data access, PBoC data scraping strategy
**Plans**: TBD

Plans:
- [x] 02-01: ECB/BoJ via FRED (ECBASSETSW, JPNASSETS)
- [x] 02-02: BoC collector (Valet API)
- [x] 02-03: BoE collector (multi-tier fallback)
- [x] 02-04: SNB collector (data.snb.ch CSV)
- [x] 02-05: PBoC collector (FRED fallback)

### Phase 3: Overnight Rates & FX
**Goal**: Overnight rate monitoring and FX collectors for carry trade signals
**Depends on**: Phase 1
**Requirements**: DATA-08, DATA-09, DATA-10, DATA-11, FX-01, FX-02, FX-03, FX-04
**Research**: Likely (NY Fed Data Hub API, BoC/BoE rate APIs)
**Research topics**: NY Fed Data Hub SOFR endpoint, ECB €STR API, BoE SONIA API, BoC CORRA API
**Plans**: 3 plans in 1 wave (all parallel)

Plans:
- [x] 03-01: SOFR collector (NY Fed + FRED fallback) | priority:high | effort:M
- [x] 03-02: €STR, SONIA, CORRA collectors + rate differentials | priority:high | effort:M
- [x] 03-03: FX collectors (DXY, major pairs via yfinance) | priority:high | effort:M

Note: FX-05 (IMF COFER) moved to Phase 5 - quarterly data fits better with Capital Flows.

### Phase 4: Market Indicators
**Goal**: Commodities collectors for economic signals
**Depends on**: Phase 1
**Requirements**: CMDTY-01, CMDTY-02, CMDTY-03, CMDTY-04, CMDTY-05
**Research**: Unlikely (Yahoo Finance, standard commodity APIs)
**Plans**: TBD

Plans:
- [x] 04-01: Commodity collector (gold, silver, copper, WTI, Brent)
- [x] 04-02: ETF flows collector (GLD, SLV, USO, CPER, DBA)

### Phase 5: Capital Flows & Stress
**Goal**: Capital flow tracking and funding market stress indicators
**Depends on**: Phase 2, Phase 3
**Requirements**: FLOW-01, FLOW-02, FLOW-03, FLOW-04, FX-05, STRESS-01, STRESS-02, STRESS-03, STRESS-04
**Research**: Likely (TIC data format, cross-currency basis sources, IMF COFER API)
**Research topics**: US Treasury TIC API, Fed custody data, cross-currency basis data sources, IMF SDMX/DBnomics
**Plans**: TBD

Plans:
- [x] 05-01: TIC data collector (Treasury CSV + FRED fallback) | wave:1 | effort:M
- [x] 05-02: Fed custody collector (WSEFINTL1, WMTSECL1, WFASECL1) | wave:1 | effort:M
- [x] 05-03: Stress indicators (SOFR-OIS, percentiles, repo, CP spreads) | wave:1 | effort:M
- [x] 05-04: Risk ETF flows (SPY, TLT, HYG, IEF, LQD) | wave:1 | effort:M
- [x] 05-05: IMF COFER collector (DBnomics API) | wave:1 | effort:M

### Phase 6: Credit & BIS Data
**Goal**: Credit market monitoring and BIS Eurodollar system tracking
**Depends on**: Phase 1
**Requirements**: CREDIT-01, CREDIT-02, CREDIT-03, CREDIT-04, FLOW-05, FLOW-06
**Research**: Likely (BIS SDMX API, SLOOS data access)
**Research topics**: BIS SDMX API endpoints, International Banking Statistics, SLOOS historical data
**Plans**: TBD

Plans:
- [x] 06-01: Credit market collectors (SLOOS survey, CP rates)
- [x] 06-02: BIS collectors (International Banking Statistics via bulk CSV)
- [x] 06-03: Registration and integration tests

### Phase 7: Liquidity Calculations
**Goal**: Core liquidity index calculations and Stealth QE score
**Depends on**: Phase 2, Phase 5
**Requirements**: CALC-01, CALC-02, CALC-03, CALC-04, ANLYS-02
**Research**: Unlikely (port from Apps Script v3.4.1, internal calculation logic)
**Plans**: TBD

Plans:
- [x] 07-01: Net Liquidity Index (Hayes formula: WALCL - TGA - RRP)
- [x] 07-02: Global Liquidity Index (Fed + ECB + BoJ + PBoC in USD)
- [x] 07-03: Stealth QE Score (port from Apps Script)
- [x] 07-04: Double-entry validation and >85% coverage verification

### Phase 8: Analysis & Correlations
**Goal**: Regime classification and cross-asset correlation engine
**Depends on**: Phase 7
**Requirements**: ANLYS-01, CORR-01, CORR-02, CORR-03, CORR-04, CORR-05
**Research**: Unlikely (internal analysis patterns)
**Plans**: TBD

Plans:
- [x] 08-01: Regime classifier (EXPANSION/CONTRACTION binary, intensity 0-100)
- [x] 08-02: Correlation engine (BTC, SPX, GOLD, TLT, DXY, COPPER, HYG)
- [x] 08-03: Alert engine (regime shift, correlation breakdown/surge)

### Phase 9: Calendar & API
**Goal**: Calendar effects tracking and FastAPI REST server
**Depends on**: Phase 7, Phase 8
**Requirements**: CAL-01, CAL-02, CAL-03, CAL-04, CAL-05, API-01, API-02, API-03, API-04, API-05, API-06, API-07, API-08, API-09
**Research**: Unlikely (FastAPI standard patterns)
**Plans**: TBD

Plans:
- [x] 09-01: Calendar effects (auctions, month-end, tax dates, Fed meetings) | wave:1 | effort:L
- [x] 09-02: FastAPI server setup and core endpoints | wave:1 | effort:L
- [x] 09-03: Additional API endpoints (FX, stress, correlations, calendar) | wave:2 | effort:M
- [x] 09-04: Docker deployment (Dockerfile, docker-compose) | wave:2 | effort:M

### Phase 10: Visualization & Alerting
**Goal**: Plotly dashboards, Discord alerting, and quality validation
**Depends on**: Phase 9
**Requirements**: VIZ-01, VIZ-02, VIZ-03, VIZ-04, VIZ-05, VIZ-06, VIZ-07, VIZ-08, ALERT-01, ALERT-02, ALERT-03, ALERT-04, QA-01, QA-02, QA-03, QA-04, QA-05, QA-06, QA-07, QA-08, QA-09, QA-10
**Research**: Unlikely (Plotly Dash standard patterns, Discord webhook standard)
**Plans**: TBD

Plans:
- [x] 10-01: Core Plotly dashboard (Net/Global Liquidity, regime) | wave:1 | effort:L
- [x] 10-02: Extended dashboard panels (FX, commodities, stress, flows) | wave:2 | effort:L
- [x] 10-03: Discord alerting (regime changes, stress alerts, DXY moves) | wave:2 | effort:M
- [x] 10-04: Quality & validation system (freshness, anomalies, cross-validation) | wave:1 | effort:L
- [x] 10-05: HTML export and data quality indicators | wave:3 | effort:M

### Phase 11: High-Frequency Data Layer
**Goal**: Reduce data lag from weekly to daily, add missing critical indicators
**Depends on**: Phase 10
**Requirements**: HF-01 (TGA daily), HF-02 (NY Fed APIs), HF-03 (China proxies), HF-04 (Cross-currency basis), HF-05 (Stablecoins), HF-06 (Credit proxies)
**Research**: Likely (US Treasury FiscalData API, NY Fed Markets API, akshare library, DefiLlama API)
**Research topics**: DTS API structure, NY Fed swap lines endpoint, SHIBOR/DR007 via akshare, EUR/USD basis sources

Plans:
- [x] 11-01: TGA Daily collector (US Treasury FiscalData API) | wave:1 | effort:M
- [x] 11-02: NY Fed collectors (RRP daily, SOMA, Swap Lines) | wave:1 | effort:M
- [x] 11-03: China HF proxies (DR007, SHIBOR via akshare) | wave:1 | effort:M
- [x] 11-04: Cross-currency basis collector (ECB/CME data) | wave:2 | effort:L
- [x] 11-05: Stablecoin supply collector (DefiLlama API) | wave:2 | effort:M
- [x] 11-06: Credit card proxy collectors (FRED consumer series) | wave:2 | effort:M

### Phase 12: Nowcasting & Forecasting
**Goal**: Estimate current/future liquidity before official releases
**Depends on**: Phase 11
**Requirements**: NOW-01 (Kalman nowcast), NOW-02 (PBoC estimator), NOW-03 (Regime forecaster), NOW-04 (Correlation predictor)
**Research**: Likely (statsmodels state-space, hmmlearn, filterpy)
**Research topics**: Kalman filter for macro nowcasting, Markov switching regression, Dynamic Factor Models

Plans:
- [ ] 12-01: Liquidity nowcast engine (Kalman filter on HF proxies) | wave:1 | effort:L
- [ ] 12-02: PBoC balance sheet estimator (SHIBOR/DR007 regression) | wave:1 | effort:M
- [ ] 12-03: Regime forecaster (HMM + LSTM) | wave:2 | effort:L
- [ ] 12-04: Correlation trend predictor (rolling beta forecast) | wave:2 | effort:M

### Phase 13: Risk Metrics
**Goal**: Professional risk analytics for portfolio management
**Depends on**: Phase 12
**Requirements**: RISK-01 (Historical VaR), RISK-02 (Parametric VaR), RISK-03 (CVaR), RISK-04 (Liquidity-adjusted), RISK-05 (Regime VaR)
**Research**: Likely (riskfolio-lib, quantstats)
**Research topics**: VaR methodologies, Expected Shortfall calculation, regime-conditional risk

Plans:
- [x] 13-01: Historical VaR calculator (95%, 99% confidence) | wave:1 | effort:M
- [x] 13-02: Parametric VaR (Normal/t-distribution) | wave:1 | effort:M
- [x] 13-03: CVaR / Expected Shortfall | wave:1 | effort:S
- [x] 13-04: Liquidity-adjusted risk metrics | wave:2 | effort:M
- [x] 13-05: Regime-conditional VaR (Expansion vs Contraction) | wave:2 | effort:M

### Phase 14: News Intelligence
**Goal**: Early warning via CB communications, FOMC statement analysis, and news monitoring
**Depends on**: Phase 11
**Requirements**: NEWS-01 (RSS aggregator), NEWS-02 (NLP translation), NEWS-03 (Sentiment analyzer), NEWS-04 (Breaking alerts), NEWS-05 (Dashboard panel), NEWS-06 (Statement scraper), NEWS-07 (Statement diff), NEWS-08 (Diff UI), NEWS-09 (Real-time webhook)
**Research**: Likely (finBERT, Helsinki NLP models, RSS parsing, difflib)
**Research topics**: finBERT financial sentiment, Chinese/German/Japanese translation models, RSS feed parsing, FOMC statement diff analysis

Plans:
- [x] 14-01: RSS feed aggregator (PBoC, ECB, Fed, BoJ) | wave:1 | effort:M
- [x] 14-02: NLP translation pipeline (CN+DE+JP+FR via Helsinki-NLP) | wave:1 | effort:M
- [x] 14-03: CB speech sentiment analyzer (finBERT + Qwen3) | wave:2 | effort:L
- [x] 14-04: Breaking news keyword alerts | wave:2 | effort:M
- [x] 14-05: News dashboard panel integration | wave:3 | effort:M
- [x] 14-06: FOMC Statement Scraper (Fed website + GitHub fallback) | wave:1 | effort:M
- [x] 14-07: Statement Diff Engine (word-level, hawkish/dovish scoring) | wave:1 | effort:M
- [x] 14-08: Statement Diff UI (Bloomberg-style side-by-side) | wave:2 | effort:M
- [x] 14-09: Real-time Statement Webhook (RSS→diff→Discord, <60s latency) | wave:3 | effort:L

### Phase 15: Backtesting Engine
**Goal**: Validate signal quality and strategy performance
**Depends on**: Phase 13
**Requirements**: BT-01 (Historical loader), BT-02 (Signal generator), BT-03 (Strategy backtester), BT-04 (Performance metrics), BT-05 (Monte Carlo), BT-06 (Regime analysis)
**Research**: Likely (quantstats, pyfolio patterns)
**Research topics**: Backtesting frameworks, Monte Carlo simulation, regime-based P&L attribution

Plans:
- [x] 15-01: Historical data loader (2010-present via FRED/archives) | wave:1 | effort:L
- [x] 15-02: Signal generator (regime-based long/short signals) | wave:1 | effort:M
- [x] 15-03: Strategy backtester (equity, BTC, multi-asset) | wave:2 | effort:L
- [x] 15-04: Performance metrics (Sharpe, Sortino, MaxDD, Calmar) | wave:2 | effort:M
- [x] 15-05: Monte Carlo simulation (distribution of outcomes) | wave:3 | effort:L
- [x] 15-06: Regime transition P&L analysis | wave:3 | effort:M

---

## 🚧 v3.0 Commodity Intelligence (In Progress)

**Milestone Goal:** Transform oil from "price tracker" to "macro liquidity indicator" with supply fundamentals, positioning data, and market structure analysis.

### Phase 16: EIA Oil Data
**Goal**: Weekly petroleum supply data (inventory, production, refinery utilization)
**Depends on**: Phase 15
**Requirements**: OIL-01 (EIA Weekly), OIL-02 (Cushing inventory), OIL-03 (Refinery runs)
**Research**: Likely (EIA API structure, FRED fallback series)
**Research topics**: EIA FiscalData API, petroleum status report structure, DPROUST/WTISPLC series

Plans:
- [x] 16-01: EIA Weekly Petroleum collector (inventory, production) | wave:1 | effort:M
- [x] 16-02: Cushing storage tracker (WTI delivery point) | wave:1 | effort:S
- [x] 16-03: Refinery utilization collector | wave:1 | effort:S
- [x] 16-04: Dashboard panel integration | wave:2 | effort:M

### Phase 17: CFTC Positioning
**Goal**: Commitment of Traders reports for WTI, copper, gold positioning
**Depends on**: Phase 16
**Requirements**: POS-01 (COT reports), POS-02 (Commercials vs specs), POS-03 (Extremes detection)
**Research**: Likely (CFTC API structure, disaggregated reports)
**Research topics**: CFTC JSON API endpoint, COT report fields, net positioning calculation

Plans:
- [ ] 17-01: CFTC COT collector (weekly disaggregated) | wave:1 | effort:M
- [ ] 17-02: Positioning metrics (commercial/non-commercial ratio) | wave:1 | effort:M
- [ ] 17-03: Extreme positioning alerts (percentile thresholds) | wave:2 | effort:M
- [ ] 17-04: Dashboard positioning heatmap | wave:2 | effort:M

### Phase 18: Oil Term Structure
**Goal**: Contango/backwardation signals from futures curve
**Depends on**: Phase 16
**Requirements**: STRUCT-01 (Front-back spread), STRUCT-02 (Curve shape), STRUCT-03 (Roll yield)
**Research**: Likely (CME futures data, yfinance continuous contracts)
**Research topics**: WTI futures chain via yfinance, CLF/CLG contract symbols, calendar spread calculation

Plans:
- [x] 18-01: Futures curve collector (front 6 contracts) | wave:1 | effort:M
- [x] 18-02: Contango/backwardation indicator | wave:1 | effort:M
- [x] 18-03: Roll yield calculator | wave:2 | effort:S
- [x] 18-04: Term structure visualization | wave:2 | effort:M

### Phase 19: Real Rates
**Goal**: Real rates tracking and oil-rates correlation analysis
**Depends on**: Phase 16
**Requirements**: RATES-01 (TIPS yield), RATES-02 (BEI), RATES-03 (Oil correlation)
**Research**: Unlikely (FRED has all series)
**Research topics**: DFII10, T10YIE, correlation rolling window

Plans:
- [x] 19-01: Real rates collector (10Y TIPS, 5Y TIPS) | wave:1 | effort:S
- [x] 19-02: Breakeven inflation calculator | wave:1 | effort:S
- [x] 19-03: Oil-real rates correlation engine | wave:1 | effort:M
- [x] 19-04: Inflation expectations dashboard | wave:2 | effort:M

### Phase 20: Commodity News
**Goal**: Oil-specific news intelligence (OPEC, sanctions, weather)
**Depends on**: Phase 14 (extends news infrastructure)
**Requirements**: NEWS-10 (Oil RSS), NEWS-11 (OPEC calendar), NEWS-12 (Weather events)
**Research**: Unlikely (extends Phase 14 patterns)
**Research topics**: Reuters/Platts RSS feeds, NOAA hurricane API, OPEC meeting calendar

Plans:
- [ ] 20-01: Oil RSS feeds (Reuters, Platts, Argus, OPEC) | wave:1 | effort:M
- [ ] 20-02: OPEC meeting calendar integration | wave:1 | effort:S
- [ ] 20-03: Hurricane/weather impact tracker (NOAA) | wave:2 | effort:M
- [ ] 20-04: Supply disruption keyword alerts | wave:2 | effort:M

### Phase 21: Supply-Demand Model
**Goal**: Oil balance calculator with inventory forecasts
**Depends on**: Phase 16, Phase 17, Phase 20
**Requirements**: MODEL-01 (Balance calc), MODEL-02 (Forecast), MODEL-03 (Regime integration)
**Research**: Unlikely (internal calculation logic)
**Research topics**: EIA supply/demand balance, inventory forecast models

Plans:
- [ ] 21-01: Supply-demand balance calculator | wave:1 | effort:M
- [ ] 21-02: Inventory forecast (YoY, seasonal adj) | wave:1 | effort:M
- [ ] 21-03: Oil regime signals (tight/loose) | wave:2 | effort:M
- [ ] 21-04: Integration with liquidity regime classifier | wave:2 | effort:L

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Core Data | 3/3 | Complete | 2026-01-21 |
| 2. Global CB Collectors | 5/5 | Complete | 2026-01-22 |
| 3. Overnight Rates & FX | 3/3 | Complete | 2026-01-23 |
| 4. Market Indicators | 2/2 | Complete | 2026-01-23 |
| 5. Capital Flows & Stress | 5/5 | Complete | 2026-01-23 |
| 6. Credit & BIS Data | 3/3 | Complete | 2026-01-24 |
| 7. Liquidity Calculations | 4/4 | Complete | 2026-01-24 |
| 8. Analysis & Correlations | 3/3 | Complete | 2026-01-26 |
| 9. Calendar & API | 4/4 | Complete | 2026-02-04 |
| 10. Visualization & Alerting | 5/5 | Complete | 2026-02-04 |
| 11. High-Frequency Data Layer | 6/6 | Complete | 2026-02-05 |
| 12. Nowcasting & Forecasting | 4/4 | Complete | 2026-02-05 |
| 13. Risk Metrics | 5/5 | Complete | 2026-02-05 |
| 14. News Intelligence | 9/9 | Complete | 2026-02-06 |
| 15. Backtesting Engine | 6/6 | Complete | 2026-02-06 |
| 16. EIA Oil Data | 4/4 | Complete | 2026-02-06 |
| 17. CFTC Positioning | 4/4 | Complete | 2026-02-06 |
| 18. Oil Term Structure | 4/4 | Complete | 2026-02-06 |
| 19. Real Rates | 4/4 | Complete | 2026-02-06 |
| 20. Commodity News | 0/4 | Not started | - |
| 21. Supply-Demand Model | 0/4 | Not started | - |

---
*Created: 2026-01-21*
*Last updated: 2026-02-06*
*Milestone 3 (v3.0): Phases 16-21 - Commodity Intelligence*
