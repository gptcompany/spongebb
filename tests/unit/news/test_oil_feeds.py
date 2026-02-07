"""Unit tests for oil RSS feed aggregator.

Tests OilNewsPoller, OIL_FEEDS configuration, and oil feed parsing
with mocked feedparser responses.

Run with: uv run pytest tests/unit/news/test_oil_feeds.py -v
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from liquidity.news.oil_feeds import (
    OIL_FEEDS,
    OilNewsPoller,
    poll_oil_feeds_once,
)
from liquidity.news.schemas import (
    FeedConfig,
    FeedSource,
    NewsItem,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def oil_poller() -> OilNewsPoller:
    """Create an OilNewsPoller instance."""
    return OilNewsPoller()


@pytest.fixture
def mock_oilprice_rss() -> str:
    """Sample RSS XML response from OilPrice.com."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>OilPrice.com</title>
    <link>https://oilprice.com</link>
    <item>
      <title>Oil Prices Surge on OPEC+ Supply Concerns</title>
      <link>https://oilprice.com/Energy/Oil-Prices/Oil-Prices-Surge-OPEC-Supply.html</link>
      <pubDate>Fri, 07 Feb 2026 08:30:00 GMT</pubDate>
      <description>Crude oil prices jumped 3% today as OPEC+ signals...</description>
    </item>
    <item>
      <title>US Shale Production Hits New Record</title>
      <link>https://oilprice.com/Energy/Crude-Oil/US-Shale-Production-Record.html</link>
      <pubDate>Thu, 06 Feb 2026 14:00:00 GMT</pubDate>
      <description>American shale producers continue to defy expectations...</description>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def mock_eia_twip_rss() -> str:
    """Sample RSS XML response from EIA TWIP."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>This Week In Petroleum</title>
    <link>https://www.eia.gov/petroleum/weekly/</link>
    <item>
      <title>This Week in Petroleum - February 5, 2026</title>
      <link>https://www.eia.gov/petroleum/weekly/archive/2026/260205/includes/analysis_print.php</link>
      <pubDate>Wed, 05 Feb 2026 10:30:00 EST</pubDate>
      <description>U.S. crude oil inventories decreased by 2.3 million barrels...</description>
    </item>
  </channel>
</rss>"""


@pytest.fixture
def mock_rigzone_rss() -> str:
    """Sample RSS XML response from Rigzone."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Rigzone - Latest News</title>
    <link>https://www.rigzone.com</link>
    <item>
      <title>Offshore Drilling Activity Rebounds in Gulf of Mexico</title>
      <link>https://www.rigzone.com/news/offshore_drilling_rebounds-07-feb-2026.asp</link>
      <pubDate>Fri, 07 Feb 2026 09:00:00 GMT</pubDate>
      <description>Rig count increases as operators resume drilling programs...</description>
    </item>
    <item>
      <title>New Deepwater Discovery Offshore Brazil</title>
      <link>https://www.rigzone.com/news/brazil_deepwater_discovery-06-feb-2026.asp</link>
      <pubDate>Thu, 06 Feb 2026 16:30:00 GMT</pubDate>
      <description>Major oil company announces significant find in Santos Basin...</description>
    </item>
  </channel>
</rss>"""


# =============================================================================
# OIL_FEEDS Configuration Tests
# =============================================================================


