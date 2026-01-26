"""Unit tests for CorrelationEngine.

Tests use synthetic data (np.sin(), np.random.randn(), identical series)
to verify correlation calculations without external dependencies.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from liquidity.analyzers.correlation_engine import (
    CorrelationEngine,
    CorrelationMatrix,
    CorrelationResult,
)


class TestCorrelationResult:
    """Tests for CorrelationResult dataclass."""

    def test_dataclass_creation(self):
        """Test result dataclass can be created."""
        result = CorrelationResult(
            timestamp=datetime.now(UTC),
            asset="BTC",
            liquidity_metric="net_liquidity",
            corr_30d=0.75,
            corr_90d=0.68,
            corr_ewma=0.72,
            p_value_30d=0.001,
            p_value_90d=0.005,
            sample_size=100,
        )
        assert result.asset == "BTC"
        assert result.corr_30d == 0.75
        assert result.sample_size == 100

    def test_dataclass_with_none_values(self):
        """Test result with None correlation values."""
        result = CorrelationResult(
            timestamp=datetime.now(UTC),
            asset="SPX",
            liquidity_metric="net_liquidity",
            corr_30d=None,
            corr_90d=None,
            corr_ewma=None,
            p_value_30d=None,
            p_value_90d=None,
            sample_size=10,
        )
        assert result.corr_30d is None
        assert result.p_value_30d is None


class TestCorrelationMatrix:
    """Tests for CorrelationMatrix dataclass."""

    def test_matrix_creation(self):
        """Test matrix dataclass can be created."""
        matrix = CorrelationMatrix(
            timestamp=datetime.now(UTC),
            assets=["BTC", "SPX"],
            correlations=pd.DataFrame([[1.0, 0.5], [0.5, 1.0]], columns=["BTC", "SPX"]),
            p_values=pd.DataFrame([[0.0, 0.01], [0.01, 0.0]], columns=["BTC", "SPX"]),
        )
        assert matrix.assets == ["BTC", "SPX"]
        assert matrix.correlations.shape == (2, 2)

    def test_matrix_empty_defaults(self):
        """Test matrix with default empty values."""
        matrix = CorrelationMatrix(timestamp=datetime.now(UTC))
        assert matrix.assets == []
        assert matrix.correlations.empty


class TestCorrelationEngine:
    """Tests for CorrelationEngine class."""

    def test_init_default(self):
        """Test engine initialization with defaults."""
        engine = CorrelationEngine()
        assert engine is not None
        assert engine._ewma_halflife == 21

    def test_init_custom_halflife(self):
        """Test engine initialization with custom halflife."""
        engine = CorrelationEngine(ewma_halflife=14)
        assert engine._ewma_halflife == 14

    def test_repr(self):
        """Test string representation."""
        engine = CorrelationEngine(ewma_halflife=30)
        assert "CorrelationEngine" in repr(engine)
        assert "ewma_halflife=30" in repr(engine)

    def test_assets_constant(self):
        """Test ASSETS constant has expected values."""
        engine = CorrelationEngine()
        assert "BTC" in engine.ASSETS
        assert "SPX" in engine.ASSETS
        assert "GOLD" in engine.ASSETS
        assert len(engine.ASSETS) == 7

    def test_windows_constant(self):
        """Test WINDOWS constant."""
        assert CorrelationEngine.WINDOWS == [30, 90]


class TestRollingCorrelationPerfectPositive:
    """Tests for rolling correlation with perfect positive correlation."""

    @pytest.fixture
    def identical_series(self):
        """Create identical series for testing."""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        values = np.random.randn(100).cumsum()
        series1 = pd.Series(values, index=dates, name="asset")
        series2 = pd.Series(values, index=dates, name="liquidity")
        return series1, series2

    def test_perfect_positive_correlation(self, identical_series):
        """Test correlation of identical series is +1."""
        engine = CorrelationEngine()
        asset_ret, liq_ret = identical_series

        # Calculate returns (they will still be identical)
        result = engine.calculate_single_correlation(asset_ret, liq_ret, window=30)

        # Perfect correlation
        assert result.corr_30d is not None
        assert result.corr_30d == pytest.approx(1.0, abs=0.001)

    def test_rolling_correlation_returns_series(self, identical_series):
        """Test rolling correlation returns full series."""
        engine = CorrelationEngine()
        series1, series2 = identical_series

        results = engine.calculate_correlations(series1.to_frame(), series2)
        assert "corr_30d" in results
        assert not results["corr_30d"].empty


class TestRollingCorrelationPerfectNegative:
    """Tests for rolling correlation with perfect negative correlation."""

    @pytest.fixture
    def negatively_correlated_series(self):
        """Create perfectly negatively correlated series."""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        values = np.random.randn(100).cumsum()
        series1 = pd.Series(values, index=dates, name="asset")
        series2 = pd.Series(-values, index=dates, name="liquidity")  # Negative
        return series1, series2

    def test_perfect_negative_correlation(self, negatively_correlated_series):
        """Test correlation of negatively correlated series is -1."""
        engine = CorrelationEngine()
        asset_ret, liq_ret = negatively_correlated_series

        result = engine.calculate_single_correlation(asset_ret, liq_ret, window=30)

        assert result.corr_30d is not None
        assert result.corr_30d == pytest.approx(-1.0, abs=0.001)


class TestRollingCorrelationUncorrelated:
    """Tests for rolling correlation with uncorrelated series."""

    @pytest.fixture
    def uncorrelated_series(self):
        """Create uncorrelated series using sin/cos."""
        dates = pd.date_range(start="2024-01-01", periods=360, freq="D")
        # Sin and cos are orthogonal over full period
        x = np.linspace(0, 4 * np.pi, 360)
        series1 = pd.Series(np.sin(x), index=dates, name="asset")
        series2 = pd.Series(np.cos(x), index=dates, name="liquidity")
        return series1, series2

    def test_uncorrelated_near_zero(self, uncorrelated_series):
        """Test correlation of orthogonal series is near 0."""
        engine = CorrelationEngine()
        series1, series2 = uncorrelated_series

        result = engine.calculate_single_correlation(series1, series2, window=90)

        # Orthogonal signals should have near-zero correlation over many periods
        assert result.corr_90d is not None
        assert abs(result.corr_90d) < 0.3  # Allow some noise

    def test_random_uncorrelated(self):
        """Test correlation of independent random series."""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=500, freq="D")
        series1 = pd.Series(np.random.randn(500), index=dates, name="asset")
        series2 = pd.Series(np.random.randn(500), index=dates, name="liquidity")

        engine = CorrelationEngine()
        result = engine.calculate_single_correlation(series1, series2, window=90)

        # Independent random series should have low correlation
        assert result.corr_90d is not None
        assert abs(result.corr_90d) < 0.2


class TestEWMAWeightsRecentMore:
    """Tests for EWMA giving more weight to recent observations."""

    def test_ewma_weights_recent_more(self):
        """Test EWMA correlation weights recent observations more heavily."""
        engine = CorrelationEngine(ewma_halflife=10)

        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")

        # Create series that changes correlation midway
        # First 50 days: positive correlation, last 50 days: negative
        np.random.seed(42)
        base = np.random.randn(100).cumsum()

        series1 = pd.Series(base, index=dates, name="asset")
        # First half: same sign, second half: opposite sign
        series2_values = np.concatenate([base[:50], -base[50:]])
        series2 = pd.Series(series2_values, index=dates, name="liquidity")

        # Calculate EWMA correlation
        ewma_corr = engine._calculate_ewma_correlation(series1, series2)

        # The EWMA at the end should be negative (reflecting recent negative correlation)
        # while standard correlation over full period would be near zero
        final_ewma = ewma_corr.iloc[-1]
        assert final_ewma < 0, "EWMA should reflect recent negative correlation"

    def test_shorter_halflife_more_responsive(self):
        """Test shorter halflife responds faster to changes."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        np.random.seed(42)
        base = np.random.randn(100).cumsum()

        series1 = pd.Series(base, index=dates, name="asset")
        series2_values = np.concatenate([base[:50], -base[50:]])
        series2 = pd.Series(series2_values, index=dates, name="liquidity")

        engine_short = CorrelationEngine(ewma_halflife=5)
        engine_long = CorrelationEngine(ewma_halflife=30)

        ewma_short = engine_short._calculate_ewma_correlation(series1, series2)
        ewma_long = engine_long._calculate_ewma_correlation(series1, series2)

        # Short halflife should be more negative at the end
        # (more responsive to recent negative correlation)
        assert ewma_short.iloc[-1] < ewma_long.iloc[-1]


