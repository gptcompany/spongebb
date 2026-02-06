# Phase 19: Real Rates - Context

## Goal

Real rates tracking e analisi correlazione oil-real rates. I tassi reali (TIPS yields) sono indicatori chiave per:
- Valutare se la politica monetaria è veramente restrittiva/accomodante
- Prevedere movimenti oil (correlazione inversa: real rates ↑ → oil ↓)
- Calcolare breakeven inflation expectations

## Requirements (from ROADMAP)

| ID | Requirement |
|----|-------------|
| RATES-01 | TIPS yield collector (10Y, 5Y) |
| RATES-02 | Breakeven inflation calculator |
| RATES-03 | Oil-real rates correlation analysis |

## Plans

| Plan | Description | Effort | Wave |
|------|-------------|--------|------|
| 19-01 | Real rates collector (10Y TIPS, 5Y TIPS via FRED) | S | 1 |
| 19-02 | Breakeven inflation calculator (BEI = nominal - real) | S | 1 |
| 19-03 | Oil-real rates correlation engine | M | 1 |
| 19-04 | Inflation expectations dashboard panel | M | 2 |

## Technical Approach

### Plan 19-01: Real Rates Collector

**FRED Series:**
- `DFII10` - 10-Year Treasury Inflation-Indexed Security, Constant Maturity (daily)
- `DFII5` - 5-Year Treasury Inflation-Indexed Security, Constant Maturity (daily)
- `DGS10` - 10-Year Treasury Constant Maturity Rate (già in FRED collector)
- `DGS5` - 5-Year Treasury Constant Maturity Rate

**Implementation:**
- Estendere `SERIES_MAP` in `collectors/fred.py` con le serie TIPS
- Nuova funzione `fetch_real_rates()` che ritorna DataFrame con:
  - `tips_10y`: DFII10
  - `tips_5y`: DFII5
  - `nominal_10y`: DGS10
  - `nominal_5y`: DGS5

### Plan 19-02: Breakeven Inflation Calculator

**Formula:**
```
BEI_10Y = DGS10 - DFII10  (10-year breakeven)
BEI_5Y = DGS5 - DFII5     (5-year breakeven)
5Y5Y Forward = BEI_10Y - BEI_5Y  (5-year, 5-year forward inflation)
```

**Implementation:**
- Nuovo modulo `src/liquidity/analyzers/real_rates.py`
- Classe `RealRatesAnalyzer` con metodi:
  - `calculate_breakeven()` → BEI series
  - `calculate_forward_inflation()` → 5Y5Y forward
  - `get_current_state()` → snapshot con valori attuali

### Plan 19-03: Oil-Real Rates Correlation

**Rationale:**
- Oil e real rates hanno correlazione inversa storica (~-0.4 to -0.6)
- Real rates ↑ → USD ↑ → Oil ↓ (pricing in USD)
- Real rates ↑ → growth expectations ↓ → Oil demand ↓

**Implementation:**
- Estendere `correlation_engine.py` con:
  - Nuovo asset: "REAL_10Y" (DFII10)
  - Nuova funzione `compute_oil_real_correlation()`
  - Rolling correlation oil vs real rates (30d, 90d)

### Plan 19-04: Dashboard Panel

**Components:**
- Real rates chart (TIPS 10Y, 5Y)
- Breakeven inflation chart (BEI 10Y, 5Y, 5Y5Y forward)
- Oil vs Real Rates scatter plot con regressione
- Correlation heatmap (oil, real rates, BEI)

**Implementation:**
- Nuovo file `dashboard/components/inflation.py`
- Integrazione in `layout.py`

## Dependencies

- **Phase 16**: EIA oil data (per correlazione)
- **Phase 1**: FRED collector base
- **Phase 8**: Correlation engine

## Files to Create/Modify

| Action | File |
|--------|------|
| MODIFY | `src/liquidity/collectors/fred.py` (add TIPS series) |
| CREATE | `src/liquidity/analyzers/real_rates.py` |
| MODIFY | `src/liquidity/analyzers/correlation_engine.py` (add oil-rates) |
| CREATE | `src/liquidity/dashboard/components/inflation.py` |
| MODIFY | `src/liquidity/dashboard/layout.py` (add panel) |
| CREATE | `tests/unit/test_real_rates.py` |
| CREATE | `tests/integration/test_real_rates_integration.py` |

## Validation Criteria

- [ ] FRED collector fetches DFII10, DFII5 senza errori
- [ ] BEI calculation matches Bloomberg/FRED derivati
- [ ] Correlation oil-real rates ~-0.4 to -0.6 (storico)
- [ ] Dashboard panel renderizza senza errori
- [ ] Test coverage > 80% per nuovo codice
