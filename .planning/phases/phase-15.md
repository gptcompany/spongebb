# Phase 15: Backtesting Engine

## Overview

Implement a comprehensive backtesting framework to validate signal quality before live trading. This addresses the critical gap of having no way to test if the liquidity-based signals actually generate alpha historically.

## Goals

1. **Historical Data Loader**: Load 2010+ data from FRED archives
2. **Signal Generator**: Generate regime-based trading signals
3. **Strategy Backtester**: Test long/short strategies on multiple assets
4. **Performance Metrics**: Sharpe, Sortino, MaxDD, Calmar
5. **Monte Carlo**: Distribution of outcomes via simulation
6. **Regime Analysis**: P&L attribution by liquidity regime

## Dependencies

- Phase 13 (Risk Metrics) - For VaR integration in backtests

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| BT-01 | Historical data loader (2010-present) | HIGH |
| BT-02 | Signal generator from regime classifier | HIGH |
| BT-03 | Multi-asset strategy backtester | HIGH |
| BT-04 | Standard performance metrics | HIGH |
| BT-05 | Monte Carlo simulation | MEDIUM |
| BT-06 | Regime-based P&L attribution | MEDIUM |

## Research Topics

1. **quantstats**
   - GitHub: https://github.com/ranaroussi/quantstats (6,659 stars)
   - Tear sheets, metrics, HTML reports
   - VaR, Sharpe, Sortino, drawdown analysis
   - Install: `pip install quantstats`

2. **pyfolio**
   - GitHub: https://github.com/quantopian/pyfolio (6,219 stars)
   - Professional portfolio analytics
   - Tear sheets, factor analysis
   - Install: `pip install pyfolio-reloaded`

3. **vectorbt**
   - GitHub: https://github.com/polakowo/vectorbt (4,234 stars)
   - Vectorized backtesting (very fast)
   - Portfolio simulation
   - Install: `pip install vectorbt`

4. **backtrader**
   - Classic event-driven backtester
   - Multiple data feeds, indicators
   - Install: `pip install backtrader`

## Plans

### Plan 15-01: Historical Data Loader
**Wave**: 1 | **Effort**: L | **Priority**: HIGH

Load and process historical data from 2010 to present.

**Data Sources**:
```python
HISTORICAL_SOURCES = {
    # Fed Balance Sheet
    "WALCL": {"source": "FRED", "start": "2002-12-18"},
    "WTREGEN": {"source": "FRED", "start": "2002-12-18"},
    "RRPONTSYD": {"source": "FRED", "start": "2013-09-23"},

    # Asset Prices
    "BTC": {"source": "Yahoo", "ticker": "BTC-USD", "start": "2014-09-17"},
    "SPY": {"source": "Yahoo", "ticker": "SPY", "start": "1993-01-29"},
    "TLT": {"source": "Yahoo", "ticker": "TLT", "start": "2002-07-30"},

    # Global CB (where available)
    "ECBASSETSW": {"source": "FRED", "start": "1999-01-01"},
    "JPNASSETS": {"source": "FRED", "start": "1998-04-01"},
}
```

**Deliverables**:
- `src/liquidity/backtesting/data_loader.py`
- `src/liquidity/backtesting/data_cache.py`
- Parquet file caching for fast reload
- Tests in `tests/unit/test_backtesting/`

**Acceptance Criteria**:
- [ ] Loads all FRED series from 2010+
- [ ] Loads asset prices from Yahoo
- [ ] Handles missing data (interpolation/forward-fill)
- [ ] Caches to Parquet for fast reload
- [ ] Date alignment across all series

### Plan 15-02: Signal Generator
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Generate trading signals from regime classifier output.

**Signal Logic**:
```python
def generate_signals(regime: pd.Series,
                     intensity: pd.Series,
                     stealth_qe: pd.Series) -> pd.DataFrame:
    """
    Signal generation rules:

    LONG conditions (bullish liquidity):
    - Regime == EXPANSION AND intensity > 60
    - OR Regime change: CONTRACTION → EXPANSION
    - OR Stealth QE > 7 (hidden QE)

    SHORT conditions (bearish liquidity):
    - Regime == CONTRACTION AND intensity > 60
    - OR Regime change: EXPANSION → CONTRACTION
    - OR Stealth QE < 3 (hidden QT)

    Position sizing:
    - Base: 100% allocation
    - Scale by intensity: 50% + (intensity/100) * 50%
    """
    signals = pd.DataFrame(index=regime.index)
    signals["signal"] = 0  # -1 = short, 0 = flat, 1 = long
    signals["position_size"] = 0.0

    # ... signal logic
    return signals
```

