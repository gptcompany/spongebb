---
status: complete
phase: 05-capital-flows-stress
source: 05-01-PLAN.md, 05-02-PLAN.md, 05-03-PLAN.md, 05-04-PLAN.md, 05-05-PLAN.md
started: 2026-01-23T18:15:00Z
updated: 2026-01-23T18:32:00Z
---

## Current Test

[testing complete]

## Tests

### 1. TIC Collector - Foreign Treasury Holdings
expected: Run TICCollector.collect_major_holders(), returns DataFrame with top foreign Treasury holders (Japan ~1.3T, China ~1T USD)
result: pass
verified: Japan: 1299.9B, China: 1033.8B, UK: 610.7B - correct columns (timestamp, series_id, source, value, unit)

### 2. Fed Custody - Weekly Holdings
expected: Run FedCustodyCollector.collect_all(), returns weekly Fed custody data with ~$3T total holdings (WSEFINTL1, WMTSECL1, WFASECL1 series)
result: skipped
reason: Requires FRED API key (LIQUIDITY_FRED_API_KEY not configured)

### 3. Stress Indicators - SOFR-OIS Spread
expected: Run StressIndicatorCollector.collect_sofr_ois_spread(), returns spread in basis points (typically 0-15 bps in normal conditions)
result: skipped
reason: Requires FRED API key (LIQUIDITY_FRED_API_KEY not configured)

### 4. Stress Indicators - Regime Classification
expected: Run StressIndicatorCollector.get_current_regime(), returns "GREEN", "YELLOW", or "RED" based on current market stress levels
result: pass
verified: Returns 'GREEN' when no data provided (default safe state)

### 5. Risk ETFs - Shares Outstanding
expected: Run RiskETFCollector.collect_current_shares(), returns shares outstanding for SPY, TLT, HYG, IEF, LQD (SPY should have ~900M+ shares)
result: pass
verified: SPY: 917.8M shares, TLT: 109.7M, HYG: 195.6M, IEF: 146M, LQD: 293.5M - all with total_assets and nav_price

### 6. Risk ETFs - Risk Appetite Ratio
expected: Run RiskETFCollector.calculate_risk_appetite(), returns SPY/TLT ratio (~8-10 in neutral conditions) indicating risk-on vs risk-off sentiment
result: issue
reported: "Method requires shares_df parameter - cannot be called without arguments"
severity: minor
root_cause: API design requires user to first call collect_current_shares() then pass result to calculate_risk_appetite()

### 7. COFER - Currency Reserves
expected: Run COFERCollector.collect_reserves_by_currency(), returns IMF reserve data with USD dominant (~56%), EUR (~20%), CNY growing
result: pass
verified: Returns quarterly data from 1999-present with USD reserves ~7T millions_usd in latest period

### 8. COFER - De-dollarization Rate
expected: Run COFERCollector.calculate_dedollarization_rate(), returns YoY change in USD share (tracking gradual de-dollarization trend)
result: pass
verified: Returns YoY changes in percentage_points. Latest: Q1 2025 shows -1.32pp (de-dollarization trend)

### 9. Registry Integration - All Collectors
expected: Run `registry.list_collectors()`, should include: tic, fed_custody, stress, risk_etfs, cofer
result: pass
verified: All 5 Phase 5 collectors registered: tic, fed_custody, stress, risk_etfs, cofer

### 10. Integration Tests Pass
expected: Run integration tests - all tests pass (64+ passed, some skipped for API keys)
result: pass
verified: 64 passed, 23 skipped, 69 warnings in 120.40s

## Summary

total: 10
passed: 7
issues: 1
pending: 0
skipped: 2

## Issues for /gsd:plan-fix

- ~~UAT-001: RiskETFCollector.calculate_risk_appetite() requires shares_df parameter (minor) - Test 6~~
  **FIXED**: Method now auto-fetches SPY/TLT if no DataFrame provided (commit 98ebbf5)
