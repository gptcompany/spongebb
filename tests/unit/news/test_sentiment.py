"""Unit tests for CB Speech Sentiment Analyzer.

Tests cover:
- SentimentResult model validation
- SentimentAnalyzer initialization
- Keyword-based scoring
- FinBERT-based scoring (mocked)
- Dynamic weighting based on translation confidence
- Batch processing
- Fallback behavior on errors

Uses mock models to avoid downloading HuggingFace weights in CI.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from liquidity.news.lexicons import (
    DOVISH_KEYWORDS,
    HAWKISH_KEYWORDS,
    classify_keyword,
    get_all_keywords,
    get_keyword_weight,
)
from liquidity.news.sentiment import (
    DEFAULT_FINBERT_WEIGHT,
    DEFAULT_KEYWORD_WEIGHT,
    DOVISH_THRESHOLD,
    FINBERT_LABEL_TO_SCORE,
    HAWKISH_THRESHOLD,
    MAX_LENGTH,
    SENTIMENT_MODEL,
    FinBERTOutput,
    SentimentAnalyzer,
    SentimentResult,
)

# ============================================================================
# Sample CB Statements for Testing
# ============================================================================

HAWKISH_STATEMENTS = [
    "The Fed announced a rate increase of 25 basis points amid inflation concerns.",
    "We are committed to tightening monetary policy to achieve price stability.",
    "The economy is overheating and we must raise rates to normalize policy.",
    "Quantitative tightening will continue as planned with balance sheet reduction.",
]

DOVISH_STATEMENTS = [
    "The central bank cut rates to support growth amid downside risks.",
    "We remain accommodative and patient as we monitor economic conditions.",
    "Rate cuts are necessary to address subdued inflation and unemployment concerns.",
    "The Fed announced quantitative easing and increased asset purchases.",
]

NEUTRAL_STATEMENTS = [
    "The committee met to discuss the current economic outlook.",
    "Economic data will continue to inform our policy decisions.",
    "The central bank issued its regular quarterly statement.",
]


# ============================================================================
# Lexicon Tests
# ============================================================================


class TestLexicons:
    """Tests for keyword lexicons."""

    @pytest.mark.unit
    def test_hawkish_keywords_not_empty(self) -> None:
        """Test that hawkish keywords dictionary is not empty."""
        assert len(HAWKISH_KEYWORDS) > 0

    @pytest.mark.unit
    def test_dovish_keywords_not_empty(self) -> None:
        """Test that dovish keywords dictionary is not empty."""
        assert len(DOVISH_KEYWORDS) > 0

    @pytest.mark.unit
    def test_hawkish_keywords_positive_weights(self) -> None:
        """Test that all hawkish keywords have positive weights."""
        for keyword, weight in HAWKISH_KEYWORDS.items():
            assert weight > 0, f"Hawkish keyword '{keyword}' has non-positive weight"
            assert weight <= 1.0, f"Hawkish keyword '{keyword}' weight exceeds 1.0"

    @pytest.mark.unit
    def test_dovish_keywords_negative_weights(self) -> None:
        """Test that all dovish keywords have negative weights."""
        for keyword, weight in DOVISH_KEYWORDS.items():
            assert weight < 0, f"Dovish keyword '{keyword}' has non-negative weight"
            assert weight >= -1.0, f"Dovish keyword '{keyword}' weight below -1.0"

    @pytest.mark.unit
    def test_get_all_keywords(self) -> None:
        """Test get_all_keywords returns combined dictionary."""
        all_kw = get_all_keywords()
        assert "rate increase" in all_kw
        assert "rate cut" in all_kw
        assert all_kw["rate increase"] == 1.0
        assert all_kw["rate cut"] == -1.0

    @pytest.mark.unit
    def test_get_keyword_weight_hawkish(self) -> None:
        """Test getting weight for hawkish keyword."""
        assert get_keyword_weight("rate increase") == 1.0
        assert get_keyword_weight("tightening") == 1.0
        assert get_keyword_weight("Rate Increase") == 1.0  # Case insensitive

    @pytest.mark.unit
    def test_get_keyword_weight_dovish(self) -> None:
        """Test getting weight for dovish keyword."""
        assert get_keyword_weight("rate cut") == -1.0
        assert get_keyword_weight("easing") == -1.0

    @pytest.mark.unit
    def test_get_keyword_weight_not_found(self) -> None:
        """Test getting weight for unknown keyword."""
        assert get_keyword_weight("unknown keyword") is None

    @pytest.mark.unit
    def test_classify_keyword(self) -> None:
        """Test keyword classification."""
        assert classify_keyword("rate increase") == "hawkish"
        assert classify_keyword("rate cut") == "dovish"
        assert classify_keyword("unknown") is None


# ============================================================================
# SentimentResult Tests
# ============================================================================


class TestSentimentResult:
    """Tests for SentimentResult model."""

    @pytest.mark.unit
    def test_result_creation_valid(self) -> None:
        """Test basic SentimentResult creation."""
        result = SentimentResult(
            sentiment="positive",
            confidence=0.85,
            tone="hawkish",
            combined_score=0.45,
            finbert_score=0.3,
            keyword_score=0.6,
            finbert_weight_used=0.7,
            keyword_weight_used=0.3,
            translation_confidence=1.0,
        )

        assert result.sentiment == "positive"
        assert result.confidence == 0.85
        assert result.tone == "hawkish"
        assert result.combined_score == 0.45
        assert result.finbert_score == 0.3
        assert result.keyword_score == 0.6
        assert result.finbert_weight_used == 0.7
        assert result.keyword_weight_used == 0.3
        assert result.translation_confidence == 1.0

    @pytest.mark.unit
    def test_result_neutral_fallback(self) -> None:
        """Test neutral fallback creation."""
        result = SentimentResult.neutral_fallback("test_reason")

        assert result.sentiment == "neutral"
        assert result.confidence == 0.0
        assert result.tone == "neutral"
        assert result.combined_score == 0.0
        assert result.finbert_score == 0.0
        assert result.keyword_score == 0.0

    @pytest.mark.unit
    def test_result_confidence_bounds(self) -> None:
        """Test confidence validation (0-1)."""
        # Valid at boundaries
        result_zero = SentimentResult(
            sentiment="neutral",
            confidence=0.0,
            tone="neutral",
            combined_score=0.0,
            finbert_score=0.0,
            keyword_score=0.0,
            finbert_weight_used=0.5,
            keyword_weight_used=0.5,
            translation_confidence=1.0,
        )
        assert result_zero.confidence == 0.0

        result_one = SentimentResult(
            sentiment="positive",
            confidence=1.0,
            tone="hawkish",
            combined_score=0.5,
            finbert_score=0.3,
            keyword_score=0.7,
            finbert_weight_used=0.7,
            keyword_weight_used=0.3,
            translation_confidence=1.0,
        )
        assert result_one.confidence == 1.0

    @pytest.mark.unit
    def test_result_invalid_confidence_high(self) -> None:
        """Test that confidence > 1 raises validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SentimentResult(
                sentiment="positive",
                confidence=1.5,  # Invalid
                tone="hawkish",
                combined_score=0.5,
                finbert_score=0.3,
                keyword_score=0.7,
                finbert_weight_used=0.7,
                keyword_weight_used=0.3,
                translation_confidence=1.0,
            )

    @pytest.mark.unit
    def test_result_to_dict(self) -> None:
        """Test SentimentResult serialization."""
        result = SentimentResult(
            sentiment="negative",
            confidence=0.75,
            tone="dovish",
            combined_score=-0.35,
            finbert_score=-0.3,
            keyword_score=-0.5,
            finbert_weight_used=0.6,
            keyword_weight_used=0.4,
            translation_confidence=0.85,
        )

        d = result.to_dict()

        assert isinstance(d, dict)
        assert d["sentiment"] == "negative"
        assert d["tone"] == "dovish"
        assert d["combined_score"] == -0.35
        assert d["translation_confidence"] == 0.85

    @pytest.mark.unit
    def test_result_frozen(self) -> None:
        """Test that SentimentResult is immutable."""
        result = SentimentResult(
            sentiment="neutral",
            confidence=0.5,
            tone="neutral",
            combined_score=0.0,
            finbert_score=0.0,
            keyword_score=0.0,
            finbert_weight_used=0.7,
            keyword_weight_used=0.3,
            translation_confidence=1.0,
        )

        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            result.sentiment = "positive"  # type: ignore[misc]


