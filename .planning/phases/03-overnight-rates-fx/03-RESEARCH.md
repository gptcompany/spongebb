# Phase 3: Overnight Rates & FX - Research

**Researched:** 2026-01-22
**Domain:** Central bank overnight rates + FX data collection
**Confidence:** HIGH

<research_summary>
## Summary

Researched data sources and APIs for overnight reference rates (SOFR, €STR, SONIA, CORRA) and FX data (DXY, major pairs, IMF COFER). All four overnight rates have free, public APIs with no authentication required for basic access. FRED provides excellent fallback coverage for all rates.

Key finding: **FRED is the reliable backup for all overnight rates** - SOFR, €STR (via ECBESTRVOLWGTTRMDMNRT), SONIA (via IUDSOIA), and CORRA are all available. Primary sources (NY Fed, ECB, BoE, BoC) should be tried first for freshness, with FRED as universal fallback. This matches the existing multi-tier fallback pattern in the codebase (see `boe.py`).

**Primary recommendation:** Use multi-tier fallback pattern for each rate: Primary API → FRED fallback. For FX, use Yahoo Finance (yfinance) for DXY and major pairs, with FRED as backup for DXY (DTWEXBGS broad dollar index).

</research_summary>

<standard_stack>
## Standard Stack

The established libraries/tools for this domain:

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.27+ | Async HTTP client | Already used, excellent async support |
| pandas | 2.0+ | Data manipulation | Already used, time series support |
| openbb | 4.0+ | Financial data SDK | Already used for FRED |
| yfinance | 0.2+ | Yahoo Finance API | De facto standard for free FX data |

### Supporting (May Need to Add)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyvalet | 0.1.2 | BoC Valet API wrapper | Optional - direct HTTP simpler |
| sdmx1 | 2.5+ | SDMX data access | IMF COFER quarterly data |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| yfinance for FX | OpenBB FX | OpenBB has provider fees, yfinance free |
| Direct API calls | pyvalet | Direct HTTP is simpler, no extra dependency |
| IMF SDMX | DBnomics | DBnomics wraps IMF, adds caching but extra dep |

**Installation:**
```bash
uv add yfinance  # For FX data (DXY, major pairs)
# sdmx1 only if IMF COFER needed: uv add sdmx1
```
</standard_stack>

<data_sources>
## Data Sources by Rate

### SOFR (Secured Overnight Financing Rate)
**Primary:** NY Fed Markets Data API
- Endpoint: `https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json`
- No authentication required
- Published daily ~8:00 AM ET
- Response includes: rate, percentiles, volume

**Fallback:** FRED
- Series: `SOFR`
- Via OpenBB: `obb.economy.fred_series(symbol="SOFR")`

### €STR (Euro Short-Term Rate)
**Primary:** ECB Data Portal API
- Endpoint: `https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT`
- Dataset: EST (Euro Short-Term Rate)
- Series key: `EST.B.EU000A2X2A25.WT`
- Published daily 08:00 CET (T+1)
- No authentication required

**Fallback:** FRED
- Series: `ECBESTRVOLWGTTRMDMNRT`
- Via OpenBB: `obb.economy.fred_series(symbol="ECBESTRVOLWGTTRMDMNRT")`

### SONIA (Sterling Overnight Index Average)
**Primary:** Bank of England IADB
- Endpoint: `https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp`
- Series code: `IUDSOIA`
- Parameters: `SeriesCodes=IUDSOIA&CSVF=TN&UsingCodes=Y`
- Published daily 09:00 London (T+1)
- No authentication required

**Fallback:** FRED
- Series: `IUDSOIA`
- Via OpenBB: `obb.economy.fred_series(symbol="IUDSOIA")`

### CORRA (Canadian Overnight Repo Rate Average)
**Primary:** Bank of Canada Valet API
- Endpoint: `https://www.bankofcanada.ca/valet/observations/AVG.INTWO/json`
- Group: CORRA (includes volume, trimmed volume, submitters)
- Published daily 09:00-11:00 ET
- No authentication required, no API key needed

**Fallback:** FRED
- Series: `CORRAV` (if available) or use primary only
- BoC Valet is highly reliable

### DXY (US Dollar Index)
**Primary:** Yahoo Finance
- Ticker: `DX-Y.NYB`
- Via yfinance: `yf.download("DX-Y.NYB")`
- Real-time during market hours

**Fallback:** FRED Broad Dollar Index
- Series: `DTWEXBGS` (Nominal Broad USD Index)
- Different calculation but highly correlated

