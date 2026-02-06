"""Tests for Monte Carlo simulation."""

import numpy as np
import pandas as pd
import pytest

from liquidity.backtesting.monte_carlo.simulation import (
    MonteCarloResult,
    MonteCarloSimulator,
)


class TestMonteCarloSimulator:
    """Test Monte Carlo simulator."""

    @pytest.fixture
    def sample_trade_returns(self) -> np.ndarray:
        """Create sample trade returns."""
        np.random.seed(42)
        return np.random.normal(0.005, 0.02, 200)

    @pytest.fixture
    def sample_returns_series(self) -> pd.Series:
        """Create sample daily returns."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        return pd.Series(np.random.normal(0.0003, 0.015, 500), index=dates)

    @pytest.fixture
    def sample_regimes(self, sample_returns_series: pd.Series) -> pd.Series:
        """Create sample regime series."""
        # Alternating regimes
        regimes = pd.Series(
            ["EXPANSION"] * 250 + ["CONTRACTION"] * 250,
            index=sample_returns_series.index,
        )
        return regimes

    def test_shuffle_simulation_runs(self, sample_trade_returns: np.ndarray) -> None:
        """Shuffle simulation should complete."""
        sim = MonteCarloSimulator(n_simulations=100, random_seed=42)
        result = sim.run_shuffle_simulation(sample_trade_returns)

        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations > 0

    def test_result_distributions_populated(
        self, sample_trade_returns: np.ndarray
    ) -> None:
        """Result should have distribution arrays."""
        sim = MonteCarloSimulator(n_simulations=100, random_seed=42)
        result = sim.run_shuffle_simulation(sample_trade_returns)

        assert len(result.drawdown_dist) > 0
        assert len(result.equity_dist) > 0
        assert len(result.return_dist) > 0

    def test_percentiles_ordered_correctly(
        self, sample_trade_returns: np.ndarray
    ) -> None:
        """5th percentile should be < median < 95th."""
        sim = MonteCarloSimulator(n_simulations=1000, random_seed=42)
        result = sim.run_shuffle_simulation(sample_trade_returns)

        # For returns (higher is better)
        assert result.total_return_5th <= result.total_return_median
        assert result.total_return_median <= result.total_return_95th

        # For drawdowns (more negative is worse), 5th is worst
        assert result.max_drawdown_5th <= result.max_drawdown_median

    def test_skip_rate_reduces_trades(self, sample_trade_returns: np.ndarray) -> None:
        """Higher skip rate should affect results."""
        sim_low = MonteCarloSimulator(n_simulations=100, skip_rate=0.0, random_seed=42)
        sim_high = MonteCarloSimulator(
            n_simulations=100, skip_rate=0.5, random_seed=42
        )

        result_low = sim_low.run_shuffle_simulation(sample_trade_returns)
        result_high = sim_high.run_shuffle_simulation(sample_trade_returns)

        # Distributions should differ
        assert not np.allclose(result_low.return_dist, result_high.return_dist)

    def test_regime_bootstrap(
        self, sample_returns_series: pd.Series, sample_regimes: pd.Series
    ) -> None:
        """Regime bootstrap should complete."""
        sim = MonteCarloSimulator(n_simulations=100, random_seed=42)
        result = sim.run_regime_bootstrap(sample_returns_series, sample_regimes)

        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations > 0

    def test_block_bootstrap(self, sample_returns_series: pd.Series) -> None:
        """Block bootstrap should complete."""
        sim = MonteCarloSimulator(n_simulations=100, random_seed=42)
        result = sim.run_block_bootstrap(sample_returns_series, block_size=20)

        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations > 0

    def test_prob_positive_return(self, sample_trade_returns: np.ndarray) -> None:
        """Probability of positive return should be 0-100."""
        sim = MonteCarloSimulator(n_simulations=100, random_seed=42)
        result = sim.run_shuffle_simulation(sample_trade_returns)

        assert 0 <= result.prob_positive_return <= 100

    def test_validate_backtest_normal(self, sample_trade_returns: np.ndarray) -> None:
        """Validation should pass for reasonable results."""
        sim = MonteCarloSimulator(n_simulations=1000, random_seed=42)
        mc_result = sim.run_shuffle_simulation(sample_trade_returns)

        # Use median as "actual" - should be ~50th percentile
        actual = {
            "total_return": mc_result.total_return_median,
            "max_drawdown": mc_result.max_drawdown_median,
            "sharpe": mc_result.sharpe_median,
        }

        validation = sim.validate_backtest(actual, mc_result)

        # Median should be around 50th percentile
        assert 20 < validation["return_percentile"] < 80
        assert not validation["is_suspicious"]

    def test_validate_backtest_suspicious(
        self, sample_trade_returns: np.ndarray
    ) -> None:
        """Validation should flag unrealistic results."""
        sim = MonteCarloSimulator(n_simulations=1000, random_seed=42)
        mc_result = sim.run_shuffle_simulation(sample_trade_returns)

        # Suspiciously good results
        actual = {
            "total_return": mc_result.total_return_95th * 2,  # Way above 95th
            "max_drawdown": 0,  # No drawdown
            "sharpe": 5.0,  # Unrealistic Sharpe
        }

        validation = sim.validate_backtest(actual, mc_result)

        assert validation["is_suspicious"]
        assert len(validation["warnings"]) > 0


class TestMonteCarloResult:
    """Test MonteCarloResult dataclass."""

    def test_result_fields(self) -> None:
        """Verify result has all required fields."""
        result = MonteCarloResult(
            n_simulations=1000,
            max_drawdown_5th=-30.0,
            max_drawdown_median=-15.0,
            max_drawdown_95th=-5.0,
            final_equity_5th=80000,
            final_equity_median=120000,
            final_equity_95th=180000,
            total_return_5th=-20.0,
            total_return_median=20.0,
            total_return_95th=80.0,
            sharpe_5th=0.2,
            sharpe_median=0.8,
            sharpe_95th=1.5,
            prob_positive_return=75.0,
        )

        assert result.n_simulations == 1000
        assert result.prob_positive_return == 75.0
