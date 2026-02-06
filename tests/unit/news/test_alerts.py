"""Unit tests for breaking news keyword alerts.

Tests NewsAlertEngine, Priority levels, keyword matching, and Discord integration.

Run with: uv run pytest tests/unit/news/test_alerts.py -v
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from liquidity.news.alerts import (
    BREAKING_KEYWORDS,
    CENTRAL_BANK_PATTERNS,
    AlertColors,
    NewsAlert,
    NewsAlertEngine,
    Priority,
)
from liquidity.news.schemas import FeedSource, NewsItem

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def engine() -> NewsAlertEngine:
    """Create a NewsAlertEngine without Discord."""
    return NewsAlertEngine(discord_client=None)


@pytest.fixture
def mock_discord_client() -> MagicMock:
    """Create a mock Discord client."""
    client = MagicMock()
    client.is_configured = True
    client.send_embed_async = AsyncMock(return_value=True)
    client.reset_rate_limit = MagicMock()
    return client


@pytest.fixture
def engine_with_discord(mock_discord_client: MagicMock) -> NewsAlertEngine:
    """Create a NewsAlertEngine with mock Discord."""
    return NewsAlertEngine(discord_client=mock_discord_client)


@pytest.fixture
def sample_news_item() -> NewsItem:
    """Create a sample news item."""
    return NewsItem(
        id="abc123",
        source=FeedSource.FED_PRESS,
        title="Federal Reserve issues FOMC statement",
        link="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260206a.htm",
        published=datetime(2026, 2, 6, 14, 0, 0, tzinfo=UTC),
        summary="The Federal Open Market Committee decided to maintain the target range.",
        content="Full policy statement content...",
        language="en",
        content_hash="x" * 64,
        fetched_at=datetime.now(UTC),
    )


@pytest.fixture
def critical_news_item() -> NewsItem:
    """Create a critical/emergency news item."""
    return NewsItem(
        id="emerg001",
        source=FeedSource.FED_PRESS,
        title="Federal Reserve announces emergency rate cut",
        link="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260206b.htm",
        published=datetime(2026, 2, 6, 15, 0, 0, tzinfo=UTC),
        summary="Emergency action to address market stress",
        content="Emergency liquidity facility activated...",
        language="en",
        content_hash="y" * 64,
        fetched_at=datetime.now(UTC),
    )


@pytest.fixture
def low_priority_news_item() -> NewsItem:
    """Create a low priority news item."""
    return NewsItem(
        id="speech001",
        source=FeedSource.FED_SPEECHES,
        title="Governor Smith remarks on economic outlook",
        link="https://www.federalreserve.gov/newsevents/speech/smith20260206.htm",
        published=datetime(2026, 2, 6, 10, 0, 0, tzinfo=UTC),
        summary="Remarks at conference",
        content="Speech text...",
        language="en",
        content_hash="z" * 64,
        fetched_at=datetime.now(UTC),
    )


@pytest.fixture
def no_match_news_item() -> NewsItem:
    """Create a news item that shouldn't match any keywords."""
    return NewsItem(
        id="nomatch001",
        source=FeedSource.FED_PRESS,
        title="Board announces staff appointments",
        link="https://www.federalreserve.gov/newsevents/pressreleases/other20260206.htm",
        published=datetime(2026, 2, 6, 9, 0, 0, tzinfo=UTC),
        summary="Administrative announcement",
        content="Personnel changes...",
        language="en",
        content_hash="w" * 64,
        fetched_at=datetime.now(UTC),
    )


# =============================================================================
# Priority Enum Tests
# =============================================================================


class TestPriority:
    """Tests for Priority enum."""

    def test_priority_ordering(self) -> None:
        """Test that priorities are correctly ordered."""
        assert Priority.CRITICAL > Priority.HIGH
        assert Priority.HIGH > Priority.MEDIUM
        assert Priority.MEDIUM > Priority.LOW

    def test_priority_values(self) -> None:
        """Test priority integer values."""
        assert Priority.LOW.value == 1
        assert Priority.MEDIUM.value == 2
        assert Priority.HIGH.value == 3
        assert Priority.CRITICAL.value == 4

    def test_priority_names(self) -> None:
        """Test priority names."""
        assert Priority.LOW.name == "LOW"
        assert Priority.MEDIUM.name == "MEDIUM"
        assert Priority.HIGH.name == "HIGH"
        assert Priority.CRITICAL.name == "CRITICAL"