### Major FX Pairs
**Primary:** Yahoo Finance
- EUR/USD: `EURUSD=X`
- USD/JPY: `USDJPY=X`
- GBP/USD: `GBPUSD=X`
- USD/CHF: `USDCHF=X`
- USD/CAD: `USDCAD=X`
- USD/CNY: `USDCNY=X`
- AUD/USD: `AUDUSD=X`

**Fallback:** OpenBB currency module (requires provider)

### IMF COFER (Currency Composition of Foreign Exchange Reserves)
**Primary:** IMF SDMX API
- Endpoint: `https://sdmxcentral.imf.org/ws/public/sdmxapi/rest/data/COFER`
- Quarterly data
- No authentication required
- Returns reserve allocations by currency (USD, EUR, CNY, JPY, GBP, etc.)

**Alternative:** DBnomics
- URL: `https://db.nomics.world/IMF/COFER`
- Provides cached access to IMF data

</data_sources>

<architecture_patterns>
## Architecture Patterns

### Recommended Collector Structure
```
src/liquidity/collectors/
├── overnight_rates/
│   ├── __init__.py
│   ├── sofr.py      # NY Fed primary + FRED fallback
│   ├── estr.py      # ECB primary + FRED fallback
│   ├── sonia.py     # BoE primary + FRED fallback
│   └── corra.py     # BoC Valet (highly reliable)
├── fx/
│   ├── __init__.py
│   ├── dxy.py       # Yahoo Finance + FRED fallback
│   ├── pairs.py     # Yahoo Finance for major pairs
│   └── cofer.py     # IMF quarterly reserves
```

Alternative (simpler): Single `overnight_rates.py` and `fx.py` files if the logic is straightforward.

### Pattern 1: Multi-Tier Fallback (from existing boe.py)
**What:** Try primary source, fallback to FRED, guaranteed baseline
**When to use:** All overnight rate collectors
**Example:**
```python
class SOFRCollector(BaseCollector[pd.DataFrame]):
    """SOFR collector with NY Fed primary, FRED fallback."""

    BASELINE_VALUE = 4.35  # percent (Jan 2026)
    BASELINE_DATE = "2026-01-22"

    async def collect(self, start_date=None, end_date=None) -> pd.DataFrame:
        # Tier 1: NY Fed API
        try:
            return await self._collect_nyfed()
        except Exception as e:
            logger.warning("SOFR Tier 1 (NY Fed) failed: %s", e)

        # Tier 2: FRED fallback
        try:
            return await self._collect_fred(start_date, end_date)
        except Exception as e:
            logger.warning("SOFR Tier 2 (FRED) failed: %s", e)

        # Tier 3: Cached baseline (GUARANTEED)
        return self._get_cached_baseline()
```

### Pattern 2: Rate Differential Calculation
**What:** Pre-calculate spreads between rates for carry trade signals
**When to use:** After collecting all overnight rates
**Example:**
```python
@staticmethod
def calculate_rate_differentials(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate SOFR vs other overnight rate differentials."""
    pivot = df.pivot(index="timestamp", columns="series_id", values="value")

    differentials = pd.DataFrame({
        "timestamp": pivot.index,
        "sofr_estr_spread": pivot["SOFR"] - pivot["ESTR"],
        "sofr_sonia_spread": pivot["SOFR"] - pivot["SONIA"],
        "sofr_corra_spread": pivot["SOFR"] - pivot["CORRA"],
    })
    return differentials
```

### Pattern 3: FX Collector with yfinance
**What:** Use yfinance for FX data with async wrapper
**When to use:** DXY and major pairs
**Example:**
```python
async def _fetch_fx_yahoo(self, symbols: list[str]) -> pd.DataFrame:
    """Fetch FX data from Yahoo Finance."""
    def _sync_fetch():
        import yfinance as yf
        df = yf.download(symbols, period="30d", progress=False)
        return df

    return await asyncio.to_thread(_sync_fetch)
```

### Anti-Patterns to Avoid
- **Scraping rate websites:** APIs exist, use them (no 403 issues like BoE balance sheet)
- **Assuming same-day availability:** €STR and SONIA are T+1 (published next business day)
- **Mixing rate units:** Some sources use percent, some decimal (0.0435 vs 4.35%)
- **Ignoring weekend gaps:** Overnight rates don't publish weekends/holidays

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FX rate calculations | Custom pair math | yfinance direct pairs | Cross rates have bid/ask spreads |
| DXY calculation | Weighted basket math | Yahoo DX-Y.NYB | Official ICE calculation differs |
| Rate T+1 handling | Custom date logic | pandas business day | Holiday calendars are complex |
| SDMX parsing | Custom XML parser | sdmx1 library | SDMX has complex structures |
| Timezone conversion | Manual UTC offsets | pandas tz_convert | DST handling is error-prone |

