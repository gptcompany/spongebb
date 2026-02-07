"""Oil supply disruption keyword alert system.

Provides pattern matching for oil supply disruption news with priority-based
categorization for alerting.

Example:
    from liquidity.news.oil_alerts import SupplyDisruptionMatcher, AlertPriority

    matcher = SupplyDisruptionMatcher()

    text = "OPEC+ announces significant production cut"
    matches = matcher.match(text)

    for match in matches:
        print(f"{match.priority.value}: {match.keyword} ({match.category})")
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    """Alert priority levels for oil supply disruptions.

    Priority determines how alerts are delivered:
    - HIGH: Immediate alert (push notification)
    - MEDIUM: Daily digest
    - LOW: Weekly summary
    """

    HIGH = "high"  # Immediate alert
    MEDIUM = "medium"  # Daily digest
    LOW = "low"  # Weekly summary


@dataclass(frozen=True)
class KeywordMatch:
    """Represents a matched keyword in text.

    Attributes:
        keyword: The keyword that matched.
        category: Category of the disruption (sanctions, opec, outage, etc.).
        priority: Alert priority level.
        context: Surrounding text context for the match.
    """

    keyword: str
    category: str
    priority: AlertPriority
    context: str


# Default supply disruption keywords with categories and priorities
SUPPLY_KEYWORDS: Dict[str, Dict] = {
    # HIGH priority - Immediate market impact
    "sanctions": {"category": "sanctions", "priority": AlertPriority.HIGH},
    "embargo": {"category": "sanctions", "priority": AlertPriority.HIGH},
    "force majeure": {"category": "outage", "priority": AlertPriority.HIGH},
    "pipeline explosion": {"category": "outage", "priority": AlertPriority.HIGH},
    "pipeline attack": {"category": "outage", "priority": AlertPriority.HIGH},
    "refinery fire": {"category": "outage", "priority": AlertPriority.HIGH},
    "refinery explosion": {"category": "outage", "priority": AlertPriority.HIGH},
    "production halt": {"category": "outage", "priority": AlertPriority.HIGH},
    "production shutdown": {"category": "outage", "priority": AlertPriority.HIGH},
    "export ban": {"category": "sanctions", "priority": AlertPriority.HIGH},
    "oil spill": {"category": "outage", "priority": AlertPriority.HIGH},
    "tanker attack": {"category": "geopolitical", "priority": AlertPriority.HIGH},
    "strait of hormuz": {"category": "geopolitical", "priority": AlertPriority.HIGH},
    "blockade": {"category": "geopolitical", "priority": AlertPriority.HIGH},
    "civil war": {"category": "geopolitical", "priority": AlertPriority.HIGH},
    "military strike": {"category": "geopolitical", "priority": AlertPriority.HIGH},
    # MEDIUM priority - Scheduled/expected events
    "production cut": {"category": "opec", "priority": AlertPriority.MEDIUM},
    "output cut": {"category": "opec", "priority": AlertPriority.MEDIUM},
    "opec+": {"category": "opec", "priority": AlertPriority.MEDIUM},
    "opec meeting": {"category": "opec", "priority": AlertPriority.MEDIUM},
    "opec decision": {"category": "opec", "priority": AlertPriority.MEDIUM},
    "supply reduction": {"category": "opec", "priority": AlertPriority.MEDIUM},
    "voluntary cut": {"category": "opec", "priority": AlertPriority.MEDIUM},
    "quota change": {"category": "opec", "priority": AlertPriority.MEDIUM},
    "production quota": {"category": "opec", "priority": AlertPriority.MEDIUM},
    "maintenance shutdown": {"category": "maintenance", "priority": AlertPriority.MEDIUM},
    "refinery maintenance": {"category": "maintenance", "priority": AlertPriority.MEDIUM},
    "pipeline maintenance": {"category": "maintenance", "priority": AlertPriority.MEDIUM},
    "hurricane": {"category": "weather", "priority": AlertPriority.MEDIUM},
    "tropical storm": {"category": "weather", "priority": AlertPriority.MEDIUM},
    "spr release": {"category": "spr", "priority": AlertPriority.MEDIUM},
    "strategic reserve": {"category": "spr", "priority": AlertPriority.MEDIUM},
    # LOW priority - General market context
    "demand growth": {"category": "demand", "priority": AlertPriority.LOW},
    "demand decline": {"category": "demand", "priority": AlertPriority.LOW},
    "demand forecast": {"category": "demand", "priority": AlertPriority.LOW},
    "consumption growth": {"category": "demand", "priority": AlertPriority.LOW},
    "inventory build": {"category": "inventory", "priority": AlertPriority.LOW},
    "inventory draw": {"category": "inventory", "priority": AlertPriority.LOW},
    "stockpile": {"category": "inventory", "priority": AlertPriority.LOW},
    "output increase": {"category": "supply", "priority": AlertPriority.LOW},
    "production increase": {"category": "supply", "priority": AlertPriority.LOW},
    "capacity expansion": {"category": "supply", "priority": AlertPriority.LOW},
    "shale production": {"category": "supply", "priority": AlertPriority.LOW},
    "rig count": {"category": "supply", "priority": AlertPriority.LOW},
}


class SupplyDisruptionMatcher:
    """Matcher for oil supply disruption keywords.

    Detects supply-related keywords in text and returns matches with
    category and priority information.

    Example:
        matcher = SupplyDisruptionMatcher()

        # Match keywords
        matches = matcher.match("OPEC+ announces production cut")
        for m in matches:
            print(f"{m.keyword}: {m.priority.value}")

        # Get highest priority
        if matches:
            highest = matcher.get_highest_priority(matches)
            print(f"Highest priority: {highest.value}")

    Attributes:
        keywords: Dictionary of keyword configurations.
    """

    def __init__(self, keywords: Dict[str, Dict] | None = None) -> None:
        """Initialize the matcher.

        Args:
            keywords: Custom keyword-to-config mapping. Uses SUPPLY_KEYWORDS if None.
        """
        if keywords is not None:
            self.keywords = dict(keywords)
        else:
            self.keywords = dict(SUPPLY_KEYWORDS)
        self._patterns: Dict[str, re.Pattern[str]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for all keywords.

        Uses word boundaries (\b) for keywords that start and end with
        alphanumeric characters. For keywords with special characters
        at the boundaries, uses lookbehind/lookahead patterns.
        """
        self._patterns = {}
        for kw in self.keywords:
            self._patterns[kw] = self._build_pattern(kw)

    def _build_pattern(self, keyword: str) -> re.Pattern[str]:
        """Build a regex pattern for a keyword.

        Args:
            keyword: The keyword to build a pattern for.

        Returns:
            Compiled regex pattern.
        """
        escaped = re.escape(keyword)

        # Check if first/last chars are alphanumeric (where \b works)
        first_is_alnum = keyword[0].isalnum() if keyword else False
        last_is_alnum = keyword[-1].isalnum() if keyword else False

        # Build pattern with appropriate boundaries
        if first_is_alnum and last_is_alnum:
            # Standard word boundary works
            pattern = rf"\b{escaped}\b"
        elif first_is_alnum:
            # Word boundary at start, but need lookahead at end
            # Match if followed by whitespace, punctuation, or end of string
            pattern = rf"\b{escaped}(?=\s|$|[^\w])"
        elif last_is_alnum:
            # Lookbehind at start, word boundary at end
            pattern = rf"(?<=\s|^|[^\w]){escaped}\b"
        else:
            # Both ends have special chars - use lookahead/lookbehind
            pattern = rf"(?<=\s|^|[^\w]){escaped}(?=\s|$|[^\w])"

        return re.compile(pattern, re.IGNORECASE)

    def add_keyword(
        self, keyword: str, category: str, priority: AlertPriority
    ) -> None:
        """Add a new keyword to the matcher.

        Args:
            keyword: Keyword or phrase to match (case-insensitive).
            category: Category of the disruption.
            priority: Alert priority level.

        Raises:
            ValueError: If keyword is empty.
        """
        keyword_lower = keyword.lower().strip()
        if not keyword_lower:
            raise ValueError("Keyword cannot be empty")

        self.keywords[keyword_lower] = {
            "category": category,
            "priority": priority,
        }
        self._patterns[keyword_lower] = self._build_pattern(keyword_lower)
        logger.info(
            "Added keyword '%s' (category=%s, priority=%s)",
            keyword_lower,
            category,
            priority.value,
        )

    def remove_keyword(self, keyword: str) -> None:
        """Remove a keyword from the matcher.

        Args:
            keyword: Keyword to remove.

        Raises:
            KeyError: If keyword doesn't exist.
        """
        keyword_lower = keyword.lower().strip()
        if keyword_lower not in self.keywords:
            raise KeyError(f"Keyword '{keyword}' not found")

        del self.keywords[keyword_lower]
        del self._patterns[keyword_lower]
        logger.info("Removed keyword '%s'", keyword_lower)

    def _extract_context(
        self, text: str, match: re.Match[str], context_chars: int = 50
    ) -> str:
        """Extract context around a match.

        Args:
            text: Full text.
            match: Regex match object.
            context_chars: Number of characters to include on each side.

        Returns:
            Context string with the match and surrounding text.
        """
        start = max(0, match.start() - context_chars)
        end = min(len(text), match.end() + context_chars)

        context = text[start:end]

        # Add ellipsis if truncated
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."

        return context

    def match(self, text: str) -> List[KeywordMatch]:
        """Find all keyword matches in text.

        Args:
            text: Text to search for keywords.

        Returns:
            List of KeywordMatch objects for all matches found.
        """
        matches: List[KeywordMatch] = []

        for keyword, pattern in self._patterns.items():
            m = pattern.search(text)
            if m:
                config = self.keywords[keyword]
                matches.append(
                    KeywordMatch(
                        keyword=keyword,
                        category=config["category"],
                        priority=config["priority"],
                        context=self._extract_context(text, m),
                    )
                )

        return matches

    def get_highest_priority(self, matches: List[KeywordMatch]) -> AlertPriority:
        """Get the highest priority from a list of matches.

        Priority order: HIGH > MEDIUM > LOW

        Args:
            matches: List of keyword matches.

        Returns:
            Highest priority level. Returns LOW if matches is empty.
        """
        if not matches:
            return AlertPriority.LOW

        priority_order = {
            AlertPriority.HIGH: 3,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 1,
        }

        return max(matches, key=lambda m: priority_order[m.priority]).priority

    def get_matches_by_priority(
        self, matches: List[KeywordMatch], priority: AlertPriority
    ) -> List[KeywordMatch]:
        """Filter matches by priority level.

        Args:
            matches: List of keyword matches.
            priority: Priority to filter by.

        Returns:
            Matches with the specified priority.
        """
        return [m for m in matches if m.priority == priority]

    def get_matches_by_category(
        self, matches: List[KeywordMatch], category: str
    ) -> List[KeywordMatch]:
        """Filter matches by category.

        Args:
            matches: List of keyword matches.
            category: Category to filter by.

        Returns:
            Matches with the specified category.
        """
        return [m for m in matches if m.category == category]

    def get_categories(self) -> List[str]:
        """Get all unique categories.

        Returns:
            List of category names.
        """
        return list(set(cfg["category"] for cfg in self.keywords.values()))

    def get_stats(self) -> Dict:
        """Get matcher statistics.

        Returns:
            Dictionary with matcher statistics.
        """
        categories = self.get_categories()
        priority_counts = {p.value: 0 for p in AlertPriority}

        for cfg in self.keywords.values():
            priority_counts[cfg["priority"].value] += 1

        return {
            "total_keywords": len(self.keywords),
            "categories": categories,
            "category_count": len(categories),
            "keywords_by_priority": priority_counts,
        }

    def __repr__(self) -> str:
        """Return string representation."""
        return f"SupplyDisruptionMatcher(keywords={len(self.keywords)})"
