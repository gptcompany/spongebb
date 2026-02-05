# Research: Phase 13 - Risk Metrics

**Date:** 2026-02-05
**Phase:** 13 - Risk Metrics
**Keywords:** VaR, CVaR, Expected Shortfall, Regime-conditional, Liquidity-adjusted

## Executive Summary

Phase 13 richiede l'implementazione di metriche di rischio professionali per portfolio management. Le metriche core sono:
- **VaR (Value at Risk)**: Perdita massima attesa a un dato livello di confidenza
- **CVaR/ES (Expected Shortfall)**: Media delle perdite oltre il VaR (tail risk)
- **Regime-conditional VaR**: VaR segmentato per regime di liquidità

## Metodologie VaR

### 1. Historical Simulation (Non-parametrico)
- Usa distribuzione empirica dei rendimenti
- `VaR(α) = np.percentile(returns, α * 100)`
- Pro: No assunzioni sulla distribuzione
- Contro: Sensibile a window size, ignora eventi non ancora osservati

### 2. Parametric (Variance-Covariance)
- Assume distribuzione normale o t-Student
- `VaR(α) = μ - σ × z_α`
- Pro: Semplice, veloce
- Contro: Sottostima tail risk se distribuzione non normale

### 3. Monte Carlo Simulation
- Genera scenari dalla distribuzione fittata
- Calcola VaR dalla distribuzione simulata
- Pro: Flessibile, può catturare non-linearità
- Contro: Computazionalmente costoso

## CVaR / Expected Shortfall

Formula:
```
CVaR(α) = E[Loss | Loss > VaR(α)]
         = (1/(1-α)) × ∫[α,1] VaR(u) du
```

Per calcolo empirico:
```python
var_threshold = np.percentile(returns, (1-confidence)*100)
cvar = returns[returns <= var_threshold].mean()
```

## Regime-Conditional Risk

L'insight chiave: il rischio varia drasticamente per regime di liquidità.

| Regime | Volatility Multiplier | Tail Thickness |
|--------|----------------------|----------------|
| EXPANSION | 0.8x | Thinner tails |
| NEUTRAL | 1.0x | Normal |
| CONTRACTION | 1.5-2.0x | Fat tails |

Approccio:
1. Calcola VaR/CVaR per ogni regime separatamente
2. Usa modello di regime (HMM/Markov) per probabilità corrente
3. Risk = Σ P(regime) × VaR(regime)

## Liquidity-Adjusted VaR (LAVaR)

LAVaR incorpora costo di liquidità nel VaR:

```
LAVaR = VaR + Liquidity Cost
      = VaR + (spread/2) × position_size × volatility_factor
```

Utile per asset illiquidi o posizioni large.

## Librerie Python Raccomandate

### 1. riskfolio-lib (v7.2)
- CVaR, EVaR, RLVaR supportati
- Ottimizzazione portfolio con vincoli di rischio
- Richiede MOSEK solver per CVaR (CLARABEL può fallire)

### 2. quantstats
- Metriche di performance e rischio
- VaR, CVaR, Sortino, Calmar, Max Drawdown
- Integrazione con Pandas

### 3. scipy.stats
- Distribuzioni parametriche (norm, t)
- PPF per quantili analitici

### 4. Implementazione custom
- Per controllo totale e integrazione con regime classifier
- Usa numpy/pandas per calcoli base

## Design Proposto

```
src/liquidity/risk/
├── __init__.py
├── var.py              # Historical, Parametric, Monte Carlo VaR
├── cvar.py             # Expected Shortfall
├── regime_var.py       # Regime-conditional VaR
├── liquidity_adjusted.py  # LAVaR
└── reporting.py        # Risk report generator
```

### Integrazione con Phase 12

Usa output di:
- `RegimeEnsemble.get_regime_probabilities()` → regime weights
- `CorrelationTrendPredictor.predict()` → breakdown risk

## Confidence Levels Standard

| Use Case | VaR Level | CVaR Level |
|----------|-----------|------------|
| Day-to-day | 95% | 95% |
| Regulatory (Basel III) | 99% | 97.5% |
| Stress testing | 99.9% | 99% |

## Validation Strategy

1. **Backtesting**: Kupiec test per VaR exceedances
2. **Christoffersen test**: Independence di exceedances
3. **Regime accuracy**: VaR conditional su regime vs unconditional

## References

Sources:
- [QuantInsti CVaR Guide](https://blog.quantinsti.com/cvar-expected-shortfall/)
- [PyQuant News VaR/CVaR](https://www.pyquantnews.com/free-python-resources/risk-metrics-in-python-var-and-cvar-guide)
- [IBKR Quant Risk Metrics](https://www.interactivebrokers.com/campus/ibkr-quant-news/risk-metrics-in-python-var-and-cvar-guide/)
- [Riskfolio-Lib Docs](https://riskfolio-lib.readthedocs.io/)
- [Wikipedia Expected Shortfall](https://en.wikipedia.org/wiki/Expected_shortfall)
- [TommasoBelluzzo/SystemicRisk](https://github.com/TommasoBelluzzo/SystemicRisk)

---
*Generated: 2026-02-05*
