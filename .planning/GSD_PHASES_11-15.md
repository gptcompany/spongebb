# GSD Pipeline: Phases 11-15

**Project**: Global Liquidity Monitor v2.0
**Created**: 2026-02-04
**Purpose**: Documento per ingestione in `/pipeline:gsd` fase per fase

---

## Panoramica Milestone 2 (v2.0)

Dopo il completamento di v1.0 (Phase 1-10), questa milestone aggiunge:
- **High-Frequency Data**: Riduzione lag da 7d a 1d
- **Nowcasting**: Stima liquidità prima dei rilasci ufficiali
- **Risk Metrics**: Analisi rischio professionale (VaR, CVaR)
- **News Intelligence**: Early warning da comunicazioni CB
- **Backtesting**: Validazione qualità segnali

### Esclusioni (per decisione utente)
- ❌ Satellite Imagery - Alto costo, basso ROI iniziale
- ✅ Credit Card Flows - Mantenuto via proxy FRED

---

## Quick Reference: Comandi GSD

```bash
# Per ogni fase, eseguire in sequenza:
/pipeline:gsd 11   # High-Frequency Data Layer
/pipeline:gsd 12   # Nowcasting & Forecasting
/pipeline:gsd 13   # Risk Metrics
/pipeline:gsd 14   # News Intelligence
/pipeline:gsd 15   # Backtesting Engine
```

---

## Phase 11: High-Frequency Data Layer

### Obiettivo
Ridurre data lag da settimanale a giornaliero, aggiungendo indicatori critici mancanti.

### Plans (6)
| Plan | Descrizione | Wave | Effort |
|------|-------------|------|--------|
| 11-01 | TGA Daily (Treasury FiscalData API) | 1 | M |
| 11-02 | NY Fed APIs (RRP, SOMA, Swap Lines) | 1 | M |
| 11-03 | China HF Proxies (DR007, SHIBOR via akshare) | 1 | M |
| 11-04 | Cross-Currency Basis (ECB/CME) | 2 | L |
| 11-05 | Stablecoin Supply (DefiLlama) | 2 | M |
| 11-06 | Credit Card Proxies (FRED consumer series) | 2 | M |

### Librerie Richieste
```bash
pip install akshare DeFiLlama
```

### Data Sources
- US Treasury FiscalData: https://fiscaldata.treasury.gov/
- NY Fed Markets: https://markets.newyorkfed.org/
- CFETS/SHIBOR: https://www.shibor.org/
- DefiLlama: https://defillama.com/docs/api

### Research Keywords
- DTS API, TGA daily, NY Fed API, akshare SHIBOR, cross-currency basis, stablecoin supply

---

## Phase 12: Nowcasting & Forecasting

### Obiettivo
Stimare liquidità corrente/futura prima dei rilasci ufficiali, ridurre lag PBoC da 30d a ~7d.

### Plans (4)
| Plan | Descrizione | Wave | Effort |
|------|-------------|------|--------|
| 12-01 | Liquidity Nowcast (Kalman filter) | 1 | L |
| 12-02 | PBoC Estimator (SHIBOR/DR007 regression) | 1 | M |
| 12-03 | Regime Forecaster (HMM + LSTM) | 2 | L |
| 12-04 | Correlation Predictor (rolling beta) | 2 | M |

### Librerie Richieste
```bash
pip install filterpy hmmlearn darts
```

### Methodology
- Kalman filter per state-space nowcasting
- Hidden Markov Model per regime detection
- Ridge regression per PBoC estimation
- ARIMA/LSTM per correlation forecasting

### Research Keywords
- Kalman filter macro, Markov switching regression, Dynamic Factor Model, nowcasting GDP

---

## Phase 13: Risk Metrics

### Obiettivo
Implementare analytics rischio professionali per gestione portfolio.

### Plans (5)
| Plan | Descrizione | Wave | Effort |
|------|-------------|------|--------|
| 13-01 | Historical VaR (95%, 99%) | 1 | M |
| 13-02 | Parametric VaR (Normal, t-dist) | 1 | M |
| 13-03 | CVaR / Expected Shortfall | 1 | S |
| 13-04 | Liquidity-Adjusted Risk | 2 | M |
| 13-05 | Regime-Conditional VaR | 2 | M |

### Librerie Richieste
```bash
pip install riskfolio-lib quantstats
```

### Formulas
- VaR_α = -Percentile(returns, 1-α)
- CVaR_α = E[Loss | Loss > VaR_α]
- L-VaR = VaR + 0.5*spread + market_impact

