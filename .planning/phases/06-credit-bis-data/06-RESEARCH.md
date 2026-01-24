# Phase 6: Credit & BIS Data - Research

**Researched:** 2026-01-24
**Domain:** Credit market monitoring and BIS Eurodollar system tracking
**Confidence:** HIGH

<research_summary>
## Summary

Researched data access patterns for credit market indicators (HY OAS, SLOOS, CP rates) and BIS international banking statistics (Eurodollar system). The standard approach uses FRED API for credit data (already in codebase) and BIS bulk CSV downloads for international banking statistics.

Key finding: BIS data is best accessed via bulk CSV downloads rather than SDMX API. The bulk downloads are free, no-auth, and updated quarterly. The SDMX API via `sdmx1` library works but has known quirks per data source. Given we already use similar CSV/HTTP patterns (SNB, DBnomics), bulk CSV is the simpler, more reliable approach.

**Primary recommendation:** Use FRED for all credit data (HY OAS already implemented, add SLOOS and CP rates). Use BIS bulk CSV downloads for LBS/CBS international banking statistics. Calculate FRA-OIS equivalent using SOFR-OIS spread (TED spread discontinued post-LIBOR).

</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.27+ | HTTP client | Already in codebase, async support |
| pandas | 2.2+ | Data manipulation | Already in codebase |
| fredapi | 0.5+ | FRED API access | Alternative to OpenBB for FRED |
| openbb | 4.4+ | Multi-source data | Already in codebase for FRED |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sdmx1 | 2.18+ | SDMX API client | If needing real-time BIS updates (not bulk) |
| zipfile | stdlib | Extract bulk downloads | For BIS CSV processing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| BIS bulk CSV | sdmx1 SDMX API | SDMX more complex, bulk is quarterly anyway |
| FRED direct | DBnomics FRED mirror | DBnomics adds latency, FRED is source |
| OpenBB for FRED | fredapi directly | OpenBB already in codebase, use existing pattern |

**Installation:**
```bash
# No new dependencies needed - already have httpx, pandas, openbb
# Optional for SDMX if needed later:
uv add sdmx1
```

</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
src/liquidity/collectors/
├── credit.py          # CreditCollector: HY OAS, CP rates, credit spreads
├── sloos.py           # SLOOSCollector: Fed lending standards survey
├── bis.py             # BISCollector: LBS, CBS international banking stats
└── ... (existing)
```

### Pattern 1: FRED Series Extension
**What:** Add new FRED series to existing FREDCollector SERIES_MAP
**When to use:** Credit spreads, CP rates, SLOOS data already on FRED
**Example:**
```python
# In fred.py - extend SERIES_MAP
SERIES_MAP: dict[str, str] = {
    # ... existing ...
    # Credit Markets (Phase 6)
    "hy_oas": "BAMLH0A0HYM2",      # High Yield OAS (already exists!)
    "bbb_oas": "BAMLC0A4CBBB",     # BBB OAS
    "cp_fin_aa": "DCPF3M",         # 90-day AA Financial CP
    "cp_nonfin_aa": "DCPN3M",      # 90-day AA Nonfinancial CP
    # SLOOS
    "sloos_ci_large": "DRTSCILM",  # C&I loans to large firms
    "sloos_ci_small": "DRTSCIS",   # C&I loans to small firms
    "sloos_cre": "DRTSROM",        # Commercial Real Estate
}
```

### Pattern 2: Bulk CSV Collector (BIS)
**What:** Download quarterly CSV, cache locally, parse on demand
**When to use:** BIS data (updated quarterly, large files)
**Example:**
```python
# Source: Follows SNB collector pattern
class BISCollector(BaseCollector[pd.DataFrame]):
    """BIS International Banking Statistics via bulk CSV."""

    BIS_BULK_URL = "https://data.bis.org/static/bulk"
    DATASETS = {
        "lbs": "WS_LBS_D_PUB_csv_col.zip",  # Locational Banking
        "cbs": "WS_CBS_PUB_csv_col.zip",     # Consolidated Banking
        "gli": "WS_GLI_csv_col.zip",         # Global Liquidity
    }

    async def _download_and_cache(self, dataset: str) -> Path:
        """Download bulk CSV if not cached or stale."""
        cache_path = self._settings.cache_dir / f"bis_{dataset}.csv"
        # Check if cache is fresh (quarterly data, cache for 7 days)
        if cache_path.exists():
            age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            if age.days < 7:
                return cache_path
        # Download and extract
        ...
