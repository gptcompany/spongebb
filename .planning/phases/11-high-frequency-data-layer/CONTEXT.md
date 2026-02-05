# Context: Phase 11 - High-Frequency Data Layer

**Created**: 2026-02-05
**Phase**: 11
**Status**: Ready for Planning

## Phase Goal

Reduce data lag from weekly to daily by adding high-frequency data sources. Currently the Net Liquidity calculation uses weekly FRED data (WTREGEN/WDTGAL), while Bloomberg users have daily/real-time access. This phase closes that gap.

## What We're Building

### 1. TGA Daily Collector (Plan 11-01)
- **Current**: Weekly WDTGAL from FRED (7-day lag)
- **Target**: Daily from US Treasury FiscalData API (same-day by 4PM ET)
- **Impact**: Net Liquidity calculation accuracy improves significantly

### 2. NY Fed Collectors (Plan 11-02)
- **RRP Daily**: Currently WLRRAL weekly, need same-day RRP operations
- **SOMA Holdings**: Fed portfolio composition (useful for QT tracking)
- **Swap Lines**: CB liquidity swap usage (stress indicator)
- **Impact**: Hayes formula with same-day RRP data

### 3. China HF Proxies (Plan 11-03)
- **Problem**: PBoC data has 1-month lag (official balance sheet)
- **Solution**: Use SHIBOR/DR007 as daily proxies for PBoC policy stance
- **Library**: akshare (15k+ stars, well-maintained)
- **Impact**: PBoC nowcasting for Global Liquidity Index

### 4. Cross-Currency Basis (Plan 11-04)
- **What**: EUR/USD basis swap spread
- **Why**: Post-LIBOR stress indicator (shows USD funding stress globally)
- **Threshold**: < -30bps = severe stress
- **Source**: ECB SDW or CME Index

### 5. Stablecoin Supply (Plan 11-05)
- **What**: USDT, USDC, DAI total market cap (~$200B+)
- **Why**: Crypto liquidity proxy, alternative to traditional banking
- **Source**: DefiLlama API (free, no auth)
- **Impact**: Crypto market sentiment indicator

### 6. Consumer Credit Proxies (Plan 11-06)
- **What**: FRED consumer series (RSAFS, UMCSENT, TOTALSL)
- **Why**: Economic signal enrichment
- **Already Have**: FREDCollector can fetch these directly
- **Impact**: Consumer spending sentiment

## Existing Codebase Context

### Collector Pattern
All collectors extend `BaseCollector[pd.DataFrame]`:
- Use `fetch_with_retry()` for resilience (retry + circuit breaker)
- Output normalized DataFrame: `timestamp, series_id, source, value, unit`
- Register with `registry.register("name", CollectorClass)`

### Key Files
- `src/liquidity/collectors/base.py` - Base class with retry/CB
- `src/liquidity/collectors/fred.py` - Reference implementation
- `src/liquidity/collectors/registry.py` - Collector registry
- `src/liquidity/config.py` - Settings (pydantic-settings)

### Current FREDCollector
Already has Hayes formula series:
- `WALCL` (Fed Total Assets, weekly, millions USD)
- `WLRRAL` (RRP, weekly, billions USD)
- `WDTGAL` (TGA, weekly, billions USD)

### Net Liquidity Calculation
```python
# src/liquidity/collectors/fred.py
net_liquidity = WALCL - (WLRRAL * 1000) - (WDTGAL * 1000)
# All converted to millions USD
```

## Integration Points

### Dashboard
- `src/liquidity/dashboard/` - Plotly Dash
- Add China rates panel
- Add stablecoin panel
- Stress indicators panel already exists (add xccy basis)

### API
- `src/liquidity/api/` - FastAPI
- New endpoints needed:
  - `/tga/daily` - TGA daily data
  - `/china/rates` - SHIBOR/DR007
  - `/stablecoins` - Market cap
  - `/stress/xccy-basis` - Cross-currency basis

### Calculations
- `src/liquidity/calculations/` - Net Liquidity, Global Liquidity, Stealth QE
- Update `calculate_net_liquidity()` to use daily TGA
- Update `calculate_global_liquidity()` to use China proxies

## Dependencies to Add

```toml
# pyproject.toml
dependencies = [
    # ... existing ...
    "akshare>=1.18.0",   # China financial data (SHIBOR, DR007)
]
```

Note: DefiLlama doesn't need a pip package - just httpx requests to their API.

## Technical Decisions

### Q1: How to handle TGA daily vs weekly?
**Decision**: Prefer daily, fallback to weekly. In calculations, use daily TGA when available, interpolate or forward-fill for alignment with weekly WALCL/WLRRAL.

### Q2: akshare threading?
**Decision**: akshare is sync, use `asyncio.to_thread()` like we do with OpenBB.

### Q3: Cross-currency basis source?
**Decision**: Try ECB SDW first (free), fall back to CME if available. If neither works, use FRED proxy if one exists.

### Q4: Stablecoin update frequency?
**Decision**: Daily is sufficient. DefiLlama provides real-time but daily refresh is enough for macro analysis.

## Wave Structure

### Wave 1 (Parallel)
- 11-01: TGA Daily
- 11-02: NY Fed (RRP, SOMA, Swap Lines)
- 11-03: China HF Proxies

### Wave 2 (Parallel)
- 11-04: Cross-Currency Basis
- 11-05: Stablecoins
- 11-06: Consumer Credit

## Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| TGA data freshness | 7 days | 1 day |
| RRP data freshness | 7 days | Same-day |
| China proxy coverage | None | Daily SHIBOR/DR007 |
| Stress indicators | SOFR-OIS only | + Cross-currency basis |
| Crypto liquidity | None | Stablecoin market cap |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| FiscalData API downtime | High | Fallback to FRED weekly |
| akshare API changes | Medium | Pin version, add tests |
| ECB SDW complexity | Medium | SDMX parsing, fallback to CME |
| DefiLlama rate limits | Low | Cache responses, daily refresh |

## References

- Research: `RESEARCH.md` (in this directory)
- Phase spec: `.planning/phases/phase-11.md`
- REQUIREMENTS.md: HF-01 through HF-06
