"""Unit tests for NLP Translation Pipeline.

Tests cover:
- TranslationResult dataclass validation
- TranslationPipeline initialization
- Language support and confidence decay
- Translation with mocked models
- Batch processing
- Error handling and fallback behavior

Uses mock models to avoid downloading HuggingFace weights in CI.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from liquidity.news.translation import (
    CONFIDENCE_DECAY,
    MAX_LENGTH,
    OPUS_MODELS,
    QWEN_MODEL,
    TranslationPipeline,
    TranslationResult,
)

# ============================================================================
# Sample Central Bank Texts for Testing
# ============================================================================

SAMPLE_TEXTS = {
    "zh": "中国人民银行决定下调存款准备金率0.5个百分点",  # PBoC RRR cut
    "ja": "日本銀行は金融政策決定会合を開催しました",  # BoJ policy meeting
    "de": "Die Bundesbank erhöht den Leitzins um 25 Basispunkte",  # Bundesbank rate hike
    "fr": "La BCE maintient les taux directeurs inchangés",  # ECB rates unchanged
    "en": "The Federal Reserve announced a rate cut of 25 basis points",
}


# ============================================================================
# TranslationResult Tests
# ============================================================================


class TestTranslationResult:
    """Tests for TranslationResult dataclass."""

    @pytest.mark.unit
    def test_result_creation_valid(self) -> None:
        """Test basic TranslationResult creation."""
        result = TranslationResult(
            text="Translated text",
            source_lang="de",
            model_used="Helsinki-NLP/opus-mt-de-en",
            confidence=0.95,
            is_truncated=False,
        )

        assert result.text == "Translated text"
        assert result.source_lang == "de"
        assert result.model_used == "Helsinki-NLP/opus-mt-de-en"
        assert result.confidence == 0.95
        assert result.is_truncated is False

    @pytest.mark.unit
    def test_result_confidence_zero(self) -> None:
        """Test result with zero confidence (valid edge case)."""
        result = TranslationResult(
            text="text",
            source_lang="zh",
            model_used="fallback",
            confidence=0.0,
            is_truncated=False,
        )
        assert result.confidence == 0.0

    @pytest.mark.unit
    def test_result_confidence_one(self) -> None:
        """Test result with confidence of 1.0 (English passthrough)."""
        result = TranslationResult(
            text="English text",
            source_lang="en",
            model_used="passthrough",
            confidence=1.0,
            is_truncated=False,
        )
        assert result.confidence == 1.0

    @pytest.mark.unit
    def test_result_invalid_confidence_high(self) -> None:
        """Test that confidence > 1 raises ValueError."""
        with pytest.raises(ValueError, match="confidence must be in"):
            TranslationResult(
                text="text",
                source_lang="de",
                model_used="test",
                confidence=1.5,
                is_truncated=False,
            )

    @pytest.mark.unit
    def test_result_invalid_confidence_negative(self) -> None:
        """Test that negative confidence raises ValueError."""
        with pytest.raises(ValueError, match="confidence must be in"):
            TranslationResult(
                text="text",
                source_lang="de",
                model_used="test",
                confidence=-0.1,
                is_truncated=False,
            )

    @pytest.mark.unit
    def test_result_to_dict(self) -> None:
        """Test TranslationResult serialization."""
        result = TranslationResult(
            text="Translated",
            source_lang="fr",
            model_used="Helsinki-NLP/opus-mt-fr-en",
            confidence=0.95,
            is_truncated=True,
        )

        d = result.to_dict()

        assert isinstance(d, dict)
        assert d["text"] == "Translated"
        assert d["source_lang"] == "fr"
        assert d["model_used"] == "Helsinki-NLP/opus-mt-fr-en"
        assert d["confidence"] == 0.95
        assert d["is_truncated"] is True

    @pytest.mark.unit
    def test_result_truncated_flag(self) -> None:
        """Test is_truncated flag."""
        result = TranslationResult(
            text="truncated text",
            source_lang="zh",
            model_used=QWEN_MODEL,
            confidence=0.80,
            is_truncated=True,
        )
        assert result.is_truncated is True


# ============================================================================
# TranslationPipeline Tests
# ============================================================================


class TestTranslationPipelineInit:
    """Tests for TranslationPipeline initialization."""

    @pytest.mark.unit
    def test_init_default_params(self) -> None:
        """Test pipeline initialization with defaults."""
        with patch("torch.cuda.is_available", return_value=False):
            pipeline = TranslationPipeline()

        assert pipeline.device == "cpu"
        assert pipeline.batch_size == 16
        assert pipeline.max_length == MAX_LENGTH

    @pytest.mark.unit
    def test_init_custom_device_cpu(self) -> None:
        """Test pipeline initialization with explicit CPU."""
        pipeline = TranslationPipeline(device="cpu")
        assert pipeline.device == "cpu"

    @pytest.mark.unit
    def test_init_custom_batch_size(self) -> None:
        """Test pipeline initialization with custom batch size."""
        pipeline = TranslationPipeline(device="cpu", batch_size=8)
        assert pipeline.batch_size == 8

    @pytest.mark.unit
    def test_init_custom_max_length(self) -> None:
        """Test pipeline initialization with custom max length."""
        pipeline = TranslationPipeline(device="cpu", max_length=256)
        assert pipeline.max_length == 256

    @pytest.mark.unit
    @patch("torch.cuda.is_available", return_value=True)
    def test_init_auto_detect_cuda(self, mock_cuda: MagicMock) -> None:
        """Test auto-detection of CUDA device."""
        pipeline = TranslationPipeline()
        assert pipeline.device == "cuda"


class TestTranslationPipelineLanguageSupport:
    """Tests for language support methods."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline instance for tests."""
        return TranslationPipeline(device="cpu")

    @pytest.mark.unit
    def test_get_supported_languages(self, pipeline: TranslationPipeline) -> None:
        """Test getting supported languages."""
        languages = pipeline.get_supported_languages()

        assert "zh" in languages
        assert "ja" in languages
        assert "de" in languages
        assert "fr" in languages
        assert "en" in languages
        assert len(languages) == 5

    @pytest.mark.unit
    def test_get_confidence_decay_chinese(self, pipeline: TranslationPipeline) -> None:
        """Test Chinese confidence decay."""
        decay = pipeline.get_confidence_decay("zh")
        assert decay == 0.80

    @pytest.mark.unit
    def test_get_confidence_decay_japanese(self, pipeline: TranslationPipeline) -> None:
        """Test Japanese confidence decay."""
        decay = pipeline.get_confidence_decay("ja")
        assert decay == 0.85

    @pytest.mark.unit
    def test_get_confidence_decay_german(self, pipeline: TranslationPipeline) -> None:
        """Test German confidence decay."""
        decay = pipeline.get_confidence_decay("de")
        assert decay == 0.95

    @pytest.mark.unit
    def test_get_confidence_decay_french(self, pipeline: TranslationPipeline) -> None:
        """Test French confidence decay."""
        decay = pipeline.get_confidence_decay("fr")
        assert decay == 0.95

    @pytest.mark.unit
    def test_get_confidence_decay_english(self, pipeline: TranslationPipeline) -> None:
        """Test English confidence decay (no translation)."""
        decay = pipeline.get_confidence_decay("en")
        assert decay == 1.00

    @pytest.mark.unit
    def test_get_confidence_decay_unsupported(self, pipeline: TranslationPipeline) -> None:
        """Test unsupported language raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported language"):
            pipeline.get_confidence_decay("es")

    @pytest.mark.unit
    def test_get_confidence_decay_case_insensitive(self, pipeline: TranslationPipeline) -> None:
        """Test language codes are case-insensitive."""
        assert pipeline.get_confidence_decay("ZH") == 0.80
        assert pipeline.get_confidence_decay("De") == 0.95


class TestTranslationPipelineEnglishPassthrough:
    """Tests for English passthrough (no translation needed)."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline instance."""
        return TranslationPipeline(device="cpu")

    @pytest.mark.unit
    def test_translate_english_passthrough(self, pipeline: TranslationPipeline) -> None:
        """Test English text passes through unchanged."""
        text = SAMPLE_TEXTS["en"]
        result = pipeline.translate(text, source_lang="en")

        assert result.text == text
        assert result.source_lang == "en"
        assert result.model_used == "passthrough"
        assert result.confidence == 1.0
        assert result.is_truncated is False

    @pytest.mark.unit
    def test_translate_batch_english(self, pipeline: TranslationPipeline) -> None:
        """Test batch English translation passes through."""
        texts = [SAMPLE_TEXTS["en"], "Another English text", "Third English text"]
        results = pipeline.translate_batch(texts, source_lang="en")

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.text == texts[i]
            assert result.model_used == "passthrough"
            assert result.confidence == 1.0

    @pytest.mark.unit
    def test_translate_batch_empty(self, pipeline: TranslationPipeline) -> None:
        """Test empty batch returns empty list."""
        results = pipeline.translate_batch([], source_lang="en")
        assert results == []


