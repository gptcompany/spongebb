"""FOMC Statement Diff Engine.

Word-level diff between consecutive FOMC statements with hawkish/dovish scoring.

Methodology:
- Uses stdlib difflib.SequenceMatcher for word-level diff
- Semantic phrase detection for policy-relevant changes
- Bloomberg-style HTML output with red/green highlighting

Usage:
    from liquidity.news.fomc.diff import StatementDiffEngine

    engine = StatementDiffEngine()
    diff = engine.diff(old_statement, new_statement, old_date, new_date)
    print(diff.change_score.direction)  # "hawkish" | "dovish" | "neutral"
    print(diff.html)  # Bloomberg-style HTML
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Policy Phrase Lexicons
# =============================================================================


class PolicySignal(str, Enum):
    """Policy signal direction."""

    HAWKISH = "hawkish"
    DOVISH = "dovish"
    NEUTRAL = "neutral"


# Hawkish phrases indicate tightening bias
HAWKISH_PHRASES: dict[str, float] = {
    # Rate/Inflation focused
    "inflation": 0.2,
    "elevated": 0.3,
    "elevated inflation": 0.5,
    "price stability": 0.2,
    "price pressures": 0.4,
    "restrictive": 0.5,
    "sufficiently restrictive": 0.6,
    "tightening": 0.5,
    "further tightening": 0.7,
    "additional firming": 0.6,
    "tight labor market": 0.3,
    "strong labor market": 0.2,
    # Activity focused
    "robust": 0.3,
    "solid": 0.2,
    "solid pace": 0.3,
    "strong pace": 0.4,
    "brisk": 0.3,
    "near-term": 0.1,
    # Urgency
    "highly attentive": 0.4,
    "closely monitoring": 0.3,
    "prepared to adjust": 0.4,
    "appropriate": 0.1,
}

# Dovish phrases indicate easing bias
DOVISH_PHRASES: dict[str, float] = {
    # Rate/Easing focused
    "accommodative": 0.5,
    "patient": 0.4,
    "data-dependent": 0.2,
    "data dependent": 0.2,
    "gradual": 0.3,
    "gradual approach": 0.4,
    "considerable time": 0.5,
    "some time": 0.3,
    "at some point": 0.3,
    "well anchored": 0.3,
    "anchored": 0.2,
    # Weakness focused
    "subdued": 0.4,
    "softening": 0.4,
    "cooling": 0.3,
    "slowing": 0.3,
    "moderate pace": 0.2,
    "modest pace": 0.3,
    "modest growth": 0.3,
    "slowdown": 0.4,
    "downside risks": 0.5,
    # Balance sheet
    "reinvesting": 0.3,
    "purchases": 0.2,
    # Outlook
    "uncertainty": 0.2,
    "uncertain": 0.2,
    "evolving outlook": 0.2,
}

# Policy phrases for phrase-shift detection (phrase -> signal)
POLICY_PHRASES: dict[str, PolicySignal] = {
    # Dovish
    "patient": PolicySignal.DOVISH,
    "data-dependent": PolicySignal.NEUTRAL,
    "data dependent": PolicySignal.NEUTRAL,
    "gradual": PolicySignal.DOVISH,
    "considerable time": PolicySignal.DOVISH,
    "near-term": PolicySignal.HAWKISH,
    "subdued": PolicySignal.DOVISH,
    "well anchored": PolicySignal.DOVISH,
    "anchored": PolicySignal.DOVISH,
    "moderate pace": PolicySignal.DOVISH,
    "modest pace": PolicySignal.DOVISH,
    "softening": PolicySignal.DOVISH,
    "cooling": PolicySignal.DOVISH,
    "downside risks": PolicySignal.DOVISH,
    # Hawkish
    "solid": PolicySignal.HAWKISH,
    "robust": PolicySignal.HAWKISH,
    "restrictive": PolicySignal.HAWKISH,
    "sufficiently restrictive": PolicySignal.HAWKISH,
    "elevated": PolicySignal.HAWKISH,
    "elevated inflation": PolicySignal.HAWKISH,
    "tight labor market": PolicySignal.HAWKISH,
    "strong labor market": PolicySignal.HAWKISH,
    "further tightening": PolicySignal.HAWKISH,
    "additional firming": PolicySignal.HAWKISH,
    "highly attentive": PolicySignal.HAWKISH,
    "prepared to adjust": PolicySignal.HAWKISH,
    "strong pace": PolicySignal.HAWKISH,
    "brisk": PolicySignal.HAWKISH,
}


# =============================================================================
# Pydantic Schemas
# =============================================================================


class DiffOp(BaseModel):
    """Single diff operation."""

    op: Literal["equal", "insert", "delete", "replace"] = Field(
        description="Operation type"
    )
    old_text: str | None = Field(default=None, description="Original text (for delete/replace)")
    new_text: str | None = Field(default=None, description="New text (for insert/replace)")
    position: int = Field(ge=0, description="Word position in original text")


class PhraseShift(BaseModel):
    """Detected policy phrase change."""

    phrase: str = Field(description="The policy phrase")
    change: Literal["added", "removed"] = Field(description="Whether phrase was added or removed")
    policy_signal: str = Field(description="hawkish, dovish, or neutral")


class ChangeScore(BaseModel):
    """Overall hawkish/dovish scoring of the diff."""

    direction: Literal["hawkish", "dovish", "neutral"] = Field(
        description="Net direction of changes"
    )
    magnitude: float = Field(
        ge=-1.0, le=1.0, description="Score magnitude (-1 dovish to +1 hawkish)"
    )
    key_changes: list[str] = Field(
        default_factory=list, description="Most significant changes"
    )


class StatementDiff(BaseModel):
    """Complete diff result between two FOMC statements."""

    old_date: date = Field(description="Date of previous statement")
    new_date: date = Field(description="Date of current statement")
    operations: list[DiffOp] = Field(default_factory=list, description="All diff operations")
    additions: list[str] = Field(default_factory=list, description="Added text segments")
    deletions: list[str] = Field(default_factory=list, description="Removed text segments")
    unchanged_ratio: float = Field(
        ge=0.0, le=1.0, description="Fraction of text unchanged"
    )
    change_score: ChangeScore = Field(description="Hawkish/dovish scoring")
    phrase_shifts: list[PhraseShift] = Field(
        default_factory=list, description="Detected policy phrase changes"
    )
    html: str = Field(description="Bloomberg-style HTML rendering")


# =============================================================================
# Semantic Phrase Detection Layer
# =============================================================================


@dataclass
class SemanticDiffLayer:
    """Detects policy-relevant phrase changes in FOMC statements.

    This layer operates on top of the word-level diff to identify:
    - Additions/removals of known policy phrases
    - Hawkish/dovish scoring based on keyword lexicons
    """

    hawkish_lexicon: dict[str, float]
    dovish_lexicon: dict[str, float]
    policy_phrases: dict[str, PolicySignal]

    @classmethod
    def default(cls) -> SemanticDiffLayer:
        """Create with default lexicons."""
        return cls(
            hawkish_lexicon=HAWKISH_PHRASES,
            dovish_lexicon=DOVISH_PHRASES,
            policy_phrases=POLICY_PHRASES,
        )

    def score_text(self, text: str) -> tuple[float, list[str]]:
        """Score text for hawkish/dovish sentiment.

        Args:
            text: Text to score

        Returns:
            Tuple of (score, list of matched phrases)
            Score > 0 is hawkish, < 0 is dovish
        """
        text_lower = text.lower()
        score = 0.0
        matched: list[str] = []

        # Check hawkish phrases (sorted by length desc for longest match first)
        for phrase, weight in sorted(
            self.hawkish_lexicon.items(), key=lambda x: -len(x[0])
        ):
            if phrase in text_lower:
                score += weight
                matched.append(f"+{phrase}")

        # Check dovish phrases
        for phrase, weight in sorted(
            self.dovish_lexicon.items(), key=lambda x: -len(x[0])
        ):
            if phrase in text_lower:
                score -= weight
                matched.append(f"-{phrase}")

        return score, matched

    def detect_phrase_shifts(
        self, old_text: str, new_text: str
    ) -> list[PhraseShift]:
        """Detect policy phrase additions and removals.

        Args:
            old_text: Previous statement text
            new_text: Current statement text

        Returns:
            List of detected phrase shifts
        """
        old_lower = old_text.lower()
        new_lower = new_text.lower()
        shifts: list[PhraseShift] = []

        for phrase, signal in self.policy_phrases.items():
            in_old = phrase in old_lower
            in_new = phrase in new_lower

            if in_new and not in_old:
                shifts.append(
                    PhraseShift(
                        phrase=phrase,
                        change="added",
                        policy_signal=signal.value,
                    )
                )
            elif in_old and not in_new:
                shifts.append(
                    PhraseShift(
                        phrase=phrase,
                        change="removed",
                        policy_signal=signal.value,
                    )
                )

        return shifts

    def compute_change_score(
        self, additions: list[str], deletions: list[str]
    ) -> ChangeScore:
        """Compute overall hawkish/dovish change score.

        Args:
            additions: Added text segments
            deletions: Removed text segments

        Returns:
            ChangeScore with direction, magnitude, and key changes
        """
        added_text = " ".join(additions)
        deleted_text = " ".join(deletions)

        add_score, add_matches = self.score_text(added_text)
        del_score, del_matches = self.score_text(deleted_text)

        # Net score: additions contribute positively, deletions negatively
        # Adding hawkish (+) increases score, removing dovish (+) increases score
        # Adding dovish (-) decreases score, removing hawkish (-) decreases score
        net_score = add_score - del_score

        # Normalize to [-1, 1] range (clamp)
        magnitude = max(-1.0, min(1.0, net_score))

        # Determine direction
        if magnitude > 0.1:
            direction: Literal["hawkish", "dovish", "neutral"] = "hawkish"
        elif magnitude < -0.1:
            direction = "dovish"
        else:
            direction = "neutral"

        # Collect key changes
        key_changes = add_matches + [f"(removed){m}" for m in del_matches]

        return ChangeScore(
            direction=direction,
            magnitude=round(magnitude, 3),
            key_changes=key_changes[:10],  # Limit to top 10
        )


# =============================================================================
# Statement Diff Engine
# =============================================================================


class StatementDiffEngine:
    """Word-level diff engine for FOMC statements.

    Uses difflib.SequenceMatcher for efficient word-level comparison
    and SemanticDiffLayer for policy-relevant phrase detection.

    Example:
        engine = StatementDiffEngine()
        diff = engine.diff(
            old_text="The Committee remains patient.",
            new_text="The Committee is prepared to adjust.",
            old_date=date(2024, 1, 31),
            new_date=date(2024, 3, 20),
        )
        print(diff.change_score.direction)  # "hawkish"
    """

    def __init__(self, semantic_layer: SemanticDiffLayer | None = None) -> None:
        """Initialize the diff engine.

        Args:
            semantic_layer: Custom semantic layer, or None for default
        """
        self.semantic_layer = semantic_layer or SemanticDiffLayer.default()

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Tokenize text into words, preserving punctuation.

        Args:
            text: Input text

        Returns:
            List of word tokens
        """
        if not text:
            return []
        # Split on whitespace, keeping punctuation attached to words
        return text.split()

    @staticmethod
    def normalize(text: str) -> str:
        """Normalize text for comparison.

        Args:
            text: Input text

        Returns:
            Normalized text (lowercase, normalized whitespace)
        """
        # Collapse multiple spaces/newlines to single space
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def compute_operations(
        self, old_words: list[str], new_words: list[str]
    ) -> list[DiffOp]:
        """Compute diff operations between word lists.

        Uses SequenceMatcher.get_opcodes() for optimal diff.

        Args:
            old_words: Words from previous statement
            new_words: Words from current statement

        Returns:
            List of DiffOp objects
        """
        matcher = SequenceMatcher(None, old_words, new_words)
        operations: list[DiffOp] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                operations.append(
                    DiffOp(
                        op="equal",
                        old_text=" ".join(old_words[i1:i2]),
                        new_text=" ".join(new_words[j1:j2]),
                        position=i1,
                    )
                )
            elif tag == "replace":
                operations.append(
                    DiffOp(
                        op="replace",
                        old_text=" ".join(old_words[i1:i2]),
                        new_text=" ".join(new_words[j1:j2]),
                        position=i1,
                    )
                )
            elif tag == "delete":
                operations.append(
                    DiffOp(
                        op="delete",
                        old_text=" ".join(old_words[i1:i2]),
                        new_text=None,
                        position=i1,
                    )
                )
            elif tag == "insert":
                operations.append(
                    DiffOp(
                        op="insert",
                        old_text=None,
                        new_text=" ".join(new_words[j1:j2]),
                        position=i1,
                    )
                )

        return operations

    def extract_changes(
        self, operations: list[DiffOp]
    ) -> tuple[list[str], list[str]]:
        """Extract additions and deletions from operations.

        Args:
            operations: List of diff operations

        Returns:
            Tuple of (additions, deletions)
        """
        additions: list[str] = []
        deletions: list[str] = []

        for op in operations:
            if op.op == "insert" and op.new_text:
                additions.append(op.new_text)
            elif op.op == "delete" and op.old_text:
                deletions.append(op.old_text)
            elif op.op == "replace":
                if op.old_text:
                    deletions.append(op.old_text)
                if op.new_text:
                    additions.append(op.new_text)

        return additions, deletions

    def compute_unchanged_ratio(
        self, operations: list[DiffOp], old_words: list[str]
    ) -> float:
        """Compute fraction of text that remained unchanged.

        Args:
            operations: List of diff operations
            old_words: Original word list

        Returns:
            Ratio of unchanged words (0.0 to 1.0)
        """
        if not old_words:
            return 1.0

        equal_count = sum(
            len(op.old_text.split()) if op.old_text else 0
            for op in operations
            if op.op == "equal"
        )

        return round(equal_count / len(old_words), 3)

    def render_html(self, operations: list[DiffOp]) -> str:
        """Render diff as Bloomberg-style HTML.

        Colors:
        - Green (#00ff88): Additions
        - Red (#ff4444): Deletions
        - Background highlights for inline changes

        Args:
            operations: List of diff operations

        Returns:
            HTML string
        """
        html_parts: list[str] = []

        # CSS styles (inline for standalone HTML)
        css = """
        <style>
            .fomc-diff { font-family: 'Georgia', serif; line-height: 1.8; color: #e0e0e0; }
            .fomc-diff .added { color: #00ff88; background: rgba(0, 255, 136, 0.1); padding: 2px 4px; border-radius: 2px; }
            .fomc-diff .removed { color: #ff4444; background: rgba(255, 68, 68, 0.1); padding: 2px 4px; border-radius: 2px; text-decoration: line-through; }
            .fomc-diff .replaced-old { color: #ff4444; background: rgba(255, 68, 68, 0.1); padding: 2px 4px; border-radius: 2px; text-decoration: line-through; }
            .fomc-diff .replaced-new { color: #00ff88; background: rgba(0, 255, 136, 0.1); padding: 2px 4px; border-radius: 2px; }
            .fomc-diff .unchanged { color: #888888; }
        </style>
        """
        html_parts.append(css)
        html_parts.append('<div class="fomc-diff">')

        for op in operations:
            if op.op == "equal":
                text = self._escape_html(op.old_text or "")
                html_parts.append(f'<span class="unchanged">{text}</span> ')
            elif op.op == "insert":
                text = self._escape_html(op.new_text or "")
                html_parts.append(f'<span class="added">{text}</span> ')
            elif op.op == "delete":
                text = self._escape_html(op.old_text or "")
                html_parts.append(f'<span class="removed">{text}</span> ')
            elif op.op == "replace":
                old_text = self._escape_html(op.old_text or "")
                new_text = self._escape_html(op.new_text or "")
                html_parts.append(
                    f'<span class="replaced-old">{old_text}</span>'
                    f'<span class="replaced-new">{new_text}</span> '
                )

        html_parts.append("</div>")
        return "".join(html_parts)

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def diff(
        self,
        old_text: str,
        new_text: str,
        old_date: date,
        new_date: date,
    ) -> StatementDiff:
        """Compute full diff between two FOMC statements.

        Args:
            old_text: Previous statement text
            new_text: Current statement text
            old_date: Date of previous statement
            new_date: Date of current statement

        Returns:
            StatementDiff with all analysis results
        """
        # Normalize and tokenize
        old_normalized = self.normalize(old_text)
        new_normalized = self.normalize(new_text)
        old_words = self.tokenize(old_normalized)
        new_words = self.tokenize(new_normalized)

        # Compute word-level diff
        operations = self.compute_operations(old_words, new_words)

        # Extract changes
        additions, deletions = self.extract_changes(operations)

        # Compute unchanged ratio
        unchanged_ratio = self.compute_unchanged_ratio(operations, old_words)

        # Semantic analysis
        phrase_shifts = self.semantic_layer.detect_phrase_shifts(
            old_text, new_text
        )
        change_score = self.semantic_layer.compute_change_score(
            additions, deletions
        )

        # Render HTML
        html = self.render_html(operations)

        return StatementDiff(
            old_date=old_date,
            new_date=new_date,
            operations=operations,
            additions=additions,
            deletions=deletions,
            unchanged_ratio=unchanged_ratio,
            change_score=change_score,
            phrase_shifts=phrase_shifts,
            html=html,
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def diff_statements(
    old_text: str,
    new_text: str,
    old_date: date,
    new_date: date,
) -> StatementDiff:
    """Convenience function to diff two statements.

    Args:
        old_text: Previous statement text
        new_text: Current statement text
        old_date: Date of previous statement
        new_date: Date of current statement

    Returns:
        StatementDiff with all analysis results
    """
    engine = StatementDiffEngine()
    return engine.diff(old_text, new_text, old_date, new_date)