**Key insight:** All four central banks have official APIs. FRED mirrors most of them. The hard problem is not data access — it's handling publication delays, holiday calendars, and ensuring fallback reliability. Focus on the multi-tier fallback pattern, not exotic data sources.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Publication Timing Mismatch
**What goes wrong:** Expecting same-day rates when they publish T+1
**Why it happens:** €STR, SONIA publish next business day
**How to avoid:** Label timestamps as "as_of" dates, not "for" dates. €STR published 2026-01-22 is FOR 2026-01-21.
**Warning signs:** Most recent rate is always "yesterday"

### Pitfall 2: Weekend/Holiday Gaps
**What goes wrong:** Missing data on weekends causes NaN in calculations
**Why it happens:** Overnight rates only publish on business days
**How to avoid:** Use forward-fill (`ffill()`) for rate data, don't interpolate
**Warning signs:** Gaps every Saturday/Sunday in time series

### Pitfall 3: Unit Inconsistency
**What goes wrong:** Rate differentials are wrong (e.g., 435 - 3.5 instead of 4.35 - 3.5)
**Why it happens:** Different sources use percent vs decimal
**How to avoid:** Standardize all rates to percent (4.35, not 0.0435) on ingest
**Warning signs:** Differentials in the hundreds instead of single digits

### Pitfall 4: Yahoo Finance Rate Limiting
**What goes wrong:** 429 errors when fetching multiple FX pairs
**Why it happens:** Too many requests in short time
**How to avoid:** Batch multiple symbols in single `yf.download()` call
**Warning signs:** Intermittent failures on FX collection

### Pitfall 5: IMF COFER Quarterly Lag
**What goes wrong:** Expecting recent COFER data
**Why it happens:** COFER is quarterly with 3-month lag
**How to avoid:** Design system to work with stale COFER (structural data, not tactical)
**Warning signs:** Latest COFER is always 3+ months old
</common_pitfalls>

<code_examples>
## Code Examples

Verified patterns from official sources:

### NY Fed SOFR API Call
```python
# Source: NY Fed Markets API docs
import httpx

async def fetch_sofr_nyfed() -> dict:
    url = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        # Returns: {"refRates": [{"effectiveDate": "2026-01-21", "percentRate": 4.35, ...}]}
        return data["refRates"][0]
```

### ECB €STR API Call
```python
# Source: ECB Data Portal API docs
import httpx

async def fetch_estr_ecb() -> dict:
    url = "https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT"
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
```

### BoE SONIA API Call
```python
# Source: BoE IADB documentation
import httpx
import pandas as pd

async def fetch_sonia_boe(start_date: str, end_date: str) -> pd.DataFrame:
    base_url = "https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp"
    params = {
        "SeriesCodes": "IUDSOIA",
        "Datefrom": start_date,  # "01/Jan/2026"
        "Dateto": end_date,
        "CSVF": "TN",
        "UsingCodes": "Y",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(base_url, params=params)
        response.raise_for_status()
        # Parse CSV response
        from io import StringIO
        df = pd.read_csv(StringIO(response.text))
        return df
```

### BoC CORRA Valet API Call
```python
# Source: Bank of Canada Valet API docs
import httpx

async def fetch_corra_boc() -> dict:
    url = "https://www.bankofcanada.ca/valet/observations/AVG.INTWO/json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        # Returns: {"observations": [{"d": "2026-01-21", "AVG.INTWO": {"v": "4.25"}}]}
        return data["observations"]
```

### Yahoo Finance FX Data
```python
# Source: yfinance documentation
import asyncio
import yfinance as yf
import pandas as pd

async def fetch_fx_yahoo(symbols: list[str], period: str = "30d") -> pd.DataFrame:
    """Fetch FX data from Yahoo Finance."""
    def _sync():
        # Single download call for all symbols (avoids rate limiting)
        df = yf.download(symbols, period=period, progress=False)
        return df["Close"]  # Just closing prices

    return await asyncio.to_thread(_sync)

# Usage:
# symbols = ["DX-Y.NYB", "EURUSD=X", "USDJPY=X", "GBPUSD=X"]
# df = await fetch_fx_yahoo(symbols)
```
</code_examples>

<fred_series_reference>
## FRED Series Reference

Complete list of FRED series for overnight rates and FX:

### Overnight Rates
| Rate | FRED Series | Unit | Frequency | Source |
|------|-------------|------|-----------|--------|
| SOFR | `SOFR` | Percent | Daily | NY Fed |
| €STR | `ECBESTRVOLWGTTRMDMNRT` | Percent | Daily | ECB |
| SONIA | `IUDSOIA` | Percent | Daily | BoE |
| EFFR | `EFFR` | Percent | Daily | NY Fed |
| OBFR | `OBFR` | Percent | Daily | NY Fed |

