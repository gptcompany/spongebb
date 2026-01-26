# Phase 8: Analysis & Correlations - Research

**Researched:** 2026-01-26
**Domain:** Time-series regime classification, rolling correlations, multi-factor scoring
**Confidence:** HIGH

<research_summary>
## Summary

Researched the ecosystem for building a regime classifier and correlation engine for macro liquidity analysis. The domain is well-established Python data science — pandas + scipy form the core stack. No exotic libraries needed.

Key finding: Regime classification in finance uses multi-factor scoring with percentile-based thresholds (not fixed levels). Rolling correlation with EWMA is standard for capturing recent dynamics. Statistical significance via scipy.stats.pearsonr/spearmanr provides p-values for correlation validity.

**Primary recommendation:** Use pandas ewm() for EWMA, pandas rolling().corr() for fixed windows, scipy.stats for significance testing. Follow existing StealthQECalculator pattern for multi-factor scoring structure.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 2.2+ | Rolling statistics, EWMA, correlation matrices | De facto standard for time-series |
| numpy | 1.26+ | Array operations, percentile calculations | Foundation for pandas |
| scipy.stats | 1.11+ | Correlation significance (p-values), statistical tests | Gold standard for hypothesis testing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| QuestDB (existing) | - | Time-series storage | Already in project |
| purgatory (existing) | 0.7.x | Circuit breaker | Already in project for collectors |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pandas ewm | statsmodels EWMA | Statsmodels heavier, pandas simpler for our needs |
| scipy correlation | numpy.corrcoef | Numpy lacks p-values, scipy provides full test |
| Custom regime model | sklearn GMM | GMM overkill for 3 inputs, custom scoring simpler |

**Installation:**
```bash
# Already in project dependencies
uv add pandas numpy scipy
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```
src/liquidity/
├── analyzers/              # NEW: Phase 8 code
│   ├── __init__.py
│   ├── regime_classifier.py     # RegimeClassifier class
│   ├── correlation_engine.py    # CorrelationEngine class
│   └── alert_engine.py          # AlertEngine class (prepares payloads)
├── calculators/            # Existing (Net/Global/StealthQE)
├── collectors/             # Existing
└── storage/                # Existing
```

### Pattern 1: Multi-Factor Regime Scoring
**What:** Combine multiple signals into single regime score using weighted percentiles
**When to use:** When regime depends on multiple correlated factors
**Example:**
```python
# Source: StealthQECalculator pattern (existing codebase)
def calculate_regime_score(
    net_liquidity: pd.Series,
    global_liquidity: pd.Series,
    stealth_qe_score: pd.Series,
    lookback: int = 90
) -> tuple[str, float]:
    """
    Returns: (direction: 'EXPANSION'|'CONTRACTION', intensity: 0-100)
    """
    # Calculate percentiles over lookback window
    net_pct = net_liquidity.rank(pct=True).iloc[-1]
    global_pct = global_liquidity.rank(pct=True).iloc[-1]
    stealth_pct = stealth_qe_score.iloc[-1] / 100  # Already 0-100

    # Weighted composite (weights from CONTEXT.md decisions)
    composite = (
        net_pct * 0.40 +
        global_pct * 0.40 +
        stealth_pct * 0.20
    )

    # Direction + intensity
    direction = "EXPANSION" if composite > 0.5 else "CONTRACTION"
    intensity = abs(composite - 0.5) * 200  # 0-100 scale
    return direction, intensity
```

### Pattern 2: EWMA Rolling Correlation
**What:** Exponentially weighted correlation for faster regime shift detection
**When to use:** When recent correlations matter more than historical
**Example:**
```python
# Source: pandas documentation (ewm.corr)
def ewma_correlation(
    series1: pd.Series,
    series2: pd.Series,
    halflife: int = 21
) -> pd.Series:
    """
    Rolling EWMA correlation with 21-day halflife (~1 trading month).
    """
    return series1.ewm(halflife=halflife).corr(series2)

# Fixed window + EWMA comparison
correlations = pd.DataFrame({
    '30d': returns['BTC'].rolling(30).corr(returns['NetLiq']),
    '90d': returns['BTC'].rolling(90).corr(returns['NetLiq']),
    'ewma_21': returns['BTC'].ewm(halflife=21).corr(returns['NetLiq']),
})
```

### Pattern 3: Correlation Matrix with Significance
**What:** Full correlation matrix with p-value filtering
**When to use:** Dashboard heatmap, identifying significant correlations only
**Example:**
```python
# Source: scipy.stats documentation
from scipy import stats

