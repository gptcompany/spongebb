"""Unit tests for correlation trend prediction module."""

import numpy as np
import pandas as pd
import pytest

from liquidity.nowcasting.correlation import (
    CorrelationFeatureBuilder,
    CorrelationFeatures,
    CorrelationTrendPredictor,
    TrendDirection,
)


class TestTrendDirection:
    """Tests for TrendDirection enum."""

    def test_values(self) -> None:
        """Test enum values."""
        assert TrendDirection.STRENGTHENING.value == "strengthening"
        assert TrendDirection.STABLE.value == "stable"
        assert TrendDirection.WEAKENING.value == "weakening"


class TestCorrelationFeatures:
    """Tests for CorrelationFeatures dataclass."""

    def test_creation(self) -> None:
        """Test dataclass creation."""
        features = CorrelationFeatures(
            asset="BTC",
            current_corr_30d=0.5,
            current_corr_90d=0.45,
            corr_momentum=0.1,
            corr_acceleration=0.02,
            ewma_corr=0.48,
            zscore=1.2,
        )

        assert features.asset == "BTC"
        assert features.current_corr_30d == 0.5
        assert features.current_corr_90d == 0.45

    def test_as_array(self) -> None:
        """Test as_array method."""
        features = CorrelationFeatures(
            asset="BTC",
            current_corr_30d=0.5,
            current_corr_90d=0.45,
            corr_momentum=0.1,
            corr_acceleration=0.02,
            ewma_corr=0.48,
            zscore=1.2,
        )

        arr = features.as_array()
        assert isinstance(arr, np.ndarray)
        assert arr.dtype == np.float64
        assert len(arr) == 6
        assert arr[0] == 0.5  # current_corr_30d


