# Requirements: Global Liquidity Monitor (OpenBB)

**Defined:** 2026-01-21
**Core Value:** Real-time regime classification — Know instantly whether we're in Expansionary, Neutral, or Contractionary liquidity regime to inform trading decisions.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Data Collection

- [ ] **DATA-01**: Collector retrieves Fed balance sheet data (WALCL, TGA, RRP) from FRED API
- [ ] **DATA-02**: Collector retrieves ECB balance sheet data from ECB SDW API
- [ ] **DATA-03**: Collector retrieves BoJ balance sheet data from FRED/BoJ API
- [ ] **DATA-04**: Collector retrieves PBoC balance sheet data (monthly lag accepted)
- [ ] **DATA-05**: Collector retrieves BoE balance sheet data from FRED API
- [ ] **DATA-06**: Collector retrieves SNB balance sheet data from SNB/FRED API
- [ ] **DATA-07**: Collector retrieves BoC balance sheet data from BoC/FRED API
- [ ] **DATA-08**: Collector retrieves SOFR rate from NY Fed Data Hub
- [ ] **DATA-09**: Collector retrieves €STR rate from ECB SDW API
- [ ] **DATA-10**: Collector retrieves SONIA rate from BoE API
- [ ] **DATA-11**: Collector retrieves CORRA rate from BoC API
- [ ] **DATA-12**: Collector retrieves MOVE index from Yahoo Finance
- [ ] **DATA-13**: Collector retrieves VIX index from Yahoo Finance
- [ ] **DATA-14**: Collector retrieves US Treasury yield curve from FRED API
- [ ] **DATA-15**: Collector retrieves credit spreads (IG, HY) from FRED API

### FX & Currency Flows

- [ ] **FX-01**: Collector retrieves DXY (Dollar Index) from Yahoo Finance/FRED
- [ ] **FX-02**: Collector retrieves USD/JPY rate for carry trade monitoring
- [ ] **FX-03**: Collector retrieves USD/CNY rate for yuan devaluation signals
- [ ] **FX-04**: Collector retrieves EUR/USD rate
- [ ] **FX-05**: Collector retrieves global FX reserves data from IMF COFER (quarterly)

### Commodities & Metals

- [ ] **CMDTY-01**: Collector retrieves Gold spot price (XAU/USD)
- [ ] **CMDTY-02**: Collector retrieves Gold ETF flows (GLD holdings)
- [ ] **CMDTY-03**: Collector retrieves Copper price ("Dr. Copper" economic indicator)
- [ ] **CMDTY-04**: Collector retrieves WTI Crude Oil price
- [ ] **CMDTY-05**: Collector retrieves Silver spot price (XAG/USD)

### Capital Flows

- [ ] **FLOW-01**: Collector retrieves TIC data (Treasury International Capital) from US Treasury
- [ ] **FLOW-02**: Collector retrieves foreign CB US Treasury holdings
- [ ] **FLOW-03**: Collector retrieves major ETF flows (SPY, TLT, GLD, HYG)
- [ ] **FLOW-04**: Collector retrieves Fed custody holdings for foreign CBs
- [ ] **FLOW-05**: Collector retrieves BIS International Banking Statistics (Eurodollar size, quarterly)
- [ ] **FLOW-06**: Collector retrieves BIS Locational Banking Statistics (cross-border USD flows)

### Stress Indicators

- [ ] **STRESS-01**: System calculates SOFR-OIS spread (funding market stress)
- [ ] **STRESS-02**: Collector retrieves cross-currency basis (EUR, JPY, GBP vs USD) — Eurodollar stress signal
- [ ] **STRESS-03**: Collector retrieves FRA-OIS spread
- [ ] **STRESS-04**: System calculates repo market stress indicator (fails, haircuts)

### Credit Markets

- [ ] **CREDIT-01**: Collector retrieves corporate bond issuance pace (IG, HY)
- [ ] **CREDIT-02**: Collector retrieves high-yield OAS (option-adjusted spread)
- [ ] **CREDIT-03**: Collector retrieves SLOOS (Senior Loan Officer Opinion Survey) from Fed
- [ ] **CREDIT-04**: Collector retrieves commercial paper rates (AA financial, nonfinancial)

### Liquidity Calculation

- [ ] **CALC-01**: System calculates Net Liquidity Index using Hayes formula (WALCL - TGA - RRP)
- [ ] **CALC-02**: System calculates Global Liquidity Index (Fed + ECB + BoJ + PBoC in USD)
- [ ] **CALC-03**: System calculates Stealth QE Score (port from Apps Script v3.4.1)
- [ ] **CALC-04**: System validates data consistency via double-entry accounting checks

