# Phase 18 Research: Oil Term Structure

## Executive Summary

WTI futures term structure analysis per contango/backwardation signals. yfinance fornisce solo CL=F (front month continuous), ma è sufficiente per MVP. Full term structure richiede CME API.

## Data Sources

### yfinance (Verified Working)

| Symbol | Description | Status |
|--------|-------------|--------|
| `CL=F` | WTI Crude front-month continuous | ✅ Working |
| `CLF26`, `CLG26`, etc. | Specific contract months | ❌ Not available |
| `BZ=F` | Brent Crude front-month | ✅ Working |

**Limitations:**
- Solo front month disponibile
- No full futures curve
- Rollover automatico nasconde term structure

### CME API (Future Enhancement)

- Undocumented endpoints available
- Full contract chain data
- Richiede custom HTTP scraper
- Reference: `https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.quotes.html`

### FRED (Spot Only)

| Series | Description |
|--------|-------------|
| `DCOILWTICO` | WTI Spot Price |
| `DCOILBRENTEU` | Brent Spot Price |

No term structure data - solo spot prices.

## Contract Naming Conventions

CME WTI (CL) month codes:
- F = January
- G = February
- H = March
- J = April
- K = May
- M = June
- N = July
- Q = August
- U = September
- V = October
- X = November
- Z = December

Example: `CLG26` = February 2026 WTI contract

## Term Structure Calculations

### 1. Contango/Backwardation Detection

```python
spread = back_month_price - front_month_price

if spread > threshold:
    structure = "CONTANGO"      # Supply abundant, storage costs priced in
elif spread < -threshold:
    structure = "BACKWARDATION" # Supply tight, immediate delivery premium
else:
    structure = "FLAT"
```

**Market Interpretation:**
- **Contango:** Bearish supply signal, oversupply, weak demand
- **Backwardation:** Bullish supply signal, tight supply, strong demand

### 2. Front-Back Spread

```python
# Typical calculation: front month vs 12-month out
front_back_spread = front_price - back_12m_price

# Percentage version
spread_pct = (front_back_spread / front_price) * 100
```

### 3. Roll Yield

```python
# Monthly roll yield
roll_yield = (front_price - next_month_price) / front_price * 12

# Annualized: multiply by periods per year
annualized_roll = roll_yield * 12
```

### 4. Curve Shape Classification

| Shape | Description | Signal |
|-------|-------------|--------|
| Strong Contango | >$2/bbl spread | Very bearish |
| Mild Contango | $0.50-$2 spread | Bearish |
| Flat | -$0.50 to +$0.50 | Neutral |
| Mild Backwardation | -$2 to -$0.50 | Bullish |
| Strong Backwardation | <-$2/bbl | Very bullish |

## Implementation Strategy

### MVP (Phase 18)

**Approach:** Use yfinance CL=F + historical trend analysis

Since we only have front month, we can:
1. Track week-over-week price momentum
2. Compare to historical seasonal patterns
3. Use EIA inventory data as proxy for term structure direction
4. Cross-reference with CFTC positioning (Phase 17)

**Output Series:**
- `wti_term_structure_signal`: CONTANGO/BACKWARDATION/FLAT
- `wti_front_price`: Current front month price
- `wti_price_momentum`: 5-day change %
- `wti_roll_yield_proxy`: Estimated from historical patterns

### Future Enhancement (Post-MVP)

Add CME scraper for full curve:
- All 6 front contracts
- True calendar spreads
- Precise roll yield calculation
- Time spread analysis

## Codebase Patterns

### BaseCollector Integration

```python
# From src/liquidity/collectors/base.py
class TermStructureCollector(BaseCollector):
    def __init__(self):
        super().__init__(
            name="term_structure",
            source="yfinance",
            frequency="daily"
        )
```

### CommodityCollector Reference

Existing pattern in `src/liquidity/collectors/commodities.py`:
- Uses `yf.download()` with retry logic
- Standard OHLCV normalization
- Handles missing data gracefully

### Data Validation

From existing collectors:
- Price range validation: $20-$200/barrel
- Freshness check: data < 5 days old
- Missing data handling: forward fill with limit

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| yfinance contract roll gaps | Minor price discontinuities | Use adjusted close, validate vs FRED spot |
| No true term structure | Reduced accuracy | Combine with EIA inventory, CFTC data |
| CME data changes | Scraper breaks | Multiple fallbacks, monitoring |

## References

- CME WTI Specifications: https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.html
- yfinance Documentation: https://github.com/ranaroussi/yfinance
- EIA Short-Term Energy Outlook: https://www.eia.gov/outlooks/steo/

---
*Research completed: 2026-02-06*
