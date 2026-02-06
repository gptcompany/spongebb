"""Breaking news keyword alert engine.

Provides pattern matching for central bank news items with priority levels
and Discord integration for real-time notifications.

Example:
    from liquidity.news.alerts import NewsAlertEngine, Priority
    from liquidity.alerts import DiscordClient, DiscordConfig

    # Create engine with Discord integration
    discord = DiscordClient(DiscordConfig(webhook_url="..."))
    engine = NewsAlertEngine(discord_client=discord)

    # Process incoming news
    items = await poller.poll_all()
    alerts = await engine.process_news(items)

    for alert in alerts:
        print(f"{alert.priority.name}: {alert.news_item.title}")
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

from discord_webhook import DiscordEmbed

from liquidity.alerts.discord import DiscordClient
from liquidity.news.schemas import FeedSource, NewsItem

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Alert priority levels.

    Higher values indicate higher priority.
    CRITICAL alerts bypass rate limiting.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# Default breaking news keywords with priority mappings
BREAKING_KEYWORDS: dict[str, Priority] = {
    # Critical - emergency actions
    "emergency": Priority.CRITICAL,
    "emergency rate": Priority.CRITICAL,
    "emergency cut": Priority.CRITICAL,
    "emergency meeting": Priority.CRITICAL,
    "emergency action": Priority.CRITICAL,
    "extraordinary measures": Priority.CRITICAL,
    "swap line": Priority.CRITICAL,
    "liquidity facility": Priority.CRITICAL,
    # High - policy decisions
    "rate decision": Priority.HIGH,
    "policy statement": Priority.HIGH,
    "fomc statement": Priority.HIGH,
    "monetary policy decision": Priority.HIGH,
    "interest rate": Priority.HIGH,
    "policy rate": Priority.HIGH,
    "quantitative easing": Priority.HIGH,
    "quantitative tightening": Priority.HIGH,
    "asset purchase": Priority.HIGH,
    "taper": Priority.HIGH,
    # Medium - balance sheet and macro
    "balance sheet": Priority.MEDIUM,
    "inflation": Priority.MEDIUM,
    "inflation report": Priority.MEDIUM,
    "cpi": Priority.MEDIUM,
    "price stability": Priority.MEDIUM,
    "financial stability": Priority.MEDIUM,
    "economic outlook": Priority.MEDIUM,
    "gdp": Priority.MEDIUM,
    "recession": Priority.MEDIUM,
    # Low - regular updates
    "employment": Priority.LOW,
    "minutes": Priority.LOW,
    "speech": Priority.LOW,
    "testimony": Priority.LOW,
    "press conference": Priority.LOW,
    "remarks": Priority.LOW,
}

# Central bank specific patterns
CENTRAL_BANK_PATTERNS: dict[FeedSource, list[str]] = {
    FeedSource.FED_PRESS: [
        "fomc",
        "federal reserve",
        "federal funds",
        "discount rate",
        "rrp",
        "reverse repo",
        "soma",
    ],
    FeedSource.FED_SPEECHES: [
        "chair powell",
        "governor",
        "fed governor",
    ],
    FeedSource.ECB_PRESS: [
        "ecb",
        "governing council",
        "lagarde",
        "main refinancing",
        "deposit facility",
        "pepp",
        "app",
    ],
    FeedSource.BOJ_NEWS: [
        "boj",
        "bank of japan",
        "kuroda",
        "ueda",
        "yield curve control",
        "ycc",
    ],
    FeedSource.BOE_NEWS: [
        "boe",
        "bank of england",
        "mpc",
        "monetary policy committee",
        "bailey",
    ],
    FeedSource.SNB_NEWS: [
        "snb",
        "swiss national bank",
        "swiss franc",
    ],
    FeedSource.BOC_NEWS: [
        "boc",
        "bank of canada",
        "macklem",
    ],
    FeedSource.PBOC_NEWS: [
        "pboc",
        "people's bank",
        "yuan",
        "rmb",
        "rrr",
        "mlf",
        "lpr",
    ],
}


@dataclass(frozen=True)
class NewsAlert:
    """Alert generated from a news item match.

    Attributes:
        news_item: The original news item that triggered the alert.
        priority: Alert priority level.
        matched_keywords: List of keywords that matched.
        matched_patterns: Central bank specific patterns that matched.
        created_at: When the alert was created.
    """

    news_item: NewsItem
    priority: Priority
    matched_keywords: tuple[str, ...]
    matched_patterns: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary representation.

        Returns:
            Dictionary with alert data.
        """
        return {
            "news_id": self.news_item.id,
            "source": self.news_item.source.value,
            "title": self.news_item.title,
            "link": str(self.news_item.link),
            "published": self.news_item.published.isoformat(),
            "priority": self.priority.name,
            "priority_value": self.priority.value,
            "matched_keywords": list(self.matched_keywords),
            "matched_patterns": list(self.matched_patterns),
            "created_at": self.created_at.isoformat(),
        }


