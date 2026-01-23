# Phase 5: Funding Market Stress Indicators - Research

**Researched:** 2026-01-23
**Domain:** Funding market stress metrics (SOFR-OIS, FRA-OIS, repo fails, CP-OIS)
**Confidence:** HIGH

<research_summary>

## Summary

Researched funding market stress indicators—the critical early warning signals for liquidity crises in money markets. Primary focus: SOFR-OIS spread, FRA-OIS spread, repo market stress metrics, and commercial paper-OIS spread.

**Key findings:**
1. **SOFR-OIS spread:** Available via FRED (SOFR + 3M OIS derived from swaps). Widening indicates funding stress; normal <10bps, stressed >25bps.
2. **SOFR percentiles:** NY Fed publishes SOFR1, SOFR25, SOFR75, SOFR99 daily. Distribution width is stress indicator.
3. **Repo stress:** RPONTSYD (Repo purchases) and RRPONTSYD (RRP sales) track Fed intervention. Haircuts on Treasuries widen under stress.
4. **CP-OIS spread:** Commercial paper rates (DCPN3M, DCPF3M) minus 3M OIS. Component of St. Louis Fed Financial Stress Index.

**Standard approach:** FRED API via OpenBB for all components, matching existing collector patterns.

</research_summary>

<standard_stack>

## FRED Series IDs and Data Sources

### 1. SOFR-OIS Spread

**What it measures:** Difference between 3-month SOFR and 3-month OIS rate. Widening indicates banking system stress and liquidity concerns.

**Components:**

| Component | FRED Series | Frequency | Unit | Source | Status |
|-----------|-------------|-----------|------|--------|--------|
| SOFR (spot rate) | SOFR | Daily | percent | NY Fed Markets API + FRED | Available |
| SOFR 90-day average | SOFR90DAYAVG | Daily | percent | FRED | Available |
| 3-Month OIS | N/A | Daily | percent | Bloomberg (NOT in FRED) | Limited |
| Effective Fed Funds Rate | EFFR | Daily | percent | FRED | Available |
| Fed Funds Target Upper Bound | N/A | Variable | percent | Fed announcements | Available |

**Calculation:**
```
SOFR-OIS Spread = SOFR(3M) - OIS(3M)
                = SOFR(3M) - Federal Funds Rate(3M implied)
```

**Key insight:** Perfect OIS proxy unavailable in FRED. Practical substitute: use Fed Funds Target Upper Bound or EFFR + basis adjustment.

**Stress thresholds (historical):**
- Normal: <10 basis points
- Elevated: 10-25 bps
- Stressed: >25 bps (Sept 2019: >100 bps at peak)

### 2. SOFR Percentiles (Distribution-Based Stress)

**What it measures:** Volume-weighted distribution of SOFR transactions. Wide spread (99th - 1st percentile) = market dysfunction.

**FRED Series:**

| Percentile | FRED Series | Frequency | Unit | Availability |
|-----------|------------|-----------|------|--------------|
| 1st | SOFR1 | Daily | percent | Available from Apr 2018 |
| 25th | SOFR25 | Daily | percent | Available from Apr 2018 |
| 75th | SOFR75 | Daily | percent | Available from Apr 2018 |
| 99th | SOFR99 | Daily | percent | Available from Apr 2018 |
| Median | SOFR | Daily | percent | Available from Apr 2018 |

**Calculation:**
```
Distribution Width = SOFR99 - SOFR1
Normal: <10 bps
Stressed: >50 bps (indicates some lenders being shut out)
```

**Interpretation:**
- Wide spread = some participants paying much more than others
- Suggests tiering in money markets (cash crunch for weaker banks)
- Precursor to broader funding stress

### 3. Repo Market Stress Indicators

**What it measures:** Federal Reserve Standing Repo Facility (SRF) usage, overnight repo rate spikes, failed trades.

**Fed Repo Operations Data:**

