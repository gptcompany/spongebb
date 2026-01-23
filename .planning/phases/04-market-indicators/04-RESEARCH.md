# Phase 4: Market Indicators - Research

**Researched:** 2026-01-23
**Domain:** Commodity spot prices and ETF flow data collection
**Confidence:** HIGH

<research_summary>
## Summary

Researched data sources for commodities (gold, silver, copper, oil) and ETF flows. The standard approach uses a mix of FRED (for official prices) and yfinance (for futures/ETFs), following existing collector patterns.

Key finding: Spot prices available via both FRED (LBMA fix) and yfinance (futures). ETF shares outstanding available via `yf.Ticker().info['sharesOutstanding']`. The existing FX collector pattern (yfinance batch download with ffill) works perfectly for commodities.

**Primary recommendation:** Use yfinance for all commodities (consistent API, real-time, free) with FRED as fallback for gold/silver. ETF flows via yfinance `.info` property.

</research_summary>

<standard_stack>
## Standard Stack

### Core Data Sources

| Source | Data Type | Series/Ticker | Notes |
|--------|-----------|---------------|-------|
| yfinance | Gold futures | GC=F | Continuous contract, daily |
| yfinance | Silver futures | SI=F | Continuous contract, daily |
| yfinance | Copper futures | HG=F | Continuous contract, daily |
| yfinance | WTI Crude | CL=F | Continuous contract, daily |
| yfinance | Brent Crude | BZ=F | Continuous contract, daily |
| FRED | Gold (LBMA) | GOLDPMGBD228NLBM | London PM fix, daily |
| FRED | Silver (LBMA) | SLVPRUSD | London fix, daily |
| FRED | Copper | PCOPPUSDM | Global price, monthly |
| FRED | WTI | DCOILWTICO | Daily, EIA |
| FRED | Brent | DCOILBRENTEU | Daily, EIA |

### ETF Tickers

| ETF | Underlying | Ticker | Use |
|-----|------------|--------|-----|
| GLD | Gold | GLD | Shares outstanding, price |
| SLV | Silver | SLV | Shares outstanding, price |
| CPER | Copper | CPER | Shares outstanding, price |
| USO | Oil (WTI) | USO | Shares outstanding, price |
| DBA | Agriculture | DBA | Shares outstanding, price |

### Libraries (already in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yfinance | latest | Commodity futures, ETF data | Same as FX collector |
| openbb | latest | FRED API access | Already used for FRED collector |
| pandas | latest | Data manipulation | Already used everywhere |

**No new dependencies required.**

</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended: Extend Existing Patterns

The FX collector (`fx.py`) provides the exact pattern needed:
- Single `yf.download()` call for all symbols (avoids rate limiting)
- Forward fill for weekend/holiday gaps
- Long-format DataFrame output
- FRED fallback for reliability

### Project Structure (existing)

```
src/liquidity/collectors/
├── commodities.py      # NEW: Gold, silver, copper, oil
├── etf_flows.py        # NEW: ETF shares outstanding tracking
├── fx.py               # REFERENCE: Pattern to follow
├── fred.py             # REFERENCE: FRED fallback pattern
└── ...
```

### Pattern 1: Commodity Collector (following FX pattern)

**What:** Single collector for all commodity spot prices
**When to use:** All commodity price collection
**Example:**
```python
# Following fx.py pattern exactly
COMMODITY_SYMBOLS: dict[str, str] = {
    "gold": "GC=F",
    "silver": "SI=F",
    "copper": "HG=F",
    "wti": "CL=F",
    "brent": "BZ=F",
}

async def collect(self, symbols: list[str] | None = None, ...) -> pd.DataFrame:
    # Single yf.download() call for all symbols
    df = yf.download(symbols, start=..., end=..., progress=False, auto_adjust=True)
    # Normalize to long format
    # Forward fill gaps
    return df_long
```

### Pattern 2: ETF Flow Tracker

**What:** Track shares outstanding changes for ETF flows
**When to use:** Daily ETF flow monitoring
**Example:**
```python
async def collect_etf_flows(self, etfs: list[str] = None) -> pd.DataFrame:
    """Collect ETF shares outstanding and calculate daily changes."""
    results = []
    for etf in etfs:
        ticker = yf.Ticker(etf)
        info = ticker.info
        shares = info.get('sharesOutstanding')
        results.append({
            'timestamp': datetime.now(UTC),
            'etf': etf,
            'shares_outstanding': shares,
            'source': 'yahoo',
        })
    return pd.DataFrame(results)
```

### Pattern 3: Derived Metrics (Spreads/Ratios)

