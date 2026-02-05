"""MIDAS feature engineering module.

This module provides feature engineering for Mixed-Data Sampling (MIDAS)
regression models. The key insight is to preserve high-frequency information
when predicting low-frequency targets, rather than averaging HF data to LF.

Almon polynomial distributed lags give more weight to recent observations
while still incorporating information from older lags.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class MIDASFeatures:
    """Feature engineering for MIDAS regression.

    Key insight: Don't average HF data to LF. Instead, use polynomial
    distributed lags to preserve daily information in monthly model.

    The Almon polynomial weighting scheme gives exponentially decaying
    weights to lagged observations, allowing recent data to contribute
    more while still incorporating historical information.

    Example:
        >>> features = MIDASFeatures()
        >>> X, names = features.create_midas_features(
        ...     daily_series=shibor,
        ...     weekly_series=dr007,
        ...     spread_series=cny_cnh,
        ...     n_daily_lags=30,
        ...     n_weekly_lags=4,
        ... )
    """

    DEFAULT_DECAY = 30.0
    DEFAULT_DAILY_LAGS = 30
    DEFAULT_WEEKLY_LAGS = 4

    @staticmethod
    def almon_weights(n_lags: int, decay: float = 30.0) -> NDArray[np.float64]:
        """Compute Almon polynomial weighting scheme.

        Gives more weight to recent observations, decaying exponentially.
        The weights sum to 1 for interpretability.

        Formula: w(i) = exp(-(i^2) / decay) / sum(weights)

        Args:
            n_lags: Number of lag periods.
            decay: Decay parameter controlling weight falloff.
                   Smaller values = faster decay (more weight on recent obs).
                   Default 30.0 gives moderate decay over ~20-30 lags.

        Returns:
            Normalized weight array of shape (n_lags,).

        Raises:
            ValueError: If n_lags < 1 or decay <= 0.

        Example:
            >>> weights = MIDASFeatures.almon_weights(10, decay=30.0)
            >>> weights.sum()  # Should be 1.0
            1.0
            >>> weights[0] > weights[-1]  # Recent obs weighted higher
            True
        """
        if n_lags < 1:
            raise ValueError(f"n_lags must be >= 1, got {n_lags}")
        if decay <= 0:
            raise ValueError(f"decay must be > 0, got {decay}")

        lags = np.arange(1, n_lags + 1, dtype=np.float64)
        weights = np.exp(-(lags**2) / decay)
        return weights / weights.sum()

    @staticmethod
    def exponential_weights(n_lags: int, half_life: float = 10.0) -> NDArray[np.float64]:
        """Compute exponential weighting scheme (alternative to Almon).

        Uses standard exponential decay: w(i) = lambda^i where lambda < 1.

        Args:
            n_lags: Number of lag periods.
            half_life: Number of periods for weight to halve.
                       Default 10.0 means weight halves every 10 periods.

        Returns:
            Normalized weight array of shape (n_lags,).

        Raises:
            ValueError: If n_lags < 1 or half_life <= 0.
        """
        if n_lags < 1:
            raise ValueError(f"n_lags must be >= 1, got {n_lags}")
        if half_life <= 0:
            raise ValueError(f"half_life must be > 0, got {half_life}")

        decay_factor = 0.5 ** (1 / half_life)
        lags = np.arange(1, n_lags + 1, dtype=np.float64)
        weights = decay_factor**lags
        return weights / weights.sum()

    def create_midas_features(
        self,
        daily_series: pd.Series,
        weekly_series: pd.Series,
        spread_series: pd.Series | None = None,
        n_daily_lags: int = 30,
        n_weekly_lags: int = 4,
        daily_decay: float = 30.0,
        include_level_features: bool = True,
        include_change_features: bool = True,
    ) -> tuple[pd.DataFrame, list[str]]:
        """Create MIDAS feature matrix from high-frequency inputs.

        Creates weighted lag features from daily and weekly series,
        preserving high-frequency information for monthly prediction.

        Args:
            daily_series: Daily frequency series (e.g., SHIBOR O/N).
            weekly_series: Weekly frequency series (e.g., DR007).
            spread_series: Optional spread series (e.g., CNY-CNH spread).
            n_daily_lags: Number of daily lags to include. Default 30.
            n_weekly_lags: Number of weekly lags to include. Default 4.
            daily_decay: Almon decay parameter for daily weights. Default 30.0.
            include_level_features: Include level features. Default True.
            include_change_features: Include change (delta) features. Default True.

        Returns:
            Tuple of (features DataFrame, feature names list).

        Example:
            >>> features = MIDASFeatures()
            >>> X, names = features.create_midas_features(
            ...     daily_series=shibor_overnight,
            ...     weekly_series=dr007,
            ...     spread_series=cny_cnh_spread,
            ... )
            >>> X.shape[1]  # Number of features
            70  # 30 daily + 4 weekly + 1 spread + aggregates
        """
        feature_dict: dict[str, pd.Series] = {}
        feature_names: list[str] = []

        # Align all series to common daily index
        all_dates = daily_series.index.union(weekly_series.index)
        if spread_series is not None:
            all_dates = all_dates.union(spread_series.index)

        # Forward-fill to handle missing daily observations
        daily_aligned = daily_series.reindex(all_dates).ffill()
        weekly_aligned = weekly_series.reindex(all_dates).ffill()

        if spread_series is not None:
            spread_aligned = spread_series.reindex(all_dates).ffill()
        else:
            spread_aligned = None

        # ----- DAILY LAGS WITH ALMON WEIGHTING -----
        if include_level_features:
            daily_weights = self.almon_weights(n_daily_lags, daily_decay)
            for i in range(1, n_daily_lags + 1):
                feat_name = f"daily_lag_{i}"
                # Weight applied at feature creation - preserves temporal info
                feature_dict[feat_name] = daily_aligned.shift(i) * daily_weights[i - 1]
                feature_names.append(feat_name)

        # Weighted sum of all daily lags (aggregate feature)
        if include_level_features and n_daily_lags > 0:
            daily_weights_full = self.almon_weights(n_daily_lags, daily_decay)
            weighted_sum = pd.Series(0.0, index=all_dates)
            for i in range(1, n_daily_lags + 1):
                weighted_sum += daily_aligned.shift(i) * daily_weights_full[i - 1]
            feature_dict["daily_weighted_sum"] = weighted_sum
            feature_names.append("daily_weighted_sum")

        # ----- WEEKLY LAGS -----
        if include_level_features:
            for j in range(1, n_weekly_lags + 1):
                lag_days = j * 5  # Approximate weekly to daily
                feat_name = f"weekly_lag_{j}"
                feature_dict[feat_name] = weekly_aligned.shift(lag_days)
                feature_names.append(feat_name)

        # Weighted sum of weekly lags
        if include_level_features and n_weekly_lags > 0:
            weekly_weights = self.almon_weights(n_weekly_lags, decay=5.0)
            weighted_weekly = pd.Series(0.0, index=all_dates)
            for j in range(1, n_weekly_lags + 1):
                lag_days = j * 5
                weighted_weekly += weekly_aligned.shift(lag_days) * weekly_weights[j - 1]
            feature_dict["weekly_weighted_sum"] = weighted_weekly
            feature_names.append("weekly_weighted_sum")

        # ----- SPREAD FEATURE -----
        if spread_aligned is not None and include_level_features:
            feature_dict["spread"] = spread_aligned
            feature_names.append("spread")

            # Rolling average spread
            feature_dict["spread_ma5"] = spread_aligned.rolling(5, min_periods=1).mean()
            feature_names.append("spread_ma5")

        # ----- CHANGE FEATURES -----
        if include_change_features:
            # Daily change (momentum)
            feature_dict["daily_change_1d"] = daily_aligned.diff(1)
            feature_names.append("daily_change_1d")

            feature_dict["daily_change_5d"] = daily_aligned.diff(5)
            feature_names.append("daily_change_5d")

            feature_dict["daily_change_20d"] = daily_aligned.diff(20)
            feature_names.append("daily_change_20d")

            # Weekly change
            feature_dict["weekly_change_1w"] = weekly_aligned.diff(5)
            feature_names.append("weekly_change_1w")

            # Volatility features
            feature_dict["daily_volatility_5d"] = daily_aligned.rolling(5, min_periods=1).std()
            feature_names.append("daily_volatility_5d")

            feature_dict["daily_volatility_20d"] = daily_aligned.rolling(20, min_periods=1).std()
            feature_names.append("daily_volatility_20d")

        # Build DataFrame
        features_df = pd.DataFrame(feature_dict, index=all_dates)
        features_df.columns = list(feature_dict.keys())

        logger.info(
            "Created MIDAS features: %d features, %d observations",
            len(feature_names),
            len(features_df),
        )

        return features_df, feature_names

    def create_aggregated_features(
        self,
        daily_series: pd.Series,
        weekly_series: pd.Series,
        spread_series: pd.Series | None = None,
        resample_freq: str = "ME",
    ) -> tuple[pd.DataFrame, list[str]]:
        """Create aggregated features at target frequency.

        Alternative to full lag expansion - creates summary statistics
        aggregated to the target frequency (e.g., monthly).

        Args:
            daily_series: Daily frequency series.
            weekly_series: Weekly frequency series.
            spread_series: Optional spread series.
            resample_freq: Target frequency for aggregation. Default "ME" (month-end).

        Returns:
            Tuple of (features DataFrame, feature names list).
        """
        feature_dict: dict[str, pd.Series] = {}
        feature_names: list[str] = []

        # Daily aggregates
        daily_grouped = daily_series.resample(resample_freq)
        feature_dict["daily_mean"] = daily_grouped.mean()
        feature_dict["daily_std"] = daily_grouped.std()
        feature_dict["daily_min"] = daily_grouped.min()
        feature_dict["daily_max"] = daily_grouped.max()
        feature_dict["daily_last"] = daily_grouped.last()
        feature_dict["daily_range"] = feature_dict["daily_max"] - feature_dict["daily_min"]
        feature_names.extend(
            ["daily_mean", "daily_std", "daily_min", "daily_max", "daily_last", "daily_range"]
        )

        # Weekly aggregates
        weekly_grouped = weekly_series.resample(resample_freq)
        feature_dict["weekly_mean"] = weekly_grouped.mean()
        feature_dict["weekly_std"] = weekly_grouped.std()
        feature_dict["weekly_last"] = weekly_grouped.last()
        feature_names.extend(["weekly_mean", "weekly_std", "weekly_last"])

        # Spread aggregates
        if spread_series is not None:
            spread_grouped = spread_series.resample(resample_freq)
            feature_dict["spread_mean"] = spread_grouped.mean()
            feature_dict["spread_std"] = spread_grouped.std()
            feature_dict["spread_last"] = spread_grouped.last()
            feature_names.extend(["spread_mean", "spread_std", "spread_last"])

        # Build DataFrame
        features_df = pd.DataFrame(feature_dict)

        logger.info(
            "Created aggregated features: %d features, %d observations",
            len(feature_names),
            len(features_df),
        )

        return features_df, feature_names
