# Funding Market Stress Indicators - FRED Series Cheatsheet

**Quick lookup table for Phase 5 implementation.**

## At a Glance

| **What You Need** | **FRED Series** | **Frequency** | **Unit** | **Access** |
|---|---|---|---|---|
| SOFR (spot rate) | `SOFR` | Daily | % | ✅ OpenBB |
| SOFR distribution (stress signal) | `SOFR1`, `SOFR25`, `SOFR75`, `SOFR99` | Daily | % | ✅ OpenBB |
| Fed Funds Rate (baseline) | `EFFR` | Daily | % | ✅ OpenBB |
| Repo purchases (Fed ops) | `RPONTSYD` | Daily | $M | ✅ OpenBB |
| Reverse repo (liquidity ops) | `RRPONTSYD` | Daily | $M | ✅ OpenBB |
| Commercial paper (financial) | `DCPF3M` | Daily | % | ✅ OpenBB |
| Commercial paper (nonfinancial) | `DCPN3M` | Daily | % | ✅ OpenBB |
| Fed total assets (normalize RRP) | `WALCL` | Weekly | $M | ✅ OpenBB |
| Financial stress index (aggregate) | `STLFSI4` | Weekly | Index | ✅ OpenBB |
| Treasury 3-Month (risk-free) | `DGS3MO` or `TB3MS` | Daily | % | ✅ OpenBB |

**Key:** All series available via OpenBB's FRED integration. No external APIs needed.

---

## Spread Calculations (Copy-Paste Ready)

### SOFR-OIS Spread

```
= (SOFR - Fed_Funds_Upper_Bound - 0.08) × 100

Normal:  0-10 bps
Alert:  10-25 bps
Crisis: >25 bps
```

**FRED Series:** `SOFR` + `EFFR` + Fed Funds target (manual)

### SOFR Distribution Stress

```
= (SOFR99 - SOFR1) × 100

Normal:  <20 bps
Alert:  20-50 bps
Crisis: >50 bps
```

**FRED Series:** `SOFR99` + `SOFR1`

### Commercial Paper Spread

```
= ((DCPF3M + DCPN3M) / 2 - DGS3MO) × 100

Normal:  20-40 bps
Alert:  40-80 bps
Crisis: >100 bps
```

**FRED Series:** `DCPF3M` + `DCPN3M` + `DGS3MO`

### Federal Liquidity Usage Ratio

```
= (RRPONTSYD / 1000) / WALCL × 100

Normal:  <1%
Alert:   1-3%
Crisis:  >3%
```

**FRED Series:** `RRPONTSYD` + `WALCL`

---

## Implementation Checklist

- [ ] **Week 1:** Fetch SOFR, percentiles from FRED via OpenBB
- [ ] **Week 1:** Fetch Fed Funds and commercial paper rates
- [ ] **Week 2:** Implement SOFR-OIS spread calculation
- [ ] **Week 2:** Implement SOFR distribution width calculation
- [ ] **Week 3:** Fetch repo operations (RPONTSYD, RRPONTSYD)
- [ ] **Week 3:** Normalize repo by Fed total assets (WALCL)
- [ ] **Week 4:** Implement CP-OIS spread calculation
- [ ] **Week 4:** Set up alert thresholds and color coding
- [ ] **Week 5:** Dashboard integration and testing

---

## Common Mistakes (Avoid!)

| ❌ DON'T | ✅ DO |
|---|---|
| Use spot SOFR as stress indicator | Calculate SOFR-OIS spread (bps) |
| Forget basis adjustment (-8 bps) | Include OIS discount in calculation |
| Mix up units (% vs bps) | Convert explicitly: bps = % × 100 |
| Use RRPONTSYD in millions directly | Divide by 1000 to get billions |
| Ignore distribution width | Track SOFR99 - SOFR1 as stress signal |
| Forget Fed Funds target changed | Update target quarterly on FOMC meetings |

---

## Quick Stress Status (Jan 2026)

```
SOFR-OIS Spread:      ~15-25 bps      → YELLOW (elevated)
SOFR Distribution:    ~22 bps         → YELLOW (slightly elevated)
Fed RRP Usage:        ~$326B          → YELLOW (elevated)
CP Spread:            ~5 bps          → GREEN (normal)

Overall Status:       YELLOW - WATCH MODE (not crisis, elevated from normal)
```

---

## External References (For Deep Dives)

| Source | Link | Content |
|---|---|---|
| **NY Fed Markets** | https://markets.newyorkfed.org/api/rates/secured/sofr | Real-time SOFR percentiles |
| **FRED SOFR Data** | https://fred.stlouisfed.org/series/SOFR | Historical SOFR |
| **FRED Repo Data** | https://fred.stlouisfed.org/series/RRPONTSYD/ | Historical repo operations |
| **St. Louis Fed Stress Index** | https://fred.stlouisfed.org/series/STLFSI4 | Aggregate stress measure |
| **Fed Announcements** | https://www.federalreserve.gov | Fed Funds target changes |

---

## Formulas at a Glance

**SOFR-OIS Stress Score** (0-100, where >50 is alert)
```
stress_score = max(
    (SOFR_OIS_spread_bps / 25) × 50,              # 50% weight
    ((SOFR99 - SOFR1) / 50) × 30,                 # 30% weight
    ((RRPONTSYD / 1000) / WALCL / 0.03) × 20      # 20% weight
)
```

---

## Data Refresh Schedule

| Series | Update | Check Frequency | Purpose |
|--------|--------|---|---|
| SOFR, percentiles | Daily 8 AM ET | Morning before market open | Real-time stress detection |
| CP rates, Repo data | Daily EOD | Daily EOD | Daily trend tracking |
| WALCL, STLFSI4 | Weekly Thursday | Weekly | Macro regime classification |
| Fed Funds Target | FOMC meetings (8x/year) | Quarterly review | Update spread calculations |

---

**Recommendation:** Bookmark this sheet + TECHNICAL_REFERENCE.md for Phase 5 implementation.

*Created: 2026-01-23*
