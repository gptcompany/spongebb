# Phase 4: Market Indicators - Context

**Gathered:** 2026-01-23
**Status:** Ready for planning

<vision>
## How This Should Work

Standalone data collection for commodities and ETF flows. These are inputs for later analysis (Phase 8) — not trying to derive signals or correlations yet.

Collect everything reliably now. Let the analysis phase figure out what matters.

The commodities tracked are the "real economy" signals: gold and silver as safe havens, copper as economic health, oil as energy/inflation. ETF flows show where money is actually moving.

</vision>

<essential>
## What Must Be Nailed

- **Reliable daily spot prices** — Consistent, gap-free commodity prices every trading day
- **Accurate ETF flow data** — Precise shares outstanding / AUM changes to track real money movement
- **Both must work** — Can't have one without the other for meaningful later analysis

</essential>

<specifics>
## Specific Ideas

**Spot Prices:**
- Gold (XAU/USD), Silver (XAG/USD), Copper, WTI, Brent
- Mix of sources based on reliability (FRED, Yahoo, whatever works best per commodity)
- Forward fill for weekends/holidays (consistent with FX collectors)

**ETF Flows:**
- Broad coverage: GLD, SLV (precious metals), USO (oil), CPER (copper), DBA (agriculture)
- Track shares outstanding and/or AUM changes

**Oil Specifics:**
- Both WTI and Brent benchmarks
- Pre-calculate Brent-WTI spread as derived metric

**Derived Metrics:**
- Copper/Gold ratio (risk-on/risk-off indicator)
- Other ratios (Au/Ag, Oil/Au) deferred to Phase 8 analysis

</specifics>

<notes>
## Additional Context

MOVE and VIX already collected in Phase 1 via yahoo.py. Treasury yields and credit spreads also already covered via FRED.

This phase focuses specifically on commodities — the "real economy" indicators that complement the liquidity and volatility data.

No need for natural gas or platinum/palladium — the core commodities (gold, silver, copper, oil) plus the ETF flows cover the essential signals.

</notes>

---

*Phase: 04-market-indicators*
*Context gathered: 2026-01-23*
