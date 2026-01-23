# Phase 5: Capital Flows & Stress - Research

**Researched:** 2026-01-23
**Status:** Complete

---

## Executive Summary

Phase 5 covers two distinct but complementary data domains:
1. **Capital Flows** - Where money is moving (TIC data, Fed custody, IMF COFER)
2. **Stress Indicators** - When plumbing is breaking (SOFR-OIS, cross-currency basis, repo stress)

All data sources are available through free APIs (FRED, Treasury, DBnomics, NY Fed). No Bloomberg terminal required.

---

## 1. TIC Data (Treasury International Capital)

### What It Measures
Foreign holdings and transactions in US securities - shows when foreign central banks/investors are buying or selling US Treasuries.

### Data Source
- **Primary:** US Treasury direct CSV download
- **URL:** `https://www.treasury.gov/resource-center/data-chart-center/tic/Documents/`
- **Format:** TXT (tab-delimited), HTML tables
- **Authentication:** None required (public data)

### Key Tables
| Table | Description | Use Case |
|-------|-------------|----------|
| slt_table3.txt | Foreign holdings by country | Total Treasury holdings |
| slt_table5.txt | Major Foreign Holders (MFH) | Top 25 countries ranked |

### Update Frequency
- Monthly release ~15-18 days after month-end
- Data latency: 2-3 weeks
- Historical: Back to 1939 for some series

### FRED Fallback Series
For quarterly aggregate data (no country breakdown):
```
BOGZ1FL263061130Q - Foreign Official Treasury Holdings
BOGZ1FL263061145Q - Foreign Private Treasury Holdings
```

### Implementation Notes
- **Series break at Feb 2023:** Form S → Form SLT (perspective reversed)
- Holdings data continuous, transaction data has break
- Parse CSV directly, no JSON API available

### Code Pattern
```python
import pandas as pd
import requests
from io import StringIO

def fetch_major_holders() -> pd.DataFrame:
    url = "https://www.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
    response = requests.get(url)
    return pd.read_csv(StringIO(response.text), delimiter='\t')
```

---

## 2. Fed Custody Holdings

### What It Measures
Securities held by Federal Reserve AS CUSTODIAN for foreign central banks and international accounts. Weekly granularity vs TIC monthly.

### Primary FRED Series

| Series ID | Description | Frequency |
|-----------|-------------|-----------|
| **WSEFINTL1** | Total custody holdings (Wed level) | Weekly |
| **WSEFINT1** | Total custody holdings (week average) | Weekly |
| **WMTSECL1** | Marketable Treasuries (Wed level) | Weekly |
| **WFASECL1** | Agency debt & MBS (Wed level) | Weekly |

### Update Schedule
- H.4.1 Report: Thursdays 4:30 PM ET
- Data as of Wednesday close-of-business
- Historical: From December 2002

### Current Values (Jan 2026)
- Total: $3,069,850M
- Treasuries: $2,770,578M (~90%)
- Agencies/MBS: $221,289M (~7%)

### Key Interpretation
- **Rising:** Foreign CBs accumulating Treasuries (safe-haven demand)
- **Falling:** Reserve reduction, repatriation, or collateral usage

---

## 3. IMF COFER (Currency Composition of FX Reserves)

### What It Measures
Global FX reserves composition by currency - tracks de-dollarization trends.

### Data Access (DBnomics Recommended)
IMF SDMX API has limitations. Use DBnomics mirror:

```
Base URL: https://api.db.nomics.world/v22/series/IMF/COFER
```

### Key Series Codes
| Currency | Series Code |
|----------|-------------|
| USD reserves | Q.W00.RAXGFXARUSD_USD |
| EUR reserves | Q.W00.RAXGFXARDEM_USD |
| CNY reserves | Q.W00.RAXGFXARCNY_USD |
| JPY reserves | Q.W00.RAXGFXARJPY_USD |
| GBP reserves | Q.W00.RAXGFXARGBP_USD |

### Update Frequency
- Quarterly (Q+1 month release)
- Historical: Q1 1999 - present
- Coverage: 147-149 central banks

