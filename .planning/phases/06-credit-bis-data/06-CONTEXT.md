# Phase 6: Credit & BIS Data - Context

**Gathered:** 2026-01-23
**Status:** Ready for research

<vision>
## How This Should Work

Credit markets and Eurodollar system tracking are BOTH essential for the complete liquidity picture. This phase adds the credit dimension that's missing from central bank balance sheets alone.

Three complementary data streams:
1. **Credit stress signals** - HY spreads, CP rates, issuance data showing real-time credit conditions
2. **Lending standards** - SLOOS survey data showing bank willingness to lend (leading indicator)
3. **Eurodollar system** - BIS international banking data tracking offshore USD liquidity (Hayes' key insight)

Together these feed into:
- Risk regime classification (credit stress = risk-off)
- Leading indicators (credit moves before equity)
- Complete Hayes picture (offshore USD as shadow liquidity)

</vision>

<essential>
## What Must Be Nailed

- **HY OAS spreads** - High-yield spreads are the clearest credit stress signal
- **SLOOS data** - Lending tightening precedes recessions
- **BIS Eurodollar data** - Offshore USD is the shadow liquidity Hayes emphasizes

All three are essential - can't prioritize one over another. Need complete credit picture.

</essential>

<specifics>
## Specific Ideas

No specific requirements - open to standard approaches for:
- Credit data sources (FRED, ICE BofA indices)
- SLOOS from Fed website
- BIS SDMX API for international banking statistics

</specifics>

<notes>
## Additional Context

This phase completes the "inputs" side of the liquidity system:
- Phases 1-5: Central bank balance sheets, rates, FX, flows
- Phase 6: Credit markets (the demand side of liquidity)
- Phase 7+: Calculations and analysis

Credit data is essential for regime classification - can't just look at supply (CB balance sheets) without demand (credit conditions).

</notes>

---

*Phase: 06-credit-bis-data*
*Context gathered: 2026-01-23*