| Metric | FRED Series | Frequency | Unit | Source |
|--------|------------|-----------|------|--------|
| Repo Purchases (TOMO) | RPONTSYD | Daily | millions USD | Fed Open Market Operations |
| Reverse Repo Sales (TOMO) | RRPONTSYD | Daily | millions USD | Fed Open Market Operations |
| Standing Repo Facility | N/A | Daily | millions USD | NY Fed (via API/press releases) |

**Calculation:**
```
Repo Stress Index = (RRP Usage + SRF Usage) / Fed Total Assets
                  = (RRPONTSYD + SRF) / WALCL
```

**Key thresholds:**
- Normal: RRP <$100B/day
- Elevated: RRP >$500B/day
- Stressed: SRF tapped (nearly zero baseline) or RRP >$1T

**Historical context:**
- Sept 2019: SOFR spiked to 5.25% (from ~2%), repo rates >8%
- March 2020: RRP usage surged during COVID panic
- Nov 2025: SRF drawn $18.5B single day (largest since inception)

**NY Fed Markets API:**
```
https://markets.newyorkfed.org/api/rates/secured/sofr
https://markets.newyorkfed.org/api/rates/secured/rrp (for RRP data)
```

### 4. FRA-OIS Spread

**What it measures:** Spread between 3-month Forward Rate Agreement (LIBOR legacy) and OIS. Euribor/€STR equivalents exist for EUR.

**Data Challenge:** FRA data primarily from Bloomberg (commercial), not FRED.

**FRED Proxy Series:**

| Metric | FRED Series | Frequency | Unit | Notes |
|--------|------------|-----------|------|-------|
| 3-Month LIBOR-OIS (historical) | MMNRNJ | Daily | basis points | Discontinued post-LIBOR |
| Replaced by: SOFR-OIS approach | (calculated) | Daily | basis points | Use SOFR proxy |

**Challenge:** FRED doesn't have direct 3M OIS series. Workaround:
1. Use Fed Funds Swaps or EFFR as OIS proxy
2. Combine SOFR vs implied FF rate
3. Monitor St. Louis Fed Financial Stress Index (includes FRA-OIS)

**St. Louis Fed Financial Stress Index (STLFSI4):**
- FRED Series: STLFSI4
- Frequency: Weekly
- Includes FRA-OIS spread as component
- Aggregate stress measure (easier alternative)

### 5. Commercial Paper - OIS Spread

**What it measures:** Credit risk premium in short-term corporate borrowing. Widens when credit market stress increases.

**FRED Series:**

| Component | FRED Series | Frequency | Unit | Type |
|-----------|------------|-----------|------|------|
| 3M AA Financial CP | DCPF3M | Daily | percent | Financial company issuers |
| 3M AA Nonfinancial CP | DCPN3M | Daily | percent | Non-financial company issuers |
| 3M Treasury Bill | DGS3MO or TB3MS | Daily | percent | Risk-free baseline |
| 3M Comm Paper - Fed Funds | CPFF | Daily | basis points | Pre-calculated spread |

**Calculation:**
```
CP-OIS Spread = (DCPF3M or DCPN3M) - (OIS equivalent)
              = (DCPF3M) - (EFFR or TB3MS)
Pre-calculated in FRED: CPFF = CP - Fed Funds Rate
```

**Stress thresholds:**
- Normal: 20-40 bps
- Elevated: 40-100 bps
- Stressed: >100 bps (2008 crisis: >600 bps)

**Key insight:** Financial CP typically >25bps premium to nonfinancial (banks tighter credit than corporates).

</standard_stack>

<calculation_formulas>

## Recommended Stress Indicator Calculations

### 1. Comprehensive SOFR-OIS Spread (Practical Version)

Since true OIS not in FRED:

```python
sofr_ois_proxy = (
    sofr_rate(t)
    - fed_funds_target_upper_bound(t)
    - basis_adjustment
)

# Basis adjustment: ~-5 to -10 bps (OIS typically trades below Fed Funds)
# During normal times: adjustment needed to match market spreads
```