# ============================================================================
# SentimentAnalyzer Initialization Tests
# ============================================================================


class TestSentimentAnalyzerInit:
    """Tests for SentimentAnalyzer initialization."""

    @pytest.mark.unit
    def test_init_default_params(self) -> None:
        """Test analyzer initialization with defaults."""
        with patch("torch.cuda.is_available", return_value=False):
            analyzer = SentimentAnalyzer()

        assert analyzer.device == "cpu"
        assert analyzer.max_length == MAX_LENGTH
        assert analyzer._model is None  # Lazy loading

    @pytest.mark.unit
    def test_init_custom_device_cpu(self) -> None:
        """Test analyzer initialization with explicit CPU."""
        analyzer = SentimentAnalyzer(device="cpu")
        assert analyzer.device == "cpu"

    @pytest.mark.unit
    def test_init_custom_max_length(self) -> None:
        """Test analyzer initialization with custom max length."""
        analyzer = SentimentAnalyzer(device="cpu", max_length=256)
        assert analyzer.max_length == 256

    @pytest.mark.unit
    @patch("torch.cuda.is_available", return_value=True)
    def test_init_auto_detect_cuda(self, mock_cuda: MagicMock) -> None:
        """Test auto-detection of CUDA device."""
        analyzer = SentimentAnalyzer()
        assert analyzer.device == "cuda"

    @pytest.mark.unit
    def test_pattern_compilation(self) -> None:
        """Test that keyword patterns are compiled on init."""
        analyzer = SentimentAnalyzer(device="cpu")

        assert len(analyzer._hawkish_patterns) == len(HAWKISH_KEYWORDS)
        assert len(analyzer._dovish_patterns) == len(DOVISH_KEYWORDS)


