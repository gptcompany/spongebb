"""Hawkish/Dovish keyword lexicons for central bank sentiment analysis.

Provides curated keyword dictionaries with associated sentiment weights for
identifying monetary policy stance in central bank communications.

The lexicons are designed to augment FinBERT sentiment analysis with
domain-specific financial terminology that may not be captured by the
general financial sentiment model.

References:
    - Arthur Hayes' framework for CB communication analysis
    - Federal Reserve communication studies
    - ECB monetary policy glossary
"""

from __future__ import annotations

# =============================================================================
# Hawkish Keywords
# =============================================================================
# Positive weights indicate hawkish sentiment (tighter monetary policy)
# Scale: 0.0 (weak signal) to 1.0 (strong signal)

HAWKISH_KEYWORDS: dict[str, float] = {
    # Strong hawkish signals (1.0)
    "rate increase": 1.0,
    "rate hike": 1.0,
    "tightening": 1.0,
    "raise rates": 1.0,
    "higher rates": 1.0,
    "hiking cycle": 1.0,
    "quantitative tightening": 1.0,
    "qt": 1.0,
    "balance sheet reduction": 1.0,
    "reduce purchases": 1.0,
    # Moderate hawkish signals (0.8-0.9)
    "reduce accommodation": 0.9,
    "less accommodative": 0.9,
    "remove stimulus": 0.9,
    "inflation concern": 0.8,
    "inflation concerns": 0.8,
    "inflation pressures": 0.8,
    "overheating": 0.8,
    "above target": 0.8,
    "excessive inflation": 0.8,
    "inflation risks": 0.8,
    "upside risks to inflation": 0.8,
    # Medium hawkish signals (0.6-0.7)
    "price stability": 0.7,
    "anchor inflation expectations": 0.7,
    "normalize": 0.6,
    "normalization": 0.6,
    "normalize policy": 0.6,
    "remove extraordinary measures": 0.7,
    "data dependent": 0.6,  # Often used before hikes
    "further tightening": 0.7,
    "additional tightening": 0.7,
    # Weaker hawkish signals (0.4-0.5)
    "vigilant": 0.5,
    "monitor inflation": 0.5,
    "watching inflation": 0.5,
    "strong labor market": 0.5,
    "robust employment": 0.5,
    "solid growth": 0.4,
    "resilient economy": 0.4,
    "upside risks": 0.5,
}

# =============================================================================
# Dovish Keywords
# =============================================================================
# Negative weights indicate dovish sentiment (looser monetary policy)
# Scale: -1.0 (strong dovish) to 0.0 (weak signal)

DOVISH_KEYWORDS: dict[str, float] = {
    # Strong dovish signals (-1.0)
    "rate cut": -1.0,
    "rate cuts": -1.0,
    "cut rates": -1.0,
    "lower rates": -1.0,
    "easing": -1.0,
    "monetary easing": -1.0,
    "quantitative easing": -1.0,
    "qe": -1.0,
    "asset purchases": -1.0,
    "expand balance sheet": -1.0,
    "increase purchases": -1.0,
    # Moderate dovish signals (-0.8 to -0.9)
    "accommodate": -0.9,
    "accommodative": -0.9,
    "highly accommodative": -0.9,
    "maintain accommodation": -0.9,
    "support growth": -0.8,
    "support the economy": -0.8,
    "economic support": -0.8,
    "stimulus": -0.8,
    "fiscal stimulus": -0.8,
    # Medium dovish signals (-0.6 to -0.7)
    "downside risks": -0.7,
    "risks to the downside": -0.7,
    "employment": -0.6,  # Focus on employment often dovish
    "labor market slack": -0.7,
    "unemployment concerns": -0.7,
    "below target": -0.7,
    "subdued inflation": -0.7,
    "low inflation": -0.6,
    "disinflationary": -0.7,
    # Weaker dovish signals (-0.4 to -0.5)
    "patient": -0.5,
    "patience": -0.5,
    "wait and see": -0.5,
    "transitory": -0.4,
    "temporary": -0.4,
    "gradual": -0.4,
    "measured pace": -0.5,
    "flexible": -0.4,
    "uncertainty": -0.4,
    "headwinds": -0.5,
    "economic weakness": -0.6,
    "slowing growth": -0.6,
}

# =============================================================================
# Neutral/Ambiguous Keywords
# =============================================================================
# These can shift meaning based on context; weight is 0 but tracked

NEUTRAL_KEYWORDS: dict[str, float] = {
    "data dependent": 0.0,
    "monitor closely": 0.0,
    "assess conditions": 0.0,
    "appropriate": 0.0,
    "balanced": 0.0,
    "symmetric": 0.0,
    "dual mandate": 0.0,
    "price stability and employment": 0.0,
    "evolving outlook": 0.0,
    "incoming data": 0.0,
}

# =============================================================================
# Helper Functions
# =============================================================================


def get_all_keywords() -> dict[str, float]:
    """Get combined dictionary of all sentiment keywords.

    Returns:
        Dictionary mapping keywords to their sentiment weights.
        Positive = hawkish, Negative = dovish, Zero = neutral.
    """
    combined = {}
    combined.update(HAWKISH_KEYWORDS)
    combined.update(DOVISH_KEYWORDS)
    combined.update(NEUTRAL_KEYWORDS)
    return combined


def get_keyword_weight(keyword: str) -> float | None:
    """Get the sentiment weight for a specific keyword.

    Args:
        keyword: Keyword phrase to look up (case-insensitive).

    Returns:
        Weight value if found, None otherwise.
    """
    keyword_lower = keyword.lower().strip()

    if keyword_lower in HAWKISH_KEYWORDS:
        return HAWKISH_KEYWORDS[keyword_lower]
    if keyword_lower in DOVISH_KEYWORDS:
        return DOVISH_KEYWORDS[keyword_lower]
    if keyword_lower in NEUTRAL_KEYWORDS:
        return NEUTRAL_KEYWORDS[keyword_lower]

    return None


def classify_keyword(keyword: str) -> str | None:
    """Classify a keyword as hawkish, dovish, or neutral.

    Args:
        keyword: Keyword phrase to classify (case-insensitive).

    Returns:
        "hawkish", "dovish", "neutral", or None if not found.
    """
    keyword_lower = keyword.lower().strip()

    if keyword_lower in HAWKISH_KEYWORDS:
        return "hawkish"
    if keyword_lower in DOVISH_KEYWORDS:
        return "dovish"
    if keyword_lower in NEUTRAL_KEYWORDS:
        return "neutral"

    return None
