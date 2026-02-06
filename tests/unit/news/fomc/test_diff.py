"""Tests for FOMC Statement Diff Engine.

Uses real FOMC statement excerpts for realistic testing.
"""

from datetime import date

import pytest

# Import directly from diff module to avoid schemas.py import issues
from liquidity.news.fomc.diff import (
    ChangeScore,
    DiffOp,
    PhraseShift,
    PolicySignal,
    SemanticDiffLayer,
    StatementDiff,
    StatementDiffEngine,
    diff_statements,
)

# =============================================================================
# Real FOMC Statement Excerpts for Testing
# =============================================================================

# January 2024 statement (hawkish stance)
FOMC_JAN_2024 = """
The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent
over the longer run. The Committee judges that the risks to achieving its employment and
inflation goals are moving into better balance. The economic outlook is uncertain, and the
Committee remains highly attentive to inflation risks.

In support of its goals, the Committee decided to maintain the target range for the federal
funds rate at 5-1/4 to 5-1/2 percent. In considering any adjustments to the target range for
the federal funds rate, the Committee will carefully assess incoming data, the evolving
outlook, and the balance of risks.
"""

# March 2024 statement (slightly more dovish)
FOMC_MAR_2024 = """
The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent
over the longer run. The Committee judges that the risks to achieving its employment and
inflation goals are moving into better balance. The economic outlook is uncertain, and the
Committee remains attentive to inflation risks.

In support of its goals, the Committee decided to maintain the target range for the federal
funds rate at 5-1/4 to 5-1/2 percent. In considering any adjustments to the target range for
the federal funds rate, the Committee will carefully assess incoming data, the evolving
outlook, and the balance of risks. The Committee does not expect it will be appropriate to
reduce the target range until it has gained greater confidence that inflation is moving
sustainably toward 2 percent.
"""

# Simple hawkish to dovish shift
HAWKISH_STATEMENT = """
The labor market remains tight with solid job gains. Inflation remains elevated and the
Committee is highly attentive to inflation risks. The Committee is prepared to adjust the
stance of monetary policy as appropriate.
"""

DOVISH_STATEMENT = """
The labor market remains balanced with moderate job gains. Inflation has been subdued and
the Committee is patient in assessing the outlook. The Committee will take a gradual approach
to adjusting the stance of monetary policy.
"""

# Empty and edge case statements
EMPTY_STATEMENT = ""
IDENTICAL_STATEMENT = "The Committee decided to maintain rates."


class TestDiffOp:
    """Tests for DiffOp schema."""

    def test_equal_op(self) -> None:
        """Equal operation should have both texts."""
        op = DiffOp(op="equal", old_text="test", new_text="test", position=0)
        assert op.op == "equal"
        assert op.old_text == "test"
        assert op.new_text == "test"

    def test_insert_op(self) -> None:
        """Insert operation should have only new text."""
        op = DiffOp(op="insert", old_text=None, new_text="added", position=5)
        assert op.op == "insert"
        assert op.old_text is None
        assert op.new_text == "added"

    def test_delete_op(self) -> None:
        """Delete operation should have only old text."""
        op = DiffOp(op="delete", old_text="removed", new_text=None, position=3)
        assert op.op == "delete"
        assert op.old_text == "removed"
        assert op.new_text is None

    def test_replace_op(self) -> None:
        """Replace operation should have both texts."""
        op = DiffOp(op="replace", old_text="old", new_text="new", position=2)
        assert op.op == "replace"
        assert op.old_text == "old"
        assert op.new_text == "new"


class TestPhraseShift:
    """Tests for PhraseShift schema."""

    def test_added_phrase(self) -> None:
        """Added phrase should have correct fields."""
        shift = PhraseShift(phrase="patient", change="added", policy_signal="dovish")
        assert shift.phrase == "patient"
        assert shift.change == "added"
        assert shift.policy_signal == "dovish"

    def test_removed_phrase(self) -> None:
        """Removed phrase should have correct fields."""
        shift = PhraseShift(phrase="restrictive", change="removed", policy_signal="hawkish")
        assert shift.change == "removed"