class TestTranslationPipelineUnsupportedLanguage:
    """Tests for unsupported language handling."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline instance."""
        return TranslationPipeline(device="cpu")

    @pytest.mark.unit
    def test_translate_unsupported_language(self, pipeline: TranslationPipeline) -> None:
        """Test unsupported language raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported language"):
            pipeline.translate("Hola mundo", source_lang="es")

    @pytest.mark.unit
    def test_translate_batch_unsupported_language(self, pipeline: TranslationPipeline) -> None:
        """Test batch with unsupported language raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported language"):
            pipeline.translate_batch(["text1", "text2"], source_lang="ru")


class TestTranslationPipelineWithMocks:
    """Tests for translation with mocked HuggingFace models."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline instance."""
        return TranslationPipeline(device="cpu")

    @pytest.fixture
    def mock_opus_model(self) -> MagicMock:
        """Create mock OPUS-MT model."""
        model = MagicMock()
        model.to.return_value = model
        model.eval.return_value = None
        model.generate.return_value = [[101, 102, 103]]  # Fake token IDs
        return model

    @pytest.fixture
    def mock_opus_tokenizer(self) -> MagicMock:
        """Create mock OPUS tokenizer."""
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1, 2, 3, 4, 5]
        tokenizer.decode.return_value = "Translated text from German"

        # Create a mock that can be called and returns something with .to()
        mock_encoding = MagicMock()
        mock_encoding.to.return_value = mock_encoding  # Return self for chaining
        tokenizer.return_value = mock_encoding
        return tokenizer

    @pytest.mark.unit
    def test_translate_german_mocked(
        self,
        pipeline: TranslationPipeline,
        mock_opus_model: MagicMock,
        mock_opus_tokenizer: MagicMock,
    ) -> None:
        """Test German translation with mocked model."""
        with patch(
            "liquidity.news.translation.TranslationPipeline._load_opus_model",
            return_value=(mock_opus_model, mock_opus_tokenizer),
        ):
            result = pipeline.translate(SAMPLE_TEXTS["de"], source_lang="de")

        assert result.source_lang == "de"
        assert result.model_used == OPUS_MODELS["de"]
        assert result.confidence == CONFIDENCE_DECAY["de"]
        assert result.text == "Translated text from German"

    @pytest.mark.unit
    def test_translate_french_mocked(
        self,
        pipeline: TranslationPipeline,
        mock_opus_model: MagicMock,
        mock_opus_tokenizer: MagicMock,
    ) -> None:
        """Test French translation with mocked model."""
        mock_opus_tokenizer.decode.return_value = "The ECB maintains rates unchanged"

        with patch(
            "liquidity.news.translation.TranslationPipeline._load_opus_model",
            return_value=(mock_opus_model, mock_opus_tokenizer),
        ):
            result = pipeline.translate(SAMPLE_TEXTS["fr"], source_lang="fr")

        assert result.source_lang == "fr"
        assert result.model_used == OPUS_MODELS["fr"]
        assert result.confidence == CONFIDENCE_DECAY["fr"]

    @pytest.mark.unit
    def test_translate_japanese_mocked(
        self,
        pipeline: TranslationPipeline,
        mock_opus_model: MagicMock,
        mock_opus_tokenizer: MagicMock,
    ) -> None:
        """Test Japanese translation with mocked model."""
        mock_opus_tokenizer.decode.return_value = "BoJ held monetary policy meeting"

        with patch(
            "liquidity.news.translation.TranslationPipeline._load_opus_model",
            return_value=(mock_opus_model, mock_opus_tokenizer),
        ):
            result = pipeline.translate(SAMPLE_TEXTS["ja"], source_lang="ja")

        assert result.source_lang == "ja"
        assert result.model_used == OPUS_MODELS["ja"]
        assert result.confidence == CONFIDENCE_DECAY["ja"]