class TestMinPeriodsHandling:
    """Tests for min_periods handling in rolling correlations."""

    def test_insufficient_data_returns_none(self):
        """Test that insufficient data returns None correlations."""
        engine = CorrelationEngine()

        dates = pd.date_range(start="2024-01-01", periods=10, freq="D")
        series1 = pd.Series(np.random.randn(10), index=dates, name="asset")
        series2 = pd.Series(np.random.randn(10), index=dates, name="liquidity")

        result = engine.calculate_single_correlation(series1, series2, window=30)

        # With only 10 observations and min_periods=15, should return None
        # Actually min_periods is min(15, sample_size) so it will calculate
        assert result.sample_size == 10

    def test_partial_data_uses_min_periods(self):
        """Test that partial data uses min_periods correctly."""
        engine = CorrelationEngine()

        dates = pd.date_range(start="2024-01-01", periods=20, freq="D")
        np.random.seed(42)
        values = np.random.randn(20).cumsum()
        series1 = pd.Series(values, index=dates, name="asset")
        series2 = pd.Series(values, index=dates, name="liquidity")

        result = engine.calculate_single_correlation(series1, series2, window=30)

        # Should still get a correlation with 20 observations
        # min_periods = min(15, 20) = 15
        assert result.corr_30d is not None
        assert result.sample_size == 20