**Deliverables**:
- `src/liquidity/backtesting/signal_generator.py`
- Multiple signal variations (conservative, aggressive)
- Tests in `tests/unit/test_backtesting/`

**Acceptance Criteria**:
- [ ] Clear signal generation rules
- [ ] Position sizing based on intensity
- [ ] Regime change detection
- [ ] Signal visualization
- [ ] Configurable parameters

### Plan 15-03: Strategy Backtester
**Wave**: 2 | **Effort**: L | **Priority**: HIGH

Implement backtesting engine for multiple assets.

**Methodology**:
```python
def backtest_strategy(signals: pd.DataFrame,
                      prices: pd.DataFrame,
                      transaction_cost: float = 0.001,
                      slippage: float = 0.0005) -> pd.DataFrame:
    """
    Event-driven backtest:

    For each day:
    1. Get signal for today
    2. If signal changed, execute trade
    3. Apply transaction costs + slippage
    4. Calculate daily P&L
    5. Track positions, equity curve

    Assets: BTC, SPY, 60/40 portfolio
    """
    results = pd.DataFrame(index=prices.index)
    results["position"] = 0
    results["pnl"] = 0.0
    results["equity"] = 100.0  # Starting equity

    # ... backtest loop
    return results
```

**Deliverables**:
- `src/liquidity/backtesting/backtester.py`
- Multi-asset support
- Transaction cost modeling
- Tests in `tests/unit/test_backtesting/`

**Acceptance Criteria**:
- [ ] Backtests on BTC, SPY, TLT
- [ ] Portfolio backtests (60/40, risk parity)
- [ ] Realistic transaction costs
- [ ] Trade log with entry/exit prices
- [ ] Equity curve generation

### Plan 15-04: Performance Metrics
**Wave**: 2 | **Effort**: M | **Priority**: HIGH

Calculate standard and liquidity-specific performance metrics.

**Metrics**:
```python
PERFORMANCE_METRICS = {
    # Return metrics
    "total_return": "Cumulative return",
    "cagr": "Compound annual growth rate",
    "annualized_return": "Annualized return",

    # Risk-adjusted
    "sharpe_ratio": "Sharpe (risk-free = 0)",
    "sortino_ratio": "Sortino (downside deviation)",
    "calmar_ratio": "CAGR / Max Drawdown",
    "omega_ratio": "Probability-weighted gains/losses",

    # Drawdown
    "max_drawdown": "Maximum peak-to-trough decline",
    "avg_drawdown": "Average drawdown",
    "max_drawdown_duration": "Longest drawdown in days",

    # Trade statistics
    "win_rate": "Percentage of winning trades",
    "profit_factor": "Gross profit / Gross loss",
    "avg_win": "Average winning trade",
    "avg_loss": "Average losing trade",

    # Custom liquidity metrics
    "expansion_return": "Return during EXPANSION regime",
    "contraction_return": "Return during CONTRACTION regime",
    "regime_sharpe": "Sharpe by regime",
}
```

**Deliverables**:
- `src/liquidity/backtesting/metrics.py`
- HTML tear sheet generation (quantstats)
- Tests in `tests/unit/test_backtesting/`

**Acceptance Criteria**:
- [ ] All standard metrics calculated
- [ ] Regime-specific metrics
- [ ] HTML report generation
- [ ] Comparison to benchmarks (buy-hold)

### Plan 15-05: Monte Carlo Simulation
**Wave**: 3 | **Effort**: L | **Priority**: MEDIUM

Simulate distribution of outcomes via bootstrapping.

**Methodology**:
```python
def monte_carlo_simulation(returns: pd.Series,
                           n_simulations: int = 10000,
                           n_days: int = 252) -> dict:
    """
    Bootstrap simulation:

    1. Sample daily returns with replacement
    2. Compound to get terminal wealth
    3. Repeat n_simulations times
    4. Calculate percentiles: 5%, 25%, 50%, 75%, 95%

    Output:
    - Distribution of terminal wealth
    - Probability of loss
    - Expected shortfall
    - Confidence intervals
    """
    terminal_values = []
    for _ in range(n_simulations):
        sampled = np.random.choice(returns, size=n_days, replace=True)
        terminal = np.prod(1 + sampled)
        terminal_values.append(terminal)

    return {
        "median": np.percentile(terminal_values, 50),
        "p5": np.percentile(terminal_values, 5),
        "p95": np.percentile(terminal_values, 95),
        "prob_loss": np.mean([t < 1 for t in terminal_values]),
    }
```