**What:** Pre-calculate spreads and ratios from collected data
**When to use:** Brent-WTI spread, Copper/Gold ratio
**Example:**
```python
@staticmethod
def calculate_brent_wti_spread(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Brent-WTI spread from commodity data."""
    pivot = df.pivot(index="timestamp", columns="series_id", values="value")
    spread = pivot["BZ=F"] - pivot["CL=F"]
    return pd.DataFrame({
        "timestamp": spread.index,
        "brent_wti_spread": spread.values,
        "unit": "usd_per_barrel",
    })

@staticmethod
def calculate_copper_gold_ratio(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Copper/Gold ratio (risk indicator)."""
    pivot = df.pivot(index="timestamp", columns="series_id", values="value")
    # Copper in $/lb, Gold in $/oz - ratio is dimensionless
    ratio = pivot["HG=F"] / pivot["GC=F"] * 1000  # Scale for readability
    return pd.DataFrame({
        "timestamp": ratio.index,
        "copper_gold_ratio": ratio.values,
        "unit": "ratio",
    })
```

### Anti-Patterns to Avoid

- **Individual API calls per symbol:** Use single batch download (rate limiting)
- **Custom datetime parsing:** Use pandas `to_datetime` with existing patterns
- **New dependencies:** yfinance and FRED via OpenBB already available
- **Different output format:** Match existing collectors (timestamp, series_id, source, value, unit)

</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Commodity API | Custom API client | yfinance (already used in FX) | Handles rate limits, parsing |
| Weekend gaps | Custom gap detection | pandas ffill (already in FX) | Proven pattern |
| FRED access | Direct HTTP | OpenBB FRED (already used) | Auth, retries, parsing |
| Data normalization | Custom DataFrame logic | Existing collector base class | Consistency |
| Circuit breaker | Custom retry logic | BaseCollector.fetch_with_retry | Already implemented |

**Key insight:** Phase 3 FX collector solves all these problems. Copy the pattern exactly.

</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: yfinance Rate Limiting
**What goes wrong:** Individual ticker downloads get rate limited
**Why it happens:** Yahoo Finance throttles rapid sequential requests
**How to avoid:** Use single `yf.download()` call with list of symbols (already in FX pattern)
**Warning signs:** HTTP 429 errors, empty DataFrames

### Pitfall 2: Futures Contract Rollover
**What goes wrong:** Price jumps at contract expiry
**Why it happens:** Continuous contracts (GC=F) roll to next month
**How to avoid:** Accept this limitation for daily monitoring (not backtesting). For historical analysis, use FRED spot prices instead.
**Warning signs:** Sudden price gaps not matching market news

### Pitfall 3: ETF Shares Outstanding Staleness
**What goes wrong:** `.info['sharesOutstanding']` may be stale
**Why it happens:** Yahoo Finance caches ETF info, not always real-time
**How to avoid:** Accept daily granularity (sufficient for flow analysis). Cross-check with price * shares vs reported AUM.
**Warning signs:** Shares unchanged for >1 week

### Pitfall 4: FRED Monthly vs Daily
**What goes wrong:** Mixing FRED monthly data (copper) with daily data
**Why it happens:** PCOPPUSDM is monthly only
**How to avoid:** Use yfinance HG=F for daily copper, FRED as fallback/validation only
**Warning signs:** Date alignment issues, gaps in joined data

### Pitfall 5: Unit Mismatches
**What goes wrong:** Comparing prices in different units
**Why it happens:** Gold $/oz, Copper $/lb, Oil $/barrel
**How to avoid:** Store raw units, convert only for ratio calculations
**Warning signs:** Ratios with nonsensical values

</common_pitfalls>

<code_examples>
## Code Examples

### Commodity Collector (following FX pattern)

```python
# Source: Adapted from fx.py (existing codebase)
COMMODITY_SYMBOLS: dict[str, str] = {
    "gold": "GC=F",      # Gold futures ($/oz)
    "silver": "SI=F",    # Silver futures ($/oz)
    "copper": "HG=F",    # Copper futures ($/lb)
    "wti": "CL=F",       # WTI Crude ($/barrel)
    "brent": "BZ=F",     # Brent Crude ($/barrel)
}

def _fetch_sync(self, symbols: list[str], ...) -> pd.DataFrame:
    """Fetch commodity data using yfinance batch download."""
    df = yf.download(
        symbols,
        start=calc_start.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )

    # Handle MultiIndex columns for multiple symbols
    if isinstance(df.columns, pd.MultiIndex):
        df = df["Close"].copy()

    # Melt to long format
    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df_long = df.melt(
        id_vars=[date_col],
        var_name="series_id",
        value_name="value",
    )

    # Forward fill weekend/holiday gaps
    df_long = df_long.sort_values(["series_id", "timestamp"])
    df_long["value"] = df_long.groupby("series_id")["value"].ffill()

    return df_long
```