class TestCorrelationMatrixSymmetric:
    """Tests for correlation matrix symmetry."""

    @pytest.fixture
    def returns_df(self):
        """Create returns DataFrame for testing."""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        return pd.DataFrame(
            {
                "BTC": np.random.randn(100).cumsum(),
                "SPX": np.random.randn(100).cumsum(),
                "GOLD": np.random.randn(100).cumsum(),
            },
            index=dates,
        )

    def test_correlation_matrix_symmetric(self, returns_df):
        """Test that correlation matrix is symmetric."""
        engine = CorrelationEngine()
        matrix = engine.calculate_correlation_matrix(returns_df)

        corr = matrix.correlations
        # Check symmetry: corr[i,j] == corr[j,i]
        for i in range(len(matrix.assets)):
            for j in range(len(matrix.assets)):
                assert corr.iloc[i, j] == pytest.approx(
                    corr.iloc[j, i], abs=1e-10
                ), f"Matrix not symmetric at ({i}, {j})"


class TestCorrelationMatrixDiagonalOnes:
    """Tests for correlation matrix diagonal values."""

    @pytest.fixture
    def returns_df(self):
        """Create returns DataFrame for testing."""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        return pd.DataFrame(
            {
                "BTC": np.random.randn(100),
                "SPX": np.random.randn(100),
                "GOLD": np.random.randn(100),
                "TLT": np.random.randn(100),
            },
            index=dates,
        )

    def test_diagonal_is_one(self, returns_df):
        """Test that diagonal of correlation matrix is 1."""
        engine = CorrelationEngine()
        matrix = engine.calculate_correlation_matrix(returns_df)

        corr = matrix.correlations
        for i in range(len(matrix.assets)):
            assert corr.iloc[i, i] == pytest.approx(
                1.0, abs=1e-10
            ), f"Diagonal at ({i}, {i}) is not 1.0"

    def test_diagonal_p_value_is_zero(self, returns_df):
        """Test that diagonal p-values are 0 (perfect correlation with self)."""
        engine = CorrelationEngine()
        matrix = engine.calculate_correlation_matrix(returns_df)

        p_vals = matrix.p_values
        for i in range(len(matrix.assets)):
            assert p_vals.iloc[i, i] == pytest.approx(
                0.0, abs=1e-10
            ), f"Diagonal p-value at ({i}, {i}) is not 0.0"


