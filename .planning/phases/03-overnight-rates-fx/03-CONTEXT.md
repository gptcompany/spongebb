# Phase 3: Overnight Rates & FX - Context

**Gathered:** 2026-01-22
**Status:** Ready for planning

<vision>
## How This Should Work

Overnight rates and FX data serve **two equal purposes** in the liquidity system:

1. **Carry Trade Signals** — Where is capital flowing based on rate advantage?
   - Rate differentials (SOFR vs €STR/SONIA/CORRA) show the *cause* — why money moves
   - DXY shows the *effect* — where it ended up
   - Major pairs (EUR/USD, USD/JPY, GBP/USD) provide granular analysis

2. **Funding Stress Monitoring** — Early warning for liquidity issues
   - SOFR spikes above Fed target = classic stress signal
   - Cross-currency divergence = unusual capital flows
   - Historical deviation (2+ std dev) = something abnormal happening

The data feeds into regime classification (Phase 8) as a stress signal while also being visible separately in dashboards for maximum insight.

</vision>

<essential>
## What Must Be Nailed

All three equally important:

- **Reliable daily collection** — SOFR, €STR, SONIA, CORRA with robust fallbacks when primary sources fail
- **Pre-calculated differentials** — Spreads ready for regime analysis (e.g., SOFR-€STR spread)
- **FX integration** — DXY and major pairs feeding into the liquidity picture

</essential>

<specifics>
## Specific Ideas

**Data Sources:** Use most reliable authoritative sources:
- SOFR: NY Fed (authoritative)
- €STR: ECB (authoritative, T+1)
- SONIA: BoE
- CORRA: BoC

**FX Coverage:**
- DXY (Dollar Index)
- Major pairs: EUR/USD, USD/JPY, GBP/USD, USD/CHF, USD/CAD
- CNY (aligns with PBoC tracking)
- AUD (commodity currency, risk-on/risk-off signal)
- IMF COFER (quarterly — reserve currency composition shifts)

**Timing:** Use most recent available data with clear timestamp labeling. T+1 acceptable for macro analysis.

**Stress Indicators (for Phase 5 integration):**
- Rate spikes above target
- Cross-currency divergence
- Historical deviation bands

</specifics>

<notes>
## Additional Context

**Gaps addressed in discussion:**
- Different CBs publish at different times → use date alignment, label timestamps
- Weekend/holiday gaps → inherent to the data, handle gracefully
- DXY sources vary → pick most reliable (will research during planning)

**Scope decisions:**
- Include CNY (PBoC already tracked) and AUD (useful risk signal)
- IMF COFER included despite quarterly frequency (structural insights)
- Individual pairs included for granular analysis beyond DXY summary

**Integration:**
- Data feeds into regime classifier (Phase 8) as stress signal
- Also shown separately in dashboards for direct visibility

</notes>

---

*Phase: 03-overnight-rates-fx*
*Context gathered: 2026-01-22*