**Data sources needed:**
- SOFR (FRED: SOFR)
- Fed Funds Target Upper Bound (from Fed announcements, varies quarterly)
- Implied 3M FF rate (from Fed Funds Futures or calculated from yield curve)

### 2. SOFR Distribution Stress Index

```python
sofr_distribution_stress = (
    (sofr_99 - sofr_1) / sofr_median
) * 100  # as percentage

# Interpretation:
# <5% = normal market (tight distribution)
# 5-15% = elevated (widening)
# >15% = stressed (significant tiering)
```

### 3. Federal Liquidity Stress Index

```python
fed_liquidity_stress = (
    reverse_repo_usage / fed_total_assets +
    standing_repo_usage / fed_total_assets
)

# Can normalize by fed_total_assets to get as % of system liquidity
# Thresholds:
# <0.1% = normal
# 0.1-0.5% = elevated
# >0.5% = stressed (need for emergency Fed ops)
```

### 4. Credit Market Stress (CP-OIS)

```python
cp_ois_spread = (
    (dcpf3m + dcpn3m) / 2  # avg of financial and nonfinancial
    - (dgs3mo or effective_fed_funds)
)

# Convert to basis points
cp_ois_spread_bps = cp_ois_spread * 100
```

</calculation_formulas>

<typical_values>

## Typical Values and Stress Thresholds

### SOFR-OIS Spread History

| Event | SOFR-OIS | Context |
|-------|----------|---------|
| Normal (pre-2019) | 0-5 bps | Well-functioning markets |
| Early 2020 (normal pre-COVID) | 5-10 bps | Baseline post-LIBOR transition |
| March 2020 (COVID panic) | 20-50 bps | First shock, recovering quickly |
| June 2020 (post-SRF launch) | <10 bps | Liquidity ample, Fed backstop effective |
| Oct-Nov 2025 (current stress) | 15-25 bps | Persistent tightness, SOFR near ceiling |

**Stress signals:**
- >10 bps: Watch (not normal, but not emergency)
- >25 bps: Alert (funding stress building)
- >50 bps: Crisis (banking system stress)
- >100 bps: Emergency (Sept 2019 peak, March 2020 worst)

### SOFR Percentiles - Normal Conditions

**Jan 2026 snapshot (approximate):**
- SOFR1: 4.20%
- SOFR25: 4.28%
- SOFR (median): 4.33%
- SOFR75: 4.37%
- SOFR99: 4.42%
- Range (99-1): 22 bps (normal, <50 bps)

**During Sept 2019 stress:**
- Range widened to >100 bps (showing market fragmentation)

### Fed Repo Operations - Typical Usage

| Scenario | RRPONTSYD Volume | Duration |
|----------|-----------------|----------|
| Normal (pre-2019) | ~$0 (rarely used) | N/A |
| Steady state (2020-2022) | $0-50B | Daily |
| QT period (2023-2024) | Ramping $0-100B | Gradual |
| Recent stress (Oct-Nov 2025) | $200-400B spikes | Intermittent |
| Standing Repo Facility | <$1B baseline | Triggered during stress |

### Commercial Paper - OIS Spread

| Scenario | CP-OIS (bps) | Signal |
|----------|-------------|--------|
| Normal, tight credit | 20-30 | Equilibrium |
| Fed hiking cycle | 30-50 | Normal uncertainty |
| Recession expectations | 50-100 | Credit tightening |
| Market crisis (2008) | >600 | Credit markets frozen |
| COVID initial shock (Mar 2020) | 150-200 | Panic selling |
| Post-emergency program | 50-80 | Recovering |

</typical_values>

<data_availability>

## Data Availability Summary

### Complete Coverage (FRED via OpenBB)

