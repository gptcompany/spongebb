"""RSS feed aggregator for central bank communications.

Implements NewsPoller with:
- Async polling of multiple RSS feeds
- Per-feed rate limiting
- Content hash deduplication with 24h TTL
- Exponential backoff on failures (1->2->4->8 min)
- Random jitter to avoid thundering herd
"""

import asyncio
import hashlib
import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any

import feedparser
import httpx

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

logger = logging.getLogger(__name__)


class DeduplicationCache:
    """In-memory cache for content hash deduplication.

    Stores content hashes with TTL to avoid reprocessing
    the same news items within the deduplication window.

    Attributes:
        _cache: Dict mapping content_hash to expiry timestamp.
        _ttl_hours: Time-to-live for cache entries in hours.
    """

    def __init__(self, ttl_hours: int = DEDUP_CACHE_TTL_HOURS) -> None:
        """Initialize deduplication cache.

        Args:
            ttl_hours: Time-to-live for cache entries (default: 24h).
        """
        self._cache: dict[str, datetime] = {}
        self._ttl_hours = ttl_hours

    def contains(self, content_hash: str) -> bool:
        """Check if content hash exists in cache (not expired).

        Args:
            content_hash: SHA256 hash to check.

        Returns:
            True if hash exists and not expired.
        """
        if content_hash not in self._cache:
            return False

        expiry = self._cache[content_hash]
        now = datetime.now(UTC)

        if now > expiry:
            # Entry expired, remove it
            del self._cache[content_hash]
            return False

        return True

    def add(self, content_hash: str) -> None:
        """Add content hash to cache with TTL.

        Args:
            content_hash: SHA256 hash to add.
        """
        expiry = datetime.now(UTC) + timedelta(hours=self._ttl_hours)
        self._cache[content_hash] = expiry

    def cleanup(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed.
        """
        now = datetime.now(UTC)
        expired = [h for h, exp in self._cache.items() if now > exp]
        for h in expired:
            del self._cache[h]
        return len(expired)

    def size(self) -> int:
        """Get current cache size.

        Returns:
            Number of entries in cache.
        """
        return len(self._cache)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()


class RateLimiter:
    """Per-feed rate limiter with jitter support.

    Ensures minimum interval between polls to a single feed,
    with configurable random jitter to avoid synchronized requests.
    """

    def __init__(self) -> None:
        """Initialize rate limiter."""
        self._last_poll: dict[FeedSource, datetime] = {}

    def can_poll(self, config: FeedConfig) -> bool:
        """Check if feed can be polled based on rate limit.

        Args:
            config: Feed configuration.

        Returns:
            True if sufficient time has passed since last poll.
        """
        if config.source not in self._last_poll:
            return True

        last = self._last_poll[config.source]
        now = datetime.now(UTC)
        elapsed = (now - last).total_seconds()

        # Add jitter to the check
        jitter = random.uniform(-config.jitter_seconds, config.jitter_seconds)
        required = config.poll_interval_seconds + jitter

        return elapsed >= required

    def record_poll(self, source: FeedSource) -> None:
        """Record a poll attempt for rate limiting.

        Args:
            source: Feed source that was polled.
        """
        self._last_poll[source] = datetime.now(UTC)

    def get_wait_time(self, config: FeedConfig) -> float:
        """Get seconds until next allowed poll.

        Args:
            config: Feed configuration.

        Returns:
            Seconds to wait, or 0 if can poll now.
        """
        if config.source not in self._last_poll:
            return 0.0

        last = self._last_poll[config.source]
        now = datetime.now(UTC)
        elapsed = (now - last).total_seconds()

        jitter = random.uniform(-config.jitter_seconds, config.jitter_seconds)
        required = config.poll_interval_seconds + jitter

        wait = required - elapsed
        return max(0.0, wait)


def compute_content_hash(title: str, published: datetime) -> str:
    """Compute SHA256 hash for deduplication.

    Args:
        title: News item title.
        published: Publication timestamp.

    Returns:
        SHA256 hex digest of title + ISO date string.
    """
    # Normalize: lowercase title, ISO date only (no time for robustness)
    normalized = f"{title.lower().strip()}|{published.date().isoformat()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_item_id(title: str, published: datetime) -> str:
    """Compute unique item ID (shorter hash for display).

    Args:
        title: News item title.
        published: Publication timestamp.

    Returns:
        First 16 chars of content hash.
    """
    return compute_content_hash(title, published)[:16]


def parse_feed_entry(
    entry: Any,
    source: FeedSource,
    language: str,
) -> NewsItem | None:
    """Parse a feedparser entry into a NewsItem.

    Args:
        entry: feedparser entry object.
        source: Feed source identifier.
        language: Default language for the feed.

    Returns:
        NewsItem if parsing succeeds, None otherwise.
    """
    try:
        # Extract title (required)
        title = entry.get("title", "").strip()
        if not title:
            logger.debug("Skipping entry with empty title")
            return None

        # Extract link (required)
        link = entry.get("link", "").strip()
        if not link:
            logger.debug("Skipping entry with empty link: %s", title)
            return None

        # Parse published date
        published_parsed = entry.get("published_parsed")
        if published_parsed:
            # feedparser returns a time.struct_time
            published = datetime(
                *published_parsed[:6],
                tzinfo=UTC,
            )
        else:
            # Fallback to current time if no date
            published = datetime.now(UTC)
            logger.debug("No published date for '%s', using current time", title)

        # Extract summary
        summary = entry.get("summary", "").strip()

        # Extract content (may be in different locations)
        content = ""
        if "content" in entry and entry["content"]:
            # feedparser content is a list of dicts
            content = entry["content"][0].get("value", "")
        elif summary:
            content = summary

        # Compute hashes
        content_hash = compute_content_hash(title, published)
        item_id = content_hash[:16]

        return NewsItem(
            id=item_id,
            source=source,
            title=title,
            link=link,
            published=published,
            summary=summary,
            content=content,
            language=language,
            content_hash=content_hash,
            fetched_at=datetime.now(UTC),
        )

    except Exception as e:
        logger.warning("Failed to parse feed entry: %s", e)
        return None


class NewsPoller:
    """Async RSS feed poller for central bank communications.

    Polls configured RSS feeds with rate limiting, deduplication,
    and exponential backoff on failures.

    Example:
        poller = NewsPoller()
        await poller.start()

        # In a loop or callback:
        items = await poller.poll_all()
        for item in items:
            print(f"{item.source}: {item.title}")

        await poller.close()

    Attributes:
        feeds: Dict of feed configurations.
        states: Dict of feed runtime states.
        dedup_cache: Content deduplication cache.
        rate_limiter: Per-feed rate limiter.
    """

    def __init__(
        self,
        feeds: dict[FeedSource, FeedConfig] | None = None,
        http_timeout: float = 30.0,
    ) -> None:
        """Initialize the news poller.

        Args:
            feeds: Feed configurations. Defaults to a copy of CENTRAL_BANK_FEEDS.
            http_timeout: HTTP request timeout in seconds.
        """
        # Make a copy to avoid mutating the global default
        self.feeds = dict(feeds) if feeds else dict(CENTRAL_BANK_FEEDS)
        self.states: dict[FeedSource, FeedState] = {
            source: FeedState(source=source)
            for source in self.feeds
        }
        self.dedup_cache = DeduplicationCache()
        self.rate_limiter = RateLimiter()
        self._http_timeout = http_timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Returns:
            Shared httpx AsyncClient instance.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._http_timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "LiquidityMonitor/1.0 RSS Aggregator",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _calculate_backoff(self, consecutive_errors: int) -> int:
        """Calculate exponential backoff duration.

        Args:
            consecutive_errors: Number of consecutive failures.

        Returns:
            Backoff duration in seconds.
        """
        # Exponential: 60, 120, 240, 480 (capped)
        backoff = BACKOFF_BASE_SECONDS * (BACKOFF_MULTIPLIER ** (consecutive_errors - 1))
        return int(min(backoff, BACKOFF_MAX_SECONDS))

    async def poll_feed(self, source: FeedSource) -> list[NewsItem]:
        """Poll a single feed and return new items.

        Handles rate limiting, backoff, and deduplication.

        Args:
            source: Feed source to poll.

        Returns:
            List of new (non-duplicate) NewsItem objects.

        Raises:
            ValueError: If source is not configured.
        """
        if source not in self.feeds:
            raise ValueError(f"Unknown feed source: {source}")

        config = self.feeds[source]
        state = self.states[source]

        # Check if feed is enabled
        if not config.enabled:
            logger.debug("Feed %s is disabled, skipping", source.value)
            return []

        # Check rate limit
        if not self.rate_limiter.can_poll(config):
            wait_time = self.rate_limiter.get_wait_time(config)
            logger.debug(
                "Rate limit for %s, wait %.1fs",
                source.value,
                wait_time,
            )
            return []

        # Check backoff
        now = datetime.now(UTC)
        if not state.should_poll(now):
            logger.debug(
                "Feed %s in backoff until %s",
                source.value,
                state.backoff_until,
            )
            return []

        # Update state
        state.last_poll = now
        self.rate_limiter.record_poll(source)

        try:
            # Fetch feed
            client = await self._get_client()
            response = await client.get(str(config.url))
            response.raise_for_status()

            # Parse feed
            feed = feedparser.parse(response.text)

            if feed.bozo and feed.bozo_exception:
                # feedparser detected malformed feed but may have partial data
                logger.warning(
                    "Feed %s has issues: %s",
                    source.value,
                    feed.bozo_exception,
                )

            # Process entries
            new_items: list[NewsItem] = []
            for entry in feed.entries:
                item = parse_feed_entry(entry, source, config.language)
                if item is None:
                    continue

                # Check dedup cache
                if self.dedup_cache.contains(item.content_hash):
                    logger.debug("Duplicate item skipped: %s", item.title[:50])
                    continue

                # New item
                self.dedup_cache.add(item.content_hash)
                new_items.append(item)

            # Update state on success
            state.last_success = now
            state.consecutive_errors = 0
            state.backoff_until = None
            state.last_error = None
            state.items_fetched_total += len(new_items)

            logger.info(
                "Polled %s: %d new items (total: %d)",
                source.value,
                len(new_items),
                state.items_fetched_total,
            )

            return new_items

        except httpx.HTTPStatusError as e:
            state.consecutive_errors += 1
            state.last_error = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
            backoff_secs = self._calculate_backoff(state.consecutive_errors)
            state.backoff_until = now + timedelta(seconds=backoff_secs)
            logger.warning(
                "Feed %s HTTP error: %s (backoff: %ds)",
                source.value,
                state.last_error,
                backoff_secs,
            )
            return []

        except httpx.RequestError as e:
            state.consecutive_errors += 1
            state.last_error = f"Request error: {type(e).__name__}"
            backoff_secs = self._calculate_backoff(state.consecutive_errors)
            state.backoff_until = now + timedelta(seconds=backoff_secs)
            logger.warning(
                "Feed %s request error: %s (backoff: %ds)",
                source.value,
                state.last_error,
                backoff_secs,
            )
            return []

        except Exception as e:
            state.consecutive_errors += 1
            state.last_error = f"Unexpected error: {type(e).__name__}: {e}"
            backoff_secs = self._calculate_backoff(state.consecutive_errors)
            state.backoff_until = now + timedelta(seconds=backoff_secs)
            logger.error(
                "Feed %s unexpected error: %s (backoff: %ds)",
                source.value,
                state.last_error,
                backoff_secs,
            )
            return []

    async def poll_all(self) -> list[NewsItem]:
        """Poll all configured feeds concurrently.

        Returns:
            Combined list of new items from all feeds.
        """
        tasks = [self.poll_feed(source) for source in self.feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: list[NewsItem] = []
        for source, result in zip(self.feeds, results):
            if isinstance(result, Exception):
                logger.error("Poll task failed for %s: %s", source.value, result)
                continue
            all_items.extend(result)

        # Periodic cache cleanup
        removed = self.dedup_cache.cleanup()
        if removed > 0:
            logger.debug("Cleaned up %d expired cache entries", removed)

        return all_items

    def get_feed_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all feeds.

        Returns:
            Dict of feed statuses keyed by source name.
        """
        status: dict[str, dict[str, Any]] = {}
        for source, state in self.states.items():
            config = self.feeds[source]
            status[source.value] = {
                "name": config.name,
                "enabled": config.enabled,
                "url": str(config.url),
                "last_poll": state.last_poll.isoformat() if state.last_poll else None,
                "last_success": state.last_success.isoformat() if state.last_success else None,
                "consecutive_errors": state.consecutive_errors,
                "backoff_until": state.backoff_until.isoformat() if state.backoff_until else None,
                "last_error": state.last_error,
                "items_fetched_total": state.items_fetched_total,
            }
        return status

    def get_cache_stats(self) -> dict[str, int]:
        """Get deduplication cache statistics.

        Returns:
            Dict with cache size and TTL hours.
        """
        return {
            "size": self.dedup_cache.size(),
            "ttl_hours": self.dedup_cache._ttl_hours,
        }


async def poll_feeds_once(
    sources: list[FeedSource] | None = None,
) -> list[NewsItem]:
    """Convenience function to poll feeds once.

    Creates a temporary poller, polls specified feeds, and cleans up.

    Args:
        sources: List of feeds to poll. Defaults to all configured feeds.

    Returns:
        List of new news items.
    """
    poller = NewsPoller()
    try:
        if sources:
            items: list[NewsItem] = []
            for source in sources:
                items.extend(await poller.poll_feed(source))
            return items
        else:
            return await poller.poll_all()
    finally:
        await poller.close()