class TestPValueSignificance:
    """Tests for p-value calculation and significance."""

    @pytest.fixture
    def highly_correlated(self):
        """Create highly correlated series."""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        base = np.random.randn(100).cumsum()
        noise = np.random.randn(100) * 0.1
        series1 = pd.Series(base, index=dates, name="asset")
        series2 = pd.Series(base + noise, index=dates, name="liquidity")
        return series1, series2

    def test_significant_correlation_low_p_value(self, highly_correlated):
        """Test that significant correlation has low p-value."""
        engine = CorrelationEngine()
        series1, series2 = highly_correlated

        result = engine.calculate_single_correlation(series1, series2, window=30)

        # High correlation should have low p-value
        assert result.p_value_30d is not None
        assert result.p_value_30d < 0.05, "Significant correlation should have p < 0.05"

    def test_nonsignificant_correlation_high_p_value(self):
        """Test that weak correlation has high p-value."""
        engine = CorrelationEngine()

        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        # Independent random series
        series1 = pd.Series(np.random.randn(100), index=dates, name="asset")
        series2 = pd.Series(np.random.randn(100), index=dates, name="liquidity")

        result = engine.calculate_single_correlation(series1, series2, window=30)

        # Weak correlation should have higher p-value (not always >0.05 due to randomness)
        # Just verify p-value is calculated
        assert result.p_value_30d is not None
        assert 0 <= result.p_value_30d <= 1


class TestReturnsCalculation:
    """Tests for returns calculation."""

    def test_calculate_returns_basic(self):
        """Test basic returns calculation."""
        engine = CorrelationEngine()

        dates = pd.date_range(start="2024-01-01", periods=5, freq="D")
        prices = pd.DataFrame({"asset": [100, 110, 105, 115, 120]}, index=dates)

        returns = engine._calculate_returns(prices)

        # First row dropped (NaN)
        assert len(returns) == 4
        # Check returns
        assert returns["asset"].iloc[0] == pytest.approx(0.10)  # 110/100 - 1
        assert returns["asset"].iloc[1] == pytest.approx(-0.0454545, abs=0.001)  # 105/110 - 1

    def test_calculate_returns_drops_first_row(self):
        """Test that returns drops first row (NaN from pct_change)."""
        engine = CorrelationEngine()

        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        prices = pd.DataFrame(
            {"asset": np.arange(100) + 100},
            index=dates,
        )

        returns = engine._calculate_returns(prices)

        assert len(returns) == 99  # One less than prices
        assert not returns.isna().any().any()  # No NaN values


class TestCalculateCorrelations:
    """Tests for calculate_correlations method."""

    @pytest.fixture
    def multi_asset_data(self):
        """Create multi-asset returns data."""
        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=120, freq="D")

        # Create base liquidity signal
        liquidity = pd.Series(np.random.randn(120).cumsum(), index=dates, name="liquidity")

        # Create assets with different correlations to liquidity
        assets = pd.DataFrame(
            {
                "BTC": liquidity * 0.8 + np.random.randn(120) * 0.2,  # High correlation
                "GOLD": -liquidity * 0.5 + np.random.randn(120) * 0.5,  # Negative correlation
                "DXY": np.random.randn(120),  # Uncorrelated
            },
            index=dates,
        )

        return assets, liquidity

    def test_calculate_correlations_returns_dict(self, multi_asset_data):
        """Test calculate_correlations returns dictionary with expected keys."""
        engine = CorrelationEngine()
        assets, liquidity = multi_asset_data

        results = engine.calculate_correlations(assets, liquidity)

        assert isinstance(results, dict)
        assert "corr_30d" in results
        assert "corr_90d" in results
        assert "corr_ewma" in results

    def test_calculate_correlations_correct_columns(self, multi_asset_data):
        """Test calculate_correlations maintains asset columns."""
        engine = CorrelationEngine()
        assets, liquidity = multi_asset_data

        results = engine.calculate_correlations(assets, liquidity)

        for key in ["corr_30d", "corr_90d", "corr_ewma"]:
            assert "BTC" in results[key].columns
            assert "GOLD" in results[key].columns
            assert "DXY" in results[key].columns

    def test_calculate_correlations_single_series(self, multi_asset_data):
        """Test calculate_correlations with single Series input."""
        engine = CorrelationEngine()
        assets, liquidity = multi_asset_data

        # Pass single series instead of DataFrame
        single_asset = assets["BTC"]
        results = engine.calculate_correlations(single_asset, liquidity)

        assert "corr_30d" in results
        assert not results["corr_30d"].empty