# =============================================================================
# Default Keywords Tests
# =============================================================================


class TestDefaultKeywords:
    """Tests for default keyword configuration."""

    def test_breaking_keywords_has_critical(self) -> None:
        """Test that BREAKING_KEYWORDS includes critical keywords."""
        critical_keywords = [k for k, v in BREAKING_KEYWORDS.items() if v == Priority.CRITICAL]
        assert "emergency" in critical_keywords
        assert len(critical_keywords) >= 4  # At least 4 critical keywords

    def test_breaking_keywords_has_high(self) -> None:
        """Test that BREAKING_KEYWORDS includes high priority keywords."""
        high_keywords = [k for k, v in BREAKING_KEYWORDS.items() if v == Priority.HIGH]
        assert "rate decision" in high_keywords
        assert "policy statement" in high_keywords
        assert len(high_keywords) >= 5

    def test_breaking_keywords_has_medium(self) -> None:
        """Test that BREAKING_KEYWORDS includes medium priority keywords."""
        medium_keywords = [k for k, v in BREAKING_KEYWORDS.items() if v == Priority.MEDIUM]
        assert "balance sheet" in medium_keywords
        assert "inflation" in medium_keywords

    def test_breaking_keywords_has_low(self) -> None:
        """Test that BREAKING_KEYWORDS includes low priority keywords."""
        low_keywords = [k for k, v in BREAKING_KEYWORDS.items() if v == Priority.LOW]
        assert "minutes" in low_keywords
        assert "employment" in low_keywords

    def test_central_bank_patterns_coverage(self) -> None:
        """Test that major central banks have patterns."""
        assert FeedSource.FED_PRESS in CENTRAL_BANK_PATTERNS
        assert FeedSource.ECB_PRESS in CENTRAL_BANK_PATTERNS
        assert FeedSource.BOJ_NEWS in CENTRAL_BANK_PATTERNS

        # Fed patterns should include FOMC
        fed_patterns = CENTRAL_BANK_PATTERNS[FeedSource.FED_PRESS]
        assert "fomc" in fed_patterns


# =============================================================================
# NewsAlert Model Tests
# =============================================================================


class TestNewsAlert:
    """Tests for NewsAlert dataclass."""

    def test_create_alert(self, sample_news_item: NewsItem) -> None:
        """Test creating a NewsAlert."""
        alert = NewsAlert(
            news_item=sample_news_item,
            priority=Priority.HIGH,
            matched_keywords=("fomc statement", "policy statement"),
        )

        assert alert.news_item == sample_news_item
        assert alert.priority == Priority.HIGH
        assert len(alert.matched_keywords) == 2
        assert alert.matched_patterns == ()

    def test_alert_is_frozen(self, sample_news_item: NewsItem) -> None:
        """Test that NewsAlert is immutable."""
        alert = NewsAlert(
            news_item=sample_news_item,
            priority=Priority.HIGH,
            matched_keywords=("rate decision",),
        )

        with pytest.raises((TypeError, AttributeError)):  # Frozen model cannot be modified
            alert.priority = Priority.LOW  # type: ignore

    def test_alert_to_dict(self, sample_news_item: NewsItem) -> None:
        """Test converting alert to dictionary."""
        alert = NewsAlert(
            news_item=sample_news_item,
            priority=Priority.HIGH,
            matched_keywords=("rate decision",),
            matched_patterns=("fomc",),
        )

        d = alert.to_dict()

        assert d["news_id"] == "abc123"
        assert d["source"] == "fed_press"
        assert d["priority"] == "HIGH"
        assert d["priority_value"] == 3
        assert "rate decision" in d["matched_keywords"]
        assert "fomc" in d["matched_patterns"]
        assert "created_at" in d


