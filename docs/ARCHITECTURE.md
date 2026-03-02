# SpongeBB Architecture

> **Note**: Canonical architecture source. Auto-updated by architecture-validator.

## Overview

SpongeBB is a macro liquidity tracking system built on the OpenBB SDK, implementing Arthur Hayes' framework for monitoring central bank liquidity flows and their impact on risk assets. It ingests data from 30+ sources (FRED, NY Fed, ECB SDW, Yahoo Finance, BIS, EIA, CFTC, and others), computes liquidity indices (Net Liquidity, Global Liquidity, Stealth QE Score), classifies market regimes, and presents results through both a REST API and an interactive Plotly Dash dashboard with Discord alerting.

The system comprises ~52,000 lines of Python across 174 source files and 155 test files, organized into 15 domain modules covering the full pipeline from data collection through nowcasting, risk analytics, backtesting, and visualization.

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Language | Python 3.11+ | Core implementation |
| Package Manager | uv | Dependency management, virtual environments |
| Data Platform | OpenBB SDK 4.x | Unified financial data access |
| Time-Series DB | QuestDB | High-performance ILP ingestion, PGWire queries |
| Pub/Sub & Cache | Redis 7 | Shared state, caching |
| API Framework | FastAPI | REST endpoints (read-only) |
| Dashboard | Plotly Dash + Bootstrap | Interactive visualization |
| Alerting | Discord Webhooks | Regime change, stress, correlation alerts |
| NLP | HuggingFace Transformers | CB speech translation, sentiment analysis |
| ML/Forecasting | PyTorch, hmmlearn, statsmodels, filterpy | LSTM, HMM, Markov switching, Kalman filter |
| Backtesting | numpy, pandas | Strategy simulation, performance metrics |
| Risk Analytics | riskfolio-lib, scipy | VaR, CVaR, portfolio optimization |
| Resilience | tenacity, purgatory | Retry with backoff, circuit breaker |
| Metrics | prometheus-client | Observability |
| Build System | hatchling | Python package build |
| Linting | ruff | Code quality (pycodestyle, pyflakes, isort, bugbear) |
| Type Checking | mypy (strict), pyright | Static type analysis |
| Testing | pytest, pytest-asyncio, pytest-cov, Playwright | Unit, integration, data E2E, visual regression |
| Containerization | Docker, Docker Compose | Deployment with QuestDB/Redis |

## Project Structure

```
spongebb/
├── src/liquidity/              # Core package (174 files, ~52K LOC)
│   ├── __init__.py             # Package metadata (v0.1.0)
│   ├── config.py               # Pydantic Settings (LIQUIDITY_ env prefix)
│   ├── collectors/             # 30+ data source collectors
│   ├── calculators/            # Liquidity index calculations
│   ├── analyzers/              # Regime, correlation, positioning analysis
│   ├── nowcasting/             # Kalman filter, MIDAS, regime forecasting
│   ├── risk/                   # VaR, CVaR, regime-conditional risk
│   ├── backtesting/            # Strategy simulation engine
│   ├── oil/                    # Oil market supply-demand analysis
│   ├── news/                   # CB RSS feeds, NLP sentiment, FOMC diffs
│   ├── alerts/                 # Discord alerting system
│   ├── calendar/               # Treasury auctions, CB meetings, tax dates
│   ├── weather/                # NOAA hurricane tracking (GOM impact)
│   ├── validation/             # Data quality engine (QA-01 through QA-07)
│   ├── storage/                # QuestDB ILP/PGWire storage layer
│   ├── api/                    # FastAPI REST server
│   └── dashboard/              # Plotly Dash interactive UI
├── tests/                      # 155 test files
│   ├── unit/                   # Module-level unit tests
│   ├── integration/            # Cross-module integration tests
│   ├── collectors/             # Collector-specific tests
│   ├── e2e/                    # End-to-end with real data
│   └── visual/                 # Playwright visual regression
├── scripts/                    # Utility scripts
│   ├── run_dashboard.py        # Dashboard launcher
│   ├── run-dashboard.sh        # Shell launcher
│   ├── validate.sh             # Validation runner
│   └── validate-automations.sh # Automation validation
├── playwright.config.js        # Playwright config (webServer + projects)
├── package.json                # Playwright scripts/dependencies
├── docs/                       # Documentation
├── .planning/                  # Requirements, roadmap, reference
├── .github/workflows/          # CI pipelines (including visual regression)
├── docker-compose.yml          # Multi-profile Docker deployment
├── Dockerfile                  # API container image
├── pyproject.toml              # Project config, deps, tool settings
└── .env.example                # Environment variable template
```

