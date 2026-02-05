"""Correlation trend prediction module.

Provides tools for predicting the direction of cross-asset correlations
with Net Liquidity for portfolio adjustment decisions.

Key components:
- CorrelationFeatureBuilder: Compute rolling correlation features
- CorrelationTrendPredictor: Predict correlation direction
- TrendDirection: Enum for trend classification

Example:
    from liquidity.nowcasting.correlation import (
        CorrelationTrendPredictor,
        TrendDirection,
    )

    predictor = CorrelationTrendPredictor()
    predictor.fit(asset_returns, liquidity_returns)
    report = predictor.predict(asset_returns, liquidity_returns)

    for asset, forecasts in report.forecasts.items():
        print(f"{asset}: {forecasts[0].direction.value}")
"""

from liquidity.nowcasting.correlation.features import (
    CorrelationFeatureBuilder,
    CorrelationFeatures,
    TrendDirection,
)
from liquidity.nowcasting.correlation.trend_predictor import (
    CorrelationForecast,
    CorrelationTrendPredictor,
    CorrelationTrendReport,
)

__all__ = [
    "CorrelationFeatureBuilder",
    "CorrelationFeatures",
    "CorrelationForecast",
    "CorrelationTrendPredictor",
    "CorrelationTrendReport",
    "TrendDirection",
]
