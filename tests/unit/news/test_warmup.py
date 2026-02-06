"""Tests for model warmup utilities.

Tests the warmup functionality without actually loading models.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from liquidity.news.warmup import (
    WarmupResult,
    WarmupSummary,
    _warm_finbert,
    _warm_translation_model,
    warm_models,
    warm_models_minimal,
)


# =============================================================================
# WarmupResult Tests
# =============================================================================


class TestWarmupResult:
    """Tests for WarmupResult dataclass."""

    def test_successful_result(self) -> None:
        """Successful result should have correct fields."""
        result = WarmupResult(
            model_name="test-model",
            success=True,
            load_time_seconds=1.5,
        )
        assert result.model_name == "test-model"
        assert result.success is True
        assert result.load_time_seconds == 1.5
        assert result.error is None

    def test_failed_result(self) -> None:
        """Failed result should include error."""
        result = WarmupResult(
            model_name="test-model",
            success=False,
            load_time_seconds=0.1,
            error="Import error",
        )
        assert result.success is False
        assert result.error == "Import error"

    def test_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        result = WarmupResult(
            model_name="test-model",
            success=True,
            load_time_seconds=1.234,
        )
        d = result.to_dict()
        assert d["model_name"] == "test-model"
        assert d["success"] is True
        assert d["load_time_seconds"] == 1.23  # Rounded


# =============================================================================
# WarmupSummary Tests
# =============================================================================


class TestWarmupSummary:
    """Tests for WarmupSummary dataclass."""

    def test_all_success(self) -> None:
        """All success should be calculated correctly."""
        results = [
            WarmupResult("model1", True, 1.0),
            WarmupResult("model2", True, 2.0),
        ]
        summary = WarmupSummary(results=results, total_time_seconds=3.0)

        assert summary.all_success is True
        assert summary.models_loaded == 2
        assert summary.models_failed == 0

    def test_partial_success(self) -> None:
        """Partial success should be calculated correctly."""
        results = [
            WarmupResult("model1", True, 1.0),
            WarmupResult("model2", False, 0.1, error="Failed"),
        ]
        summary = WarmupSummary(results=results, total_time_seconds=1.1)

        assert summary.all_success is False
        assert summary.models_loaded == 1
        assert summary.models_failed == 1

    def test_empty_results(self) -> None:
        """Empty results should work."""
        summary = WarmupSummary(results=[], total_time_seconds=0.0)

        assert summary.all_success is True
        assert summary.models_loaded == 0
        assert summary.models_failed == 0

    def test_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        results = [WarmupResult("model1", True, 1.0)]
        summary = WarmupSummary(results=results, total_time_seconds=1.0)

        d = summary.to_dict()
        assert "results" in d
        assert "total_time_seconds" in d
        assert "models_loaded" in d
        assert "all_success" in d


# =============================================================================
# Warmup Function Tests (Mocked)
# =============================================================================


class TestWarmFinbert:
    """Tests for finBERT warming function."""

    def test_finbert_returns_result(self) -> None:
        """Should always return a WarmupResult."""
        # _warm_finbert handles its own exceptions, so this should never raise
        result = _warm_finbert()
        assert isinstance(result, WarmupResult)
        assert result.model_name == "ProsusAI/finbert"
        # May succeed or fail depending on whether transformers is available
        assert result.load_time_seconds >= 0


class TestWarmTranslationModel:
    """Tests for OPUS-MT translation model warming."""

    def test_unsupported_language(self) -> None:
        """Should return failure for unsupported language."""
        result = _warm_translation_model("xx")  # Unsupported
        assert result.success is False
        assert "not supported" in (result.error or "")

    def test_supported_language_returns_result(self) -> None:
        """Should return a WarmupResult for supported language."""
        result = _warm_translation_model("de")
        assert isinstance(result, WarmupResult)
        # May succeed or fail depending on whether transformers is available
        assert result.load_time_seconds >= 0


# =============================================================================
# Async Warmup Tests
# =============================================================================


class TestWarmModels:
    """Tests for async warm_models function."""

    @pytest.mark.asyncio
    async def test_no_models_selected(self) -> None:
        """Should handle case where no models are selected."""
        summary = await warm_models(
            include_sentiment=False,
            include_translation=False,
            include_chinese=False,
        )

        assert summary.total_time_seconds >= 0
        assert len(summary.results) == 0
        assert summary.all_success is True

    @pytest.mark.asyncio
    async def test_specific_translation_languages(self) -> None:
        """Should warm only specified languages."""
        # Mock to prevent actual model loading
        with patch(
            "liquidity.news.warmup._warm_translation_model",
            return_value=WarmupResult("test", True, 0.1),
        ) as mock_warm:
            summary = await warm_models(
                include_sentiment=False,
                include_translation=True,
                translation_languages=["de"],
                include_chinese=False,
            )

            # Should only warm German
            mock_warm.assert_called_once()
            call_args = mock_warm.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_all_default_languages(self) -> None:
        """Should warm all default languages when none specified."""
        with patch(
            "liquidity.news.warmup._warm_translation_model",
            return_value=WarmupResult("test", True, 0.1),
        ) as mock_warm:
            summary = await warm_models(
                include_sentiment=False,
                include_translation=True,
                translation_languages=None,  # Use defaults
                include_chinese=False,
            )

            # Should warm ja, de, fr (3 languages)
            assert mock_warm.call_count == 3


class TestWarmModelsMinimal:
    """Tests for minimal warmup function."""

    @pytest.mark.asyncio
    async def test_minimal_only_warms_sentiment(self) -> None:
        """Minimal warmup should only warm sentiment model."""
        with patch(
            "liquidity.news.warmup._warm_finbert",
            return_value=WarmupResult("finbert", True, 0.5),
        ) as mock_finbert, patch(
            "liquidity.news.warmup._warm_translation_model",
            return_value=WarmupResult("opus", True, 0.1),
        ) as mock_opus:
            summary = await warm_models_minimal()

            # Should call finBERT
            mock_finbert.assert_called_once()

            # Should NOT call translation
            mock_opus.assert_not_called()