# ============================================================================
# Keyword Scoring Tests
# ============================================================================


class TestKeywordScoring:
    """Tests for keyword-based sentiment scoring."""

    @pytest.fixture
    def analyzer(self) -> SentimentAnalyzer:
        """Create analyzer instance."""
        return SentimentAnalyzer(device="cpu")

    @pytest.mark.unit
    def test_keyword_score_hawkish(self, analyzer: SentimentAnalyzer) -> None:
        """Test keyword scoring for hawkish text."""
        text = "The Fed announced a rate increase due to inflation concerns."
        score = analyzer._keyword_score(text)
        assert score > 0, "Hawkish text should have positive score"

    @pytest.mark.unit
    def test_keyword_score_dovish(self, analyzer: SentimentAnalyzer) -> None:
        """Test keyword scoring for dovish text."""
        text = "The central bank cut rates to support growth amid downside risks."
        score = analyzer._keyword_score(text)
        assert score < 0, "Dovish text should have negative score"

    @pytest.mark.unit
    def test_keyword_score_neutral(self, analyzer: SentimentAnalyzer) -> None:
        """Test keyword scoring for neutral text."""
        text = "The committee met to discuss the agenda."
        score = analyzer._keyword_score(text)
        assert score == 0.0, "Neutral text should have zero score"

    @pytest.mark.unit
    def test_keyword_score_empty_text(self, analyzer: SentimentAnalyzer) -> None:
        """Test keyword scoring for empty text."""
        assert analyzer._keyword_score("") == 0.0
        assert analyzer._keyword_score("   ") == 0.0

    @pytest.mark.unit
    def test_keyword_score_case_insensitive(self, analyzer: SentimentAnalyzer) -> None:
        """Test that keyword matching is case-insensitive."""
        text1 = "RATE INCREASE"
        text2 = "rate increase"
        text3 = "Rate Increase"

        assert analyzer._keyword_score(text1) == analyzer._keyword_score(text2)
        assert analyzer._keyword_score(text2) == analyzer._keyword_score(text3)

    @pytest.mark.unit
    def test_keyword_score_multiple_matches(self, analyzer: SentimentAnalyzer) -> None:
        """Test scoring with multiple keyword matches."""
        text = "Rate increase and tightening due to inflation concerns and overheating."
        score = analyzer._keyword_score(text)
        assert score > 0.5, "Multiple hawkish keywords should yield high score"

    @pytest.mark.unit
    def test_keyword_score_mixed_signals(self, analyzer: SentimentAnalyzer) -> None:
        """Test scoring with mixed hawkish/dovish signals."""
        text = "While there are inflation concerns, we remain patient."
        score = analyzer._keyword_score(text)
        # Should be somewhere between -1 and 1, not extreme
        assert -0.5 < score < 0.5

    @pytest.mark.unit
    def test_keyword_score_bounded(self, analyzer: SentimentAnalyzer) -> None:
        """Test that scores are bounded to [-1, 1]."""
        # Very hawkish text
        hawkish_text = " ".join(["rate increase tightening"] * 10)
        assert analyzer._keyword_score(hawkish_text) <= 1.0

        # Very dovish text
        dovish_text = " ".join(["rate cut easing"] * 10)
        assert analyzer._keyword_score(dovish_text) >= -1.0


