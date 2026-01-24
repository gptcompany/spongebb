# Plan 06-02: BIS Collector - Summary

**Completed:** 2026-01-24

## Implemented

### BISCollector (src/liquidity/collectors/bis.py)
- Bulk CSV download from BIS (LBS/CBS datasets)
- 7-day cache for quarterly data  
- Filter by: FREQ=Q, L_MEASURE=S, L_POSITION=C, L_CURR_TYPE=USD
- Calculates offshore USD (excludes US positions)
- Methods: collect_lbs_usd_claims(), get_eurodollar_total()

### Config (src/liquidity/config.py)
- Added cache_dir property

### Tests (tests/unit/test_bis.py)
- 32 unit tests (caching, parsing, filtering, error handling)

## Files Changed
- Created: src/liquidity/collectors/bis.py
- Created: tests/unit/test_bis.py
- Modified: src/liquidity/config.py, src/liquidity/collectors/__init__.py

## Verification
- Import: PASS
- ruff: PASS
- pytest: NOT RUN (disk full)
