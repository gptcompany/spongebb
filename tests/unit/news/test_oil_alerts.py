"""Unit tests for oil supply disruption keyword alerts.

Tests SupplyDisruptionMatcher, AlertPriority, and keyword matching functionality.

Run with: uv run pytest tests/unit/news/test_oil_alerts.py -v
"""

import pytest

from liquidity.news.oil_alerts import (
    SUPPLY_KEYWORDS,
    AlertPriority,
    KeywordMatch,
    SupplyDisruptionMatcher,
)

# =============================================================================
# AlertPriority Enum Tests
# =============================================================================


class TestAlertPriority:
    """Tests for AlertPriority enum."""

    def test_priority_values(self) -> None:
        """Test priority string values."""
        assert AlertPriority.HIGH.value == "high"
        assert AlertPriority.MEDIUM.value == "medium"
        assert AlertPriority.LOW.value == "low"

    def test_priority_names(self) -> None:
        """Test priority names."""
        assert AlertPriority.HIGH.name == "HIGH"
        assert AlertPriority.MEDIUM.name == "MEDIUM"
        assert AlertPriority.LOW.name == "LOW"

    def test_all_priorities_exist(self) -> None:
        """Test that all expected priorities exist."""
        priorities = list(AlertPriority)
        assert len(priorities) == 3
        assert AlertPriority.HIGH in priorities
        assert AlertPriority.MEDIUM in priorities
        assert AlertPriority.LOW in priorities


# =============================================================================
# Default Keywords Tests
# =============================================================================


class TestDefaultKeywords:
    """Tests for default SUPPLY_KEYWORDS configuration."""

    def test_keywords_has_high_priority(self) -> None:
        """Test that SUPPLY_KEYWORDS includes high priority keywords."""
        high_keywords = [
            k for k, v in SUPPLY_KEYWORDS.items() if v["priority"] == AlertPriority.HIGH
        ]
        assert "sanctions" in high_keywords
        assert "embargo" in high_keywords
        assert "force majeure" in high_keywords
        assert "pipeline explosion" in high_keywords
        assert len(high_keywords) >= 10  # At least 10 high priority keywords

    def test_keywords_has_medium_priority(self) -> None:
        """Test that SUPPLY_KEYWORDS includes medium priority keywords."""
        medium_keywords = [
            k
            for k, v in SUPPLY_KEYWORDS.items()
            if v["priority"] == AlertPriority.MEDIUM
        ]
        assert "production cut" in medium_keywords
        assert "opec+" in medium_keywords
        assert len(medium_keywords) >= 10

    def test_keywords_has_low_priority(self) -> None:
        """Test that SUPPLY_KEYWORDS includes low priority keywords."""
        low_keywords = [
            k for k, v in SUPPLY_KEYWORDS.items() if v["priority"] == AlertPriority.LOW
        ]
        assert "demand growth" in low_keywords
        assert len(low_keywords) >= 5

    def test_keywords_have_categories(self) -> None:
        """Test that all keywords have categories."""
        for keyword, config in SUPPLY_KEYWORDS.items():
            assert "category" in config, f"Keyword '{keyword}' missing category"
            assert config["category"], f"Keyword '{keyword}' has empty category"

    def test_sanctions_category(self) -> None:
        """Test sanctions keywords have correct category."""
        assert SUPPLY_KEYWORDS["sanctions"]["category"] == "sanctions"
        assert SUPPLY_KEYWORDS["embargo"]["category"] == "sanctions"

    def test_opec_category(self) -> None:
        """Test OPEC keywords have correct category."""
        assert SUPPLY_KEYWORDS["production cut"]["category"] == "opec"
        assert SUPPLY_KEYWORDS["opec+"]["category"] == "opec"


# =============================================================================
# KeywordMatch Model Tests
# =============================================================================