class TestChangeScore:
    """Tests for ChangeScore schema."""

    def test_hawkish_score(self) -> None:
        """Hawkish score should be positive."""
        score = ChangeScore(direction="hawkish", magnitude=0.5, key_changes=["+elevated"])
        assert score.direction == "hawkish"
        assert score.magnitude > 0

    def test_dovish_score(self) -> None:
        """Dovish score should be negative."""
        score = ChangeScore(direction="dovish", magnitude=-0.3, key_changes=["-patient"])
        assert score.direction == "dovish"
        assert score.magnitude < 0

    def test_neutral_score(self) -> None:
        """Neutral score should be near zero."""
        score = ChangeScore(direction="neutral", magnitude=0.0, key_changes=[])
        assert score.direction == "neutral"
        assert abs(score.magnitude) <= 0.1


class TestSemanticDiffLayer:
    """Tests for SemanticDiffLayer."""

    @pytest.fixture
    def layer(self) -> SemanticDiffLayer:
        """Default semantic layer."""
        return SemanticDiffLayer.default()

    def test_score_hawkish_text(self, layer: SemanticDiffLayer) -> None:
        """Hawkish text should score positive."""
        text = "Inflation remains elevated and the labor market is tight."
        score, matched = layer.score_text(text)
        assert score > 0
        assert any("elevated" in m for m in matched)

    def test_score_dovish_text(self, layer: SemanticDiffLayer) -> None:
        """Dovish text should score negative."""
        text = "The Committee remains patient with a gradual approach."
        score, matched = layer.score_text(text)
        assert score < 0
        assert any("patient" in m or "gradual" in m for m in matched)

    def test_score_neutral_text(self, layer: SemanticDiffLayer) -> None:
        """Neutral text should score near zero."""
        text = "The Committee met today to discuss policy."
        score, _ = layer.score_text(text)
        assert abs(score) < 0.5

    def test_detect_phrase_shifts_added(self, layer: SemanticDiffLayer) -> None:
        """Should detect added policy phrases."""
        old = "The Committee discussed the outlook."
        new = "The Committee remains patient with the outlook."
        shifts = layer.detect_phrase_shifts(old, new)

        added_phrases = [s.phrase for s in shifts if s.change == "added"]
        assert "patient" in added_phrases

    def test_detect_phrase_shifts_removed(self, layer: SemanticDiffLayer) -> None:
        """Should detect removed policy phrases."""
        old = "The labor market remains tight with solid job gains."
        new = "The labor market shows signs of cooling."
        shifts = layer.detect_phrase_shifts(old, new)

        # "solid" was removed, "cooling" was added
        removed = [s for s in shifts if s.change == "removed"]
        added = [s for s in shifts if s.change == "added"]

        assert any(s.phrase == "solid" for s in removed)
        assert any(s.phrase == "cooling" for s in added)

    def test_compute_change_score_hawkish_shift(self, layer: SemanticDiffLayer) -> None:
        """Adding hawkish, removing dovish should score hawkish."""
        additions = ["elevated inflation", "tight labor market"]
        deletions = ["patient", "gradual"]

        score = layer.compute_change_score(additions, deletions)
        assert score.direction == "hawkish"
        assert score.magnitude > 0

    def test_compute_change_score_dovish_shift(self, layer: SemanticDiffLayer) -> None:
        """Adding dovish, removing hawkish should score dovish."""
        additions = ["patient", "gradual approach", "subdued"]
        deletions = ["elevated", "tight labor market"]

        score = layer.compute_change_score(additions, deletions)
        assert score.direction == "dovish"
        assert score.magnitude < 0


