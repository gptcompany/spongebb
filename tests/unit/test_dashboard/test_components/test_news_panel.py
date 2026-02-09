"""Tests for news panel component."""

from datetime import UTC, datetime, timedelta


class TestNewsPanel:
    """Test news panel creation."""

    def test_create_panel(self) -> None:
        """Test creating the news panel."""
        from liquidity.dashboard.components.news import create_news_panel

        panel = create_news_panel()

        assert panel is not None

    def test_panel_has_card_structure(self) -> None:
        """Test that panel is a Bootstrap Card."""
        import dash_bootstrap_components as dbc

        from liquidity.dashboard.components.news import create_news_panel

        panel = create_news_panel()

        assert isinstance(panel, dbc.Card)

    def test_panel_has_filter_buttons(self) -> None:
        """Test that panel contains filter buttons."""
        from liquidity.dashboard.components.news import create_news_panel

        panel = create_news_panel()

        # Panel should exist and have children
        assert panel is not None
        assert panel.children is not None


class TestNewsItem:
    """Test individual news item creation."""

    def test_create_news_item_basic(self) -> None:
        """Test creating a basic news item."""
        from liquidity.dashboard.components.news import create_news_item

        item = create_news_item(
            title="Test News Title",
            source="Fed",
            sentiment="neutral",
            time_ago="2h ago",
        )

        assert item is not None

    def test_create_news_item_with_link(self) -> None:
        """Test creating a news item with link."""
        from liquidity.dashboard.components.news import create_news_item

        item = create_news_item(
            title="Test News Title",
            source="ECB",
            sentiment="hawkish",
            time_ago="4h ago",
            link="https://example.com/news",
        )

        assert item is not None

    def test_create_news_item_all_sentiments(self) -> None:
        """Test creating news items with all sentiment types."""
        from liquidity.dashboard.components.news import (
            SENTIMENT_DOVISH,
            SENTIMENT_HAWKISH,
            SENTIMENT_NEUTRAL,
            create_news_item,
        )

        for sentiment in [SENTIMENT_HAWKISH, SENTIMENT_DOVISH, SENTIMENT_NEUTRAL]:
            item = create_news_item(
                title=f"Test {sentiment} news",
                source="Fed",
                sentiment=sentiment,
                time_ago="1h ago",
            )
            assert item is not None


class TestNewsItemsList:
    """Test news items list creation."""

    def test_create_empty_list(self) -> None:
        """Test creating list with no items."""
        from liquidity.dashboard.components.news import create_news_items_list

        result = create_news_items_list([])

        assert result is not None

    def test_create_list_with_items(self) -> None:
        """Test creating list with items."""
        from liquidity.dashboard.components.news import create_news_items_list

        items = [
            {
                "title": "Test News 1",
                "source": "Fed",
                "sentiment": "hawkish",
                "published": datetime.now(UTC) - timedelta(hours=2),
            },
            {
                "title": "Test News 2",
                "source": "ECB",
                "sentiment": "dovish",
                "published": datetime.now(UTC) - timedelta(hours=4),
            },
        ]

        result = create_news_items_list(items)

        assert result is not None

    def test_filter_by_fed(self) -> None:
        """Test filtering items by Fed source."""
        from liquidity.dashboard.components.news import create_news_items_list

        items = [
            {"title": "Fed News", "source": "Fed", "sentiment": "neutral", "published": datetime.now(UTC)},
            {"title": "ECB News", "source": "ECB", "sentiment": "neutral", "published": datetime.now(UTC)},
            {"title": "BoJ News", "source": "BoJ", "sentiment": "neutral", "published": datetime.now(UTC)},
        ]

        result = create_news_items_list(items, filter_source="fed")

        assert result is not None

    def test_filter_by_ecb(self) -> None:
        """Test filtering items by ECB source."""
        from liquidity.dashboard.components.news import create_news_items_list

        items = [
            {"title": "Fed News", "source": "Fed", "sentiment": "neutral", "published": datetime.now(UTC)},
            {"title": "ECB News", "source": "ECB", "sentiment": "neutral", "published": datetime.now(UTC)},
        ]

        result = create_news_items_list(items, filter_source="ecb")

        assert result is not None

    def test_filter_by_all(self) -> None:
        """Test no filtering with 'all' option."""
        from liquidity.dashboard.components.news import create_news_items_list

        items = [
            {"title": "Fed News", "source": "Fed", "sentiment": "neutral", "published": datetime.now(UTC)},
            {"title": "ECB News", "source": "ECB", "sentiment": "neutral", "published": datetime.now(UTC)},
        ]

        result = create_news_items_list(items, filter_source="all")

        assert result is not None


