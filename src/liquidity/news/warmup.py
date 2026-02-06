"""Model warming utilities for NLP pipeline startup.

Pre-loads all NLP models at application startup to reduce first-request latency.
This is especially important for real-time monitoring where we need sub-60s response.

Models warmed:
- finBERT (sentiment analysis) - if available
- Helsinki-NLP OPUS-MT (translation for ja, de, fr)
- Qwen (Chinese translation) - optional, as it's memory-intensive

Usage:
    from liquidity.news.warmup import warm_models

    # At application startup
    await warm_models()

    # With specific options
    await warm_models(include_translation=True, include_chinese=False)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WarmupResult:
    """Result of model warming operation.

    Attributes:
        model_name: Name of the model.
        success: Whether warming succeeded.
        load_time_seconds: Time taken to load the model.
        error: Error message if warming failed.
    """

    model_name: str
    success: bool
    load_time_seconds: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "success": self.success,
            "load_time_seconds": round(self.load_time_seconds, 2),
            "error": self.error,
        }


@dataclass
class WarmupSummary:
    """Summary of all model warming operations.

    Attributes:
        results: List of individual warming results.
        total_time_seconds: Total time for all warmups.
        models_loaded: Number of models successfully loaded.
        models_failed: Number of models that failed to load.
    """

    results: list[WarmupResult]
    total_time_seconds: float

    @property
    def models_loaded(self) -> int:
        """Count of successfully loaded models."""
        return sum(1 for r in self.results if r.success)

    @property
    def models_failed(self) -> int:
        """Count of failed model loads."""
        return sum(1 for r in self.results if not r.success)

    @property
    def all_success(self) -> bool:
        """Check if all models loaded successfully."""
        return all(r.success for r in self.results)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "results": [r.to_dict() for r in self.results],
            "total_time_seconds": round(self.total_time_seconds, 2),
            "models_loaded": self.models_loaded,
            "models_failed": self.models_failed,
            "all_success": self.all_success,
        }


def _warm_finbert() -> WarmupResult:
    """Load finBERT sentiment model.

    Returns:
        WarmupResult with loading outcome.
    """
    model_name = "ProsusAI/finbert"
    start = time.perf_counter()

    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info("Loading finBERT model: %s", model_name)

        # Load tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)

        # Run a dummy inference to fully initialize
        inputs = tokenizer(
            "The Federal Reserve raised interest rates.",
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        _ = model(**inputs)

        load_time = time.perf_counter() - start
        logger.info("finBERT loaded successfully in %.2fs", load_time)

        return WarmupResult(
            model_name=model_name,
            success=True,
            load_time_seconds=load_time,
        )

    except ImportError as e:
        load_time = time.perf_counter() - start
        error = f"transformers not installed: {e}"
        logger.warning("finBERT warmup skipped: %s", error)
        return WarmupResult(
            model_name=model_name,
            success=False,
            load_time_seconds=load_time,
            error=error,
        )

    except Exception as e:
        load_time = time.perf_counter() - start
        error = f"{type(e).__name__}: {e}"
        logger.warning("finBERT warmup failed: %s", error)
        return WarmupResult(
            model_name=model_name,
            success=False,
            load_time_seconds=load_time,
            error=error,
        )


def _warm_translation_model(lang: str) -> WarmupResult:
    """Load Helsinki-NLP OPUS-MT translation model.

    Args:
        lang: Source language code (ja, de, fr).

    Returns:
        WarmupResult with loading outcome.
    """
    from liquidity.news.translation import OPUS_MODELS

    if lang not in OPUS_MODELS:
        return WarmupResult(
            model_name=f"opus-mt-{lang}-en",
            success=False,
            load_time_seconds=0.0,
            error=f"Language '{lang}' not supported",
        )

    model_name = OPUS_MODELS[lang]
    start = time.perf_counter()

    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        logger.info("Loading OPUS-MT model: %s", model_name)

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

        # Run dummy translation to initialize
        inputs = tokenizer("Test.", return_tensors="pt", padding=True)
        _ = model.generate(**inputs, max_length=10)

        load_time = time.perf_counter() - start
        logger.info("OPUS-MT (%s) loaded in %.2fs", lang, load_time)

        return WarmupResult(
            model_name=model_name,
            success=True,
            load_time_seconds=load_time,
        )

    except ImportError as e:
        load_time = time.perf_counter() - start
        error = f"transformers not installed: {e}"
        logger.warning("OPUS-MT (%s) warmup skipped: %s", lang, error)
        return WarmupResult(
            model_name=model_name,
            success=False,
            load_time_seconds=load_time,
            error=error,
        )

    except Exception as e:
        load_time = time.perf_counter() - start
        error = f"{type(e).__name__}: {e}"
        logger.warning("OPUS-MT (%s) warmup failed: %s", lang, error)
        return WarmupResult(
            model_name=model_name,
            success=False,
            load_time_seconds=load_time,
            error=error,
        )


def _warm_qwen() -> WarmupResult:
    """Load Qwen model for Chinese translation.

    This is memory-intensive (~3GB) so it's optional.

    Returns:
        WarmupResult with loading outcome.
    """
    from liquidity.news.translation import QWEN_MODEL

    model_name = QWEN_MODEL
    start = time.perf_counter()

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading Qwen model: %s (this may take a while)", model_name)

        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype="auto",
            device_map="auto",
        )

        # Run minimal inference to initialize
        inputs = tokenizer("Hello", return_tensors="pt")
        _ = model.generate(**inputs, max_new_tokens=5)

        load_time = time.perf_counter() - start
        logger.info("Qwen loaded in %.2fs", load_time)

        return WarmupResult(
            model_name=model_name,
            success=True,
            load_time_seconds=load_time,
        )

    except ImportError as e:
        load_time = time.perf_counter() - start
        error = f"transformers not installed: {e}"
        logger.warning("Qwen warmup skipped: %s", error)
        return WarmupResult(
            model_name=model_name,
            success=False,
            load_time_seconds=load_time,
            error=error,
        )

    except Exception as e:
        load_time = time.perf_counter() - start
        error = f"{type(e).__name__}: {e}"
        logger.warning("Qwen warmup failed: %s", error)
        return WarmupResult(
            model_name=model_name,
            success=False,
            load_time_seconds=load_time,
            error=error,
        )


async def warm_models(
    include_sentiment: bool = True,
    include_translation: bool = True,
    translation_languages: list[str] | None = None,
    include_chinese: bool = False,
) -> WarmupSummary:
    """Pre-load all NLP models at application startup.

    Loads models in parallel where possible to minimize total warmup time.
    Uses asyncio.to_thread to prevent blocking the event loop.

    Args:
        include_sentiment: Load finBERT sentiment model. Default True.
        include_translation: Load OPUS-MT translation models. Default True.
        translation_languages: List of languages to warm (ja, de, fr).
                             Defaults to all supported languages.
        include_chinese: Load Qwen for Chinese translation. Default False
                        (memory-intensive, ~3GB).

    Returns:
        WarmupSummary with results for all warming operations.

    Example:
        # Warm all default models
        summary = await warm_models()
        logger.info("Models warmed in %.1fs", summary.total_time_seconds)

        # Warm only sentiment model
        summary = await warm_models(include_translation=False)

        # Warm specific translation languages
        summary = await warm_models(translation_languages=["de", "ja"])
    """
    start_total = time.perf_counter()
    results: list[WarmupResult] = []

    logger.info("Starting model warmup...")

    # Prepare warmup tasks
    tasks: list[tuple[str, Any]] = []

    if include_sentiment:
        tasks.append(("sentiment", _warm_finbert))

    if include_translation:
        langs = translation_languages or ["ja", "de", "fr"]
        for lang in langs:
            tasks.append((f"translation_{lang}", lambda lang_code=lang: _warm_translation_model(lang_code)))

    if include_chinese:
        tasks.append(("qwen", _warm_qwen))

    # Run warmups in parallel using to_thread
    async def run_warmup(name: str, func: Any) -> WarmupResult:
        """Run warmup in thread pool."""
        logger.debug("Starting warmup: %s", name)
        return await asyncio.to_thread(func)

    if tasks:
        warmup_coros = [run_warmup(name, func) for name, func in tasks]
        completed = await asyncio.gather(*warmup_coros, return_exceptions=True)

        for (name, _), result in zip(tasks, completed, strict=False):
            if isinstance(result, Exception):
                results.append(
                    WarmupResult(
                        model_name=name,
                        success=False,
                        load_time_seconds=0.0,
                        error=f"{type(result).__name__}: {result}",
                    )
                )
            else:
                results.append(result)

    total_time = time.perf_counter() - start_total

    summary = WarmupSummary(results=results, total_time_seconds=total_time)

    # Log summary
    logger.info(
        "Model warmup complete: %d/%d loaded in %.1fs",
        summary.models_loaded,
        len(results),
        total_time,
    )

    for result in results:
        if result.success:
            logger.debug("  - %s: %.2fs", result.model_name, result.load_time_seconds)
        else:
            logger.warning("  - %s: FAILED (%s)", result.model_name, result.error)

    return summary


async def warm_models_minimal() -> WarmupSummary:
    """Minimal model warmup for FOMC watcher.

    Only warms the sentiment model needed for statement analysis.
    This is the recommended warmup for the real-time statement webhook.

    Returns:
        WarmupSummary with results.
    """
    return await warm_models(
        include_sentiment=True,
        include_translation=False,
        include_chinese=False,
    )


def warm_models_sync(
    include_sentiment: bool = True,
    include_translation: bool = True,
    translation_languages: list[str] | None = None,
    include_chinese: bool = False,
) -> WarmupSummary:
    """Synchronous version of warm_models.

    Useful when called outside an async context.

    Args:
        Same as warm_models.

    Returns:
        WarmupSummary with results.
    """
    return asyncio.run(
        warm_models(
            include_sentiment=include_sentiment,
            include_translation=include_translation,
            translation_languages=translation_languages,
            include_chinese=include_chinese,
        )
    )
