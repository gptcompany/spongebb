# Phase 18 Context: Oil Term Structure

## Goal
Implementare contango/backwardation signals dalla curva futures WTI per anticipare supply dynamics.

## Business Value
- **Contango:** Supply abundant, bearish oil, storage costs priced in
- **Backwardation:** Supply tight, bullish oil, immediate delivery premium
- **Roll Yield:** Trading signal per commodity ETF positioning

## Scope

### In Scope
- WTI futures front month data (CL=F via yfinance)
- Contango/backwardation classification
- Roll yield proxy calculation
- Price momentum analysis
- Dashboard panel integrazione
- Alert su curve inversions

### Out of Scope (Future)
- Full CME curve (6 contracts) - requires CME API
- Brent term structure
- Calendar spread trading signals
- Options-implied term structure

## Technical Approach

### Data Source
```python
# yfinance - verified working
import yfinance as yf
data = yf.download("CL=F", period="2y")
```

### Term Structure Proxy
Senza full curve, usiamo:
1. **Price momentum** (5-day, 20-day changes)
2. **EIA inventory correlation** (inventory build → contango)
3. **CFTC positioning** (speculators short → contango)
4. **Historical seasonal patterns**

### Signal Classification
| Condition | Signal | Interpretation |
|-----------|--------|----------------|
| Momentum > 2% + Inventory draw | BACKWARDATION | Supply tight |
| Momentum < -2% + Inventory build | CONTANGO | Supply abundant |
| Otherwise | FLAT | Balanced |

## Integration Points

### Collector
`src/liquidity/collectors/oil_term_structure.py`
- Extends BaseCollector
- Fetches CL=F via yfinance
- Calculates momentum metrics

### Analyzer
`src/liquidity/analyzers/term_structure.py`
- Curve shape classification
- Roll yield estimation
- Cross-reference EIA + CFTC data

### Dashboard
`src/liquidity/dashboard/components/oil_term_structure.py`
- Price chart with momentum bands
- Signal gauge (Backwardation ↔ Contango)
- Roll yield indicator

### Alerts
`src/liquidity/alerts/oil_term_structure_alerts.py`
- Curve inversion alerts
- Extreme momentum alerts

## Dependencies

### Phase Dependencies
- Phase 16 (EIA data) - per inventory correlation
- Phase 17 (CFTC positioning) - per speculator data

### Package Dependencies
- yfinance (existing)
- pandas, numpy (existing)
- plotly, dash (existing)

## Success Criteria
1. ✅ Collector fetches WTI futures data daily
2. ✅ Analyzer classifies term structure signal
3. ✅ Dashboard shows curve shape + signal
4. ✅ Alerts fire on curve inversions
5. ✅ Tests: >90% coverage su nuovo codice

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| yfinance rate limits | Circuit breaker + FRED fallback |
| No true curve | Proxy via momentum + fundamentals |
| Contract roll gaps | Use adjusted close, validate ranges |

## Data Schema

### Collector Output
```python
DataFrame:
  - timestamp: datetime
  - series_id: str ("wti_front", "wti_momentum_5d", etc.)
  - source: str ("yfinance")
  - value: float
  - unit: str ("usd_per_barrel", "percent")
```

### Analyzer Output
```python
@dataclass
class TermStructureSignal:
    timestamp: datetime
    curve_shape: Literal["CONTANGO", "BACKWARDATION", "FLAT"]
    intensity: float  # 0-100
    roll_yield_proxy: float  # annualized %
    momentum_5d: float
    momentum_20d: float
```

## Plan Files
- 18-01: Futures curve collector
- 18-02: Contango/backwardation indicator
- 18-03: Roll yield calculator
- 18-04: Term structure visualization

---
*Context gathered: 2026-02-06*
