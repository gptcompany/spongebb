# Phase 17: CFTC Positioning - Research

## Executive Summary

La CFTC pubblica i **Commitment of Traders (COT) reports** ogni venerdì alle 15:30 ET con dati riferiti al martedì precedente. I dati sono disponibili via **Socrata Open Data API (SODA)** senza autenticazione richiesta.

## Data Sources

### Primary: CFTC Socrata API

**Endpoint Disaggregated Futures Only:**
```
https://publicreporting.cftc.gov/resource/72hh-3qpy.json
```

**Caratteristiche:**
- **Autenticazione**: Non richiesta (pubblico)
- **Rate Limit**: Non specificato, ma nessun problema rilevato
- **Formato**: JSON (default) o CSV
- **Storico**: Dal 2006-06-13
- **Aggiornamento**: Weekly (venerdì 15:30 ET, dati del martedì)

**Query Parameters (SoQL):**
- `$where`: Filtri (e.g., `cftc_commodity_code = '067'`)
- `$order`: Sorting (e.g., `report_date_as_yyyy_mm_dd DESC`)
- `$limit`: Max records (default 1000)
- `$offset`: Pagination

### Fallback: cot_reports Library

Libreria Python per download bulk da CFTC Historical Compressed files.

```python
pip install cot-reports
```

```python
import cot_reports as cot
df = cot.cot_all(cot_report_type='disaggregated_fut')
```

**Pro:** Storico completo, offline processing
**Contro:** Bulk download, no incremental updates

## Key Commodity Codes

| Commodity | CFTC Code | Contract | Exchange |
|-----------|-----------|----------|----------|
| **WTI Crude Oil** | 067 | CRUDE OIL, LIGHT SWEET-WTI | NYME |
| **Gold** | 088 | GOLD | CMX |
| **Copper** | 085 | COPPER- #1 | CMX |
| **Silver** | 084 | SILVER | CMX |
| **Natural Gas** | 023 | NATURAL GAS | NYME |
| Corn | 002 | CORN | CBT |
| Wheat | 001 | WHEAT-SRW | CBT |
| Soybeans | 005 | SOYBEANS | CBT |

## Field Mapping (Disaggregated Report)

### Core Fields

| Field | Description |
|-------|-------------|
| `id` | Unique record ID |
| `report_date_as_yyyy_mm_dd` | Report date (timestamp) |
| `cftc_commodity_code` | Commodity code (e.g., "067") |
| `commodity_name` | Commodity name |
| `contract_market_name` | Contract name |
| `cftc_market_code` | Exchange code (NYME, CMX, CBT) |
| `open_interest_all` | Total open interest |

### Position Fields (Disaggregated Categories)

**Producer/Merchant (Commercials):**
- `prod_merc_positions_long` - Commercial Long
- `prod_merc_positions_short` - Commercial Short

**Swap Dealers:**
- `swap_positions_long_all` - Swap Long
- `swap__positions_short_all` - Swap Short (nota: doppio underscore)
- `swap__positions_spread_all` - Swap Spread

**Managed Money (Speculators):**
- `m_money_positions_long_all` - Speculator Long
- `m_money_positions_short_all` - Speculator Short
- `m_money_positions_spread` - Speculator Spread

**Other Reportables:**
- `other_rept_positions_long` - Other Long
- `other_rept_positions_short` - Other Short
- `other_rept_positions_spread` - Other Spread

**Non-Reportables:**
- `nonrept_positions_long_all` - Non-Reportable Long
- `nonrept_positions_short_all` - Non-Reportable Short

### Change Fields

- `change_in_prod_merc_long`, `change_in_prod_merc_short`
- `change_in_m_money_long_all`, `change_in_m_money_short_all`
- `change_in_swap_long_all`, `change_in_swap_short_all`

### Percentage of OI Fields

- `pct_of_oi_prod_merc_long`, `pct_of_oi_prod_merc_short`
- `pct_of_oi_m_money_long_all`, `pct_of_oi_m_money_short_all`
- `pct_of_oi_swap_long_all`, `pct_of_oi_swap_short_all`

## API Query Examples

### Fetch Latest WTI Crude Data

