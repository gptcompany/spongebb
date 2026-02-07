"""Oil and energy RSS feed aggregator.

Implements oil-specific news polling with:
- OilPrice.com latest news (high frequency, market moving)
- EIA Weekly Petroleum Status Report (TWIP)
- Rigzone industry news

Uses the same NewsPoller infrastructure as central bank feeds.
"""

import logging
from typing import Any

from liquidity.news.feeds import NewsPoller
from liquidity.news.schemas import (
    FeedConfig,
    FeedSource,
    NewsItem,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Oil Feed Configuration
# =============================================================================

OIL_FEEDS: dict[FeedSource, FeedConfig] = {
    FeedSource.OILPRICE_NEWS: FeedConfig(
        source=FeedSource.OILPRICE_NEWS,
        url="https://oilprice.com/rss/main",
        name="OilPrice.com Latest News",
        language="en",
        poll_interval_seconds=300,  # 5 minutes - high frequency for market news
        jitter_seconds=30,
    ),
    FeedSource.EIA_TWIP: FeedConfig(
        source=FeedSource.EIA_TWIP,
        url="https://www.eia.gov/petroleum/weekly/feed.xml",
        name="EIA This Week in Petroleum",
        language="en",
        poll_interval_seconds=3600,  # 1 hour - weekly publication
        jitter_seconds=30,  # Max allowed jitter
    ),
    FeedSource.RIGZONE_NEWS: FeedConfig(
        source=FeedSource.RIGZONE_NEWS,
        url="https://www.rigzone.com/news/rss/rigzone_latest.aspx",
        name="Rigzone Latest News",
        language="en",
        poll_interval_seconds=600,  # 10 minutes - industry news
        jitter_seconds=30,
    ),
}


class OilNewsPoller(NewsPoller):
    """Async RSS feed poller for oil and energy news.

    Extends NewsPoller with oil-specific feed configurations.
    Uses the same rate limiting, deduplication, and backoff mechanisms.

    Example:
        poller = OilNewsPoller()

        # Poll all oil feeds
        items = await poller.poll_all()
        for item in items:
            print(f"{item.source}: {item.title}")

        await poller.close()

    Attributes:
        feeds: Dict of oil feed configurations.
        states: Dict of feed runtime states.
        dedup_cache: Content deduplication cache.
        rate_limiter: Per-feed rate limiter.
    """

    def __init__(
        self,
        feeds: dict[FeedSource, FeedConfig] | None = None,
        http_timeout: float = 30.0,
    ) -> None:
        """Initialize the oil news poller.

        Args:
            feeds: Feed configurations. Defaults to a copy of OIL_FEEDS.
            http_timeout: HTTP request timeout in seconds.
        """
        # Use oil feeds as default instead of central bank feeds
        effective_feeds = dict(feeds) if feeds else dict(OIL_FEEDS)
        super().__init__(feeds=effective_feeds, http_timeout=http_timeout)

    def get_oil_feed_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all oil feeds.

        Returns:
            Dict of feed statuses keyed by source name.
        """
        return self.get_feed_status()


async def poll_oil_feeds_once(
    sources: list[FeedSource] | None = None,
) -> list[NewsItem]:
    """Convenience function to poll oil feeds once.

    Creates a temporary poller, polls specified feeds, and cleans up.

    Args:
        sources: List of oil feeds to poll. Defaults to all configured oil feeds.

    Returns:
        List of new news items.
    """
    poller = OilNewsPoller()
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
