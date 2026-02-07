"""Kalman filter nowcaster for Net Liquidity using state-space models.

This module provides a state-space model implementation using statsmodels
UnobservedComponents for nowcasting Net Liquidity before official Fed releases.

The model uses a local linear trend specification:
    State equation:
        level_t = level_{t-1} + trend_{t-1} + eta_t  (level disturbance)
        trend_t = trend_{t-1} + zeta_t               (trend disturbance)

    Observation equation:
        y_t = level_t + epsilon_t                    (measurement noise)

Ragged edge handling:
    Missing observations (NaN) are handled natively by the Kalman filter.
    The filter simply skips the update step when observations are missing,
    propagating uncertainty forward.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.structural import UnobservedComponents

if TYPE_CHECKING:
    from statsmodels.tsa.statespace.structural import (
        UnobservedComponentsResults,
    )

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NowcastResult:
    """Result of liquidity nowcast.

    Attributes:
        timestamp: Timestamp of the nowcast.
        mean: Point estimate of Net Liquidity.
        std: Standard deviation of the estimate.
        ci_lower: Lower bound of 95% confidence interval.
        ci_upper: Upper bound of 95% confidence interval.
        kalman_gain: Kalman gain matrix from last update (for diagnostics).
        innovation: Prediction error (forecast - observation) from last update.
        filtered_state: Current filtered state estimate [level, trend].
        n_missing: Number of missing observations in the data.
    """

    timestamp: pd.Timestamp
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    kalman_gain: np.ndarray
    innovation: float
    filtered_state: np.ndarray
    n_missing: int = 0

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"NowcastResult(timestamp={self.timestamp}, "
            f"mean={self.mean:.2f}, "
            f"ci=[{self.ci_lower:.2f}, {self.ci_upper:.2f}], "
            f"std={self.std:.2f})"
        )

    @property
    def ci_width(self) -> float:
        """Width of the confidence interval."""
        return self.ci_upper - self.ci_lower

    @property
    def level(self) -> float:
        """Current level from filtered state."""
        return float(self.filtered_state[0])

    @property
    def trend(self) -> float:
        """Current trend from filtered state (if available)."""
        if len(self.filtered_state) > 1:
            return float(self.filtered_state[1])
        return 0.0


class LiquidityStateSpace:
    """Kalman filter nowcaster for Net Liquidity.

    Uses statsmodels UnobservedComponents with local linear trend.
    Handles ragged edge (mixed frequency) via NaN for missing observations.

    The model decomposes the liquidity series into:
    - Level: Current underlying liquidity level
    - Trend: Direction and rate of change
    - Irregular: Noise component

    Example:
        import pandas as pd
        from liquidity.nowcasting.kalman import LiquidityStateSpace

        # Historical Net Liquidity data (weekly, with some gaps)
        data = pd.Series([5.1, 5.2, np.nan, 5.4, 5.3, ...], index=dates)

        # Fit and nowcast
        model = LiquidityStateSpace()
        model.fit(data)
        result = model.nowcast(steps=5)  # 5 days ahead

        print(f"Net Liquidity nowcast: {result.mean:.2f}T")
        print(f"95% CI: [{result.ci_lower:.2f}, {result.ci_upper:.2f}]T")
    """

    def __init__(
        self,
        level: Literal["local level", "dconstant", "llevel"] = "local level",
        trend: Literal[
            "local linear trend", "dtrend", "lltrend", "random walk", None
        ] = "local linear trend",
        seasonal: int | None = None,
        freq_seasonal: list[dict[str, int]] | None = None,
        autoregressive: int | None = None,
        irregular: bool = True,
    ) -> None:
        """Initialize the state-space model.

        Args:
            level: Level component specification. Options:
                - "local level" (default): Random walk level
                - "dconstant": Deterministic constant
                - "llevel": Local level (alias)
            trend: Trend component specification. Options:
                - "local linear trend" (default): Random walk level and trend
                - "dtrend": Deterministic trend
                - "lltrend": Local linear trend (alias)
                - "random walk": Random walk without trend
                - None: No trend component
            seasonal: Period of seasonal component (None for no seasonality).
            freq_seasonal: List of dicts for stochastic frequency seasonality.
            autoregressive: Order of AR component (None for no AR).
            irregular: Whether to include irregular component.
        """
        self.level = level
        self.trend = trend
        self.seasonal = seasonal
        self.freq_seasonal = freq_seasonal
        self.autoregressive = autoregressive
        self.irregular = irregular

        self._model: UnobservedComponents | None = None
        self._results: UnobservedComponentsResults | None = None
        self._endog: pd.Series | None = None

    @property
    def is_fitted(self) -> bool:
        """Check if the model has been fitted."""
        return self._results is not None

    def fit(
        self,
        endog: pd.Series,
        maxiter: int = 500,
        disp: bool = False,
        **kwargs: object,
    ) -> LiquidityStateSpace:
        """Fit the model on historical data.

        Args:
            endog: Time series of Net Liquidity values.
                   Index should be DatetimeIndex.
                   NaN values are handled as missing observations.
            maxiter: Maximum iterations for optimizer.
            disp: Whether to display optimizer output.
            **kwargs: Additional arguments passed to model.fit().

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If endog is empty or has no valid observations.
        """
        if endog.empty:
            raise ValueError("Cannot fit on empty series")

        n_valid = endog.notna().sum()
        if n_valid < 10:
            raise ValueError(
                f"Insufficient data: need at least 10 valid observations, got {n_valid}"
            )

        # Store original data
        self._endog = endog.copy()

        # Create the model
        self._model = UnobservedComponents(
            endog=endog,
            level=self.level,
            trend=self.trend if self.trend != "random walk" else None,
            seasonal=self.seasonal,
            freq_seasonal=self.freq_seasonal,
            autoregressive=self.autoregressive,
            irregular=self.irregular,
            stochastic_level=self.trend != "random walk",
            stochastic_trend=self.trend == "local linear trend",
        )

        # Fit with MLE
        self._results = self._model.fit(
            maxiter=maxiter,
            disp=disp,
            **kwargs,
        )

        n_missing = endog.isna().sum()
        logger.info(
            "LiquidityStateSpace fitted: %d observations (%d missing), "
            "AIC=%.2f, BIC=%.2f",
            len(endog),
            n_missing,
            self._results.aic,
            self._results.bic,
        )

        return self

    def nowcast(self, steps: int = 1, alpha: float = 0.05) -> NowcastResult:
        """Generate nowcast for next `steps` periods.

        Args:
            steps: Number of steps ahead to forecast.
            alpha: Significance level for confidence intervals (default 0.05 = 95% CI).

        Returns:
            NowcastResult with point estimate and confidence intervals.

        Raises:
            ValueError: If model not fitted.
        """
        if self._results is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Get forecast
        forecast = self._results.get_forecast(steps=steps)
        mean = float(forecast.predicted_mean.iloc[-1])
        se = float(forecast.se_mean.iloc[-1])

        # Get confidence intervals
        ci = forecast.conf_int(alpha=alpha).iloc[-1]

        # Get Kalman filter results
        filter_results = self._results.filter_results
        kalman_gain = filter_results.kalman_gain[:, :, -1].copy()

        # Get innovation (prediction error) from last observation
        forecasts_error = filter_results.forecasts_error
        innovation = float(forecasts_error[0, -1]) if forecasts_error.size > 0 else 0.0

        # Get filtered state
        filtered_state = filter_results.filtered_state[:, -1].copy()

        # Calculate timestamp for forecast
        if isinstance(self._endog.index, pd.DatetimeIndex):
            last_date = self._endog.index[-1]
            # Assume business day frequency for liquidity data
            forecast_date = last_date + pd.Timedelta(days=steps)
        else:
            forecast_date = pd.Timestamp.now()

        n_missing = int(self._endog.isna().sum()) if self._endog is not None else 0

        return NowcastResult(
            timestamp=forecast_date,
            mean=mean,
            std=se,
            ci_lower=float(ci.iloc[0]),
            ci_upper=float(ci.iloc[1]),
            kalman_gain=kalman_gain,
            innovation=innovation,
            filtered_state=filtered_state,
            n_missing=n_missing,
        )

    def predict_in_sample(self) -> pd.DataFrame:
        """Get in-sample predictions and filtered states.

        Returns:
            DataFrame with columns:
            - observed: Original observations
            - predicted: In-sample predictions
            - level: Filtered level component
            - trend: Filtered trend component (if applicable)
            - residual: Prediction residuals

        Raises:
            ValueError: If model not fitted.
        """
        if self._results is None or self._endog is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Get in-sample predictions
        predicted = self._results.fittedvalues

        # Get filtered components
        level = self._results.level.filtered
        trend = getattr(self._results, "trend", None)
        trend_values = trend.filtered if trend is not None else pd.Series(
            0.0, index=self._endog.index
        )

        # Build result DataFrame
        result = pd.DataFrame(
            {
                "observed": self._endog,
                "predicted": predicted,
                "level": level,
                "trend": trend_values,
                "residual": self._endog - predicted,
            },
            index=self._endog.index,
        )

        return result

    def update(
        self,
        new_observation: float | None,
        timestamp: pd.Timestamp | None = None,
    ) -> NowcastResult:
        """Update filter with new observation and return updated nowcast.

        Note: statsmodels doesn't support true online updating, so we
        extend the data and refit. For high-frequency updates, consider
        using filterpy directly.

        Args:
            new_observation: New observation value (use None or NaN for missing).
            timestamp: Timestamp for new observation (optional).

        Returns:
            Updated NowcastResult.

        Raises:
            ValueError: If model not fitted.
        """
        if self._results is None or self._endog is None:
            raise ValueError("Model not fitted. Call fit() first.")

        # Extend the series
        if timestamp is None:
            last_date = self._endog.index[-1]
            if isinstance(last_date, pd.Timestamp):
                timestamp = last_date + pd.Timedelta(days=1)
            else:
                timestamp = pd.Timestamp.now()

        # Create new observation (NaN if missing)
        obs_value = new_observation if new_observation is not None else np.nan

        # Extend series
        new_series = pd.concat([
            self._endog,
            pd.Series([obs_value], index=[timestamp]),
        ])

        # Refit model
        self.fit(new_series)

        # Return nowcast
        return self.nowcast(steps=1)

    def get_smoothed_state(self) -> pd.DataFrame:
        """Get smoothed state estimates (uses all data, not just past).

        Smoothed estimates use information from the entire sample,
        providing better estimates for historical values but not
        suitable for real-time nowcasting.

        Returns:
            DataFrame with smoothed level and trend.

        Raises:
            ValueError: If model not fitted.
        """
        if self._results is None or self._endog is None:
            raise ValueError("Model not fitted. Call fit() first.")

        level_smoothed = self._results.level.smoothed
        trend = getattr(self._results, "trend", None)
        trend_smoothed = trend.smoothed if trend is not None else pd.Series(
            0.0, index=self._endog.index
        )

        return pd.DataFrame(
            {
                "level_smoothed": level_smoothed,
                "trend_smoothed": trend_smoothed,
            },
            index=self._endog.index,
        )

    def get_diagnostics(self) -> dict[str, float]:
        """Get model diagnostic statistics.

        Returns:
            Dictionary with diagnostic metrics:
            - aic: Akaike Information Criterion
            - bic: Bayesian Information Criterion
            - llf: Log-likelihood
            - mse: Mean squared error of residuals
            - mae: Mean absolute error of residuals
            - durbin_watson: Durbin-Watson statistic for residual autocorrelation

        Raises:
            ValueError: If model not fitted.
        """
        if self._results is None:
            raise ValueError("Model not fitted. Call fit() first.")

        resid = self._results.resid.dropna()

        # Durbin-Watson statistic
        diff_resid = np.diff(resid)
        dw = float(np.sum(diff_resid**2) / np.sum(resid**2))

        return {
            "aic": float(self._results.aic),
            "bic": float(self._results.bic),
            "llf": float(self._results.llf),
            "mse": float(np.mean(resid**2)),
            "mae": float(np.mean(np.abs(resid))),
            "durbin_watson": dw,
        }

    def __repr__(self) -> str:
        """Return string representation."""
        status = "fitted" if self.is_fitted else "not fitted"
        return (
            f"LiquidityStateSpace(level={self.level!r}, trend={self.trend!r}, "
            f"status={status})"
        )
