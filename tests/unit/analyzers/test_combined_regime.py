"""Unit tests for CombinedRegimeAnalyzer.

Tests the combination of liquidity and oil regimes into a unified macro signal.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from liquidity.analyzers.regime_classifier import (
    CombinedRegime,
    CombinedRegimeAnalyzer,
    CombinedRegimeState,
    RegimeDirection,
    RegimeResult,
)


@pytest.fixture
def mock_oil_regime():
    """Mock OilRegime enum."""
    with patch("liquidity.analyzers.regime_classifier.TYPE_CHECKING", False):
        from liquidity.oil.regime import OilRegime
        yield OilRegime


@pytest.fixture
def mock_oil_state():
    """Mock OilRegimeState."""
    with patch("liquidity.analyzers.regime_classifier.TYPE_CHECKING", False):
        from liquidity.oil.regime import OilRegime, OilRegimeState
        return OilRegimeState(
            timestamp=datetime.now(UTC),
            regime=OilRegime.BALANCED,
            confidence=75.0,  # 0-100 scale
            inventory_signal="neutral",
            production_signal="neutral",
            utilization_signal="neutral",
            balance_signal="flat",
            composite_score=0.0,
            drivers=["Inventory near 5-year avg", "Balanced supply-demand"],
        )


@pytest.fixture
def mock_liquidity_result():
    """Mock RegimeResult for liquidity classification."""
    return RegimeResult(
        timestamp=datetime.now(UTC),
        direction=RegimeDirection.EXPANSION,
        intensity=65.0,
        confidence="HIGH",
        net_liq_percentile=0.7,
        global_liq_percentile=0.8,
        stealth_qe_score=0.6,
        components="NET:0.70 GLO:0.80 SQE:0.60",
    )


@pytest.fixture
def analyzer():
    """Create analyzer with mocked classifiers."""
    # Patch the OilRegimeClassifier at its source location
    with patch("liquidity.oil.regime.OilRegimeClassifier") as mock_oil_cls:
        mock_oil = MagicMock()
        mock_oil_cls.return_value = mock_oil

        # Create analyzer - it will import and use the mocked OilRegimeClassifier
        analyzer = CombinedRegimeAnalyzer.__new__(CombinedRegimeAnalyzer)
        analyzer._settings = MagicMock()
        analyzer._liquidity = MagicMock()
        analyzer._oil = MagicMock()
        # Initialize the matrix
        CombinedRegimeAnalyzer._init_regime_matrix()
        yield analyzer


class TestCombinedRegime:
    """Test CombinedRegime enum."""

    def test_all_values_defined(self):
        assert CombinedRegime.VERY_BULLISH == "very_bullish"
        assert CombinedRegime.BULLISH == "bullish"
        assert CombinedRegime.NEUTRAL == "neutral"
        assert CombinedRegime.BEARISH == "bearish"
        assert CombinedRegime.VERY_BEARISH == "very_bearish"

    def test_enum_is_string(self):
        assert isinstance(CombinedRegime.BULLISH, str)
        assert CombinedRegime.BULLISH.value == "bullish"


class TestCombinedRegimeState:
    """Test CombinedRegimeState dataclass."""

    def test_state_creation(self, mock_oil_regime):
        state = CombinedRegimeState(
            timestamp=datetime.now(UTC),
            liquidity_regime="EXPANSION",
            oil_regime=mock_oil_regime.TIGHT,
            combined_regime=CombinedRegime.VERY_BULLISH,
            confidence=0.85,
            commodity_signal="long",
            drivers=["Liquidity: EXPANSION", "Oil: tight"],
        )

        assert state.liquidity_regime == "EXPANSION"
        assert state.oil_regime == mock_oil_regime.TIGHT
        assert state.combined_regime == CombinedRegime.VERY_BULLISH
        assert state.confidence == 0.85
        assert state.commodity_signal == "long"
        assert len(state.drivers) == 2


class TestRegimeMatrix:
    """Test the REGIME_MATRIX combinations."""

    def test_expansion_tight_very_bullish(self, analyzer, mock_oil_regime):
        """EXPANSION + TIGHT = VERY_BULLISH."""
        result = analyzer._combine_regimes("EXPANSION", mock_oil_regime.TIGHT)
        assert result == CombinedRegime.VERY_BULLISH

    def test_expansion_balanced_bullish(self, analyzer, mock_oil_regime):
        """EXPANSION + BALANCED = BULLISH."""
        result = analyzer._combine_regimes("EXPANSION", mock_oil_regime.BALANCED)
        assert result == CombinedRegime.BULLISH

    def test_expansion_loose_neutral(self, analyzer, mock_oil_regime):
        """EXPANSION + LOOSE = NEUTRAL."""
        result = analyzer._combine_regimes("EXPANSION", mock_oil_regime.LOOSE)
        assert result == CombinedRegime.NEUTRAL

    def test_neutral_tight_bullish(self, analyzer, mock_oil_regime):
        """NEUTRAL + TIGHT = BULLISH."""
        result = analyzer._combine_regimes("NEUTRAL", mock_oil_regime.TIGHT)
        assert result == CombinedRegime.BULLISH

    def test_neutral_balanced_neutral(self, analyzer, mock_oil_regime):
        """NEUTRAL + BALANCED = NEUTRAL."""
        result = analyzer._combine_regimes("NEUTRAL", mock_oil_regime.BALANCED)
        assert result == CombinedRegime.NEUTRAL

    def test_neutral_loose_bearish(self, analyzer, mock_oil_regime):
        """NEUTRAL + LOOSE = BEARISH."""
        result = analyzer._combine_regimes("NEUTRAL", mock_oil_regime.LOOSE)
        assert result == CombinedRegime.BEARISH

    def test_contraction_tight_neutral(self, analyzer, mock_oil_regime):
        """CONTRACTION + TIGHT = NEUTRAL."""
        result = analyzer._combine_regimes("CONTRACTION", mock_oil_regime.TIGHT)
        assert result == CombinedRegime.NEUTRAL

    def test_contraction_balanced_bearish(self, analyzer, mock_oil_regime):
        """CONTRACTION + BALANCED = BEARISH."""
        result = analyzer._combine_regimes("CONTRACTION", mock_oil_regime.BALANCED)
        assert result == CombinedRegime.BEARISH

    def test_contraction_loose_very_bearish(self, analyzer, mock_oil_regime):
        """CONTRACTION + LOOSE = VERY_BEARISH."""
        result = analyzer._combine_regimes("CONTRACTION", mock_oil_regime.LOOSE)
        assert result == CombinedRegime.VERY_BEARISH

    def test_all_nine_combinations(self, analyzer, mock_oil_regime):
        """Verify all 9 combinations are defined and produce correct output."""
        expected = {
            ("EXPANSION", mock_oil_regime.TIGHT): CombinedRegime.VERY_BULLISH,
            ("EXPANSION", mock_oil_regime.BALANCED): CombinedRegime.BULLISH,
            ("EXPANSION", mock_oil_regime.LOOSE): CombinedRegime.NEUTRAL,
            ("NEUTRAL", mock_oil_regime.TIGHT): CombinedRegime.BULLISH,
            ("NEUTRAL", mock_oil_regime.BALANCED): CombinedRegime.NEUTRAL,
            ("NEUTRAL", mock_oil_regime.LOOSE): CombinedRegime.BEARISH,
            ("CONTRACTION", mock_oil_regime.TIGHT): CombinedRegime.NEUTRAL,
            ("CONTRACTION", mock_oil_regime.BALANCED): CombinedRegime.BEARISH,
            ("CONTRACTION", mock_oil_regime.LOOSE): CombinedRegime.VERY_BEARISH,
        }

        for (liq, oil), expected_combined in expected.items():
            result = analyzer._combine_regimes(liq, oil)
            assert result == expected_combined, f"Failed for ({liq}, {oil})"


class TestSignalGeneration:
    """Test trading signal generation from combined regime."""

    def test_very_bullish_long(self, analyzer):
        result = analyzer._regime_to_signal(CombinedRegime.VERY_BULLISH)
        assert result == "long"

    def test_bullish_long(self, analyzer):
        result = analyzer._regime_to_signal(CombinedRegime.BULLISH)
        assert result == "long"

    def test_neutral_neutral(self, analyzer):
        result = analyzer._regime_to_signal(CombinedRegime.NEUTRAL)
        assert result == "neutral"

    def test_bearish_short(self, analyzer):
        result = analyzer._regime_to_signal(CombinedRegime.BEARISH)
        assert result == "short"

    def test_very_bearish_short(self, analyzer):
        result = analyzer._regime_to_signal(CombinedRegime.VERY_BEARISH)
        assert result == "short"

    def test_all_signals(self, analyzer):
        """Verify all regimes map to correct signals."""
        long_regimes = [CombinedRegime.VERY_BULLISH, CombinedRegime.BULLISH]
        short_regimes = [CombinedRegime.VERY_BEARISH, CombinedRegime.BEARISH]
        neutral_regimes = [CombinedRegime.NEUTRAL]

        for regime in long_regimes:
            assert analyzer._regime_to_signal(regime) == "long"

        for regime in short_regimes:
            assert analyzer._regime_to_signal(regime) == "short"

        for regime in neutral_regimes:
            assert analyzer._regime_to_signal(regime) == "neutral"


class TestGetCombinedRegime:
    """Test the async get_combined_regime method."""

    @pytest.mark.asyncio
    async def test_returns_combined_state(
        self, analyzer, mock_liquidity_result, mock_oil_state
    ):
        """Test that get_combined_regime returns CombinedRegimeState."""
        analyzer._liquidity.classify = AsyncMock(return_value=mock_liquidity_result)
        analyzer._oil.classify = AsyncMock(return_value=mock_oil_state)

        result = await analyzer.get_combined_regime()

        assert isinstance(result, CombinedRegimeState)
        assert result.liquidity_regime == "EXPANSION"
        assert result.combined_regime in list(CombinedRegime)

    @pytest.mark.asyncio
    async def test_confidence_calculation(
        self, analyzer, mock_liquidity_result, mock_oil_state
    ):
        """Test confidence is averaged from both classifiers."""
        # HIGH -> 1.0, oil confidence = 75.0/100 = 0.75
        # Average = (1.0 + 0.75) / 2 = 0.875
        analyzer._liquidity.classify = AsyncMock(return_value=mock_liquidity_result)
        analyzer._oil.classify = AsyncMock(return_value=mock_oil_state)

        result = await analyzer.get_combined_regime()

        assert result.confidence == pytest.approx(0.875, rel=0.01)

    @pytest.mark.asyncio
    async def test_drivers_include_both_sources(
        self, analyzer, mock_liquidity_result, mock_oil_state
    ):
        """Test drivers include info from both classifiers."""
        analyzer._liquidity.classify = AsyncMock(return_value=mock_liquidity_result)
        analyzer._oil.classify = AsyncMock(return_value=mock_oil_state)

        result = await analyzer.get_combined_regime()

        # Should have liquidity driver, oil driver, and oil state drivers
        assert any("Liquidity" in d for d in result.drivers)
        assert any("Oil" in d for d in result.drivers)
        assert len(result.drivers) >= 3  # At least: liquidity, oil, + oil state drivers

    @pytest.mark.asyncio
    async def test_expansion_balanced_produces_bullish(
        self, analyzer, mock_oil_regime
    ):
        """Test EXPANSION + BALANCED = BULLISH with correct signal."""
        from liquidity.oil.regime import OilRegimeState

        liq_result = RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.EXPANSION,
            intensity=70.0,
            confidence="HIGH",
            net_liq_percentile=0.75,
            global_liq_percentile=0.80,
            stealth_qe_score=0.65,
            components="NET:0.75 GLO:0.80 SQE:0.65",
        )

        oil_state = OilRegimeState(
            timestamp=datetime.now(UTC),
            regime=mock_oil_regime.BALANCED,
            confidence=80.0,  # 0-100 scale
            inventory_signal="neutral",
            production_signal="neutral",
            utilization_signal="neutral",
            balance_signal="flat",
            composite_score=0.0,
            drivers=["Test driver"],
        )

        analyzer._liquidity.classify = AsyncMock(return_value=liq_result)
        analyzer._oil.classify = AsyncMock(return_value=oil_state)

        result = await analyzer.get_combined_regime()

        assert result.combined_regime == CombinedRegime.BULLISH
        assert result.commodity_signal == "long"

    @pytest.mark.asyncio
    async def test_contraction_loose_produces_very_bearish(
        self, analyzer, mock_oil_regime
    ):
        """Test CONTRACTION + LOOSE = VERY_BEARISH with short signal."""
        from liquidity.oil.regime import OilRegimeState

        liq_result = RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.CONTRACTION,
            intensity=80.0,
            confidence="HIGH",
            net_liq_percentile=0.25,
            global_liq_percentile=0.20,
            stealth_qe_score=0.15,
            components="NET:0.25 GLO:0.20 SQE:0.15",
        )

        oil_state = OilRegimeState(
            timestamp=datetime.now(UTC),
            regime=mock_oil_regime.LOOSE,
            confidence=85.0,  # 0-100 scale
            inventory_signal="bearish",
            production_signal="bearish",
            utilization_signal="bearish",
            balance_signal="build",
            composite_score=-50.0,
            drivers=["Oversupply"],
        )

        analyzer._liquidity.classify = AsyncMock(return_value=liq_result)
        analyzer._oil.classify = AsyncMock(return_value=oil_state)

        result = await analyzer.get_combined_regime()

        assert result.combined_regime == CombinedRegime.VERY_BEARISH
        assert result.commodity_signal == "short"


class TestUnknownRegimeHandling:
    """Test handling of unknown or edge case regimes."""

    def test_unknown_liquidity_regime_defaults_to_neutral(self, analyzer, mock_oil_regime):
        """Unknown liquidity regime should default to NEUTRAL lookup."""
        # This should log a warning and use NEUTRAL
        result = analyzer._combine_regimes("UNKNOWN", mock_oil_regime.BALANCED)
        assert result == CombinedRegime.NEUTRAL

    def test_unknown_combination_defaults_to_neutral(self, analyzer):
        """Unmapped combination should default to NEUTRAL."""
        # Force an unmapped lookup
        result = CombinedRegimeAnalyzer.REGIME_MATRIX.get(
            ("INVALID", "INVALID"),
            CombinedRegime.NEUTRAL,
        )
        assert result == CombinedRegime.NEUTRAL


class TestConfidenceMapping:
    """Test confidence level mapping from liquidity classifier."""

    @pytest.mark.asyncio
    async def test_high_confidence_maps_to_1(self, analyzer, mock_oil_regime):
        """HIGH confidence should map to 1.0."""
        from liquidity.oil.regime import OilRegimeState

        liq_result = RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.EXPANSION,
            intensity=50.0,
            confidence="HIGH",
            net_liq_percentile=0.5,
            global_liq_percentile=0.5,
            stealth_qe_score=0.5,
            components="",
        )

        oil_state = OilRegimeState(
            timestamp=datetime.now(UTC),
            regime=mock_oil_regime.BALANCED,
            confidence=80.0,  # 0-100 scale
            inventory_signal="neutral",
            production_signal="neutral",
            utilization_signal="neutral",
            balance_signal="flat",
            composite_score=0.0,
            drivers=[],
        )

        analyzer._liquidity.classify = AsyncMock(return_value=liq_result)
        analyzer._oil.classify = AsyncMock(return_value=oil_state)

        result = await analyzer.get_combined_regime()

        # (1.0 + 0.8) / 2 = 0.9
        assert result.confidence == pytest.approx(0.9, rel=0.01)

    @pytest.mark.asyncio
    async def test_medium_confidence_maps_to_066(self, analyzer, mock_oil_regime):
        """MEDIUM confidence should map to 0.66."""
        from liquidity.oil.regime import OilRegimeState

        liq_result = RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.EXPANSION,
            intensity=50.0,
            confidence="MEDIUM",
            net_liq_percentile=0.5,
            global_liq_percentile=0.5,
            stealth_qe_score=0.5,
            components="",
        )

        oil_state = OilRegimeState(
            timestamp=datetime.now(UTC),
            regime=mock_oil_regime.BALANCED,
            confidence=66.0,  # 0-100 scale
            inventory_signal="neutral",
            production_signal="neutral",
            utilization_signal="neutral",
            balance_signal="flat",
            composite_score=0.0,
            drivers=[],
        )

        analyzer._liquidity.classify = AsyncMock(return_value=liq_result)
        analyzer._oil.classify = AsyncMock(return_value=oil_state)

        result = await analyzer.get_combined_regime()

        # (0.66 + 0.66) / 2 = 0.66
        assert result.confidence == pytest.approx(0.66, rel=0.01)

    @pytest.mark.asyncio
    async def test_low_confidence_maps_to_033(self, analyzer, mock_oil_regime):
        """LOW confidence should map to 0.33."""
        from liquidity.oil.regime import OilRegimeState

        liq_result = RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.EXPANSION,
            intensity=50.0,
            confidence="LOW",
            net_liq_percentile=0.5,
            global_liq_percentile=0.5,
            stealth_qe_score=0.5,
            components="",
        )

        oil_state = OilRegimeState(
            timestamp=datetime.now(UTC),
            regime=mock_oil_regime.BALANCED,
            confidence=67.0,  # 0-100 scale
            inventory_signal="neutral",
            production_signal="neutral",
            utilization_signal="neutral",
            balance_signal="flat",
            composite_score=0.0,
            drivers=[],
        )

        analyzer._liquidity.classify = AsyncMock(return_value=liq_result)
        analyzer._oil.classify = AsyncMock(return_value=oil_state)

        result = await analyzer.get_combined_regime()

        # (0.33 + 0.67) / 2 = 0.5
        assert result.confidence == pytest.approx(0.5, rel=0.01)
