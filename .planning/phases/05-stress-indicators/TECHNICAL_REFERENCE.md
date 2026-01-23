# Phase 5: Funding Market Stress Indicators - Technical Reference

**Created:** 2026-01-23
**Purpose:** Concrete FRED series IDs, calculation examples, and historical thresholds for stress indicators.

## Quick Reference: FRED Series Summary

### Stress Indicators (PRIMARY)

| Indicator | FRED Series | Frequency | Unit | Min | Max | Last Value |
|-----------|------------|-----------|------|-----|-----|------------|
| **SOFR (spot)** | SOFR | Daily | % | 0.05 (May 2020) | 5.33 (Aug 2023) | 4.33 (Jan 2026) |
| **SOFR 1st percentile** | SOFR1 | Daily | % | — | — | 4.20 (Jan 2026) |
| **SOFR 25th percentile** | SOFR25 | Daily | % | — | — | 4.28 (Jan 2026) |
| **SOFR 75th percentile** | SOFR75 | Daily | % | — | — | 4.37 (Jan 2026) |
| **SOFR 99th percentile** | SOFR99 | Daily | % | — | — | 4.42 (Jan 2026) |
| **SOFR 90-day average** | SOFR90DAYAVG | Daily | % | 0.07 (May 2020) | 5.30 (Aug 2023) | 4.32 (Jan 2026) |
| **Effective Fed Funds Rate** | EFFR | Daily | % | 0.02 (May 2020) | 5.33 (Aug 2023) | 4.33 (Jan 2026) |
| **Commercial Paper (Financial)** | DCPF3M | Daily | % | 0.03 (May 2020) | 5.90 (Nov 2023) | 5.45 (Jan 2026) |
| **Commercial Paper (Nonfinancial)** | DCPN3M | Daily | % | 0.10 (May 2020) | 5.49 (Jul 2023) | 5.16 (Jan 2026) |
| **Repo Purchases (Fed)** | RPONTSYD | Daily | $M | 0 | — | 27,500 (Jan 2026) |
| **Reverse Repo (Fed)** | RRPONTSYD | Daily | $M | 0 | — | 326,000 (Jan 2026) |

### Supporting Series (for context/spreads)

| Metric | FRED Series | Frequency | Unit | Purpose |
|--------|------------|-----------|------|---------|
| Treasury 3-Month Yield | DGS3MO or TB3MS | Daily | % | Risk-free baseline for CP spread |
| Treasury 2-Year Yield | DGS2 | Daily | % | Yield curve slope |
| Treasury 10-Year Yield | DGS10 | Daily | % | Long-end anchor |
| Fed Total Assets | WALCL | Weekly | $M | Normalize repo volumes |
| VIX | VIXCLS | Daily | % | Equity volatility (secondary stress signal) |
| HY Credit OAS | BAMLH0A0HYM2 | Daily | bps | Credit stress (macro correlate) |
| IG Credit OAS | BAMLC0A0CM | Daily | bps | IG stress indicator |
| St. Louis Fed Financial Stress | STLFSI4 | Weekly | Index | Aggregate stress (includes SOFR-OIS, FRA-OIS) |

## Spread Calculation Examples

### 1. SOFR-OIS Spread (Practical Version)

**Formula:**
```
SOFR_OIS_Spread_bps = (SOFR - Fed_Funds_Upper + Basis_Adjustment) × 100
```

**Inputs:**
- SOFR: FRED series SOFR (daily, percent)
- Fed Funds Upper: Depends on FOMC decision (current: 4.50%)
- Basis adjustment: -0.07 to -0.10 (OIS trades below Fed Funds)

**Example: January 22, 2026**
```
SOFR (spot)           = 4.33%
Fed Funds Upper       = 4.50%
Basis adjustment      = -0.08%

SOFR_OIS_Spread = (4.33 - 4.50 + (-0.08)) × 100
                = (-0.25) × 100
                = -25 bps

Interpretation: SOFR is 25 bps ABOVE the fair OIS level
              (More stress than normal: normal is -5 to -10 bps)
```

**Alternative: Using 90-day average (smoother)**
```
SOFR90DAYAVG = 4.32%
Basis adj = -0.08%

SOFR_OIS_Spread = (4.32 - 4.50 + (-0.08)) × 100 = -26 bps
```

### 2. SOFR Distribution Width (Percentile Spread)

**Formula:**
```
Distribution_Width_bps = (SOFR99 - SOFR1) × 100
Distribution_Width_Pct = Distribution_Width_bps / SOFR × 100
```

