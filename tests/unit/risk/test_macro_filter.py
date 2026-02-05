"""Tests for NautilusTrader Macro Filter."""

import pytest

from liquidity.risk.macro_filter import (
    AdaptiveRiskManager,
    FilterResult,
    LiquidityRiskFilter,
    TradingDecision,
)
from liquidity.risk.regime_var import RegimeType


class TestTradingDecision:
    """Test TradingDecision enum."""

    def test_enum_values(self) -> None:
        """Enum should have correct values."""
        assert TradingDecision.ALLOW.value == "ALLOW"
        assert TradingDecision.REDUCE.value == "REDUCE"
        assert TradingDecision.BLOCK.value == "BLOCK"


class TestLiquidityRiskFilter:
    """Test macro filter decisions."""

    @pytest.fixture
    def filter(self) -> LiquidityRiskFilter:
        """Default filter instance."""
        return LiquidityRiskFilter()

    def test_expansion_allows_trading(self, filter: LiquidityRiskFilter) -> None:
        """Expansion regime should allow trading."""
        result = filter.evaluate(RegimeType.EXPANSION, var_level=0.02)

        assert result.decision == TradingDecision.ALLOW
        assert result.position_multiplier >= 1.0
        assert "EXPANSION" in result.reason

    def test_neutral_allows_trading(self, filter: LiquidityRiskFilter) -> None:
        """Neutral regime should allow trading."""
        result = filter.evaluate(RegimeType.NEUTRAL, var_level=0.02)

        assert result.decision == TradingDecision.ALLOW
        assert result.position_multiplier == 1.0

    def test_contraction_reduces_position(self, filter: LiquidityRiskFilter) -> None:
        """Contraction should reduce position size."""
        result = filter.evaluate(RegimeType.CONTRACTION, var_level=0.02)

        assert result.decision == TradingDecision.REDUCE
        assert result.position_multiplier < 1.0
        assert "CONTRACTION" in result.reason

    def test_high_var_blocks_trading(self, filter: LiquidityRiskFilter) -> None:
        """High VaR should block trading."""
        result = filter.evaluate(RegimeType.NEUTRAL, var_level=0.10)

        assert result.decision == TradingDecision.BLOCK
        assert result.position_multiplier == 0.0
        assert "exceeds block" in result.reason

    def test_moderate_var_reduces(self, filter: LiquidityRiskFilter) -> None:
        """Moderate VaR should reduce position."""
        result = filter.evaluate(RegimeType.NEUTRAL, var_level=0.04)

        assert result.decision == TradingDecision.REDUCE
        assert 0 < result.position_multiplier < 1.0

    def test_should_trade_shortcut(self, filter: LiquidityRiskFilter) -> None:
        """should_trade should return boolean."""
        assert filter.should_trade(RegimeType.EXPANSION, 0.02) is True
        assert filter.should_trade(RegimeType.NEUTRAL, 0.10) is False

    def test_risk_score_range(self, filter: LiquidityRiskFilter) -> None:
        """Risk score should be 0-100."""
        result = filter.evaluate(RegimeType.CONTRACTION, var_level=0.05)

        assert 0 <= result.risk_score <= 100

    def test_risk_score_increases_with_risk(self, filter: LiquidityRiskFilter) -> None:
        """Risk score should increase with regime risk and VaR."""
        expansion_result = filter.evaluate(RegimeType.EXPANSION, var_level=0.01)
        contraction_result = filter.evaluate(RegimeType.CONTRACTION, var_level=0.04)

        assert contraction_result.risk_score > expansion_result.risk_score

    def test_get_position_multiplier(self, filter: LiquidityRiskFilter) -> None:
        """Position multiplier should vary by regime."""
        assert filter.get_position_multiplier(RegimeType.EXPANSION) == 1.2
        assert filter.get_position_multiplier(RegimeType.NEUTRAL) == 1.0
        assert filter.get_position_multiplier(RegimeType.CONTRACTION) == 0.5

    def test_filter_result_dataclass(self) -> None:
        """FilterResult should be a proper dataclass."""
        result = FilterResult(
            decision=TradingDecision.ALLOW,
            position_multiplier=1.0,
            regime=RegimeType.NEUTRAL,
            var_level=0.02,
            risk_score=35.0,
            reason="Test reason",
        )
        assert result.decision == TradingDecision.ALLOW
        assert result.reason == "Test reason"

    def test_custom_thresholds(self) -> None:
        """Custom thresholds should work."""
        strict_filter = LiquidityRiskFilter(
            var_threshold_reduce=0.01,
            var_threshold_block=0.02,
        )

        result = strict_filter.evaluate(RegimeType.NEUTRAL, var_level=0.015)
        assert result.decision == TradingDecision.REDUCE

        result = strict_filter.evaluate(RegimeType.NEUTRAL, var_level=0.025)
        assert result.decision == TradingDecision.BLOCK

    def test_contraction_with_high_var_more_severe(
        self, filter: LiquidityRiskFilter
    ) -> None:
        """Contraction + high VaR should have specific handling."""
        result = filter.evaluate(RegimeType.CONTRACTION, var_level=0.04)

        assert result.decision == TradingDecision.REDUCE
        assert result.position_multiplier == filter.contraction_reduce_factor