## Core Components

### Component: Collectors

**Purpose**: Fetch data from 30+ external sources with resilience patterns (retry, circuit breaker).
**Location**: `src/liquidity/collectors/`
**Key files**:
- `base.py` - Abstract `BaseCollector[T]` with tenacity retry + purgatory circuit breaker
- `registry.py` - `CollectorRegistry` for collector discovery
- `fred.py` - FRED API (Fed, ECB, BoJ balance sheets, rates, bonds)
- `nyfed.py` - NY Fed (SOFR, RRP, repo data)
- `tga_daily.py` - Treasury FiscalData API (daily TGA)
- `pboc.py` - PBoC balance sheet
- `yahoo.py` - Yahoo Finance (MOVE, VIX, DXY, FX)
- `eia.py` - EIA petroleum data (crude, products, refinery)
- `cftc_cot.py` - CFTC Commitments of Traders
- `oil_term_structure.py` - Oil futures curve
- `sofr.py` - SOFR rates
- `fx.py` - FX pairs (DXY, EUR/USD, USD/JPY, etc.)
- `bis.py` - BIS international banking statistics
- `commodities.py` - Gold, silver, copper, oil
- `etf_flows.py` - ETF flow tracking
- `credit.py` - Credit market (SLOOS, commercial paper)
- `overnight_rates.py` - ESTR, SONIA, CORRA
- `china_rates.py` - SHIBOR, DR007 via akshare
- `stablecoins.py` - Crypto stablecoin supply
- `xccy_basis.py` - Cross-currency basis swaps
- `stress.py` - Funding stress indicators
- `cofer.py` - IMF COFER reserve composition
- `fed_custody.py` - Fed custody holdings
- `tic.py` - Treasury International Capital
- `consumer_credit.py` - Consumer credit data
- `boc.py`, `boe.py`, `snb.py` - BoC, BoE, SNB balance sheets
- `swap_lines.py` - Fed swap lines

**Interface**:
```python
class BaseCollector(ABC, Generic[T]):
    async def collect(self, *args, **kwargs) -> T: ...
    async def fetch_with_retry(self, fetch_fn, breaker_name=None) -> T: ...
```

### Component: Calculators

**Purpose**: Compute liquidity indices from raw central bank data.
**Location**: `src/liquidity/calculators/`
**Key files**:
- `net_liquidity.py` - `NetLiquidityCalculator` (Hayes formula: WALCL - TGA - RRP)
- `global_liquidity.py` - `GlobalLiquidityCalculator` (Fed + ECB + BoJ + PBoC in USD)
- `stealth_qe.py` - `StealthQECalculator` (hidden liquidity injection detection)
- `validation.py` - `LiquidityValidator` (double-entry consistency checks)

**Interface**:
```python
class NetLiquidityCalculator:
    def calculate(self, walcl, tga, rrp) -> NetLiquidityResult: ...

class GlobalLiquidityCalculator:
    def calculate(self, fed, ecb, boj, pboc, fx_rates) -> GlobalLiquidityResult: ...
```

### Component: Analyzers

**Purpose**: Convert liquidity metrics into actionable trading intelligence.
**Location**: `src/liquidity/analyzers/`
**Key files**:
- `regime_classifier.py` - `RegimeClassifier` (EXPANSION/CONTRACTION), `CombinedRegimeAnalyzer`
- `correlation_engine.py` - `CorrelationEngine` (asset-liquidity correlations)
- `alert_engine.py` - `AlertEngine` (regime shifts, correlation breakdowns)
- `positioning.py` - `PositioningAnalyzer` (CFTC COT extreme detection)
- `term_structure.py` - `TermStructureAnalyzer` (curve shape, roll yield)
- `real_rates.py` - `RealRatesAnalyzer` (real rate regime classification)
- `oil_real_rates.py` - `OilRealRatesAnalyzer` (oil-rates correlation)