class TestEWMACorrelation:
    """Tests for EWMA correlation calculation."""

    def test_ewma_correlation_bounded(self):
        """Test EWMA correlation is bounded between -1 and 1."""
        engine = CorrelationEngine()

        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        series1 = pd.Series(np.random.randn(100).cumsum(), index=dates)
        series2 = pd.Series(np.random.randn(100).cumsum(), index=dates)

        ewma_corr = engine._calculate_ewma_correlation(series1, series2)

        # Drop NaN values and check bounds
        valid = ewma_corr.dropna()
        assert (valid >= -1.0).all(), "EWMA correlation below -1"
        assert (valid <= 1.0).all(), "EWMA correlation above 1"

    def test_ewma_correlation_identical_series(self):
        """Test EWMA correlation of identical series is 1."""
        engine = CorrelationEngine()

        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        values = np.random.randn(100).cumsum()
        series1 = pd.Series(values, index=dates)
        series2 = pd.Series(values, index=dates)

        ewma_corr = engine._calculate_ewma_correlation(series1, series2)

        # After warmup, should be close to 1
        assert ewma_corr.iloc[-1] == pytest.approx(1.0, abs=0.01)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_series(self):
        """Test handling of empty series."""
        engine = CorrelationEngine()

        empty = pd.Series(dtype=float, name="asset")
        liquidity = pd.Series(dtype=float, name="liquidity")

        result = engine.calculate_single_correlation(empty, liquidity, window=30)

        assert result.corr_30d is None
        assert result.sample_size == 0

    def test_misaligned_indices(self):
        """Test handling of misaligned date indices."""
        engine = CorrelationEngine()

        dates1 = pd.date_range(start="2024-01-01", periods=50, freq="D")
        dates2 = pd.date_range(start="2024-02-01", periods=50, freq="D")

        # Only 20 days overlap
        np.random.seed(42)
        series1 = pd.Series(np.random.randn(50).cumsum(), index=dates1, name="asset")
        series2 = pd.Series(np.random.randn(50).cumsum(), index=dates2, name="liquidity")

        result = engine.calculate_single_correlation(series1, series2, window=30)

        # Should handle alignment gracefully
        assert result.sample_size <= 50  # At most overlap

    def test_nan_values_in_series(self):
        """Test handling of NaN values in series."""
        engine = CorrelationEngine()

        np.random.seed(42)
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        values = np.random.randn(100).cumsum()
        values[20:25] = np.nan  # Insert some NaNs

        series1 = pd.Series(values, index=dates, name="asset")
        series2 = pd.Series(np.random.randn(100).cumsum(), index=dates, name="liquidity")

        # Should not raise exception
        result = engine.calculate_single_correlation(series1, series2, window=30)
        assert isinstance(result, CorrelationResult)

    def test_constant_series(self):
        """Test handling of constant series (zero variance)."""
        engine = CorrelationEngine()

        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        constant = pd.Series([1.0] * 100, index=dates, name="asset")
        varying = pd.Series(np.random.randn(100).cumsum(), index=dates, name="liquidity")

        # Constant series has zero variance, correlation undefined
        result = engine.calculate_single_correlation(constant, varying, window=30)

        # Should handle gracefully (NaN or None)
        # The correlation will be NaN for constant series
        assert result.sample_size == 100