class TestOilFeedsConfig:
    """Tests for OIL_FEEDS configuration."""

    def test_oil_feeds_has_all_expected_sources(self) -> None:
        """Test that all expected oil sources are configured."""
        expected_sources = {
            FeedSource.OILPRICE_NEWS,
            FeedSource.EIA_TWIP,
            FeedSource.RIGZONE_NEWS,
        }

        assert set(OIL_FEEDS.keys()) == expected_sources

    def test_oilprice_config(self) -> None:
        """Test OilPrice.com feed configuration."""
        config = OIL_FEEDS[FeedSource.OILPRICE_NEWS]

        assert config.source == FeedSource.OILPRICE_NEWS
        assert str(config.url) == "https://oilprice.com/rss/main"
        assert config.name == "OilPrice.com Latest News"
        assert config.poll_interval_seconds == 300  # 5 minutes
        assert config.language == "en"
        assert config.enabled is True

    def test_eia_twip_config(self) -> None:
        """Test EIA TWIP feed configuration."""
        config = OIL_FEEDS[FeedSource.EIA_TWIP]

        assert config.source == FeedSource.EIA_TWIP
        assert str(config.url) == "https://www.eia.gov/petroleum/weekly/feed.xml"
        assert config.name == "EIA This Week in Petroleum"
        assert config.poll_interval_seconds == 3600  # 1 hour
        assert config.language == "en"

    def test_rigzone_config(self) -> None:
        """Test Rigzone feed configuration."""
        config = OIL_FEEDS[FeedSource.RIGZONE_NEWS]

        assert config.source == FeedSource.RIGZONE_NEWS
        assert str(config.url) == "https://www.rigzone.com/news/rss/rigzone_latest.aspx"
        assert config.name == "Rigzone Latest News"
        assert config.poll_interval_seconds == 600  # 10 minutes
        assert config.language == "en"

    def test_all_configs_are_valid_feed_configs(self) -> None:
        """Test that all oil feed configs are valid FeedConfig instances."""
        for source, config in OIL_FEEDS.items():
            assert isinstance(config, FeedConfig)
            assert config.source == source
            assert config.poll_interval_seconds >= 60  # Minimum poll interval


# =============================================================================
# OilNewsPoller Tests
# =============================================================================