class TestAdaptiveRiskManager:
    """Test adaptive risk manager."""

    @pytest.fixture
    def manager(self) -> AdaptiveRiskManager:
        """Default manager instance."""
        return AdaptiveRiskManager()

    def test_expansion_higher_risk(self, manager: AdaptiveRiskManager) -> None:
        """Expansion should allow higher risk per trade."""
        expansion_risk = manager.get_risk_per_trade(
            RegimeType.EXPANSION, var_level=0.02
        )
        contraction_risk = manager.get_risk_per_trade(
            RegimeType.CONTRACTION, var_level=0.02
        )

        assert expansion_risk >= contraction_risk

    def test_risk_within_bounds(self, manager: AdaptiveRiskManager) -> None:
        """Risk should stay within min/max."""
        # Very low VaR should not exceed max
        risk = manager.get_risk_per_trade(
            RegimeType.EXPANSION, var_level=0.001
        )
        assert manager.min_risk_pct <= risk <= manager.max_risk_pct

        # Very high VaR should not go below min
        risk = manager.get_risk_per_trade(
            RegimeType.CONTRACTION, var_level=0.10
        )
        assert manager.min_risk_pct <= risk <= manager.max_risk_pct

    def test_risk_with_zero_var(self, manager: AdaptiveRiskManager) -> None:
        """Zero VaR should not cause division error."""
        risk = manager.get_risk_per_trade(RegimeType.NEUTRAL, var_level=0.0)
        assert risk == manager.base_risk_pct

    def test_stop_loss_expansion_wider(self, manager: AdaptiveRiskManager) -> None:
        """Expansion should have wider stops."""
        exp_stop = manager.get_stop_loss(RegimeType.EXPANSION, var_level=0.02)
        con_stop = manager.get_stop_loss(RegimeType.CONTRACTION, var_level=0.02)

        assert exp_stop > con_stop

    def test_stop_loss_high_vol_wider(self, manager: AdaptiveRiskManager) -> None:
        """High volatility should have wider stops."""
        low_vol_stop = manager.get_stop_loss(RegimeType.NEUTRAL, var_level=0.01)
        high_vol_stop = manager.get_stop_loss(RegimeType.NEUTRAL, var_level=0.04)

        assert high_vol_stop > low_vol_stop

    def test_custom_base_risk(self) -> None:
        """Custom base risk should work."""
        custom_manager = AdaptiveRiskManager(
            base_risk_pct=0.01,
            max_risk_pct=0.02,
            min_risk_pct=0.001,
        )

        risk = custom_manager.get_risk_per_trade(RegimeType.NEUTRAL, var_level=0.02)
        assert custom_manager.min_risk_pct <= risk <= custom_manager.max_risk_pct