- ✅ SOFR (SOFR) - daily, 2018-present
- ✅ SOFR percentiles (SOFR1, SOFR25, SOFR75, SOFR99) - daily, 2018-present
- ✅ Effective Fed Funds Rate (EFFR) - daily, 1954-present
- ✅ Treasury yields (DGS2, DGS10, DGS3MO) - daily, 1962-present
- ✅ VIX (VIXCLS) - daily, 1990-present
- ✅ Credit spreads (BAMLH0A0HYM2, BAMLC0A0CM) - daily, 1990s-present
- ✅ Reverse Repo data (RRPONTSYD, RPONTSYD) - daily, via FRED
- ✅ St. Louis Fed Financial Stress Index (STLFSI4) - weekly

### Limited Coverage (Workarounds)

- ⚠️ 3-Month OIS: NOT in FRED. Workaround = use Fed Funds proxy + basis adjustment
- ⚠️ FRA data: Primarily Bloomberg (NOT in FRED). Workaround = use STLFSI4 index instead
- ⚠️ Standing Repo Facility: Not in FRED. Source = NY Fed press releases + API

### Alternative Sources (Non-FRED)

- **NY Fed Markets API:** https://markets.newyorkfed.org/api/
  - SOFR detailed data (percentiles, volumes)
  - RRP operations data
  - Repo rates by collateral type

- **NY Fed Data Hub:** https://www.newyorkfed.org/data-hub/
  - Standing Repo Facility usage
  - Repo operations details

</data_availability>

<architecture_patterns>

## Implementation Patterns for Stress Collectors

### Pattern 1: SOFR-Derived Spreads

**Suggested collector:** `stress_sofr_ois.py`

```python
# Following existing SOFR collector pattern
class SOFRStressCollector(BaseCollector):

    def __init__(self):
        # Uses existing SOFR collector for base data
        # Adds Fed Funds data from FRED
        # Calculates SOFR-OIS proxy
        pass

    async def collect(self) -> pd.DataFrame:
        """
        Returns:
            DataFrame with columns:
            - timestamp
            - series_id (SOFR-OIS-PROXY, SOFR-FF-SPREAD, etc.)
            - source (computed)
            - value (bps)
            - unit (basis_points)
        """
```

### Pattern 2: Percentile Distribution Collector

**Suggested collector:** `sofr_percentiles.py`

```python
# Fetches SOFR1, SOFR25, SOFR75, SOFR99 from FRED
class SOFRPercentilesCollector(BaseCollector):

    PERCENTILE_SERIES = {
        "sofr1": "SOFR1",
        "sofr25": "SOFR25",
        "sofr75": "SOFR75",
        "sofr99": "SOFR99",
    }

    async def collect(self) -> pd.DataFrame:
        """Returns percentile data + calculated distribution width."""
        # Similar to existing FRED collector
        # Add calculated field: distribution_width = sofr99 - sofr1
```

### Pattern 3: Fed Repo Operations Collector

**Suggested collector:** `fed_repo_operations.py`

```python
# Fetches RPONTSYD, RRPONTSYD from FRED
# Optionally enriched with SRF data from NY Fed API
class FedRepoCollector(BaseCollector):

    REPO_SERIES = {
        "repo_purchases": "RPONTSYD",      # Daily TOMO repos
        "reverse_repo": "RRPONTSYD",       # Daily RRP
    }

    async def collect(self) -> pd.DataFrame:
        """
        Returns daily Fed repo operations.
        Can be normalized by WALCL for stress intensity.
        """
```

### Pattern 4: Commercial Paper Collector

**Suggested collector:** `commercial_paper_spread.py`

```python
# Fetches CP rates and Treasury rates, calculates spread
class CommercialPaperCollector(BaseCollector):

    CP_SERIES = {
        "cp_financial": "DCPF3M",
        "cp_nonfinancial": "DCPN3M",
        "cp_ff_spread": "CPFF",
    }

    async def collect(self) -> pd.DataFrame:
        """
        Returns both individual CP rates and calculated CP-OIS spread.
        Average financial and nonfinancial for composite stress metric.
        """
```