### Python Library
```bash
pip install requests  # Direct API calls
pip install sdmx1     # SDMX metadata (not data queries)
```

### Recent Data (Q2 2025)
- Total FX reserves: $12.94T
- USD share: 56.32%
- EUR share: ~20%
- CNY share: ~2-3%

---

## 4. Stress Indicators

### 4.1 SOFR-OIS Spread

**What It Measures:** Funding market stress - difference between secured (SOFR) and unsecured (OIS/Fed Funds) rates.

**Calculation:**
```
SOFR_OIS_Spread = (SOFR - EFFR) × 100  # in basis points
```

**FRED Series:**
- `SOFR` - Secured Overnight Financing Rate
- `EFFR` - Effective Federal Funds Rate

**Thresholds:**
| Range | Signal |
|-------|--------|
| 0-10 bps | Normal |
| 10-25 bps | Elevated (Yellow) |
| >25 bps | Stress (Red) |

**Current (Jan 2026):** 15-25 bps (YELLOW)

### 4.2 SOFR Percentiles (Market Fragmentation)

**FRED Series:**
- `SOFR1` - 1st percentile
- `SOFR25` - 25th percentile
- `SOFR75` - 75th percentile
- `SOFR99` - 99th percentile

**Stress Metric:**
```
Distribution_Width = SOFR99 - SOFR1
```

**Thresholds:**
| Width | Signal |
|-------|--------|
| <20 bps | Normal |
| 20-50 bps | Elevated |
| >50 bps | Crisis |

**Current (Jan 2026):** 22 bps (YELLOW)

### 4.3 Cross-Currency Basis

**What It Measures:** USD funding premium/discount via FX swaps. More negative = stronger USD funding stress.

**Key Pairs:**
- EUR/USD basis (most liquid, ECB primary concern)
- JPY/USD basis (Japanese bank dollar demand)
- GBP/USD basis

**Data Sources:**
1. **ECB SDW** (EUR/USD only, weekly, free)
2. **CME EURXR futures** (real-time, subscription)
3. **Calculate from components** (FRED rates + spot FX)

**Thresholds (EUR/USD):**
| Range | Signal |
|-------|--------|
| -5 to -25 bps | Normal |
| -30 to -50 bps | Stress |
| >-80 bps | Acute stress |
| >-120 bps | Extreme (crisis) |

**Note:** Free data limited. ECB publishes EUR/USD weekly. For JPY/GBP, calculate from rate differentials or use St. Louis Fed Financial Stress Index (STLFSI4) as proxy.

### 4.4 Repo Market Stress

**FRED Series:**
- `RPONTSYD` - Repo purchases (Fed injecting liquidity)
- `RRPONTSYD` - Reverse repo (Fed draining liquidity)
- `WALCL` - Fed total assets (for normalization)

**Stress Metric:**
```
Repo_Stress = (RRPONTSYD / WALCL) × 100
```

**Thresholds:**
| Ratio | Signal |
|-------|--------|
| <1% | Normal |
| 1-3% | Elevated |
| >3% | Crisis |

**Current (Jan 2026):** $326B RRP / $7T = 4.7% (YELLOW)

### 4.5 Commercial Paper Spread

**FRED Series:**
- `DCPF3M` - 3-month financial CP rate
- `DCPN3M` - 3-month nonfinancial CP rate
- `DTB3` - 3-month Treasury bill rate

**Calculation:**
```
CP_Spread = (DCPF3M - DTB3) × 100  # in bps
```

**Thresholds:**
| Spread | Signal |
|--------|--------|
| 20-40 bps | Normal |
| 40-80 bps | Elevated |
| >100 bps | Crisis |

**Current (Jan 2026):** ~5 bps (GREEN)

---

## 5. Collector Architecture

### Recommended Pattern
Follow existing collector structure from Phases 1-4:

