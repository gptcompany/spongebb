"""Tests for FOMC Statement Diff Panel component.

Tests the dashboard component for comparing FOMC statements with
Bloomberg-style side-by-side diff visualization.
"""

from datetime import date

import dash_bootstrap_components as dbc
import pytest
from dash import html

from liquidity.dashboard.components.fomc_diff import (
    DOVISH_COLOR,
    HAWKISH_COLOR,
    NEUTRAL_COLOR,
    create_change_summary,
    create_diff_view,
    create_empty_diff_view,
    create_error_diff_view,
    create_fomc_diff_panel,
    create_loading_diff_view,
    format_date_option,
    get_available_dates_options,
    parse_date_value,
)
from liquidity.news.fomc.diff import (
    ChangeScore,
    PhraseShift,
    StatementDiff,
    StatementDiffEngine,
)


class TestFOMCDiffPanel:
    """Test FOMC diff panel creation."""

    def test_create_panel(self) -> None:
        """Test creating the FOMC diff panel."""
        panel = create_fomc_diff_panel()
        assert panel is not None

    def test_panel_has_card_structure(self) -> None:
        """Test that panel is a Bootstrap Card."""
        panel = create_fomc_diff_panel()
        assert isinstance(panel, dbc.Card)

    def test_panel_has_header(self) -> None:
        """Test that panel has a header with title."""
        panel = create_fomc_diff_panel()
        # Card should have children including CardHeader
        assert panel.children is not None
        assert len(panel.children) >= 2  # Header + Body

    def test_panel_has_date_dropdowns(self) -> None:
        """Test that panel contains two date dropdown selectors."""
        panel = create_fomc_diff_panel()

        def find_by_id(component, target_id: str) -> bool:
            """Recursively search for component by ID."""
            if hasattr(component, "id") and component.id == target_id:
                return True
            if hasattr(component, "children"):
                children = component.children
                if isinstance(children, list):
                    return any(find_by_id(c, target_id) for c in children)
                elif children is not None:
                    return find_by_id(children, target_id)
            return False

        assert find_by_id(panel, "fomc-date-1")
        assert find_by_id(panel, "fomc-date-2")

    def test_panel_has_compare_button(self) -> None:
        """Test that panel contains compare button."""
        panel = create_fomc_diff_panel()

        def find_by_id(component, target_id: str) -> bool:
            if hasattr(component, "id") and component.id == target_id:
                return True
            if hasattr(component, "children"):
                children = component.children
                if isinstance(children, list):
                    return any(find_by_id(c, target_id) for c in children)
                elif children is not None:
                    return find_by_id(children, target_id)
            return False

        assert find_by_id(panel, "fomc-compare-btn")

    def test_panel_has_diff_view_container(self) -> None:
        """Test that panel contains diff view container."""
        panel = create_fomc_diff_panel()

        def find_by_id(component, target_id: str) -> bool:
            if hasattr(component, "id") and component.id == target_id:
                return True
            if hasattr(component, "children"):
                children = component.children
                if isinstance(children, list):
                    return any(find_by_id(c, target_id) for c in children)
                elif children is not None:
                    return find_by_id(children, target_id)
            return False

        assert find_by_id(panel, "fomc-diff-view")


class TestChangeSummary:
    """Test change summary display."""

    def test_hawkish_change_summary(self) -> None:
        """Test hawkish change shows red color and up arrow."""
        score = ChangeScore(
            direction="hawkish",
            magnitude=0.45,
            key_changes=["+elevated", "+tight"],
        )
        shifts = [
            PhraseShift(phrase="elevated", change="added", policy_signal="hawkish"),
            PhraseShift(phrase="patient", change="removed", policy_signal="dovish"),
        ]

        summary = create_change_summary(score, shifts)

        assert summary is not None
        # Should contain HAWKISH text
        assert _contains_text(summary, "HAWKISH")
        # Should contain up arrow
        assert _contains_text(summary, "\u25b2")

    def test_dovish_change_summary(self) -> None:
        """Test dovish change shows green color and down arrow."""
        score = ChangeScore(
            direction="dovish",
            magnitude=-0.35,
            key_changes=["-restrictive", "+patient"],
        )
        shifts = [
            PhraseShift(phrase="patient", change="added", policy_signal="dovish"),
        ]

        summary = create_change_summary(score, shifts)

        assert summary is not None
        assert _contains_text(summary, "DOVISH")
        assert _contains_text(summary, "\u25bc")

    def test_neutral_change_summary(self) -> None:
        """Test neutral change shows gray color."""
        score = ChangeScore(
            direction="neutral",
            magnitude=0.05,
            key_changes=[],
        )

        summary = create_change_summary(score, [])

        assert summary is not None
        assert _contains_text(summary, "NEUTRAL")

    def test_magnitude_formatting(self) -> None:
        """Test magnitude is formatted correctly with sign."""
        positive_score = ChangeScore(
            direction="hawkish",
            magnitude=0.45,
            key_changes=[],
        )
        negative_score = ChangeScore(
            direction="dovish",
            magnitude=-0.30,
            key_changes=[],
        )

        pos_summary = create_change_summary(positive_score, [])
        neg_summary = create_change_summary(negative_score, [])

        # Positive should have + sign
        assert _contains_text(pos_summary, "+0.45")
        # Negative should show negative
        assert _contains_text(neg_summary, "-0.30")

    def test_phrase_shifts_badges(self) -> None:
        """Test phrase shifts are displayed as badges."""
        score = ChangeScore(direction="hawkish", magnitude=0.5, key_changes=[])
        shifts = [
            PhraseShift(phrase="elevated", change="added", policy_signal="hawkish"),
            PhraseShift(phrase="patient", change="removed", policy_signal="dovish"),
        ]

        summary = create_change_summary(score, shifts)

        # Should contain phrase text
        assert _contains_text(summary, "elevated")
        assert _contains_text(summary, "patient")


