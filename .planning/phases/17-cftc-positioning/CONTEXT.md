# Phase 17: CFTC Positioning - Context

## Vision

Integrare i dati di posizionamento CFTC (Commitment of Traders) nel sistema di liquidity monitoring per identificare:
1. **Sentiment dei market participants** (commercials vs speculators)
2. **Estremi di positioning** che precedono inversioni
3. **Correlazioni positioning-regime** per segnali macro

## Scope

### In Scope

- **CFTC COT Collector**: Fetch weekly disaggregated futures data via Socrata API
- **Positioning Metrics**: Net positions, ratios, percentile ranks
- **Extreme Detection**: Alert su positioning estremo (>90th o <10th percentile)
- **Dashboard Panel**: Heatmap e time series positioning

### Out of Scope

- Options data (futures-only per ora)
- Real-time intraday data (COT is weekly)
- Backtesting integration (will be Phase 21)

## Key Commodities

Priorità per il liquidity framework:

| Priority | Commodity | Rationale |
|----------|-----------|-----------|
| P0 | WTI Crude Oil | Core macro indicator, inflation proxy |
| P0 | Gold | Risk-off hedge, inverse USD |
| P1 | Copper | Industrial demand, China proxy |
| P1 | Natural Gas | Energy, Europe sensitivity |
| P2 | Silver | Gold correlation, industrial |

## Positioning Interpretation

### Commercials (Producer/Merchant)

- **"Smart money"** - hanno exposure reale alla commodity
- **Commercial Short**: Produttori che hedgiano → aspettano prezzi più bassi
- **Commercial Long**: Consumers che hedgiano → aspettano prezzi più alti
- **Extreme Commercial Short** = bearish signal (smart money hedging)

### Managed Money (Speculators)

- **"Dumb money"** trend followers
- **Extreme Spec Long** = crowded long, reversal risk
- **Extreme Spec Short** = crowded short, squeeze risk
- **Spec vs Commercial divergence** = high conviction signal

### Swap Dealers

- Intermediari, meno informativo per direction
- Spread positions = market making activity

## Alert Thresholds

| Metric | Bullish Alert | Bearish Alert |
|--------|---------------|---------------|
| Spec Net Percentile | <10th (squeeze risk) | >90th (reversal risk) |
| Comm Net Percentile | >90th (smart $ bullish) | <10th (smart $ bearish) |
| Comm/Spec Divergence | Comm>0, Spec<0 | Comm<0, Spec>0 |

## Technical Decisions

### API Choice: Socrata (Primary)

**Pro:**
- No auth required
- JSON/CSV formats
- Real-time (weekly updates)
- Query filtering (SoQL)
- Free, official source

**Contro:**
- Rate limits non documentati (ma non osservati)
- Occasional API downtime

### Fallback: cot_reports Library

Per bulk historical data se API down.

### Output Schema

Normalizzato al formato standard del progetto:
```
timestamp | series_id | source | value | unit
```

Series IDs:
- `cot_wti_comm_net` - WTI Commercial Net
- `cot_wti_spec_net` - WTI Speculator Net
- `cot_wti_spec_pctl` - WTI Speculator Percentile (52w)
- `cot_gold_comm_net` - Gold Commercial Net
- etc.

## Dependencies

### Upstream

- Phase 16 (EIA): Per correlazione oil positioning vs inventory

### Downstream

- Phase 21 (Supply-Demand Model): Positioning come input

## Risks

| Risk | Mitigation |
|------|------------|
| API changes | Fallback a cot_reports library |
| Weekend release (venerdì PM) | Scheduler per sabato mattina |
| Missing weeks | Interpolation o skip con warning |

## Success Criteria

1. **Collector funzionante** per 5+ commodities
2. **Percentile calculation** rolling 52 weeks
3. **Alert system** per positioning estremi
4. **Dashboard panel** con heatmap

## Estimated Effort

| Plan | Description | Effort |
|------|-------------|--------|
| 17-01 | CFTC COT collector | M |
| 17-02 | Positioning metrics | M |
| 17-03 | Extreme alerts | M |
| 17-04 | Dashboard heatmap | M |

Total: ~4 plans, 1 wave (all parallel)

---
*Context gathered: 2026-02-06*
