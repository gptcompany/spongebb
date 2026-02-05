# Phase 12: Nowcasting & Forecasting - Context

## Phase Goal

Estimate current/future liquidity before official releases and upgrade regime detection to probabilistic ensemble model.

## User Priorities

- **Focus**: Balanced (nowcasting accuracy + regime forecasting)
- **Regime States**: 3 (EXPANSION, NEUTRAL, CONTRACTION)
- **Complexity Level**: Advanced (Ensemble: HMM + Markov Switching + LSTM)

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Nowcast library | statsmodels UnobservedComponents | Production-grade, native ragged edge handling |
| Regime detection | HMM primary (hmmlearn) | Interpretable, regime persistence via transition matrix |
| Regime switching | statsmodels MarkovRegression | Parameter switching for enhanced accuracy |
| Forecasting | LSTM (PyTorch) | Non-linear dependencies, 7-30 day horizon |
| Ensemble | Weighted average | HMM 40% + Markov 30% + LSTM 30% |

## Technical Requirements

### 12-01: Liquidity Nowcast Engine
- **Input**: HF proxies (TGA daily, RRP daily, SOFR spread, VIX)
- **Output**: Net Liquidity nowcast with confidence intervals
- **Method**: Kalman filter (statsmodels state-space)
- **Update frequency**: Daily (8 AM when TGA/RRP released)
- **Validation**: Pseudo-real-time backtest vs official releases

### 12-02: PBoC Balance Sheet Estimator
- **Input**: SHIBOR (daily), DR007 (weekly), CNY-CNH spread
- **Output**: PBoC total assets estimate (2-3 weeks before official)
- **Method**: MIDAS regression + Ridge regularization
- **Validation**: MAPE < 5% vs official monthly release

### 12-03: Regime Forecaster (Ensemble)
- **Input**: Net Liquidity, Global Liquidity, Stealth QE Score
- **Output**: Regime probabilities for 3 states + 7/14/30 day forecast
- **Method**: Ensemble (HMM + Markov Switching + LSTM)
- **Persistence**: Transition matrix with high diagonal (>0.9)
- **Validation**: Accuracy > 75%, avoid spurious flips

### 12-04: Correlation Trend Predictor
- **Input**: Rolling correlations (30d, 90d) for BTC, SPX, GOLD, DXY
- **Output**: Predicted correlation direction (strengthening/weakening)
- **Method**: Rolling beta forecast + trend detection
- **Validation**: Directional accuracy > 60%

## Data Available

From Phase 11 (HF collectors):
- TGA daily (US Treasury FiscalData API)
- RRP daily (NY Fed Markets API)
- SOFR daily (NY Fed + FRED)
- SHIBOR/DR007 (akshare)
- Stablecoin supply (DefiLlama)
- Cross-currency basis (ECB)

## Dependencies

- Phase 7: Net Liquidity, Global Liquidity calculations
- Phase 8: RegimeClassifier (upgrade target), CorrelationEngine
- Phase 11: HF collectors (input data)

## Libraries to Add

```toml
# pyproject.toml additions
hmmlearn = "^0.3.3"      # HMM regime detection
filterpy = "^1.4.5"       # Kalman filter (optional, for prototyping)
torch = "^2.0"            # LSTM (CPU-only sufficient)
scikit-learn = "^1.4"     # Already present, for Ridge/preprocessing
```

## Architecture

```
src/liquidity/nowcasting/
├── __init__.py
├── engine.py                 # NowcastEngine orchestrator
├── kalman/
│   ├── __init__.py
│   ├── liquidity_state_space.py  # Custom state-space model
│   └── tuning.py                  # Q/R matrix estimation
├── midas/
│   ├── __init__.py
│   └── pboc_estimator.py     # PBoC MIDAS regression
├── regime/
│   ├── __init__.py
│   ├── hmm_classifier.py     # GaussianHMM wrapper
│   ├── markov_switching.py   # MarkovRegression wrapper
│   ├── lstm_forecaster.py    # LSTM regime forecaster
│   └── ensemble.py           # Weighted ensemble
├── correlation/
│   ├── __init__.py
│   └── trend_predictor.py    # Rolling beta forecast
└── validation/
    ├── __init__.py
    ├── backtesting.py        # Pseudo-real-time backtest
    └── metrics.py            # MAPE, accuracy, flip rate
```

## API Endpoints (Phase 9 extension)

- `GET /api/v1/nowcast/liquidity` - Current nowcast + CI
- `GET /api/v1/nowcast/pboc` - PBoC estimate
- `GET /api/v1/regime/forecast` - 7/14/30 day regime forecast
- `GET /api/v1/regime/probabilities` - Current ensemble probabilities
- `GET /api/v1/correlation/forecast` - Correlation trend predictions

## Dashboard Panels (Phase 10 extension)

- Nowcast vs Official (line chart with CI band)
- Regime Probabilities (stacked area chart, 3 colors)
- LSTM Forecast (regime prediction for next 30 days)
- Correlation Trends (heatmap with arrows)

## Success Criteria

1. **Nowcast MAPE < 3%** vs official Fed balance sheet release
2. **PBoC MAPE < 5%** vs official monthly release
3. **Regime accuracy > 75%** on held-out test set
4. **Regime flip rate < 15%** (avoid spurious changes)
5. **Forecast lead time**: 7-30 days for regime changes
6. **Latency**: < 500ms for real-time API endpoints

## Risks

| Risk | Mitigation |
|------|------------|
| HMM state ambiguity | Validate states against economic interpretation |
| LSTM overfitting | Dropout, early stopping, walk-forward validation |
| Data drift | Retrain ensemble monthly with rolling window |
| Feature correlation | PCA/regularization for multicollinearity |

---
*Created: 2026-02-05*
*Phase: 12 of 15*