class TestStatementDiffEngine:
    """Tests for StatementDiffEngine."""

    @pytest.fixture
    def engine(self) -> StatementDiffEngine:
        """Default diff engine."""
        return StatementDiffEngine()

    def test_tokenize_simple(self, engine: StatementDiffEngine) -> None:
        """Should tokenize simple text."""
        words = engine.tokenize("The Committee decided today.")
        assert words == ["The", "Committee", "decided", "today."]

    def test_tokenize_empty(self, engine: StatementDiffEngine) -> None:
        """Empty text should return empty list."""
        words = engine.tokenize("")
        assert words == []

    def test_normalize_whitespace(self, engine: StatementDiffEngine) -> None:
        """Should normalize whitespace."""
        text = "The   Committee\n\ndecided\t today."
        normalized = engine.normalize(text)
        assert normalized == "The Committee decided today."

    def test_compute_operations_identical(self, engine: StatementDiffEngine) -> None:
        """Identical text should have all equal operations."""
        words = ["The", "Committee", "decided."]
        ops = engine.compute_operations(words, words)

        assert len(ops) == 1
        assert ops[0].op == "equal"

    def test_compute_operations_insert(self, engine: StatementDiffEngine) -> None:
        """Should detect insertions."""
        old = ["The", "Committee", "decided."]
        new = ["The", "Committee", "unanimously", "decided."]
        ops = engine.compute_operations(old, new)

        insert_ops = [op for op in ops if op.op == "insert"]
        assert len(insert_ops) >= 1
        assert any("unanimously" in (op.new_text or "") for op in insert_ops)

    def test_compute_operations_delete(self, engine: StatementDiffEngine) -> None:
        """Should detect deletions."""
        old = ["The", "Committee", "unanimously", "decided."]
        new = ["The", "Committee", "decided."]
        ops = engine.compute_operations(old, new)

        delete_ops = [op for op in ops if op.op == "delete"]
        assert len(delete_ops) >= 1
        assert any("unanimously" in (op.old_text or "") for op in delete_ops)

    def test_compute_operations_replace(self, engine: StatementDiffEngine) -> None:
        """Should detect replacements."""
        old = ["The", "hawkish", "stance."]
        new = ["The", "dovish", "stance."]
        ops = engine.compute_operations(old, new)

        replace_ops = [op for op in ops if op.op == "replace"]
        assert len(replace_ops) >= 1

    def test_extract_changes(self, engine: StatementDiffEngine) -> None:
        """Should extract additions and deletions from operations."""
        ops = [
            DiffOp(op="equal", old_text="The", new_text="The", position=0),
            DiffOp(op="delete", old_text="old", new_text=None, position=1),
            DiffOp(op="insert", old_text=None, new_text="new", position=1),
        ]
        additions, deletions = engine.extract_changes(ops)

        assert "new" in additions
        assert "old" in deletions

    def test_unchanged_ratio_identical(self, engine: StatementDiffEngine) -> None:
        """Identical text should have 1.0 unchanged ratio."""
        old_words = ["The", "Committee", "decided."]
        ops = engine.compute_operations(old_words, old_words)
        ratio = engine.compute_unchanged_ratio(ops, old_words)

        assert ratio == 1.0

    def test_unchanged_ratio_partial(self, engine: StatementDiffEngine) -> None:
        """Partially changed text should have ratio between 0 and 1."""
        old_words = ["The", "Committee", "decided", "today."]
        new_words = ["The", "Committee", "voted", "today."]
        ops = engine.compute_operations(old_words, new_words)
        ratio = engine.compute_unchanged_ratio(ops, old_words)

        assert 0 < ratio < 1

    def test_render_html_contains_styles(self, engine: StatementDiffEngine) -> None:
        """HTML should contain inline styles."""
        ops = [DiffOp(op="equal", old_text="test", new_text="test", position=0)]
        html = engine.render_html(ops)

        assert "<style>" in html
        assert ".fomc-diff" in html

    def test_render_html_added_class(self, engine: StatementDiffEngine) -> None:
        """Added text should have 'added' class."""
        ops = [DiffOp(op="insert", old_text=None, new_text="new", position=0)]
        html = engine.render_html(ops)

        assert 'class="added"' in html
        assert "new" in html

    def test_render_html_removed_class(self, engine: StatementDiffEngine) -> None:
        """Removed text should have 'removed' class."""
        ops = [DiffOp(op="delete", old_text="old", new_text=None, position=0)]
        html = engine.render_html(ops)

        assert 'class="removed"' in html
        assert "old" in html

    def test_render_html_escapes_special_chars(self, engine: StatementDiffEngine) -> None:
        """HTML special characters should be escaped."""
        ops = [DiffOp(op="equal", old_text="<script>", new_text="<script>", position=0)]
        html = engine.render_html(ops)

        assert "&lt;script&gt;" in html
        assert "<script>" not in html.replace("&lt;script&gt;", "")


