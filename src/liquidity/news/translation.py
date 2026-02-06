"""NLP Translation Pipeline for central bank news and documents.

Provides multi-language translation support for financial documents with:
- Helsinki-NLP OPUS-MT models for EU languages (ja, de, fr)
- Qwen3-1.5B for Chinese (better quality for financial docs)
- Lazy model loading to conserve memory
- Confidence scoring for downstream sentiment weighting

References:
    - Helsinki-NLP OPUS-MT: https://huggingface.co/Helsinki-NLP
    - Qwen3: https://huggingface.co/Qwen/Qwen2.5-1.5B
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SupportedLanguage(str, Enum):
    """Supported source languages for translation."""

    CHINESE = "zh"
    JAPANESE = "ja"
    GERMAN = "de"
    FRENCH = "fr"
    ENGLISH = "en"


# Language-specific confidence decay factors
# Lower values indicate translation may reduce accuracy
CONFIDENCE_DECAY: dict[str, float] = {
    "zh": 0.80,  # Chinese: complex financial terminology
    "ja": 0.85,  # Japanese: formal vs informal variations
    "de": 0.95,  # German: high quality OPUS model
    "fr": 0.95,  # French: high quality OPUS model
    "en": 1.00,  # English: no translation needed
}

# Helsinki-NLP OPUS-MT model mappings
OPUS_MODELS: dict[str, str] = {
    "ja": "Helsinki-NLP/opus-mt-ja-en",
    "de": "Helsinki-NLP/opus-mt-de-en",
    "fr": "Helsinki-NLP/opus-mt-fr-en",
}

# Qwen model for Chinese (better financial document quality)
QWEN_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

# Maximum token length for input
MAX_LENGTH = 512


@dataclass
class TranslationResult:
    """Result of a translation operation.

    Attributes:
        text: Translated text (or original if source is English).
        source_lang: Detected or specified source language code.
        model_used: Name of the translation model used.
        confidence: Confidence score (0-1) for downstream weighting.
        is_truncated: Whether input was truncated to MAX_LENGTH.
    """

    text: str
    source_lang: str
    model_used: str
    confidence: float
    is_truncated: bool

    def __post_init__(self) -> None:
        """Validate result fields."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "source_lang": self.source_lang,
            "model_used": self.model_used,
            "confidence": self.confidence,
            "is_truncated": self.is_truncated,
        }