class AlertColors:
    """Color constants for news alert embeds."""

    CRITICAL = 0xFF0000  # Bright red
    HIGH = 0xFF6600  # Orange-red
    MEDIUM = 0xFFAA00  # Orange
    LOW = 0x888888  # Gray


class NewsAlertEngine:
    """Engine for detecting and alerting on breaking news keywords.

    Processes NewsItem objects and generates alerts when configured
    keywords are detected. Integrates with Discord for notifications.

    Example:
        engine = NewsAlertEngine()

        # Add custom keywords
        engine.add_keyword("emergency cut", Priority.CRITICAL)

        # Process news
        alerts = await engine.process_news(news_items)
    """

    def __init__(
        self,
        discord_client: DiscordClient | None = None,
        keywords: dict[str, Priority] | None = None,
        central_bank_patterns: dict[FeedSource, list[str]] | None = None,
    ) -> None:
        """Initialize the news alert engine.

        Args:
            discord_client: Discord client for sending alerts. Optional.
            keywords: Custom keyword-to-priority mapping. Uses BREAKING_KEYWORDS if None.
            central_bank_patterns: Custom central bank patterns. Uses defaults if None.
        """
        self._discord = discord_client
        self._keywords: dict[str, Priority] = dict(keywords or BREAKING_KEYWORDS)
        self._cb_patterns: dict[FeedSource, list[str]] = dict(
            central_bank_patterns or CENTRAL_BANK_PATTERNS
        )
        # Compile regex patterns for efficient matching
        self._compiled_keywords: dict[re.Pattern[str], Priority] = {}
        self._recompile_keywords()
        # Track processed items to avoid duplicate alerts
        self._processed_ids: set[str] = set()

    def _recompile_keywords(self) -> None:
        """Recompile keyword patterns after changes."""
        self._compiled_keywords = {
            re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE): priority
            for kw, priority in self._keywords.items()
        }

    @property
    def keywords(self) -> dict[str, Priority]:
        """Get current keyword-to-priority mapping."""
        return dict(self._keywords)

    @property
    def discord_enabled(self) -> bool:
        """Check if Discord notifications are enabled."""
        return self._discord is not None and self._discord.is_configured

    def add_keyword(self, keyword: str, priority: Priority) -> None:
        """Add a custom keyword pattern.

        Args:
            keyword: Keyword or phrase to match (case-insensitive).
            priority: Priority level for matches.
        """
        keyword_lower = keyword.lower().strip()
        if not keyword_lower:
            raise ValueError("Keyword cannot be empty")

        self._keywords[keyword_lower] = priority
        self._recompile_keywords()
        logger.info("Added keyword '%s' with priority %s", keyword_lower, priority.name)

    def remove_keyword(self, keyword: str) -> None:
        """Remove a keyword pattern.

        Args:
            keyword: Keyword to remove.

        Raises:
            KeyError: If keyword doesn't exist.
        """
        keyword_lower = keyword.lower().strip()
        if keyword_lower not in self._keywords:
            raise KeyError(f"Keyword '{keyword}' not found")

        del self._keywords[keyword_lower]
        self._recompile_keywords()
        logger.info("Removed keyword '%s'", keyword_lower)

    def update_priority(self, keyword: str, priority: Priority) -> None:
        """Update priority for an existing keyword.

        Args:
            keyword: Keyword to update.
            priority: New priority level.

        Raises:
            KeyError: If keyword doesn't exist.
        """
        keyword_lower = keyword.lower().strip()
        if keyword_lower not in self._keywords:
            raise KeyError(f"Keyword '{keyword}' not found")

        self._keywords[keyword_lower] = priority
        self._recompile_keywords()
        logger.info("Updated keyword '%s' to priority %s", keyword_lower, priority.name)

    def add_central_bank_pattern(self, source: FeedSource, pattern: str) -> None:
        """Add a pattern for a specific central bank feed.

        Args:
            source: Feed source to add pattern for.
            pattern: Pattern string (case-insensitive).
        """
        pattern_lower = pattern.lower().strip()
        if source not in self._cb_patterns:
            self._cb_patterns[source] = []

        if pattern_lower not in self._cb_patterns[source]:
            self._cb_patterns[source].append(pattern_lower)
            logger.info(
                "Added pattern '%s' for source %s", pattern_lower, source.value
            )

    def match_keywords(self, text: str) -> list[tuple[str, Priority]]:
        """Find all matching keywords in text.

        Args:
            text: Text to search (title, summary, content).

        Returns:
            List of (keyword, priority) tuples for all matches.
        """
        matches: list[tuple[str, Priority]] = []

        for pattern, priority in self._compiled_keywords.items():
            if pattern.search(text):
                # Extract the original keyword from the pattern
                keyword = pattern.pattern.replace(r"\b", "").replace("\\", "")
                matches.append((keyword, priority))

        return matches

    def match_central_bank_patterns(
        self, text: str, source: FeedSource
    ) -> list[str]:
        """Find matching central bank specific patterns.

        Args:
            text: Text to search.
            source: Feed source for source-specific patterns.

        Returns:
            List of matched pattern strings.
        """
        patterns = self._cb_patterns.get(source, [])
        matches: list[str] = []

        text_lower = text.lower()
        for pattern in patterns:
            if pattern in text_lower:
                matches.append(pattern)

        return matches

    def analyze_item(self, item: NewsItem) -> NewsAlert | None:
        """Analyze a single news item for alert conditions.

        Args:
            item: News item to analyze.

        Returns:
            NewsAlert if keywords matched, None otherwise.
        """
        # Skip if already processed
        if item.id in self._processed_ids:
            logger.debug("Item %s already processed, skipping", item.id)
            return None

        # Combine text for matching
        text = f"{item.title} {item.summary} {item.content}"

        # Find keyword matches
        keyword_matches = self.match_keywords(text)
        if not keyword_matches:
            self._processed_ids.add(item.id)
            return None

        # Find central bank pattern matches
        cb_matches = self.match_central_bank_patterns(text, item.source)

        # Determine highest priority
        max_priority = max(priority for _, priority in keyword_matches)

        # Create alert
        alert = NewsAlert(
            news_item=item,
            priority=max_priority,
            matched_keywords=tuple(kw for kw, _ in keyword_matches),
            matched_patterns=tuple(cb_matches),
        )

        self._processed_ids.add(item.id)
        logger.info(
            "Alert generated for '%s' - Priority: %s, Keywords: %s",
            item.title[:50],
            max_priority.name,
            [kw for kw, _ in keyword_matches],
        )

        return alert

    async def process_news(self, items: list[NewsItem]) -> list[NewsAlert]:
        """Process news items and generate alerts for matches.

        Args:
            items: List of news items to process.

        Returns:
            List of generated alerts (sorted by priority, highest first).
        """
        alerts: list[NewsAlert] = []

        for item in items:
            alert = self.analyze_item(item)
            if alert is not None:
                alerts.append(alert)

                # Send Discord notification if configured
                if self.discord_enabled:
                    await self._send_discord_alert(alert)

        # Sort by priority (highest first)
        alerts.sort(key=lambda a: a.priority, reverse=True)

        logger.info("Processed %d items, generated %d alerts", len(items), len(alerts))
        return alerts

    def process_news_sync(self, items: list[NewsItem]) -> list[NewsAlert]:
        """Synchronous version of process_news (without Discord).

        Args:
            items: List of news items to process.

        Returns:
            List of generated alerts (sorted by priority, highest first).
        """
        alerts: list[NewsAlert] = []

        for item in items:
            alert = self.analyze_item(item)
            if alert is not None:
                alerts.append(alert)

        alerts.sort(key=lambda a: a.priority, reverse=True)
        return alerts

    async def _send_discord_alert(self, alert: NewsAlert) -> bool:
        """Send alert to Discord.

        Args:
            alert: Alert to send.

        Returns:
            True if sent successfully.
        """
        if self._discord is None:
            return False

        embed = self._format_alert_embed(alert)
        alert_type = f"news_alert_{alert.priority.name.lower()}"

        # Critical alerts bypass rate limiting
        if alert.priority == Priority.CRITICAL:
            self._discord.reset_rate_limit(alert_type)

        return await self._discord.send_embed_async(embed, alert_type)

    def _format_alert_embed(self, alert: NewsAlert) -> DiscordEmbed:
        """Format alert as Discord embed.

        Args:
            alert: Alert to format.

        Returns:
            Discord embed object.
        """
        # Choose color based on priority
        color_map = {
            Priority.CRITICAL: AlertColors.CRITICAL,
            Priority.HIGH: AlertColors.HIGH,
            Priority.MEDIUM: AlertColors.MEDIUM,
            Priority.LOW: AlertColors.LOW,
        }
        color = color_map.get(alert.priority, AlertColors.LOW)

        # Choose emoji based on priority
        emoji_map = {
            Priority.CRITICAL: "\U0001f6a8",  # Siren
            Priority.HIGH: "\u26a0\ufe0f",  # Warning
            Priority.MEDIUM: "\U0001f4e2",  # Loudspeaker
            Priority.LOW: "\U0001f4f0",  # Newspaper
        }
        emoji = emoji_map.get(alert.priority, "\U0001f4f0")

        # Build title
        source_name = alert.news_item.source.value.upper().replace("_", " ")
        embed = DiscordEmbed(
            title=f"{emoji} {alert.priority.name} | {source_name}",
            description=alert.news_item.title,
            color=color,
        )

        # Add link
        embed.add_embed_field(
            name="Link",
            value=str(alert.news_item.link),
            inline=False,
        )

        # Add matched keywords
        if alert.matched_keywords:
            keywords_str = ", ".join(alert.matched_keywords)
            embed.add_embed_field(
                name="Matched Keywords",
                value=keywords_str,
                inline=True,
            )

        # Add matched patterns
        if alert.matched_patterns:
            patterns_str = ", ".join(alert.matched_patterns)
            embed.add_embed_field(
                name="CB Patterns",
                value=patterns_str,
                inline=True,
            )

        # Add published time
        embed.add_embed_field(
            name="Published",
            value=alert.news_item.published.strftime("%Y-%m-%d %H:%M UTC"),
            inline=True,
        )

        # Add summary if available
        if alert.news_item.summary:
            summary = alert.news_item.summary[:300]
            if len(alert.news_item.summary) > 300:
                summary += "..."
            embed.add_embed_field(
                name="Summary",
                value=summary,
                inline=False,
            )

        embed.set_timestamp()
        embed.set_footer(text="News Intelligence | Liquidity Monitor")

        return embed

    def reset_processed(self) -> None:
        """Clear the set of processed item IDs."""
        count = len(self._processed_ids)
        self._processed_ids.clear()
        logger.info("Reset processed items cache (%d items cleared)", count)

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics.

        Returns:
            Dictionary with engine stats.
        """
        return {
            "keywords_count": len(self._keywords),
            "central_bank_sources": len(self._cb_patterns),
            "processed_items": len(self._processed_ids),
            "discord_enabled": self.discord_enabled,
            "keywords_by_priority": {
                priority.name: sum(
                    1 for p in self._keywords.values() if p == priority
                )
                for priority in Priority
            },
        }

    def __repr__(self) -> str:
        """Return string representation."""
        discord_status = "discord=enabled" if self.discord_enabled else "discord=disabled"
        return (
            f"NewsAlertEngine(keywords={len(self._keywords)}, "
            f"processed={len(self._processed_ids)}, {discord_status})"
        )
