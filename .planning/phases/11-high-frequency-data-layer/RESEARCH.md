# Research: Phase 11 - High-Frequency Data Layer

**Research Date**: 2026-02-05
**Status**: Complete

## 1. US Treasury FiscalData API (TGA Daily)

### API Details

- **Base URL**: `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/`
- **Endpoint**: `v1/accounting/dts/operating_cash_balance`
- **Auth**: None required (open API)
- **Update Frequency**: Daily by 4PM ET
- **Data Range**: 2005-10-03 to present

### Request Format

```python
# Example request
import requests

params = {
    "fields": "record_date,account_type,close_today_bal",
    "filter": "account_type:eq:Treasury General Account (TGA),record_date:gte:2024-01-01",
    "sort": "-record_date",
    "page[size]": 100,
    "format": "json"
}
response = requests.get(
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance",
    params=params
)
```

### Response Structure

```json
{
  "data": [
    {
      "record_date": "2026-02-04",
      "account_type": "Treasury General Account (TGA)",
      "open_today_bal": "832541",
      "open_month_bal": "714000",
      "open_fiscal_year_bal": "715234",
      "close_today_bal": "845123"  // Note: null after 2022-04-18, use account_type filter
    }
  ],
  "meta": {
    "count": 100,
    "total-count": 5000,
    "total-pages": 50
  },
  "links": {
    "self": "...",
    "next": "..."
  }
}
```

### Important Notes

1. **Post April 18, 2022**: `close_today_bal` column is null. Use `account_type:eq:Treasury General Account (TGA)` filter and read from opening balance columns
2. **Filter Syntax**: Uses colon-separated operators (`eq`, `gte`, `lt`, `in`)
3. **Pagination**: Use `page[number]` and `page[size]` parameters

### Fallback Strategy

FRED series `WTREGEN` (weekly) as backup if DTS API fails.

---

## 2. NY Fed Markets API (RRP, SOMA, Swap Lines)

### API Details

- **Base URL**: `https://markets.newyorkfed.org/api`
- **Auth**: None required
- **Format**: JSON

### Endpoints

#### RRP Operations (Daily)

```python
# All RRP operations - last two weeks
url = "https://markets.newyorkfed.org/api/rp/all/all/results/lastTwoWeeks.json"

# RRP operations - specific date range
url = "https://markets.newyorkfed.org/api/rp/all/all/results/search.json?startDate=2026-01-01&endDate=2026-02-05"
```

Response structure:
```json
{
  "repo": {
    "operations": [
      {
        "operationDate": "2026-02-04",
        "operationType": "Overnight Reverse Repo",
        "totalAmtSubmitted": 1500000000000,
        "totalAmtAccepted": 1500000000000,
        "awardRate": 4.55,
        "settlementDate": "2026-02-04"
      }
    ]
  }
}
```

#### SOMA Holdings (Weekly)

```python
# SOMA summary
url = "https://markets.newyorkfed.org/api/soma/summary.json"

# SOMA by security type
url = "https://markets.newyorkfed.org/api/soma/asofdates/latest.json"
```

#### Central Bank Liquidity Swaps

```python
# Swap line operations
url = "https://markets.newyorkfed.org/api/fxs/all/results/latest.json"
```

### Available Partners (5 Major)

| Central Bank | Currency | Line Size |
|--------------|----------|-----------|
| ECB | EUR | Unlimited |
| BoJ | JPY | Unlimited |
| BoE | GBP | Unlimited |
| SNB | CHF | Unlimited |
| BoC | CAD | Unlimited |

---

## 3. akshare Library (SHIBOR, DR007)

### Installation

```bash
pip install akshare>=1.18.0
```

### SHIBOR Functions

```python
import akshare as ak

# SHIBOR all tenors (O/N to 1Y)
shibor_df = ak.macro_china_shibor_all()
# Columns: 日期, O/N-定价, O/N-涨跌幅, 1W-定价, 1W-涨跌幅, ...

# SHIBOR LPR (Loan Prime Rate)
lpr_df = ak.macro_china_lpr()
```

### DR007 Function

```python
# DR007 - 7-day repo rate for depositary institutions
# This is the PBoC's de-facto policy rate target

# Option 1: Direct interbank rate
interbank_df = ak.rate_interbank()  # Includes DR007

# Option 2: Macro series
# Note: Function name may vary by akshare version
# Check ak.macro_china_* namespace
```

### Data Frequency

- SHIBOR: Daily (trading days)
- DR007: Daily (trading days)
- LPR: Monthly (20th of each month)

### Historical Range

Data available from ~2015 to present.

---

## 4. Cross-Currency Basis (EUR/USD)

### Data Sources

#### Option 1: ECB SDW (Recommended - Free)

ECB Statistical Data Warehouse provides EUR/USD basis swap quotes.

```python
# ECB SDMX REST API
base_url = "https://data-api.ecb.europa.eu/service/data"
# Series: FM.M.U2.EUR.4F.BB.US_FX_EUR_M_3M.HSTA

# Note: Monthly data, requires SDMX parsing
```

#### Option 2: FRED (3-month basis)

```python
# EUR/USD 3-month cross-currency basis swap
# Series: EURUSCCBS (if available)
```

#### Option 3: CME Index (Official but may require subscription)

CME EUR/USD Cross Currency Basis Index:
- URL: https://www.cmegroup.com/market-data/cme-group-benchmark-administration/eur-usd-cross-currency-basis-index.html
- Update: Daily
- Note: May require CME DataMine subscription for API access