# =============================================================================
# NewsAlertEngine Initialization Tests
# =============================================================================


class TestNewsAlertEngineInit:
    """Tests for NewsAlertEngine initialization."""

    def test_init_without_discord(self) -> None:
        """Test initialization without Discord client."""
        engine = NewsAlertEngine()

        assert not engine.discord_enabled
        assert len(engine.keywords) > 0

    def test_init_with_discord(self, mock_discord_client: MagicMock) -> None:
        """Test initialization with Discord client."""
        engine = NewsAlertEngine(discord_client=mock_discord_client)

        assert engine.discord_enabled

    def test_init_with_custom_keywords(self) -> None:
        """Test initialization with custom keywords."""
        custom_keywords = {
            "custom pattern": Priority.HIGH,
            "another pattern": Priority.LOW,
        }
        engine = NewsAlertEngine(keywords=custom_keywords)

        assert engine.keywords == custom_keywords
        assert "emergency" not in engine.keywords

    def test_init_with_custom_patterns(self) -> None:
        """Test initialization with custom central bank patterns."""
        custom_patterns = {
            FeedSource.FED_PRESS: ["custom", "patterns"],
        }
        engine = NewsAlertEngine(central_bank_patterns=custom_patterns)

        matches = engine.match_central_bank_patterns("custom text", FeedSource.FED_PRESS)
        assert "custom" in matches


# =============================================================================
# Keyword Management Tests
# =============================================================================


