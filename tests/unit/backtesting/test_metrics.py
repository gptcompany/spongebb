"""Tests for performance metrics calculator (pure numpy)."""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from liquidity.backtesting.engine.metrics import (
    MetricsCalculator,
    PerformanceMetrics,
    compare_strategies,
)


class TestMetricsCalculator:
    """Test metrics calculator."""

    @pytest.fixture
    def sample_returns(self) -> pd.Series:
        """Create sample daily returns."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        returns = pd.Series(
            np.random.normal(0.0003, 0.015, 500),
            index=dates,
            name="returns",
        )
        return returns

    @pytest.fixture
    def benchmark_returns(self) -> pd.Series:
        """Create benchmark returns."""
        np.random.seed(123)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")
        return pd.Series(
            np.random.normal(0.0002, 0.012, 500),
            index=dates,
            name="benchmark",
        )

    def test_calculate_returns_metrics(self, sample_returns):
        """Metrics should calculate return values."""
        calc = MetricsCalculator()
        metrics = calc.calculate(sample_returns)

        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_return != 0
        assert metrics.cagr != 0

    def test_sharpe_ratio_reasonable(self, sample_returns):
        """Sharpe ratio should be in reasonable range."""
        calc = MetricsCalculator(risk_free_rate=0.05)
        metrics = calc.calculate(sample_returns)

        assert -2 < metrics.sharpe_ratio < 3

    def test_sortino_ratio_calculated(self, sample_returns):
        """Sortino ratio should be calculated for returns with downside."""
        calc = MetricsCalculator()
        metrics = calc.calculate(sample_returns)

        assert np.isfinite(metrics.sortino_ratio)
        assert metrics.sortino_ratio != metrics.sharpe_ratio

    def test_max_drawdown_negative(self, sample_returns):
        """Max drawdown should be negative."""
        calc = MetricsCalculator()
        metrics = calc.calculate(sample_returns)

        assert metrics.max_drawdown <= 0

    def test_win_rate_between_0_and_100(self, sample_returns):
        """Win rate should be percentage."""
        calc = MetricsCalculator()
        metrics = calc.calculate(sample_returns)

        assert 0 <= metrics.win_rate <= 100

    def test_information_ratio_with_benchmark(self, sample_returns, benchmark_returns):
        """Information ratio should calculate with benchmark."""
        calc = MetricsCalculator()
        metrics = calc.calculate(sample_returns, benchmark_returns)

        assert metrics.information_ratio is not None

    def test_generate_tearsheet_to_file(self, sample_returns):
        """Tearsheet generation should save HTML to file and return content."""
        calc = MetricsCalculator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "tearsheet.html"
            result = calc.generate_tearsheet(
                sample_returns,
                output_path=output_path,
                title="Test Report",
            )

            assert result is not None
            assert "<html" in result.lower() or "<!doctype" in result.lower()
            assert output_path.exists()
            content = output_path.read_text()
            assert content == result

    def test_generate_tearsheet_without_path(self, sample_returns):
        """Tearsheet generation should return HTML without saving."""
        calc = MetricsCalculator()
        result = calc.generate_tearsheet(
            sample_returns,
            output_path=None,
            title="Test Report",
        )

        assert result is not None
        assert "<html" in result.lower() or "<!doctype" in result.lower()

    def test_var_cvar_reasonable(self, sample_returns):
        """VaR and CVaR should be negative for returns with downside."""
        calc = MetricsCalculator()
        metrics = calc.calculate(sample_returns)

        assert metrics.var_95 < 0
        assert metrics.cvar_95 <= metrics.var_95


class TestCompareStrategies:
    """Test strategy comparison."""

    def test_compare_multiple_strategies(self):
        """Compare should return DataFrame with all strategies."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=200, freq="B")

        strategies = {
            "aggressive": pd.Series(np.random.normal(0.001, 0.02, 200), index=dates),
            "conservative": pd.Series(np.random.normal(0.0003, 0.008, 200), index=dates),
        }

        result = compare_strategies(strategies)

        assert isinstance(result, pd.DataFrame)
        assert "aggressive" in result.index
        assert "conservative" in result.index
        assert "Sharpe" in result.columns


class TestPerformanceMetrics:
    """Test PerformanceMetrics dataclass."""

    def test_all_fields_present(self):
        """Verify all metrics fields exist."""
        metrics = PerformanceMetrics(
            total_return=10.0,
            cagr=8.0,
            mtd=1.0,
            ytd=5.0,
            volatility=15.0,
            downside_deviation=10.0,
            max_drawdown=-12.0,
            avg_drawdown=-5.0,
            drawdown_duration=30,
            sharpe_ratio=0.8,
            sortino_ratio=1.1,
            calmar_ratio=0.7,
            omega_ratio=1.5,
            win_rate=55.0,
            profit_factor=1.8,
            payoff_ratio=1.5,
            expected_return=0.05,
            var_95=-2.5,
            cvar_95=-3.5,
            skewness=-0.1,
            kurtosis=3.5,
            best_month=8.0,
            worst_month=-6.0,
            avg_monthly_return=0.8,
        )

        assert metrics.sharpe_ratio == 0.8
        assert metrics.max_drawdown == -12.0