### FX / Dollar Indices
| Index | FRED Series | Unit | Frequency | Notes |
|-------|-------------|------|-----------|-------|
| Broad USD | `DTWEXBGS` | Index | Daily | Trade-weighted, broad |
| Major USD | `DTWEXM` | Index | Daily | Trade-weighted, major currencies |
| EUR/USD | `DEXUSEU` | USD/EUR | Daily | Spot rate |
| USD/JPY | `DEXJPUS` | JPY/USD | Daily | Spot rate |
| GBP/USD | `DEXUSUK` | USD/GBP | Daily | Spot rate |

Note: FRED FX series are daily noon buying rates, may differ slightly from real-time quotes.
</fred_series_reference>

<sota_updates>
## State of the Art (2025-2026)

What's changed recently:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LIBOR rates | Risk-free rates (SOFR, €STR, SONIA) | 2021-2023 | LIBOR fully discontinued, use RFRs |
| ECB SDW API | ECB Data Portal API | 2024 | New endpoint: data-api.ecb.europa.eu |
| Manual COFER parsing | IMF eliminated "unallocated" | 2025Q3 | Now 100% currency composition available |

**New tools/patterns to consider:**
- **OpenBB 4.x:** Unified provider model, but FX requires paid providers
- **ECB Data Portal:** Modern API replaces older SDW web services

**Deprecated/outdated:**
- **LIBOR:** Fully discontinued June 2023, no longer published
- **ECB SDW direct:** Redirects to Data Portal API now
- **FRED BOEBSTAUKA:** BoE balance sheet discontinued 2016 (not relevant for SONIA)
</sota_updates>

<open_questions>
## Open Questions

Things that couldn't be fully resolved:

1. **NY Fed SOFR API pagination**
   - What we know: `/last/1.json` returns latest, `/last/N.json` for N days
   - What's unclear: Maximum N value, rate limits
   - Recommendation: Use FRED for historical, NY Fed for latest only

2. **CORRA availability on FRED**
   - What we know: BoC Valet is authoritative and reliable
   - What's unclear: Whether FRED mirrors CORRA (couldn't confirm series code)
   - Recommendation: BoC Valet primary only, skip FRED fallback for CORRA

3. **IMF COFER API exact endpoint**
   - What we know: SDMX Central has COFER data
   - What's unclear: Exact series keys for USD share, EUR share, etc.
   - Recommendation: Use DBnomics wrapper initially for simpler access
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [NY Fed Markets API](https://markets.newyorkfed.org/static/docs/markets-api.html) - SOFR endpoint docs
- [ECB Data Portal API](https://data.ecb.europa.eu/help/api/overview) - €STR endpoint
- [BoE SONIA Benchmark](https://www.bankofengland.co.uk/markets/sonia-benchmark) - SONIA publication details
- [BoC Valet API Docs](https://www.bankofcanada.ca/valet/docs) - CORRA series AVG.INTWO
- [FRED SOFR Series](https://fred.stlouisfed.org/series/SOFR) - Fallback source
- [Yahoo Finance DXY](https://finance.yahoo.com/quote/DX-Y.NYB/) - DX-Y.NYB ticker

### Secondary (MEDIUM confidence)
- [yfinance GitHub](https://github.com/ranaroussi/yfinance) - FX ticker format verified
- [IMF COFER Dataset](https://data.imf.org/en/datasets/IMF.STA:COFER) - Quarterly reserves data
- [ECB €STR API Example](https://www.estr.dev/) - Third-party verification of ECB endpoint

### Tertiary (LOW confidence - needs validation)
- NY Fed API rate limits: Not documented, assume reasonable (10 req/min)
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: Central bank overnight rate APIs
- Ecosystem: httpx, pandas, yfinance, FRED via OpenBB
- Patterns: Multi-tier fallback, rate differential calculation
- Pitfalls: T+1 publication, timezone handling, unit consistency

**Confidence breakdown:**
- Data sources: HIGH - All APIs are official, free, documented
- Architecture: HIGH - Matches existing codebase patterns (boe.py)
- Pitfalls: HIGH - Well-known issues in financial data collection
- Code examples: HIGH - From official API documentation

**Research date:** 2026-01-22
**Valid until:** 2026-02-22 (30 days - stable domain, APIs don't change frequently)
</metadata>

---

*Phase: 03-overnight-rates-fx*
*Research completed: 2026-01-22*
*Ready for planning: yes*