```

### Pattern 3: Calculated Spreads
**What:** Calculate spreads from component series
**When to use:** FRA-OIS equivalent (SOFR-OIS), credit spreads over Treasuries
**Example:**
```python
# Calculate SOFR-OIS spread as FRA-OIS replacement
async def calculate_sofr_ois_spread(self) -> pd.DataFrame:
    """SOFR-OIS spread as funding stress indicator (replaces LIBOR-OIS)."""
    sofr = await self.fred_collector.collect_series(["sofr"])
    # OIS rates not directly on FRED - use Fed Funds as proxy
    fed_funds = await self.fred_collector.collect_series(["DFF"])
    # Merge and calculate spread
    merged = sofr.merge(fed_funds, on="timestamp", suffixes=("_sofr", "_ff"))
    merged["sofr_ff_spread"] = merged["value_sofr"] - merged["value_ff"]
    return merged
```

### Anti-Patterns to Avoid
- **Real-time BIS queries:** BIS data is quarterly with 3-month lag; don't poll for updates
- **TED spread calculation:** LIBOR discontinued Jan 2022; use SOFR-based spreads
- **SDMX for simple CSV data:** BIS bulk CSV simpler than SDMX for batch processing

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FRED data fetching | Custom HTTP requests | OpenBB `obb.economy.fred_series()` | Already in codebase, handles auth |
| SDMX parsing | Manual XML/JSON parsing | `sdmx1` library | Complex standard, library handles it |
| CSV compression | Custom zip handling | `zipfile` stdlib | Standard library, battle-tested |
| Date alignment | Manual period matching | pandas `merge_asof()` | Handles quarterly/daily alignment |
| Credit spread indices | Calculate from bonds | FRED ICE BofA indices | Pre-calculated, industry standard |

**Key insight:** Credit market data is well-served by FRED - don't need alternative sources. BIS data is best as bulk CSV (quarterly update cadence matches quarterly data). The SDMX API adds complexity without benefit for our use case.

</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: LIBOR/TED Spread Discontinuation
**What goes wrong:** Code references TEDRATE or LIBOR series that no longer update
**Why it happens:** LIBOR was discontinued January 31, 2022
**How to avoid:** Use SOFR-based spreads as replacement stress indicator
**Warning signs:** FRED series showing "DISCONTINUED" in name

### Pitfall 2: BIS Data Frequency Mismatch
**What goes wrong:** Expecting daily/weekly updates from quarterly BIS data
**Why it happens:** Confusing update frequency with data frequency
**How to avoid:** Document data lag clearly; LBS/CBS are quarterly with 3-month lag
**Warning signs:** Empty results when filtering for recent dates

### Pitfall 3: SLOOS Survey Interpretation
**What goes wrong:** Treating net percentage as absolute level
**Why it happens:** SLOOS measures change in standards, not standard level
**How to avoid:** Positive = tightening, negative = easing, zero = unchanged
**Warning signs:** Expecting values 0-100%, getting -50 to +50%

### Pitfall 4: Credit Spread Units
**What goes wrong:** Mixing basis points and percentage points
**Why it happens:** FRED reports OAS in percent (e.g., 3.5 = 350 bps)
**How to avoid:** Check FRED series metadata; ICE BofA indices are in percent
**Warning signs:** Spreads looking 100x too large or too small

### Pitfall 5: BIS CSV Column Names
**What goes wrong:** Parsing fails on special characters in column names
**Why it happens:** BIS CSV uses verbose multi-level headers
**How to avoid:** Use `header=[0,1]` for multi-level, or skip rows
**Warning signs:** pandas errors on column access

</common_pitfalls>

<code_examples>
## Code Examples

### FRED SLOOS Data Access
```python
# Source: Existing FREDCollector pattern
from openbb import obb

# SLOOS series for C&I loan standards
sloos_data = await asyncio.to_thread(
    lambda: obb.economy.fred_series(
        symbol="DRTSCILM",  # Net % tightening C&I to large firms
        start_date="2020-01-01",
    ).to_df()
)

# Interpretation: Positive = net tightening, Negative = net easing
# Values range roughly -30% to +70% historically
```

### FRED Commercial Paper Rates
```python
# Source: FRED API documentation
# Series: DCPF3M (financial), DCPN3M (nonfinancial)
cp_rates = await asyncio.to_thread(
    lambda: obb.economy.fred_series(
        symbol="DCPF3M,DCPN3M",
        start_date="2020-01-01",
    ).to_df()
)
```

### BIS Bulk CSV Download
```python
# Source: BIS Data Portal bulk download pattern
import httpx
import zipfile
from io import BytesIO

BIS_BULK_URL = "https://data.bis.org/static/bulk"

async def download_bis_lbs() -> pd.DataFrame:
    """Download BIS Locational Banking Statistics."""
    url = f"{BIS_BULK_URL}/WS_LBS_D_PUB_csv_col.zip"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    # Extract CSV from zip
    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        csv_name = [n for n in zf.namelist() if n.endswith('.csv')][0]
        with zf.open(csv_name) as f:
            df = pd.read_csv(f)

    return df