class TestTranslationPipelineChineseMocked:
    """Tests for Chinese translation with mocked Qwen model."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline instance."""
        return TranslationPipeline(device="cpu")

    @pytest.fixture
    def mock_qwen_model(self) -> MagicMock:
        """Create mock Qwen model."""
        model = MagicMock()
        model.to.return_value = model
        model.eval.return_value = None
        model.generate.return_value = [[101, 102, 103, 104, 105]]
        return model

    @pytest.fixture
    def mock_qwen_tokenizer(self) -> MagicMock:
        """Create mock Qwen tokenizer."""
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1, 2, 3, 4, 5]
        tokenizer.decode.return_value = (
            "System prompt... User: ... English: "
            "The PBoC decided to cut RRR by 0.5 percentage points"
        )
        tokenizer.apply_chat_template.return_value = "formatted_prompt"
        tokenizer.eos_token_id = 0
        tokenizer.return_value = MagicMock(
            to=lambda x: {"input_ids": MagicMock(), "attention_mask": MagicMock()}  # noqa: ARG005
        )
        return tokenizer

    @pytest.mark.unit
    def test_translate_chinese_mocked(
        self,
        pipeline: TranslationPipeline,
        mock_qwen_model: MagicMock,
        mock_qwen_tokenizer: MagicMock,
    ) -> None:
        """Test Chinese translation with mocked Qwen model."""
        with patch(
            "liquidity.news.translation.TranslationPipeline._load_qwen_model",
            return_value=(mock_qwen_model, mock_qwen_tokenizer),
        ):
            result = pipeline.translate(SAMPLE_TEXTS["zh"], source_lang="zh")

        assert result.source_lang == "zh"
        assert result.model_used == QWEN_MODEL
        assert result.confidence == CONFIDENCE_DECAY["zh"]
        assert "PBoC" in result.text or "RRR" in result.text or "cut" in result.text