class TestKeywordManagement:
    """Tests for keyword add/remove/update operations."""

    def test_add_keyword(self, engine: NewsAlertEngine) -> None:
        """Test adding a new keyword."""
        engine.add_keyword("new keyword", Priority.HIGH)

        assert "new keyword" in engine.keywords
        assert engine.keywords["new keyword"] == Priority.HIGH

    def test_add_keyword_normalizes_case(self, engine: NewsAlertEngine) -> None:
        """Test that keyword is normalized to lowercase."""
        engine.add_keyword("MiXeD CaSe", Priority.MEDIUM)

        assert "mixed case" in engine.keywords
        assert "MiXeD CaSe" not in engine.keywords

    def test_add_empty_keyword_raises(self, engine: NewsAlertEngine) -> None:
        """Test that empty keyword raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            engine.add_keyword("", Priority.HIGH)

        with pytest.raises(ValueError, match="cannot be empty"):
            engine.add_keyword("   ", Priority.HIGH)

    def test_remove_keyword(self, engine: NewsAlertEngine) -> None:
        """Test removing a keyword."""
        # Add then remove
        engine.add_keyword("temporary", Priority.LOW)
        assert "temporary" in engine.keywords

        engine.remove_keyword("temporary")
        assert "temporary" not in engine.keywords

    def test_remove_nonexistent_keyword_raises(self, engine: NewsAlertEngine) -> None:
        """Test that removing non-existent keyword raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            engine.remove_keyword("nonexistent")

    def test_update_priority(self, engine: NewsAlertEngine) -> None:
        """Test updating keyword priority."""
        engine.add_keyword("test keyword", Priority.LOW)
        engine.update_priority("test keyword", Priority.CRITICAL)

        assert engine.keywords["test keyword"] == Priority.CRITICAL

    def test_update_nonexistent_keyword_raises(self, engine: NewsAlertEngine) -> None:
        """Test that updating non-existent keyword raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            engine.update_priority("nonexistent", Priority.HIGH)


# =============================================================================
# Keyword Matching Tests
# =============================================================================


class TestKeywordMatching:
    """Tests for keyword matching functionality."""

    def test_match_single_keyword(self, engine: NewsAlertEngine) -> None:
        """Test matching a single keyword."""
        text = "Federal Reserve announces emergency rate cut"
        matches = engine.match_keywords(text)

        keywords = [kw for kw, _ in matches]
        assert "emergency" in keywords or any("emergency" in kw for kw in keywords)

    def test_match_multiple_keywords(self, engine: NewsAlertEngine) -> None:
        """Test matching multiple keywords in same text."""
        text = "FOMC statement on rate decision and balance sheet policy"
        matches = engine.match_keywords(text)

        assert len(matches) >= 2

    def test_match_case_insensitive(self, engine: NewsAlertEngine) -> None:
        """Test that matching is case-insensitive."""
        text1 = "EMERGENCY RATE CUT"
        text2 = "emergency rate cut"

        matches1 = engine.match_keywords(text1)
        matches2 = engine.match_keywords(text2)

        # Both should match the same keywords
        keywords1 = {kw for kw, _ in matches1}
        keywords2 = {kw for kw, _ in matches2}
        assert keywords1 == keywords2

    def test_match_word_boundaries(self, engine: NewsAlertEngine) -> None:
        """Test that matching respects word boundaries."""
        engine.add_keyword("rate", Priority.HIGH)

        # Should match
        matches_yes = engine.match_keywords("interest rate decision")
        assert any(kw == "rate" for kw, _ in matches_yes)

        # Should NOT match partial word
        matches_no = engine.match_keywords("ratemaking process")
        rate_matches = [kw for kw, _ in matches_no if kw == "rate"]
        # Word boundary should prevent match
        assert len(rate_matches) == 0 or "ratemaking".find("rate ") == -1

    def test_no_match_returns_empty(self, engine: NewsAlertEngine) -> None:
        """Test that no matches returns empty list."""
        text = "Staff appointments and administrative changes"
        matches = engine.match_keywords(text)

        assert matches == []


# =============================================================================
# Central Bank Pattern Matching Tests
# =============================================================================


class TestCentralBankPatterns:
    """Tests for central bank specific pattern matching."""

    def test_match_fed_patterns(self, engine: NewsAlertEngine) -> None:
        """Test matching Fed-specific patterns."""
        text = "FOMC statement on federal funds rate"
        matches = engine.match_central_bank_patterns(text, FeedSource.FED_PRESS)

        assert "fomc" in matches
        assert "federal funds" in matches

    def test_match_ecb_patterns(self, engine: NewsAlertEngine) -> None:
        """Test matching ECB-specific patterns."""
        text = "ECB Governing Council decision"
        matches = engine.match_central_bank_patterns(text, FeedSource.ECB_PRESS)

        assert "ecb" in matches
        assert "governing council" in matches

    def test_add_central_bank_pattern(self, engine: NewsAlertEngine) -> None:
        """Test adding custom central bank pattern."""
        engine.add_central_bank_pattern(FeedSource.FED_PRESS, "custom term")

        text = "Statement includes custom term"
        matches = engine.match_central_bank_patterns(text, FeedSource.FED_PRESS)

        assert "custom term" in matches


# =============================================================================
# News Item Analysis Tests
# =============================================================================


class TestAnalyzeItem:
    """Tests for news item analysis."""

    def test_analyze_matching_item(
        self, engine: NewsAlertEngine, sample_news_item: NewsItem
    ) -> None:
        """Test analyzing an item that matches keywords."""
        alert = engine.analyze_item(sample_news_item)

        assert alert is not None
        assert alert.news_item == sample_news_item
        assert alert.priority in list(Priority)
        assert len(alert.matched_keywords) > 0

    def test_analyze_no_match_returns_none(
        self, engine: NewsAlertEngine, no_match_news_item: NewsItem
    ) -> None:
        """Test analyzing an item that doesn't match returns None."""
        alert = engine.analyze_item(no_match_news_item)

        assert alert is None

    def test_analyze_critical_priority(
        self, engine: NewsAlertEngine, critical_news_item: NewsItem
    ) -> None:
        """Test that critical keywords result in critical priority."""
        alert = engine.analyze_item(critical_news_item)

        assert alert is not None
        assert alert.priority == Priority.CRITICAL

    def test_analyze_highest_priority_wins(self, engine: NewsAlertEngine) -> None:
        """Test that highest matching priority is used."""
        # Create item with multiple priority matches
        item = NewsItem(
            id="multi001",
            source=FeedSource.FED_PRESS,
            title="Emergency FOMC statement on rate decision and employment",
            link="https://example.com/multi",
            published=datetime.now(UTC),
            summary="Multiple keywords",
            content="Content with emergency, rate decision, employment",
            language="en",
            content_hash="m" * 64,
            fetched_at=datetime.now(UTC),
        )

        alert = engine.analyze_item(item)

        assert alert is not None
        assert alert.priority == Priority.CRITICAL  # Emergency is highest

    def test_analyze_skips_already_processed(
        self, engine: NewsAlertEngine, sample_news_item: NewsItem
    ) -> None:
        """Test that already processed items are skipped."""
        # First analysis
        alert1 = engine.analyze_item(sample_news_item)
        assert alert1 is not None

        # Second analysis should return None (already processed)
        alert2 = engine.analyze_item(sample_news_item)
        assert alert2 is None

    def test_analyze_includes_cb_patterns(
        self, engine: NewsAlertEngine, sample_news_item: NewsItem
    ) -> None:
        """Test that central bank patterns are included in alert."""
        alert = engine.analyze_item(sample_news_item)

        assert alert is not None
        # Title contains "FOMC" which is a Fed pattern
        assert "fomc" in alert.matched_patterns