### Interpretation

| Basis Level | Signal |
|-------------|--------|
| > 0 bps | Normal (USD discount) |
| -10 to 0 bps | Mild stress |
| -30 to -10 bps | Moderate stress |
| < -30 bps | Severe USD funding stress |

### Fallback Strategy

1. Try ECB SDW API
2. Fall back to FRED proxy (if available)
3. Cache last known value (max 7 days stale)

---

## 5. DefiLlama API (Stablecoins)

### API Details

- **Base URL**: `https://stablecoins.llama.fi`
- **Auth**: None required
- **Rate Limit**: Fair use (no hard limit documented)

### Endpoints

#### All Stablecoins

```python
url = "https://stablecoins.llama.fi/stablecoins"
```

Response:
```json
{
  "peggedAssets": [
    {
      "id": "1",
      "name": "Tether",
      "symbol": "USDT",
      "gecko_id": "tether",
      "pegType": "peggedUSD",
      "pegMechanism": "fiat-backed",
      "circulating": {
        "peggedUSD": 143000000000
      },
      "chainCirculating": {
        "Ethereum": {"current": {"peggedUSD": 65000000000}},
        "Tron": {"current": {"peggedUSD": 60000000000}}
      }
    }
  ]
}
```

#### Single Stablecoin Details

```python
url = "https://stablecoins.llama.fi/stablecoin/tether"  # by name
url = "https://stablecoins.llama.fi/stablecoin/1"       # by ID
```

#### Historical Market Cap

```python
url = "https://stablecoins.llama.fi/stablecoincharts/all"
```

### Top Stablecoins to Track

| Rank | Symbol | Type | Market Cap (Jan 2026) |
|------|--------|------|----------------------|
| 1 | USDT | Fiat-backed | ~$143B |
| 2 | USDC | Fiat-backed | ~$55B |
| 3 | DAI | Crypto-backed | ~$5B |
| 4 | FDUSD | Fiat-backed | ~$3B |
| 5 | USDe | Algo/Derivative | ~$6B |

### Python Wrapper

```bash
pip install defillama
```

```python
from defillama import DefiLlama

client = DefiLlama()
stablecoins = client.get_stablecoins()
```

---

## 6. FRED Consumer Series (Credit Proxies)

### Recommended Series

| Series ID | Name | Frequency | Use Case |
|-----------|------|-----------|----------|
| RSAFS | Retail Sales: Total | Monthly | Consumer spending |
| RRSFS | Retail Sales: ex Autos | Monthly | Core spending |
| UMCSENT | Consumer Sentiment | Monthly | Forward indicator |
| TOTALSL | Consumer Credit | Monthly | Credit usage |
| PCE | Personal Consumption | Monthly | GDP component |
| CCLACBW027SBOG | Credit Card Loans | Weekly | Real-time proxy |

### Weekly Series (Higher Frequency)

```python
# Credit card loans at commercial banks (weekly)
series_id = "CCLACBW027SBOG"

# Consumer loans at commercial banks (weekly)
series_id = "CLSACBW027SBOG"
```

### Already Available via FREDCollector

These series can be fetched using the existing `FREDCollector` base class from Phase 1.

---

## Implementation Recommendations

### Priority Order

1. **11-01 TGA Daily** - Immediate improvement to Net Liquidity accuracy
2. **11-02 NY Fed** - Same-day RRP data, critical for Hayes formula
3. **11-03 China HF** - Fill PBoC data gap with proxies
4. **11-04 X-Ccy Basis** - Post-LIBOR stress indicator
5. **11-05 Stablecoins** - Crypto liquidity proxy
6. **11-06 Consumer** - Economic signal enrichment

### Dependencies to Add

```toml
# pyproject.toml
dependencies = [
    "akshare>=1.18.0",   # China financial data
    "defillama>=1.0.0",  # Stablecoin API wrapper (optional)
]
```

### Error Handling Pattern

```python
async def collect_with_fallback(primary_fn, fallback_fn, max_stale_days=7):
    """Standard pattern for all HF collectors."""
    try:
        data = await primary_fn()
        if data is not None and len(data) > 0:
            return data
    except Exception as e:
        logger.warning(f"Primary source failed: {e}")

    # Try fallback
    try:
        data = await fallback_fn()
        return data
    except Exception as e:
        logger.error(f"Fallback also failed: {e}")

    # Return cached if within staleness window
    return await get_cached_if_fresh(max_stale_days)
```

---

## Sources

- [US Treasury FiscalData API](https://fiscaldata.treasury.gov/api-documentation/)
- [Daily Treasury Statement Dataset](https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/)
- [NY Fed Markets Data APIs](https://markets.newyorkfed.org/static/docs/markets-api.html)
- [NY Fed Reverse Repo Operations](https://www.newyorkfed.org/markets/desk-operations/reverse-repo)
- [NY Fed SOMA Holdings](https://www.newyorkfed.org/markets/soma-holdings)
- [akshare GitHub](https://github.com/akfamily/akshare)
- [akshare Documentation](https://akshare.akfamily.xyz/)
- [DefiLlama API Docs](https://api-docs.defillama.com/)
- [DefiLlama Stablecoins](https://defillama.com/stablecoins)
- [CME EUR/USD Basis Index](https://www.cmegroup.com/market-data/cme-group-benchmark-administration/eur-usd-cross-currency-basis-index.html)
- [ECB Data Portal API](https://data.ecb.europa.eu/help/api/data)