class TestCorrelationFeatureBuilder:
    """Tests for CorrelationFeatureBuilder."""

    @pytest.fixture
    def sample_data(self) -> tuple[pd.Series, pd.Series]:
        """Create sample returns data."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=500, freq="B")

        # Create correlated returns
        liquidity_returns = pd.Series(np.random.randn(500) * 0.01, index=dates)
        asset_returns = pd.Series(
            0.5 * liquidity_returns + np.random.randn(500) * 0.02, index=dates
        )

        return asset_returns, liquidity_returns

    def test_initialization(self) -> None:
        """Test builder initialization."""
        builder = CorrelationFeatureBuilder()

        assert builder.short_window == 30
        assert builder.long_window == 90
        assert builder.ewma_span == 20
        assert builder.zscore_window == 252

    def test_custom_windows(self) -> None:
        """Test custom window configuration."""
        builder = CorrelationFeatureBuilder(
            short_window=20, long_window=60, ewma_span=10, zscore_window=126
        )

        assert builder.short_window == 20
        assert builder.long_window == 60

    def test_compute_features(
        self, sample_data: tuple[pd.Series, pd.Series]
    ) -> None:
        """Test feature computation."""
        asset_returns, liquidity_returns = sample_data
        builder = CorrelationFeatureBuilder()

        features_df = builder.compute_features(
            asset_returns, liquidity_returns, "BTC"
        )

        assert isinstance(features_df, pd.DataFrame)
        assert "BTC_corr_30d" in features_df.columns
        assert "BTC_corr_90d" in features_df.columns
        assert "BTC_momentum" in features_df.columns
        assert "BTC_acceleration" in features_df.columns
        assert "BTC_ewma" in features_df.columns
        assert "BTC_zscore" in features_df.columns

    def test_get_current_features(
        self, sample_data: tuple[pd.Series, pd.Series]
    ) -> None:
        """Test getting current features."""
        asset_returns, liquidity_returns = sample_data
        builder = CorrelationFeatureBuilder()

        features = builder.get_current_features(
            asset_returns, liquidity_returns, "BTC"
        )

        assert isinstance(features, CorrelationFeatures)
        assert features.asset == "BTC"
        assert -1 <= features.current_corr_30d <= 1
        assert -1 <= features.current_corr_90d <= 1

    def test_compute_all_assets(
        self, sample_data: tuple[pd.Series, pd.Series]
    ) -> None:
        """Test computing features for multiple assets."""
        _, liquidity_returns = sample_data
        np.random.seed(43)

        asset_returns = {
            "BTC": pd.Series(
                np.random.randn(500) * 0.02, index=liquidity_returns.index
            ),
            "SPX": pd.Series(
                np.random.randn(500) * 0.01, index=liquidity_returns.index
            ),
        }

        builder = CorrelationFeatureBuilder()
        features_df = builder.compute_all_assets(asset_returns, liquidity_returns)

        assert "BTC_corr_30d" in features_df.columns
        assert "SPX_corr_30d" in features_df.columns


class TestCorrelationTrendPredictor:
    """Tests for CorrelationTrendPredictor."""

    @pytest.fixture
    def sample_data(self) -> tuple[dict[str, pd.Series], pd.Series]:
        """Create sample returns data."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=750, freq="B")

        liquidity_returns = pd.Series(np.random.randn(750) * 0.01, index=dates)

        asset_returns = {
            "BTC": pd.Series(
                0.5 * liquidity_returns + np.random.randn(750) * 0.02, index=dates
            ),
            "SPX": pd.Series(
                0.3 * liquidity_returns + np.random.randn(750) * 0.01, index=dates
            ),
        }

        return asset_returns, liquidity_returns

    def test_initialization(self) -> None:
        """Test predictor initialization."""
        predictor = CorrelationTrendPredictor()

        assert predictor.alpha == 1.0
        assert predictor.short_window == 30
        assert predictor.long_window == 90
        assert not predictor.is_fitted

    def test_custom_assets(self) -> None:
        """Test custom asset configuration."""
        predictor = CorrelationTrendPredictor(assets=["BTC", "ETH", "GOLD"])

        assert predictor.assets == ["BTC", "ETH", "GOLD"]

    def test_fit(
        self, sample_data: tuple[dict[str, pd.Series], pd.Series]
    ) -> None:
        """Test model fitting."""
        asset_returns, liquidity_returns = sample_data
        predictor = CorrelationTrendPredictor(assets=["BTC", "SPX"])

        predictor.fit(asset_returns, liquidity_returns)

        assert predictor.is_fitted
        assert "BTC" in predictor._models
        assert "SPX" in predictor._models

    def test_fit_returns_self(
        self, sample_data: tuple[dict[str, pd.Series], pd.Series]
    ) -> None:
        """Test fit returns self for chaining."""
        asset_returns, liquidity_returns = sample_data
        predictor = CorrelationTrendPredictor(assets=["BTC"])

        result = predictor.fit(asset_returns, liquidity_returns)

        assert result is predictor

    def test_predict_before_fit_raises(
        self, sample_data: tuple[dict[str, pd.Series], pd.Series]
    ) -> None:
        """Test predict raises if not fitted."""
        asset_returns, liquidity_returns = sample_data
        predictor = CorrelationTrendPredictor()

        with pytest.raises(ValueError, match="not fitted"):
            predictor.predict(asset_returns, liquidity_returns)

    def test_predict(
        self, sample_data: tuple[dict[str, pd.Series], pd.Series]
    ) -> None:
        """Test prediction."""
        asset_returns, liquidity_returns = sample_data
        predictor = CorrelationTrendPredictor(assets=["BTC", "SPX"])

        predictor.fit(asset_returns, liquidity_returns)
        report = predictor.predict(asset_returns, liquidity_returns)

        assert report.timestamp is not None
        assert "BTC" in report.forecasts
        assert "SPX" in report.forecasts
        assert len(report.forecasts["BTC"]) == 3  # 7, 14, 30 days

    def test_forecast_structure(
        self, sample_data: tuple[dict[str, pd.Series], pd.Series]
    ) -> None:
        """Test forecast structure."""
        asset_returns, liquidity_returns = sample_data
        predictor = CorrelationTrendPredictor(assets=["BTC"])

        predictor.fit(asset_returns, liquidity_returns)
        report = predictor.predict(asset_returns, liquidity_returns)

        forecast = report.forecasts["BTC"][0]

        assert forecast.asset == "BTC"
        assert forecast.horizon == 7
        assert -1 <= forecast.predicted_corr <= 1
        assert isinstance(forecast.direction, TrendDirection)
        assert 0 <= forecast.confidence <= 1

    def test_breakdown_risk(
        self, sample_data: tuple[dict[str, pd.Series], pd.Series]
    ) -> None:
        """Test breakdown risk calculation."""
        asset_returns, liquidity_returns = sample_data
        predictor = CorrelationTrendPredictor(assets=["BTC", "SPX"])

        predictor.fit(asset_returns, liquidity_returns)

        risks = predictor.get_correlation_breakdown_risk(
            asset_returns, liquidity_returns
        )

        assert "BTC" in risks
        assert "SPX" in risks
        assert 0 <= risks["BTC"] <= 1
        assert 0 <= risks["SPX"] <= 1


class TestCorrelationIntegration:
    """Integration tests for correlation prediction."""

    def test_full_workflow(self) -> None:
        """Test complete workflow."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=1000, freq="B")

        liquidity_returns = pd.Series(np.random.randn(1000) * 0.01, index=dates)
        asset_returns = {
            "BTC": pd.Series(
                0.6 * liquidity_returns + np.random.randn(1000) * 0.02, index=dates
            ),
        }

        # Build features
        builder = CorrelationFeatureBuilder()
        features = builder.get_current_features(
            asset_returns["BTC"], liquidity_returns, "BTC"
        )
        assert isinstance(features, CorrelationFeatures)

        # Fit predictor
        predictor = CorrelationTrendPredictor(assets=["BTC"])
        predictor.fit(asset_returns, liquidity_returns)

        # Generate report
        report = predictor.predict(asset_returns, liquidity_returns)

        assert len(report.forecasts["BTC"]) == 3
        assert isinstance(report.breakdown_risks, dict)
