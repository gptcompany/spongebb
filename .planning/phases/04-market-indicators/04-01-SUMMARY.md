# Plan 04-01 Summary: Commodity Collector

**Status:** Complete
**Completed:** 2026-01-23

## What Was Built

Created `CommodityCollector` for fetching spot prices of precious metals and energy commodities.

### Files Created/Modified
- `src/liquidity/collectors/commodities.py` - CommodityCollector implementation
- `tests/integration/test_commodities.py` - 17 tests (all passing)

### Features Implemented
1. **Symbol Mapping**
   - Gold (GC=F): $/oz
   - Silver (SI=F): $/oz
   - Copper (HG=F): $/lb
   - WTI Crude (CL=F): $/barrel
   - Brent Crude (BZ=F): $/barrel

2. **Batch Download**
   - Single `yf.download()` call for all symbols (avoids rate limiting)
   - Follows exact FX collector pattern

3. **Derived Metrics**
   - `calculate_brent_wti_spread()` - Returns spread in $/barrel
   - `calculate_copper_gold_ratio()` - Risk-on/risk-off indicator (scaled x1000)

4. **Convenience Methods**
   - `collect_precious_metals()` - Gold, Silver only
   - `collect_energy()` - WTI, Brent only
   - `collect_all()` - All commodities
   - `get_current_gold_price()` - Latest gold price

5. **Data Quality**
   - Forward fill for weekend/holiday gaps
   - Standard output format: timestamp, series_id, source, value, unit

### Verification Results
```
OK: 15 rows (5 commodities × 3 days)
Symbols: ['BZ=F', 'CL=F', 'GC=F', 'HG=F', 'SI=F']
Brent-WTI spread: $4.70/barrel
Cu/Au ratio: 1.1698
```

### Tests
- 17 tests passing
- Symbol mapping tests
- Output format tests
- Derived metric calculation tests (mock + real data)
- Registry integration test

## Design Decisions
- Used futures contracts (=F suffix) for consistent pricing
- Unit map matches commodity unit conventions
- FRED fallback defined but not actively used (Yahoo reliable)
- Forward fill strategy consistent with FX collector