class TestStatementDiffIntegration:
    """Integration tests with real FOMC statements."""

    @pytest.fixture
    def engine(self) -> StatementDiffEngine:
        """Default diff engine."""
        return StatementDiffEngine()

    def test_diff_jan_to_mar_2024(self, engine: StatementDiffEngine) -> None:
        """January to March 2024 should show slight dovish shift."""
        diff = engine.diff(
            old_text=FOMC_JAN_2024,
            new_text=FOMC_MAR_2024,
            old_date=date(2024, 1, 31),
            new_date=date(2024, 3, 20),
        )

        # Should have some changes
        assert len(diff.operations) > 1
        assert len(diff.additions) > 0 or len(diff.deletions) > 0

        # Unchanged ratio should be high (statements are similar)
        assert diff.unchanged_ratio > 0.6

        # Should detect "highly attentive" -> "attentive" change
        assert any("highly" in d for d in diff.deletions) or \
               any("highly attentive" in d for d in diff.deletions)

        # HTML should be valid
        assert "<style>" in diff.html
        assert "</div>" in diff.html

    def test_diff_hawkish_to_dovish(self, engine: StatementDiffEngine) -> None:
        """Hawkish to dovish shift should score dovish."""
        diff = engine.diff(
            old_text=HAWKISH_STATEMENT,
            new_text=DOVISH_STATEMENT,
            old_date=date(2024, 1, 1),
            new_date=date(2024, 6, 1),
        )

        # Should detect dovish shift
        assert diff.change_score.direction == "dovish"
        assert diff.change_score.magnitude < 0

        # Should have phrase shifts
        assert len(diff.phrase_shifts) > 0

        # Check specific shifts
        added_phrases = [s.phrase for s in diff.phrase_shifts if s.change == "added"]
        [s.phrase for s in diff.phrase_shifts if s.change == "removed"]

        # Dovish phrases added
        assert any(p in added_phrases for p in ["patient", "subdued", "gradual"])

    def test_diff_identical_statements(self, engine: StatementDiffEngine) -> None:
        """Identical statements should have no changes."""
        diff = engine.diff(
            old_text=IDENTICAL_STATEMENT,
            new_text=IDENTICAL_STATEMENT,
            old_date=date(2024, 1, 1),
            new_date=date(2024, 1, 1),
        )

        assert diff.unchanged_ratio == 1.0
        assert len(diff.additions) == 0
        assert len(diff.deletions) == 0
        assert diff.change_score.direction == "neutral"
        assert diff.change_score.magnitude == 0.0

    def test_diff_empty_old_statement(self, engine: StatementDiffEngine) -> None:
        """Empty old statement should have all additions."""
        diff = engine.diff(
            old_text=EMPTY_STATEMENT,
            new_text=IDENTICAL_STATEMENT,
            old_date=date(2024, 1, 1),
            new_date=date(2024, 2, 1),
        )

        assert len(diff.additions) > 0
        assert len(diff.deletions) == 0
        # All operations should be inserts
        assert all(op.op in ("insert", "equal") for op in diff.operations)

    def test_diff_empty_new_statement(self, engine: StatementDiffEngine) -> None:
        """Empty new statement should have all deletions."""
        diff = engine.diff(
            old_text=IDENTICAL_STATEMENT,
            new_text=EMPTY_STATEMENT,
            old_date=date(2024, 1, 1),
            new_date=date(2024, 2, 1),
        )

        assert len(diff.deletions) > 0
        assert len(diff.additions) == 0

    def test_diff_preserves_dates(self, engine: StatementDiffEngine) -> None:
        """Diff should preserve input dates."""
        old_d = date(2023, 6, 14)
        new_d = date(2023, 7, 26)

        diff = engine.diff(
            old_text="Test",
            new_text="Test",
            old_date=old_d,
            new_date=new_d,
        )

        assert diff.old_date == old_d
        assert diff.new_date == new_d


