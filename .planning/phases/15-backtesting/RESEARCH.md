# RESEARCH.md: Backtesting Engine for Liquidity Regime-Based Trading

## Executive Summary

Research completata per Phase 15 del Global Liquidity Monitor.

**Key Findings:**
1. **VectorBT** è il framework raccomandato per backtesting regime-based
2. **QuantStats** per metriche e tear sheet generation
3. **FRED/ALFRED** fornisce dati point-in-time per evitare look-ahead bias
4. Monte Carlo richiede 10,000+ iterazioni per validità statistica
5. L'HMM classifier esistente si integra naturalmente con i segnali

---

## 1. Library Comparison

| Aspect | VectorBT | Backtesting.py | Backtrader |
|--------|----------|----------------|------------|
| **Speed** | Fastest (Numba) | Fast | Slow |
| **Macro Suitability** | Excellent | Good | Medium |
| **Weekly Data** | Native | Good | Good |
| **Multi-asset** | Excellent | Limited | Good |

**Raccomandazione**: VectorBT + QuantStats

### VectorBT Pros
- Operazioni vectorizzate su DataFrame
- Ottimizzazione parametri in secondi
- Portfolio analytics built-in
- Supporto nativo per regime filtering

### VectorBT Cons
- Versione PRO per features avanzate
- Learning curve più ripida
- No live trading built-in

---

## 2. Look-Ahead Bias Prevention

### Il Problema

I dati delle banche centrali hanno lag di pubblicazione:
- **WALCL**: Giovedì per settimana precedente (T+6)
- **TGA**: Giornaliero T+1
- **ECB/BoJ**: 1 settimana
- **PBoC**: 1 mese

### Soluzione: ALFRED (Archival FRED)

```python
from fredapi import Fred

fred = Fred(api_key='key')
walcl_pit = fred.get_series_as_of_date(
    'WALCL',
    realtime_start='2020-03-15',
    realtime_end='2020-03-15'
)
```

### Publication Lag Rules

| Data Source | Publication Lag | Backtest Lag |
|-------------|-----------------|--------------|
| WALCL | T+6 | 7 giorni |
| TGA | T+1 | 2 giorni |
| RRP | T+1 | 2 giorni |
| ECB Assets | T+7 | 8 giorni |
| PBoC | T+30 | 35 giorni |

---

## 3. Monte Carlo Simulation

### Approccio: Trade Sequence Shuffling

```python
def monte_carlo_shuffle(
    trade_returns: np.ndarray,
    n_simulations: int = 10_000,
    skip_rate: float = 0.10,
) -> dict:
    results = {'max_drawdowns': [], 'final_equity': []}

    for _ in range(n_simulations):
        shuffled = np.random.permutation(trade_returns)
        mask = np.random.random(len(shuffled)) > skip_rate
        filtered = shuffled[mask]
        equity_curve = np.cumprod(1 + filtered)
        results['max_drawdowns'].append(
            ((equity_curve / np.maximum.accumulate(equity_curve)) - 1).min()
        )

    return {
        'max_dd_5th': np.percentile(results['max_drawdowns'], 5),
        'max_dd_median': np.median(results['max_drawdowns']),
        'max_dd_95th': np.percentile(results['max_drawdowns'], 95),
    }
```

### Best Practices
- 10,000+ simulazioni
- Skip rate 5-15% per execution failures
- Report confidence intervals (5th/50th/95th)

---

## 4. Regime Attribution

### Metriche per Regime

```python
def compute_regime_attribution(returns, regimes):
    attribution = {}
    for regime in ['EXPANSION', 'CONTRACTION']:
        regime_returns = returns[regimes == regime]
        attribution[regime] = {
            'total_return': (1 + regime_returns).prod() - 1,
            'sharpe': regime_returns.mean() / regime_returns.std() * np.sqrt(252),
            'max_drawdown': compute_max_drawdown(regime_returns),
            'win_rate': (regime_returns > 0).mean() * 100,
        }
    return pd.DataFrame(attribution).T
```

### Key Metrics

| Metric | Target |
|--------|--------|
| Regime Sharpe | > 1.0 in favorable regime |
| Regime Hit Rate | > 60% |
| Transition Alpha | Positive |
| Conditional Drawdown | < 15% |

---

## 5. Integration con Codebase Esistente

### Componenti da Riutilizzare

| Component | Location | Use |
|-----------|----------|-----|
| HMMRegimeClassifier | `nowcasting/regime/hmm_classifier.py` | Signal generation |
| LiquidityStateSpace | `nowcasting/kalman/` | Nowcast features |
| NowcastBacktester | `nowcasting/validation/backtesting.py` | Walk-forward |
| RegimeVaR | `risk/regime_var.py` | Conditional risk |

### Architettura Proposta

```
src/liquidity/backtesting/
├── data/
│   ├── historical_loader.py    # FRED/ALFRED point-in-time
│   └── asset_loader.py         # BTC, SPX, ETF prices
├── signals/
│   └── regime_signals.py       # Regime-based long/short
├── engine/
│   ├── vectorbt_engine.py      # VectorBT wrapper
│   └── metrics.py              # Performance metrics
├── monte_carlo/
│   └── simulation.py           # MC stress testing
└── attribution/
    └── regime_attribution.py   # P&L by regime
```

---

## 6. Dependencies

```toml
vectorbt = "^0.28"
quantstats = "^0.0.62"
fredapi = "^0.5"  # già presente
```

---

*Research: 2026-02-06*