class TestOilNewsPoller:
    """Tests for OilNewsPoller class."""

    def test_init_uses_oil_feeds_by_default(self, oil_poller: OilNewsPoller) -> None:
        """Test that OilNewsPoller uses OIL_FEEDS by default."""
        assert set(oil_poller.feeds.keys()) == set(OIL_FEEDS.keys())

    def test_init_creates_states_for_all_oil_feeds(
        self, oil_poller: OilNewsPoller
    ) -> None:
        """Test that init creates state for each oil feed."""
        for source in OIL_FEEDS:
            assert source in oil_poller.states
            assert oil_poller.states[source].source == source

    def test_init_with_custom_feeds(self) -> None:
        """Test OilNewsPoller with custom feed configuration."""
        custom_feeds = {
            FeedSource.OILPRICE_NEWS: OIL_FEEDS[FeedSource.OILPRICE_NEWS],
        }
        poller = OilNewsPoller(feeds=custom_feeds)

        assert len(poller.feeds) == 1
        assert FeedSource.OILPRICE_NEWS in poller.feeds

    def test_get_oil_feed_status(self, oil_poller: OilNewsPoller) -> None:
        """Test get_oil_feed_status returns correct structure."""
        status = oil_poller.get_oil_feed_status()

        assert len(status) == len(OIL_FEEDS)
        for source in OIL_FEEDS:
            assert source.value in status
            feed_status = status[source.value]
            assert "name" in feed_status
            assert "enabled" in feed_status
            assert "url" in feed_status

    @pytest.mark.asyncio
    async def test_poll_oilprice_success(
        self, oil_poller: OilNewsPoller, mock_oilprice_rss: str
    ) -> None:
        """Test successful OilPrice.com feed poll."""
        source = FeedSource.OILPRICE_NEWS

        mock_response = MagicMock()
        mock_response.text = mock_oilprice_rss
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            oil_poller, "_get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            items = await oil_poller.poll_feed(source)

        assert len(items) == 2
        assert all(isinstance(item, NewsItem) for item in items)
        assert all(item.source == FeedSource.OILPRICE_NEWS for item in items)
        assert "OPEC" in items[0].title or "Shale" in items[0].title

    @pytest.mark.asyncio
    async def test_poll_eia_twip_success(
        self, oil_poller: OilNewsPoller, mock_eia_twip_rss: str
    ) -> None:
        """Test successful EIA TWIP feed poll."""
        source = FeedSource.EIA_TWIP

        mock_response = MagicMock()
        mock_response.text = mock_eia_twip_rss
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            oil_poller, "_get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            items = await oil_poller.poll_feed(source)

        assert len(items) == 1
        assert items[0].source == FeedSource.EIA_TWIP
        assert "This Week in Petroleum" in items[0].title

    @pytest.mark.asyncio
    async def test_poll_rigzone_success(
        self, oil_poller: OilNewsPoller, mock_rigzone_rss: str
    ) -> None:
        """Test successful Rigzone feed poll."""
        source = FeedSource.RIGZONE_NEWS

        mock_response = MagicMock()
        mock_response.text = mock_rigzone_rss
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            oil_poller, "_get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            items = await oil_poller.poll_feed(source)

        assert len(items) == 2
        assert all(item.source == FeedSource.RIGZONE_NEWS for item in items)

    @pytest.mark.asyncio
    async def test_poll_all_oil_feeds(
        self,
        mock_oilprice_rss: str,
        mock_eia_twip_rss: str,
        mock_rigzone_rss: str,
    ) -> None:
        """Test polling all oil feeds at once."""
        poller = OilNewsPoller()

        # Create different responses for different URLs
        async def mock_get(url: str) -> MagicMock:
            response = MagicMock()
            response.raise_for_status = MagicMock()

            url_str = str(url)
            if "oilprice.com" in url_str:
                response.text = mock_oilprice_rss
            elif "eia.gov" in url_str:
                response.text = mock_eia_twip_rss
            else:  # rigzone
                response.text = mock_rigzone_rss

            return response

        with patch.object(
            poller, "_get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_get_client.return_value = mock_client

            items = await poller.poll_all()

        await poller.close()

        # Should have items from all feeds (5 total: 2 + 1 + 2)
        assert len(items) == 5

        # Check we have items from each source
        sources = {item.source for item in items}
        assert FeedSource.OILPRICE_NEWS in sources
        assert FeedSource.EIA_TWIP in sources
        assert FeedSource.RIGZONE_NEWS in sources

    @pytest.mark.asyncio
    async def test_deduplication_across_polls(
        self, oil_poller: OilNewsPoller, mock_oilprice_rss: str
    ) -> None:
        """Test that duplicate items are filtered across polls."""
        source = FeedSource.OILPRICE_NEWS

        mock_response = MagicMock()
        mock_response.text = mock_oilprice_rss
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            oil_poller, "_get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            # First poll
            items1 = await oil_poller.poll_feed(source)
            assert len(items1) == 2

            # Reset rate limiter to allow immediate repoll
            oil_poller.rate_limiter._last_poll.pop(source)

            # Second poll - should be deduped
            items2 = await oil_poller.poll_feed(source)
            assert len(items2) == 0

    @pytest.mark.asyncio
    async def test_close_cleans_up_client(self, oil_poller: OilNewsPoller) -> None:
        """Test that close properly cleans up HTTP client."""
        await oil_poller._get_client()
        assert oil_poller._client is not None

        await oil_poller.close()
        assert oil_poller._client is None


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestPollOilFeedsOnce:
    """Tests for poll_oil_feeds_once convenience function."""

    @pytest.mark.asyncio
    async def test_poll_oil_feeds_once_all(self, mock_oilprice_rss: str) -> None:
        """Test poll_oil_feeds_once with all feeds."""
        mock_response = MagicMock()
        mock_response.text = mock_oilprice_rss
        mock_response.raise_for_status = MagicMock()

        with patch(
            "liquidity.news.oil_feeds.OilNewsPoller._get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            items = await poll_oil_feeds_once()

        # Should poll all feeds and get items
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_poll_oil_feeds_once_specific_sources(
        self, mock_oilprice_rss: str
    ) -> None:
        """Test poll_oil_feeds_once with specific sources."""
        mock_response = MagicMock()
        mock_response.text = mock_oilprice_rss
        mock_response.raise_for_status = MagicMock()

        with patch(
            "liquidity.news.oil_feeds.OilNewsPoller._get_client", new_callable=AsyncMock
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            items = await poll_oil_feeds_once(sources=[FeedSource.OILPRICE_NEWS])

        # Should only poll the specified source
        assert all(item.source == FeedSource.OILPRICE_NEWS for item in items)


# =============================================================================
# FeedSource Enum Tests
# =============================================================================


class TestFeedSourceEnum:
    """Tests for oil-related FeedSource enum values."""

    def test_oil_source_values(self) -> None:
        """Test that oil source enum values are correct."""
        assert FeedSource.OILPRICE_NEWS.value == "oilprice_news"
        assert FeedSource.EIA_TWIP.value == "eia_twip"
        assert FeedSource.RIGZONE_NEWS.value == "rigzone_news"

    def test_oil_sources_are_string_enums(self) -> None:
        """Test that oil sources work as strings."""
        assert str(FeedSource.OILPRICE_NEWS) == "FeedSource.OILPRICE_NEWS"
        assert FeedSource.OILPRICE_NEWS == "oilprice_news"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