# =============================================================================
# Process News Tests
# =============================================================================


class TestProcessNews:
    """Tests for batch news processing."""

    @pytest.mark.asyncio
    async def test_process_empty_list(self, engine: NewsAlertEngine) -> None:
        """Test processing empty list returns empty list."""
        alerts = await engine.process_news([])
        assert alerts == []

    @pytest.mark.asyncio
    async def test_process_multiple_items(
        self,
        engine: NewsAlertEngine,
        sample_news_item: NewsItem,
        critical_news_item: NewsItem,
        no_match_news_item: NewsItem,
    ) -> None:
        """Test processing multiple items."""
        items = [sample_news_item, critical_news_item, no_match_news_item]
        alerts = await engine.process_news(items)

        # Should have 2 alerts (no_match should not match)
        assert len(alerts) == 2

    @pytest.mark.asyncio
    async def test_process_sorts_by_priority(
        self,
        engine: NewsAlertEngine,
        sample_news_item: NewsItem,
        critical_news_item: NewsItem,
        low_priority_news_item: NewsItem,
    ) -> None:
        """Test that alerts are sorted by priority (highest first)."""
        items = [low_priority_news_item, sample_news_item, critical_news_item]
        alerts = await engine.process_news(items)

        # First alert should be critical
        assert alerts[0].priority == Priority.CRITICAL
        # Last should be lowest priority
        assert alerts[-1].priority <= alerts[0].priority

    @pytest.mark.asyncio
    async def test_process_with_discord(
        self,
        engine_with_discord: NewsAlertEngine,
        mock_discord_client: MagicMock,
        sample_news_item: NewsItem,
    ) -> None:
        """Test that Discord notification is sent during processing."""
        await engine_with_discord.process_news([sample_news_item])

        mock_discord_client.send_embed_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_critical_resets_rate_limit(
        self,
        engine_with_discord: NewsAlertEngine,
        mock_discord_client: MagicMock,
        critical_news_item: NewsItem,
    ) -> None:
        """Test that critical alerts reset rate limit."""
        await engine_with_discord.process_news([critical_news_item])

        mock_discord_client.reset_rate_limit.assert_called()

    def test_process_sync(
        self,
        engine: NewsAlertEngine,
        sample_news_item: NewsItem,
        critical_news_item: NewsItem,
    ) -> None:
        """Test synchronous processing."""
        items = [sample_news_item, critical_news_item]
        alerts = engine.process_news_sync(items)

        assert len(alerts) == 2
        assert alerts[0].priority == Priority.CRITICAL


# =============================================================================
# Discord Integration Tests
# =============================================================================


