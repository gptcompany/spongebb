# Phase 15 Context: Backtesting Engine

## Obiettivo

Validare la qualità dei segnali di regime e le performance delle strategie attraverso backtesting storico.

## Scope

### In Scope
- Historical data loader (2010-present)
- Signal generator basato su regime
- Strategy backtester (BTC, SPX, multi-asset)
- Performance metrics (Sharpe, Sortino, MaxDD, Calmar)
- Monte Carlo simulation
- Regime transition P&L analysis

### Out of Scope
- Live trading integration
- High-frequency backtesting (<daily)
- Paper trading

## Decisioni Tecniche

| Decisione | Scelta | Rationale |
|-----------|--------|-----------|
| Framework | VectorBT | Veloce, vectorizzato, regime filtering nativo |
| Metrics | QuantStats | Tear sheets completi, MC built-in |
| Point-in-time data | ALFRED via fredapi | Evita look-ahead bias |
| Publication lag | 7 giorni per CB data | Match schedule reale |
| Monte Carlo | 10,000 sims, 10% skip | Standard industry |

## Componenti Esistenti da Riutilizzare

1. **HMMRegimeClassifier** (`nowcasting/regime/hmm_classifier.py`)
   - `predict_sequence()` per generare segnali
   - Stati: EXPANSION, NEUTRAL, CONTRACTION

2. **NowcastBacktester** (`nowcasting/validation/backtesting.py`)
   - Framework walk-forward esistente
   - Può essere esteso per multi-asset

3. **RegimeVaR** (`risk/regime_var.py`)
   - Risk metrics condizionali al regime
   - Integration per risk-adjusted returns

4. **LiquidityStateSpace** (`nowcasting/kalman/`)
   - Nowcast features per segnali più tempestivi

## Data Sources

| Asset | Source | Periodo |
|-------|--------|---------|
| Fed Balance Sheet | FRED/ALFRED | 2010-present |
| ECB/BoJ Assets | FRED | 2010-present |
| BTC | Yahoo Finance | 2014-present |
| SPX | Yahoo Finance | 2010-present |
| Gold (GLD) | Yahoo Finance | 2010-present |
| TLT | Yahoo Finance | 2010-present |

## Strategie da Testare

1. **Regime Long/Short**
   - EXPANSION: Long risk assets
   - CONTRACTION: Short risk / Long safe haven

2. **Regime Momentum**
   - Long when regime trending positive
   - Exit on regime reversal

3. **Multi-Asset Allocation**
   - Dynamic allocation basata su regime
   - BTC/SPX/Gold/TLT weights

## Acceptance Criteria

- [ ] Backtest dal 2010 senza look-ahead bias
- [ ] Sharpe ratio calcolato correttamente
- [ ] Monte Carlo con 10,000+ simulazioni
- [ ] P&L breakdown per regime
- [ ] Transition analysis completa
- [ ] Unit tests per ogni componente

## Rischi e Mitigazioni

| Rischio | Mitigazione |
|---------|-------------|
| Look-ahead bias | ALFRED point-in-time + publication lag |
| Overfitting | Walk-forward validation + Monte Carlo |
| Regime classification lag | Use HMM smoothed states |
| Data gaps | Forward-fill con validation |

## Timeline Stimata

- Plan 15-01: Historical loader - Wave 1
- Plan 15-02: Signal generator - Wave 1
- Plan 15-03: Strategy backtester - Wave 2
- Plan 15-04: Performance metrics - Wave 2
- Plan 15-05: Monte Carlo - Wave 3
- Plan 15-06: Regime P&L analysis - Wave 3

---
*Created: 2026-02-06*