class TestKeywordMatch:
    """Tests for KeywordMatch dataclass."""

    def test_create_match(self) -> None:
        """Test creating a KeywordMatch."""
        match = KeywordMatch(
            keyword="sanctions",
            category="sanctions",
            priority=AlertPriority.HIGH,
            context="US announces new sanctions on oil exports",
        )

        assert match.keyword == "sanctions"
        assert match.category == "sanctions"
        assert match.priority == AlertPriority.HIGH
        assert "sanctions" in match.context

    def test_match_is_frozen(self) -> None:
        """Test that KeywordMatch is immutable."""
        match = KeywordMatch(
            keyword="embargo",
            category="sanctions",
            priority=AlertPriority.HIGH,
            context="context",
        )

        with pytest.raises((TypeError, AttributeError)):
            match.keyword = "new_keyword"  # type: ignore

    def test_match_equality(self) -> None:
        """Test KeywordMatch equality."""
        match1 = KeywordMatch(
            keyword="sanctions",
            category="sanctions",
            priority=AlertPriority.HIGH,
            context="context",
        )
        match2 = KeywordMatch(
            keyword="sanctions",
            category="sanctions",
            priority=AlertPriority.HIGH,
            context="context",
        )

        assert match1 == match2


# =============================================================================
# SupplyDisruptionMatcher Initialization Tests
# =============================================================================


class TestMatcherInit:
    """Tests for SupplyDisruptionMatcher initialization."""

    def test_init_default_keywords(self) -> None:
        """Test initialization with default keywords."""
        matcher = SupplyDisruptionMatcher()

        assert len(matcher.keywords) == len(SUPPLY_KEYWORDS)
        assert "sanctions" in matcher.keywords
        assert "opec+" in matcher.keywords

    def test_init_custom_keywords(self) -> None:
        """Test initialization with custom keywords."""
        custom = {
            "custom disruption": {
                "category": "custom",
                "priority": AlertPriority.HIGH,
            },
        }
        matcher = SupplyDisruptionMatcher(keywords=custom)

        assert len(matcher.keywords) == 1
        assert "custom disruption" in matcher.keywords
        assert "sanctions" not in matcher.keywords

    def test_init_empty_keywords(self) -> None:
        """Test initialization with empty keywords dict."""
        matcher = SupplyDisruptionMatcher(keywords={})

        assert len(matcher.keywords) == 0


# =============================================================================
# Keyword Matching Tests - Sanctions
# =============================================================================


