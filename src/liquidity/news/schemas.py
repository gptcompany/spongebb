"""Pydantic models for news intelligence module.

Defines data models for:
- NewsItem: Individual news/announcement item from RSS feeds
- FeedConfig: Configuration for a single RSS feed
- FeedState: Runtime state tracking for a feed (backoff, errors)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class FeedSource(str, Enum):
    """Central bank feed source identifiers."""

    FED_PRESS = "fed_press"
    FED_SPEECHES = "fed_speeches"
    ECB_PRESS = "ecb_press"
    BOJ_NEWS = "boj_news"
    BOE_NEWS = "boe_news"
    SNB_NEWS = "snb_news"
    BOC_NEWS = "boc_news"
    PBOC_NEWS = "pboc_news"


class NewsItem(BaseModel):
    """Individual news item from an RSS feed.

    Represents a single announcement, press release, or speech from
    a central bank's RSS feed.

    Attributes:
        id: Unique identifier (SHA256 hash of title+date).
        source: Feed source identifier.
        title: News item title.
        link: URL to the original content.
        published: Publication timestamp.
        summary: Brief description or excerpt.
        content: Full content if available.
        language: ISO 639-1 language code (e.g., "en", "zh").
        content_hash: SHA256 hash for deduplication.
        fetched_at: When this item was fetched.
    """

    id: str = Field(description="Unique identifier (SHA256 of title+date)")
    source: FeedSource = Field(description="Feed source identifier")
    title: str = Field(description="News item title")
    link: HttpUrl = Field(description="URL to original content")
    published: datetime = Field(description="Publication timestamp")
    summary: str = Field(default="", description="Brief description or excerpt")
    content: str = Field(default="", description="Full content if available")
    language: str = Field(default="en", description="ISO 639-1 language code")
    content_hash: str = Field(description="SHA256 hash for deduplication")
    fetched_at: datetime = Field(description="When this item was fetched")

    model_config = ConfigDict(frozen=True)


class FeedConfig(BaseModel):
    """Configuration for a single RSS feed.

    Defines the feed URL, polling behavior, and metadata for
    a central bank RSS feed.

    Attributes:
        source: Feed source identifier.
        url: RSS feed URL.
        name: Human-readable feed name.
        language: Primary language of feed content.
        poll_interval_seconds: Base polling interval.
        jitter_seconds: Random jitter range (+/-).
        enabled: Whether this feed is actively polled.
    """

    source: FeedSource = Field(description="Feed source identifier")
    url: HttpUrl = Field(description="RSS feed URL")
    name: str = Field(description="Human-readable feed name")
    language: str = Field(default="en", description="Primary language of feed content")
    poll_interval_seconds: int = Field(
        default=60,
        ge=60,
        description="Base polling interval (minimum 60s)",
    )
    jitter_seconds: int = Field(
        default=10,
        ge=0,
        le=30,
        description="Random jitter range (+/-)",
    )
    enabled: bool = Field(default=True, description="Whether feed is actively polled")

    model_config = ConfigDict(frozen=True)


class FeedState(BaseModel):
    """Runtime state for a feed during polling.

    Tracks error counts, backoff state, and last successful poll
    for adaptive polling behavior.

    Attributes:
        source: Feed source identifier.
        last_poll: Timestamp of last poll attempt.
        last_success: Timestamp of last successful poll.
        consecutive_errors: Number of consecutive failures.
        backoff_until: Don't poll until this time (exponential backoff).
        last_error: Most recent error message.
        items_fetched_total: Total items fetched since startup.
    """

    source: FeedSource = Field(description="Feed source identifier")
    last_poll: datetime | None = Field(default=None, description="Last poll attempt")
    last_success: datetime | None = Field(default=None, description="Last successful poll")
    consecutive_errors: int = Field(default=0, description="Consecutive failure count")
    backoff_until: datetime | None = Field(
        default=None, description="Backoff deadline (exponential)"
    )
    last_error: str | None = Field(default=None, description="Most recent error message")
    items_fetched_total: int = Field(
        default=0, description="Total items fetched since startup"
    )

    def should_poll(self, now: datetime) -> bool:
        """Check if feed should be polled based on backoff state.

        Args:
            now: Current timestamp.

        Returns:
            True if feed should be polled, False if in backoff.
        """
        if self.backoff_until is None:
            return True
        return now >= self.backoff_until


# =============================================================================
# Feed Configuration Constants
# =============================================================================

CENTRAL_BANK_FEEDS: dict[FeedSource, FeedConfig] = {
    FeedSource.FED_PRESS: FeedConfig(
        source=FeedSource.FED_PRESS,
        url="https://www.federalreserve.gov/feeds/press_all.xml",
        name="Federal Reserve Press Releases",
        language="en",
    ),
    FeedSource.FED_SPEECHES: FeedConfig(
        source=FeedSource.FED_SPEECHES,
        url="https://www.federalreserve.gov/feeds/speeches.xml",
        name="Federal Reserve Speeches",
        language="en",
    ),
    FeedSource.ECB_PRESS: FeedConfig(
        source=FeedSource.ECB_PRESS,
        url="https://www.ecb.europa.eu/rss/press.html",
        name="ECB Press Releases",
        language="en",
    ),
    FeedSource.BOJ_NEWS: FeedConfig(
        source=FeedSource.BOJ_NEWS,
        url="https://www.boj.or.jp/en/rss/whatsnew.xml",
        name="Bank of Japan What's New",
        language="en",
    ),
    FeedSource.BOE_NEWS: FeedConfig(
        source=FeedSource.BOE_NEWS,
        url="https://www.bankofengland.co.uk/rss/news",
        name="Bank of England News",
        language="en",
    ),
    FeedSource.SNB_NEWS: FeedConfig(
        source=FeedSource.SNB_NEWS,
        url="https://www.snb.ch/en/service/rss",
        name="Swiss National Bank News",
        language="en",
    ),
    FeedSource.BOC_NEWS: FeedConfig(
        source=FeedSource.BOC_NEWS,
        url="https://www.bankofcanada.ca/content-type/press-releases/feed/",
        name="Bank of Canada Press Releases",
        language="en",
    ),
}

# Backoff configuration
BACKOFF_BASE_SECONDS: int = 60  # 1 minute base
BACKOFF_MAX_SECONDS: int = 480  # 8 minutes max
BACKOFF_MULTIPLIER: float = 2.0  # Exponential factor

# Deduplication cache TTL
DEDUP_CACHE_TTL_HOURS: int = 24
