# Plan 04-02 Summary: ETF Flows Collector

**Status:** Complete
**Completed:** 2026-01-23

## What Was Built

Created `ETFFlowCollector` for tracking commodity ETF shares outstanding and prices.

### Files Created/Modified
- `src/liquidity/collectors/etf_flows.py` - ETFFlowCollector implementation
- `tests/integration/test_etf_flows.py` - 16 tests (all passing)

### Features Implemented
1. **ETF Mapping**
   - GLD: SPDR Gold Shares (gold)
   - SLV: iShares Silver Trust (silver)
   - USO: United States Oil Fund (oil)
   - CPER: United States Copper Index Fund (copper)
   - DBA: Invesco DB Agriculture Fund (agriculture)

2. **Current Shares Outstanding**
   - `collect_current_shares()` - Fetches from `yf.Ticker().info`:
     - shares_outstanding
     - total_assets
     - nav_price
     - market_price

3. **Historical Prices**
   - `collect_historical_prices()` - Batch download for efficiency
   - Output: timestamp, etf, underlying, source, close, volume

4. **Flow Estimation**
   - `estimate_daily_flows()` - Calculates shares_change from historical data
   - Note: Full flow tracking requires persistence layer (QuestDB)

5. **Convenience Methods**
   - `collect_precious_metal_etfs()` - GLD, SLV only
   - `collect_all()` - All ETFs
   - `get_gld_holdings()` - Quick GLD snapshot

### Verification Results
```
Shares data: 5 ETFs
GLD shares: 260,300,000
Price history: 15 rows (5 ETFs × 3 days)
ETFs: ['CPER', 'DBA', 'GLD', 'SLV', 'USO']
```

### Tests
- 16 tests passing
- ETF mapping tests
- Output format tests (shares + prices)
- Flow estimation tests (single + multiple timestamps)
- Convenience method tests
- Registry integration test

## Design Decisions
- Separated shares outstanding (snapshot) from price history (time series)
- yfinance `.info` doesn't provide historical shares - flow tracking requires storing snapshots
- Forward fill for price gaps consistent with other collectors
- Used batch download for price history (single API call)

## Future Enhancements
- Store daily shares snapshots in QuestDB for true flow analysis
- Add premium/discount to NAV calculation
- Correlate with underlying commodity prices