**Interface**:
```python
class RegimeClassifier:
    def classify(self, net_liquidity_series) -> RegimeResult: ...
    # Returns: direction (EXPANSION/CONTRACTION), intensity, confidence

class CorrelationEngine:
    def compute(self, data) -> CorrelationMatrix: ...
```

### Component: Nowcasting

**Purpose**: Estimate current Net Liquidity before official Fed releases using high-frequency proxies.
**Location**: `src/liquidity/nowcasting/`
**Key files**:
- `engine.py` - `NowcastEngine` orchestrator (daily pipeline: fetch, validate, model, alert)
- `kalman/liquidity_state_space.py` - `LiquidityStateSpace` Kalman filter
- `kalman/tuning.py` - `KalmanTuner` adaptive parameter estimation
- `midas/features.py` - `MIDASFeatures` mixed-frequency feature engineering
- `midas/pboc_estimator.py` - `PBoCEstimator` MIDAS regression for PBoC balance sheet
- `regime/hmm_classifier.py` - `HMMRegimeClassifier` (Hidden Markov Model)
- `regime/markov_switching.py` - `MarkovSwitchingClassifier`
- `regime/lstm_forecaster.py` - `LSTMRegimeForecaster` (PyTorch)
- `regime/ensemble.py` - `RegimeEnsemble` (combines HMM + Markov + LSTM)
- `correlation/trend_predictor.py` - `CorrelationTrendPredictor`
- `validation/` - Backtesting and metrics for nowcast evaluation

**Interface**:
```python
class NowcastEngine:
    async def run_daily_nowcast(self) -> NowcastResult: ...
    def fit_on_historical(self, net_liquidity, tune=True) -> NowcastResult: ...
    def is_significant_move(self, result) -> bool: ...
```

### Component: Risk

**Purpose**: Portfolio risk analytics with regime-conditional adjustments.
**Location**: `src/liquidity/risk/`
**Key files**:
- `var/historical.py` - `HistoricalVaR`
- `var/parametric.py` - `ParametricVaR` (Normal, Student-t, Cornish-Fisher)
- `cvar.py` - `ExpectedShortfall` (CVaR/ES)
- `regime_var.py` - `RegimeConditionalVaR` (VaR adjusted by liquidity regime)
- `liquidity_adjusted.py` - `LiquidityAdjustedRisk` (LA-VaR with bid-ask, market impact)
- `macro_filter.py` - `LiquidityRiskFilter`, `AdaptiveRiskManager` (trade filtering)

**Interface**:
```python
class RegimeConditionalVaR:
    def compute(self, returns, regime) -> RegimeVaRResult: ...

class LiquidityRiskFilter:
    def evaluate(self, signal, regime) -> TradingDecision: ...
```

### Component: Backtesting

**Purpose**: Historical strategy simulation using liquidity regime signals.
**Location**: `src/liquidity/backtesting/`
**Key files**:
- `engine/vectorbt_engine.py` - `VectorBTBacktester` (numpy-based vectorized backtesting)
- `engine/metrics.py` - `MetricsCalculator` (Sharpe, Sortino, max drawdown via pure numpy)
- `signals/regime_signals.py` - `RegimeSignalGenerator` (entry/exit from regime)
- `data/historical_loader.py` - `HistoricalLoader` (point-in-time data reconstruction)
- `data/asset_loader.py` - `AssetLoader` (price data for strategy testing)
- `attribution/regime_attribution.py` - `RegimeAttributionAnalyzer` (P&L by regime)
- `monte_carlo/simulation.py` - `MonteCarloSimulator` (confidence intervals on performance)

### Component: Oil Market Analysis

**Purpose**: US petroleum supply-demand balance and oil market regime classification.
**Location**: `src/liquidity/oil/`
**Key files**:
- `supply_demand.py` - `SupplyDemandCalculator` (weekly balance from EIA data)
- `inventory_forecast.py` - `InventoryForecaster` (YoY, seasonal, 4-week forecast)
- `regime.py` - `OilRegimeClassifier` (TIGHT/BALANCED/LOOSE)

### Component: News Intelligence