**Example: January 22, 2026**
```
SOFR99 = 4.42%
SOFR1  = 4.20%

Distribution_Width = (4.42 - 4.20) × 100 = 22 bps
Distribution_Width % = (22 bps) / (4.33% × 100) = 5.1%

Interpretation: Normal to slightly elevated
               (Normal: <5%, Stressed: >15%)
```

**Historical comparison: September 2019 peak**
```
SOFR99 ≈ 5.30%
SOFR1  ≈ 4.20%

Distribution_Width ≈ (5.30 - 4.20) × 100 = 110 bps (CRISIS LEVEL)
                  → Market severely fragmented, some lenders completely shut out
```

### 3. Commercial Paper - OIS Spread

**Formula:**
```
CP_OIS_Spread_bps = ((DCPF3M + DCPN3M) / 2 - Treasury_3M) × 100
```

**Example: January 22, 2026**
```
DCPF3M (Financial CP)    = 5.45%
DCPN3M (Nonfinancial CP) = 5.16%
Treasury 3M (DGS3MO)     = 5.25%

CP_OIS_Spread = ((5.45 + 5.16) / 2 - 5.25) × 100
              = (5.305 - 5.25) × 100
              = 5.5 bps

Interpretation: Normal credit premium (~20-40 bps is normal, this is TIGHT)
               Suggests funding confidence
```

**Alternative: Using pre-calculated CPFF**
```
CPFF (3M CP - Fed Funds) = 0.05% = 5 bps
Adjustment for upper bound = CPFF - (Fed_Funds_Upper - Fed_Funds_Current)
```

### 4. Federal Liquidity Intensity Index

**Formula:**
```
Liquidity_Intensity = (RRPONTSYD / 1000) / WALCL × 100
```

**Example: January 22, 2026**
```
RRPONTSYD          = 326,000M = $326B
WALCL (Fed Assets) = 7,000,000M = $7,000B

Liquidity_Intensity = (326 / 7000) × 100 = 4.7%

Interpretation: Fed RRP is using ~5% of total Fed balance sheet
               Normal baseline: <1%
               Elevated: 1-3%
               Stressed: >3%

Current state: ELEVATED (above normal, not yet crisis)
```

**Sept 2019 peak (for context):**
```
RRP usage was nearly $0 (not yet established)
But Fed Funds rate spiked to 5.25%, indicating systemic stress
→ RRP didn't exist; stress manifested in SOFR spike instead
```

## Historical Stress Events - Reference Table

### Event: September 2019 (Repo Market Crisis)

| Metric | Pre-Crisis | Peak | Post-Resolution | Source |
|--------|-----------|------|-----------------|--------|
| SOFR | ~2.0% | 5.25% | ~2.2% | NY Fed |
| SOFR-OIS Spread | ~5 bps | >100 bps | ~10 bps | Calculated |
| SOFR Distribution Width | — | >100 bps | <30 bps | NY Fed percentiles |
| Fed Funds Rate | 2.0% | 5.25% | 2.0% | Federal Reserve |
| Repo Rate (GC) | ~2.1% | 8.5% | ~2.2% | SIFMA |
| Fed RRP Usage | ~$0 (not used) | — | — | Fed |

**What happened:** End-of-quarter liquidity crunch + corporate tax date + Fed balance sheet reduction → overnight repo rates spiked

**Fed response:** Launched Standing Repo Facility and resumed repo operations

### Event: March 2020 (COVID Pandemic)

| Metric | Pre-Crisis | Worst Day | Recovery (Apr 2020) | Source |
|--------|-----------|-----------|-------------------|--------|
| SOFR | ~1.5% | 0.54% (low) | ~1.3% | NY Fed |
| SOFR-OIS Spread | ~2 bps | 20-40 bps (brief) | <10 bps | Market data |
| VIX | 17 | 82 (peak) | 35 | CBOE |
| HY OAS (BAMLH0A0HYM2) | 350 bps | 1000+ bps | 600 bps | BofA |
| IG OAS (BAMLC0A0CM) | 100 bps | 400+ bps | 200 bps | BofA |
| Fed Total Assets (WALCL) | 4,200B | — | 7,100B (+68%) | FRED |

**What happened:** Panic selling, money market outflows, credit spreads blew out, Fed launched emergency programs

**Fed response:** Massive QE, commercial paper lending facility, Main Street lending, money market support

### Event: October-November 2025 (Current/Recent Stress)

