"""Unit tests for MOVE Z-Score calculator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from liquidity.calculators.move_zscore import (
    MIN_DATA_THRESHOLD,
    SIGNAL_THRESHOLDS,
    ZSCORE_WINDOW,
    MOVESignal,
    MOVEZScoreCalculator,
    MOVEZScoreResult,
    classify_signal,
)


class TestMOVESignal:
    """Tests for MOVESignal enum."""

    def test_signal_values(self):
        assert MOVESignal.EXTREME_HIGH.value == "EXTREME_HIGH"
        assert MOVESignal.HIGH.value == "HIGH"
        assert MOVESignal.NORMAL.value == "NORMAL"
        assert MOVESignal.LOW.value == "LOW"
        assert MOVESignal.EXTREME_LOW.value == "EXTREME_LOW"

    def test_all_signals_are_string_enum(self):
        for signal in MOVESignal:
            assert isinstance(signal.value, str)


class TestClassifySignal:
    """Tests for Z-Score signal classification."""

    def test_extreme_high(self):
        assert classify_signal(2.5) == MOVESignal.EXTREME_HIGH

    def test_high(self):
        assert classify_signal(1.5) == MOVESignal.HIGH

    def test_normal_positive(self):
        assert classify_signal(0.5) == MOVESignal.NORMAL

    def test_normal_zero(self):
        assert classify_signal(0.0) == MOVESignal.NORMAL

    def test_normal_negative(self):
        assert classify_signal(-0.5) == MOVESignal.NORMAL

    def test_low(self):
        assert classify_signal(-1.5) == MOVESignal.LOW

    def test_extreme_low(self):
        assert classify_signal(-2.5) == MOVESignal.EXTREME_LOW

    def test_boundary_high(self):
        """Z > 1.0 is HIGH."""
        assert classify_signal(1.01) == MOVESignal.HIGH

    def test_boundary_extreme_high(self):
        """Z > 2.0 is EXTREME_HIGH."""
        assert classify_signal(2.01) == MOVESignal.EXTREME_HIGH

    def test_boundary_low(self):
        """Z < -1.0 is LOW."""
        assert classify_signal(-1.01) == MOVESignal.LOW

    def test_boundary_normal_upper(self):
        """Z == 1.0 is NORMAL."""
        assert classify_signal(1.0) == MOVESignal.NORMAL

    def test_boundary_normal_lower(self):
        """Z == -1.0 is NORMAL."""
        assert classify_signal(-1.0) == MOVESignal.NORMAL


class TestMOVEZScoreResult:
    """Tests for MOVEZScoreResult dataclass."""

    def test_dataclass_creation(self):
        result = MOVEZScoreResult(
            timestamp=datetime.now(UTC),
            current_move=110.5,
            mean_move=100.0,
            std_move=10.0,
            zscore=1.05,
            percentile=75.0,
            signal=MOVESignal.HIGH,
        )
        assert result.current_move == 110.5
        assert result.zscore == 1.05
        assert result.signal == MOVESignal.HIGH


class TestConstants:
    """Tests for module constants."""

    def test_zscore_window(self):
        assert ZSCORE_WINDOW == 20

    def test_min_data_threshold(self):
        assert MIN_DATA_THRESHOLD == 0.30

    def test_signal_thresholds(self):
        assert SIGNAL_THRESHOLDS["extreme_high"] == 2.0
        assert SIGNAL_THRESHOLDS["high"] == 1.0
        assert SIGNAL_THRESHOLDS["low"] == -1.0
        assert SIGNAL_THRESHOLDS["extreme_low"] == -2.0


class TestMOVEZScoreCalculator:
    """Tests for MOVEZScoreCalculator."""

    @pytest.fixture()
    def calculator(self):
        return MOVEZScoreCalculator()

    @pytest.fixture()
    def sample_move_data(self):
        """Create sample MOVE data for testing."""
        dates = pd.date_range("2026-01-01", periods=40, freq="B")
        # Generate realistic MOVE data (mean ~100, std ~10)
        np.random.seed(42)
        values = np.random.normal(100, 10, len(dates))
        return pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": "^MOVE",
                "source": "yahoo",
                "value": values,
                "unit": "index",
            }
        )

    def test_init_defaults(self, calculator):
        assert calculator._window == ZSCORE_WINDOW
        assert calculator._min_threshold == MIN_DATA_THRESHOLD

    def test_init_custom_window(self):
        calc = MOVEZScoreCalculator(window=10, min_threshold=0.5)
        assert calc._window == 10
        assert calc._min_threshold == 0.5

    @pytest.mark.asyncio()
    async def test_calculate_returns_dataframe(self, calculator, sample_move_data):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = sample_move_data
            df = await calculator.calculate()

            assert not df.empty
            assert "move" in df.columns
            assert "zscore" in df.columns
            assert "signal" in df.columns
            assert "percentile" in df.columns
            assert "mean" in df.columns
            assert "std" in df.columns

    @pytest.mark.asyncio()
    async def test_calculate_zscore_values(self, calculator, sample_move_data):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = sample_move_data
            df = await calculator.calculate()

            # Z-scores should be roughly standard normal
            assert df["zscore"].mean() == pytest.approx(0, abs=1.0)
            # All signals should be valid
            valid_signals = {s.value for s in MOVESignal}
            assert set(df["signal"].unique()).issubset(valid_signals)

    @pytest.mark.asyncio()
    async def test_calculate_empty_data(self, calculator):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = pd.DataFrame(
                columns=["timestamp", "symbol", "source", "value", "unit"]
            )
            df = await calculator.calculate()
            assert df.empty

    @pytest.mark.asyncio()
    async def test_get_current(self, calculator, sample_move_data):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = sample_move_data
            result = await calculator.get_current()

            assert isinstance(result, MOVEZScoreResult)
            assert isinstance(result.signal, MOVESignal)
            assert 0 <= result.percentile <= 100
            assert result.std_move > 0

    @pytest.mark.asyncio()
    async def test_get_current_empty_raises(self, calculator):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = pd.DataFrame(
                columns=["timestamp", "symbol", "source", "value", "unit"]
            )
            with pytest.raises(ValueError, match="No MOVE data"):
                await calculator.get_current()

    @pytest.mark.asyncio()
    async def test_percentile_bounds(self, calculator, sample_move_data):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = sample_move_data
            df = await calculator.calculate()

            assert df["percentile"].min() >= 0
            assert df["percentile"].max() <= 100