**Purpose**: Central bank communication monitoring with NLP sentiment analysis.
**Location**: `src/liquidity/news/`
**Key files**:
- `feeds.py` - `NewsPoller` (RSS aggregation with dedup and rate limiting)
- `schemas.py` - `FeedConfig`, `NewsItem`, `CENTRAL_BANK_FEEDS` definitions
- `sentiment.py` - `SentimentAnalyzer` (hawkish/dovish classification)
- `lexicons.py` - Keyword dictionaries (hawkish, dovish, neutral with weights)
- `translation.py` - `TranslationPipeline` (OPUS-MT multi-language translation)
- `alerts.py` - `NewsAlertEngine` (breaking news keyword detection)
- `oil_feeds.py` - `OilNewsPoller` (oil-specific RSS feeds)
- `oil_alerts.py` - `SupplyDisruptionMatcher` (supply disruption detection)
- `fomc/` - FOMC statement scraping, diff analysis, sentiment watcher
- `warmup.py` - NLP model pre-loading utilities

### Component: Alerts

**Purpose**: Discord webhook notification system for regime changes and market stress.
**Location**: `src/liquidity/alerts/`
**Key files**:
- `__init__.py` - `AlertManager` (high-level interface combining all alert subsystems)
- `discord.py` - `DiscordClient` (webhook integration with rate limiting)
- `handlers.py` - `AlertHandlers` (regime, stress, DXY, correlation checks)
- `formatter.py` - `AlertFormatter` (rich Discord embed formatting)
- `scheduler.py` - `AlertScheduler`, `FullAlertScheduler` (periodic checks)
- `config.py` - `AlertConfig`, thresholds, rate limits
- `positioning_alerts.py` - `PositioningAlertEngine` (CFTC extreme position alerts)
- `oil_term_structure_alerts.py` - `TermStructureAlertEngine` (curve shape alerts)

### Component: Calendar

**Purpose**: Track liquidity-impacting events (auctions, CB meetings, tax dates).
**Location**: `src/liquidity/calendar/`
**Key files**:
- `base.py` - `BaseCalendar`, `CalendarEvent`, `EventType`, `ImpactLevel`
- `treasury.py` - `TreasuryAuctionCalendar` (2026 auction schedule)
- `central_banks.py` - `CBMeetingCalendar` (FOMC, ECB, BoJ, BoE 2026)
- `tax_dates.py` - `TaxDateCalendar` (quarterly tax payment dates)
- `holidays.py` - `USMarketHolidays` (market closure dates)
- `opec.py` - `OPECCalendar` (OPEC+ meeting schedule)
- `registry.py` - `CalendarRegistry` (unified access, Fed blackout detection)

### Component: Data Validation

**Purpose**: Comprehensive data quality assurance (QA-01 through QA-07).
**Location**: `src/liquidity/validation/`
**Key files**:
- `__init__.py` - `ValidationEngine` (unified entry point for all checks)
- `freshness.py` - `FreshnessChecker` (QA-01: stale data detection)
- `completeness.py` - `CompletenessChecker` (QA-02: gap detection)
- `cross_validation.py` - `CrossValidator` (QA-03: multi-source consistency)
- `anomalies.py` - `AnomalyDetector` (QA-04: >3 std dev moves)
- `regression.py` - `RegressionTester` (QA-05/06: formula validation)
- `quality_score.py` - `QualityScorer` (aggregate score 0-100%)
- `config.py` - Thresholds and validation parameters

### Component: Storage

**Purpose**: QuestDB time-series storage with ILP ingestion.
**Location**: `src/liquidity/storage/`
**Key files**:
- `questdb.py` - `QuestDBStorage` (ILP ingestion 28-92x faster than SQL, PGWire queries)
- `schemas.py` - Table definitions, column mappings, SYMBOL columns

### Component: API

**Purpose**: Read-only REST endpoints for liquidity data consumption.
**Location**: `src/liquidity/api/`
**Key files**:
- `server.py` - FastAPI app with lifespan handler, CORS, health check
- `schemas.py` - Pydantic response models
- `deps.py` - Dependency injection (storage, settings)
- `routers/liquidity.py` - Net/Global liquidity endpoints
- `routers/regime.py` - Regime classification endpoint
- `routers/metrics.py` - Stealth QE and derived metrics
- `routers/fx.py` - DXY and FX pair data
- `routers/stress.py` - Funding stress indicators
- `routers/correlations.py` - Asset-liquidity correlation heatmap
- `routers/calendar.py` - Upcoming liquidity events

