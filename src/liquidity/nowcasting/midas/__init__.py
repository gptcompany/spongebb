"""MIDAS (Mixed-Data Sampling) regression module.

Provides tools for estimating low-frequency variables (e.g., monthly PBoC assets)
from high-frequency predictors (e.g., daily SHIBOR, weekly DR007).

Key components:
- MIDASFeatures: Feature engineering with Almon polynomial weighting
- PBoCEstimator: MIDAS regression estimator for PBoC balance sheet
- PBoCEstimate: Dataclass for estimation results with uncertainty bounds
"""

from liquidity.nowcasting.midas.features import MIDASFeatures
from liquidity.nowcasting.midas.pboc_estimator import PBoCEstimate, PBoCEstimator

__all__ = [
    "MIDASFeatures",
    "PBoCEstimate",
    "PBoCEstimator",
]
