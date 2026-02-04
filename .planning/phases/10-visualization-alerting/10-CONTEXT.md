# Phase 10: Visualization & Alerting - Context

## Phase Goal

Build Plotly Dash dashboard for visualizing liquidity data, Discord alerting for regime changes and stress events, and comprehensive data quality validation system.

## User Preferences (from Discuss)

### Dashboard
- **Type**: Plotly Dash (interactive server)
- **Features**: Filters, zoom, auto-refresh
- **Panels**: Net/Global Liquidity, Regime, FX, Commodities, Stress, Capital Flows, Calendar overlay

### Alerting
- **Channel**: Discord webhooks
- **Alert Types** (all 4):
  - ALERT-01: Regime state change (EXPANSION ↔ CONTRACTION)
  - ALERT-02: Previous/current regime with key metrics
  - ALERT-03: Stress indicator threshold breach
  - ALERT-04: Significant DXY move (>1% daily)
  - Plus: Correlation regime shift (>0.3 change) from CORR-05

### QA Validation
- **Level**: Full (QA-01 to QA-10)
- **Features**:
  - Data freshness detection
  - Gap/missing value detection
  - Cross-source validation
  - Anomaly flagging (>3σ)
  - Apps Script v3.4.1 cross-validation
  - Dashboard quality indicators

## Technical Constraints

### Dependencies to Add
- `dash>=2.18.0` - Plotly Dash framework
- `dash-bootstrap-components>=1.6.0` - Bootstrap styling
- `discord-webhook>=1.3.0` - Discord webhook client (sync/async)

### Existing Components to Integrate
| Component | Location | Dashboard Usage |
|-----------|----------|-----------------|
| NetLiquidityCalculator | `calculators/net_liquidity.py` | Net Liquidity panel |
| GlobalLiquidityCalculator | `calculators/global_liquidity.py` | Global Liquidity panel |
| RegimeClassifier | `analyzers/regime_classifier.py` | Regime panel + alerts |
| CorrelationEngine | `analyzers/correlation_engine.py` | Correlation heatmap |
| AlertEngine | `analyzers/alert_engine.py` | Alert generation |
| FXCollector | `collectors/fx.py` | FX panel |
| CommodityCollector | `collectors/commodity.py` | Commodities panel |
| StressIndicatorCollector | `collectors/stress.py` | Stress panel |
| CalendarRegistry | `calendar/registry.py` | Calendar overlay |
| QuestDBStorage | `storage/questdb.py` | Data fetching |

## Architecture Decisions

### Module Structure
```
src/liquidity/
├── dashboard/
│   ├── __init__.py
│   ├── app.py              # Dash app setup
│   ├── layout.py           # Main layout
│   ├── callbacks.py        # Interactivity
│   └── components/
│       ├── liquidity.py    # Net/Global Liquidity panels
│       ├── regime.py       # Regime panel
│       ├── fx.py           # FX panel
│       ├── commodities.py  # Commodities panel
│       ├── stress.py       # Stress panel
│       ├── flows.py        # Capital flows panel
│       ├── correlations.py # Correlation heatmap
│       ├── calendar.py     # Calendar overlay
│       └── quality.py      # Data quality indicators
│
├── alerts/
│   ├── __init__.py
│   ├── discord.py          # Discord webhook client
│   ├── handlers.py         # Alert handlers (regime, stress, dxy, correlation)
│   └── scheduler.py        # Alert check scheduler
│
├── validation/
│   ├── __init__.py
│   ├── freshness.py        # QA-01: Stale data detection
│   ├── completeness.py     # QA-02: Gap detection
│   ├── cross_validation.py # QA-03: Source cross-validation
│   ├── anomalies.py        # QA-04: Anomaly flagging
│   ├── regression.py       # QA-05/06/07: Regression tests
│   └── quality_score.py    # QA-08/09/10: Quality metrics
```

### Dashboard Layout
```
┌─────────────────────────────────────────────────────────┐
│  Header: Global Liquidity Monitor   [Refresh] [Export]  │
├─────────────────────────────────────────────────────────┤
│ Data Quality: 98% │ Last Update: 5 min ago │ Regime: ▲  │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐             │
│  │ Net Liquidity    │  │ Global Liquidity │             │
│  │ [Chart]          │  │ [Chart]          │             │
│  └──────────────────┘  └──────────────────┘             │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐             │
│  │ Regime Panel     │  │ Correlation Heat │             │
│  │ [EXPANSION]      │  │ [Heatmap]        │             │
│  └──────────────────┘  └──────────────────┘             │
├─────────────────────────────────────────────────────────┤
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │  FX    │ │ Stress │ │ Cmdty  │ │ Flows  │           │
│  │[DXY]   │ │[SOFR]  │ │[Gold]  │ │[TIC]   │           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
├─────────────────────────────────────────────────────────┤
│  Calendar: [Treasury Auction Feb 10] [FOMC Feb 28]      │
└─────────────────────────────────────────────────────────┘
```

### Discord Alert Format
```
🔴 REGIME CHANGE: CONTRACTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Previous: EXPANSION (intensity 72)
Current:  CONTRACTION (intensity 35)
Confidence: HIGH

Key Metrics:
• Net Liquidity: $5.8T (-$120B)
• Global Liquidity: $28.2T (-$450B)
• DXY: 104.5 (+0.8%)

🕐 2026-02-04 15:30 UTC
```

## Out of Scope (Phase 10)
- Real-time streaming updates (polling every 5 min sufficient)
- User authentication (internal tool)
- Mobile-responsive design (desktop focus)
- Historical data export (use QuestDB directly)

## Risk Assessment
- **Low**: Plotly Dash well-documented, Discord webhook simple
- **Medium**: Dashboard performance with large datasets (use sampling)
- **Medium**: Discord rate limits (batch alerts, max 1 per minute per type)

## Success Criteria
- [ ] Dashboard loads in <3 seconds
- [ ] All 8 visualization panels render correctly
- [ ] Discord alerts fire within 60s of event
- [ ] Data quality score visible on dashboard
- [ ] HTML export generates valid standalone file
- [ ] 100% unit test coverage for validation module