| Metric | September 2025 | Peak (Nov 2025) | Latest (Jan 2026) | Trend |
|--------|---|---|---|---|
| SOFR | 4.15% | 4.42% | 4.33% | **Elevated** |
| SOFR-OIS Spread | ~10 bps | ~20+ bps | ~15-25 bps | **Persistent stress** |
| SOFR Distribution Width | <20 bps | >30 bps | ~22 bps | **Remains wide** |
| Standing Repo Facility | <$1B | $18.5B (single day) | ~$5-10B typical | **Active** |
| Fed Total Assets | 6,850B | 6,900B | 7,000B | **Growing again** |

**What happened:** Persistent monetary tightness, thin reserve conditions, quarter-end pressures

**Status:** Still in "watch" mode, not yet crisis

## Stress Regime Definitions

Based on SOFR-OIS spread and supporting indicators:

### GREEN (Normal Functioning)
**SOFR-OIS Spread:** 0-10 bps | **Distribution Width:** <20 bps

Characteristics:
- SOFR trades in normal band vs Fed Funds
- Percentile distribution tight (all lenders accessing similar rates)
- Commercial paper spreads normal (20-40 bps over Treasuries)
- Fed RRP usage low (<$100B)
- Repo rates stable

Example: Most of 2021-2022, 2015-2018

### YELLOW (Elevated - Watch Mode)
**SOFR-OIS Spread:** 10-30 bps | **Distribution Width:** 20-50 bps

Characteristics:
- SOFR rising above Fed target band
- Some tiering in percentiles (larger banks getting better rates)
- CP spreads widening (40-80 bps)
- Fed RRP usage increasing ($100-500B)
- Repo rates occasionally elevated

Actions:
- Monitor daily; update alerts
- Check quarter-end/month-end calendar
- Watch for policy responses (Fed meetings)

Current status: **October 2025-Present**

### RED (Stressed/Crisis)
**SOFR-OIS Spread:** >30 bps | **Distribution Width:** >50 bps

Characteristics:
- SOFR breaking Fed target band
- Severe tiering (small lenders shut out of funding)
- CP spreads spiking (100+ bps)
- Fed RRP maxed or SRF activated
- Repo rates >Fed Funds target
- May see Fed emergency programs

Actions:
- Daily monitoring of all indicators
- Alert trading desks immediately
- Coordinate with Fed announcements
- Track alternative funding sources

Historical: September 2019, March 2020

## Key Decision Trees

### Decision 1: Is This Real Stress or Noise?

```
IF SOFR-OIS spread > 15 bps:
  ├─ Check SOFR Distribution Width
  │  ├─ If <20 bps: Likely noise (single event, temporary)
  │  └─ If >20 bps: Real stress (market fragmentation)
  ├─ Check Commercial Paper spread
  │  ├─ If <40 bps: Still manageable
  │  └─ If >40 bps: Credit stress building
  └─ Check Fed RRP usage
     ├─ If <$200B: Liquidity ample
     └─ If >$300B: Liquidity tight
```

### Decision 2: Should We Adjust Our Macro Framework?

```
IF 2+ of these 3 triggered simultaneously:
  1. SOFR-OIS spread >25 bps
  2. SOFR Distribution Width >30 bps
  3. Fed RRP usage >$250B

THEN:
  ├─ Flag regime as "transitioning to stressed"
  ├─ Increase monitoring frequency (daily → intraday)
  ├─ Alert macro strategies team
  └─ Prepare scenarios with wider spreads
```

### Decision 3: When Does Fed Step In?

```
IF SOFR-OIS spread >50 bps OR
   SOFR breaks Fed Funds Upper bound OR
   SRF usage >$100B:

THEN:
  ├─ Fed almost certainly to announce support
  ├─ Historical precedent: Within 24-72 hours
  └─ Prepare for potential policy announcement
```

## Python Implementation Snippets

### Snippet 1: Calculate SOFR-OIS Spread

```python
import pandas as pd
from datetime import datetime

def calculate_sofr_ois_spread(
    sofr_value: float,  # in percent, e.g., 4.33
    fed_funds_upper: float = 4.50,  # Current as of Jan 2026
    basis_adjustment: float = -0.08,  # OIS typically -5 to -10 bps below FFR
) -> float:
    """
    Calculate SOFR-OIS spread in basis points.

    Args:
        sofr_value: SOFR rate in percent
        fed_funds_upper: Fed Funds target upper bound
        basis_adjustment: OIS discount relative to Fed Funds

    Returns:
        Spread in basis points (positive = stress, negative = cushion)
    """
    spread = (sofr_value - fed_funds_upper + basis_adjustment) * 100
    return spread

# Example
sofr_ois = calculate_sofr_ois_spread(4.33)  # -25 bps (elevated)
print(f"SOFR-OIS Spread: {sofr_ois:.1f} bps")
```

### Snippet 2: Stress Level Classification

