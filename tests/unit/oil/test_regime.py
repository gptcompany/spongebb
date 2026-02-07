"""Unit tests for oil regime classifier.

Tests OilRegimeClassifier, OilRegime enum, and OilRegimeState dataclass.
Run with: uv run pytest tests/unit/oil/test_regime.py -v
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from liquidity.oil.regime import (
    OilRegime,
    OilRegimeClassifier,
    OilRegimeState,
)


class TestOilRegimeEnum:
    """Tests for OilRegime enum."""

    def test_regime_tight_value(self) -> None:
        """Test TIGHT regime value."""
        assert OilRegime.TIGHT.value == "tight"

    def test_regime_balanced_value(self) -> None:
        """Test BALANCED regime value."""
        assert OilRegime.BALANCED.value == "balanced"

    def test_regime_loose_value(self) -> None:
        """Test LOOSE regime value."""
        assert OilRegime.LOOSE.value == "loose"

    def test_regime_enum_members(self) -> None:
        """Test all regime enum members exist."""
        members = [m.value for m in OilRegime]
        assert "tight" in members
        assert "balanced" in members
        assert "loose" in members
        assert len(members) == 3


class TestOilRegimeState:
    """Tests for OilRegimeState dataclass."""

    def test_regime_state_fields(self) -> None:
        """Test OilRegimeState has all required fields."""
        state = OilRegimeState(
            timestamp=datetime(2026, 2, 7, 10, 0, 0),
            regime=OilRegime.TIGHT,
            confidence=75.0,
            inventory_signal="bullish",
            production_signal="neutral",
            utilization_signal="bullish",
            balance_signal="draw",
            composite_score=45.0,
            drivers=["Inventory below 5-year average"],
        )

        assert state.timestamp == datetime(2026, 2, 7, 10, 0, 0)
        assert state.regime == OilRegime.TIGHT
        assert state.confidence == 75.0
        assert state.inventory_signal == "bullish"
        assert state.production_signal == "neutral"
        assert state.utilization_signal == "bullish"
        assert state.balance_signal == "draw"
        assert state.composite_score == 45.0
        assert state.drivers == ["Inventory below 5-year average"]

    def test_regime_state_empty_drivers(self) -> None:
        """Test OilRegimeState with empty drivers list."""
        state = OilRegimeState(
            timestamp=datetime(2026, 2, 7),
            regime=OilRegime.BALANCED,
            confidence=15.0,
            inventory_signal="neutral",
            production_signal="neutral",
            utilization_signal="neutral",
            balance_signal="flat",
            composite_score=5.0,
            drivers=[],
        )

        assert state.drivers == []
        assert state.regime == OilRegime.BALANCED


class TestOilRegimeClassifierConstants:
    """Tests for OilRegimeClassifier constants."""

    def test_inventory_thresholds(self) -> None:
        """Test inventory threshold values."""
        assert OilRegimeClassifier.INVENTORY_BULLISH_THRESHOLD == -5
        assert OilRegimeClassifier.INVENTORY_BEARISH_THRESHOLD == 5

    def test_utilization_thresholds(self) -> None:
        """Test utilization threshold values."""
        assert OilRegimeClassifier.UTILIZATION_TIGHT == 93
        assert OilRegimeClassifier.UTILIZATION_LOOSE == 88

    def test_regime_classification_thresholds(self) -> None:
        """Test regime classification thresholds."""
        assert OilRegimeClassifier.REGIME_TIGHT_THRESHOLD == 30
        assert OilRegimeClassifier.REGIME_LOOSE_THRESHOLD == -30

    def test_signal_threshold(self) -> None:
        """Test signal classification threshold."""
        assert OilRegimeClassifier.SIGNAL_THRESHOLD == 20


class TestInventoryScoring:
    """Tests for _score_inventory method."""

    @pytest.fixture
    def classifier(self) -> OilRegimeClassifier:
        """Create a classifier instance."""
        return OilRegimeClassifier()

    def test_inventory_scoring_below_average(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test inventory below 5yr avg = bullish (positive score)."""
        # 5% below avg = bullish (+50)
        score = classifier._score_inventory(-5)
        assert score == 50

        # 10% below avg = bullish (+100, clamped)
        score = classifier._score_inventory(-10)
        assert score == 100

    def test_inventory_scoring_above_average(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test inventory above 5yr avg = bearish (negative score)."""
        # 5% above avg = bearish (-50)
        score = classifier._score_inventory(5)
        assert score == -50

        # 10% above avg = bearish (-100, clamped)
        score = classifier._score_inventory(10)
        assert score == -100

    def test_inventory_scoring_at_average(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test inventory at 5yr avg = neutral (0 score)."""
        score = classifier._score_inventory(0)
        assert score == 0

    def test_inventory_scoring_extreme_values(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test inventory scoring clamps at +/- 100."""
        # Extreme below average: clamped at +100
        score = classifier._score_inventory(-15)
        assert score == 100

        # Extreme above average: clamped at -100
        score = classifier._score_inventory(15)
        assert score == -100

    def test_inventory_scoring_fractional(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test inventory scoring with fractional percentages."""
        # 2.5% below = +25
        score = classifier._score_inventory(-2.5)
        assert score == 25

        # 7.5% above = -75
        score = classifier._score_inventory(7.5)
        assert score == -75


class TestBalanceScoring:
    """Tests for _score_balance method."""

    @pytest.fixture
    def classifier(self) -> OilRegimeClassifier:
        """Create a classifier instance."""
        return OilRegimeClassifier()

    def test_balance_scoring_draw(self, classifier: OilRegimeClassifier) -> None:
        """Test negative balance (draw) = bullish (positive score)."""
        # 500 kb/d draw = +50
        score = classifier._score_balance(-500)
        assert score == 50

        # 1000 kb/d draw = +100 (clamped)
        score = classifier._score_balance(-1000)
        assert score == 100

    def test_balance_scoring_build(self, classifier: OilRegimeClassifier) -> None:
        """Test positive balance (build) = bearish (negative score)."""
        # 500 kb/d build = -50
        score = classifier._score_balance(500)
        assert score == -50

        # 1000 kb/d build = -100 (clamped)
        score = classifier._score_balance(1000)
        assert score == -100

    def test_balance_scoring_flat(self, classifier: OilRegimeClassifier) -> None:
        """Test zero balance = neutral (0 score)."""
        score = classifier._score_balance(0)
        assert score == 0

    def test_balance_scoring_extreme_values(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test balance scoring clamps at +/- 100."""
        # Extreme draw: clamped at +100
        score = classifier._score_balance(-2000)
        assert score == 100

        # Extreme build: clamped at -100
        score = classifier._score_balance(2000)
        assert score == -100


class TestUtilizationScoring:
    """Tests for _score_utilization method."""

    @pytest.fixture
    def classifier(self) -> OilRegimeClassifier:
        """Create a classifier instance."""
        return OilRegimeClassifier()

    def test_utilization_scoring_high(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test high utilization = bullish (positive score)."""
        # 95% utilization (midpoint = 90.5, diff = 4.5)
        # score = 4.5 * 20 = 90
        score = classifier._score_utilization(95)
        assert abs(score - 90) < 0.1

    def test_utilization_scoring_low(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test low utilization = bearish (negative score)."""
        # 85% utilization (midpoint = 90.5, diff = -5.5)
        # score = -5.5 * 20 = -110 -> clamped to -100
        score = classifier._score_utilization(85)
        assert score == -100

    def test_utilization_scoring_midpoint(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test utilization at midpoint = neutral (0 score)."""
        # Midpoint = (93 + 88) / 2 = 90.5
        score = classifier._score_utilization(90.5)
        assert abs(score) < 0.1

    def test_utilization_scoring_at_thresholds(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test utilization at TIGHT and LOOSE thresholds."""
        # At TIGHT threshold (93%): 93 - 90.5 = 2.5, score = 50
        score = classifier._score_utilization(93)
        assert abs(score - 50) < 0.1

        # At LOOSE threshold (88%): 88 - 90.5 = -2.5, score = -50
        score = classifier._score_utilization(88)
        assert abs(score - (-50)) < 0.1


class TestRegimeClassification:
    """Tests for _classify_regime method."""

    @pytest.fixture
    def classifier(self) -> OilRegimeClassifier:
        """Create a classifier instance."""
        return OilRegimeClassifier()

    def test_regime_classification_tight(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test composite > 30 = TIGHT regime."""
        assert classifier._classify_regime(50) == OilRegime.TIGHT
        assert classifier._classify_regime(31) == OilRegime.TIGHT
        assert classifier._classify_regime(100) == OilRegime.TIGHT

    def test_regime_classification_loose(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test composite < -30 = LOOSE regime."""
        assert classifier._classify_regime(-50) == OilRegime.LOOSE
        assert classifier._classify_regime(-31) == OilRegime.LOOSE
        assert classifier._classify_regime(-100) == OilRegime.LOOSE

    def test_regime_classification_balanced(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test -30 <= composite <= 30 = BALANCED regime."""
        assert classifier._classify_regime(0) == OilRegime.BALANCED
        assert classifier._classify_regime(15) == OilRegime.BALANCED
        assert classifier._classify_regime(-15) == OilRegime.BALANCED
        assert classifier._classify_regime(30) == OilRegime.BALANCED
        assert classifier._classify_regime(-30) == OilRegime.BALANCED


class TestConfidenceCalculation:
    """Tests for _calculate_confidence method."""

    @pytest.fixture
    def classifier(self) -> OilRegimeClassifier:
        """Create a classifier instance."""
        return OilRegimeClassifier()

    def test_confidence_high_positive(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test high positive score = high confidence."""
        assert classifier._calculate_confidence(80) == 80
        assert classifier._calculate_confidence(100) == 100

    def test_confidence_high_negative(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test high negative score = high confidence."""
        assert classifier._calculate_confidence(-80) == 80
        assert classifier._calculate_confidence(-100) == 100

    def test_confidence_low_score(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test low score = low confidence."""
        assert classifier._calculate_confidence(10) == 10
        assert classifier._calculate_confidence(-10) == 10

    def test_confidence_zero_score(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test zero score = zero confidence."""
        assert classifier._calculate_confidence(0) == 0

    def test_confidence_capped_at_100(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test confidence is capped at 100."""
        assert classifier._calculate_confidence(150) == 100
        assert classifier._calculate_confidence(-150) == 100


class TestScoreToSignal:
    """Tests for _score_to_signal method."""

    @pytest.fixture
    def classifier(self) -> OilRegimeClassifier:
        """Create a classifier instance."""
        return OilRegimeClassifier()

    def test_score_to_signal_bullish(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test score > 20 = 'bullish'."""
        assert classifier._score_to_signal(50) == "bullish"
        assert classifier._score_to_signal(21) == "bullish"
        assert classifier._score_to_signal(100) == "bullish"

    def test_score_to_signal_bearish(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test score < -20 = 'bearish'."""
        assert classifier._score_to_signal(-50) == "bearish"
        assert classifier._score_to_signal(-21) == "bearish"
        assert classifier._score_to_signal(-100) == "bearish"

    def test_score_to_signal_neutral(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test -20 <= score <= 20 = 'neutral'."""
        assert classifier._score_to_signal(0) == "neutral"
        assert classifier._score_to_signal(10) == "neutral"
        assert classifier._score_to_signal(-10) == "neutral"
        assert classifier._score_to_signal(20) == "neutral"
        assert classifier._score_to_signal(-20) == "neutral"


class TestIdentifyDrivers:
    """Tests for _identify_drivers method."""

    @pytest.fixture
    def classifier(self) -> OilRegimeClassifier:
        """Create a classifier instance."""
        return OilRegimeClassifier()

    def test_identify_drivers_inventory_below(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test driver identification for inventory below average."""
        drivers = classifier._identify_drivers(50, 0, 0)
        assert len(drivers) == 1
        assert "Inventory below 5-year average" in drivers[0]

    def test_identify_drivers_inventory_above(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test driver identification for inventory above average."""
        drivers = classifier._identify_drivers(-50, 0, 0)
        assert len(drivers) == 1
        assert "Inventory above 5-year average" in drivers[0]

    def test_identify_drivers_weekly_draws(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test driver identification for weekly draws."""
        drivers = classifier._identify_drivers(0, 50, 0)
        assert len(drivers) == 1
        assert "Weekly draws" in drivers[0]

    def test_identify_drivers_weekly_builds(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test driver identification for weekly builds."""
        drivers = classifier._identify_drivers(0, -50, 0)
        assert len(drivers) == 1
        assert "Weekly builds" in drivers[0]

    def test_identify_drivers_utilization_high(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test driver identification for high utilization."""
        drivers = classifier._identify_drivers(0, 0, 50)
        assert len(drivers) == 1
        assert "Refinery utilization high" in drivers[0]

    def test_identify_drivers_utilization_low(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test driver identification for low utilization."""
        drivers = classifier._identify_drivers(0, 0, -50)
        assert len(drivers) == 1
        assert "Refinery utilization low" in drivers[0]

    def test_identify_drivers_multiple(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test driver identification with multiple drivers."""
        drivers = classifier._identify_drivers(50, 50, 50)
        assert len(drivers) == 3

    def test_identify_drivers_none(
        self, classifier: OilRegimeClassifier
    ) -> None:
        """Test driver identification with no significant drivers."""
        drivers = classifier._identify_drivers(10, 10, 10)
        assert len(drivers) == 0


class TestClassifierInit:
    """Tests for OilRegimeClassifier initialization."""

    def test_init_default(self) -> None:
        """Test init with default parameters."""
        classifier = OilRegimeClassifier()
        assert classifier._supply_demand is None
        assert classifier._inventory is None
        assert classifier._eia is None

    def test_init_with_dependencies(self) -> None:
        """Test init with injected dependencies."""
        mock_supply_demand = AsyncMock()
        mock_inventory = AsyncMock()
        mock_eia = AsyncMock()

        classifier = OilRegimeClassifier(
            supply_demand=mock_supply_demand,
            inventory=mock_inventory,
            eia=mock_eia,
        )

        assert classifier._supply_demand is mock_supply_demand
        assert classifier._inventory is mock_inventory
        assert classifier._eia is mock_eia


class TestClassify:
    """Tests for classify method."""

    @pytest.fixture
    def mock_supply_demand(self) -> AsyncMock:
        """Create mock SupplyDemandCalculator."""
        mock = AsyncMock()
        mock_balance = MagicMock()
        mock_balance.balance = -500.0  # Draw = bullish
        mock_balance.signal = "draw"
        mock.get_current_balance = AsyncMock(return_value=mock_balance)
        return mock

    @pytest.fixture
    def mock_inventory(self) -> AsyncMock:
        """Create mock InventoryForecaster."""
        mock = AsyncMock()
        mock_analysis = MagicMock()
        mock_analysis.vs_5yr_avg_pct = -5.0  # 5% below average = bullish
        mock.get_current_analysis = AsyncMock(return_value=mock_analysis)
        return mock

    @pytest.fixture
    def mock_eia(self) -> AsyncMock:
        """Create mock EIACollector."""
        import pandas as pd

        mock = AsyncMock()
        mock_df = pd.DataFrame({
            "timestamp": [pd.Timestamp("2026-02-07")],
            "value": [95.0],  # High utilization = bullish
        })
        mock.collect_refinery_utilization = AsyncMock(return_value=mock_df)
        return mock

    @pytest.mark.asyncio
    async def test_classify_returns_regime_state(
        self,
        mock_supply_demand: AsyncMock,
        mock_inventory: AsyncMock,
        mock_eia: AsyncMock,
    ) -> None:
        """Test classify returns OilRegimeState."""
        classifier = OilRegimeClassifier(
            supply_demand=mock_supply_demand,
            inventory=mock_inventory,
            eia=mock_eia,
        )

        result = await classifier.classify()

        assert isinstance(result, OilRegimeState)
        assert isinstance(result.regime, OilRegime)

    @pytest.mark.asyncio
    async def test_classify_tight_regime(
        self,
        mock_supply_demand: AsyncMock,
        mock_inventory: AsyncMock,
        mock_eia: AsyncMock,
    ) -> None:
        """Test classify returns TIGHT regime with bullish indicators."""
        classifier = OilRegimeClassifier(
            supply_demand=mock_supply_demand,
            inventory=mock_inventory,
            eia=mock_eia,
        )

        result = await classifier.classify()

        # All bullish indicators should produce TIGHT regime
        assert result.regime == OilRegime.TIGHT
        assert result.composite_score > 30  # TIGHT threshold

    @pytest.mark.asyncio
    async def test_classify_loose_regime(
        self, mock_eia: AsyncMock
    ) -> None:
        """Test classify returns LOOSE regime with bearish indicators."""
        # Create bearish mocks
        mock_supply_demand = AsyncMock()
        mock_balance = MagicMock()
        mock_balance.balance = 1000.0  # Build = bearish
        mock_balance.signal = "build"
        mock_supply_demand.get_current_balance = AsyncMock(return_value=mock_balance)

        mock_inventory = AsyncMock()
        mock_analysis = MagicMock()
        mock_analysis.vs_5yr_avg_pct = 10.0  # 10% above average = bearish
        mock_inventory.get_current_analysis = AsyncMock(return_value=mock_analysis)

        # Low utilization
        import pandas as pd
        mock_df = pd.DataFrame({
            "timestamp": [pd.Timestamp("2026-02-07")],
            "value": [85.0],  # Low utilization = bearish
        })
        mock_eia.collect_refinery_utilization = AsyncMock(return_value=mock_df)

        classifier = OilRegimeClassifier(
            supply_demand=mock_supply_demand,
            inventory=mock_inventory,
            eia=mock_eia,
        )

        result = await classifier.classify()

        # All bearish indicators should produce LOOSE regime
        assert result.regime == OilRegime.LOOSE
        assert result.composite_score < -30  # LOOSE threshold

    @pytest.mark.asyncio
    async def test_classify_balanced_regime(
        self, mock_eia: AsyncMock
    ) -> None:
        """Test classify returns BALANCED regime with neutral indicators."""
        # Create neutral mocks
        mock_supply_demand = AsyncMock()
        mock_balance = MagicMock()
        mock_balance.balance = 0.0  # Flat
        mock_balance.signal = "flat"
        mock_supply_demand.get_current_balance = AsyncMock(return_value=mock_balance)

        mock_inventory = AsyncMock()
        mock_analysis = MagicMock()
        mock_analysis.vs_5yr_avg_pct = 0.0  # At average
        mock_inventory.get_current_analysis = AsyncMock(return_value=mock_analysis)

        # Midpoint utilization
        import pandas as pd
        mock_df = pd.DataFrame({
            "timestamp": [pd.Timestamp("2026-02-07")],
            "value": [90.5],  # Midpoint utilization
        })
        mock_eia.collect_refinery_utilization = AsyncMock(return_value=mock_df)

        classifier = OilRegimeClassifier(
            supply_demand=mock_supply_demand,
            inventory=mock_inventory,
            eia=mock_eia,
        )

        result = await classifier.classify()

        assert result.regime == OilRegime.BALANCED

    @pytest.mark.asyncio
    async def test_classify_has_timestamp(
        self,
        mock_supply_demand: AsyncMock,
        mock_inventory: AsyncMock,
        mock_eia: AsyncMock,
    ) -> None:
        """Test classify sets timestamp."""
        classifier = OilRegimeClassifier(
            supply_demand=mock_supply_demand,
            inventory=mock_inventory,
            eia=mock_eia,
        )

        result = await classifier.classify()

        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_classify_signals_populated(
        self,
        mock_supply_demand: AsyncMock,
        mock_inventory: AsyncMock,
        mock_eia: AsyncMock,
    ) -> None:
        """Test classify populates all signal fields."""
        classifier = OilRegimeClassifier(
            supply_demand=mock_supply_demand,
            inventory=mock_inventory,
            eia=mock_eia,
        )

        result = await classifier.classify()

        assert result.inventory_signal in ["bullish", "bearish", "neutral"]
        assert result.production_signal in ["bullish", "bearish", "neutral"]
        assert result.utilization_signal in ["bullish", "bearish", "neutral"]
        assert result.balance_signal in ["build", "draw", "flat"]


class TestGetUtilization:
    """Tests for _get_utilization method."""

    @pytest.mark.asyncio
    async def test_get_utilization_returns_value(self) -> None:
        """Test _get_utilization returns utilization value."""
        import pandas as pd

        mock_eia = AsyncMock()
        mock_df = pd.DataFrame({
            "timestamp": [pd.Timestamp("2026-02-07")],
            "value": [92.5],
        })
        mock_eia.collect_refinery_utilization = AsyncMock(return_value=mock_df)

        classifier = OilRegimeClassifier(eia=mock_eia)
        result = await classifier._get_utilization()

        assert result == 92.5

    @pytest.mark.asyncio
    async def test_get_utilization_default_on_empty(self) -> None:
        """Test _get_utilization returns default on empty data."""
        import pandas as pd

        mock_eia = AsyncMock()
        mock_eia.collect_refinery_utilization = AsyncMock(
            return_value=pd.DataFrame()
        )

        classifier = OilRegimeClassifier(eia=mock_eia)
        result = await classifier._get_utilization()

        assert result == 90.0  # Default value

    @pytest.mark.asyncio
    async def test_get_utilization_default_on_error(self) -> None:
        """Test _get_utilization returns default on error."""
        mock_eia = AsyncMock()
        mock_eia.collect_refinery_utilization = AsyncMock(
            side_effect=Exception("API error")
        )

        classifier = OilRegimeClassifier(eia=mock_eia)
        result = await classifier._get_utilization()

        assert result == 90.0  # Default value


class TestClassifierClose:
    """Tests for classifier cleanup."""

    @pytest.mark.asyncio
    async def test_close_releases_dependencies(self) -> None:
        """Test close releases all dependencies."""
        mock_supply_demand = AsyncMock()
        mock_inventory = AsyncMock()
        mock_eia = AsyncMock()

        classifier = OilRegimeClassifier(
            supply_demand=mock_supply_demand,
            inventory=mock_inventory,
            eia=mock_eia,
        )

        await classifier.close()

        mock_supply_demand.close.assert_called_once()
        mock_inventory.close.assert_called_once()
        mock_eia.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_none_dependencies(self) -> None:
        """Test close handles None dependencies gracefully."""
        classifier = OilRegimeClassifier()

        # Should not raise
        await classifier.close()


class TestModuleExports:
    """Tests for module exports in oil/__init__.py."""

    def test_oil_regime_exported(self) -> None:
        """Test OilRegime is exported from oil module."""
        from liquidity.oil import OilRegime as ExportedRegime

        assert ExportedRegime is OilRegime

    def test_oil_regime_classifier_exported(self) -> None:
        """Test OilRegimeClassifier is exported from oil module."""
        from liquidity.oil import OilRegimeClassifier as ExportedClassifier

        assert ExportedClassifier is OilRegimeClassifier

    def test_oil_regime_state_exported(self) -> None:
        """Test OilRegimeState is exported from oil module."""
        from liquidity.oil import OilRegimeState as ExportedState

        assert ExportedState is OilRegimeState


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
