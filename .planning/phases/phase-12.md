# Phase 12: Nowcasting & Forecasting

## Overview

Implement nowcasting and forecasting capabilities to estimate current liquidity conditions before official data releases and predict future regime changes. This addresses the critical gap of relying on lagged official data (especially PBoC at 30-45 days).

## Goals

1. **Liquidity Nowcast**: Real-time estimate of current liquidity using HF proxies
2. **PBoC Estimator**: Predict PBoC balance sheet from SHIBOR/DR007 movements
3. **Regime Forecaster**: Predict regime transitions 1-4 weeks ahead
4. **Correlation Predictor**: Forecast correlation trends for portfolio hedging

## Dependencies

- Phase 11 (High-Frequency Data Layer) - Required for HF proxy data

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NOW-01 | Kalman filter nowcasting for Net Liquidity | HIGH |
| NOW-02 | PBoC balance sheet regression estimator | HIGH |
| NOW-03 | Markov switching regime forecaster | MEDIUM |
| NOW-04 | Rolling correlation trend predictor | MEDIUM |

## Research Topics

1. **Kalman Filter Nowcasting**
   - Library: filterpy (3,763 stars)
   - Paper: "Nowcasting GDP with Machine Learning" (ECB 2022)
   - State-space model for liquidity estimation
   - Install: `pip install filterpy`

2. **Markov Regime Switching**
   - Library: statsmodels.tsa.regime_switching
   - Library: hmmlearn (3,378 stars)
   - Hamilton (1989) two-state model
   - Install: `pip install hmmlearn`

3. **Dynamic Factor Models**
   - Library: statsmodels.tsa.statespace
   - Multiple HF indicators → single liquidity factor
   - Optimal weighting via MLE

4. **Neural Forecasting**
   - Library: darts (9,184 stars)
   - Models: N-BEATS, TFT, LSTM
   - Install: `pip install darts`

## Plans

### Plan 12-01: Liquidity Nowcast Engine
**Wave**: 1 | **Effort**: L | **Priority**: HIGH

Implement Kalman filter-based nowcasting for Net Liquidity Index.

**Methodology**:
```
State: Net_Liq_t (unobserved current value)
Observations:
  - TGA_daily (high-frequency, 1-day lag)
  - RRP_daily (high-frequency, same-day)
  - SOFR spread (market signal)
  - SPY returns (risk proxy)

Kalman Filter:
  x_t = A * x_{t-1} + w_t  (state transition)
  y_t = H * x_t + v_t      (observation equation)
```

**Deliverables**:
- `src/liquidity/nowcasting/kalman_engine.py`
- `src/liquidity/nowcasting/state_space.py`
- Tests in `tests/unit/test_nowcasting/`

**Acceptance Criteria**:
- [ ] Real-time liquidity estimate with confidence interval
- [ ] Tracks official releases with <5% RMSE
- [ ] Updates on each new HF observation
- [ ] Dashboard integration showing nowcast vs official

### Plan 12-02: PBoC Balance Sheet Estimator
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Build regression model to estimate PBoC balance sheet from daily proxies.

**Methodology**:
```
Target: PBoC_Assets_t (monthly, 30-45 day lag)
Predictors:
  - SHIBOR_ON (overnight rate)
  - DR007 (PBoC target rate)
  - CNH-CNY spread (offshore-onshore)
  - PBoC OMO announcements (text features)

Model: Ridge regression with rolling window
  PBoC_est = β0 + β1*SHIBOR + β2*DR007 + β3*Spread + ε
```

**Deliverables**:
- `src/liquidity/nowcasting/pboc_estimator.py`
- Historical validation (backtesting accuracy)
- Tests in `tests/unit/test_nowcasting/`

**Acceptance Criteria**:
- [ ] Estimates PBoC 2-3 weeks before official release
- [ ] <10% MAPE on historical data
- [ ] Confidence bands for estimates
- [ ] Alert when estimate diverges from trend

### Plan 12-03: Regime Forecaster
**Wave**: 2 | **Effort**: L | **Priority**: MEDIUM

Implement Markov switching model for regime prediction.

**Methodology**:
```
States: {EXPANSION, CONTRACTION}
Transition Matrix:
  P(E→E) = 0.95  P(E→C) = 0.05
  P(C→E) = 0.10  P(C→C) = 0.90

Features:
  - Net Liquidity change rate
  - Global Liquidity momentum
  - Stealth QE score
  - Stress indicators

Model: HMM with Gaussian emissions
  - hmmlearn.GaussianHMM(n_components=2)
  - Or statsmodels.MarkovAutoregression
```

**Deliverables**:
- `src/liquidity/nowcasting/regime_forecaster.py`
- Transition probability dashboard widget
- Tests in `tests/unit/test_nowcasting/`

**Acceptance Criteria**:
- [ ] 1-4 week regime prediction
- [ ] Transition probability estimation
- [ ] Historical accuracy >65% on regime calls
- [ ] Alert on high transition probability

### Plan 12-04: Correlation Trend Predictor
**Wave**: 2 | **Effort**: M | **Priority**: MEDIUM

Forecast rolling correlation trends for hedging decisions.

**Methodology**:
```
Target: ρ(BTC, NetLiq)_{t+h} for h = 7, 14, 30 days
Features:
  - Current correlation level
  - Correlation momentum (Δρ over 30d)
  - Volatility regime (VIX level)
  - Liquidity regime (from classifier)

Model: ARIMA(p,d,q) or LSTM for correlation series
```

**Deliverables**:
- `src/liquidity/nowcasting/correlation_predictor.py`
- Correlation forecast panel in dashboard
- Tests in `tests/unit/test_nowcasting/`

**Acceptance Criteria**:
- [ ] Predicts correlation direction (up/down/stable)
- [ ] Forecasts correlation breakdown events
- [ ] Confidence intervals for predictions
- [ ] Integrates with alert system

## Technical Notes

### New Dependencies

```toml
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "filterpy>=1.4.5",    # Kalman filters
    "hmmlearn>=0.3.0",    # Hidden Markov Models
    "darts>=0.27.0",      # Time series forecasting
]
```

### Module Structure

```
src/liquidity/nowcasting/
├── __init__.py
├── kalman_engine.py      # Kalman filter implementation
├── state_space.py        # State-space model definitions
├── pboc_estimator.py     # PBoC regression model
├── regime_forecaster.py  # HMM regime prediction
├── correlation_predictor.py  # Correlation forecasting
└── models/
    ├── __init__.py
    ├── base.py           # Base forecaster class
    └── metrics.py        # Forecast accuracy metrics
```

## Success Metrics

| Metric | Target |
|--------|--------|
| Net Liq nowcast RMSE | <5% vs official |
| PBoC estimate MAPE | <10% |
| Regime prediction accuracy | >65% |
| Correlation direction accuracy | >60% |

## References

- filterpy Documentation: https://filterpy.readthedocs.io/
- hmmlearn Documentation: https://hmmlearn.readthedocs.io/
- statsmodels State Space: https://www.statsmodels.org/stable/statespace.html
- darts Documentation: https://unit8co.github.io/darts/
- Hamilton (1989) "A New Approach to the Economic Analysis of Nonstationary Time Series"
