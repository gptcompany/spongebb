"""Correlation feature computation for trend prediction.

Provides rolling correlation features with momentum and z-score indicators
for predicting correlation direction changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    pass


class TrendDirection(Enum):
    """Correlation trend direction."""

    STRENGTHENING = "strengthening"
    STABLE = "stable"
    WEAKENING = "weakening"


@dataclass
class CorrelationFeatures:
    """Features for correlation prediction.

    Attributes:
        asset: Asset name.
        current_corr_30d: Current 30-day rolling correlation.
        current_corr_90d: Current 90-day rolling correlation.
        corr_momentum: 30-day change in correlation.
        corr_acceleration: Change in momentum (second derivative).
        ewma_corr: EWMA smoothed correlation.
        zscore: How unusual current correlation is vs historical.
    """

    asset: str
    current_corr_30d: float
    current_corr_90d: float
    corr_momentum: float
    corr_acceleration: float
    ewma_corr: float
    zscore: float

    def as_array(self) -> np.ndarray:
        """Return features as numpy array for model input."""
        return np.array(
            [
                self.current_corr_30d,
                self.current_corr_90d,
                self.corr_momentum,
                self.corr_acceleration,
                self.ewma_corr,
                self.zscore,
            ],
            dtype=np.float64,
        )


class CorrelationFeatureBuilder:
    """Build features for correlation trend prediction.

    Computes rolling correlations, momentum, and z-scores for
    predicting correlation direction changes.

    Example:
        builder = CorrelationFeatureBuilder()
        features_df = builder.compute_features(
            asset_returns, liquidity_returns, "BTC"
        )
    """

    def __init__(
        self,
        short_window: int = 30,
        long_window: int = 90,
        ewma_span: int = 20,
        zscore_window: int = 252,
    ):
        """Initialize feature builder.

        Args:
            short_window: Short rolling window for correlation (days).
            long_window: Long rolling window for correlation (days).
            ewma_span: EWMA span for smoothing.
            zscore_window: Window for z-score computation.
        """
        self.short_window = short_window
        self.long_window = long_window
        self.ewma_span = ewma_span
        self.zscore_window = zscore_window

    def compute_features(
        self,
        asset_returns: pd.Series,
        liquidity_returns: pd.Series,
        asset_name: str,
    ) -> pd.DataFrame:
        """Compute correlation features over time.

        Args:
            asset_returns: Daily returns of asset (e.g., BTC, SPX).
            liquidity_returns: Daily returns of Net Liquidity.
            asset_name: Name for labeling columns.

        Returns:
            DataFrame with correlation features at each timestamp.
        """
        # Align series
        aligned = pd.DataFrame(
            {"asset": asset_returns, "liquidity": liquidity_returns}
        ).dropna()

        asset_ret = aligned["asset"]
        liq_ret = aligned["liquidity"]

        # Rolling correlations
        corr_30d = asset_ret.rolling(self.short_window).corr(liq_ret)
        corr_90d = asset_ret.rolling(self.long_window).corr(liq_ret)

        # Momentum features (change over time)
        corr_momentum = corr_30d.diff(periods=self.short_window)
        corr_acceleration = corr_momentum.diff(periods=10)

        # EWMA smoothing
        ewma_corr = corr_30d.ewm(span=self.ewma_span).mean()

        # Z-score (how unusual is current correlation)
        corr_mean = corr_30d.rolling(self.zscore_window).mean()
        corr_std = corr_30d.rolling(self.zscore_window).std()
        zscore = (corr_30d - corr_mean) / (corr_std + 1e-8)

        return pd.DataFrame(
            {
                f"{asset_name}_corr_30d": corr_30d,
                f"{asset_name}_corr_90d": corr_90d,
                f"{asset_name}_momentum": corr_momentum,
                f"{asset_name}_acceleration": corr_acceleration,
                f"{asset_name}_ewma": ewma_corr,
                f"{asset_name}_zscore": zscore,
            }
        )

    def get_current_features(
        self,
        asset_returns: pd.Series,
        liquidity_returns: pd.Series,
        asset_name: str,
    ) -> CorrelationFeatures:
        """Get features for latest observation.

        Args:
            asset_returns: Daily returns of asset.
            liquidity_returns: Daily returns of Net Liquidity.
            asset_name: Asset name.

        Returns:
            CorrelationFeatures for the most recent timestamp.
        """
        features_df = self.compute_features(asset_returns, liquidity_returns, asset_name)
        latest = features_df.iloc[-1]

        return CorrelationFeatures(
            asset=asset_name,
            current_corr_30d=float(latest[f"{asset_name}_corr_30d"]),
            current_corr_90d=float(latest[f"{asset_name}_corr_90d"]),
            corr_momentum=float(latest[f"{asset_name}_momentum"]),
            corr_acceleration=float(latest[f"{asset_name}_acceleration"]),
            ewma_corr=float(latest[f"{asset_name}_ewma"]),
            zscore=float(latest[f"{asset_name}_zscore"]),
        )

    def compute_all_assets(
        self,
        asset_returns: dict[str, pd.Series],
        liquidity_returns: pd.Series,
    ) -> pd.DataFrame:
        """Compute features for all assets.

        Args:
            asset_returns: Dict of asset name -> returns series.
            liquidity_returns: Net Liquidity returns.

        Returns:
            Combined DataFrame with features for all assets.
        """
        dfs = []
        for asset_name, returns in asset_returns.items():
            df = self.compute_features(returns, liquidity_returns, asset_name)
            dfs.append(df)

        if not dfs:
            return pd.DataFrame()

        return pd.concat(dfs, axis=1)