class TestDiffView:
    """Test diff view rendering."""

    @pytest.fixture
    def sample_diff(self) -> StatementDiff:
        """Create a sample diff for testing."""
        engine = StatementDiffEngine()
        return engine.diff(
            old_text="The Committee remains patient.",
            new_text="The Committee is vigilant.",
            old_date=date(2024, 1, 31),
            new_date=date(2024, 3, 20),
        )

    def test_create_diff_view(self, sample_diff: StatementDiff) -> None:
        """Test creating diff view from StatementDiff."""
        view = create_diff_view(sample_diff)

        assert view is not None
        assert isinstance(view, html.Div)

    def test_diff_view_contains_dates(self, sample_diff: StatementDiff) -> None:
        """Test diff view displays comparison dates."""
        view = create_diff_view(sample_diff)

        # Should contain date information
        assert _contains_text(view, "Jan 31, 2024") or _contains_text(view, "Jan")
        assert _contains_text(view, "Mar 20, 2024") or _contains_text(view, "Mar")

    def test_diff_view_contains_unchanged_ratio(self, sample_diff: StatementDiff) -> None:
        """Test diff view shows unchanged ratio."""
        view = create_diff_view(sample_diff)

        # Should show "Unchanged:" text
        assert _contains_text(view, "Unchanged")

    def test_diff_view_uses_iframe(self, sample_diff: StatementDiff) -> None:
        """Test diff view uses iframe for isolated styles."""
        view = create_diff_view(sample_diff)

        def find_iframe(component) -> bool:
            if isinstance(component, html.Iframe):
                return True
            if hasattr(component, "children"):
                children = component.children
                if isinstance(children, list):
                    return any(find_iframe(c) for c in children)
                elif children is not None:
                    return find_iframe(children)
            return False

        assert find_iframe(view)


class TestEmptyDiffView:
    """Test empty/placeholder diff view."""

    def test_create_empty_view(self) -> None:
        """Test creating empty diff view."""
        view = create_empty_diff_view()

        assert view is not None
        assert isinstance(view, html.Div)

    def test_empty_view_shows_default_message(self) -> None:
        """Test empty view shows default placeholder message."""
        view = create_empty_diff_view()

        assert _contains_text(view, "Select two statement dates to compare")

    def test_empty_view_with_custom_message(self) -> None:
        """Test empty view with custom message."""
        custom_msg = "No statements available"
        view = create_empty_diff_view(custom_msg)

        assert _contains_text(view, custom_msg)


class TestLoadingDiffView:
    """Test loading state diff view."""

    def test_create_loading_view(self) -> None:
        """Test creating loading diff view."""
        view = create_loading_diff_view()

        assert view is not None
        assert isinstance(view, html.Div)

    def test_loading_view_has_spinner(self) -> None:
        """Test loading view contains spinner."""
        view = create_loading_diff_view()

        def find_spinner(component) -> bool:
            if isinstance(component, dbc.Spinner):
                return True
            if hasattr(component, "children"):
                children = component.children
                if isinstance(children, list):
                    return any(find_spinner(c) for c in children)
                elif children is not None:
                    return find_spinner(children)
            return False

        assert find_spinner(view)


class TestErrorDiffView:
    """Test error state diff view."""

    def test_create_error_view(self) -> None:
        """Test creating error diff view."""
        view = create_error_diff_view("Failed to load statements")

        assert view is not None
        assert isinstance(view, html.Div)

    def test_error_view_shows_message(self) -> None:
        """Test error view displays error message."""
        error_msg = "Failed to load statements"
        view = create_error_diff_view(error_msg)

        assert _contains_text(view, error_msg)


