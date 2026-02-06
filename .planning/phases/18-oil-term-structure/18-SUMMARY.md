# Phase 18 Summary: Oil Term Structure

## Completed: 2026-02-06

## Overview
Implemented contango/backwardation analysis for oil futures using price momentum as a proxy for term structure shape.

## Components Implemented

### 1. OilTermStructureCollector (Plan 18-01)
**File:** `src/liquidity/collectors/oil_term_structure.py`
- Fetches WTI and Brent front month prices via yfinance
- Calculates 5-day and 20-day momentum metrics
- Registers in collector registry

**Tests:** 32 unit tests + 7 integration tests

### 2. TermStructureAnalyzer (Plan 18-02)
**File:** `src/liquidity/analyzers/term_structure.py`
- Classifies curve shape: CONTANGO, BACKWARDATION, FLAT
- Calculates intensity (0-100) based on momentum
- Estimates roll yield proxy (annualized %)
- Optional EIA inventory correlation

**Tests:** 28 unit tests

### 3. TermStructureAlertEngine (Plan 18-03)
**File:** `src/liquidity/alerts/oil_term_structure_alerts.py`
- Alerts on regime changes (curve shape transitions)
- Alerts on high intensity (>70 warning, >90 critical)
- Alerts on extreme roll yield (>20% annualized)
- Discord webhook integration

**Tests:** 18 unit tests

### 4. Dashboard Component (Plan 18-04)
**File:** `src/liquidity/dashboard/components/oil_term_structure.py`
- Signal tab with curve gauge (Backwardation ↔ Contango)
- Price tab with WTI chart and 20D MA
- Roll yield tab with horizon bars (1M, 3M, 12M)

**Tests:** 24 unit tests

## Data Schema

### Collector Output
```
timestamp | series_id | source | value | unit
2026-02-06 | wti_front | yfinance | 72.45 | usd_per_barrel
2026-02-06 | wti_front_momentum_5d | calculated | 3.2 | percent
2026-02-06 | wti_front_momentum_20d | calculated | 5.8 | percent
```

### Signal Output
```python
TermStructureSignal(
    timestamp=datetime,
    curve_shape=CurveShape.BACKWARDATION,
    intensity=65.0,
    roll_yield_proxy=12.5,
    momentum_5d=3.2,
    momentum_20d=5.8,
    confidence=0.75,
)
```

## Technical Notes

### Why Momentum Proxy?
yfinance only provides front month continuous contracts (CL=F, BZ=F). True term structure would require CME API access for full futures curve (6+ contracts).

We use momentum as proxy:
- **Rising prices** → supply tightening → backwardation tendency
- **Falling prices** → supply abundant → contango tendency

### EIA Correlation
When EIA inventory data is available:
- **Inventory build** weakens backwardation signal
- **Inventory draw** weakens contango signal

## Test Coverage

| Component | Unit Tests | Integration Tests |
|-----------|------------|-------------------|
| Collector | 32 | 7 |
| Analyzer | 28 | - |
| Alerts | 18 | - |
| Dashboard | 24 | - |
| **Total** | **102** | **7** |

All 109 tests pass.

## Files Created/Modified

### New Files
- `src/liquidity/collectors/oil_term_structure.py` (~280 LOC)
- `src/liquidity/analyzers/term_structure.py` (~280 LOC)
- `src/liquidity/alerts/oil_term_structure_alerts.py` (~180 LOC)
- `src/liquidity/dashboard/components/oil_term_structure.py` (~260 LOC)
- `tests/unit/collectors/test_oil_term_structure.py`
- `tests/unit/analyzers/test_term_structure.py`
- `tests/unit/alerts/test_oil_term_structure_alerts.py`
- `tests/unit/test_dashboard/test_components/test_oil_term_structure.py`
- `tests/integration/collectors/test_oil_term_structure_integration.py`

### Modified Files
- `src/liquidity/collectors/__init__.py` - Added exports
- `src/liquidity/analyzers/__init__.py` - Added exports
- `src/liquidity/alerts/__init__.py` - Added exports
- `src/liquidity/dashboard/components/__init__.py` - Added exports

## Usage Example

```python
from liquidity.collectors import OilTermStructureCollector
from liquidity.analyzers import TermStructureAnalyzer
from liquidity.alerts import TermStructureAlertEngine

# Collect data
collector = OilTermStructureCollector()
data = await collector.collect_with_momentum()

# Analyze
analyzer = TermStructureAnalyzer()
signal = analyzer.analyze(data)
roll_yield = analyzer.calculate_roll_yield(data)

print(f"Curve: {signal.curve_shape.value}")
print(f"Intensity: {signal.intensity}/100")
print(f"Roll Yield: {roll_yield.annual_yield}% annualized")

# Alert
engine = TermStructureAlertEngine(discord_webhook="...")
alerts = engine.check_alerts(signal, roll_yield)
for alert in alerts:
    await engine.send_alert(alert)
```

## Next Steps
- Phase 19: Real Rates (TIPS, Breakeven Inflation)
- Phase 20: Commodity News (OPEC, Weather)
- Phase 21: Supply-Demand Model

---
*Phase 18 completed: 2026-02-06*
*Total implementation: ~1000 LOC + ~1200 LOC tests*
