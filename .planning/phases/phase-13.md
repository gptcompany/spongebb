# Phase 13: Risk Metrics

## Overview

Implement professional risk analytics for portfolio management. This addresses the critical gap of having no risk metrics (VaR, CVaR) while Bloomberg users have full risk analytics suites. The focus is on liquidity-regime-aware risk measurement.

## Goals

1. **Historical VaR**: Standard percentile-based Value at Risk
2. **Parametric VaR**: Distribution-based VaR (Normal, t-distribution)
3. **CVaR/ES**: Expected Shortfall for tail risk
4. **Liquidity-adjusted Risk**: Incorporate bid-ask spreads and market impact
5. **Regime VaR**: Conditional risk metrics for Expansion vs Contraction

## Dependencies

- Phase 12 (Nowcasting & Forecasting) - For regime predictions

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| RISK-01 | Historical VaR at 95%, 99% confidence | HIGH |
| RISK-02 | Parametric VaR with distribution choice | HIGH |
| RISK-03 | CVaR / Expected Shortfall calculation | HIGH |
| RISK-04 | Liquidity-adjusted risk metrics | MEDIUM |
| RISK-05 | Regime-conditional VaR | MEDIUM |

## Research Topics

1. **Riskfolio-Lib**
   - GitHub: https://github.com/dcajasn/Riskfolio-Lib (3,760 stars)
   - 24 risk measures: VaR, CVaR, EVaR, WVaR, TG, etc.
   - Portfolio optimization: MVO, MAD, CVaR optimization
   - Install: `pip install riskfolio-lib`

2. **quantstats**
   - GitHub: https://github.com/ranaroussi/quantstats (6,659 stars)
   - Performance metrics: Sharpe, Sortino, Calmar
   - VaR, CVaR built-in
   - HTML report generation
   - Install: `pip install quantstats`

3. **PyPortfolioOpt**
   - GitHub: https://github.com/PyPortfolio/PyPortfolioOpt (5,466 stars)
   - Mean-variance optimization
   - Black-Litterman model
   - Install: `pip install pyportfolioopt`

## Plans

### Plan 13-01: Historical VaR Calculator
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Implement historical simulation VaR.

**Methodology**:
```python
def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Historical VaR: percentile of return distribution
    VaR_α = -Percentile(returns, 1-α)

    Example: VaR_95 = -5th percentile of returns
    """
    return -np.percentile(returns, 100 * (1 - confidence))
```

**Deliverables**:
- `src/liquidity/risk/var.py`
- API endpoint: `GET /risk/var`
- Dashboard risk panel
- Tests in `tests/unit/test_risk/`

**Acceptance Criteria**:
- [ ] VaR at 95%, 99%, 99.5% confidence levels
- [ ] Rolling VaR (30d, 90d, 252d windows)
- [ ] Multiple assets (BTC, SPX, Portfolio)
- [ ] Backtesting validation (VaR breaches)

### Plan 13-02: Parametric VaR
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Implement distribution-based VaR with multiple distributions.

**Methodology**:
```python
def parametric_var(returns: pd.Series, confidence: float = 0.95,
                   dist: str = "normal") -> float:
    """
    Parametric VaR assuming distribution:
    - Normal: VaR = μ - σ * Z_α
    - t-distribution: VaR = μ - σ * t_α(ν)
    - Cornish-Fisher: VaR with skew/kurtosis adjustment
    """
    mu = returns.mean()
    sigma = returns.std()

    if dist == "normal":
        z = scipy.stats.norm.ppf(1 - confidence)
        return -(mu + sigma * z)
    elif dist == "t":
        # Fit t-distribution
        nu, _, _ = scipy.stats.t.fit(returns)
        t = scipy.stats.t.ppf(1 - confidence, nu)
        return -(mu + sigma * t)
```

**Deliverables**:
- Update `src/liquidity/risk/var.py`
- Distribution fitting module
- Tests in `tests/unit/test_risk/`

**Acceptance Criteria**:
- [ ] Normal distribution VaR
- [ ] Student-t distribution VaR
- [ ] Cornish-Fisher expansion VaR
- [ ] Distribution goodness-of-fit tests

### Plan 13-03: CVaR / Expected Shortfall
**Wave**: 1 | **Effort**: S | **Priority**: HIGH

Implement Conditional VaR (Expected Shortfall).

**Methodology**:
```python
def cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    CVaR: Average loss beyond VaR threshold
    CVaR_α = E[Loss | Loss > VaR_α]

    More coherent risk measure than VaR:
    - Subadditivity: CVaR(A+B) ≤ CVaR(A) + CVaR(B)
    - Better tail risk capture
    """
    var = historical_var(returns, confidence)
    return -returns[returns <= -var].mean()
```