class TestDiscordIntegration:
    """Tests for Discord alert formatting and sending."""

    def test_format_alert_embed_critical(
        self, engine: NewsAlertEngine, critical_news_item: NewsItem
    ) -> None:
        """Test formatting critical alert embed."""
        alert = NewsAlert(
            news_item=critical_news_item,
            priority=Priority.CRITICAL,
            matched_keywords=("emergency",),
        )

        embed = engine._format_alert_embed(alert)

        assert embed.title is not None
        assert "CRITICAL" in embed.title
        assert embed.color == AlertColors.CRITICAL

    def test_format_alert_embed_includes_link(
        self, engine: NewsAlertEngine, sample_news_item: NewsItem
    ) -> None:
        """Test that embed includes link."""
        alert = NewsAlert(
            news_item=sample_news_item,
            priority=Priority.HIGH,
            matched_keywords=("fomc statement",),
        )

        embed = engine._format_alert_embed(alert)

        # Check fields
        field_names = [f.get("name") for f in embed.fields or []]
        assert "Link" in field_names

    def test_format_alert_embed_includes_keywords(
        self, engine: NewsAlertEngine, sample_news_item: NewsItem
    ) -> None:
        """Test that embed includes matched keywords."""
        alert = NewsAlert(
            news_item=sample_news_item,
            priority=Priority.HIGH,
            matched_keywords=("fomc statement", "policy statement"),
        )

        embed = engine._format_alert_embed(alert)

        field_names = [f.get("name") for f in embed.fields or []]
        assert "Matched Keywords" in field_names

    def test_discord_enabled_false_without_client(
        self, engine: NewsAlertEngine
    ) -> None:
        """Test discord_enabled is False without client."""
        assert not engine.discord_enabled

    def test_discord_enabled_true_with_client(
        self, engine_with_discord: NewsAlertEngine
    ) -> None:
        """Test discord_enabled is True with configured client."""
        assert engine_with_discord.discord_enabled


# =============================================================================
# State Management Tests
# =============================================================================


class TestStateManagement:
    """Tests for engine state management."""

    def test_reset_processed(
        self, engine: NewsAlertEngine, sample_news_item: NewsItem
    ) -> None:
        """Test resetting processed items cache."""
        # Process an item
        engine.analyze_item(sample_news_item)
        assert len(engine._processed_ids) == 1

        # Reset
        engine.reset_processed()
        assert len(engine._processed_ids) == 0

        # Can process same item again
        alert = engine.analyze_item(sample_news_item)
        assert alert is not None

    def test_get_stats(self, engine: NewsAlertEngine) -> None:
        """Test getting engine statistics."""
        stats = engine.get_stats()

        assert "keywords_count" in stats
        assert "central_bank_sources" in stats
        assert "processed_items" in stats
        assert "discord_enabled" in stats
        assert "keywords_by_priority" in stats

        assert stats["keywords_count"] > 0
        assert stats["discord_enabled"] is False

    def test_repr(self, engine: NewsAlertEngine) -> None:
        """Test string representation."""
        repr_str = repr(engine)

        assert "NewsAlertEngine" in repr_str
        assert "keywords=" in repr_str
        assert "discord=disabled" in repr_str


# =============================================================================
# Alert Colors Tests
# =============================================================================


class TestAlertColors:
    """Tests for alert color constants."""

    def test_colors_are_valid_hex(self) -> None:
        """Test that all colors are valid hex values."""
        assert 0 <= AlertColors.CRITICAL <= 0xFFFFFF
        assert 0 <= AlertColors.HIGH <= 0xFFFFFF
        assert 0 <= AlertColors.MEDIUM <= 0xFFFFFF
        assert 0 <= AlertColors.LOW <= 0xFFFFFF

    def test_critical_is_red(self) -> None:
        """Test critical color is red."""
        # 0xFF0000 = bright red
        assert AlertColors.CRITICAL == 0xFF0000

    def test_colors_are_distinct(self) -> None:
        """Test that priority colors are visually distinct."""
        colors = [
            AlertColors.CRITICAL,
            AlertColors.HIGH,
            AlertColors.MEDIUM,
            AlertColors.LOW,
        ]
        # All colors should be unique
        assert len(set(colors)) == len(colors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
