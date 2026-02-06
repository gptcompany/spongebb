"""Tests for regime attribution analysis."""

import numpy as np
import pandas as pd
import pytest

from liquidity.backtesting.attribution.regime_attribution import (
    RegimeAttributionAnalyzer,
    RegimePerformance,
    TransitionAnalysis,
)


class TestRegimeAttributionAnalyzer:
    """Test regime attribution analyzer."""

    @pytest.fixture
    def sample_data(self) -> tuple[pd.Series, pd.Series]:
        """Create sample returns and regimes."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")

        # Returns with regime-dependent characteristics
        returns = []
        regimes = []
        for i in range(500):
            if i < 200:
                # Expansion: positive drift
                returns.append(np.random.normal(0.001, 0.012))
                regimes.append("EXPANSION")
            elif i < 350:
                # Contraction: negative drift, higher vol
                returns.append(np.random.normal(-0.0005, 0.018))
                regimes.append("CONTRACTION")
            else:
                # Back to expansion
                returns.append(np.random.normal(0.0008, 0.010))
                regimes.append("EXPANSION")

        return (
            pd.Series(returns, index=dates, name="returns"),
            pd.Series(regimes, index=dates, name="regime"),
        )

    def test_compute_regime_performance(self, sample_data):
        """Should compute performance for each regime."""
        returns, regimes = sample_data
        analyzer = RegimeAttributionAnalyzer()

        perf = analyzer.compute_regime_performance(returns, regimes)

        assert "EXPANSION" in perf
        assert "CONTRACTION" in perf
        assert isinstance(perf["EXPANSION"], RegimePerformance)

    def test_expansion_outperforms_contraction(self, sample_data):
        """Expansion should have better returns (by construction)."""
        returns, regimes = sample_data
        analyzer = RegimeAttributionAnalyzer()

        perf = analyzer.compute_regime_performance(returns, regimes)

        # Expansion has positive drift, contraction negative
        assert perf["EXPANSION"].avg_daily_return > perf["CONTRACTION"].avg_daily_return

    def test_contraction_higher_volatility(self, sample_data):
        """Contraction should have higher volatility (by construction)."""
        returns, regimes = sample_data
        analyzer = RegimeAttributionAnalyzer()

        perf = analyzer.compute_regime_performance(returns, regimes)

        # Contraction has 1.8% vol vs expansion 1.2%
        assert perf["CONTRACTION"].volatility > perf["EXPANSION"].volatility

    def test_analyze_transitions(self, sample_data):
        """Should detect and analyze transitions."""
        returns, regimes = sample_data
        analyzer = RegimeAttributionAnalyzer(transition_window=5)

        transitions = analyzer.analyze_transitions(returns, regimes)

        assert len(transitions) > 0
        # Should have expansion_to_contraction and vice versa
        trans_types = [t.transition_type for t in transitions]
        assert "EXPANSION_to_CONTRACTION" in trans_types

    def test_compute_regime_durations(self, sample_data):
        """Should compute duration statistics."""
        _returns, regimes = sample_data
        analyzer = RegimeAttributionAnalyzer()

        durations = analyzer.compute_regime_durations(regimes)

        assert "EXPANSION" in durations.index
        assert "CONTRACTION" in durations.index
        assert "avg_duration" in durations.columns

    def test_generate_attribution_report(self, sample_data):
        """Should generate complete report."""
        returns, regimes = sample_data
        analyzer = RegimeAttributionAnalyzer()

        report = analyzer.generate_attribution_report(returns, regimes)

        assert "regime_performance" in report
        assert "transitions" in report
        assert "durations" in report
        assert "contributions" in report
        assert "total_return" in report

    def test_to_dataframe(self, sample_data):
        """Should convert to DataFrame."""
        returns, regimes = sample_data
        analyzer = RegimeAttributionAnalyzer()

        perf = analyzer.compute_regime_performance(returns, regimes)
        df = analyzer.to_dataframe(perf)

        assert isinstance(df, pd.DataFrame)
        assert "Sharpe" in df.columns
        assert len(df) == 2  # EXPANSION and CONTRACTION


class TestRegimePerformance:
    """Test RegimePerformance dataclass."""

    def test_fields_exist(self):
        """Verify all fields exist."""
        perf = RegimePerformance(
            regime="EXPANSION",
            n_periods=200,
            pct_time=40.0,
            total_return=15.0,
            annualized_return=18.0,
            avg_daily_return=0.05,
            volatility=12.0,
            max_drawdown=-8.0,
            avg_drawdown=-3.0,
            sharpe_ratio=1.2,
            sortino_ratio=1.8,
            win_rate=55.0,
            profit_factor=1.6,
            avg_win=0.8,
            avg_loss=-0.5,
        )

        assert perf.regime == "EXPANSION"
        assert perf.sharpe_ratio == 1.2


class TestTransitionAnalysis:
    """Test TransitionAnalysis dataclass."""

    def test_fields_exist(self):
        """Verify all fields exist."""
        trans = TransitionAnalysis(
            transition_type="EXPANSION_to_CONTRACTION",
            n_transitions=5,
            pre_return=2.0,
            pre_volatility=10.0,
            post_return=-1.5,
            post_volatility=15.0,
            transition_alpha=-3.5,
            transition_signal_value=0.8,
            avg_duration_from=45.0,
            avg_duration_to=30.0,
        )

        assert trans.transition_type == "EXPANSION_to_CONTRACTION"
        assert trans.transition_alpha == -3.5
