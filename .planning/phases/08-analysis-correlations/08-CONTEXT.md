# Phase 8: Analysis & Correlations - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning

<vision>
## How This Should Work

Phase 8 is the **alpha generator**. Phases 1-7 collected data. Phase 8 converts data into **actionable trading intelligence**.

The system should tell me two things instantly:
1. **Regime** — Are we in expansion or contraction? How strong?
2. **Correlations** — What's moving together NOW, and when does that break?

When I pull up the regime, I want a clear EXPANSION/CONTRACTION call with an intensity score (0-100). No hiding behind "neutral" — the market is always doing something, give me the direction and confidence level.

When I look at correlations, I want to see what's correlated to liquidity RIGHT NOW (not 90 days ago). I need to catch correlation breakdowns fast — when BTC stops tracking liquidity, that's a signal.

</vision>

<essential>
## What Must Be Nailed

- **Multi-factor regime scoring** — Don't rely on single metric. Combine Net Liquidity + Global Liquidity + Stealth QE Score into one regime call. Single metric misses stealth QE episodes.

- **Binary + intensity model** — Expansion or Contraction, period. Plus intensity 0-100 for confidence. "Neutral" is cop-out that masks low conviction.

- **Fast correlation updates** — EWMA with 21d half-life on top of standard 30d/90d windows. Catch breakdowns before they become obvious.

- **Full macro correlation basket** — BTC, SPX, Gold, TLT, DXY, Copper, HYG. DXY-liquidity correlation is core Hayes thesis. Missing it = missing the trade.

- **Alert on regime correlation shifts** — >0.3 change in correlation AND 2σ deviation from rolling mean. Both absolute and statistical thresholds.

</essential>

<specifics>
## Specific Ideas

**Regime Classifier:**
- Inputs: Net Liquidity Index, Global Liquidity Index, Stealth QE Score
- Output: `{direction: "EXPANSION"|"CONTRACTION", intensity: 0-100, confidence: "HIGH"|"MEDIUM"|"LOW"}`
- Use rolling percentiles (90d) for context, not fixed thresholds
- Rate of change matters more than absolute level

**Correlation Engine:**
- Assets: BTC, SPX, Gold/XAU, TLT (bonds), DXY, Copper (Dr. Copper), HYG (credit risk)
- Windows: 30d rolling, 90d rolling, EWMA (halflife=21)
- Output: correlation matrix + rolling history
- Store in QuestDB for dashboard access

**Alert Engine:**
- Trigger on >0.3 correlation change (any window)
- Trigger on >2σ deviation from 90d rolling mean
- Prepare alert payload for Discord (Phase 10)

**Implementation:**
- `src/liquidity/analyzers/regime_classifier.py`
- `src/liquidity/analyzers/correlation_engine.py`
- `src/liquidity/analyzers/alert_engine.py`
- Follow existing pattern (BaseCollector style, async, purgatory circuit breaker)

</specifics>

<notes>
## Additional Context

**Decisions made (autonomous, with SWOT analysis):**

| Question | Decision | Rationale |
|----------|----------|-----------|
| Regime logic | Multi-factor scoring | Single metric misses stealth QE |
| Correlation windows | Fixed + EWMA | EWMA catches breakdowns faster |
| Asset basket | Full macro (7 assets) | DXY, HYG critical for thesis |
| Alert threshold | 0.3 + 2σ statistical | Both absolute and relative anomalies |
| Regime states | Binary + intensity | Forces view, no neutral cop-out |
| Implementation | Separate classes | Matches codebase pattern, testable |

**Requirements covered:**
- ANLYS-01: Regime classifier
- CORR-01: BTC/Net Liquidity correlation
- CORR-02: SPX/Global Liquidity correlation
- CORR-03: Gold/Real Rates correlation
- CORR-04: Correlation heatmap
- CORR-05: Regime shift alerts (>0.3 change)

**Open items for planning:**
- Weight tuning for multi-factor regime score
- EWMA half-life optimization (starting at 21)
- QuestDB schema for correlation time series

</notes>

---

*Phase: 08-analysis-correlations*
*Context gathered: 2026-01-26*