class TestConvenienceFunction:
    """Tests for diff_statements convenience function."""

    def test_diff_statements_returns_statement_diff(self) -> None:
        """Should return StatementDiff object."""
        result = diff_statements(
            old_text="The Committee decided.",
            new_text="The Committee voted.",
            old_date=date(2024, 1, 1),
            new_date=date(2024, 2, 1),
        )

        assert isinstance(result, StatementDiff)
        assert result.old_date == date(2024, 1, 1)
        assert result.new_date == date(2024, 2, 1)

    def test_diff_statements_real_data(self) -> None:
        """Should work with real FOMC excerpts."""
        result = diff_statements(
            old_text=FOMC_JAN_2024,
            new_text=FOMC_MAR_2024,
            old_date=date(2024, 1, 31),
            new_date=date(2024, 3, 20),
        )

        assert len(result.operations) > 0
        assert result.html is not None


class TestPolicySignalEnum:
    """Tests for PolicySignal enum."""

    def test_enum_values(self) -> None:
        """Enum should have correct values."""
        assert PolicySignal.HAWKISH.value == "hawkish"
        assert PolicySignal.DOVISH.value == "dovish"
        assert PolicySignal.NEUTRAL.value == "neutral"

    def test_enum_is_string(self) -> None:
        """Enum value should be usable as string."""
        # PolicySignal extends str, so .value gives the string
        assert PolicySignal.HAWKISH.value == "hawkish"
        # Can be used in string comparisons
        assert PolicySignal.HAWKISH == "hawkish"


class TestEdgeCases:
    """Edge case tests."""

    @pytest.fixture
    def engine(self) -> StatementDiffEngine:
        """Default diff engine."""
        return StatementDiffEngine()

    def test_very_long_statement(self, engine: StatementDiffEngine) -> None:
        """Should handle very long statements."""
        long_text = " ".join(["word"] * 5000)
        diff = engine.diff(
            old_text=long_text,
            new_text=long_text + " extra",
            old_date=date(2024, 1, 1),
            new_date=date(2024, 2, 1),
        )

        assert diff.unchanged_ratio > 0.99
        assert len(diff.additions) > 0

    def test_special_characters(self, engine: StatementDiffEngine) -> None:
        """Should handle special characters."""
        old = "Rate: 5.25%-5.50% (Fed funds)"
        new = "Rate: 5.00%-5.25% (Fed funds)"

        diff = engine.diff(
            old_text=old,
            new_text=new,
            old_date=date(2024, 1, 1),
            new_date=date(2024, 2, 1),
        )

        assert len(diff.operations) > 0
        # HTML should escape special chars properly
        assert "&" not in diff.html or "&amp;" in diff.html

    def test_unicode_text(self, engine: StatementDiffEngine) -> None:
        """Should handle unicode text."""
        old = "The Committee discussed policy."
        new = "The Committee discussed policy."

        diff = engine.diff(
            old_text=old,
            new_text=new,
            old_date=date(2024, 1, 1),
            new_date=date(2024, 2, 1),
        )

        # Should handle gracefully
        assert diff is not None

    def test_whitespace_only_changes(self, engine: StatementDiffEngine) -> None:
        """Changes in whitespace only should result in identical normalized text."""
        old = "The  Committee   decided."
        new = "The Committee decided."

        diff = engine.diff(
            old_text=old,
            new_text=new,
            old_date=date(2024, 1, 1),
            new_date=date(2024, 2, 1),
        )

        # After normalization, should be identical
        assert diff.unchanged_ratio == 1.0

    def test_custom_semantic_layer(self) -> None:
        """Should support custom semantic layer."""
        custom_layer = SemanticDiffLayer(
            hawkish_lexicon={"test_hawk": 1.0},
            dovish_lexicon={"test_dove": 1.0},
            policy_phrases={"custom_phrase": PolicySignal.HAWKISH},
        )
        engine = StatementDiffEngine(semantic_layer=custom_layer)

        diff = engine.diff(
            old_text="No phrases here",
            new_text="Added custom_phrase and test_hawk",
            old_date=date(2024, 1, 1),
            new_date=date(2024, 2, 1),
        )

        # Should detect custom phrase
        assert any(s.phrase == "custom_phrase" for s in diff.phrase_shifts)

        # Should score based on custom lexicon
        assert diff.change_score.magnitude > 0