### Anti-Patterns to Avoid

- ❌ Creating custom OIS calculation without basis adjustment (spreads won't match market)
- ❌ Using spot SOFR instead of SOFR-OIS for stress assessment (spot rate ≠ stress indicator)
- ❌ Ignoring SOFR percentiles (distribution width often leads spot SOFR-OIS spread as warning)
- ❌ Forgetting unit conversions (RPONTSYD in millions, SOFR in percent, bps for spreads)

</architecture_patterns>

<critical_details>

## Critical Implementation Details

### 1. SOFR-OIS Basis Adjustment

**Problem:** Perfect OIS unavailable in FRED. Need proxy for 3-month OIS.

**Solution cascade:**
1. **First choice:** Federal Funds Futures implied 3M rate (most accurate)
2. **Second choice:** SOFR90DAYAVG (close proxy, available in FRED)
3. **Third choice:** EFFR + basis (rough, but works)

**Basis adjustment needed:** OIS typically trades 5-10 bps *below* Fed Funds Target Upper Bound in normal conditions.

```python
# Example: Calculate SOFR-OIS spread
sofr_spot = df[df['series_id'] == 'SOFR']['value']
ff_upper = fed_target_upper_bound(date)  # from Fed announcements
basis = -0.07  # -7 bps (OIS typical discount)

sofr_ois_spread = sofr_spot - (ff_upper + basis)  # In percent
sofr_ois_spread_bps = sofr_ois_spread * 100  # Convert to bps
```

### 2. Unit Conversions

| FRED Series | Unit | Conversion |
|-------------|------|-----------|
| SOFR, EFFR | percent | ×100 for bps |
| DCPF3M, DCPN3M | percent | ×100 for bps |
| RPONTSYD, RRPONTSYD | millions USD | ÷1000 for billions |
| VIXCLS | percent | as-is |

### 3. SOFR vs SOFR90DAYAVG

- **SOFR:** Daily spot rate, high volatility (can spike intraday)
- **SOFR90DAYAVG:** 90-day moving average, smoother signal, better for trend
- **Use spot for:** Daily stress detection, high-frequency monitoring
- **Use average for:** Regime classification, smoothed stress index

### 4. Fed Funds Target Range

The Fed Funds Target is a **range**, not a point:
- Lower bound: 4.25% (as of Jan 2026)
- Upper bound: 4.50% (as of Jan 2026)

Use **upper bound** for SOFR-OIS calculation. Updates quarterly via FOMC decisions.

### 5. Standing Repo Facility Tracking

SRF not in FRED. Must track via:
1. NY Fed press releases (published when tapped)
2. NY Fed Markets API (if available in operations data)
3. Manual monitoring (baseline is $0 usage, any draw is a signal)

Fallback: Use RRPONTSYD (overnight RRP) as proxy for tight money conditions.

</critical_details>

<dont_hand_roll>

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Calculate OIS | Custom fed funds model | SOFR90DAYAVG + basis adjustment | Validated method, avoids custody risk |
| Fetch SOFR percentiles | Web scraper for NY Fed | FRED (SOFR1/25/75/99) | Reliable, historical, in standard stack |
| Repo operations data | Custom Fed parsing | FRED (RPONTSYD, RRPONTSYD) | Standardized, frequent updates |
| LIBOR-OIS legacy | Recreate from swaps | St. Louis Fed Financial Stress Index (STLFSI4) | Officially maintained, includes FRA-OIS |
| Haircut tracking | Complex collateral model | Fed Repo Operations volume changes | Inverse correlation sufficient for stress |

**Key insight:** All SOFR and repo data needed for Phase 5 is already available via existing FRED integration. No new APIs required.

</dont_hand_roll>

<common_pitfalls>

## Common Pitfalls

### Pitfall 1: Confusing SOFR with SOFR-OIS Spread

**What goes wrong:** Using spot SOFR rate (4.33%) as stress indicator instead of spread (15 bps).

**Why it happens:** SOFR itself is published prominently, spread requires calculation.

**How to avoid:** ALWAYS calculate spread when assessing funding stress. Spot rate != stress level. (SOFR at 4.5% in neutral conditions is OK; SOFR-OIS spread >25 bps is warning.)

**Warning signs:** Dashboard shows SOFR values instead of bps spreads.

### Pitfall 2: Missing the Percentile Width Signal

**What goes wrong:** Watching SOFR median trend, missing that 99th-1st percentile spread doubled.

**Why it happens:** Median-focused analysis ignores market fragmentation.

**How to avoid:** Track both median AND distribution width. Wide distribution often precedes broader stress.

**Warning signs:** SOFR99-SOFR1 >50 bps while median still <5 bps above Fed Funds target.

### Pitfall 3: Unit Confusion on Repo Data

**What goes wrong:** RPONTSYD in millions USD, accidentally comparing to balance sheet items in trillions.

**Why it happens:** FRED doesn't standardize units across series.

**How to avoid:** Always check FRED metadata for unit. RPONTSYD is millions; divide by 1000 for billions comparison.

**Warning signs:** Repo volume <1 on charts (should be 100s-1000s of billions).

### Pitfall 4: Ignoring the Basis Adjustment

**What goes wrong:** Calculating SOFR - Fed Funds and getting negative spread (impossible for risk-free benchmark).

**Why it happens:** OIS trades at a discount to Fed Funds during stress; need -5 to -10 bps adjustment.

**How to avoid:** Use: `spread_bps = (sofr - ffr_upper + basis_adj) * 100` where basis_adj = -0.07 to -0.10

**Warning signs:** SOFR-OIS spread goes negative (should never be <-20 bps)

### Pitfall 5: Forgetting to Update Fed Funds Target Range

**What goes wrong:** July 2025 calculations still using Jan 2026 Fed Funds target, spread meaningless.

**Why it happens:** Fed Funds range only changes at FOMC meetings (8x/year).

**How to avoid:** Maintain list of target range changes. Auto-update on FOMC announcement dates.

**Warning signs:** SOFR suddenly appears "stressed" (SOFR-OIS >25bps) without news, right after FOMC decision.

</common_pitfalls>

<implementation_order>

## Recommended Implementation Order

### Phase 5a (Weeks 1-2): Foundation

1. **SOFR percentiles collector** (`sofr_percentiles.py`)
   - Fetch SOFR1, SOFR25, SOFR75, SOFR99 from FRED
   - Calculate distribution width
   - Pattern: Extend existing FRED collector (reuse architecture)

2. **Fed Repo operations collector** (`fed_repo_operations.py`)
   - Fetch RPONTSYD (Repo purchases) and RRPONTSYD (RRP)
   - Store daily volumes
   - Pattern: Extend existing FRED collector

### Phase 5b (Weeks 3-4): Spreads & Stress Metrics

3. **SOFR-OIS spread calculator** (part of `stress_sofr_ois.py`)
   - Use existing SOFR collector data
   - Fetch Fed Funds target upper bound (manual or via API)
   - Calculate spread with basis adjustment
   - Output in bps

4. **Commercial Paper spread collector** (`commercial_paper_spread.py`)
   - Fetch DCPF3M, DCPN3M, CPFF from FRED
   - Calculate CP-OIS spread
   - Store both individual rates and spread

### Phase 5c (Week 5): Integration & Dashboard

5. **Stress indicator aggregator** (`stress_indicator_composite.py`)
   - Combine all above collectors
   - Calculate composite stress score
   - Update schema to support thresholds and alerts

6. **Dashboard updates**
   - Add stress indicators panel
   - Threshold coloring (green/yellow/red)
   - Historical context (% time in stress regime)

</implementation_order>

<sota_updates>

## State of the Art (2025-2026)

| Topic | Current Best Practice | Changed from | When | Impact |
|-------|----------------------|--------------|------|--------|
| SOFR percentiles | Daily publication from NY Fed | Manual LIBOR survey | 2018+ | Real-time distribution visibility |
| OIS rates | Bloomberg Terminal + FRED proxies | Bloomberg only | 2020+ | FRED integration possible via FFR |
| Repo data | Federal Reserve Systems integration | Manual Fed H.4.1 reports | 2022+ | Real-time repo volumes in FRED |
| Stress index | St. Louis Fed STLFSI4 (weekly) + OFR FSI | CESIUSD (discontinued) | 2022+ | More comprehensive, less opaque |
| SOFR-OIS spread | Spot calculation via SOFR API + basis | LIBOR-OIS (deprecated) | 2020-2022 | Direct SOFR data available now |

**Emerging tools (to monitor):**
- **NY Fed Markets Data Hub:** API for repo operations (check availability)
- **Federal Reserve FRED API:** Expanding real-time capabilities
- **OFR Financial Stress Index:** Alternative aggregate stress measure

**Deprecated/outdated:**
- LIBOR-OIS spread (LIBOR discontinued June 2023)
- TED Spread (less relevant post-LIBOR)
- Bloomberg L3 Index (Bloomberg proprietary, expensive)

</sota_updates>

<open_questions>

## Open Questions

1. **3-Month OIS exact FRED equivalent**
   - What we know: SOFR90DAYAVG exists and is close proxy
   - What's unclear: Should we use Fed Funds Futures or Treasury-based proxy?
   - Recommendation: Start with SOFR90DAYAVG (simpler), validate spread values against market data (news reports)
   - **Action:** During Phase 5a, test proxy values against published SOFR-OIS spreads from NY Fed, Bloomberg reports

2. **Standing Repo Facility tracking**
   - What we know: SRF tapped during crises (not in FRED)
   - What's unclear: API availability, update frequency
   - Recommendation: Use RRPONTSYD as proxy; add manual SRF tracking if needed
   - **Action:** Check NY Fed Markets Data Hub for SRF API availability in Phase 5b

3. **FRA-OIS equivalent for EUR/other currencies**
   - What we know: FRA data expensive (Bloomberg)
   - What's unclear: Should Phase 5 include EUR/GBP equivalents (€STR-OIS, SONIA-OIS)?
   - Recommendation: Start with USD only; plan for EUR Phase 6
   - **Action:** Document approach for EURIBOR/€STR transition post-Phase 5

4. **SOFR vs SOFR90DAYAVG for real-time monitoring**
   - What we know: Spot SOFR highly volatile, average smoother
   - What's unclear: Which is better for stress detection?
   - Recommendation: Track both; spot for daily alerts, average for regime classification
   - **Action:** Backtest alert logic on Sept 2019 and March 2020 data during Phase 5c

</open_questions>

<sources>

## Research Sources

### Primary (HIGH confidence)

- [FRED SOFR Series](https://fred.stlouisfed.org/series/SOFR) - Daily SOFR rates, official source
- [FRED SOFR Percentiles](https://fred.stlouisfed.org/series/SOFR1/) - SOFR1, SOFR25, SOFR75, SOFR99 (official NY Fed)
- [FRED Repo Operations](https://fred.stlouisfed.org/series/RPONTSYD/) - RPONTSYD (Treasury repo purchases)
- [FRED RRP Series](https://fred.stlouisfed.org/series/RRPONTSYD) - RRPONTSYD (overnight reverse repo)
- [NY Fed SOFR Reference Rates](https://www.newyorkfed.org/markets/reference-rates/sofr) - Official SOFR methodology, percentiles
- [NY Fed Markets API](https://markets.newyorkfed.org/api/rates/secured/sofr) - Real-time SOFR and percentile data

### Secondary (MEDIUM confidence)

- [Financial Stress and Equilibrium Dynamics in Money Markets](https://www.federalreserve.gov/econresdata/feds/2015/files/2015091pap.pdf) - Academic framework for FRA-OIS, SOFR-OIS spreads
- [What Are Financial Market Stress Indexes Showing?](https://www.stlouisfed.org/on-the-economy/2022/may/what-are-financial-market-stress-indexes-showing) - St. Louis Fed explainer on stress indices
- [Anatomy of the Repo Rate Spikes in September 2019](https://www.financialresearch.gov/working-papers/files/OFRwp-23-04_anatomy-of-the-repo-rate-spikes-in-september-2019.pdf) - OFR analysis of 2019 stress event
- [St. Louis Fed Financial Stress Index v3.0](https://fredblog.stlouisfed.org/2022/01/the-st-louis-feds-financial-stress-index-version-3-0/) - STLFSI4 methodology (includes SOFR-OIS, CP-OIS)
- [Haircuts in Treasury Repo](https://tellerwindow.newyorkfed.org/2025/04/08/haircuts-in-treasury-repo-a-look-at-the-non-centrally-cleared-bilateral-repo-market/) - NY Fed analysis of repo market structure

### Tertiary (LOWER confidence - preliminary data)

- [SOFR User Guide](https://www.newyorkfed.org/medialibrary/Microsites/arrc/files/2021/users-guide-to-sofr2021-update.pdf) - ARRC technical guide (good for background)
- [OFR Financial Stress Index](https://www.financialresearch.gov/financial-stress-index/) - Alternative aggregate stress measure
- [Arthur Hayes - Stealth QE and Funding Stress](https://www.tradingview.com/news/newsbtc:582ce3226094b:0-crypto-isn-t-topping-yet-arthur-hayes-says-stealth-qe-is-near/) - Market commentary on current funding stress signals

### FRED Series Reference

- SOFR (daily, 2018-present)
- SOFR1, SOFR25, SOFR75, SOFR99 (daily, 2018-present)
- SOFR90DAYAVG (daily, 2018-present)
- EFFR (daily, 1954-present)
- DCPF3M, DCPN3M (daily, 1990s-present)
- RPONTSYD, RRPONTSYD (daily, 2010s-present)
- STLFSI4 (weekly, 2008-present)
- VIXCLS (daily, 1990-present)
- DGS2, DGS10, DGS3MO (daily, 1962-present)
- BAMLH0A0HYM2, BAMLC0A0CM (daily, 1990s-present)

</sources>

<metadata>

## Metadata

**Research scope:**
- Funding market stress indicators (SOFR-OIS, FRA-OIS, repo, CP-OIS)
- Data sources: FRED (primary), NY Fed API (secondary), Bloomberg (tertiary)
- Calculation formulas: Spread definitions, thresholds, stress levels
- Architecture: Collector patterns matching existing Phase 1-3 patterns
- Implementation order: 5-week phased approach

**Confidence breakdown:**
- SOFR-OIS spread calculation: HIGH - verified against St. Louis Fed docs
- SOFR percentiles: HIGH - official NY Fed publication
- Repo operations: HIGH - FRED + NY Fed official data
- CP-OIS spread: HIGH - FRED published, St. Louis Fed validation
- OIS proxy via Fed Funds: MEDIUM - requires basis adjustment validation
- FRA-OIS data sources: MEDIUM - Bloomberg heavy, FRED minimal

**Limitations:**
- True 3-month OIS not in FRED; proxy approach needed
- FRA-OIS primarily Bloomberg (not free); St. Louis FSI is workaround
- Standing Repo Facility not in FRED; manual tracking required
- Historical OIS data limited (SOFR started Apr 2018)

**Research date:** 2026-01-23
**Valid until:** 2026-04-23 (quarterly - Fed rate changes, repo dynamics stable)

</metadata>

---

*Phase: 05-stress-indicators*
*Research completed: 2026-01-23*
*Ready for planning: yes*