class TestSanctionsMatching:
    """Tests for sanctions keyword matching."""

    @pytest.fixture
    def matcher(self) -> SupplyDisruptionMatcher:
        """Create a matcher with default keywords."""
        return SupplyDisruptionMatcher()

    def test_match_sanctions(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching 'sanctions' keyword."""
        text = "US announces new sanctions on Russian oil exports"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "sanctions" in keywords

        sanctions_match = next(m for m in matches if m.keyword == "sanctions")
        assert sanctions_match.category == "sanctions"
        assert sanctions_match.priority == AlertPriority.HIGH

    def test_match_embargo(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching 'embargo' keyword."""
        text = "EU considers oil embargo on major producer"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "embargo" in keywords

        embargo_match = next(m for m in matches if m.keyword == "embargo")
        assert embargo_match.priority == AlertPriority.HIGH


# =============================================================================
# Keyword Matching Tests - OPEC
# =============================================================================


class TestOPECMatching:
    """Tests for OPEC keyword matching."""

    @pytest.fixture
    def matcher(self) -> SupplyDisruptionMatcher:
        """Create a matcher with default keywords."""
        return SupplyDisruptionMatcher()

    def test_match_opec_plus(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching 'opec+' keyword."""
        text = "OPEC+ announces new production targets"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "opec+" in keywords

        opec_match = next(m for m in matches if m.keyword == "opec+")
        assert opec_match.category == "opec"
        assert opec_match.priority == AlertPriority.MEDIUM

    def test_match_production_cut(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching 'production cut' keyword."""
        text = "OPEC members agree on production cut of 1 million bpd"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "production cut" in keywords

        cut_match = next(m for m in matches if m.keyword == "production cut")
        assert cut_match.priority == AlertPriority.MEDIUM

    def test_match_output_cut(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching 'output cut' keyword."""
        text = "Saudi Arabia announces output cut"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "output cut" in keywords


# =============================================================================
# Keyword Matching Tests - Outages
# =============================================================================


class TestOutageMatching:
    """Tests for outage keyword matching."""

    @pytest.fixture
    def matcher(self) -> SupplyDisruptionMatcher:
        """Create a matcher with default keywords."""
        return SupplyDisruptionMatcher()

    def test_match_force_majeure(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching 'force majeure' keyword."""
        text = "Libya declares force majeure on oil exports"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "force majeure" in keywords

        fm_match = next(m for m in matches if m.keyword == "force majeure")
        assert fm_match.category == "outage"
        assert fm_match.priority == AlertPriority.HIGH

    def test_match_pipeline_explosion(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching 'pipeline explosion' keyword."""
        text = "Major pipeline explosion reported in oil-producing region"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "pipeline explosion" in keywords

    def test_match_refinery_fire(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching 'refinery fire' keyword."""
        text = "Refinery fire causes production shutdown at major facility"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "refinery fire" in keywords


# =============================================================================
# Keyword Matching Tests - Case Insensitivity
# =============================================================================


class TestCaseInsensitivity:
    """Tests for case-insensitive matching."""

    @pytest.fixture
    def matcher(self) -> SupplyDisruptionMatcher:
        """Create a matcher with default keywords."""
        return SupplyDisruptionMatcher()

    def test_uppercase_match(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching uppercase keywords."""
        text = "SANCTIONS announced against oil exporter"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "sanctions" in keywords

    def test_mixed_case_match(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching mixed case keywords."""
        text = "Force Majeure declared on oil shipments"
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "force majeure" in keywords


# =============================================================================
# Keyword Matching Tests - No False Positives
# =============================================================================


class TestNoFalsePositives:
    """Tests to ensure no false positives on generic news."""

    @pytest.fixture
    def matcher(self) -> SupplyDisruptionMatcher:
        """Create a matcher with default keywords."""
        return SupplyDisruptionMatcher()

    def test_no_match_generic_news(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test no matches on generic news."""
        text = "Oil prices stable as market awaits economic data"
        matches = matcher.match(text)

        assert len(matches) == 0

    def test_no_match_earnings_report(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test no matches on company earnings report."""
        text = "ExxonMobil reports quarterly earnings, beats expectations"
        matches = matcher.match(text)

        assert len(matches) == 0

    def test_no_match_price_analysis(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test no matches on price analysis."""
        text = "Crude oil futures rise on technical buying"
        matches = matcher.match(text)

        assert len(matches) == 0

    def test_word_boundary_respected(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test that word boundaries are respected (no partial matches)."""
        # "demand" should not match as part of "demanding"
        matcher.add_keyword("demand", "demand", AlertPriority.LOW)

        text = "Market conditions are demanding attention"
        matches = matcher.match(text)

        demand_matches = [m for m in matches if m.keyword == "demand"]
        assert len(demand_matches) == 0

    def test_no_match_unrelated_embargo(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test no false positives from similar words."""
        # Should not match "embargogate" or "embargoed" as "embargo"
        text = "The situation remains complex with various trade policies"
        matches = matcher.match(text)

        embargo_matches = [m for m in matches if m.keyword == "embargo"]
        assert len(embargo_matches) == 0


# =============================================================================
# Priority Classification Tests
# =============================================================================


class TestPriorityClassification:
    """Tests for priority classification."""

    @pytest.fixture
    def matcher(self) -> SupplyDisruptionMatcher:
        """Create a matcher with default keywords."""
        return SupplyDisruptionMatcher()

    def test_get_highest_priority_high(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test highest priority when HIGH match exists."""
        text = "Sanctions imposed after production cut announcement"
        matches = matcher.match(text)

        highest = matcher.get_highest_priority(matches)
        assert highest == AlertPriority.HIGH

    def test_get_highest_priority_medium(
        self, matcher: SupplyDisruptionMatcher
    ) -> None:
        """Test highest priority when only MEDIUM matches exist."""
        text = "OPEC+ production cut discussed at meeting"
        matches = matcher.match(text)

        highest = matcher.get_highest_priority(matches)
        assert highest == AlertPriority.MEDIUM

    def test_get_highest_priority_low(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test highest priority when only LOW matches exist."""
        text = "Demand growth expected in coming quarter"
        matches = matcher.match(text)

        highest = matcher.get_highest_priority(matches)
        assert highest == AlertPriority.LOW

    def test_get_highest_priority_empty(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test highest priority returns LOW for empty matches."""
        highest = matcher.get_highest_priority([])
        assert highest == AlertPriority.LOW


# =============================================================================
# Multiple Matches Tests
# =============================================================================


class TestMultipleMatches:
    """Tests for multiple keyword matches in same text."""

    @pytest.fixture
    def matcher(self) -> SupplyDisruptionMatcher:
        """Create a matcher with default keywords."""
        return SupplyDisruptionMatcher()

    def test_multiple_matches(self, matcher: SupplyDisruptionMatcher) -> None:
        """Test matching multiple keywords in same text."""
        text = (
            "OPEC+ announces production cut amid sanctions concerns "
            "and force majeure declarations"
        )
        matches = matcher.match(text)

        keywords = [m.keyword for m in matches]
        assert "opec+" in keywords
        assert "production cut" in keywords
        assert "sanctions" in keywords
        assert "force majeure" in keywords

        assert len(matches) >= 4

    def test_different_priorities_in_text(
        self, matcher: SupplyDisruptionMatcher
    ) -> None:
        """Test text with different priority matches."""
        text = "Sanctions impact on demand growth forecasts"
        matches = matcher.match(text)

        priorities = [m.priority for m in matches]
        assert AlertPriority.HIGH in priorities  # sanctions
        assert AlertPriority.LOW in priorities  # demand growth


# =============================================================================
# Keyword Management Tests
# =============================================================================


class TestKeywordManagement:
    """Tests for keyword add/remove operations."""

    def test_add_keyword(self) -> None:
        """Test adding a new keyword."""
        matcher = SupplyDisruptionMatcher()
        initial_count = len(matcher.keywords)

        matcher.add_keyword("new disruption", "custom", AlertPriority.HIGH)

        assert len(matcher.keywords) == initial_count + 1
        assert "new disruption" in matcher.keywords

        # Test it matches
        matches = matcher.match("News about new disruption event")
        keywords = [m.keyword for m in matches]
        assert "new disruption" in keywords

    def test_add_keyword_normalizes_case(self) -> None:
        """Test that added keyword is normalized to lowercase."""
        matcher = SupplyDisruptionMatcher(keywords={})
        matcher.add_keyword("MiXeD CaSe", "test", AlertPriority.MEDIUM)

        assert "mixed case" in matcher.keywords
        assert "MiXeD CaSe" not in matcher.keywords

    def test_add_empty_keyword_raises(self) -> None:
        """Test that empty keyword raises ValueError."""
        matcher = SupplyDisruptionMatcher()

        with pytest.raises(ValueError, match="cannot be empty"):
            matcher.add_keyword("", "category", AlertPriority.HIGH)

        with pytest.raises(ValueError, match="cannot be empty"):
            matcher.add_keyword("   ", "category", AlertPriority.HIGH)

    def test_remove_keyword(self) -> None:
        """Test removing a keyword."""
        matcher = SupplyDisruptionMatcher()
        initial_count = len(matcher.keywords)

        matcher.remove_keyword("sanctions")

        assert len(matcher.keywords) == initial_count - 1
        assert "sanctions" not in matcher.keywords

        # Should not match anymore
        matches = matcher.match("New sanctions announced")
        keywords = [m.keyword for m in matches]
        assert "sanctions" not in keywords

    def test_remove_nonexistent_keyword_raises(self) -> None:
        """Test that removing non-existent keyword raises KeyError."""
        matcher = SupplyDisruptionMatcher()

        with pytest.raises(KeyError, match="not found"):
            matcher.remove_keyword("nonexistent")


# =============================================================================
# Filter Methods Tests
# =============================================================================


class TestFilterMethods:
    """Tests for match filtering methods."""

    @pytest.fixture
    def matcher(self) -> SupplyDisruptionMatcher:
        """Create a matcher with default keywords."""
        return SupplyDisruptionMatcher()

    def test_get_matches_by_priority(
        self, matcher: SupplyDisruptionMatcher
    ) -> None:
        """Test filtering matches by priority."""
        text = "Sanctions and production cut affect demand growth"
        matches = matcher.match(text)

        high_matches = matcher.get_matches_by_priority(matches, AlertPriority.HIGH)
        medium_matches = matcher.get_matches_by_priority(matches, AlertPriority.MEDIUM)
        low_matches = matcher.get_matches_by_priority(matches, AlertPriority.LOW)

        assert all(m.priority == AlertPriority.HIGH for m in high_matches)
        assert all(m.priority == AlertPriority.MEDIUM for m in medium_matches)
        assert all(m.priority == AlertPriority.LOW for m in low_matches)

    def test_get_matches_by_category(
        self, matcher: SupplyDisruptionMatcher
    ) -> None:
        """Test filtering matches by category."""
        text = "Sanctions imposed amid OPEC+ production cut talks"
        matches = matcher.match(text)

        sanctions_matches = matcher.get_matches_by_category(matches, "sanctions")
        opec_matches = matcher.get_matches_by_category(matches, "opec")

        assert all(m.category == "sanctions" for m in sanctions_matches)
        assert all(m.category == "opec" for m in opec_matches)


# =============================================================================
# Context Extraction Tests
# =============================================================================


class TestContextExtraction:
    """Tests for context extraction in matches."""

    @pytest.fixture
    def matcher(self) -> SupplyDisruptionMatcher:
        """Create a matcher with default keywords."""
        return SupplyDisruptionMatcher()

    def test_context_includes_keyword(
        self, matcher: SupplyDisruptionMatcher
    ) -> None:
        """Test that context includes the matched keyword."""
        text = "Breaking: US announces new sanctions on oil exports"
        matches = matcher.match(text)

        sanctions_match = next(m for m in matches if m.keyword == "sanctions")
        assert "sanctions" in sanctions_match.context

    def test_context_includes_surrounding_text(
        self, matcher: SupplyDisruptionMatcher
    ) -> None:
        """Test that context includes surrounding text."""
        text = "The government announced sanctions after the incident"
        matches = matcher.match(text)

        sanctions_match = next(m for m in matches if m.keyword == "sanctions")
        assert "announced" in sanctions_match.context or "after" in sanctions_match.context


# =============================================================================
# Stats and Repr Tests
# =============================================================================


class TestStatsAndRepr:
    """Tests for statistics and string representation."""

    def test_get_stats(self) -> None:
        """Test getting matcher statistics."""
        matcher = SupplyDisruptionMatcher()
        stats = matcher.get_stats()

        assert "total_keywords" in stats
        assert "categories" in stats
        assert "category_count" in stats
        assert "keywords_by_priority" in stats

        assert stats["total_keywords"] == len(SUPPLY_KEYWORDS)
        assert stats["category_count"] > 0

    def test_get_categories(self) -> None:
        """Test getting unique categories."""
        matcher = SupplyDisruptionMatcher()
        categories = matcher.get_categories()

        assert "sanctions" in categories
        assert "opec" in categories
        assert "outage" in categories
        assert len(categories) >= 5

    def test_repr(self) -> None:
        """Test string representation."""
        matcher = SupplyDisruptionMatcher()
        repr_str = repr(matcher)

        assert "SupplyDisruptionMatcher" in repr_str
        assert "keywords=" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