# ============================================================================
# FinBERT Scoring Tests (Mocked)
# ============================================================================


class TestFinBERTScoring:
    """Tests for FinBERT-based scoring with mocked model."""

    @pytest.fixture
    def analyzer(self) -> SentimentAnalyzer:
        """Create analyzer instance."""
        return SentimentAnalyzer(device="cpu")

    @pytest.fixture
    def mock_finbert_model(self) -> MagicMock:
        """Create mock FinBERT model."""
        import torch

        model = MagicMock()
        model.to.return_value = model
        model.eval.return_value = None

        # Mock output with logits
        mock_output = MagicMock()
        mock_output.logits = torch.tensor([[2.0, 0.5, 0.3]])  # Positive class highest
        model.return_value = mock_output

        return model

    @pytest.fixture
    def mock_finbert_tokenizer(self) -> MagicMock:
        """Create mock FinBERT tokenizer."""
        tokenizer = MagicMock()

        mock_encoding = MagicMock()
        mock_encoding.to.return_value = mock_encoding
        tokenizer.return_value = mock_encoding

        return tokenizer

    @pytest.mark.unit
    def test_finbert_score_positive(
        self,
        analyzer: SentimentAnalyzer,
        mock_finbert_model: MagicMock,
        mock_finbert_tokenizer: MagicMock,
    ) -> None:
        """Test FinBERT scoring returns positive sentiment."""
        with patch(
            "liquidity.news.sentiment.SentimentAnalyzer._load_model",
            return_value=(mock_finbert_model, mock_finbert_tokenizer),
        ):
            output = analyzer._finbert_score("Test text")

        assert output.label == "positive"
        assert output.raw_score == FINBERT_LABEL_TO_SCORE["positive"]
        assert 0 < output.score <= 1.0

    @pytest.mark.unit
    def test_finbert_score_negative(
        self,
        analyzer: SentimentAnalyzer,
        mock_finbert_tokenizer: MagicMock,
    ) -> None:
        """Test FinBERT scoring returns negative sentiment."""
        import torch

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.eval.return_value = None

        mock_output = MagicMock()
        mock_output.logits = torch.tensor([[0.3, 2.0, 0.5]])  # Negative class highest
        mock_model.return_value = mock_output

        with patch(
            "liquidity.news.sentiment.SentimentAnalyzer._load_model",
            return_value=(mock_model, mock_finbert_tokenizer),
        ):
            output = analyzer._finbert_score("Test text")

        assert output.label == "negative"
        assert output.raw_score == FINBERT_LABEL_TO_SCORE["negative"]

    @pytest.mark.unit
    def test_finbert_score_neutral(
        self,
        analyzer: SentimentAnalyzer,
        mock_finbert_tokenizer: MagicMock,
    ) -> None:
        """Test FinBERT scoring returns neutral sentiment."""
        import torch

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.eval.return_value = None

        mock_output = MagicMock()
        mock_output.logits = torch.tensor([[0.3, 0.5, 2.0]])  # Neutral class highest
        mock_model.return_value = mock_output

        with patch(
            "liquidity.news.sentiment.SentimentAnalyzer._load_model",
            return_value=(mock_model, mock_finbert_tokenizer),
        ):
            output = analyzer._finbert_score("Test text")

        assert output.label == "neutral"
        assert output.raw_score == FINBERT_LABEL_TO_SCORE["neutral"]


