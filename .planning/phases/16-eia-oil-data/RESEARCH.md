# Research: Phase 16 - EIA Oil Data

**Date:** 2026-02-06
**Confidence:** 92/100
**Status:** Complete

## Summary

EIA API v2 fornisce accesso gratuito ai dati Weekly Petroleum Status Report. Pattern esistente nel codebase (`FREDCollector`) può essere adattato.

## EIA API v2 Specification

| Item | Value |
|------|-------|
| **Base URL** | `https://api.eia.gov/v2/` |
| **Auth** | API key as URL param: `?api_key=XXXXX` |
| **Registration** | https://www.eia.gov/opendata/register.php |
| **Rate Limit** | Throttling attivo, key suspended se eccede |
| **Max rows** | 5,000 per request (JSON) |
| **Format** | JSON (default) o XML |

## Key Petroleum Routes

```
/petroleum/sum/sndw/data          # Weekly Supply Estimates
/petroleum/stoc/wstk/data         # Weekly Stocks
/petroleum/pnp/wiup/data          # Weekly Inputs & Utilization
```

## Series Codes

| Metric | Series ID | Frequency | Unit |
|--------|-----------|-----------|------|
| **Cushing Crude Inventory** | `W_EPC0_SAX_YCUOK_MBBL` | Weekly | Thousand barrels |
| **US Crude Production** | `WCRFPUS2` | Weekly | Thousand b/d |
| **US Crude Imports** | `WCRIMUS2` | Weekly | Thousand b/d |
| **US Refinery Utilization** | `WPULEUS3` | Weekly | Percent |
| **PADD 1 Utilization** | `W_NA_YUP_R10_PER` | Weekly | Percent |
| **PADD 3 Utilization** | `W_NA_YUP_R30_PER` | Weekly | Percent |
| **PADD 5 Utilization** | `W_NA_YUP_R50_PER` | Weekly | Percent |
| **US Crude Stocks Total** | `WCESTUS1` | Weekly | Thousand barrels |

## API Call Example

```bash
curl "https://api.eia.gov/v2/petroleum/stoc/wstk/data?api_key=YOUR_KEY&data[]=value&facets[series][]=W_EPC0_SAX_YCUOK_MBBL&frequency=weekly&sort[0][column]=period&sort[0][direction]=desc&length=52"
```

## Response Structure

```json
{
  "response": {
    "total": 52,
    "dateFormat": "YYYY-MM-DD",
    "frequency": "weekly",
    "data": [
      {
        "period": "2026-01-31",
        "series": "W_EPC0_SAX_YCUOK_MBBL",
        "value": 23456,
        "units": "MBBL"
      }
    ]
  }
}
```

## Python Libraries Available

| Library | Version | Notes |
|---------|---------|-------|
| [myeia](https://github.com/philsv/myeia) | 0.4.x | Active, v2 support |
| [EIAOpenData](https://pypi.org/project/EIAOpenData/) | 0.1.x | Route-based |

**Recommendation:** Use `httpx` directly (already in project) instead of adding dependency.

## Existing Pattern Reference

```python
# From src/liquidity/collectors/fred.py
class FREDCollector(BaseCollector):
    SERIES_MAP = {"fed_total_assets": "WALCL", ...}

    async def collect(self, series_ids, start_date, end_date):
        # Fetch via OpenBB → normalize to DataFrame
        ...
```

## Implementation Plan

1. Create `src/liquidity/collectors/eia.py`
2. Use `httpx.AsyncClient` for async requests
3. Follow `BaseCollector` pattern
4. Output: `timestamp, series_id, source, value, unit`

## Sources

- [EIA Weekly Petroleum Status Report](https://www.eia.gov/petroleum/supply/weekly/)
- [EIA Open Data API](https://www.eia.gov/opendata/)
- [EIA API Browser](https://www.eia.gov/opendata/browser/)
- [Cushing Inventory Data](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=W_EPC0_SAX_YCUOK_MBBL&f=W)
- [myeia GitHub](https://github.com/philsv/myeia)

## Decisions

| Decision | Rationale |
|----------|-----------|
| httpx over myeia | Fewer dependencies, more control |
| Weekly frequency | Matches WPSR release schedule |
| Cushing as priority | WTI delivery point, most liquid indicator |

## Risks

| Risk | Mitigation |
|------|------------|
| API key throttling | Implement rate limiting, cache results |
| Data format changes | Use API v2 (stable), add validation |
| Weekend gaps | Forward-fill like existing collectors |