**Deliverables**:
- `src/liquidity/backtesting/monte_carlo.py`
- Distribution visualization
- Tests in `tests/unit/test_backtesting/`

**Acceptance Criteria**:
- [ ] 10,000 simulation runs
- [ ] Percentile distribution
- [ ] Probability of loss
- [ ] Visualization (histogram, fan chart)

### Plan 15-06: Regime Transition P&L Analysis
**Wave**: 3 | **Effort**: M | **Priority**: MEDIUM

Analyze P&L attribution by regime and transitions.

**Analysis**:
```python
def regime_pnl_analysis(backtest_results: pd.DataFrame,
                        regime: pd.Series) -> dict:
    """
    P&L breakdown:

    1. By regime state:
       - EXPANSION returns
       - CONTRACTION returns
       - Flat returns

    2. By regime transition:
       - EXPANSION → CONTRACTION (regime shift short)
       - CONTRACTION → EXPANSION (regime shift long)
       - Within regime (trend following)

    3. By signal accuracy:
       - Correct regime calls
       - False signals
       - Missed opportunities
    """
    analysis = {
        "by_regime": {},
        "by_transition": {},
        "signal_accuracy": {},
    }
    # ... analysis logic
    return analysis
```

**Deliverables**:
- `src/liquidity/backtesting/regime_analysis.py`
- Attribution report
- Tests in `tests/unit/test_backtesting/`

**Acceptance Criteria**:
- [ ] P&L split by regime
- [ ] Transition timing analysis
- [ ] Signal accuracy metrics
- [ ] Visualization of regime P&L

## Technical Notes

### New Dependencies

```toml
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "quantstats>=0.0.62",       # Performance analytics
    "pyfolio-reloaded>=0.9.5",  # Tear sheets
    "pyarrow>=15.0.0",          # Parquet support
]
```

### Module Structure

```
src/liquidity/backtesting/
├── __init__.py
├── data_loader.py        # Historical data loading
├── data_cache.py         # Parquet caching
├── signal_generator.py   # Signal generation
├── backtester.py         # Core backtest engine
├── metrics.py            # Performance metrics
├── monte_carlo.py        # Simulation
├── regime_analysis.py    # Regime P&L attribution
├── reports/
│   ├── __init__.py
│   ├── tearsheet.py      # HTML report generation
│   └── templates/        # Report templates
└── strategies/
    ├── __init__.py
    ├── base.py           # Base strategy class
    ├── regime_follow.py  # Regime-following strategy
    └── mean_revert.py    # Mean reversion strategy
```

### API Endpoints

```python
# New endpoints
POST /backtest/run
  body: {"strategy": "regime_follow", "asset": "BTC", "start": "2015-01-01"}
  returns: backtest_id

GET /backtest/{backtest_id}/results
GET /backtest/{backtest_id}/metrics
GET /backtest/{backtest_id}/tearsheet  # HTML download
```

## Success Metrics

| Metric | Target |
|--------|--------|
| Data coverage | 2010-present |
| Backtest speed | <10s for 10-year BTC |
| Signal Sharpe (BTC) | >1.0 |
| Signal Sharpe (SPY) | >0.5 |
| Regime timing accuracy | >60% |

## Sample Backtest Results (Expected)

Based on Hayes framework historical analysis:

| Strategy | Asset | Period | CAGR | Sharpe | MaxDD |
|----------|-------|--------|------|--------|-------|
| Regime Follow | BTC | 2015-2025 | ~45% | ~1.2 | ~60% |
| Regime Follow | SPY | 2010-2025 | ~12% | ~0.8 | ~25% |
| Buy & Hold | BTC | 2015-2025 | ~60% | ~0.9 | ~85% |
| Buy & Hold | SPY | 2010-2025 | ~10% | ~0.6 | ~35% |

*Note: Regime following should have lower returns but better risk-adjusted performance.*

## References

- quantstats: https://github.com/ranaroussi/quantstats
- pyfolio: https://github.com/quantopian/pyfolio
- vectorbt: https://vectorbt.dev/
- "Advances in Financial Machine Learning" - Marcos López de Prado
- "Active Portfolio Management" - Grinold & Kahn