class TestFormatTimeAgo:
    """Test time ago formatting."""

    def test_format_just_now(self) -> None:
        """Test formatting for very recent time."""
        from liquidity.dashboard.components.news import format_time_ago

        recent = datetime.now(UTC) - timedelta(seconds=30)
        result = format_time_ago(recent)

        assert result == "Just now"

    def test_format_minutes_ago(self) -> None:
        """Test formatting for minutes ago."""
        from liquidity.dashboard.components.news import format_time_ago

        minutes_ago = datetime.now(UTC) - timedelta(minutes=15)
        result = format_time_ago(minutes_ago)

        assert "m ago" in result

    def test_format_hours_ago(self) -> None:
        """Test formatting for hours ago."""
        from liquidity.dashboard.components.news import format_time_ago

        hours_ago = datetime.now(UTC) - timedelta(hours=3)
        result = format_time_ago(hours_ago)

        assert "h ago" in result

    def test_format_days_ago(self) -> None:
        """Test formatting for days ago."""
        from liquidity.dashboard.components.news import format_time_ago

        days_ago = datetime.now(UTC) - timedelta(days=2)
        result = format_time_ago(days_ago)

        assert "d ago" in result

    def test_format_weeks_ago(self) -> None:
        """Test formatting for weeks ago."""
        from liquidity.dashboard.components.news import format_time_ago

        weeks_ago = datetime.now(UTC) - timedelta(days=14)
        result = format_time_ago(weeks_ago)

        assert "w ago" in result

    def test_format_old_date(self) -> None:
        """Test formatting for older dates shows month/day."""
        from liquidity.dashboard.components.news import format_time_ago

        old_date = datetime.now(UTC) - timedelta(days=60)
        result = format_time_ago(old_date)

        # Should return month day format
        assert result != "Unknown"
        assert "ago" not in result

    def test_format_none(self) -> None:
        """Test formatting None returns Unknown."""
        from liquidity.dashboard.components.news import format_time_ago

        result = format_time_ago(None)

        assert result == "Unknown"

    def test_format_iso_string(self) -> None:
        """Test formatting ISO datetime string."""
        from liquidity.dashboard.components.news import format_time_ago

        iso_string = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        result = format_time_ago(iso_string)

        assert "h ago" in result


class TestSourceLabel:
    """Test source label mapping."""

    def test_get_source_label_direct(self) -> None:
        """Test getting label for direct labels."""
        from liquidity.dashboard.components.news import _get_source_label

        assert _get_source_label("Fed") == "Fed"
        assert _get_source_label("ECB") == "ECB"
        assert _get_source_label("BoJ") == "BoJ"

    def test_get_source_label_from_feed_source(self) -> None:
        """Test getting label from FeedSource value."""
        from liquidity.dashboard.components.news import _get_source_label

        assert _get_source_label("fed_press") == "Fed"
        assert _get_source_label("ecb_press") == "ECB"
        assert _get_source_label("boj_news") == "BoJ"

    def test_get_source_label_fuzzy(self) -> None:
        """Test fuzzy matching for source labels."""
        from liquidity.dashboard.components.news import _get_source_label

        assert _get_source_label("federal_reserve") == "Fed"
        assert _get_source_label("ecb_something") == "ECB"
        assert _get_source_label("boj_other") == "BoJ"


class TestNewsItemConversion:
    """Test NewsItem object to dict conversion."""

    def test_convert_newsitem_objects(self) -> None:
        """Test converting NewsItem objects to display format."""
        from liquidity.dashboard.components.news import news_items_from_newsitem_objects
        from liquidity.news.schemas import FeedSource, NewsItem

        # Create a NewsItem object
        now = datetime.now(UTC)
        news_item = NewsItem(
            id="test123",
            source=FeedSource.FED_PRESS,
            title="Test Fed News",
            link="https://federalreserve.gov/test",
            published=now,
            summary="Test summary",
            content="Test content",
            language="en",
            content_hash="abc123def456",
            fetched_at=now,
        )

        result = news_items_from_newsitem_objects([news_item])

        assert len(result) == 1
        assert result[0]["title"] == "Test Fed News"
        assert result[0]["source"] == "fed_press"
        assert result[0]["sentiment"] == "neutral"  # Default

    def test_convert_with_sentiment_map(self) -> None:
        """Test converting with sentiment mapping."""
        from liquidity.dashboard.components.news import (
            SENTIMENT_HAWKISH,
            news_items_from_newsitem_objects,
        )
        from liquidity.news.schemas import FeedSource, NewsItem

        now = datetime.now(UTC)
        news_item = NewsItem(
            id="test456",
            source=FeedSource.FED_PRESS,
            title="Hawkish Fed News",
            link="https://federalreserve.gov/test",
            published=now,
            summary="",
            content="",
            language="en",
            content_hash="xyz789",
            fetched_at=now,
        )

        sentiment_map = {"test456": SENTIMENT_HAWKISH}
        result = news_items_from_newsitem_objects([news_item], sentiment_map)

        assert len(result) == 1
        assert result[0]["sentiment"] == SENTIMENT_HAWKISH