### ETF Shares Outstanding

```python
# Source: yfinance docs + community patterns
async def collect_etf_shares(self, etfs: list[str] = None) -> pd.DataFrame:
    """Collect ETF shares outstanding for flow tracking."""
    if etfs is None:
        etfs = ["GLD", "SLV", "USO", "CPER", "DBA"]

    def _fetch() -> pd.DataFrame:
        results = []
        for etf in etfs:
            ticker = yf.Ticker(etf)
            info = ticker.info
            results.append({
                "timestamp": datetime.now(timezone.utc),
                "etf": etf,
                "shares_outstanding": info.get("sharesOutstanding"),
                "total_assets": info.get("totalAssets"),
                "nav_price": info.get("navPrice"),
                "source": "yahoo",
            })
        return pd.DataFrame(results)

    return await asyncio.to_thread(_fetch)
```

### FRED Fallback for Gold

```python
# Source: Adapted from fred.py (existing codebase)
FRED_COMMODITY_SERIES: dict[str, str] = {
    "gold": "GOLDPMGBD228NLBM",   # LBMA PM fix, daily
    "silver": "SLVPRUSD",          # London fix, daily (if available)
    "wti": "DCOILWTICO",           # EIA daily
    "brent": "DCOILBRENTEU",       # EIA daily
    "copper": "PCOPPUSDM",         # IMF monthly only
}

async def _collect_gold_fred_fallback(self) -> pd.DataFrame:
    """FRED fallback for gold price (LBMA fix)."""
    result = obb.economy.fred_series(
        symbol="GOLDPMGBD228NLBM",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        provider="fred",
    )
    # Normalize to standard format...
```

</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pandas-datareader | yfinance | 2020+ | pandas-datareader deprecated for Yahoo |
| Individual ticker downloads | Batch yf.download() | 2022+ | Avoids rate limiting |
| Manual ETF AUM tracking | yf.Ticker().info | 2023+ | Direct shares outstanding access |

**New tools/patterns to consider:**
- **OpenBB commodity endpoints:** Could use `obb.equity.price.historical()` but yfinance is simpler for futures
- **FRED via OpenBB:** Already using, no change needed

**Deprecated/outdated:**
- **pandas-datareader Yahoo module:** Use yfinance instead
- **Yahoo Finance v7 API:** yfinance handles this internally

</sota_updates>

<open_questions>
## Open Questions

1. **ETF sharesOutstanding reliability**
   - What we know: yfinance provides it via `.info`
   - What's unclear: Update frequency, accuracy
   - Recommendation: Accept daily granularity, validate against reported AUM periodically

2. **FRED SLVPRUSD availability**
   - What we know: Gold (GOLDPMGBD228NLBM) confirmed available
   - What's unclear: Silver series may have different ID
   - Recommendation: Use yfinance SI=F as primary, research FRED fallback during implementation

</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- Existing codebase: `fx.py`, `fred.py`, `yahoo.py` - verified patterns
- [FRED Gold Series](https://fred.stlouisfed.org/series/GOLDPMGBD228NLBM) - GOLDPMGBD228NLBM confirmed
- [FRED WTI Series](https://fred.stlouisfed.org/series/DCOILWTICO) - DCOILWTICO confirmed
- [FRED Brent Series](https://fred.stlouisfed.org/series/DCOILBRENTEU) - DCOILBRENTEU confirmed
- [Yahoo Finance GC=F](https://finance.yahoo.com/quote/GC=F/) - Gold futures ticker confirmed
- [Yahoo Finance HG=F](https://finance.yahoo.com/quote/HG=F/) - Copper futures ticker confirmed

### Secondary (MEDIUM confidence)
- [yfinance PyPI](https://pypi.org/project/yfinance/) - ETF `.info` property documented
- [yfinance GitHub Discussion](https://github.com/ranaroussi/yfinance/discussions/1761) - ETF holdings patterns

### Tertiary (LOW confidence - needs validation)
- Silver FRED series (SLVPRUSD) - verify during implementation

</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: yfinance for commodities (same as FX collector)
- Ecosystem: FRED via OpenBB as fallback
- Patterns: Batch download, ffill, long-format output
- Pitfalls: Rate limiting, unit mismatches, data staleness

**Confidence breakdown:**
- Standard stack: HIGH - uses existing libraries
- Architecture: HIGH - extends existing patterns
- Pitfalls: HIGH - documented in existing collectors
- Code examples: HIGH - adapted from working codebase

**Research date:** 2026-01-23
**Valid until:** 2026-02-23 (30 days - stable ecosystem)

</metadata>

---

*Phase: 04-market-indicators*
*Research completed: 2026-01-23*
*Ready for planning: yes*