```bash
curl -s "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?\
\$where=cftc_commodity_code='067' AND contract_market_name like '%WTI%'&\
\$order=report_date_as_yyyy_mm_dd DESC&\
\$limit=10"
```

### Fetch Multi-Commodity Last 52 Weeks

```bash
curl -s "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?\
\$where=cftc_commodity_code in ('067','088','085')&\
\$order=report_date_as_yyyy_mm_dd DESC&\
\$limit=156"  # 52 weeks x 3 commodities
```

### Filter by Date Range

```bash
curl -s "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?\
\$where=report_date_as_yyyy_mm_dd >= '2025-01-01'&\
\$limit=1000"
```

## Positioning Metrics Design

### Net Positioning

```python
# Commercial Net = Long - Short
commercial_net = prod_merc_positions_long - prod_merc_positions_short

# Speculator Net = Long - Short
speculator_net = m_money_positions_long_all - m_money_positions_short_all

# Swap Dealer Net
swap_net = swap_positions_long_all - swap__positions_short_all
```

### Positioning Ratios

```python
# Commercial/Speculator Ratio
comm_spec_ratio = commercial_net / speculator_net

# Long/Short Ratio (by category)
mm_long_short_ratio = m_money_positions_long_all / m_money_positions_short_all
```

### Extreme Detection (Percentile)

```python
# Calculate percentile rank over N weeks (e.g., 52 or 156)
def positioning_percentile(current_net, historical_net):
    return scipy.stats.percentileofscore(historical_net, current_net)

# Extreme thresholds
EXTREME_BULLISH = 90  # Top 10%
EXTREME_BEARISH = 10  # Bottom 10%
```

## Integration with Liquidity Framework

### Signals

1. **Extreme Speculator Long** (>90th percentile): Potential reversal risk
2. **Extreme Commercial Short** (>90th percentile): Smart money hedging, bearish
3. **Commercial/Spec Divergence**: When commercials and specs on opposite sides

### Dashboard Integration

- **Heatmap**: Net positioning by commodity (green=long, red=short)
- **Time Series**: Historical net positions with regime overlay
- **Extremes Table**: Current percentile ranks with alerts

## Implementation Pattern

```python
class CFTCCOTCollector(BaseCollector[pd.DataFrame]):
    """CFTC Commitment of Traders collector via Socrata API."""

    BASE_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"

    # Key commodities for liquidity analysis
    COMMODITY_MAP = {
        "WTI": {"code": "067", "contract": "CRUDE OIL, LIGHT SWEET-WTI"},
        "GOLD": {"code": "088", "contract": "GOLD"},
        "COPPER": {"code": "085", "contract": "COPPER- #1"},
        "SILVER": {"code": "084", "contract": "SILVER"},
        "NATGAS": {"code": "023", "contract": "NATURAL GAS"},
    }

    async def collect(
        self,
        commodities: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        weeks: int = 52,
    ) -> pd.DataFrame:
        """Fetch COT positioning data."""
        ...
```

## Output Schema

```python
# Standard output format
columns = [
    "timestamp",        # Report date
    "commodity",        # WTI, GOLD, COPPER, etc.
    "series_id",        # e.g., "cot_wti_comm_net"
    "source",           # "cftc"
    "value",            # Numeric value
    "unit",             # "contracts" or "percent"
]

# Derived series IDs
series_patterns = [
    "{commodity}_comm_net",      # Commercial net position
    "{commodity}_spec_net",      # Speculator (managed money) net
    "{commodity}_swap_net",      # Swap dealer net
    "{commodity}_comm_pct",      # Commercial as % of OI
    "{commodity}_spec_pct",      # Speculator as % of OI
    "{commodity}_oi",            # Open interest
]
```

## Sources

- [CFTC COT Reports](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)
- [CFTC Public Reporting Portal](https://publicreporting.cftc.gov/stories/s/Commitments-of-Traders/r4w3-av2u/)
- [Socrata API Documentation](https://dev.socrata.com/docs/endpoints.html)
- [Disaggregated Futures Dataset](https://publicreporting.cftc.gov/Commitments-of-Traders/Disaggregated-Futures-Only/72hh-3qpy)
- [cot_reports Python Library](https://github.com/NDelventhal/cot_reports)

---
*Research completed: 2026-02-06*
*Data verified via live API queries*