# ============================================================================
# Score Combination Tests
# ============================================================================


class TestScoreCombination:
    """Tests for combining FinBERT and keyword scores."""

    @pytest.fixture
    def analyzer(self) -> SentimentAnalyzer:
        """Create analyzer instance."""
        return SentimentAnalyzer(device="cpu")

    @pytest.mark.unit
    def test_combine_scores_native_english(self, analyzer: SentimentAnalyzer) -> None:
        """Test score combination for native English text."""
        finbert_output = FinBERTOutput(label="positive", score=0.9, raw_score=0.3)
        keyword_score = 0.5

        result = analyzer._combine_scores(finbert_output, keyword_score, 1.0)

        # Native English: 70% FinBERT + 30% keywords
        expected = (0.7 * 0.3) + (0.3 * 0.5)
        assert abs(result.combined_score - expected) < 0.001
        assert abs(result.finbert_weight_used - DEFAULT_FINBERT_WEIGHT) < 0.001
        assert abs(result.keyword_weight_used - DEFAULT_KEYWORD_WEIGHT) < 0.001

    @pytest.mark.unit
    def test_combine_scores_translated_text(self, analyzer: SentimentAnalyzer) -> None:
        """Test score combination for translated text (lower confidence)."""
        finbert_output = FinBERTOutput(label="positive", score=0.9, raw_score=0.3)
        keyword_score = 0.5
        translation_confidence = 0.8  # e.g., Chinese translation

        result = analyzer._combine_scores(
            finbert_output, keyword_score, translation_confidence
        )

        # Translated: 56% FinBERT + 44% keywords (0.7 * 0.8 = 0.56)
        expected_finbert_weight = 0.7 * 0.8  # 0.56
        expected_keyword_weight = 1.0 - expected_finbert_weight  # 0.44

        assert abs(result.finbert_weight_used - expected_finbert_weight) < 0.001
        assert abs(result.keyword_weight_used - expected_keyword_weight) < 0.001

    @pytest.mark.unit
    def test_combine_scores_tone_hawkish(self, analyzer: SentimentAnalyzer) -> None:
        """Test that combined score above threshold yields hawkish tone."""
        finbert_output = FinBERTOutput(label="positive", score=0.9, raw_score=0.3)
        keyword_score = 0.8

        result = analyzer._combine_scores(finbert_output, keyword_score, 1.0)

        assert result.tone == "hawkish"
        assert result.combined_score > HAWKISH_THRESHOLD

    @pytest.mark.unit
    def test_combine_scores_tone_dovish(self, analyzer: SentimentAnalyzer) -> None:
        """Test that combined score below threshold yields dovish tone."""
        finbert_output = FinBERTOutput(label="negative", score=0.9, raw_score=-0.3)
        keyword_score = -0.8

        result = analyzer._combine_scores(finbert_output, keyword_score, 1.0)

        assert result.tone == "dovish"
        assert result.combined_score < DOVISH_THRESHOLD

    @pytest.mark.unit
    def test_combine_scores_tone_neutral(self, analyzer: SentimentAnalyzer) -> None:
        """Test that balanced scores yield neutral tone."""
        finbert_output = FinBERTOutput(label="neutral", score=0.9, raw_score=0.0)
        keyword_score = 0.0

        result = analyzer._combine_scores(finbert_output, keyword_score, 1.0)

        assert result.tone == "neutral"
        assert DOVISH_THRESHOLD <= result.combined_score <= HAWKISH_THRESHOLD


