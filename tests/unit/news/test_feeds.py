"""Unit tests for RSS feed aggregator.

Tests NewsPoller, DeduplicationCache, RateLimiter, and feed parsing
with mocked feedparser responses.

Run with: uv run pytest tests/unit/news/test_feeds.py -v
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from liquidity.news.feeds import (
    DeduplicationCache,
    NewsPoller,
    RateLimiter,
    compute_content_hash,
    compute_item_id,
    parse_feed_entry,
)
from liquidity.news.schemas import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_MULTIPLIER,
    CENTRAL_BANK_FEEDS,
    FeedConfig,
    FeedSource,
    FeedState,
    NewsItem,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def dedup_cache() -> DeduplicationCache:
    """Create a fresh deduplication cache."""
    return DeduplicationCache(ttl_hours=24)


@pytest.fixture
def rate_limiter() -> RateLimiter:
    """Create a fresh rate limiter."""
    return RateLimiter()


@pytest.fixture
def poller() -> NewsPoller:
    """Create a NewsPoller instance."""
    return NewsPoller()


@pytest.fixture
def mock_feed_entry() -> dict:
    """Sample feedparser entry matching Fed press release format."""
    return {
        "title": "Federal Reserve issues FOMC statement",
        "link": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260206a.htm",
        "published_parsed": (2026, 2, 6, 14, 0, 0, 3, 37, 0),  # time.struct_time
        "summary": "The Federal Open Market Committee decided to maintain the target range.",
        "content": [
            {
                "value": "Full FOMC statement text...",
                "type": "text/html",
            }
        ],
    }


@pytest.fixture
def mock_rss_response() -> str:
    """Sample RSS XML response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Federal Reserve Press Releases</title>
    <link>https://www.federalreserve.gov</link>
    <item>
      <title>Federal Reserve issues FOMC statement</title>
      <link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20260206a.htm</link>
      <pubDate>Thu, 06 Feb 2026 14:00:00 EST</pubDate>
      <description>The Federal Open Market Committee decided to maintain...</description>
    </item>
    <item>
      <title>Federal Reserve Board announces approval of application</title>
      <link>https://www.federalreserve.gov/newsevents/pressreleases/orders20260205a.htm</link>
      <pubDate>Wed, 05 Feb 2026 10:00:00 EST</pubDate>
      <description>The Federal Reserve Board announces approval...</description>
    </item>
  </channel>