**Entry points**: `liquidity-api` (console script), `uvicorn liquidity.api:app`

### Component: Dashboard

**Purpose**: Interactive Plotly Dash visualization of all liquidity metrics.
**Location**: `src/liquidity/dashboard/`
**Key files**:
- `app.py` - Dash application factory
- `layout.py` - Full page layout composition (12 panels)
- `__main__.py` - `main()` entry point
- `export.py` - `HTMLExporter` (static HTML snapshot export)
- `callbacks_main.py` - Callback registration orchestrator
- `callbacks/eia_callbacks.py` - EIA petroleum panel callbacks
- `callbacks/inflation_callbacks.py` - Inflation expectations callbacks
- `components/` - 18 panel components:
  - `header.py` - Navigation + status bar
  - `liquidity.py` - Net + Global liquidity charts
  - `regime.py` - Regime classification panel
  - `correlations.py` - Correlation heatmap
  - `fx.py` - DXY and FX panels
  - `stress.py` - Funding stress indicators
  - `commodities.py` - Gold, oil, copper charts
  - `flows.py` - TIC capital flows
  - `news.py` - Central bank news feed
  - `fomc_diff.py` - FOMC statement diff viewer
  - `eia_panel.py` - EIA weekly petroleum data
  - `inflation.py` - Inflation expectations
  - `positioning.py` - CFTC COT positioning
  - `oil_term_structure.py` - Oil futures curve
  - `calendar.py` - Event calendar strip
  - `quality.py` - Data quality panel
  - `bounds.py` - Bollinger band overlays
  - `header.py` - Header and status bar

**Entry points**: `liquidity-dashboard` (console script), `python -m liquidity.dashboard`

### Component: Visual Regression & Browser Automation

**Purpose**: Deterministic screenshot regression plus interaction-based browser E2E for the dashboard.
**Location**:
- `playwright.config.js`
- `tests/e2e_ui/`
- `tests/visual/`
- `.github/workflows/visual-regression.yml`

**Key files**:
- `playwright.config.js` - Playwright projects (visual + browser E2E), webServer orchestration
- `package.json` - Browser test entrypoints (`test:e2e`, `test:visual`)
- `tests/e2e_ui/dashboard.e2e.spec.js` - Interaction-focused browser E2E
- `tests/visual/dashboard.visual.spec.js` - Above-the-fold snapshot test
- `tests/visual/dashboard.visual.spec.js-snapshots/` - Baseline screenshots
- `.github/workflows/visual-regression.yml` - CI visual regression job + artifact upload

**Deterministic mode for snapshots**:
- `LIQUIDITY_DASHBOARD_FORCE_FALLBACK=1` forces mock/fallback dashboard data
- `LIQUIDITY_DASHBOARD_FIXED_NOW=<ISO8601>` pins timestamps for stable screenshots

**Interactive browser debugging**:
- Playwright MCP is supported for guided visual inspection and troubleshooting.

### Component: Weather

**Purpose**: NOAA hurricane tracking for Gulf of Mexico oil production impact.
**Location**: `src/liquidity/weather/`
**Key files**:
- `noaa.py` - `NOAAHurricaneTracker` (active storm monitoring)
- `impact.py` - `assess_gom_impact()` (production shutdown estimation)

## Data Flow

