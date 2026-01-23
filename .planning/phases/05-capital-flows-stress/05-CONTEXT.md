# Phase 5: Capital Flows & Stress - Context

**Gathered:** 2026-01-23
**Status:** Ready for planning

<vision>
## How This Should Work

Complete picture of where money is moving AND when the plumbing is under stress. Flows show direction - foreign buying/selling via TIC data, ETF flows showing risk-on/risk-off sentiment. Stress indicators show when things are breaking - SOFR-OIS widening, cross-currency basis blowing out, repo stress building.

The combination provides both context (flows) and early warning (stress). Foreign flows move slowly but massively. Stress indicators can flash quickly before markets react.

</vision>

<essential>
## What Must Be Nailed

- **Foreign flows (TIC data)** - Know when foreign central banks/investors are buying or selling US Treasuries
- **Funding stress indicators** - SOFR-OIS spread, cross-currency basis, repo stress signals
- **ETF flows** - SPY, TLT, HYG, GLD flows show real-time risk sentiment shifts
- **All are critical** - Each tells a different part of the story

</essential>

<specifics>
## Specific Ideas

No specific thresholds or data sources required - figure out sensible defaults based on research.

Reference the Apps Script v3.4.1 for any existing logic, but don't be constrained by it.

</specifics>

<notes>
## Additional Context

This phase bridges data collection (Phases 1-4) and analysis (Phases 7-8). The indicators collected here feed directly into the Stealth QE Score and regime classification.

TIC data is monthly (Treasury releases ~6 weeks after month-end), so this provides long-term flow context rather than real-time signals. Stress indicators can be daily/intraday for faster signals.

</notes>

---

*Phase: 05-capital-flows-stress*
*Context gathered: 2026-01-23*