</rss>"""


# =============================================================================
# DeduplicationCache Tests
# =============================================================================


class TestDeduplicationCache:
    """Tests for DeduplicationCache."""

    def test_empty_cache_contains_nothing(self, dedup_cache: DeduplicationCache) -> None:
        """Test that empty cache returns False for any hash."""
        assert not dedup_cache.contains("abc123")
        assert dedup_cache.size() == 0

    def test_add_and_contains(self, dedup_cache: DeduplicationCache) -> None:
        """Test adding and checking hash existence."""
        content_hash = "abc123def456"
        dedup_cache.add(content_hash)

        assert dedup_cache.contains(content_hash)
        assert dedup_cache.size() == 1

    def test_does_not_contain_different_hash(
        self, dedup_cache: DeduplicationCache
    ) -> None:
        """Test that cache correctly distinguishes hashes."""
        dedup_cache.add("hash1")

        assert dedup_cache.contains("hash1")
        assert not dedup_cache.contains("hash2")

    def test_expired_entry_not_found(self, dedup_cache: DeduplicationCache) -> None:
        """Test that expired entries are not found."""
        content_hash = "expired_hash"
        dedup_cache.add(content_hash)

        # Manually expire the entry
        expired_time = datetime.now(UTC) - timedelta(hours=25)
        dedup_cache._cache[content_hash] = expired_time

        assert not dedup_cache.contains(content_hash)
        assert dedup_cache.size() == 0  # Entry removed on check

    def test_cleanup_removes_expired(self, dedup_cache: DeduplicationCache) -> None:
        """Test that cleanup removes expired entries."""
        # Add some entries
        dedup_cache.add("fresh1")
        dedup_cache.add("fresh2")
        dedup_cache.add("expired1")
        dedup_cache.add("expired2")

        # Expire some
        expired_time = datetime.now(UTC) - timedelta(hours=25)
        dedup_cache._cache["expired1"] = expired_time
        dedup_cache._cache["expired2"] = expired_time

        removed = dedup_cache.cleanup()

        assert removed == 2
        assert dedup_cache.size() == 2
        assert dedup_cache.contains("fresh1")
        assert dedup_cache.contains("fresh2")

    def test_clear_removes_all(self, dedup_cache: DeduplicationCache) -> None:
        """Test that clear removes all entries."""
        dedup_cache.add("hash1")
        dedup_cache.add("hash2")
        dedup_cache.add("hash3")

        assert dedup_cache.size() == 3

        dedup_cache.clear()

        assert dedup_cache.size() == 0
        assert not dedup_cache.contains("hash1")


# =============================================================================
# RateLimiter Tests
# =============================================================================


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_can_poll_first_time(self, rate_limiter: RateLimiter) -> None:
        """Test that first poll is always allowed."""
        config = CENTRAL_BANK_FEEDS[FeedSource.FED_PRESS]
        assert rate_limiter.can_poll(config)

    def test_cannot_poll_immediately_after(self, rate_limiter: RateLimiter) -> None:
        """Test rate limiting after a poll."""
        config = FeedConfig(
            source=FeedSource.FED_PRESS,
            url="https://example.com/feed.xml",
            name="Test Feed",
            poll_interval_seconds=60,
            jitter_seconds=0,  # No jitter for predictable test
        )

        rate_limiter.record_poll(config.source)

        assert not rate_limiter.can_poll(config)

    def test_can_poll_after_interval(self, rate_limiter: RateLimiter) -> None:
        """Test that poll is allowed after interval passes."""
        config = FeedConfig(
            source=FeedSource.FED_PRESS,
            url="https://example.com/feed.xml",
            name="Test Feed",
            poll_interval_seconds=60,
            jitter_seconds=0,
        )

        # Simulate poll 2 minutes ago
        rate_limiter._last_poll[config.source] = datetime.now(UTC) - timedelta(
            seconds=120
        )

        assert rate_limiter.can_poll(config)

    def test_get_wait_time_first_poll(self, rate_limiter: RateLimiter) -> None:
        """Test wait time is 0 for first poll."""
        config = CENTRAL_BANK_FEEDS[FeedSource.FED_PRESS]
        assert rate_limiter.get_wait_time(config) == 0.0

    def test_get_wait_time_after_poll(self, rate_limiter: RateLimiter) -> None:
        """Test wait time calculation after poll."""
        config = FeedConfig(
            source=FeedSource.FED_PRESS,
            url="https://example.com/feed.xml",
            name="Test Feed",
            poll_interval_seconds=60,
            jitter_seconds=0,
        )

        rate_limiter.record_poll(config.source)
        wait_time = rate_limiter.get_wait_time(config)

        # Should be approximately 60 seconds (with some tolerance)
        assert 55 <= wait_time <= 60


# =============================================================================
# Hash Function Tests
# =============================================================================


class TestHashFunctions:
    """Tests for content hash functions."""

    def test_compute_content_hash_deterministic(self) -> None:
        """Test that content hash is deterministic."""
        title = "FOMC Statement"
        published = datetime(2026, 2, 6, 14, 0, 0, tzinfo=UTC)

        hash1 = compute_content_hash(title, published)
        hash2 = compute_content_hash(title, published)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

    def test_compute_content_hash_different_for_different_input(self) -> None:
        """Test that different inputs produce different hashes."""
        published = datetime(2026, 2, 6, 14, 0, 0, tzinfo=UTC)

        hash1 = compute_content_hash("Title A", published)
        hash2 = compute_content_hash("Title B", published)

        assert hash1 != hash2

    def test_compute_content_hash_case_insensitive(self) -> None:
        """Test that hash is case-insensitive for title."""
        published = datetime(2026, 2, 6, 14, 0, 0, tzinfo=UTC)

        hash1 = compute_content_hash("FOMC STATEMENT", published)
        hash2 = compute_content_hash("fomc statement", published)

        assert hash1 == hash2

    def test_compute_content_hash_ignores_time(self) -> None:
        """Test that hash only uses date, not time."""
        title = "FOMC Statement"
        pub1 = datetime(2026, 2, 6, 14, 0, 0, tzinfo=UTC)
        pub2 = datetime(2026, 2, 6, 18, 30, 0, tzinfo=UTC)  # Same day, different time

        hash1 = compute_content_hash(title, pub1)
        hash2 = compute_content_hash(title, pub2)

        assert hash1 == hash2

    def test_compute_item_id_is_shorter(self) -> None:
        """Test that item ID is truncated hash."""
        title = "FOMC Statement"
        published = datetime(2026, 2, 6, 14, 0, 0, tzinfo=UTC)

        item_id = compute_item_id(title, published)
        full_hash = compute_content_hash(title, published)

        assert len(item_id) == 16
        assert item_id == full_hash[:16]


# =============================================================================
# Feed Entry Parsing Tests
# =============================================================================


class TestParseFeedEntry:
    """Tests for parse_feed_entry function."""

    def test_parse_valid_entry(self, mock_feed_entry: dict) -> None:
        """Test parsing a valid feed entry."""
        item = parse_feed_entry(
            mock_feed_entry,
            FeedSource.FED_PRESS,
            "en",
        )

        assert item is not None
        assert item.title == "Federal Reserve issues FOMC statement"
        assert item.source == FeedSource.FED_PRESS
        assert item.language == "en"
        assert "2026-02-06" in item.published.isoformat()
        assert len(item.id) == 16
        assert len(item.content_hash) == 64

    def test_parse_entry_without_content(self) -> None:
        """Test parsing entry without content block."""
        entry = {
            "title": "Press Release",
            "link": "https://example.com/news",
            "published_parsed": (2026, 2, 6, 10, 0, 0, 0, 0, 0),
            "summary": "This is the summary.",
        }

        item = parse_feed_entry(entry, FeedSource.ECB_PRESS, "en")

        assert item is not None
        assert item.summary == "This is the summary."
        assert item.content == "This is the summary."  # Falls back to summary

    def test_parse_entry_without_date(self) -> None:
        """Test parsing entry without published date."""
        entry = {
            "title": "Breaking News",
            "link": "https://example.com/news",
            "summary": "Important update.",
        }

        item = parse_feed_entry(entry, FeedSource.BOJ_NEWS, "en")

        assert item is not None
        # Should use current time (approximately)
        now = datetime.now(UTC)
        assert abs((item.published - now).total_seconds()) < 5

    def test_parse_entry_empty_title_returns_none(self) -> None:
        """Test that entry with empty title returns None."""
        entry = {
            "title": "",
            "link": "https://example.com/news",
        }

        item = parse_feed_entry(entry, FeedSource.FED_PRESS, "en")

        assert item is None

    def test_parse_entry_empty_link_returns_none(self) -> None:
        """Test that entry with empty link returns None."""
        entry = {
            "title": "Valid Title",
            "link": "",
        }

        item = parse_feed_entry(entry, FeedSource.FED_PRESS, "en")

        assert item is None

    def test_parse_entry_malformed_returns_none(self) -> None:
        """Test that malformed entry returns None."""
        entry = {
            "invalid_field": "value",
        }

        item = parse_feed_entry(entry, FeedSource.FED_PRESS, "en")

        assert item is None


# =============================================================================
# FeedState Tests
# =============================================================================


class TestFeedState:
    """Tests for FeedState model."""

    def test_should_poll_no_backoff(self) -> None:
        """Test should_poll with no backoff."""
        state = FeedState(source=FeedSource.FED_PRESS)

        assert state.should_poll(datetime.now(UTC))

    def test_should_poll_in_backoff(self) -> None:
        """Test should_poll during backoff period."""
        now = datetime.now(UTC)
        state = FeedState(
            source=FeedSource.FED_PRESS,
            backoff_until=now + timedelta(minutes=5),
        )

        assert not state.should_poll(now)

    def test_should_poll_after_backoff(self) -> None:
        """Test should_poll after backoff expires."""
        now = datetime.now(UTC)
        state = FeedState(
            source=FeedSource.FED_PRESS,
            backoff_until=now - timedelta(minutes=1),  # Expired
        )

        assert state.should_poll(now)


# =============================================================================
# NewsPoller Tests
# =============================================================================


class TestNewsPoller:
    """Tests for NewsPoller class."""

    def test_init_creates_states_for_all_feeds(self, poller: NewsPoller) -> None:
        """Test that init creates state for each configured feed."""
        for source in CENTRAL_BANK_FEEDS:
            assert source in poller.states
            assert poller.states[source].source == source

    def test_calculate_backoff_first_error(self, poller: NewsPoller) -> None:
        """Test backoff calculation for first error."""
        backoff = poller._calculate_backoff(1)
        assert backoff == BACKOFF_BASE_SECONDS

    def test_calculate_backoff_exponential(self, poller: NewsPoller) -> None:
        """Test exponential backoff calculation."""
        backoff1 = poller._calculate_backoff(1)
        backoff2 = poller._calculate_backoff(2)
        backoff3 = poller._calculate_backoff(3)

        assert backoff2 == backoff1 * BACKOFF_MULTIPLIER
        assert backoff3 == backoff2 * BACKOFF_MULTIPLIER

    def test_calculate_backoff_caps_at_max(self, poller: NewsPoller) -> None:
        """Test that backoff is capped at maximum."""
        backoff = poller._calculate_backoff(10)  # Very high error count
        assert backoff == 480  # BACKOFF_MAX_SECONDS

    @pytest.mark.asyncio
    async def test_poll_feed_unknown_source(self, poller: NewsPoller) -> None:
        """Test that unknown source raises ValueError."""
        # Create a mock source that's not configured
        with pytest.raises(ValueError, match="Unknown feed source"):
            await poller.poll_feed(FeedSource.PBOC_NEWS)  # Not in default feeds

    @pytest.mark.asyncio
    async def test_poll_feed_disabled(self, poller: NewsPoller) -> None:
        """Test that disabled feed returns empty list."""
        # Disable a feed
        source = FeedSource.FED_PRESS
        disabled_config = FeedConfig(
            source=source,
            url=poller.feeds[source].url,
            name="Disabled Feed",
            enabled=False,
        )
        poller.feeds[source] = disabled_config

        items = await poller.poll_feed(source)

        assert items == []

    @pytest.mark.asyncio
    async def test_poll_feed_success(
        self, poller: NewsPoller, mock_rss_response: str
    ) -> None:
        """Test successful feed poll."""
        source = FeedSource.FED_PRESS

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            poller, "_get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            items = await poller.poll_feed(source)

        assert len(items) == 2
        assert all(isinstance(item, NewsItem) for item in items)
        assert items[0].source == FeedSource.FED_PRESS

        # State should be updated
        state = poller.states[source]
        assert state.consecutive_errors == 0
        assert state.last_success is not None
        assert state.items_fetched_total == 2

    @pytest.mark.asyncio
    async def test_poll_feed_http_error_sets_backoff(
        self, poller: NewsPoller
    ) -> None:
        """Test that HTTP error triggers backoff."""
        source = FeedSource.FED_PRESS

        # Mock HTTP error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.reason_phrase = "Internal Server Error"

        with patch.object(
            poller, "_get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Error", request=MagicMock(), response=mock_response
                )
            )
            mock_get_client.return_value = mock_client

            items = await poller.poll_feed(source)

        assert items == []
        state = poller.states[source]
        assert state.consecutive_errors == 1
        assert state.backoff_until is not None
        assert "HTTP 500" in (state.last_error or "")

    @pytest.mark.asyncio
    async def test_poll_feed_deduplicates(
        self, poller: NewsPoller, mock_rss_response: str
    ) -> None:
        """Test that duplicate items are filtered."""
        source = FeedSource.FED_PRESS

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            poller, "_get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            # First poll - should get items
            items1 = await poller.poll_feed(source)
            assert len(items1) == 2

            # Reset rate limiter to allow immediate repoll
            poller.rate_limiter._last_poll.pop(source)

            # Second poll - should get no new items (deduped)
            items2 = await poller.poll_feed(source)
            assert len(items2) == 0

    @pytest.mark.asyncio
    async def test_poll_all_returns_combined_items(
        self, mock_rss_response: str
    ) -> None:
        """Test poll_all combines items from all feeds."""
        # Create poller with only 2 feeds for faster test
        feeds = {
            FeedSource.FED_PRESS: CENTRAL_BANK_FEEDS[FeedSource.FED_PRESS],
            FeedSource.FED_SPEECHES: CENTRAL_BANK_FEEDS[FeedSource.FED_SPEECHES],
        }
        poller = NewsPoller(feeds=feeds)

        # Mock HTTP response for both feeds
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            poller, "_get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            items = await poller.poll_all()

        # Each feed has 2 items, but they're identical so dedup kicks in
        # First feed: 2 items, second feed: 0 (deduped)
        assert len(items) >= 2

    @pytest.mark.asyncio
    async def test_close_closes_client(self, poller: NewsPoller) -> None:
        """Test that close properly closes HTTP client."""
        # Initialize client
        await poller._get_client()
        assert poller._client is not None

        # Close
        await poller.close()
        assert poller._client is None

    def test_get_feed_status(self, poller: NewsPoller) -> None:
        """Test get_feed_status returns correct structure."""
        status = poller.get_feed_status()

        assert len(status) == len(poller.feeds)
        for source in poller.feeds:
            assert source.value in status
            feed_status = status[source.value]
            assert "name" in feed_status
            assert "enabled" in feed_status
            assert "url" in feed_status
            assert "last_poll" in feed_status
            assert "consecutive_errors" in feed_status

    def test_get_cache_stats(self, poller: NewsPoller) -> None:
        """Test get_cache_stats returns correct structure."""
        stats = poller.get_cache_stats()

        assert "size" in stats
        assert "ttl_hours" in stats
        assert stats["size"] == 0
        assert stats["ttl_hours"] == 24


# =============================================================================
# Schema Tests
# =============================================================================


class TestSchemas:
    """Tests for Pydantic schema models."""

    def test_news_item_immutable(self) -> None:
        """Test that NewsItem is immutable (frozen)."""
        item = NewsItem(
            id="abc123",
            source=FeedSource.FED_PRESS,
            title="Test",
            link="https://example.com",
            published=datetime.now(UTC),
            content_hash="x" * 64,
            fetched_at=datetime.now(UTC),
        )

        with pytest.raises(Exception):  # ValidationError for frozen model
            item.title = "Modified"  # type: ignore

    def test_feed_config_immutable(self) -> None:
        """Test that FeedConfig is immutable (frozen)."""
        config = FeedConfig(
            source=FeedSource.FED_PRESS,
            url="https://example.com/feed.xml",
            name="Test Feed",
        )

        with pytest.raises(Exception):
            config.name = "Modified"  # type: ignore

    def test_feed_config_poll_interval_minimum(self) -> None:
        """Test that poll_interval has minimum of 60s."""
        with pytest.raises(Exception):  # ValidationError
            FeedConfig(
                source=FeedSource.FED_PRESS,
                url="https://example.com/feed.xml",
                name="Test",
                poll_interval_seconds=30,  # Below minimum
            )

    def test_central_bank_feeds_configured(self) -> None:
        """Test that all expected feeds are configured."""
        expected_sources = {
            FeedSource.FED_PRESS,
            FeedSource.FED_SPEECHES,
            FeedSource.ECB_PRESS,
            FeedSource.BOJ_NEWS,
            FeedSource.BOE_NEWS,
            FeedSource.SNB_NEWS,
            FeedSource.BOC_NEWS,
        }

        assert set(CENTRAL_BANK_FEEDS.keys()) == expected_sources


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
