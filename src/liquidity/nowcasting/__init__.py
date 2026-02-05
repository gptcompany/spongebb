"""Nowcasting module for Net Liquidity estimation.

This module provides Kalman filter-based nowcasting for estimating current
Net Liquidity before official Fed releases using high-frequency proxies.

Key components:
- LiquidityStateSpace: Kalman filter state-space model
- NowcastEngine: Daily nowcast pipeline orchestrator
- NowcastResult: Dataclass for nowcast outputs with confidence intervals
- KalmanTuner: Parameter estimation for noise matrices
- MIDASFeatures: MIDAS feature engineering with Almon polynomial weighting
- PBoCEstimator: MIDAS regression estimator for PBoC balance sheet
- PBoCEstimate: Dataclass for PBoC estimation results with uncertainty bounds

Example:
    from liquidity.nowcasting import NowcastEngine, LiquidityStateSpace

    # Fit model on historical data
    model = LiquidityStateSpace()
    model.fit(historical_net_liquidity)

    # Generate nowcast
    result = model.nowcast(steps=1)
    print(f"Nowcast: {result.mean:.2f} +/- {result.std:.2f}")

    # PBoC estimation example
    from liquidity.nowcasting import PBoCEstimator

    estimator = PBoCEstimator()
    estimator.fit(shibor_daily, dr007_weekly, spread, pboc_monthly)
    estimate = estimator.estimate(shibor_daily, dr007_weekly, spread)
    print(f"PBoC estimate: {estimate.estimate:.2f} +/- {estimate.std:.2f} trillion CNY")
"""

from liquidity.nowcasting.correlation import (
    CorrelationFeatureBuilder,
    CorrelationTrendPredictor,
    CorrelationTrendReport,
    TrendDirection,
)
from liquidity.nowcasting.engine import NowcastEngine
from liquidity.nowcasting.kalman import KalmanTuner, LiquidityStateSpace, NowcastResult
from liquidity.nowcasting.midas import MIDASFeatures, PBoCEstimate, PBoCEstimator
from liquidity.nowcasting.regime import (
    HMMRegimeClassifier,
    LSTMRegimeForecaster,
    MarkovSwitchingClassifier,
    RegimeEnsemble,
    RegimeProbabilities,
    RegimeState,
)

__all__ = [
    # Correlation
    "CorrelationFeatureBuilder",
    "CorrelationTrendPredictor",
    "CorrelationTrendReport",
    "TrendDirection",
    # Engine
    "NowcastEngine",
    # Kalman
    "KalmanTuner",
    "LiquidityStateSpace",
    "NowcastResult",
    # MIDAS
    "MIDASFeatures",
    "PBoCEstimate",
    "PBoCEstimator",
    # Regime
    "HMMRegimeClassifier",
    "LSTMRegimeForecaster",
    "MarkovSwitchingClassifier",
    "RegimeEnsemble",
    "RegimeProbabilities",
    "RegimeState",
]