### Analysis & Classification

- [ ] **ANLYS-01**: Regime classifier outputs Expansionary/Neutral/Contractionary state
- [ ] **ANLYS-02**: System tracks >85% of global monetary flows via Tier 1 CB coverage

### Cross-Asset Correlations

- [ ] **CORR-01**: System calculates rolling BTC/Net Liquidity correlation (30d, 90d)
- [ ] **CORR-02**: System calculates rolling SPX/Global Liquidity correlation (30d, 90d)
- [ ] **CORR-03**: System calculates Gold/Real Rates correlation
- [ ] **CORR-04**: Dashboard displays correlation heatmap across major assets
- [ ] **CORR-05**: Alert triggers when correlation regime shifts (>0.3 change)

### Calendar Effects

- [ ] **CAL-01**: System tracks US Treasury auction calendar with settlement dates
- [ ] **CAL-02**: System flags month-end/quarter-end liquidity windows
- [ ] **CAL-03**: System tracks tax payment dates (April 15, Sept 15, Dec 15)
- [ ] **CAL-04**: System tracks Fed meeting dates and blackout periods
- [ ] **CAL-05**: Dashboard shows calendar overlay on liquidity charts

### API & Integration

- [ ] **API-01**: FastAPI server exposes GET /liquidity/net endpoint
- [ ] **API-02**: FastAPI server exposes GET /liquidity/global endpoint
- [ ] **API-03**: FastAPI server exposes GET /regime/current endpoint
- [ ] **API-04**: FastAPI server exposes GET /metrics/stealth-qe endpoint
- [ ] **API-05**: NautilusTrader macro filter queries regime via REST API
- [ ] **API-06**: FastAPI server exposes GET /fx/dxy endpoint
- [ ] **API-07**: FastAPI server exposes GET /stress/indicators endpoint
- [ ] **API-08**: FastAPI server exposes GET /correlations endpoint
- [ ] **API-09**: FastAPI server exposes GET /calendar/events endpoint

### Alerting & Visualization

- [ ] **VIZ-01**: Plotly dashboard displays Net Liquidity Index time series
- [ ] **VIZ-02**: Plotly dashboard displays Global Liquidity Index time series
- [ ] **VIZ-03**: Plotly dashboard displays regime classification with color coding
- [ ] **VIZ-04**: Plotly dashboard exportable to standalone HTML
- [ ] **VIZ-05**: Dashboard displays FX panel (DXY, major pairs)
- [ ] **VIZ-06**: Dashboard displays commodities panel (Gold, Copper, Oil)
- [ ] **VIZ-07**: Dashboard displays stress indicators panel with threshold alerts
- [ ] **VIZ-08**: Dashboard displays capital flows panel (TIC, ETF flows)
- [ ] **ALERT-01**: Discord webhook fires on regime state change
- [ ] **ALERT-02**: Discord webhook includes previous/current regime and key metrics
- [ ] **ALERT-03**: Discord webhook fires on stress indicator threshold breach
- [ ] **ALERT-04**: Discord webhook fires on significant DXY move (>1% daily)

### Quality & Validation

- [ ] **QA-01**: System detects stale data (>24h for daily feeds, >48h for CBs)
- [ ] **QA-02**: System detects missing values and gaps in time series
- [ ] **QA-03**: System cross-validates data between sources (FRED vs direct API)
- [ ] **QA-04**: System flags anomalies (>3 std dev moves, sudden jumps)
- [ ] **QA-05**: Unit tests validate Hayes formula against known historical values
- [ ] **QA-06**: System cross-validates results vs Apps Script v3.4.1 output
- [ ] **QA-07**: Regression tests run on each data refresh
- [ ] **QA-08**: Dashboard shows data freshness indicator per source
- [ ] **QA-09**: Dashboard shows data quality score (completeness %)
- [ ] **QA-10**: Charts include sanity bounds (historical min/max ranges)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Analysis

- **ADV-01**: RMP (Reserve Management Purchases) tracking as new Fed mechanism
- **ADV-02**: Swap lines stress indicator between Fed and 5 major CBs
- **ADV-03**: Gold flows tracking via Switzerland (refinery data) for de-dollarization

### Crypto Integration

- **CRYPTO-01**: Crypto flow tracking (stablecoin supply, exchange flows)
- **CRYPTO-02**: On-chain liquidity metrics (stablecoin market cap, DEX TVL)

### Advanced Capital Flows

