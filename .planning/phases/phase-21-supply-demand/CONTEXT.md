# Phase 21: Supply-Demand Model - Context

## Goal

Oil balance calculator con inventory forecasts e segnali di regime (tight/loose market).

## Requirements (from ROADMAP)

| ID | Requirement |
|----|-------------|
| MODEL-01 | Supply-demand balance calculator |
| MODEL-02 | Inventory forecast (YoY, seasonal adj) |
| MODEL-03 | Integration with liquidity regime |

## Plans

| Plan | Description | Effort | Wave |
|------|-------------|--------|------|
| 21-01 | Supply-demand balance calculator | M | 1 |
| 21-02 | Inventory forecast (YoY, seasonal adj) | M | 1 |
| 21-03 | Oil regime signals (tight/loose) | M | 2 |
| 21-04 | Integration with liquidity regime classifier | L | 2 |

## Technical Approach

### Plan 21-01: Supply-Demand Balance

**Formula:**
```
Balance = Supply - Demand
Supply = Production + Imports + SPR Releases
Demand = Refinery Inputs + Exports

If Balance > 0: surplus (bearish)
If Balance < 0: deficit (bullish)
```

**Data sources (from EIA collector Phase 16):**
- `WCRFPUS2`: US crude production
- `WCRIMUS2`: US crude imports
- `WCRSTUS1`: US crude stocks
- `WCREXUS2`: US crude exports

### Plan 21-02: Inventory Forecast

**Methods:**
1. YoY comparison: Current vs same week last year
2. Seasonal adjustment: 5-year average for week
3. Days of supply: Inventory / Daily demand

**Output:**
- `inventory_yoy_change`: +/- million barrels vs last year
- `inventory_vs_5yr_avg`: +/- % vs 5-year average
- `days_of_supply`: Current days of demand coverage

### Plan 21-03: Oil Regime Signals

**Regime classification:**
- **TIGHT**: Inventory below 5yr avg, production declining, high utilization
- **BALANCED**: Inventory near 5yr avg, stable production
- **LOOSE**: Inventory above 5yr avg, production rising, low utilization

**Signal strength:** 0-100 based on multiple indicators

### Plan 21-04: Liquidity Integration

Combinare oil regime con liquidity regime per segnali macro:
- EXPANSIVE liquidity + TIGHT oil = Bullish commodities
- CONTRACTIVE liquidity + LOOSE oil = Bearish commodities

## Dependencies

- **Phase 16**: EIA collector (inventory, production data)
- **Phase 8**: Regime classifier (liquidity regime)

## Files to Create/Modify

| Action | File |
|--------|------|
| CREATE | `src/liquidity/oil/supply_demand.py` |
| CREATE | `src/liquidity/oil/inventory_forecast.py` |
| CREATE | `src/liquidity/oil/regime.py` |
| CREATE | `src/liquidity/oil/__init__.py` |
| MODIFY | `src/liquidity/analyzers/regime_classifier.py` (integrate oil) |
| CREATE | `tests/unit/oil/test_supply_demand.py` |
| CREATE | `tests/unit/oil/test_inventory_forecast.py` |
| CREATE | `tests/unit/oil/test_regime.py` |

## Validation Criteria

- [ ] Balance calculation matches EIA reports
- [ ] Inventory forecast accuracy vs actual (backtest)
- [ ] Regime signals coerenti con market conditions
- [ ] Integration con liquidity regime funziona