```
                          External Data Sources
                    ┌─────────┬──────────┬──────────┐
                    │  FRED   │  NY Fed  │  Yahoo   │
                    │  ECB    │  EIA     │  BIS     │
                    │  PBoC   │  CFTC    │  NOAA    │
                    └────┬────┴────┬─────┴────┬─────┘
                         │         │          │
                         ▼         ▼          ▼
               ┌─────────────────────────────────────┐
               │         COLLECTORS (30+)             │
               │  BaseCollector[T] with retry + CB    │
               │  CollectorRegistry for discovery     │
               └──────────────┬──────────────────────┘
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
        ┌───────────────┐ ┌──────┐ ┌───────────┐
        │  CALCULATORS  │ │VALID-│ │  STORAGE   │
        │  Net Liq.     │ │ATION │ │  QuestDB   │
        │  Global Liq.  │ │QA 1-7│ │  (ILP)     │
        │  Stealth QE   │ └──┬───┘ └─────┬─────┘
        └───────┬───────┘    │           │
                │            ▼           │
                ▼      Quality Score     │
        ┌───────────────┐                │
        │   ANALYZERS   │◄───────────────┘
        │  Regime Class. │     (historical queries)
        │  Correlations  │
        │  Positioning   │
        │  Term Struct.  │
        └───────┬───────┘
                │
     ┌──────────┼──────────┬──────────────┐
     ▼          ▼          ▼              ▼
┌─────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
│NOWCAST  │ │ RISK   │ │BACKTEST │ │   OIL    │
│Kalman   │ │VaR/CVaR│ │numpy/pd │ │Supply/   │
│MIDAS    │ │Regime  │ │Monte    │ │Demand    │
│HMM/LSTM│ │LA-VaR  │ │Carlo    │ │Regime    │
└────┬────┘ └────┬───┘ └────┬────┘ └────┬─────┘
     │           │          │            │
     └───────────┼──────────┼────────────┘
                 ▼          │
        ┌───────────────┐   │
        │    ALERTS      │   │
        │  Discord       │   │
        │  Regime Change │   │
        │  Stress        │   │
        │  Positioning   │   │
        └───────────────┘   │
                            │
           ┌────────────────┼────────────────┐
           ▼                                 ▼
    ┌──────────────┐                ┌───────────────┐
    │   REST API   │                │   DASHBOARD   │
    │   FastAPI    │                │   Plotly Dash  │
    │   Port 8003  │                │   Port 8050   │
    │   7 routers  │                │   18 panels   │
    └──────────────┘                └───────────────┘
```

## Key Technical Decisions

### Decision 1: OpenBB SDK as Data Platform

- **Decision**: Use OpenBB SDK 4.x as the primary data access layer
- **Rationale**: Provides unified API across FRED, Yahoo, and other sources; handles authentication and caching; actively maintained
- **Trade-offs**: Large dependency tree; some providers require direct API access for features OpenBB does not expose (NY Fed, EIA, BIS)

### Decision 2: QuestDB for Time-Series Storage

- **Decision**: QuestDB with ILP ingestion instead of PostgreSQL/TimescaleDB
- **Rationale**: ILP is 28-92x faster than SQL INSERT for DataFrame ingestion; column-oriented storage ideal for time-series analytics; PGWire compatibility for queries
- **Trade-offs**: Less ecosystem tooling than PostgreSQL; requires separate infrastructure

### Decision 3: Kalman Filter for Nowcasting

- **Decision**: State-space model with Kalman filter for real-time Net Liquidity estimation
- **Rationale**: Fed balance sheet (WALCL) is only published weekly; daily TGA and RRP data can proxy Net Liquidity changes between releases; Kalman filter optimally combines noisy observations
- **Trade-offs**: Requires careful parameter tuning; proxy relationship is approximate

### Decision 4: Ensemble Regime Classification

- **Decision**: Combine HMM, Markov Switching, and LSTM for regime detection
- **Rationale**: Each model captures different regime dynamics; ensemble reduces false signals
- **Trade-offs**: Higher computational cost; more complex calibration

### Decision 5: Circuit Breaker + Retry Pattern

- **Decision**: All collectors use tenacity retry with purgatory circuit breaker
- **Rationale**: External APIs are unreliable; circuit breaker prevents cascading failures when a source is down; exponential backoff reduces rate limiting issues
- **Trade-offs**: Added complexity in collector base class; retry delays data freshness

### Decision 6: Shared NautilusTrader Infrastructure

- **Decision**: Default Docker profile shares QuestDB and Redis with NautilusTrader
- **Rationale**: Both projects are on the same workstation; avoids duplicate infrastructure; data can be cross-referenced
- **Trade-offs**: Coupled deployment; isolated profile available for independent testing

## Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `LIQUIDITY_FRED_API_KEY` | FRED API data access | (required) |
| `LIQUIDITY_EIA_API_KEY` | EIA petroleum data | (optional) |
| `LIQUIDITY_QUESTDB_HOST` | QuestDB hostname | `localhost` |
| `LIQUIDITY_QUESTDB_PORT` | QuestDB ILP port | `9009` |
| `LIQUIDITY_QUESTDB_HTTP_PORT` | QuestDB HTTP port | `9000` |
| `LIQUIDITY_REDIS_URL` | Redis connection | `redis://localhost:6379` |
| `LIQUIDITY_PROMETHEUS_PORT` | Metrics exposition | `8000` |
| `LIQUIDITY_CB_THRESHOLD` | Circuit breaker failure count | `5` |
| `LIQUIDITY_CB_TTL` | Circuit breaker half-open TTL (s) | `60` |
| `LIQUIDITY_RETRY_MAX_ATTEMPTS` | Max retry attempts | `5` |
| `LIQUIDITY_RETRY_MULTIPLIER` | Backoff multiplier | `1.0` |
| `LIQUIDITY_RETRY_MIN_WAIT` | Min retry wait (s) | `1` |
| `LIQUIDITY_RETRY_MAX_WAIT` | Max retry wait (s) | `60` |
| `LIQUIDITY_LOG_LEVEL` | Logging verbosity | `INFO` |
| `LIQUIDITY_DASHBOARD_FORCE_FALLBACK` | Force deterministic fallback data for dashboard/testing | unset (`false`) |
| `LIQUIDITY_DASHBOARD_FIXED_NOW` | Fixed UTC timestamp (ISO8601) for deterministic rendering | unset |

Configuration is managed via `pydantic-settings` in `src/liquidity/config.py` with the `LIQUIDITY_` environment variable prefix.

## Infrastructure

### Docker Compose Profiles

| Profile | Services | Use Case |
|---------|----------|----------|
| (default) | `liquidity-api` | API only, connects to external QuestDB/Redis |
| `isolated` | `liquidity-api-isolated` + `questdb` + `redis` | Standalone with dedicated infrastructure |
| `dev` | `liquidity-api-dev` | Hot-reload with source mount |

### Port Allocation

| Service | Default Port | Isolated Port |
|---------|-------------|---------------|
| API | 8003 | 8003 |
| Dashboard | 8050 | 8050 |
| QuestDB Web | 9000 | 9002 |
| QuestDB ILP | 9009 | 9011 |
| QuestDB PGWire | 8812 | 8814 |
| Redis | 6379 | 6381 |

### Entry Points

| Command | Target | Port |
|---------|--------|------|
| `liquidity-api` | FastAPI server | 8003 (host) |
| `liquidity-dashboard` | Dash server | 8050 |
| `python -m liquidity.dashboard` | Dash server | 8050 |
| `uvicorn liquidity.api:app --port 8003` | FastAPI server | 8003 |

## Testing Strategy

| Layer | Location | Count | Scope |
|-------|----------|-------|-------|
| Unit | `tests/unit/` | ~120 files | Individual modules, mocked dependencies |
| Integration | `tests/integration/` | ~20 files | Cross-module with real API calls |
| E2E | `tests/e2e/` | 1 file | Live-data pytest coverage (environment-dependent) |
| Browser E2E | `tests/e2e_ui/` | 1 file | Playwright interaction regression |
| Visual E2E | `tests/visual/` | 1 file | Playwright screenshot regression (desktop/mobile) |
| Collectors | `tests/collectors/` | 1 file | Collector-specific |

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html

# Run specific marker
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m e2e

# Run visual regression (Playwright)
npm ci
npx playwright install chromium
npm run test:e2e           # interaction checks
npm run test:visual:update  # baseline refresh
npm run test:visual         # regression check
```

### Visual CI Workflow

- Workflow: `.github/workflows/visual-regression.yml`
- Triggers: `pull_request`, `push` (selected paths), `workflow_dispatch`
- Outputs: `playwright-report` and `test-results` artifacts on every run

### Playwright MCP Workflow

1. Configure MCP server (`playwright`) in Codex client.
2. Restart Codex session to load the server.
3. Use MCP-driven browser automation for interactive UI diagnostics.
4. Keep CI visual snapshots as the objective regression gate.

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Development guidelines and project rules
- [README.md](../README.md) - Project overview
- [NautilusTrader Integration](nautilus_integration.md) - Strategy integration notes
- [Requirements](.planning/REQUIREMENTS.md) - Feature requirements
- [Roadmap](.planning/ROADMAP.md) - Development phases
- [Apps Script Reference](.planning/reference/appscript_v3.4.1.md) - Original formula reference
