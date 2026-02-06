"""Central Bank Speech Sentiment Analyzer.

Provides hybrid sentiment analysis for central bank communications using:
- ProsusAI/FinBERT for financial sentiment classification
- Keyword lexicons for hawkish/dovish signal detection
- Dynamic weighting based on translation confidence

The analyzer combines model-based and rule-based approaches to maximize
accuracy on CB-specific language patterns.

References:
    - ProsusAI/finbert: https://huggingface.co/ProsusAI/finbert
    - Plan 14-03: CB Speech Sentiment Analyzer
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from liquidity.news.lexicons import DOVISH_KEYWORDS, HAWKISH_KEYWORDS

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

SENTIMENT_MODEL = "ProsusAI/finbert"  # 440MB, financial sentiment

# FinBERT label to base score mapping
# Positive = slightly hawkish (optimism about economy)
# Negative = slightly dovish (concerns about economy)
FINBERT_LABEL_TO_SCORE: dict[str, float] = {
    "positive": 0.3,
    "negative": -0.3,
    "neutral": 0.0,
}

# Thresholds for hawkish/dovish classification
HAWKISH_THRESHOLD = 0.2
DOVISH_THRESHOLD = -0.2

# Maximum token length for FinBERT
MAX_LENGTH = 512

# Default weights for native English text
DEFAULT_FINBERT_WEIGHT = 0.7
DEFAULT_KEYWORD_WEIGHT = 0.3


# =============================================================================
# Data Models
# =============================================================================


class SentimentResult(BaseModel):
    """Result of sentiment analysis on a text.

    Attributes:
        sentiment: FinBERT classification (positive, negative, neutral).
        confidence: FinBERT confidence score (0-1).
        tone: Derived monetary policy tone (hawkish, dovish, neutral).
        combined_score: Final weighted score (-1 to 1).
        finbert_score: Raw FinBERT-derived score.
        keyword_score: Keyword-based sentiment score.
        finbert_weight_used: Weight applied to FinBERT score.
        keyword_weight_used: Weight applied to keyword score.
        translation_confidence: Translation quality factor (1.0 for native English).
    """

    sentiment: Literal["positive", "negative", "neutral"] = Field(
        description="FinBERT classification"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="FinBERT confidence (0-1)")
    tone: Literal["hawkish", "dovish", "neutral"] = Field(
        description="Derived monetary policy tone"
    )
    combined_score: float = Field(ge=-1.0, le=1.0, description="Final weighted score")
    finbert_score: float = Field(description="Raw FinBERT-derived score")
    keyword_score: float = Field(description="Keyword-based sentiment score")
    finbert_weight_used: float = Field(description="Weight applied to FinBERT")
    keyword_weight_used: float = Field(description="Weight applied to keywords")
    translation_confidence: float = Field(
        ge=0.0, le=1.0, description="Translation quality factor"
    )

    model_config = ConfigDict(frozen=True)

    @classmethod
    def neutral_fallback(cls, reason: str = "analysis_failed") -> SentimentResult:
        """Create a neutral fallback result when analysis fails.

        Args:
            reason: Reason for fallback (logged but not stored).

        Returns:
            Neutral SentimentResult with zero scores.
        """
        logger.warning("Sentiment analysis fallback: %s", reason)
        return cls(
            sentiment="neutral",
            confidence=0.0,
            tone="neutral",
            combined_score=0.0,
            finbert_score=0.0,
            keyword_score=0.0,
            finbert_weight_used=0.0,
            keyword_weight_used=1.0,
            translation_confidence=1.0,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "tone": self.tone,
            "combined_score": self.combined_score,
            "finbert_score": self.finbert_score,
            "keyword_score": self.keyword_score,
            "finbert_weight_used": self.finbert_weight_used,
            "keyword_weight_used": self.keyword_weight_used,
            "translation_confidence": self.translation_confidence,
        }


@dataclass
class FinBERTOutput:
    """Internal result from FinBERT model inference.

    Attributes:
        label: Classification label (positive, negative, neutral).
        score: Confidence score for the label (0-1).
        raw_score: Mapped score for combination (-0.3 to 0.3).
    """

    label: str
    score: float
    raw_score: float


# =============================================================================
# Sentiment Analyzer
# =============================================================================


class SentimentAnalyzer:
    """Hybrid sentiment analyzer for central bank communications.

    Combines FinBERT model inference with keyword-based scoring for
    accurate hawkish/dovish classification of CB statements.

    Uses dynamic weighting based on translation confidence:
    - Native English: 70% FinBERT + 30% keywords
    - Translated text: Lower FinBERT weight (reduced trust in English-trained model)

    Example:
        >>> analyzer = SentimentAnalyzer()
        >>> result = analyzer.analyze("The Fed raised rates by 25 basis points")
        >>> print(f"Tone: {result.tone}, Score: {result.combined_score:.2f}")
        Tone: hawkish, Score: 0.65

        >>> # With translated text (lower confidence)
        >>> result = analyzer.analyze(translated_text, translation_confidence=0.8)
        >>> print(f"FinBERT weight: {result.finbert_weight_used:.2f}")
        FinBERT weight: 0.56
    """

    def __init__(
        self,
        device: str | None = None,
        max_length: int = MAX_LENGTH,
    ) -> None:
        """Initialize sentiment analyzer.

        Args:
            device: Device to use ('cpu', 'cuda', or None for auto-detect).
            max_length: Maximum input token length. Default 512.
        """
        import torch

        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.max_length = max_length

        # Lazy-loaded model (None until first use)
        self._model: Any = None
        self._tokenizer: Any = None

        # Pre-compile keyword patterns for efficient matching
        self._hawkish_patterns = self._compile_patterns(HAWKISH_KEYWORDS)
        self._dovish_patterns = self._compile_patterns(DOVISH_KEYWORDS)

        logger.info(
            "SentimentAnalyzer initialized (device=%s, max_length=%d)",
            self.device,
            self.max_length,
        )

    def _compile_patterns(
        self, keywords: dict[str, float]
    ) -> list[tuple[re.Pattern[str], float]]:
        """Compile keyword dictionary into regex patterns.

        Args:
            keywords: Dictionary of keywords to weights.

        Returns:
            List of (compiled pattern, weight) tuples.
        """
        patterns = []
        for keyword, weight in keywords.items():
            # Word boundary matching, case-insensitive
            pattern = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
            patterns.append((pattern, weight))
        return patterns

    def _load_model(self) -> tuple[Any, Any]:
        """Load FinBERT model and tokenizer.

        Returns:
            Tuple of (model, tokenizer).

        Raises:
            RuntimeError: If model loading fails.
        """
        if self._model is not None:
            return self._model, self._tokenizer

        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info("Loading FinBERT model: %s", SENTIMENT_MODEL)

        try:
            tokenizer: Any = AutoTokenizer.from_pretrained(SENTIMENT_MODEL)
            model: Any = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL)
            model = model.to(self.device)
            model.eval()

            self._model = model
            self._tokenizer = tokenizer

            logger.info("FinBERT model loaded: %s", SENTIMENT_MODEL)
            return model, tokenizer

        except Exception as e:
            logger.error("Failed to load FinBERT model: %s", e)
            raise RuntimeError(f"FinBERT model loading failed: {e}") from e

    def _finbert_score(self, text: str) -> FinBERTOutput:
        """Get sentiment score from FinBERT model.

        Args:
            text: Text to analyze.

        Returns:
            FinBERTOutput with label, score, and raw_score.

        Raises:
            RuntimeError: If model inference fails.
        """
        import torch

        model, tokenizer = self._load_model()

        # Tokenize with truncation
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding=True,
        ).to(self.device)

        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=-1)

            # Get predicted class and confidence
            predicted_class_idx = int(torch.argmax(probabilities, dim=-1).item())
            confidence = float(probabilities[0, predicted_class_idx].item())

        # Map class index to label
        # FinBERT labels: 0=positive, 1=negative, 2=neutral
        label_map = {0: "positive", 1: "negative", 2: "neutral"}
        label = label_map.get(predicted_class_idx, "neutral")

        # Get raw score for combination
        raw_score = FINBERT_LABEL_TO_SCORE.get(label, 0.0)

        return FinBERTOutput(
            label=label,
            score=confidence,
            raw_score=raw_score,
        )

    def _keyword_score(self, text: str) -> float:
        """Calculate keyword-based sentiment score.

        Scans text for hawkish/dovish keywords and computes weighted average.

        Args:
            text: Text to analyze.

        Returns:
            Sentiment score from -1.0 (dovish) to 1.0 (hawkish).
        """
        total_weight = 0.0
        match_count = 0

        # Check hawkish patterns
        for pattern, weight in self._hawkish_patterns:
            matches = pattern.findall(text)
            if matches:
                total_weight += weight * len(matches)
                match_count += len(matches)

        # Check dovish patterns
        for pattern, weight in self._dovish_patterns:
            matches = pattern.findall(text)
            if matches:
                total_weight += weight * len(matches)  # weight is already negative
                match_count += len(matches)

        if match_count == 0:
            return 0.0

        # Average score, clamped to [-1, 1]
        avg_score = total_weight / match_count
        return max(-1.0, min(1.0, avg_score))

    def _combine_scores(
        self,
        finbert_output: FinBERTOutput,
        keyword_score: float,
        translation_confidence: float,
    ) -> SentimentResult:
        """Combine FinBERT and keyword scores with dynamic weighting.

        For translated text (confidence < 1.0), we:
        1. Reduce trust in FinBERT (trained on English)
        2. Increase weight of keywords (language-agnostic signals)

        Args:
            finbert_output: Output from FinBERT model.
            keyword_score: Score from keyword matching.
            translation_confidence: Translation quality (1.0 for native English).

        Returns:
            Combined SentimentResult.
        """
        # Dynamic weight: more keywords for lower translation confidence
        # Native English (1.0): 70/30 split
        # Chinese (0.8): 56/44 split
        finbert_weight = DEFAULT_FINBERT_WEIGHT * translation_confidence
        keyword_weight = 1.0 - finbert_weight

        # Combine scores
        combined = (finbert_weight * finbert_output.raw_score) + (
            keyword_weight * keyword_score
        )

        # Clamp to [-1, 1]
        combined = max(-1.0, min(1.0, combined))

        # Determine tone based on thresholds
        if combined > HAWKISH_THRESHOLD:
            tone: Literal["hawkish", "dovish", "neutral"] = "hawkish"
        elif combined < DOVISH_THRESHOLD:
            tone = "dovish"
        else:
            tone = "neutral"

        return SentimentResult(
            sentiment=finbert_output.label,  # type: ignore[arg-type]
            confidence=finbert_output.score,
            tone=tone,
            combined_score=combined,
            finbert_score=finbert_output.raw_score,
            keyword_score=keyword_score,
            finbert_weight_used=finbert_weight,
            keyword_weight_used=keyword_weight,
            translation_confidence=translation_confidence,
        )

    def analyze(
        self,
        text: str,
        translation_confidence: float = 1.0,
    ) -> SentimentResult:
        """Analyze text for sentiment and monetary policy tone.

        Uses FinBERT for base sentiment and augments with keyword detection.
        Gracefully degrades to keyword-only or neutral on failures.

        Args:
            text: Text to analyze.
            translation_confidence: Translation quality (1.0 for native English).
                From TranslationResult.confidence for translated text.

        Returns:
            SentimentResult with tone and scores.
        """
        if not text or not text.strip():
            return SentimentResult.neutral_fallback("empty_text")

        # Validate translation confidence
        translation_confidence = max(0.0, min(1.0, translation_confidence))

        # Try FinBERT first
        finbert_output: FinBERTOutput | None = None
        try:
            finbert_output = self._finbert_score(text)
        except Exception as e:
            logger.warning("FinBERT failed: %s, falling back to keyword-only", e)

        # Calculate keyword score
        try:
            keyword_score = self._keyword_score(text)
        except Exception as e:
            logger.warning("Keyword scoring failed: %s, returning neutral", e)
            return SentimentResult.neutral_fallback("keyword_scoring_failed")

        # If FinBERT failed, use keyword-only
        if finbert_output is None:
            # Determine tone from keyword score
            if keyword_score > HAWKISH_THRESHOLD:
                tone: Literal["hawkish", "dovish", "neutral"] = "hawkish"
            elif keyword_score < DOVISH_THRESHOLD:
                tone = "dovish"
            else:
                tone = "neutral"

            return SentimentResult(
                sentiment="neutral",  # No FinBERT classification
                confidence=0.0,
                tone=tone,
                combined_score=keyword_score,
                finbert_score=0.0,
                keyword_score=keyword_score,
                finbert_weight_used=0.0,
                keyword_weight_used=1.0,
                translation_confidence=translation_confidence,
            )

        # Combine scores with dynamic weighting
        return self._combine_scores(finbert_output, keyword_score, translation_confidence)

    def analyze_batch(
        self,
        texts: list[str],
        translation_confidences: list[float] | None = None,
    ) -> list[SentimentResult]:
        """Analyze multiple texts for sentiment.

        Args:
            texts: List of texts to analyze.
            translation_confidences: Optional list of translation confidences.
                If not provided, assumes all texts are native English (1.0).

        Returns:
            List of SentimentResult objects.
        """
        if not texts:
            return []

        # Default to 1.0 confidence if not provided
        if translation_confidences is None:
            translation_confidences = [1.0] * len(texts)

        if len(translation_confidences) != len(texts):
            raise ValueError(
                f"Length mismatch: {len(texts)} texts vs "
                f"{len(translation_confidences)} confidences"
            )

        results = []
        for text, confidence in zip(texts, translation_confidences, strict=True):
            result = self.analyze(text, translation_confidence=confidence)
            results.append(result)

        return results

    def unload_model(self) -> None:
        """Unload FinBERT model from memory.

        Useful for freeing GPU memory when sentiment analysis is not needed.
        """
        import gc

        import torch

        if self._model is not None:
            del self._model
            del self._tokenizer
            self._model = None
            self._tokenizer = None

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info("FinBERT model unloaded")

    def is_model_loaded(self) -> bool:
        """Check if FinBERT model is currently loaded.

        Returns:
            True if model is loaded.
        """
        return self._model is not None
