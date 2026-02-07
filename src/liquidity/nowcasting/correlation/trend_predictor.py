"""Correlation trend prediction using Ridge regression.

Predicts whether cross-asset correlations are strengthening,
stable, or weakening for portfolio adjustment decisions.

Uses AR(1) + momentum model:
    corr_{t+h} = α + β * corr_t + γ * Δcorr_t + ε
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from .features import CorrelationFeatureBuilder, TrendDirection

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class CorrelationForecast:
    """Correlation trend forecast for an asset.

    Attributes:
        asset: Asset name.
        horizon: Days ahead for forecast.
        predicted_corr: Point estimate of future correlation.
        direction: Trend direction (strengthening/stable/weakening).
        confidence: Prediction confidence (0-1).
        current_corr: Current correlation for reference.
        change: Predicted change (predicted - current).
    """

    asset: str
    horizon: int
    predicted_corr: float
    direction: TrendDirection
    confidence: float
    current_corr: float
    change: float


@dataclass
class CorrelationTrendReport:
    """Full correlation trend report for all assets.

    Attributes:
        timestamp: Report generation time.
        forecasts: Dict mapping asset to list of forecasts (7d, 14d, 30d).
        alerts: List of significant changes detected.
        breakdown_risks: Dict mapping asset to breakdown risk score.
    """

    timestamp: pd.Timestamp
    forecasts: dict[str, list[CorrelationForecast]]
    alerts: list[str]
    breakdown_risks: dict[str, float]


class CorrelationTrendPredictor:
    """Predict correlation trends for assets vs Net Liquidity.

    Uses AR(1) + momentum model with Ridge regularization to predict
    correlation direction for 7/14/30 day horizons.

    Example:
        predictor = CorrelationTrendPredictor()
        predictor.fit(asset_returns, liquidity_returns)
        report = predictor.predict(asset_returns, liquidity_returns)
    """

    DEFAULT_ASSETS = ["BTC", "SPX", "GOLD", "DXY", "TLT", "HYG", "COPPER"]
    HORIZONS = [7, 14, 30]

    # Thresholds for direction classification
    STRENGTHEN_THRESHOLD = 0.05
    WEAKEN_THRESHOLD = -0.05
    ALERT_THRESHOLD = 0.15

    def __init__(
        self,
        assets: list[str] | None = None,
        alpha: float = 1.0,
        short_window: int = 30,
        long_window: int = 90,
    ):
        """Initialize trend predictor.

        Args:
            assets: List of asset names to track. Uses DEFAULT_ASSETS if None.
            alpha: Ridge regularization strength.
            short_window: Short correlation window.
            long_window: Long correlation window.
        """
        self.assets = assets or self.DEFAULT_ASSETS
        self.alpha = alpha
        self.short_window = short_window
        self.long_window = long_window

        self.feature_builder = CorrelationFeatureBuilder(
            short_window=short_window, long_window=long_window
        )

        # Model storage: asset -> horizon -> model
        self._models: dict[str, dict[int, Ridge]] = {}
        self._scalers: dict[str, StandardScaler] = {}
        self._is_fitted = False

    @property
    def is_fitted(self) -> bool:
        """Return whether model has been fitted."""
        return self._is_fitted

    def fit(
        self,
        asset_returns: dict[str, pd.Series],
        liquidity_returns: pd.Series,
    ) -> CorrelationTrendPredictor:
        """Fit prediction models for all assets and horizons.

        Args:
            asset_returns: Dict of asset name -> daily returns.
            liquidity_returns: Net Liquidity daily returns.

        Returns:
            Self for method chaining.
        """
        for asset in self.assets:
            if asset not in asset_returns:
                logger.warning(f"Asset {asset} not in returns dict, skipping")
                continue

            self._models[asset] = {}

            # Build features
            features_df = self.feature_builder.compute_features(
                asset_returns[asset], liquidity_returns, asset
            )

            corr_col = f"{asset}_corr_30d"

            for horizon in self.HORIZONS:
                # Target: correlation h days ahead
                y = features_df[corr_col].shift(-horizon)

                # Features
                feature_cols = [
                    f"{asset}_corr_30d",
                    f"{asset}_momentum",
                    f"{asset}_acceleration",
                    f"{asset}_zscore",
                ]
                X = features_df[feature_cols]

                # Drop NaN
                mask = ~(X.isna().any(axis=1) | y.isna())
                X_clean = X[mask]
                y_clean = y[mask]

                if len(X_clean) < 100:
                    logger.warning(
                        f"Insufficient data for {asset} horizon={horizon}, skipping"
                    )
                    continue

                # Scale and fit
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X_clean)

                model = Ridge(alpha=self.alpha)
                model.fit(X_scaled, y_clean)

                self._models[asset][horizon] = model
                self._scalers[asset] = scaler

        self._is_fitted = len(self._models) > 0
        return self

    def predict(
        self,
        asset_returns: dict[str, pd.Series],
        liquidity_returns: pd.Series,
    ) -> CorrelationTrendReport:
        """Generate correlation trend forecasts for all assets.

        Args:
            asset_returns: Dict of asset name -> daily returns.
            liquidity_returns: Net Liquidity daily returns.

        Returns:
            CorrelationTrendReport with forecasts and alerts.

        Raises:
            ValueError: If model not fitted.
        """
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        forecasts: dict[str, list[CorrelationForecast]] = {}
        alerts: list[str] = []

        for asset in self.assets:
            if asset not in asset_returns or asset not in self._models:
                continue

            asset_forecasts: list[CorrelationForecast] = []

            # Get current features
            try:
                current_features = self.feature_builder.get_current_features(
                    asset_returns[asset], liquidity_returns, asset
                )
            except Exception as e:
                logger.warning(f"Failed to get features for {asset}: {e}")
                continue

            # Prepare feature array
            X = np.array(
                [
                    [
                        current_features.current_corr_30d,
                        current_features.corr_momentum,
                        current_features.corr_acceleration,
                        current_features.zscore,
                    ]
                ]
            )

            if asset not in self._scalers:
                continue

            X_scaled: NDArray[np.float64] = np.asarray(
                self._scalers[asset].transform(X), dtype=np.float64
            )

            for horizon in self.HORIZONS:
                if horizon not in self._models[asset]:
                    continue

                predicted_corr = float(self._models[asset][horizon].predict(X_scaled)[0])
                change = predicted_corr - current_features.current_corr_30d

                # Classify direction
                if change > self.STRENGTHEN_THRESHOLD:
                    direction = TrendDirection.STRENGTHENING
                elif change < self.WEAKEN_THRESHOLD:
                    direction = TrendDirection.WEAKENING
                else:
                    direction = TrendDirection.STABLE

                # Check for alert
                if abs(change) > self.ALERT_THRESHOLD:
                    verb = "increase" if change > 0 else "decrease"
                    alerts.append(
                        f"{asset}: Correlation expected to {verb} "
                        f"by {abs(change):.2f} over {horizon}d"
                    )

                asset_forecasts.append(
                    CorrelationForecast(
                        asset=asset,
                        horizon=horizon,
                        predicted_corr=predicted_corr,
                        direction=direction,
                        confidence=self._estimate_confidence(X_scaled, horizon),
                        current_corr=current_features.current_corr_30d,
                        change=change,
                    )
                )

            forecasts[asset] = asset_forecasts

        # Compute breakdown risks
        breakdown_risks = self.get_correlation_breakdown_risk(
            asset_returns, liquidity_returns
        )

        return CorrelationTrendReport(
            timestamp=pd.Timestamp.now(),
            forecasts=forecasts,
            alerts=alerts,
            breakdown_risks=breakdown_risks,
        )

    def get_correlation_breakdown_risk(
        self,
        asset_returns: dict[str, pd.Series],
        liquidity_returns: pd.Series,
    ) -> dict[str, float]:
        """Calculate risk of correlation breakdown for each asset.

        High risk indicates correlation likely to flip sign or collapse.

        Args:
            asset_returns: Dict of asset name -> daily returns.
            liquidity_returns: Net Liquidity daily returns.

        Returns:
            Dict mapping asset to breakdown risk (0-1).
        """
        risks: dict[str, float] = {}

        for asset in self.assets:
            if asset not in asset_returns:
                continue

            try:
                features = self.feature_builder.get_current_features(
                    asset_returns[asset], liquidity_returns, asset
                )
            except Exception:
                continue

            # Risk factors
            # 1. Current correlation near zero (unstable)
            zero_risk = float(np.exp(-abs(features.current_corr_30d) * 3))

            # 2. High acceleration (rapid change)
            accel_risk = min(abs(features.corr_acceleration) * 5, 1.0)

            # 3. Divergence between 30d and 90d (mean reversion pressure)
            divergence = abs(features.current_corr_30d - features.current_corr_90d)
            divergence_risk = min(divergence * 2, 1.0)

            # Combined risk (average)
            risks[asset] = (zero_risk + accel_risk + divergence_risk) / 3

        return risks

    def _estimate_confidence(
        self, X: NDArray[np.float64], horizon: int
    ) -> float:
        """Estimate prediction confidence.

        Confidence decreases with:
        - Longer horizons
        - More unusual observations (high z-score)

        Args:
            X: Scaled feature array.
            horizon: Forecast horizon in days.

        Returns:
            Confidence score (0-1).
        """
        # Base confidence decreases with horizon
        base = float(np.exp(-horizon / 30))

        # Reduce for outlier observations (z-score is 4th feature)
        zscore = abs(X[0, 3])
        zscore_penalty = float(np.exp(-zscore / 3))

        return min(base * zscore_penalty, 0.95)