class TestColorConstants:
    """Test color constant values."""

    def test_hawkish_color_is_red(self) -> None:
        """Test hawkish color is red (#ff4444)."""
        assert HAWKISH_COLOR == "#ff4444"

    def test_dovish_color_is_green(self) -> None:
        """Test dovish color is green (#00ff88)."""
        assert DOVISH_COLOR == "#00ff88"

    def test_neutral_color_is_gray(self) -> None:
        """Test neutral color is gray (#888888)."""
        assert NEUTRAL_COLOR == "#888888"


class TestHelperFunctions:
    """Test helper functions for callbacks."""

    def test_format_date_option(self) -> None:
        """Test formatting date for dropdown option."""
        test_date = date(2024, 1, 31)
        option = format_date_option(test_date)

        assert option["label"] == "Jan 31, 2024"
        assert option["value"] == "2024-01-31"

    def test_get_available_dates_options(self) -> None:
        """Test converting dates list to dropdown options."""
        dates = [date(2024, 1, 31), date(2024, 3, 20), date(2023, 12, 13)]
        options = get_available_dates_options(dates)

        assert len(options) == 3
        # Should be sorted descending (most recent first)
        assert options[0]["value"] == "2024-03-20"
        assert options[1]["value"] == "2024-01-31"
        assert options[2]["value"] == "2023-12-13"

    def test_get_available_dates_options_empty(self) -> None:
        """Test empty dates list returns empty options."""
        options = get_available_dates_options([])
        assert options == []

    def test_parse_date_value_valid(self) -> None:
        """Test parsing valid date string."""
        result = parse_date_value("2024-01-31")
        assert result == date(2024, 1, 31)

    def test_parse_date_value_none(self) -> None:
        """Test parsing None returns None."""
        result = parse_date_value(None)
        assert result is None

    def test_parse_date_value_invalid(self) -> None:
        """Test parsing invalid string returns None."""
        result = parse_date_value("invalid-date")
        assert result is None

    def test_parse_date_value_empty_string(self) -> None:
        """Test parsing empty string returns None."""
        result = parse_date_value("")
        assert result is None


class TestIntegrationWithDiffEngine:
    """Integration tests with real diff engine."""

    def test_full_panel_with_real_diff(self) -> None:
        """Test creating panel and populating with real diff."""
        # Create panel
        panel = create_fomc_diff_panel()
        assert panel is not None

        # Create real diff
        engine = StatementDiffEngine()
        diff = engine.diff(
            old_text=(
                "The Committee seeks to achieve maximum employment and inflation "
                "at the rate of 2 percent over the longer run. The Committee "
                "remains highly attentive to inflation risks."
            ),
            new_text=(
                "The Committee seeks to achieve maximum employment and inflation "
                "at the rate of 2 percent over the longer run. The Committee "
                "remains attentive to inflation risks."
            ),
            old_date=date(2024, 1, 31),
            new_date=date(2024, 3, 20),
        )

        # Create summary and view
        summary = create_change_summary(diff.change_score, diff.phrase_shifts)
        view = create_diff_view(diff)

        assert summary is not None
        assert view is not None

    def test_hawkish_to_dovish_shift_display(self) -> None:
        """Test display of hawkish to dovish shift."""
        engine = StatementDiffEngine()
        diff = engine.diff(
            old_text="The labor market remains tight with solid job gains. "
                     "The Committee is prepared to adjust the stance.",
            new_text="The labor market remains balanced with moderate job gains. "
                     "The Committee is patient in assessing the outlook.",
            old_date=date(2024, 1, 1),
            new_date=date(2024, 6, 1),
        )

        summary = create_change_summary(diff.change_score, diff.phrase_shifts)

        # Should detect dovish shift
        assert diff.change_score.direction == "dovish"
        assert _contains_text(summary, "DOVISH")


# =============================================================================
# Helper Functions
# =============================================================================


def _contains_text(component, text: str) -> bool:
    """Recursively check if component contains specific text.

    Args:
        component: Dash component to search.
        text: Text to find.

    Returns:
        True if text found, False otherwise.
    """
    if isinstance(component, str) and text in component:
        return True

    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, str) and text in children:
            return True
        if isinstance(children, list):
            return any(_contains_text(c, text) for c in children)
        elif children is not None:
            return _contains_text(children, text)

    # Check style attribute for color values
    if hasattr(component, "style") and isinstance(component.style, dict):
        for value in component.style.values():
            if isinstance(value, str) and text in value:
                return True

    return False
