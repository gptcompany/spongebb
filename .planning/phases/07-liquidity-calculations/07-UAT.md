---
status: testing
phase: 07-liquidity-calculations
source: 07-SUMMARY.md
started: 2026-01-24T12:00:00Z
updated: 2026-01-24T12:00:00Z
---

## Current Test

number: 1
name: Net Liquidity Import
expected: |
  `from liquidity.calculators import NetLiquidityCalculator, NetLiquidityResult, Sentiment`
  Import should succeed without errors.
awaiting: user response

## Tests

### 1. Net Liquidity Import
expected: Import NetLiquidityCalculator, NetLiquidityResult, Sentiment without errors
result: [pending]

### 2. Net Liquidity Calculation
expected: `NetLiquidityCalculator().calculate()` returns DataFrame with net_liquidity, walcl, tga, rrp columns
result: [pending]

### 3. Net Liquidity Current
expected: `NetLiquidityCalculator().get_current()` returns NetLiquidityResult with timestamp, net_liquidity, sentiment
result: [pending]

### 4. Global Liquidity Import
expected: Import GlobalLiquidityCalculator, GlobalLiquidityResult without errors
result: [pending]

### 5. Global Liquidity Calculation
expected: `GlobalLiquidityCalculator().calculate()` returns DataFrame with fed_usd, ecb_usd, boj_usd, pboc_usd, global_liquidity columns
result: [pending]

### 6. Stealth QE Import
expected: Import StealthQECalculator, StealthQEResult, StealthQEStatus without errors
result: [pending]

### 7. Stealth QE Daily Score
expected: `StealthQECalculator().calculate_daily()` returns DataFrame with score_daily, rrp_velocity, tga_spending columns
result: [pending]

### 8. Stealth QE Weekly Score
expected: `StealthQECalculator().calculate_weekly()` returns DataFrame with score_weekly (Wednesday values only)
result: [pending]

### 9. Validation Import
expected: Import LiquidityValidator, ValidationResult, CheckResult without errors
result: [pending]

### 10. Net Liquidity Validation
expected: `LiquidityValidator().validate_net_liquidity(8000, 800, 500, 6700)` returns CheckResult with passed=True
result: [pending]

### 11. Coverage Validation
expected: `LiquidityValidator().validate_coverage(30000)` returns CheckResult with passed=True (85.7% > 85%)
result: [pending]

### 12. Unit Tests Pass
expected: `uv run pytest tests/unit/ -v` shows 217 passed, 0 failed
result: [pending]

## Summary

total: 12
passed: 0
issues: 0
pending: 12
skipped: 0

## Issues for /gsd:plan-fix

[none yet]
