# Phase 13: Risk Metrics - Context

**Date:** 2026-02-05
**Status:** Discuss complete

## Phase Goal

Professional risk analytics per portfolio management, con integrazione NautilusTrader macro filter.

## Requirements from ROADMAP

- RISK-01: Historical VaR (95%, 99% confidence)
- RISK-02: Parametric VaR (Normal/t-distribution)
- RISK-03: CVaR / Expected Shortfall
- RISK-04: Liquidity-adjusted risk metrics
- RISK-05: Regime-conditional VaR (Expansion vs Contraction)

## User Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Default VaR level | 95% | Standard per day-to-day risk, meno conservativo |
| Library | riskfolio-lib | Feature-rich, vale l'overhead di CVXPY |
| NautilusTrader | Sì, macro filter | Integrazione prioritaria in questa fase |

## Existing Components to Leverage

### From Phase 12 (Nowcasting)
- `RegimeEnsemble.get_regime_probabilities()` → regime weights per conditional VaR
- `CorrelationTrendPredictor.predict()` → correlation breakdown risk

### From Phase 8 (Analyzers)
- `RegimeClassifier.classify()` → current regime state
- `CorrelationEngine` → rolling correlations

### Data Sources
- Asset returns: Yahoo Finance via collectors
- Liquidity series: Net Liquidity, Global Liquidity da Phase 7

## Integration Points

### NautilusTrader Macro Filter
```python
class LiquidityRiskFilter:
    """Macro filter per NautilusTrader strategies."""

    def should_trade(self, regime: str, var_level: float) -> bool:
        """Determina se tradare basandosi su regime e rischio."""
        if regime == "CONTRACTION" and var_level > threshold:
            return False  # Regime avverso, alto rischio
        return True

    def position_size_multiplier(self, regime: str) -> float:
        """Scala posizioni per regime."""
        multipliers = {
            "EXPANSION": 1.2,
            "NEUTRAL": 1.0,
            "CONTRACTION": 0.5
        }
        return multipliers.get(regime, 1.0)
```

## Deliverables

### Plan 13-01: Historical VaR Calculator
- VaR a 95% e 99% confidence
- Rolling window (252d default)
- Support per multi-asset

### Plan 13-02: Parametric VaR
- Normal distribution VaR
- t-distribution VaR (per fat tails)
- Parameter estimation da dati

### Plan 13-03: CVaR / Expected Shortfall
- Historical CVaR
- Parametric CVaR
- Confronto VaR vs CVaR

### Plan 13-04: Liquidity-Adjusted Metrics
- LAVaR con spread cost
- Liquidity factor integration
- Stress scenario multipliers

### Plan 13-05: Regime-Conditional VaR
- VaR per regime (EXPANSION/CONTRACTION)
- Weighted VaR con regime probabilities
- NautilusTrader macro filter interface

## File Structure

```
src/liquidity/risk/
├── __init__.py
├── var/
│   ├── __init__.py
│   ├── historical.py       # Historical simulation VaR
│   └── parametric.py       # Normal/t-dist VaR
├── cvar.py                 # Expected Shortfall
├── regime_var.py           # Regime-conditional VaR
├── liquidity_adjusted.py   # LAVaR
├── macro_filter.py         # NautilusTrader integration
└── reporting.py            # Risk reports
```

## Dependencies

```toml
riskfolio-lib = "^7.2"      # Portfolio risk (brings CVXPY)
```

## Out of Scope

- Portfolio optimization (future phase)
- Real-time VaR updates (batch only)
- Credit risk (CDS, default prob)

## Success Criteria

1. VaR/CVaR calcolati correttamente (validati vs riskfolio-lib)
2. Regime-conditional VaR segmenta correttamente per stato
3. NautilusTrader filter funzionante con unit tests
4. API endpoints per risk metrics
5. Dashboard panel con risk summary

---
*Generated: 2026-02-05*