```python
class StressIndicatorCollector(BaseCollector[StressData]):
    """Aggregate stress indicator collector."""

    async def collect_sofr_ois_spread(self) -> pd.DataFrame:
        """SOFR-OIS spread via FRED."""
        sofr = await self._fetch_fred("SOFR")
        effr = await self._fetch_fred("EFFR")
        spread = (sofr - effr) * 100  # bps
        return spread

    async def collect_repo_stress(self) -> pd.DataFrame:
        """Repo market stress indicator."""
        rrp = await self._fetch_fred("RRPONTSYD")
        walcl = await self._fetch_fred("WALCL")
        return (rrp / walcl) * 100
```

### Multi-Tier Fallback (Like BoE, PBoC)
For cross-currency basis:
1. **Primary:** ECB SDW API (EUR/USD)
2. **Secondary:** Calculate from FRED components
3. **Tertiary:** Use STLFSI4 (St. Louis Financial Stress Index)

---

## 6. Data Quality Notes

### Timing Considerations
| Data | Frequency | Lag | Best For |
|------|-----------|-----|----------|
| TIC | Monthly | 15-18 days | Long-term flow trends |
| Fed custody | Weekly | 1-2 days | Medium-term CB activity |
| COFER | Quarterly | 1 month | De-dollarization tracking |
| SOFR/rates | Daily | Same day | Real-time stress |

### Known Issues
- **TIC Feb 2023 break:** Transaction perspective reversed
- **Cross-currency basis:** Free data limited to EUR/USD
- **COFER:** Only aggregate data public (no country breakdown)

---

## 7. Plan Recommendations

Based on research, suggest 5 plans for Phase 5:

### Plan 05-01: TIC Data Collector
- Parse Treasury CSV files (slt_table3, slt_table5)
- FRED fallback for quarterly aggregates
- Major holders ranking

### Plan 05-02: Fed Custody Collector
- FRED series: WSEFINTL1, WMTSECL1, WFASECL1
- Week-over-week and YoY changes
- Convenience methods for Treasury vs Agency split

### Plan 05-03: Stress Indicators (SOFR-based)
- SOFR-OIS spread
- SOFR percentiles (distribution width)
- CP-OIS spread
- Repo stress ratio

### Plan 05-04: Cross-Currency Basis
- ECB SDW API for EUR/USD (primary)
- Calculate from rate differentials (fallback)
- STLFSI4 integration (composite stress)

### Plan 05-05: IMF COFER Collector
- DBnomics API integration
- Currency share tracking (USD, EUR, CNY, JPY, GBP)
- De-dollarization metrics

---

## Sources

### Official Documentation
- [US Treasury TIC System](https://home.treasury.gov/data/treasury-international-capital-tic-system)
- [Federal Reserve H.4.1 Report](https://www.federalreserve.gov/releases/h41/)
- [NY Fed SOFR Reference Rates](https://www.newyorkfed.org/markets/reference-rates/sofr)
- [ECB Statistical Data Warehouse](https://data.ecb.eu/)
- [IMF COFER Dataset](https://data.imf.org/en/datasets/IMF.STA:COFER)
- [DBnomics IMF/COFER](https://db.nomics.world/IMF/COFER)

### FRED Series Reference
- [SOFR](https://fred.stlouisfed.org/series/SOFR)
- [SOFR Percentiles](https://fred.stlouisfed.org/series/SOFR1)
- [Fed Custody Holdings](https://fred.stlouisfed.org/series/WSEFINTL1)
- [Repo Operations](https://fred.stlouisfed.org/series/RPONTSYD)

### Research Papers
- [BIS: Understanding the Cross-Currency Basis](https://www.bis.org/publ/qtrpdf/r_qt1609e.pdf)
- [OFR: Anatomy of the Repo Rate Spikes Sept 2019](https://www.financialresearch.gov/working-papers/files/OFRwp-23-04_anatomy-of-the-repo-rate-spikes-in-september-2019.pdf)
- [St. Louis Fed Financial Stress Index v3.0](https://fredblog.stlouisfed.org/2022/01/the-st-louis-feds-financial-stress-index-version-3-0/)

---

*Research completed: 2026-01-23*
*Phase: 05-capital-flows-stress*
