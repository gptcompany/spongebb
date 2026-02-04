# Phase 11: High-Frequency Data Layer

## Overview

Reduce data lag from weekly to daily by adding high-frequency data sources that provide real-time or daily updates. This phase addresses the critical gap identified in the SWOT audit where we're using weekly FRED data while Bloomberg users have daily/real-time access.

## Goals

1. **TGA Daily**: Switch from weekly WTREGEN to daily DTS (Treasury FiscalData API)
2. **NY Fed APIs**: Add RRP daily details, SOMA holdings, CB swap line data
3. **China Proxies**: Implement DR007/SHIBOR for PBoC nowcasting via akshare
4. **Cross-Currency Basis**: Add EUR/USD basis as post-LIBOR stress indicator
5. **Stablecoins**: Track $310B+ stablecoin supply as crypto liquidity proxy
6. **Credit Proxies**: Consumer spending indicators for economic signals

## Dependencies

- Phase 10 (Visualization & Alerting) - Complete

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| HF-01 | TGA daily from DTS API (4PM ET updates) | HIGH |
| HF-02 | NY Fed RRP, SOMA, Swap Lines daily | HIGH |
| HF-03 | SHIBOR/DR007 via akshare library | HIGH |
| HF-04 | EUR/USD cross-currency basis (ECB/CME) | HIGH |
| HF-05 | Stablecoin supply via DefiLlama | MEDIUM |
| HF-06 | FRED consumer series for credit proxy | MEDIUM |

## Research Topics

1. **US Treasury FiscalData API**
   - Endpoint: https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/
   - Format: JSON, CSV, XML
   - Update: Daily by 4PM ET
   - No auth required

2. **NY Fed Markets API**
   - Endpoint: https://markets.newyorkfed.org/api/
   - Data: RRP operations, SOMA holdings, swap lines
   - Format: JSON
   - No auth required

3. **akshare Library**
   - GitHub: https://github.com/akfamily/akshare (15,986 stars)
   - Data: SHIBOR, DR007, PBoC operations
   - Install: `pip install akshare`
   - Functions: `ak.rate_interbank_shibor()`, `ak.repo_rate_hist()`

4. **Cross-Currency Basis**
   - ECB SDW: https://data.ecb.europa.eu/
   - CME Index: https://www.cmegroup.com/market-data/cme-group-benchmark-administration/eur-usd-cross-currency-basis-index.html
   - Paper: https://www.ecb.europa.eu/press/financial-stability-publications/fsr/focus/2011/pdf/ecb~938a721854.fsrbox201112_08.pdf

5. **DefiLlama API**
   - Endpoint: https://defillama.com/docs/api
   - Data: Stablecoin supply by chain, peg status
   - Format: JSON
   - No auth required
   - Python wrapper: `pip install DeFiLlama`

## Plans

### Plan 11-01: TGA Daily Collector
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Create collector for Daily Treasury Statement data from FiscalData API.

**Deliverables**:
- `src/liquidity/collectors/tga_daily.py`
- Tests in `tests/integration/test_tga_daily.py`
- Update dashboard to use daily TGA

**Acceptance Criteria**:
- [ ] Fetches TGA closing balance daily
- [ ] Parses DTS JSON format correctly
- [ ] Fallback to FRED weekly on API failure
- [ ] Updates Net Liquidity calculation with daily data

### Plan 11-02: NY Fed Collectors
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Add collectors for NY Fed Markets API endpoints.

**Deliverables**:
- `src/liquidity/collectors/nyfed.py` (RRP, SOMA)
- `src/liquidity/collectors/swap_lines.py`
- Tests in `tests/integration/test_nyfed.py`

**Acceptance Criteria**:
- [ ] RRP daily operations with counterparty breakdown
- [ ] SOMA holdings by security type
- [ ] CB swap line usage (5 major partners)
- [ ] Proper error handling for API downtime

### Plan 11-03: China HF Proxies
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Implement SHIBOR and DR007 collectors using akshare library.

**Deliverables**:
- `src/liquidity/collectors/china_rates.py`
- PBoC nowcasting logic integration
- Tests in `tests/integration/test_china_rates.py`

**Acceptance Criteria**:
- [ ] Daily SHIBOR (O/N, 1W, 2W, 1M, 3M)
- [ ] Daily DR007 (PBoC target rate)
- [ ] Historical data load (90 days)
- [ ] Correlation with official PBoC data

### Plan 11-04: Cross-Currency Basis Collector
**Wave**: 2 | **Effort**: L | **Priority**: HIGH

Add EUR/USD cross-currency basis as post-LIBOR stress indicator.

**Deliverables**:
- `src/liquidity/collectors/xccy_basis.py`
- Integration with stress panel
- Tests in `tests/integration/test_xccy_basis.py`

**Acceptance Criteria**:
- [ ] Daily EUR/USD basis from ECB or CME
- [ ] Historical series for trend analysis
- [ ] Stress threshold alerts (>-30bps = stress)
- [ ] Dashboard stress panel integration

### Plan 11-05: Stablecoin Supply Collector
**Wave**: 2 | **Effort**: M | **Priority**: MEDIUM

Track stablecoin market cap as crypto liquidity proxy.

**Deliverables**:
- `src/liquidity/collectors/stablecoins.py`
- New dashboard panel for crypto liquidity
- Tests in `tests/integration/test_stablecoins.py`

**Acceptance Criteria**:
- [ ] Total market cap (USDT, USDC, DAI, others)
- [ ] Supply by chain (ETH, TRX, SOL)
- [ ] Peg deviation tracking
- [ ] Exchange reserves metric

### Plan 11-06: Credit Card Proxy Collectors
**Wave**: 2 | **Effort**: M | **Priority**: MEDIUM

Add FRED consumer series as credit card spending proxies.

**Deliverables**:
- `src/liquidity/collectors/consumer_credit.py`
- Economic indicators dashboard section
- Tests in `tests/integration/test_consumer_credit.py`

**Acceptance Criteria**:
- [ ] Retail sales (RSAFS, RRSFS)
- [ ] Consumer confidence (UMCSENT)
- [ ] Consumer credit (TOTALSL)
- [ ] Personal consumption (PCE)

## Technical Notes

### New Dependencies

```toml
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "akshare>=1.10.0",  # China financial data
    "DeFiLlama>=1.0.0",  # Stablecoin data
]
```

### Configuration

```python
# config.py additions
class Settings(BaseSettings):
    # HF Data sources
    treasury_fiscaldata_base_url: str = "https://api.fiscaldata.treasury.gov"
    nyfed_markets_base_url: str = "https://markets.newyorkfed.org/api"
    defillama_base_url: str = "https://stablecoins.llama.fi"
```

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| TGA data lag | 7 days | 1 day |
| RRP data lag | 1 day | Same-day |
| China proxy availability | None | Daily |
| Cross-currency basis | None | Daily |
| Stablecoin tracking | None | Real-time |

## References

- US Treasury FiscalData: https://fiscaldata.treasury.gov/
- NY Fed Markets: https://markets.newyorkfed.org/
- akshare Documentation: https://akshare.akfamily.xyz/
- DefiLlama API: https://defillama.com/docs/api
- ECB SDW: https://data.ecb.europa.eu/
