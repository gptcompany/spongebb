"""News and CB communication monitoring modules.

This module provides:
- RSS feed aggregation from central banks
- Content deduplication
- Rate limiting and backoff
- Multi-language translation for central bank documents
- Breaking news keyword alerts
- CB speech sentiment analysis (hawkish/dovish)
- Model warming utilities for NLP pipeline startup
"""

from liquidity.news import fomc
from liquidity.news.alerts import (
    BREAKING_KEYWORDS,
    CENTRAL_BANK_PATTERNS,
    NewsAlert,
    NewsAlertEngine,
    Priority,
)
from liquidity.news.feeds import (
    DeduplicationCache,
    NewsPoller,
    RateLimiter,
    compute_content_hash,
    compute_item_id,
    parse_feed_entry,
    poll_feeds_once,
)
from liquidity.news.oil_alerts import (
    SUPPLY_KEYWORDS,
    AlertPriority,
    KeywordMatch,
    SupplyDisruptionMatcher,
)
from liquidity.news.oil_feeds import (
    OIL_FEEDS,
    OilNewsPoller,
    poll_oil_feeds_once,
)
from liquidity.news.lexicons import (
    DOVISH_KEYWORDS,
    HAWKISH_KEYWORDS,
    NEUTRAL_KEYWORDS,
    classify_keyword,
    get_all_keywords,
    get_keyword_weight,
)
from liquidity.news.schemas import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    BACKOFF_MULTIPLIER,
    CENTRAL_BANK_FEEDS,
    DEDUP_CACHE_TTL_HOURS,
    FeedConfig,
    FeedSource,
    FeedState,
    NewsItem,
)
from liquidity.news.sentiment import (
    SentimentAnalyzer,
    SentimentResult,
)
from liquidity.news.translation import (
    CONFIDENCE_DECAY,
    TranslationPipeline,
    TranslationResult,
)
from liquidity.news.warmup import (
    WarmupResult,
    WarmupSummary,
    warm_models,
    warm_models_minimal,
    warm_models_sync,
)

__all__ = [
    # Submodules
    "fomc",
    # Schemas
    "FeedSource",
    "FeedConfig",
    "FeedState",
    "NewsItem",
    "CENTRAL_BANK_FEEDS",
    "BACKOFF_BASE_SECONDS",
    "BACKOFF_MAX_SECONDS",
    "BACKOFF_MULTIPLIER",
    "DEDUP_CACHE_TTL_HOURS",
    # Feed components
    "NewsPoller",
    "DeduplicationCache",
    "RateLimiter",
    "compute_content_hash",
    "compute_item_id",
    "parse_feed_entry",
    "poll_feeds_once",
    # Oil feeds
    "OIL_FEEDS",
    "OilNewsPoller",
    "poll_oil_feeds_once",
    # Oil alerts
    "SUPPLY_KEYWORDS",
    "AlertPriority",
    "KeywordMatch",
    "SupplyDisruptionMatcher",
    # Translation
    "TranslationPipeline",
    "TranslationResult",
    "CONFIDENCE_DECAY",
    # Alerts
    "NewsAlertEngine",
    "NewsAlert",
    "Priority",
    "BREAKING_KEYWORDS",
    "CENTRAL_BANK_PATTERNS",
    # Sentiment Analysis
    "SentimentAnalyzer",
    "SentimentResult",
    "HAWKISH_KEYWORDS",
    "DOVISH_KEYWORDS",
    "NEUTRAL_KEYWORDS",
    "get_all_keywords",
    "get_keyword_weight",
    "classify_keyword",
    # Model warmup
    "warm_models",
    "warm_models_minimal",
    "warm_models_sync",
    "WarmupResult",
    "WarmupSummary",
]
