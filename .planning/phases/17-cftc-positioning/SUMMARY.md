# Phase 17: CFTC Positioning - Summary

## Completed: 2026-02-06

## Overview

Implemented CFTC Commitment of Traders (COT) positioning analysis for commodity futures. Provides weekly positioning data for WTI, Gold, Copper, Silver, and Natural Gas with percentile ranking and extreme condition detection.

## Plans Completed

### Plan 17-01: CFTC COT Collector ✅
- **File:** `src/liquidity/collectors/cftc_cot.py`
- CFTC Socrata API integration (`72hh-3qpy` endpoint)
- 5 commodities: WTI, GOLD, COPPER, SILVER, NATGAS
- Standard output schema (timestamp, series_id, source, value, unit)
- Safe integer parsing for malformed API responses
- **Tests:** 35 unit tests + 14 integration tests

### Plan 17-02: Positioning Metrics Calculator ✅
- **File:** `src/liquidity/analyzers/positioning.py`
- `PositioningAnalyzer` class with configurable lookback
- Ratio calculations: Commercial/Speculator, Long/Short
- Rolling percentile ranks (52-week default)
- Extreme detection at 10th/90th percentiles
- `PositioningMetrics` dataclass for analysis results
- **Tests:** 39 unit tests

### Plan 17-03: Extreme Positioning Alerts ✅
- **File:** `src/liquidity/alerts/positioning_alerts.py`
- 5 alert types: SPEC_EXTREME_LONG/SHORT, COMM_EXTREME_LONG/SHORT, DIVERGENCE
- Severity levels: warning (90th/10th) and critical (95th/5th)
- Discord webhook integration with embed formatting
- Deduplication (1 week window per commodity/type)
- **Tests:** 34 unit tests

### Plan 17-04: Dashboard Positioning Panel ✅
- **File:** `src/liquidity/dashboard/components/positioning.py`
- Positioning heatmap (commodities x trader type)
- Historical time series with commodity selector
- Current extremes table with severity badges
- Color scale: red (bearish) → gray (neutral) → green (bullish)
- **Tests:** 17 unit tests

## Technical Details

### API Quirks Discovered
1. `cftc_commodity_code` has trailing spaces (use LIKE query)
2. `swap__positions_short_all` has double underscore
3. NATGAS contract is "NAT GAS NYME" not "NATURAL GAS"

### Key Commodities
| Code | Name | Market |
|------|------|--------|
| 067 | WTI Crude Oil | NYME |
| 088 | Gold | CMX |
| 085 | Copper #1 | CMX |
| 084 | Silver | CMX |
| 023 | Natural Gas | NYME |

### Series IDs Generated
- `cot_{commodity}_comm_net` - Commercial net position
- `cot_{commodity}_spec_net` - Speculator net position
- `cot_{commodity}_swap_net` - Swap dealer net position
- `cot_{commodity}_oi` - Open interest
- `cot_{commodity}_comm_pctl` - Commercial percentile (calculated)
- `cot_{commodity}_spec_pctl` - Speculator percentile (calculated)

## Test Summary

| Component | Unit Tests | Integration Tests |
|-----------|------------|-------------------|
| CFTCCOTCollector | 35 | 14 |
| PositioningAnalyzer | 39 | - |
| PositioningAlertEngine | 34 | - |
| Positioning Panel | 17 | - |
| **Total** | **125** | **14** |

## Files Created/Modified

### New Files
- `src/liquidity/collectors/cftc_cot.py`
- `src/liquidity/analyzers/positioning.py`
- `src/liquidity/alerts/positioning_alerts.py`
- `src/liquidity/dashboard/components/positioning.py`
- `tests/unit/collectors/test_cftc_cot.py`
- `tests/unit/test_positioning.py`
- `tests/unit/test_alerts/test_positioning_alerts.py`
- `tests/unit/test_dashboard/test_components/test_positioning.py`
- `tests/integration/collectors/test_cftc_cot_integration.py`

### Modified Files
- `src/liquidity/collectors/__init__.py` - Added CFTC exports
- `src/liquidity/analyzers/__init__.py` - Added positioning exports
- `src/liquidity/alerts/__init__.py` - Added positioning alerts exports
- `src/liquidity/dashboard/components/__init__.py` - Added panel exports

## Usage Examples

```python
# Collect positioning data
from liquidity.collectors import CFTCCOTCollector

collector = CFTCCOTCollector()
df = await collector.collect(commodities=["WTI", "GOLD"], weeks=52)

# Analyze positioning
from liquidity.analyzers import PositioningAnalyzer

analyzer = PositioningAnalyzer(lookback_weeks=52)
metrics = analyzer.analyze_commodity(df, "WTI")
print(f"Spec percentile: {metrics.spec_net_percentile:.1f}%")

# Check for alerts
from liquidity.alerts import PositioningAlertEngine

engine = PositioningAlertEngine(discord_webhook_url=webhook_url)
alerts = engine.check_extremes("WTI", spec_percentile=95.0, comm_percentile=15.0)
await engine.send_alerts(alerts)
```

## Next Steps

- Phase 18: OPEC Meeting Tracker (Wave 3)
- Consider adding 156-week (3-year) lookback as alternative
- Add weekly digest summary for positioning changes
