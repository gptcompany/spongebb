"""Unit tests for TermStructureAnalyzer."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from liquidity.analyzers.term_structure import (
    CurveShape,
    RollYieldMetrics,
    TermStructureAnalyzer,
)


@pytest.fixture
def analyzer():
    """Default analyzer instance."""
    return TermStructureAnalyzer()


@pytest.fixture
def backwardation_data():
    """Price data with positive momentum (backwardation signal)."""
    dates = pd.date_range("2024-01-01", periods=25, freq="D")
    return pd.DataFrame([
        {"timestamp": d, "series_id": "wti_front", "value": 70 + i, "source": "yf", "unit": "usd"}
        for i, d in enumerate(dates)
    ] + [
        {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 5.0, "source": "calc", "unit": "pct"},
        {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": 8.0, "source": "calc", "unit": "pct"},
    ])


@pytest.fixture
def contango_data():
    """Price data with negative momentum (contango signal)."""
    dates = pd.date_range("2024-01-01", periods=25, freq="D")
    return pd.DataFrame([
        {"timestamp": d, "series_id": "wti_front", "value": 80 - i, "source": "yf", "unit": "usd"}
        for i, d in enumerate(dates)
    ] + [
        {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": -4.0, "source": "calc", "unit": "pct"},
        {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": -6.0, "source": "calc", "unit": "pct"},
    ])


@pytest.fixture
def flat_data():
    """Price data with minimal momentum (flat signal)."""
    dates = pd.date_range("2024-01-01", periods=25, freq="D")
    return pd.DataFrame([
        {"timestamp": d, "series_id": "wti_front", "value": 75, "source": "yf", "unit": "usd"}
        for i, d in enumerate(dates)
    ] + [
        {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 0.5, "source": "calc", "unit": "pct"},
        {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": -0.3, "source": "calc", "unit": "pct"},
    ])


class TestCurveShapeDetection:
    """Test curve shape classification."""

    def test_detect_backwardation(self, analyzer, backwardation_data):
        signal = analyzer.analyze(backwardation_data)
        assert signal.curve_shape == CurveShape.BACKWARDATION

    def test_detect_contango(self, analyzer, contango_data):
        signal = analyzer.analyze(contango_data)
        assert signal.curve_shape == CurveShape.CONTANGO

    def test_detect_flat(self, analyzer, flat_data):
        signal = analyzer.analyze(flat_data)
        assert signal.curve_shape == CurveShape.FLAT

    def test_custom_threshold(self, flat_data):
        """With lower threshold, same data should show directional signal."""
        analyzer = TermStructureAnalyzer(momentum_threshold=0.3)
        signal = analyzer.analyze(flat_data)
        # 0.5% momentum > 0.3% threshold → backwardation
        assert signal.curve_shape == CurveShape.BACKWARDATION


class TestIntensity:
    """Test intensity calculation."""

    def test_intensity_in_range(self, analyzer, backwardation_data):
        signal = analyzer.analyze(backwardation_data)
        assert 0 <= signal.intensity <= 100

    def test_strong_momentum_high_intensity(self, analyzer):
        """Strong momentum should produce high intensity."""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        data = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 10.0, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": 12.0, "source": "calc", "unit": "pct"},
        ])
        signal = analyzer.analyze(data)
        assert signal.intensity >= 50

    def test_weak_momentum_low_intensity(self, analyzer):
        """Weak momentum should produce lower intensity."""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        data = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 2.5, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": 2.0, "source": "calc", "unit": "pct"},
        ])
        signal = analyzer.analyze(data)
        assert signal.intensity < 50


class TestRollYield:
    """Test roll yield estimation."""

    def test_backwardation_positive_roll(self, analyzer, backwardation_data):
        """Backwardation should have positive roll yield."""
        signal = analyzer.analyze(backwardation_data)
        assert signal.roll_yield_proxy > 0

    def test_contango_negative_roll(self, analyzer, contango_data):
        """Contango should have negative roll yield."""
        signal = analyzer.analyze(contango_data)
        assert signal.roll_yield_proxy < 0

    def test_flat_near_zero_roll(self, analyzer, flat_data):
        """Flat market should have near-zero roll yield."""
        signal = analyzer.analyze(flat_data)
        assert abs(signal.roll_yield_proxy) < 5  # Within 5%


class TestRollYieldMetrics:
    """Test detailed roll yield calculation."""

    def test_metrics_calculated(self, analyzer, backwardation_data):
        metrics = analyzer.calculate_roll_yield(backwardation_data)

        assert isinstance(metrics, RollYieldMetrics)
        assert metrics.monthly_yield != 0
        assert metrics.quarterly_yield != 0
        assert metrics.annual_yield != 0

    def test_yield_trend_improving(self, analyzer):
        """Higher short-term momentum = improving yield."""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        data = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 5.0, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": 3.0, "source": "calc", "unit": "pct"},
        ])
        metrics = analyzer.calculate_roll_yield(data)
        assert metrics.yield_trend == "IMPROVING"

    def test_yield_trend_deteriorating(self, analyzer):
        """Lower short-term momentum = deteriorating yield."""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        data = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 2.0, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": 4.0, "source": "calc", "unit": "pct"},
        ])
        metrics = analyzer.calculate_roll_yield(data)
        assert metrics.yield_trend == "DETERIORATING"

    def test_yield_trend_stable(self, analyzer):
        """Similar momentum = stable yield."""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        data = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 3.2, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": 3.0, "source": "calc", "unit": "pct"},
        ])
        metrics = analyzer.calculate_roll_yield(data)
        assert metrics.yield_trend == "STABLE"


class TestConfidence:
    """Test confidence calculation."""

    def test_confidence_in_range(self, analyzer, backwardation_data):
        signal = analyzer.analyze(backwardation_data)
        assert 0 <= signal.confidence <= 1

    def test_agreement_increases_confidence(self, analyzer):
        """Same direction momentum should increase confidence."""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")

        # Same direction (both positive)
        data_same = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 5.0, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": 4.0, "source": "calc", "unit": "pct"},
        ])

        # Different direction
        data_diff = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 5.0, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": -2.0, "source": "calc", "unit": "pct"},
        ])

        signal_same = analyzer.analyze(data_same)
        signal_diff = analyzer.analyze(data_diff)

        assert signal_same.confidence > signal_diff.confidence

    def test_eia_data_increases_confidence(self, analyzer, backwardation_data):
        """Having EIA data should increase confidence."""
        # Without EIA
        signal_no_eia = analyzer.analyze(backwardation_data)

        # With EIA (mock inventory data)
        eia_data = pd.DataFrame([
            {"timestamp": datetime(2024, 1, 20), "series_id": "crude_stocks", "value": 420.0, "source": "eia", "unit": "mb"},
            {"timestamp": datetime(2024, 1, 25), "series_id": "crude_stocks", "value": 418.0, "source": "eia", "unit": "mb"},
        ])
        signal_with_eia = analyzer.analyze(backwardation_data, eia_data)

        assert signal_with_eia.confidence > signal_no_eia.confidence


class TestSignalDataclass:
    """Test TermStructureSignal dataclass."""

    def test_signal_has_all_fields(self, analyzer, backwardation_data):
        signal = analyzer.analyze(backwardation_data)

        assert hasattr(signal, "timestamp")
        assert hasattr(signal, "curve_shape")
        assert hasattr(signal, "intensity")
        assert hasattr(signal, "roll_yield_proxy")
        assert hasattr(signal, "momentum_5d")
        assert hasattr(signal, "momentum_20d")
        assert hasattr(signal, "confidence")

    def test_signal_values_populated(self, analyzer, backwardation_data):
        signal = analyzer.analyze(backwardation_data)

        assert signal.timestamp is not None
        assert signal.curve_shape is not None
        assert signal.momentum_5d == 5.0
        assert signal.momentum_20d == 8.0


class TestEmptyData:
    """Test handling of empty/missing data."""

    def test_empty_dataframe(self, analyzer):
        signal = analyzer.analyze(pd.DataFrame())
        assert signal.curve_shape == CurveShape.FLAT
        assert signal.momentum_5d == 0.0
        assert signal.momentum_20d == 0.0

    def test_missing_momentum_series(self, analyzer):
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        data = pd.DataFrame([
            {"timestamp": d, "series_id": "wti_front", "value": 75, "source": "yf", "unit": "usd"}
            for d in dates
        ])
        signal = analyzer.analyze(data)
        # Should default to FLAT when no momentum data
        assert signal.curve_shape == CurveShape.FLAT

    def test_nan_momentum_values(self, analyzer):
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        data = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": np.nan, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": np.nan, "source": "calc", "unit": "pct"},
        ])
        signal = analyzer.analyze(data)
        assert signal.curve_shape == CurveShape.FLAT


class TestBatchClassification:
    """Test batch classification."""

    def test_classify_batch_returns_dataframe(self, analyzer, backwardation_data):
        result = analyzer.classify_batch(backwardation_data, lookback_days=5)
        assert isinstance(result, pd.DataFrame)

    def test_classify_batch_has_columns(self, analyzer, backwardation_data):
        result = analyzer.classify_batch(backwardation_data, lookback_days=5)

        if not result.empty:
            assert "timestamp" in result.columns
            assert "curve_shape" in result.columns
            assert "intensity" in result.columns
            assert "roll_yield_proxy" in result.columns

    def test_classify_batch_empty_data(self, analyzer):
        result = analyzer.classify_batch(pd.DataFrame())
        assert result.empty


class TestEIACorrelation:
    """Test EIA inventory correlation."""

    def test_inventory_build_weakens_backwardation(self, analyzer):
        """Inventory build should weaken backwardation signal."""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        price_data = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 5.0, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": 4.0, "source": "calc", "unit": "pct"},
        ])

        # Inventory build (increasing stocks)
        eia_build = pd.DataFrame([
            {"timestamp": dates[-2], "series_id": "crude_stocks", "value": 420.0, "source": "eia", "unit": "mb"},
            {"timestamp": dates[-1], "series_id": "crude_stocks", "value": 425.0, "source": "eia", "unit": "mb"},
        ])

        signal_no_eia = analyzer.analyze(price_data)
        signal_with_eia = analyzer.analyze(price_data, eia_build)

        # Build should reduce intensity of backwardation
        assert signal_with_eia.intensity < signal_no_eia.intensity

    def test_inventory_draw_weakens_contango(self, analyzer):
        """Inventory draw should weaken contango signal."""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        price_data = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": -5.0, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": -4.0, "source": "calc", "unit": "pct"},
        ])

        # Inventory draw (decreasing stocks)
        eia_draw = pd.DataFrame([
            {"timestamp": dates[-2], "series_id": "crude_stocks", "value": 420.0, "source": "eia", "unit": "mb"},
            {"timestamp": dates[-1], "series_id": "crude_stocks", "value": 415.0, "source": "eia", "unit": "mb"},
        ])

        signal_no_eia = analyzer.analyze(price_data)
        signal_with_eia = analyzer.analyze(price_data, eia_draw)

        # Draw should reduce intensity of contango
        assert signal_with_eia.intensity < signal_no_eia.intensity

    def test_disable_eia_correlation(self):
        """Should be able to disable EIA correlation."""
        analyzer = TermStructureAnalyzer(use_eia_correlation=False)

        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        price_data = pd.DataFrame([
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_5d", "value": 5.0, "source": "calc", "unit": "pct"},
            {"timestamp": dates[-1], "series_id": "wti_front_momentum_20d", "value": 4.0, "source": "calc", "unit": "pct"},
        ])

        eia_build = pd.DataFrame([
            {"timestamp": dates[-2], "series_id": "crude_stocks", "value": 420.0, "source": "eia", "unit": "mb"},
            {"timestamp": dates[-1], "series_id": "crude_stocks", "value": 425.0, "source": "eia", "unit": "mb"},
        ])

        signal_no_eia = analyzer.analyze(price_data)
        signal_with_eia = analyzer.analyze(price_data, eia_build)

        # With correlation disabled, EIA data should not affect intensity
        assert signal_no_eia.intensity == signal_with_eia.intensity