class TranslationPipeline:
    """Multi-language translation pipeline for central bank documents.

    Uses Helsinki-NLP OPUS-MT for EU languages and Qwen3-1.5B for Chinese.
    Models are loaded lazily on first use to conserve memory.

    Supports batch processing with configurable batch size.

    Example:
        >>> pipeline = TranslationPipeline()
        >>> result = pipeline.translate("Bundesbank erhöht Zinsen", source_lang="de")
        >>> print(f"Translation: {result.text} (confidence: {result.confidence})")

        >>> # Batch translation
        >>> texts = ["Text 1", "Text 2", "Text 3"]
        >>> results = pipeline.translate_batch(texts, source_lang="fr")
    """

    def __init__(
        self,
        device: str | None = None,
        batch_size: int = 16,
        max_length: int = MAX_LENGTH,
    ) -> None:
        """Initialize translation pipeline.

        Args:
            device: Device to use ('cpu', 'cuda', or None for auto-detect).
            batch_size: Batch size for batch processing. Default 16.
            max_length: Maximum input token length. Default 512.
        """
        import torch

        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.batch_size = batch_size
        self.max_length = max_length

        # Lazy-loaded models (None until first use)
        # Using Any type as transformers doesn't have complete type stubs
        self._opus_models: dict[str, Any] = {}
        self._opus_tokenizers: dict[str, Any] = {}
        self._qwen_model: Any = None
        self._qwen_tokenizer: Any = None

        logger.info(
            "TranslationPipeline initialized (device=%s, batch_size=%d, max_length=%d)",
            self.device,
            self.batch_size,
            self.max_length,
        )

    def _load_opus_model(self, lang: str) -> tuple[Any, Any]:
        """Load Helsinki-NLP OPUS-MT model for a language.

        Args:
            lang: Source language code (ja, de, fr).

        Returns:
            Tuple of (model, tokenizer).

        Raises:
            ValueError: If language not supported by OPUS.
        """
        if lang not in OPUS_MODELS:
            raise ValueError(f"Language '{lang}' not supported by OPUS-MT")

        if self._opus_models.get(lang) is not None:
            return self._opus_models[lang], self._opus_tokenizers[lang]

        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        model_name = OPUS_MODELS[lang]
        logger.info("Loading OPUS-MT model: %s", model_name)

        tokenizer: Any = AutoTokenizer.from_pretrained(model_name)
        model: Any = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        model = model.to(self.device)
        model.eval()

        self._opus_models[lang] = model
        self._opus_tokenizers[lang] = tokenizer

        logger.info("OPUS-MT model loaded: %s", model_name)
        return model, tokenizer

    def _load_qwen_model(self) -> tuple[Any, Any]:
        """Load Qwen model for Chinese translation.

        Returns:
            Tuple of (model, tokenizer).
        """
        if self._qwen_model is not None:
            return self._qwen_model, self._qwen_tokenizer

        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading Qwen model: %s", QWEN_MODEL)

        tokenizer: Any = AutoTokenizer.from_pretrained(QWEN_MODEL, trust_remote_code=True)
        model: Any = AutoModelForCausalLM.from_pretrained(
            QWEN_MODEL,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="auto" if self.device == "cuda" else None,
        )

        if self.device == "cpu":
            model = model.to(self.device)

        model.eval()

        self._qwen_model = model
        self._qwen_tokenizer = tokenizer

        logger.info("Qwen model loaded: %s", QWEN_MODEL)
        return model, tokenizer

    def translate(
        self,
        text: str,
        source_lang: str,
    ) -> TranslationResult:
        """Translate a single text from source language to English.

        Args:
            text: Text to translate.
            source_lang: Source language code (zh, ja, de, fr, en).

        Returns:
            TranslationResult with translated text and metadata.

        Raises:
            ValueError: If source language not supported.
        """
        # Validate language
        lang = source_lang.lower()
        if lang not in CONFIDENCE_DECAY:
            raise ValueError(
                f"Unsupported language: {source_lang}. "
                f"Supported: {list(CONFIDENCE_DECAY.keys())}"
            )

        # English: no translation needed
        if lang == "en":
            return TranslationResult(
                text=text,
                source_lang="en",
                model_used="passthrough",
                confidence=1.0,
                is_truncated=False,
            )

        # Chinese: use Qwen
        if lang == "zh":
            return self._translate_chinese(text)

        # EU languages: use OPUS-MT
        return self._translate_opus(text, lang)

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str,
    ) -> list[TranslationResult]:
        """Translate a batch of texts from source language to English.

        Args:
            texts: List of texts to translate.
            source_lang: Source language code (zh, ja, de, fr, en).

        Returns:
            List of TranslationResult objects.

        Raises:
            ValueError: If source language not supported.
        """
        if not texts:
            return []

        # Validate language
        lang = source_lang.lower()
        if lang not in CONFIDENCE_DECAY:
            raise ValueError(
                f"Unsupported language: {source_lang}. "
                f"Supported: {list(CONFIDENCE_DECAY.keys())}"
            )

        # English: no translation needed
        if lang == "en":
            return [
                TranslationResult(
                    text=t,
                    source_lang="en",
                    model_used="passthrough",
                    confidence=1.0,
                    is_truncated=False,
                )
                for t in texts
            ]

        # Process in batches
        results: list[TranslationResult] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

            if lang == "zh":
                # Chinese: process one by one (Qwen is generative)
                for text in batch:
                    results.append(self._translate_chinese(text))
            else:
                # EU languages: batch with OPUS-MT
                batch_results = self._translate_opus_batch(batch, lang)
                results.extend(batch_results)

        return results

    def _translate_chinese(self, text: str) -> TranslationResult:
        """Translate Chinese text using Qwen model.

        Uses a prompt-based approach for translation.

        Args:
            text: Chinese text to translate.

        Returns:
            TranslationResult with translation.
        """
        import torch

        try:
            model, tokenizer = self._load_qwen_model()
        except Exception as e:
            logger.warning("Failed to load Qwen model: %s, falling back to original", e)
            return self._fallback_result(text, "zh", str(e))

        # Check if text needs truncation
        is_truncated = False
        encoded = tokenizer.encode(text, add_special_tokens=False)
        if len(encoded) > self.max_length:
            is_truncated = True
            # Truncate and decode back to text
            encoded = encoded[: self.max_length]
            text = tokenizer.decode(encoded)

        # Construct translation prompt
        prompt = (
            "Translate the following Chinese financial text to English. "
            "Preserve technical terminology accurately.\n\n"
            f"Chinese: {text}\n\n"
            "English:"
        )

        messages = [
            {"role": "system", "content": "You are a professional financial translator."},
            {"role": "user", "content": prompt},
        ]

        try:
            # Format for chat model
            formatted_prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

            inputs = tokenizer(
                formatted_prompt,
                return_tensors="pt",
                truncation=True,
                max_length=self.max_length * 2,  # Allow for prompt overhead
            ).to(self.device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=self.max_length,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )

            # Decode and extract translation
            full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Extract the translation part (after "English:")
            if "English:" in full_output:
                translation = full_output.split("English:")[-1].strip()
            else:
                translation = full_output.split(prompt)[-1].strip()

            # Clean up any trailing artifacts
            translation = translation.split("\n")[0].strip()

            return TranslationResult(
                text=translation,
                source_lang="zh",
                model_used=QWEN_MODEL,
                confidence=CONFIDENCE_DECAY["zh"],
                is_truncated=is_truncated,
            )

        except Exception as e:
            logger.warning("Qwen translation failed: %s, falling back to Helsinki", e)
            # Try Helsinki as fallback (if it exists for zh - it doesn't, so fall through)
            return self._fallback_result(text, "zh", str(e))

    def _translate_opus(self, text: str, lang: str) -> TranslationResult:
        """Translate using Helsinki-NLP OPUS-MT model.

        Args:
            text: Text to translate.
            lang: Source language code (ja, de, fr).

        Returns:
            TranslationResult with translation.
        """
        import torch

        try:
            model, tokenizer = self._load_opus_model(lang)
        except Exception as e:
            logger.warning("Failed to load OPUS model for %s: %s", lang, e)
            return self._fallback_result(text, lang, str(e))

        # Check if text needs truncation
        is_truncated = False
        encoded = tokenizer.encode(text, add_special_tokens=True)
        if len(encoded) > self.max_length:
            is_truncated = True
            # Truncate at token level
            encoded = encoded[: self.max_length]
            text = tokenizer.decode(encoded, skip_special_tokens=True)

        try:
            inputs = tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length,
            ).to(self.device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_length=self.max_length,
                    num_beams=4,
                    early_stopping=True,
                )

            translation = tokenizer.decode(outputs[0], skip_special_tokens=True)

            return TranslationResult(
                text=translation,
                source_lang=lang,
                model_used=OPUS_MODELS[lang],
                confidence=CONFIDENCE_DECAY[lang],
                is_truncated=is_truncated,
            )

        except Exception as e:
            logger.warning("OPUS translation failed for %s: %s", lang, e)
            return self._fallback_result(text, lang, str(e))

    def _translate_opus_batch(
        self,
        texts: list[str],
        lang: str,
    ) -> list[TranslationResult]:
        """Batch translate using Helsinki-NLP OPUS-MT model.

        Args:
            texts: List of texts to translate.
            lang: Source language code (ja, de, fr).

        Returns:
            List of TranslationResult objects.
        """
        import torch

        try:
            model, tokenizer = self._load_opus_model(lang)
        except Exception as e:
            logger.warning("Failed to load OPUS model for %s: %s", lang, e)
            return [self._fallback_result(t, lang, str(e)) for t in texts]

        # Pre-process: check for truncation
        processed_texts: list[str] = []
        truncation_flags: list[bool] = []

        for text in texts:
            encoded = tokenizer.encode(text, add_special_tokens=True)
            if len(encoded) > self.max_length:
                truncation_flags.append(True)
                encoded = encoded[: self.max_length]
                processed_texts.append(tokenizer.decode(encoded, skip_special_tokens=True))
            else:
                truncation_flags.append(False)
                processed_texts.append(text)

        try:
            inputs = tokenizer(
                processed_texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_length,
            ).to(self.device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_length=self.max_length,
                    num_beams=4,
                    early_stopping=True,
                )

            results: list[TranslationResult] = []
            for i, output in enumerate(outputs):
                translation = tokenizer.decode(output, skip_special_tokens=True)
                results.append(
                    TranslationResult(
                        text=translation,
                        source_lang=lang,
                        model_used=OPUS_MODELS[lang],
                        confidence=CONFIDENCE_DECAY[lang],
                        is_truncated=truncation_flags[i],
                    )
                )

            return results

        except Exception as e:
            logger.warning("OPUS batch translation failed for %s: %s", lang, e)
            return [self._fallback_result(t, lang, str(e)) for t in texts]

    def _fallback_result(
        self,
        original_text: str,
        lang: str,
        error: str,
    ) -> TranslationResult:
        """Create fallback result when translation fails.

        Returns original text with minimal confidence.

        Args:
            original_text: Original untranslated text.
            lang: Source language code.
            error: Error message for logging.

        Returns:
            TranslationResult with original text and low confidence.
        """
        logger.warning(
            "Translation fallback: returning original text (lang=%s, error=%s)",
            lang,
            error,
        )
        return TranslationResult(
            text=original_text,
            source_lang=lang,
            model_used="fallback",
            confidence=0.1,  # Very low confidence for fallback
            is_truncated=False,
        )

    def unload_models(self) -> None:
        """Unload all models from memory.

        Useful for freeing GPU memory when translation is not needed.
        """
        import gc

        import torch

        # Clear OPUS models
        for lang in list(self._opus_models.keys()):
            if self._opus_models[lang] is not None:
                del self._opus_models[lang]
                del self._opus_tokenizers[lang]
        self._opus_models = {}
        self._opus_tokenizers = {}

        # Clear Qwen model
        if self._qwen_model is not None:
            del self._qwen_model
            del self._qwen_tokenizer
            self._qwen_model = None
            self._qwen_tokenizer = None

        # Force garbage collection
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("All translation models unloaded")

    def get_supported_languages(self) -> list[str]:
        """Get list of supported source languages.

        Returns:
            List of language codes.
        """
        return list(CONFIDENCE_DECAY.keys())

    def get_confidence_decay(self, lang: str) -> float:
        """Get confidence decay factor for a language.

        Args:
            lang: Source language code.

        Returns:
            Confidence decay factor (0-1).

        Raises:
            ValueError: If language not supported.
        """
        lang = lang.lower()
        if lang not in CONFIDENCE_DECAY:
            raise ValueError(f"Unsupported language: {lang}")
        return CONFIDENCE_DECAY[lang]

    def is_model_loaded(self, lang: str) -> bool:
        """Check if model for a language is currently loaded.

        Args:
            lang: Source language code.

        Returns:
            True if model is loaded.
        """
        lang = lang.lower()
        if lang == "zh":
            return self._qwen_model is not None
        if lang == "en":
            return True  # No model needed
        return self._opus_models.get(lang) is not None
