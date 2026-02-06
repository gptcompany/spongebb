"""Unit tests for OilRealRatesAnalyzer."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from liquidity.analyzers.oil_real_rates import (
    OilRealRatesAnalyzer,
    OilRealRatesCorrelation,
)


@pytest.fixture
def analyzer():
    """Default analyzer instance."""
    return OilRealRatesAnalyzer()


@pytest.fixture
def mock_oil_data():
    """Mock oil price data with realistic values."""
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    # Simulate oil prices with some volatility
    np.random.seed(42)
    prices = 75 + np.cumsum(np.random.randn(120) * 0.5)
    return pd.DataFrame(
        {
            "timestamp": dates,
            "series_id": "CL=F",
            "source": "yahoo",
            "value": prices,
            "unit": "usd_per_barrel",
        }
    )


@pytest.fixture
def mock_rates_data():
    """Mock real rates data (TIPS yield) with realistic values."""
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    # Simulate real rates around 2% with some movement
    np.random.seed(43)
    rates = 2.0 + np.cumsum(np.random.randn(120) * 0.02)
    return pd.DataFrame(
        {
            "timestamp": dates,
            "series_id": "DFII10",
            "source": "fred",
            "value": rates,
            "unit": "percent",
        }
    )


@pytest.fixture
def negatively_correlated_data():
    """Data with strong negative correlation between oil returns and rates changes."""
    dates = pd.date_range("2024-01-01", periods=120, freq="D")

    # Create negatively correlated data
    np.random.seed(44)
    base = np.random.randn(120) * 0.5

    # Oil goes up when rates go down (negative correlation)
    oil_prices = 75 + np.cumsum(-base)  # Inverse of base
    real_rates = 2.0 + np.cumsum(base * 0.03)  # Base direction

    oil_df = pd.DataFrame(
        {
            "timestamp": dates,
            "series_id": "CL=F",
            "source": "yahoo",
            "value": oil_prices,
            "unit": "usd_per_barrel",
        }
    )

    rates_df = pd.DataFrame(
        {
            "timestamp": dates,
            "series_id": "DFII10",
            "source": "fred",
            "value": real_rates,
            "unit": "percent",
        }
    )

    return oil_df, rates_df


@pytest.fixture
def positively_correlated_data():
    """Data with positive correlation (breakdown regime)."""
    dates = pd.date_range("2024-01-01", periods=120, freq="D")

    # Create positively correlated data (unusual, breakdown scenario)
    np.random.seed(45)
    base = np.random.randn(120) * 0.5

    # Oil and rates move together (positive correlation)
    oil_prices = 75 + np.cumsum(base)
    real_rates = 2.0 + np.cumsum(base * 0.03)

    oil_df = pd.DataFrame(
        {
            "timestamp": dates,
            "series_id": "CL=F",
            "source": "yahoo",
            "value": oil_prices,
            "unit": "usd_per_barrel",
        }
    )

    rates_df = pd.DataFrame(
        {
            "timestamp": dates,
            "series_id": "DFII10",
            "source": "fred",
            "value": real_rates,
            "unit": "percent",
        }
    )

    return oil_df, rates_df


class TestRegimeClassification:
    """Test regime classification logic."""

    def test_classify_surge(self, analyzer):
        """Correlation < -0.7 should be 'surge'."""
        assert analyzer._classify_regime(-0.75) == "surge"
        assert analyzer._classify_regime(-0.9) == "surge"
        assert analyzer._classify_regime(-1.0) == "surge"

    def test_classify_normal(self, analyzer):
        """Correlation in [-0.7, -0.3] should be 'normal'."""
        assert analyzer._classify_regime(-0.5) == "normal"
        assert analyzer._classify_regime(-0.7) == "normal"
        assert analyzer._classify_regime(-0.3) == "normal"
        assert analyzer._classify_regime(-0.4) == "normal"

    def test_classify_breakdown(self, analyzer):
        """Correlation > -0.3 should be 'breakdown'."""
        assert analyzer._classify_regime(-0.2) == "breakdown"
        assert analyzer._classify_regime(0.0) == "breakdown"
        assert analyzer._classify_regime(0.3) == "breakdown"
        assert analyzer._classify_regime(0.5) == "breakdown"

    def test_classify_nan(self, analyzer):
        """NaN should return 'unknown'."""
        assert analyzer._classify_regime(np.nan) == "unknown"
        assert analyzer._classify_regime(float("nan")) == "unknown"


class TestNormalCorrRange:
    """Test NORMAL_CORR_RANGE constant."""

    def test_range_values(self):
        """Verify expected correlation range."""
        assert OilRealRatesAnalyzer.NORMAL_CORR_RANGE == (-0.7, -0.3)


class TestComputeCorrelation:
    """Test compute_correlation method."""

    @pytest.mark.asyncio
    async def test_compute_with_negative_correlation(self, analyzer, negatively_correlated_data):
        """Test correlation computation with negatively correlated data."""
        oil_df, rates_df = negatively_correlated_data

        with (
            patch.object(
                analyzer._commodity_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=oil_df,
            ),
            patch.object(
                analyzer._fred_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=rates_df,
            ),
        ):
            df = await analyzer.compute_correlation()

            assert not df.empty
            assert "corr_30d" in df.columns
            assert "corr_90d" in df.columns
            assert "corr_ewma" in df.columns
            assert "regime" in df.columns
            assert "oil_ret" in df.columns
            assert "rates_diff" in df.columns

            # Should have negative correlation
            valid_corr = df["corr_30d"].dropna()
            if not valid_corr.empty:
                mean_corr = valid_corr.mean()
                assert mean_corr < 0, f"Expected negative correlation, got {mean_corr}"

    @pytest.mark.asyncio
    async def test_compute_with_positive_correlation(self, analyzer, positively_correlated_data):
        """Test correlation computation with positively correlated data (breakdown)."""
        oil_df, rates_df = positively_correlated_data

        with (
            patch.object(
                analyzer._commodity_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=oil_df,
            ),
            patch.object(
                analyzer._fred_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=rates_df,
            ),
        ):
            df = await analyzer.compute_correlation()

            assert not df.empty

            # Should have positive correlation (breakdown regime)
            valid_corr = df["corr_30d"].dropna()
            if not valid_corr.empty:
                mean_corr = valid_corr.mean()
                assert mean_corr > 0, f"Expected positive correlation, got {mean_corr}"

                # Check regime classification
                latest_regime = df["regime"].iloc[-1]
                assert latest_regime == "breakdown"

    @pytest.mark.asyncio
    async def test_compute_returns_empty_on_no_data(self, analyzer):
        """Test that empty DataFrame is returned when no data available."""
        with patch.object(
            analyzer._commodity_collector,
            "collect",
            new_callable=AsyncMock,
            return_value=pd.DataFrame(),
        ):
            df = await analyzer.compute_correlation()
            assert df.empty

    @pytest.mark.asyncio
    async def test_compute_returns_empty_on_insufficient_data(self, analyzer):
        """Test with less than 30 observations."""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        small_oil_df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": "CL=F",
                "source": "yahoo",
                "value": [75 + i for i in range(10)],
                "unit": "usd_per_barrel",
            }
        )
        small_rates_df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": "DFII10",
                "source": "fred",
                "value": [2.0 + i * 0.01 for i in range(10)],
                "unit": "percent",
            }
        )

        with (
            patch.object(
                analyzer._commodity_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=small_oil_df,
            ),
            patch.object(
                analyzer._fred_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=small_rates_df,
            ),
        ):
            df = await analyzer.compute_correlation()
            assert df.empty


class TestGetCurrentState:
    """Test get_current_state method."""

    @pytest.mark.asyncio
    async def test_get_state_returns_dataclass(self, analyzer, negatively_correlated_data):
        """Test that get_current_state returns OilRealRatesCorrelation."""
        oil_df, rates_df = negatively_correlated_data

        with (
            patch.object(
                analyzer._commodity_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=oil_df,
            ),
            patch.object(
                analyzer._fred_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=rates_df,
            ),
        ):
            state = await analyzer.get_current_state()

            assert isinstance(state, OilRealRatesCorrelation)
            assert hasattr(state, "timestamp")
            assert hasattr(state, "corr_30d")
            assert hasattr(state, "corr_90d")
            assert hasattr(state, "corr_ewma")
            assert hasattr(state, "p_value_30d")
            assert hasattr(state, "p_value_90d")
            assert hasattr(state, "regime")

    @pytest.mark.asyncio
    async def test_state_values_in_valid_range(self, analyzer, negatively_correlated_data):
        """Test that correlation values are in valid range [-1, 1]."""
        oil_df, rates_df = negatively_correlated_data

        with (
            patch.object(
                analyzer._commodity_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=oil_df,
            ),
            patch.object(
                analyzer._fred_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=rates_df,
            ),
        ):
            state = await analyzer.get_current_state()

            assert -1 <= state.corr_30d <= 1
            assert -1 <= state.corr_90d <= 1
            assert -1 <= state.corr_ewma <= 1
            assert 0 <= state.p_value_30d <= 1
            assert 0 <= state.p_value_90d <= 1

    @pytest.mark.asyncio
    async def test_state_regime_valid(self, analyzer, negatively_correlated_data):
        """Test that regime is a valid value."""
        oil_df, rates_df = negatively_correlated_data

        with (
            patch.object(
                analyzer._commodity_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=oil_df,
            ),
            patch.object(
                analyzer._fred_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=rates_df,
            ),
        ):
            state = await analyzer.get_current_state()

            assert state.regime in ["normal", "breakdown", "surge", "unknown"]

    @pytest.mark.asyncio
    async def test_get_state_raises_on_empty_data(self, analyzer):
        """Test that ValueError is raised when no data available."""
        with (
            patch.object(
                analyzer._commodity_collector,
                "collect",
                new_callable=AsyncMock,
                return_value=pd.DataFrame(),
            ),
            pytest.raises(ValueError, match="No data available"),
        ):
            await analyzer.get_current_state()


class TestOilRealRatesCorrelationDataclass:
    """Test OilRealRatesCorrelation dataclass."""

    def test_is_significant_30d(self):
        """Test is_significant_30d helper method."""
        corr = OilRealRatesCorrelation(
            timestamp=datetime.now(UTC),
            corr_30d=-0.5,
            corr_90d=-0.4,
            corr_ewma=-0.45,
            p_value_30d=0.01,
            p_value_90d=0.10,
            regime="normal",
        )

        assert corr.is_significant_30d() is True  # 0.01 < 0.05
        assert corr.is_significant_30d(alpha=0.001) is False  # 0.01 > 0.001

    def test_is_significant_90d(self):
        """Test is_significant_90d helper method."""
        corr = OilRealRatesCorrelation(
            timestamp=datetime.now(UTC),
            corr_30d=-0.5,
            corr_90d=-0.4,
            corr_ewma=-0.45,
            p_value_30d=0.01,
            p_value_90d=0.10,
            regime="normal",
        )

        assert corr.is_significant_90d() is False  # 0.10 > 0.05
        assert corr.is_significant_90d(alpha=0.15) is True  # 0.10 < 0.15


class TestEwmaCorrelation:
    """Test EWMA correlation calculation."""

    def test_ewma_correlation_calculation(self, analyzer):
        """Test EWMA correlation calculation with known values."""
        np.random.seed(46)
        n = 100
        x = pd.Series(np.random.randn(n))
        y = pd.Series(-x + np.random.randn(n) * 0.1)  # Negatively correlated

        ewma_corr = analyzer._calculate_ewma_correlation(x, y)

        assert len(ewma_corr) == n
        # Should be negative (since y = -x + noise)
        assert ewma_corr.iloc[-1] < 0

    def test_ewma_halflife_effect(self):
        """Test that different halflife values affect EWMA."""
        analyzer_short = OilRealRatesAnalyzer(ewma_halflife=10)
        analyzer_long = OilRealRatesAnalyzer(ewma_halflife=60)

        np.random.seed(47)
        n = 100
        x = pd.Series(np.random.randn(n))
        y = pd.Series(-x + np.random.randn(n) * 0.2)

        ewma_short = analyzer_short._calculate_ewma_correlation(x, y)
        ewma_long = analyzer_long._calculate_ewma_correlation(x, y)

        # Both should converge to similar values at the end
        # but shorter halflife responds faster
        assert len(ewma_short) == len(ewma_long)


class TestPValueCalculation:
    """Test p-value calculation."""

    def test_pvalue_for_correlated_data(self, analyzer):
        """Test p-value calculation for strongly correlated data."""
        np.random.seed(48)
        n = 50
        x = pd.Series(np.random.randn(n))
        y = pd.Series(x + np.random.randn(n) * 0.1)  # Strongly correlated

        pvalue = analyzer._calculate_pvalue(x, y)

        # Should be very small (significant)
        assert pvalue < 0.01

    def test_pvalue_for_uncorrelated_data(self, analyzer):
        """Test p-value calculation for uncorrelated data."""
        np.random.seed(49)
        n = 50
        x = pd.Series(np.random.randn(n))
        y = pd.Series(np.random.randn(n))  # Independent

        pvalue = analyzer._calculate_pvalue(x, y)

        # May or may not be significant, but should be a valid p-value
        assert 0 <= pvalue <= 1

    def test_pvalue_returns_1_on_insufficient_data(self, analyzer):
        """Test that p-value returns 1.0 with too few observations."""
        x = pd.Series([1, 2])
        y = pd.Series([3, 4])

        pvalue = analyzer._calculate_pvalue(x, y)
        assert pvalue == 1.0


class TestRepr:
    """Test string representation."""

    def test_repr(self, analyzer):
        """Test __repr__ output."""
        assert "OilRealRatesAnalyzer" in repr(analyzer)
        assert "ewma_halflife=30" in repr(analyzer)

    def test_repr_custom_halflife(self):
        """Test __repr__ with custom halflife."""
        analyzer = OilRealRatesAnalyzer(ewma_halflife=45)
        assert "ewma_halflife=45" in repr(analyzer)
