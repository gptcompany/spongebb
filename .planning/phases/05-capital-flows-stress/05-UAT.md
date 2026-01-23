---
status: testing
phase: 05-capital-flows-stress
source: 05-01-PLAN.md, 05-02-PLAN.md, 05-03-PLAN.md, 05-04-PLAN.md, 05-05-PLAN.md
started: 2026-01-23T18:15:00Z
updated: 2026-01-23T18:15:00Z
---

## Current Test

number: 1
name: TIC Collector - Foreign Treasury Holdings
expected: |
  Run: `uv run python -c "from liquidity.collectors import TICCollector; import asyncio; c = TICCollector(); print(asyncio.run(c.collect_major_holders()))"`

  Should return a DataFrame showing top foreign holders of US Treasuries (Japan, China, UK, etc.)
  with columns: timestamp, series_id, source, value, unit
  Values should be in billions USD (Japan ~1.3T, China ~1T)
awaiting: user response

## Tests

### 1. TIC Collector - Foreign Treasury Holdings
expected: Run TICCollector.collect_major_holders(), returns DataFrame with top foreign Treasury holders (Japan ~1.3T, China ~1T USD)
result: [pending]

### 2. Fed Custody - Weekly Holdings
expected: Run FedCustodyCollector.collect_all(), returns weekly Fed custody data with ~$3T total holdings (WSEFINTL1, WMTSECL1, WFASECL1 series)
result: [pending]

### 3. Stress Indicators - SOFR-OIS Spread
expected: Run StressIndicatorCollector.collect_sofr_ois_spread(), returns spread in basis points (typically 0-15 bps in normal conditions)
result: [pending]

### 4. Stress Indicators - Regime Classification
expected: Run StressIndicatorCollector.get_current_regime(), returns "GREEN", "YELLOW", or "RED" based on current market stress levels
result: [pending]

### 5. Risk ETFs - Shares Outstanding
expected: Run RiskETFCollector.collect_current_shares(), returns shares outstanding for SPY, TLT, HYG, IEF, LQD (SPY should have ~900M+ shares)
result: [pending]

### 6. Risk ETFs - Risk Appetite Ratio
expected: Run RiskETFCollector.calculate_risk_appetite(), returns SPY/TLT ratio (~8-10 in neutral conditions) indicating risk-on vs risk-off sentiment
result: [pending]

### 7. COFER - Currency Reserves
expected: Run COFERCollector.collect_reserves_by_currency(), returns IMF reserve data with USD dominant (~56%), EUR (~20%), CNY growing
result: [pending]

### 8. COFER - De-dollarization Rate
expected: Run COFERCollector.calculate_dedollarization_rate(), returns YoY change in USD share (tracking gradual de-dollarization trend)
result: [pending]

### 9. Registry Integration - All Collectors
expected: Run `registry.list_collectors()`, should include: tic, fed_custody, stress, risk_etfs, cofer
result: [pending]

### 10. Integration Tests Pass
expected: Run `uv run pytest tests/integration/test_tic.py tests/integration/test_fed_custody.py tests/integration/test_stress.py tests/integration/test_risk_etfs.py tests/integration/test_cofer.py -v` - all tests pass (64+ passed, some skipped for API keys)
result: [pending]

## Summary

total: 10
passed: 0
issues: 0
pending: 10
skipped: 0

## Issues for /gsd:plan-fix

[none yet]