class TestTranslationPipelineBatchMocked:
    """Tests for batch translation with mocked models."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline with small batch size."""
        return TranslationPipeline(device="cpu", batch_size=2)

    @pytest.fixture
    def mock_opus_model(self) -> MagicMock:
        """Create mock OPUS model for batch."""
        model = MagicMock()
        model.to.return_value = model
        model.eval.return_value = None
        # Return multiple outputs for batch
        model.generate.return_value = [[101, 102], [201, 202], [301, 302]]
        return model

    @pytest.fixture
    def mock_opus_tokenizer(self) -> MagicMock:
        """Create mock tokenizer for batch."""
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1, 2, 3]

        # Different decode results for each call
        decode_results = iter(["Translation 1", "Translation 2", "Translation 3"])
        tokenizer.decode.side_effect = lambda *args, **kwargs: next(decode_results)  # noqa: ARG005

        # Create a mock that can be called and returns something with .to()
        mock_encoding = MagicMock()
        mock_encoding.to.return_value = mock_encoding
        tokenizer.return_value = mock_encoding
        return tokenizer

    @pytest.mark.unit
    def test_translate_batch_german_mocked(
        self,
        pipeline: TranslationPipeline,
        mock_opus_model: MagicMock,
        mock_opus_tokenizer: MagicMock,
    ) -> None:
        """Test batch German translation."""
        # Use only 2 texts since batch_size is 2
        texts = ["German text 1", "German text 2"]

        # Mock needs to return the right number of outputs
        mock_opus_model.generate.return_value = [[101, 102], [201, 202]]

        # Reset decode iterator for 2 texts
        decode_results = iter(["Translation 1", "Translation 2"])
        mock_opus_tokenizer.decode.side_effect = lambda *_args, **_kwargs: next(decode_results)

        with patch(
            "liquidity.news.translation.TranslationPipeline._load_opus_model",
            return_value=(mock_opus_model, mock_opus_tokenizer),
        ):
            results = pipeline.translate_batch(texts, source_lang="de")

        assert len(results) == 2
        for result in results:
            assert result.source_lang == "de"
            assert result.model_used == OPUS_MODELS["de"]
            assert result.confidence == CONFIDENCE_DECAY["de"]


class TestTranslationPipelineTruncation:
    """Tests for text truncation handling."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline with small max_length."""
        return TranslationPipeline(device="cpu", max_length=10)

    @pytest.mark.unit
    def test_truncation_detected(self, pipeline: TranslationPipeline) -> None:
        """Test that long text is truncated and flagged."""
        mock_tokenizer = MagicMock()
        # Return more tokens than max_length
        mock_tokenizer.encode.return_value = list(range(20))
        mock_tokenizer.decode.return_value = "Truncated translation"
        mock_tokenizer.return_value = MagicMock(
            to=lambda x: {"input_ids": MagicMock(), "attention_mask": MagicMock()}  # noqa: ARG005
        )

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.eval.return_value = None
        mock_model.generate.return_value = [[1, 2, 3]]

        with patch(
            "liquidity.news.translation.TranslationPipeline._load_opus_model",
            return_value=(mock_model, mock_tokenizer),
        ):
            result = pipeline.translate("Very long German text " * 50, source_lang="de")

        assert result.is_truncated is True