### Research Keywords
- Value at Risk Python, Expected Shortfall, regime-conditional risk, liquidity-adjusted VaR

---

## Phase 14: News Intelligence

### Obiettivo
Early warning via monitoring comunicazioni CB e news.

### Plans (5)
| Plan | Descrizione | Wave | Effort |
|------|-------------|------|--------|
| 14-01 | RSS Aggregator (7 CB feeds) | 1 | M |
| 14-02 | NLP Translation (CN→EN) | 1 | M |
| 14-03 | Sentiment Analyzer (finBERT) | 2 | L |
| 14-04 | Breaking News Alerts | 2 | M |
| 14-05 | News Dashboard Panel | 3 | M |

### Librerie Richieste
```bash
pip install transformers feedparser deepl
```

### CB Feed Sources
| CB | URL |
|----|-----|
| Fed | https://www.federalreserve.gov/feeds/press_all.xml |
| ECB | https://www.ecb.europa.eu/rss/press.html |
| PBoC | http://www.pbc.gov.cn/rss/ |
| BoJ | https://www.boj.or.jp/en/rss.xml |

### Research Keywords
- finBERT financial sentiment, central bank NLP, Loughran-McDonald dictionary

---

## Phase 15: Backtesting Engine

### Obiettivo
Validare qualità segnali e performance strategia storicamente.

### Plans (6)
| Plan | Descrizione | Wave | Effort |
|------|-------------|------|--------|
| 15-01 | Historical Data Loader (2010+) | 1 | L |
| 15-02 | Signal Generator (regime-based) | 1 | M |
| 15-03 | Strategy Backtester (multi-asset) | 2 | L |
| 15-04 | Performance Metrics (Sharpe, MaxDD) | 2 | M |
| 15-05 | Monte Carlo Simulation | 3 | L |
| 15-06 | Regime P&L Analysis | 3 | M |

### Librerie Richieste
```bash
pip install quantstats pyfolio-reloaded pyarrow
```

### Target Metrics
- Signal Sharpe (BTC) > 1.0
- Signal Sharpe (SPY) > 0.5
- Regime timing accuracy > 60%

### Research Keywords
- quantstats backtest, pyfolio tear sheet, Monte Carlo portfolio simulation

---

## Dipendenze tra Fasi

```
Phase 10 (Complete)
     │
     ▼
Phase 11 (HF Data) ─────────────────────────┐
     │                                       │
     ├─────────────────┐                    │
     ▼                 ▼                    ▼
Phase 12 (Nowcast)  Phase 14 (News)     (parallel)
     │
     ▼
Phase 13 (Risk)
     │
     ▼
Phase 15 (Backtest)
```

**Nota**: Phase 11 è prerequisito per tutte le altre. Phase 14 può essere eseguita in parallelo a 12-13.

---

## Stima Effort Totale

| Phase | Plans | Effort (giorni) |
|-------|-------|-----------------|
| 11 | 6 | 8-10 |
| 12 | 4 | 6-8 |
| 13 | 5 | 5-7 |
| 14 | 5 | 7-9 |
| 15 | 6 | 8-10 |
| **Totale** | **26** | **34-44** |

---

## Files di Riferimento

- Audit completo: `.planning/AUDIT_SWOT_2026-02.md`
- ROADMAP aggiornato: `.planning/ROADMAP.md`
- Phase details:
  - `.planning/phases/phase-11.md`
  - `.planning/phases/phase-12.md`
  - `.planning/phases/phase-13.md`
  - `.planning/phases/phase-14.md`
  - `.planning/phases/phase-15.md`

---

## GitHub Libraries Reference

| Library | Stars | Use |
|---------|-------|-----|
| akshare | 15,986 | China financial data |
| riskfolio-lib | 3,760 | Risk metrics |
| quantstats | 6,659 | Backtest analytics |
| darts | 9,184 | Forecasting |
| hmmlearn | 3,378 | Regime detection |
| filterpy | 3,763 | Kalman filters |
| finBERT | 1,984 | Financial NLP |

---

## Comandi Utili

```bash
# Verificare stato progetto
cd /media/sam/1TB/spongebb

# Run tests
uv run pytest tests/ -v

# Run validation
./scripts/validate.sh

# Start dashboard
./scripts/run-dashboard.sh

# Check roadmap
cat .planning/ROADMAP.md
```

---

*Documento creato per ingestione in GSD pipeline*
*Last updated: 2026-02-04*