# ============================================================================
# Full Analysis Tests (Mocked FinBERT)
# ============================================================================


class TestFullAnalysis:
    """Tests for complete analyze() method with mocked FinBERT."""

    @pytest.fixture
    def analyzer(self) -> SentimentAnalyzer:
        """Create analyzer instance."""
        return SentimentAnalyzer(device="cpu")

    @pytest.fixture
    def mock_finbert_positive(self) -> tuple[MagicMock, MagicMock]:
        """Create mocks returning positive sentiment."""
        import torch

        model = MagicMock()
        model.to.return_value = model
        model.eval.return_value = None
        mock_output = MagicMock()
        mock_output.logits = torch.tensor([[2.0, 0.5, 0.3]])
        model.return_value = mock_output

        tokenizer = MagicMock()
        mock_encoding = MagicMock()
        mock_encoding.to.return_value = mock_encoding
        tokenizer.return_value = mock_encoding

        return model, tokenizer

    @pytest.mark.unit
    def test_analyze_hawkish_statement(
        self,
        analyzer: SentimentAnalyzer,
        mock_finbert_positive: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test analyzing a hawkish CB statement."""
        model, tokenizer = mock_finbert_positive

        with patch(
            "liquidity.news.sentiment.SentimentAnalyzer._load_model",
            return_value=(model, tokenizer),
        ):
            result = analyzer.analyze(HAWKISH_STATEMENTS[0])

        assert result.tone == "hawkish"
        assert result.combined_score > 0

    @pytest.mark.unit
    def test_analyze_with_translation_confidence(
        self,
        analyzer: SentimentAnalyzer,
        mock_finbert_positive: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test analyzing translated text with reduced confidence."""
        model, tokenizer = mock_finbert_positive

        with patch(
            "liquidity.news.sentiment.SentimentAnalyzer._load_model",
            return_value=(model, tokenizer),
        ):
            result = analyzer.analyze(
                "The central bank announced tightening.",
                translation_confidence=0.8,
            )

        # Should use reduced FinBERT weight
        assert result.finbert_weight_used < DEFAULT_FINBERT_WEIGHT
        assert result.keyword_weight_used > DEFAULT_KEYWORD_WEIGHT
        assert result.translation_confidence == 0.8

    @pytest.mark.unit
    def test_analyze_empty_text(self, analyzer: SentimentAnalyzer) -> None:
        """Test analyzing empty text returns neutral fallback."""
        result = analyzer.analyze("")

        assert result.tone == "neutral"
        assert result.confidence == 0.0

    @pytest.mark.unit
    def test_analyze_whitespace_only(self, analyzer: SentimentAnalyzer) -> None:
        """Test analyzing whitespace-only text."""
        result = analyzer.analyze("   \n\t   ")

        assert result.tone == "neutral"

    @pytest.mark.unit
    def test_analyze_finbert_failure_fallback(
        self, analyzer: SentimentAnalyzer
    ) -> None:
        """Test fallback to keyword-only when FinBERT fails."""
        with patch(
            "liquidity.news.sentiment.SentimentAnalyzer._load_model",
            side_effect=RuntimeError("Model not found"),
        ):
            result = analyzer.analyze(HAWKISH_STATEMENTS[0])

        # Should still work with keywords
        assert result.finbert_weight_used == 0.0
        assert result.keyword_weight_used == 1.0
        assert result.tone == "hawkish"  # Keywords should detect hawkish

    @pytest.mark.unit
    def test_analyze_confidence_clamped(
        self,
        analyzer: SentimentAnalyzer,
        mock_finbert_positive: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test that invalid translation confidence is clamped."""
        model, tokenizer = mock_finbert_positive

        with patch(
            "liquidity.news.sentiment.SentimentAnalyzer._load_model",
            return_value=(model, tokenizer),
        ):
            result_high = analyzer.analyze("test", translation_confidence=1.5)
            result_low = analyzer.analyze("test", translation_confidence=-0.5)

        assert result_high.translation_confidence == 1.0
        assert result_low.translation_confidence == 0.0


# ============================================================================
# Batch Analysis Tests
# ============================================================================


class TestBatchAnalysis:
    """Tests for batch sentiment analysis."""

    @pytest.fixture
    def analyzer(self) -> SentimentAnalyzer:
        """Create analyzer instance."""
        return SentimentAnalyzer(device="cpu")

    @pytest.fixture
    def mock_finbert(self) -> tuple[MagicMock, MagicMock]:
        """Create generic mock for FinBERT."""
        import torch

        model = MagicMock()
        model.to.return_value = model
        model.eval.return_value = None
        mock_output = MagicMock()
        mock_output.logits = torch.tensor([[1.0, 1.0, 1.0]])  # Neutral-ish
        model.return_value = mock_output

        tokenizer = MagicMock()
        mock_encoding = MagicMock()
        mock_encoding.to.return_value = mock_encoding
        tokenizer.return_value = mock_encoding

        return model, tokenizer

    @pytest.mark.unit
    def test_analyze_batch_empty(self, analyzer: SentimentAnalyzer) -> None:
        """Test batch with empty list."""
        results = analyzer.analyze_batch([])
        assert results == []

    @pytest.mark.unit
    def test_analyze_batch_multiple(
        self,
        analyzer: SentimentAnalyzer,
        mock_finbert: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test batch with multiple texts."""
        model, tokenizer = mock_finbert
        texts = ["Text 1", "Text 2", "Text 3"]

        with patch(
            "liquidity.news.sentiment.SentimentAnalyzer._load_model",
            return_value=(model, tokenizer),
        ):
            results = analyzer.analyze_batch(texts)

        assert len(results) == 3
        for result in results:
            assert isinstance(result, SentimentResult)

    @pytest.mark.unit
    def test_analyze_batch_with_confidences(
        self,
        analyzer: SentimentAnalyzer,
        mock_finbert: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test batch with varying translation confidences."""
        model, tokenizer = mock_finbert
        texts = ["Text 1", "Text 2", "Text 3"]
        confidences = [1.0, 0.8, 0.6]

        with patch(
            "liquidity.news.sentiment.SentimentAnalyzer._load_model",
            return_value=(model, tokenizer),
        ):
            results = analyzer.analyze_batch(texts, confidences)

        assert results[0].translation_confidence == 1.0
        assert results[1].translation_confidence == 0.8
        assert results[2].translation_confidence == 0.6

    @pytest.mark.unit
    def test_analyze_batch_confidence_mismatch(
        self, analyzer: SentimentAnalyzer
    ) -> None:
        """Test batch raises error on length mismatch."""
        texts = ["Text 1", "Text 2"]
        confidences = [1.0]  # Wrong length

        with pytest.raises(ValueError, match="Length mismatch"):
            analyzer.analyze_batch(texts, confidences)


# ============================================================================
# Model Management Tests
# ============================================================================


class TestModelManagement:
    """Tests for model loading and unloading."""

    @pytest.fixture
    def analyzer(self) -> SentimentAnalyzer:
        """Create analyzer instance."""
        return SentimentAnalyzer(device="cpu")

    @pytest.mark.unit
    def test_is_model_loaded_initially_false(
        self, analyzer: SentimentAnalyzer
    ) -> None:
        """Test model is not loaded initially (lazy loading)."""
        assert analyzer.is_model_loaded() is False

    @pytest.mark.unit
    def test_unload_model(self, analyzer: SentimentAnalyzer) -> None:
        """Test unloading model clears references."""
        # Simulate loaded model
        analyzer._model = MagicMock()
        analyzer._tokenizer = MagicMock()

        with patch("torch.cuda.is_available", return_value=False):
            analyzer.unload_model()

        assert analyzer._model is None
        assert analyzer._tokenizer is None
        assert analyzer.is_model_loaded() is False


# ============================================================================
# Constants Tests
# ============================================================================


class TestConstants:
    """Tests for module constants."""

    @pytest.mark.unit
    def test_sentiment_model_constant(self) -> None:
        """Test SENTIMENT_MODEL constant."""
        assert SENTIMENT_MODEL == "ProsusAI/finbert"

    @pytest.mark.unit
    def test_max_length_constant(self) -> None:
        """Test MAX_LENGTH constant."""
        assert MAX_LENGTH == 512

    @pytest.mark.unit
    def test_thresholds(self) -> None:
        """Test threshold constants."""
        assert HAWKISH_THRESHOLD == 0.2
        assert DOVISH_THRESHOLD == -0.2

    @pytest.mark.unit
    def test_default_weights(self) -> None:
        """Test default weight constants."""
        assert DEFAULT_FINBERT_WEIGHT == 0.7
        assert DEFAULT_KEYWORD_WEIGHT == 0.3
        assert DEFAULT_FINBERT_WEIGHT + DEFAULT_KEYWORD_WEIGHT == 1.0

    @pytest.mark.unit
    def test_finbert_label_scores(self) -> None:
        """Test FinBERT label to score mapping."""
        assert FINBERT_LABEL_TO_SCORE["positive"] == 0.3
        assert FINBERT_LABEL_TO_SCORE["negative"] == -0.3
        assert FINBERT_LABEL_TO_SCORE["neutral"] == 0.0


# ============================================================================
# Known CB Statement Tests
# ============================================================================


class TestKnownStatements:
    """Tests with known CB statements to validate classification."""

    @pytest.fixture
    def analyzer(self) -> SentimentAnalyzer:
        """Create analyzer instance."""
        return SentimentAnalyzer(device="cpu")

    @pytest.mark.unit
    def test_hawkish_statements_keyword_score(
        self, analyzer: SentimentAnalyzer
    ) -> None:
        """Test that hawkish statements have positive keyword scores."""
        for statement in HAWKISH_STATEMENTS:
            score = analyzer._keyword_score(statement)
            assert score > 0, f"Statement should be hawkish: {statement}"

    @pytest.mark.unit
    def test_dovish_statements_keyword_score(
        self, analyzer: SentimentAnalyzer
    ) -> None:
        """Test that dovish statements have negative keyword scores."""
        for statement in DOVISH_STATEMENTS:
            score = analyzer._keyword_score(statement)
            assert score < 0, f"Statement should be dovish: {statement}"

    @pytest.mark.unit
    def test_neutral_statements_keyword_score(
        self, analyzer: SentimentAnalyzer
    ) -> None:
        """Test that neutral statements have near-zero keyword scores."""
        for statement in NEUTRAL_STATEMENTS:
            score = analyzer._keyword_score(statement)
            assert abs(score) < 0.3, f"Statement should be neutral: {statement}"
