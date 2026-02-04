# Roadmap: Global Liquidity Monitor (OpenBB)

## Overview

Build a FAANG-grade global liquidity monitoring system from the ground up. Start with Fed data (Hayes formula core), expand to global CBs, add market indicators, implement liquidity calculations and regime classification, then deliver via API and dashboards with alerting.

## Domain Expertise

None

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation & Core Data** - Project setup, FRED API, Fed balance sheet collectors
- [x] **Phase 2: Global CB Collectors** - ECB, BoJ, PBoC, BoE, SNB, BoC balance sheet collectors
- [x] **Phase 3: Overnight Rates & FX** - SOFR, €STR, SONIA, CORRA + FX pair collectors
- [x] **Phase 4: Market Indicators** - Commodities (gold, silver, copper, oil) + ETF flows
- [x] **Phase 5: Capital Flows & Stress** - TIC data, ETF flows, stress indicators
- [x] **Phase 6: Credit & BIS Data** - Credit markets, BIS Eurodollar/international banking
- [x] **Phase 7: Liquidity Calculations** - Net Liquidity, Global Liquidity, Stealth QE Score
- [x] **Phase 8: Analysis & Correlations** - Regime classifier, correlation engine
- [x] **Phase 9: Calendar & API** - Calendar effects, FastAPI REST server
- [x] **Phase 10: Visualization & Alerting** - Plotly dashboards, Discord alerts, QA validation
- [ ] **Phase 11: High-Frequency Data Layer** - TGA daily, NY Fed APIs, China proxies, stablecoins, cross-currency basis
- [ ] **Phase 12: Nowcasting & Forecasting** - Kalman filters, HMM regime detection, PBoC estimator
- [ ] **Phase 13: Risk Metrics** - VaR, CVaR, Expected Shortfall, Regime VaR
- [ ] **Phase 14: News Intelligence** - RSS aggregation, NLP translation, CB sentiment analysis
- [ ] **Phase 15: Backtesting Engine** - Historical loader, signal generator, strategy backtester

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
- [ ] 11-01: TGA Daily collector (US Treasury FiscalData API) | wave:1 | effort:M
- [ ] 11-02: NY Fed collectors (RRP daily, SOMA, Swap Lines) | wave:1 | effort:M
- [ ] 11-03: China HF proxies (DR007, SHIBOR via akshare) | wave:1 | effort:M
- [ ] 11-04: Cross-currency basis collector (ECB/CME data) | wave:2 | effort:L
- [ ] 11-05: Stablecoin supply collector (DefiLlama API) | wave:2 | effort:M
- [ ] 11-06: Credit card proxy collectors (FRED consumer series) | wave:2 | effort:M

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
- [ ] 13-01: Historical VaR calculator (95%, 99% confidence) | wave:1 | effort:M
- [ ] 13-02: Parametric VaR (Normal/t-distribution) | wave:1 | effort:M
- [ ] 13-03: CVaR / Expected Shortfall | wave:1 | effort:S
- [ ] 13-04: Liquidity-adjusted risk metrics | wave:2 | effort:M
- [ ] 13-05: Regime-conditional VaR (Expansion vs Contraction) | wave:2 | effort:M

### Phase 14: News Intelligence
**Goal**: Early warning via CB communications and news monitoring
**Depends on**: Phase 11
**Requirements**: NEWS-01 (RSS aggregator), NEWS-02 (NLP translation), NEWS-03 (Sentiment analyzer), NEWS-04 (Breaking alerts), NEWS-05 (Dashboard panel)
**Research**: Likely (finBERT, Helsinki NLP models, RSS parsing)
**Research topics**: finBERT financial sentiment, Chinese translation models, RSS feed parsing

Plans:
- [ ] 14-01: RSS feed aggregator (PBoC, ECB, Fed, BoJ) | wave:1 | effort:M
- [ ] 14-02: NLP translation pipeline (Chinese→English) | wave:1 | effort:M
- [ ] 14-03: CB speech sentiment analyzer (finBERT) | wave:2 | effort:L
- [ ] 14-04: Breaking news keyword alerts | wave:2 | effort:M
- [ ] 14-05: News dashboard panel integration | wave:3 | effort:M

### Phase 15: Backtesting Engine
**Goal**: Validate signal quality and strategy performance
**Depends on**: Phase 13
**Requirements**: BT-01 (Historical loader), BT-02 (Signal generator), BT-03 (Strategy backtester), BT-04 (Performance metrics), BT-05 (Monte Carlo), BT-06 (Regime analysis)
**Research**: Likely (quantstats, pyfolio patterns)
**Research topics**: Backtesting frameworks, Monte Carlo simulation, regime-based P&L attribution

Plans:
- [ ] 15-01: Historical data loader (2010-present via FRED/archives) | wave:1 | effort:L
- [ ] 15-02: Signal generator (regime-based long/short signals) | wave:1 | effort:M
- [ ] 15-03: Strategy backtester (equity, BTC, multi-asset) | wave:2 | effort:L
- [ ] 15-04: Performance metrics (Sharpe, Sortino, MaxDD, Calmar) | wave:2 | effort:M
- [ ] 15-05: Monte Carlo simulation (distribution of outcomes) | wave:3 | effort:L
- [ ] 15-06: Regime transition P&L analysis | wave:3 | effort:M

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
| 11. High-Frequency Data Layer | 0/6 | Planned | - |
| 12. Nowcasting & Forecasting | 0/4 | Planned | - |
| 13. Risk Metrics | 0/5 | Planned | - |
| 14. News Intelligence | 0/5 | Planned | - |
| 15. Backtesting Engine | 0/6 | Planned | - |

---
*Created: 2026-01-21*
*Last updated: 2026-02-04*
*Milestone 2 (v2.0): Phases 11-15 planned*