- **FLOW-07**: Sovereign wealth fund flows (Norway, Singapore, etc.) — opaque, quarterly

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real-time intraday updates | Daily/weekly sufficient for macro analysis |
| Bloomberg Terminal integration | Too expensive ($24k/year), use free APIs |
| Shadow banking tracking | Opaque, unreliable data |
| Grafana dashboards | Plotly simpler, HTML export, no extra service |
| Historical backfill >5 years | MVP focus, can add later |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 2 | Pending |
| DATA-04 | Phase 2 | Pending |
| DATA-05 | Phase 2 | Pending |
| DATA-06 | Phase 2 | Pending |
| DATA-07 | Phase 2 | Pending |
| DATA-08 | Phase 3 | Pending |
| DATA-09 | Phase 3 | Pending |
| DATA-10 | Phase 3 | Pending |
| DATA-11 | Phase 3 | Pending |
| DATA-12 | Phase 1 | Pending |
| DATA-13 | Phase 1 | Pending |
| DATA-14 | Phase 1 | Pending |
| DATA-15 | Phase 1 | Pending |
| FX-01 | Phase 3 | Pending |
| FX-02 | Phase 3 | Pending |
| FX-03 | Phase 3 | Pending |
| FX-04 | Phase 3 | Pending |
| FX-05 | Phase 5 | Pending |
| CMDTY-01 | Phase 4 | Pending |
| CMDTY-02 | Phase 4 | Pending |
| CMDTY-03 | Phase 4 | Pending |
| CMDTY-04 | Phase 4 | Pending |
| CMDTY-05 | Phase 4 | Pending |
| FLOW-01 | Phase 5 | Pending |
| FLOW-02 | Phase 5 | Pending |
| FLOW-03 | Phase 5 | Pending |
| FLOW-04 | Phase 5 | Pending |
| FLOW-05 | Phase 6 | Pending |
| FLOW-06 | Phase 6 | Pending |
| STRESS-01 | Phase 5 | Pending |
| STRESS-02 | Phase 5 | Pending |
| STRESS-03 | Phase 5 | Pending |
| STRESS-04 | Phase 5 | Pending |
| CREDIT-01 | Phase 6 | Pending |
| CREDIT-02 | Phase 6 | Pending |
| CREDIT-03 | Phase 6 | Pending |
| CREDIT-04 | Phase 6 | Pending |
| CALC-01 | Phase 7 | Pending |
| CALC-02 | Phase 7 | Pending |
| CALC-03 | Phase 7 | Pending |
| CALC-04 | Phase 7 | Pending |
| ANLYS-01 | Phase 8 | Pending |
| ANLYS-02 | Phase 7 | Pending |
| CORR-01 | Phase 8 | Pending |
| CORR-02 | Phase 8 | Pending |
| CORR-03 | Phase 8 | Pending |
| CORR-04 | Phase 8 | Pending |
| CORR-05 | Phase 8 | Pending |
| CAL-01 | Phase 9 | Pending |
| CAL-02 | Phase 9 | Pending |
| CAL-03 | Phase 9 | Pending |
| CAL-04 | Phase 9 | Pending |
| CAL-05 | Phase 9 | Pending |
| API-01 | Phase 9 | Pending |
| API-02 | Phase 9 | Pending |
| API-03 | Phase 9 | Pending |
| API-04 | Phase 9 | Pending |
| API-05 | Phase 9 | Pending |
| API-06 | Phase 9 | Pending |
| API-07 | Phase 9 | Pending |
| API-08 | Phase 9 | Pending |
| API-09 | Phase 9 | Pending |
| VIZ-01 | Phase 10 | Pending |
| VIZ-02 | Phase 10 | Pending |
| VIZ-03 | Phase 10 | Pending |
| VIZ-04 | Phase 10 | Pending |
| VIZ-05 | Phase 10 | Pending |
| VIZ-06 | Phase 10 | Pending |
| VIZ-07 | Phase 10 | Pending |
| VIZ-08 | Phase 10 | Pending |
| ALERT-01 | Phase 10 | Pending |
| ALERT-02 | Phase 10 | Pending |
| ALERT-03 | Phase 10 | Pending |
| ALERT-04 | Phase 10 | Pending |
| QA-01 | Phase 10 | Pending |
| QA-02 | Phase 10 | Pending |
| QA-03 | Phase 10 | Pending |
| QA-04 | Phase 10 | Pending |
| QA-05 | Phase 10 | Pending |
| QA-06 | Phase 10 | Pending |
| QA-07 | Phase 10 | Pending |
| QA-08 | Phase 10 | Pending |
| QA-09 | Phase 10 | Pending |
| QA-10 | Phase 10 | Pending |

**Coverage:**
- v1 requirements: 86 total
- Mapped to phases: 86
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-21*
*Last updated: 2026-01-21 after roadmap creation*