class TestTranslationPipelineFallback:
    """Tests for fallback behavior on errors."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline instance."""
        return TranslationPipeline(device="cpu")

    @pytest.mark.unit
    def test_fallback_on_model_load_error(self, pipeline: TranslationPipeline) -> None:
        """Test fallback when model loading fails."""
        with patch(
            "liquidity.news.translation.TranslationPipeline._load_opus_model",
            side_effect=Exception("Model not found"),
        ):
            result = pipeline.translate(SAMPLE_TEXTS["de"], source_lang="de")

        assert result.text == SAMPLE_TEXTS["de"]  # Original text returned
        assert result.model_used == "fallback"
        assert result.confidence == 0.1  # Very low confidence

    @pytest.mark.unit
    def test_fallback_on_qwen_error(self, pipeline: TranslationPipeline) -> None:
        """Test fallback when Qwen model fails."""
        with patch(
            "liquidity.news.translation.TranslationPipeline._load_qwen_model",
            side_effect=Exception("CUDA OOM"),
        ):
            result = pipeline.translate(SAMPLE_TEXTS["zh"], source_lang="zh")

        assert result.text == SAMPLE_TEXTS["zh"]
        assert result.model_used == "fallback"
        assert result.confidence == 0.1


class TestTranslationPipelineModelManagement:
    """Tests for model loading and unloading."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline instance."""
        return TranslationPipeline(device="cpu")

    @pytest.mark.unit
    def test_is_model_loaded_english(self, pipeline: TranslationPipeline) -> None:
        """Test English always returns True (no model needed)."""
        assert pipeline.is_model_loaded("en") is True

    @pytest.mark.unit
    def test_is_model_loaded_not_loaded(self, pipeline: TranslationPipeline) -> None:
        """Test model not loaded initially."""
        assert pipeline.is_model_loaded("de") is False
        assert pipeline.is_model_loaded("zh") is False

    @pytest.mark.unit
    def test_unload_models(self, pipeline: TranslationPipeline) -> None:
        """Test unloading models clears references."""
        # Simulate loaded models
        pipeline._opus_models["de"] = MagicMock()
        pipeline._opus_tokenizers["de"] = MagicMock()
        pipeline._qwen_model = MagicMock()
        pipeline._qwen_tokenizer = MagicMock()

        with patch("torch.cuda.is_available", return_value=False):
            pipeline.unload_models()

        assert pipeline._opus_models == {}
        assert pipeline._opus_tokenizers == {}
        assert pipeline._qwen_model is None
        assert pipeline._qwen_tokenizer is None


class TestConfidenceDecayConstants:
    """Tests for confidence decay constant values."""

    @pytest.mark.unit
    def test_confidence_decay_values(self) -> None:
        """Test confidence decay values match requirements."""
        assert CONFIDENCE_DECAY["zh"] == 0.80
        assert CONFIDENCE_DECAY["ja"] == 0.85
        assert CONFIDENCE_DECAY["de"] == 0.95
        assert CONFIDENCE_DECAY["fr"] == 0.95
        assert CONFIDENCE_DECAY["en"] == 1.00

    @pytest.mark.unit
    def test_opus_models_mapping(self) -> None:
        """Test OPUS model mappings exist."""
        assert "ja" in OPUS_MODELS
        assert "de" in OPUS_MODELS
        assert "fr" in OPUS_MODELS
        assert "zh" not in OPUS_MODELS  # Chinese uses Qwen

    @pytest.mark.unit
    def test_max_length_constant(self) -> None:
        """Test MAX_LENGTH constant."""
        assert MAX_LENGTH == 512


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def pipeline(self) -> TranslationPipeline:
        """Create pipeline instance."""
        return TranslationPipeline(device="cpu")

    @pytest.mark.unit
    def test_translate_empty_string(self, pipeline: TranslationPipeline) -> None:
        """Test translating empty string."""
        result = pipeline.translate("", source_lang="en")
        assert result.text == ""
        assert result.confidence == 1.0

    @pytest.mark.unit
    def test_translate_whitespace_only(self, pipeline: TranslationPipeline) -> None:
        """Test translating whitespace-only string."""
        result = pipeline.translate("   \n\t   ", source_lang="en")
        assert result.text == "   \n\t   "

    @pytest.mark.unit
    def test_translate_case_insensitive_lang(self, pipeline: TranslationPipeline) -> None:
        """Test language codes are case-insensitive."""
        result1 = pipeline.translate("Test", source_lang="EN")
        result2 = pipeline.translate("Test", source_lang="en")
        result3 = pipeline.translate("Test", source_lang="En")

        assert result1.source_lang == "en"
        assert result2.source_lang == "en"
        assert result3.source_lang == "en"

    @pytest.mark.unit
    def test_batch_preserves_order(self, pipeline: TranslationPipeline) -> None:
        """Test batch translation preserves input order."""
        texts = ["First", "Second", "Third"]
        results = pipeline.translate_batch(texts, source_lang="en")

        assert [r.text for r in results] == texts
