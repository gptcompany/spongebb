---
phase: 08-analysis-correlations
status: completed
completed_at: 2026-01-26
---

# Phase 08: Analysis & Correlations - Summary

## Deliverables

### 1. RegimeClassifier (`src/liquidity/analyzers/regime_classifier.py`)
- **RegimeDirection enum**: EXPANSION / CONTRACTION (binary, no neutral)
- **RegimeResult dataclass**: timestamp, direction, intensity (0-100), confidence (HIGH/MEDIUM/LOW)
- **RegimeClassifier class**:
  - Configurable weights: NET_LIQUIDITY=0.40, GLOBAL_LIQUIDITY=0.40, STEALTH_QE=0.20
  - Rolling percentile calculation (90-day lookback)
  - Confidence based on component agreement (all 3 agree = HIGH)
  - `classify()` and `classify_historical()` methods

### 2. CorrelationEngine (`src/liquidity/analyzers/correlation_engine.py`)
- **CorrelationResult dataclass**: timestamp, asset, corr_30d, corr_90d, corr_ewma, p_values
- **CorrelationMatrix dataclass**: full correlation matrix with p-values
- **CorrelationEngine class**:
  - Fixed windows: 30d, 90d
  - EWMA halflife: 21 days (configurable)
  - `calculate_correlations()`: returns dict with '30d', '90d', 'ewma' DataFrames
  - `calculate_single_correlation()`: for single asset with p-values
  - `calculate_correlation_matrix()`: full matrix via scipy.stats.pearsonr
  - Asset basket: BTC, SPX, GOLD, TLT, DXY, COPPER, HYG

### 3. AlertEngine (`src/liquidity/analyzers/alert_engine.py`)
- **AlertType enum**: REGIME_SHIFT, CORRELATION_BREAKDOWN, CORRELATION_SURGE
- **AlertSeverity enum**: CRITICAL, HIGH, MEDIUM, LOW
- **Alert dataclass**: timestamp, type, severity, title, message, asset, values, z_score, metadata
- **AlertEngine class**:
  - Dual threshold detection: absolute (0.3) + statistical (2σ)
  - `check_regime_shift()`: detects EXPANSION <-> CONTRACTION transitions
  - `check_correlation_shift()`: detects breakdowns/surges
  - `check_all()`: combined check with CRITICAL upgrade logic
  - `format_discord_payload()`: Discord-ready embed with color coding

### 4. Module Exports (`src/liquidity/analyzers/__init__.py`)
All classes exported:
- RegimeClassifier, RegimeDirection, RegimeResult
- CorrelationEngine, CorrelationResult, CorrelationMatrix
- AlertEngine, Alert, AlertType, AlertSeverity

## Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| `tests/unit/test_regime_classifier.py` | 41 | PASS |
| `tests/unit/test_correlation_engine.py` | 34 | PASS |
| `tests/integration/test_analyzers.py` | 19 | PASS |
| **Total** | **94** | **PASS** |

## Key Algorithms

### Regime Classification
```
composite = net_pct * 0.40 + global_pct * 0.40 + stealth_pct * 0.20
direction = EXPANSION if composite > 0.5 else CONTRACTION
intensity = abs(composite - 0.5) * 200
```

### EWMA Correlation
```python
ewm(halflife=21).corr()  # Exponential weighted correlation
```

### Alert Dual Threshold
```
alert if: |change| > 0.3 OR z_score > 2.0
severity = HIGH if both breached, MEDIUM if one
CRITICAL if regime_shift AND correlation_breakdown coincide
```

## Files Changed

```
src/liquidity/analyzers/
├── __init__.py              # Module exports
├── regime_classifier.py     # RegimeClassifier implementation
├── correlation_engine.py    # CorrelationEngine implementation
└── alert_engine.py          # AlertEngine implementation

tests/
├── unit/
│   ├── test_regime_classifier.py   # 41 unit tests
│   └── test_correlation_engine.py  # 34 unit tests
└── integration/
    └── test_analyzers.py           # 19 integration tests
```

## Dependencies Added
- `scipy>=1.17.0` (for stats.pearsonr)

## Next Phase
Phase 09: Dashboard & Visualization