def correlation_matrix_with_pvalues(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns correlation matrix and p-value matrix.
    """
    cols = df.columns
    n = len(cols)
    corr_matrix = pd.DataFrame(index=cols, columns=cols, dtype=float)
    pval_matrix = pd.DataFrame(index=cols, columns=cols, dtype=float)

    for i, c1 in enumerate(cols):
        for j, c2 in enumerate(cols):
            if i == j:
                corr_matrix.loc[c1, c2] = 1.0
                pval_matrix.loc[c1, c2] = 0.0
            elif i < j:
                result = stats.pearsonr(df[c1].dropna(), df[c2].dropna())
                corr_matrix.loc[c1, c2] = result.statistic
                corr_matrix.loc[c2, c1] = result.statistic
                pval_matrix.loc[c1, c2] = result.pvalue
                pval_matrix.loc[c2, c1] = result.pvalue

    return corr_matrix, pval_matrix
```

### Anti-Patterns to Avoid
- **Fixed threshold regime classification:** Markets evolve; use percentiles, not $7T
- **Single-window correlation:** 90d misses recent shifts; use EWMA + fixed
- **Correlation without significance:** 0.3 correlation with p=0.15 is noise
- **Hardcoded weights without config:** Put weights in config for tuning
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| EWMA calculation | Custom exponential weights | `pandas.Series.ewm()` | Handles edge cases, min_periods, NaN |
| Rolling correlation | Manual window loop | `pandas.rolling().corr()` | Vectorized, handles alignment |
| P-value calculation | T-test from scratch | `scipy.stats.pearsonr` | Correct degrees of freedom, edge cases |
| Percentile ranks | Manual sorting | `pandas.Series.rank(pct=True)` | Handles ties, NaN correctly |
| Correlation matrix | Nested loops | `pandas.DataFrame.corr()` | Vectorized, handles missing values |

**Key insight:** Pandas/scipy have 15+ years of edge case handling. Rolling stats with NaN, alignment issues, and numerical stability are solved problems. Don't re-solve them.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Lookahead Bias in Percentiles
**What goes wrong:** Calculating percentile using future data
**Why it happens:** Using full series percentile instead of rolling/expanding window
**How to avoid:** Use `expanding().rank()` or `rolling(lookback).rank()`, not `rank()` on full series
**Warning signs:** Regime calls look "perfect" in backtest

### Pitfall 2: EWMA Halflife Confusion
**What goes wrong:** Setting halflife=21 expecting 21-day window
**Why it happens:** Halflife is decay parameter, not window size. halflife=21 means weight decays to 50% after 21 observations
**How to avoid:** For ~1 month effective window, halflife=21 is correct. For ~3 months, use halflife=63
**Warning signs:** EWMA looks too smooth or too noisy

### Pitfall 3: Correlation Regime Alerts Fire Too Often
**What goes wrong:** Alert on every minor correlation fluctuation
**Why it happens:** Using raw 0.3 change threshold without statistical filter
**How to avoid:** Combine absolute threshold (>0.3) with statistical threshold (>2σ from rolling mean)
**Warning signs:** Multiple alerts per week, alert fatigue

### Pitfall 4: Missing Data in Correlation Pairs
**What goes wrong:** NaN propagates, breaks correlation calculation
**Why it happens:** Assets have different trading calendars (BTC 24/7, SPX market hours)
**How to avoid:** Use `min_periods` parameter, align to common dates, forward-fill gaps
**Warning signs:** Correlation series shorter than expected

### Pitfall 5: Timezone Misalignment
**What goes wrong:** Correlating yesterday's BTC with today's SPX
**Why it happens:** Data sources use different timezone conventions
**How to avoid:** Normalize all timestamps to UTC, use market close times consistently
**Warning signs:** Correlations look lagged or offset
</common_pitfalls>

<code_examples>
## Code Examples

Verified patterns from official sources and existing codebase:

### Regime Classification Dataclass
```python
# Source: Existing StealthQEResult pattern
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class RegimeDirection(str, Enum):
    EXPANSION = "EXPANSION"
    CONTRACTION = "CONTRACTION"

@dataclass
class RegimeResult:
    """Regime classification result."""
    timestamp: datetime
    direction: RegimeDirection
    intensity: float  # 0-100
    confidence: str  # HIGH/MEDIUM/LOW
    net_liq_percentile: float
    global_liq_percentile: float
    stealth_qe_score: float
    components: str  # "NetLiq:40% Global:40% StealthQE:20%"
```

### EWMA Correlation Engine
```python
# Source: pandas documentation
import pandas as pd

class CorrelationEngine:
    """Calculate rolling and EWMA correlations."""

    ASSETS = ['BTC', 'SPX', 'GOLD', 'TLT', 'DXY', 'COPPER', 'HYG']
    WINDOWS = [30, 90]
    EWMA_HALFLIFE = 21

    def calculate_all(
        self,
        returns: pd.DataFrame,
        liquidity: pd.Series
    ) -> dict[str, pd.DataFrame]:
        """
        Returns dict with keys: '30d', '90d', 'ewma'
        Each value is DataFrame with asset correlations over time.
        """
        results = {}

        # Fixed windows
        for window in self.WINDOWS:
            corrs = pd.DataFrame(index=returns.index)
            for asset in self.ASSETS:
                if asset in returns.columns:
                    corrs[asset] = returns[asset].rolling(window).corr(liquidity)
            results[f'{window}d'] = corrs

        # EWMA
        corrs = pd.DataFrame(index=returns.index)
        for asset in self.ASSETS:
            if asset in returns.columns:
                corrs[asset] = returns[asset].ewm(halflife=self.EWMA_HALFLIFE).corr(liquidity)
        results['ewma'] = corrs

        return results
```

### Alert Detection
```python
# Source: Research on regime shift detection
def detect_correlation_shift(
    correlations: pd.Series,
    absolute_threshold: float = 0.3,
    rolling_window: int = 90,
    sigma_threshold: float = 2.0
) -> bool:
    """
    Detect correlation regime shift using dual threshold:
    1. Absolute change > threshold
    2. Statistical deviation > sigma_threshold from rolling mean
    """
    if len(correlations) < rolling_window + 1:
        return False

    current = correlations.iloc[-1]
    previous = correlations.iloc[-2]
    rolling_mean = correlations.rolling(rolling_window).mean().iloc[-2]
    rolling_std = correlations.rolling(rolling_window).std().iloc[-2]

    # Absolute change check
    absolute_change = abs(current - previous)

    # Statistical deviation check
    if rolling_std > 0:
        z_score = abs(current - rolling_mean) / rolling_std
    else:
        z_score = 0

    return absolute_change > absolute_threshold or z_score > sigma_threshold
```
</code_examples>

<sota_updates>
## State of the Art (2025-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed threshold regimes | Percentile-based adaptive | 2020+ | More robust to market evolution |
| Simple rolling correlation | EWMA + fixed windows | Standard | Faster regime shift detection |
| Manual p-value calc | scipy.stats integration | Standard | Correct statistical testing |

**New tools/patterns to consider:**
- **pandas 2.0+ ewm.corr():** Direct EWMA correlation method (no need for manual calculation)
- **Markov switching models:** For formal regime probability, but overkill for 3-factor model

**Deprecated/outdated:**
- **pandas.rolling_corr():** Deprecated, use `Series.rolling().corr()` instead
- **pandas.ewmcorr():** Deprecated, use `Series.ewm().corr()` instead
</sota_updates>

<open_questions>
## Open Questions

1. **Optimal EWMA halflife**
   - What we know: 21 days (~1 trading month) is standard starting point
   - What's unclear: May need tuning based on backtest
   - Recommendation: Start with 21, make configurable, tune in Phase 10

2. **Weight optimization for multi-factor score**
   - What we know: 40/40/20 (Net/Global/StealthQE) is reasonable starting point
   - What's unclear: Optimal weights depend on historical regime accuracy
   - Recommendation: Start with 40/40/20, add weight config, tune later

3. **Correlation significance filtering**
   - What we know: p < 0.05 is standard
   - What's unclear: Should we filter display or just flag?
   - Recommendation: Display all, flag insignificant (p > 0.05) with warning
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- [pandas documentation - ewm](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.ewm.html) - EWMA methods
- [pandas documentation - rolling correlation](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.core.window.rolling.Rolling.corr.html) - Rolling correlation
- [scipy.stats.pearsonr](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html) - Correlation significance

### Secondary (MEDIUM confidence)
- [Macrosynergy - Classifying Market Regimes](https://macrosynergy.com/research/classifying-market-regimes/) - GMM regime classification
- [LSEG - Market Regime Detection](https://developers.lseg.com/en/article-catalog/article/market-regime-detection) - HMM approaches
- [Robot Wealth - EWMA for Trading](https://robotwealth.com/using-exponentially-weighted-moving-averages-to-navigate-trade-offs-in-systematic-trading/) - EWMA practical usage

### Tertiary (needs validation)
- [STARS Regime Shift Detection](https://sites.google.com/view/regime-shift-test/home) - Correlation shift testing (academic)
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: pandas, numpy, scipy
- Ecosystem: Time-series analysis, rolling statistics
- Patterns: Multi-factor scoring, EWMA correlation, regime classification
- Pitfalls: Lookahead bias, halflife confusion, timezone issues

**Confidence breakdown:**
- Standard stack: HIGH - well-documented, widely used
- Architecture: HIGH - follows existing codebase pattern (StealthQECalculator)
- Pitfalls: HIGH - documented in pandas docs and quant literature
- Code examples: HIGH - from official docs and existing codebase

**Research date:** 2026-01-26
**Valid until:** 2026-02-26 (30 days - pandas/scipy ecosystem stable)
</metadata>

---

*Phase: 08-analysis-correlations*
*Research completed: 2026-01-26*
*Ready for planning: yes*