**Deliverables**:
- Update `src/liquidity/risk/var.py` with CVaR
- API endpoint: `GET /risk/cvar`
- Tests in `tests/unit/test_risk/`

**Acceptance Criteria**:
- [ ] CVaR at 95%, 99% confidence
- [ ] Rolling CVaR
- [ ] CVaR/VaR ratio (tail risk indicator)
- [ ] Comparison chart VaR vs CVaR

### Plan 13-04: Liquidity-Adjusted Risk
**Wave**: 2 | **Effort**: M | **Priority**: MEDIUM

Incorporate liquidity costs into risk metrics.

**Methodology**:
```python
def liquidity_adjusted_var(returns: pd.Series,
                           bid_ask_spread: float,
                           volume: float,
                           position_size: float,
                           confidence: float = 0.95) -> float:
    """
    L-VaR = VaR + Liquidity Cost

    Liquidity Cost = 0.5 * spread + market_impact
    Market Impact = k * sqrt(position / ADV)

    Where:
    - spread: bid-ask spread in %
    - k: market impact coefficient (~0.1 for liquid)
    - ADV: average daily volume
    """
    base_var = historical_var(returns, confidence)

    # Liquidity cost
    half_spread = 0.5 * bid_ask_spread
    market_impact = 0.1 * np.sqrt(position_size / volume)
    liquidity_cost = half_spread + market_impact

    return base_var + liquidity_cost
```

**Deliverables**:
- `src/liquidity/risk/liquidity_risk.py`
- Bid-ask spread collector integration
- Tests in `tests/unit/test_risk/`

**Acceptance Criteria**:
- [ ] L-VaR for liquid assets (SPY, BTC)
- [ ] L-VaR for illiquid assets (small caps)
- [ ] Time-varying liquidity costs
- [ ] Stress scenario liquidity

### Plan 13-05: Regime-Conditional VaR
**Wave**: 2 | **Effort**: M | **Priority**: MEDIUM

Calculate VaR conditioned on liquidity regime.

**Methodology**:
```python
def regime_var(returns: pd.Series,
               regime: pd.Series,  # From regime classifier
               confidence: float = 0.95) -> dict:
    """
    Regime-conditional VaR:

    VaR_expansion = VaR(returns | regime == EXPANSION)
    VaR_contraction = VaR(returns | regime == CONTRACTION)

    Typically: VaR_contraction >> VaR_expansion
    """
    expansion_returns = returns[regime == "EXPANSION"]
    contraction_returns = returns[regime == "CONTRACTION"]

    return {
        "expansion_var": historical_var(expansion_returns, confidence),
        "contraction_var": historical_var(contraction_returns, confidence),
        "ratio": contraction_var / expansion_var
    }
```

**Deliverables**:
- `src/liquidity/risk/regime_risk.py`
- Integration with regime classifier
- Tests in `tests/unit/test_risk/`

**Acceptance Criteria**:
- [ ] Separate VaR for each regime
- [ ] Transition risk (entering contraction)
- [ ] Regime-switching VaR model
- [ ] Dashboard regime risk panel

## Technical Notes

### New Dependencies

```toml
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "riskfolio-lib>=4.0.0",  # Risk metrics & optimization
    "quantstats>=0.0.62",    # Performance analytics
]
```

### Module Structure

```
src/liquidity/risk/
├── __init__.py
├── var.py            # VaR implementations
├── cvar.py           # Expected Shortfall
├── liquidity_risk.py # Liquidity-adjusted metrics
├── regime_risk.py    # Regime-conditional risk
└── utils.py          # Distribution fitting, validation
```

### API Endpoints

```python
# New endpoints
GET /risk/var?asset=BTC&confidence=0.95&window=252
GET /risk/cvar?asset=BTC&confidence=0.95
GET /risk/regime?asset=BTC
GET /risk/portfolio?weights={"BTC":0.5,"SPY":0.5}
```

## Success Metrics

| Metric | Target |
|--------|--------|
| VaR breach rate (95%) | 5% ± 1% |
| VaR breach rate (99%) | 1% ± 0.5% |
| CVaR accuracy | <5% RMSE vs actual tail losses |
| Regime VaR ratio | Contraction/Expansion > 2x |

## References

- Riskfolio-Lib: https://riskfolio-lib.readthedocs.io/
- quantstats: https://github.com/ranaroussi/quantstats
- Jorion "Value at Risk" (3rd ed.)
- Basel III Liquidity Risk Framework
- Acerbi & Tasche (2002) "Expected Shortfall: A Natural Coherent Alternative to Value at Risk"
