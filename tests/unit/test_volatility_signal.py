"""Unit tests for composite Volatility Signal calculator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from liquidity.calculators.move_zscore import MOVESignal, MOVEZScoreResult
from liquidity.calculators.vix_term_structure import TermStructure, VIXTermStructureResult
from liquidity.calculators.volatility_signal import (
    REGIME_RISK_OFF,
    REGIME_RISK_ON,
    WEIGHT_MOVE_ZSCORE,
    WEIGHT_VIX_LEVEL,
    WEIGHT_VIX_TERM,
    VolatilityRegime,
    VolatilitySignalCalculator,
    VolatilitySignalResult,
    _score_move_zscore,
    _score_vix_level,
    _score_vix_term,
    classify_regime,
)


class TestVolatilityRegime:
    """Tests for VolatilityRegime enum."""

    def test_enum_values(self):
        assert VolatilityRegime.RISK_ON.value == "RISK_ON"
        assert VolatilityRegime.NEUTRAL.value == "NEUTRAL"
        assert VolatilityRegime.RISK_OFF.value == "RISK_OFF"


class TestClassifyRegime:
    """Tests for regime classification."""

    def test_risk_on(self):
        assert classify_regime(50.0) == VolatilityRegime.RISK_ON

    def test_neutral(self):
        assert classify_regime(0.0) == VolatilityRegime.NEUTRAL

    def test_risk_off(self):
        assert classify_regime(-50.0) == VolatilityRegime.RISK_OFF

    def test_boundary_risk_on(self):
        assert classify_regime(30.01) == VolatilityRegime.RISK_ON
        assert classify_regime(30.0) == VolatilityRegime.NEUTRAL

    def test_boundary_risk_off(self):
        assert classify_regime(-30.01) == VolatilityRegime.RISK_OFF
        assert classify_regime(-30.0) == VolatilityRegime.NEUTRAL


class TestWeights:
    """Tests for component weights."""

    def test_weights_sum_to_one(self):
        total = WEIGHT_MOVE_ZSCORE + WEIGHT_VIX_TERM + WEIGHT_VIX_LEVEL
        assert total == pytest.approx(1.0)


class TestScoreMoveZscore:
    """Tests for MOVE Z-Score scoring function."""

    def _make_result(self, signal: MOVESignal, zscore: float = 0.0) -> MOVEZScoreResult:
        return MOVEZScoreResult(
            timestamp=datetime.now(UTC),
            current_move=100.0,
            mean_move=100.0,
            std_move=10.0,
            zscore=zscore,
            percentile=50.0,
            signal=signal,
        )

    def test_extreme_low_is_positive(self):
        """EXTREME_LOW MOVE = calm bonds = positive score."""
        score = _score_move_zscore(self._make_result(MOVESignal.EXTREME_LOW, -2.5))
        assert score > 50

    def test_extreme_high_is_negative(self):
        """EXTREME_HIGH MOVE = bond stress = negative score."""
        score = _score_move_zscore(self._make_result(MOVESignal.EXTREME_HIGH, 2.5))
        assert score < -50

    def test_normal_is_near_zero(self):
        score = _score_move_zscore(self._make_result(MOVESignal.NORMAL, 0.0))
        assert -25 <= score <= 25

    def test_score_bounded(self):
        """Score should be within [-100, 100]."""
        for signal in MOVESignal:
            for z in [-5, -2, 0, 2, 5]:
                score = _score_move_zscore(self._make_result(signal, z))
                assert -100 <= score <= 100


class TestScoreVixTerm:
    """Tests for VIX term structure scoring function."""

    def _make_result(self, structure: TermStructure, ratio: float) -> VIXTermStructureResult:
        return VIXTermStructureResult(
            timestamp=datetime.now(UTC),
            vix=20.0,
            vix3m=20.0 / ratio if ratio else 20.0,
            ratio=ratio,
            structure=structure,
            spread=0.0,
        )

    def test_contango_is_positive(self):
        score = _score_vix_term(self._make_result(TermStructure.CONTANGO, 0.85))
        assert score > 50

    def test_backwardation_is_negative(self):
        score = _score_vix_term(self._make_result(TermStructure.BACKWARDATION, 1.15))
        assert score < -50

    def test_flat_is_near_zero(self):
        score = _score_vix_term(self._make_result(TermStructure.FLAT, 1.0))
        assert -30 <= score <= 30


class TestScoreVixLevel:
    """Tests for VIX level scoring function."""

    def test_low_vix_positive(self):
        """VIX < 15 = calm = positive score."""
        assert _score_vix_level(12.0) == 100.0

    def test_moderate_vix(self):
        """VIX 15-20 = normal = moderate positive."""
        score = _score_vix_level(17.5)
        assert 0 < score < 100

    def test_high_vix_negative(self):
        """VIX 25-30 = stress = negative."""
        score = _score_vix_level(27.5)
        assert score < -50

    def test_extreme_vix_max_negative(self):
        """VIX > 30 = extreme stress."""
        assert _score_vix_level(40.0) == -100.0


class TestVolatilitySignalResult:
    """Tests for VolatilitySignalResult dataclass."""

    def test_dataclass_creation(self):
        move = MOVEZScoreResult(
            timestamp=datetime.now(UTC),
            current_move=100.0, mean_move=95.0, std_move=8.0,
            zscore=0.625, percentile=60.0, signal=MOVESignal.NORMAL,
        )
        vix = VIXTermStructureResult(
            timestamp=datetime.now(UTC),
            vix=18.0, vix3m=20.0, ratio=0.9,
            structure=TermStructure.FLAT, spread=-2.0,
        )
        result = VolatilitySignalResult(
            timestamp=datetime.now(UTC),
            composite_score=25.0,
            regime=VolatilityRegime.NEUTRAL,
            move_zscore=move,
            vix_term=vix,
            move_component=10.0,
            term_component=10.0,
            level_component=5.0,
        )
        assert result.composite_score == 25.0
        assert result.regime == VolatilityRegime.NEUTRAL


class TestVolatilitySignalCalculator:
    """Tests for VolatilitySignalCalculator."""

    @pytest.fixture()
    def calculator(self):
        return VolatilitySignalCalculator()

    @pytest.fixture()
    def mock_move_result(self):
        return MOVEZScoreResult(
            timestamp=datetime.now(UTC),
            current_move=100.0,
            mean_move=95.0,
            std_move=8.0,
            zscore=0.625,
            percentile=60.0,
            signal=MOVESignal.NORMAL,
        )

    @pytest.fixture()
    def mock_vix_result(self):
        return VIXTermStructureResult(
            timestamp=datetime.now(UTC),
            vix=18.0,
            vix3m=20.0,
            ratio=0.90,
            structure=TermStructure.FLAT,
            spread=-2.0,
        )

    @pytest.mark.asyncio()
    async def test_get_current(self, calculator, mock_move_result, mock_vix_result):
        with (
            patch.object(calculator._move_calc, "get_current", new_callable=AsyncMock) as mock_move,
            patch.object(calculator._vix_calc, "get_current", new_callable=AsyncMock) as mock_vix,
        ):
            mock_move.return_value = mock_move_result
            mock_vix.return_value = mock_vix_result

            result = await calculator.get_current()

            assert isinstance(result, VolatilitySignalResult)
            assert isinstance(result.regime, VolatilityRegime)
            assert -100 <= result.composite_score <= 100
            assert result.move_zscore is mock_move_result
            assert result.vix_term is mock_vix_result

    @pytest.mark.asyncio()
    async def test_risk_on_scenario(self, calculator):
        """Low MOVE + contango + low VIX = RISK_ON."""
        move = MOVEZScoreResult(
            timestamp=datetime.now(UTC),
            current_move=80.0, mean_move=100.0, std_move=10.0,
            zscore=-2.0, percentile=5.0, signal=MOVESignal.EXTREME_LOW,
        )
        vix = VIXTermStructureResult(
            timestamp=datetime.now(UTC),
            vix=12.0, vix3m=18.0, ratio=0.667,
            structure=TermStructure.CONTANGO, spread=-6.0,
        )
        with (
            patch.object(calculator._move_calc, "get_current", new_callable=AsyncMock, return_value=move),
            patch.object(calculator._vix_calc, "get_current", new_callable=AsyncMock, return_value=vix),
        ):
            result = await calculator.get_current()
            assert result.regime == VolatilityRegime.RISK_ON
            assert result.composite_score > REGIME_RISK_ON

    @pytest.mark.asyncio()
    async def test_risk_off_scenario(self, calculator):
        """High MOVE + backwardation + high VIX = RISK_OFF."""
        move = MOVEZScoreResult(
            timestamp=datetime.now(UTC),
            current_move=150.0, mean_move=100.0, std_move=10.0,
            zscore=5.0, percentile=99.0, signal=MOVESignal.EXTREME_HIGH,
        )
        vix = VIXTermStructureResult(
            timestamp=datetime.now(UTC),
            vix=35.0, vix3m=25.0, ratio=1.4,
            structure=TermStructure.BACKWARDATION, spread=10.0,
        )
        with (
            patch.object(calculator._move_calc, "get_current", new_callable=AsyncMock, return_value=move),
            patch.object(calculator._vix_calc, "get_current", new_callable=AsyncMock, return_value=vix),
        ):
            result = await calculator.get_current()
            assert result.regime == VolatilityRegime.RISK_OFF
            assert result.composite_score < REGIME_RISK_OFF