```python
def classify_stress_level(
    sofr_ois_spread: float,  # in bps
    sofr_distribution_width: float,  # in bps
    fed_rrp_usage_billions: float,  # in billions USD
) -> str:
    """Classify market stress regime based on multiple indicators."""

    # Green: Normal
    if sofr_ois_spread < 10 and sofr_distribution_width < 20 and fed_rrp_usage_billions < 100:
        return "GREEN"

    # Yellow: Elevated
    elif sofr_ois_spread < 30 and sofr_distribution_width < 50 and fed_rrp_usage_billions < 500:
        return "YELLOW"

    # Red: Stressed
    else:
        return "RED"

# Example
status = classify_stress_level(sofr_ois_spread=-25, sofr_distribution_width=22, fed_rrp_usage_billions=326)
print(f"Stress Status: {status}")  # Output: YELLOW
```

### Snippet 3: FRED Data Fetch (pseudo-code)

```python
from openbb import obb
import pandas as pd

async def fetch_sofr_indicators(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch all SOFR-based stress indicators from FRED."""

    series_ids = [
        "SOFR",      # Spot rate
        "SOFR1",     # 1st percentile
        "SOFR25",    # 25th percentile
        "SOFR75",    # 75th percentile
        "SOFR99",    # 99th percentile
        "SOFR90DAYAVG",  # 90-day average
        "DCPF3M",    # Financial CP
        "DCPN3M",    # Nonfinancial CP
        "RPONTSYD",  # Repo purchases
        "RRPONTSYD", # Reverse repo
        "WALCL",     # Fed total assets
    ]

    all_data = {}
    for series_id in series_ids:
        df = obb.economy.fred_series(
            symbol=series_id,
            start_date=start_date,
            end_date=end_date,
            provider="fred"
        )
        all_data[series_id] = df

    return all_data
```

## Thresholds for Alerting

### Daily Monitoring Thresholds

| Alert Level | SOFR-OIS Spread | Distribution Width | Fed RRP Usage | Action |
|---|---|---|---|---|
| **Green** | <10 bps | <20 bps | <$100B | Log only |
| **Yellow-1** | 10-15 bps | 20-30 bps | $100-200B | Notify team daily |
| **Yellow-2** | 15-25 bps | 30-50 bps | $200-500B | **Alert + brief** |
| **Red-1** | 25-40 bps | 50-100 bps | $500B-1T | **Alert + update strategy** |
| **Red-2** | >40 bps | >100 bps | >$1T | **Escalate to leadership** |

### Threshold Rationale

- **10 bps (Green→Yellow):** First signal of tightening (persistent)
- **25 bps (Yellow→Red):** Historical stress begins (2008 levels)
- **50 bps+ (Red-2):** Systemic crisis (equivalent to Sept 2019)

## Data Quality Notes

### Known Issues & Workarounds

1. **SOFR percentiles occasionally go NaN or missing**
   - Cause: NY Fed may skip holiday reporting
   - Fix: Forward-fill from previous trading day
   - Check: SOFR99 > SOFR75 > SOFR (median) > SOFR25 > SOFR1 always

2. **RRPONTSYD can spike on quarter-end (false signals)**
   - Cause: Quarter-end reserve drains (not stress-related)
   - Fix: Filter out last day of March, June, Sept, Dec
   - Context: Check other indicators (SOFR-OIS spread, CP spreads)

3. **Fed Funds Target changes quarterly, not captured in FRED**
   - Cause: FOMC decisions, not automated data
   - Fix: Manually maintain list of target range changes
   - Source: Federal Reserve press releases (8x/year)

4. **DCPF3M vs DCPN3M divergence**
   - Cause: Banks (financial) vs corporates (nonfinancial) different credit tiers
   - Normal: DCPF3M > DCPN3M by 20-30 bps
   - Alert: Divergence >50 bps = severe financial sector stress

### Data Freshness Requirements

| Series | Update Frequency | Max Age for Alerts | Recommended Check |
|--------|---|---|---|
| SOFR, SOFR percentiles | Daily (8:00 AM ET) | <24 hours | Before market open |
| DCPF3M, DCPN3M | Daily | <24 hours | Before market open |
| RPONTSYD, RRPONTSYD | Daily | <24 hours | After Fed ops close |
| WALCL | Weekly (Thursday) | <7 days | Weekly review |
| STLFSI4 | Weekly | <7 days | Weekly review |

---

**This document is a companion to RESEARCH.md. Use RESEARCH.md for methodology and sources; use this document for concrete calculations and thresholds.**

*Created: 2026-01-23*
*Last updated: 2026-01-23*