```

### SOFR-OIS Spread (FRA-OIS Replacement)
```python
# Source: Community pattern post-LIBOR transition
# Note: True OIS not on FRED; use Fed Funds effective rate as proxy

async def calculate_funding_stress_spread() -> pd.DataFrame:
    """Calculate SOFR minus Fed Funds as funding stress indicator."""
    # Fetch both series
    sofr = await fred_collector.collect_series(["sofr"])  # SOFR
    ff = await fred_collector.collect_series(["DFF"])     # Fed Funds Effective

    # Align dates and calculate spread
    merged = sofr.merge(ff, on="timestamp", suffixes=("_sofr", "_ff"))
    merged["spread_bps"] = (merged["value_sofr"] - merged["value_ff"]) * 100

    # Spread > 10 bps typically signals funding stress
    return merged[["timestamp", "spread_bps"]]
```

</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LIBOR-OIS spread | SOFR-OIS spread | Jan 2022 | LIBOR discontinued, use SOFR |
| TED spread (TEDRATE) | SOFR-FF spread | Jan 2022 | TED spread discontinued on FRED |
| pandasdmx | sdmx1 | 2023 | sdmx1 is maintained fork |
| BIS SDMX-ML | BIS bulk CSV | Current | Bulk simpler for quarterly batch |

**New tools/patterns to consider:**
- **BIS Data Portal code snippets:** Auto-generates Python code for SDMX queries
- **SOFR term rates:** Futures-implied term SOFR available for forward-looking stress

**Deprecated/outdated:**
- **LIBOR (all tenors):** Discontinued January 31, 2022
- **TEDRATE on FRED:** Marked DISCONTINUED, no updates
- **pandasdmx (original):** Use sdmx1 fork instead

</sota_updates>

<open_questions>
## Open Questions

1. **Corporate Bond Issuance Volume**
   - What we know: SIFMA publishes issuance data, available as Excel downloads
   - What's unclear: No API or FRED series for real-time issuance pace
   - Recommendation: Use credit spread changes as proxy for issuance conditions; skip direct issuance volume

2. **BIS Data Granularity**
   - What we know: LBS has country-level breakdowns, ~200 counterparty countries
   - What's unclear: Optimal filtering for "Eurodollar size" metric Hayes references
   - Recommendation: Start with total USD cross-border claims, refine based on usage

3. **SLOOS Release Lag**
   - What we know: Quarterly survey, results published ~6 weeks after quarter end
   - What's unclear: Best way to handle gap between survey date and publish date
   - Recommendation: Use survey reference quarter, not publication date, as timestamp

</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [FRED BAMLH0A0HYM2](https://fred.stlouisfed.org/series/BAMLH0A0HYM2) - HY OAS index
- [FRED DRTSCILM](https://fred.stlouisfed.org/series/DRTSCILM) - SLOOS C&I tightening
- [FRED DCPF3M/DCPN3M](https://fred.stlouisfed.org/series/DCPF3M) - Commercial paper rates
- [BIS Bulk Downloads](https://data.bis.org/bulkdownload) - LBS/CBS CSV files
- [BIS Stats API](https://stats.bis.org/api-doc/v1/) - SDMX API documentation
- [sdmx1 readthedocs](https://sdmx1.readthedocs.io/en/latest/sources.html) - BIS source docs

### Secondary (MEDIUM confidence)
- [SIFMA Corporate Bond Stats](https://www.sifma.org/research/statistics/us-corporate-bonds-statistics) - Issuance data (Excel only)
- [Fed SLOOS page](https://www.federalreserve.gov/data/sloos.htm) - Survey methodology

### Tertiary (LOW confidence - needs validation)
- SOFR-FF spread as funding stress proxy (community pattern, not official metric)

</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: FRED API, BIS bulk CSV downloads
- Ecosystem: httpx, pandas, existing OpenBB patterns
- Patterns: Extend FRED collector, new BIS bulk collector
- Pitfalls: LIBOR discontinuation, data frequency, SLOOS interpretation

**Confidence breakdown:**
- Credit data (FRED): HIGH - well-documented, existing collector pattern
- SLOOS (FRED): HIGH - straightforward FRED series
- BIS bulk CSV: HIGH - verified URL patterns, simple approach
- BIS SDMX API: MEDIUM - library works but adds complexity
- FRA-OIS replacement: MEDIUM - SOFR-FF is approximation

**Research date:** 2026-01-24
**Valid until:** 2026-02-24 (30 days - data sources stable)

</metadata>

---

*Phase: 06-credit-bis-data*
*Research completed: 2026-01-24*
*Ready for planning: yes*
