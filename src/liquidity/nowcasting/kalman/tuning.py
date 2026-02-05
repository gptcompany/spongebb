"""Parameter tuning for Kalman filter noise matrices.

This module provides heuristics for estimating process noise (Q) and
measurement noise (R) matrices for the liquidity nowcasting model.

Estimation approaches:
1. Measurement noise (R): Based on historical measurement errors
   - TGA typical error: +/- $0.5B
   - RRP typical error: +/- $1B
   - SOFR typical error: +/- 1bp

2. Process noise (Q): Based on innovation variance
   - Level noise: 5% of returns volatility (liquidity changes slowly)
   - Trend noise: Much smaller than level noise

These heuristics provide starting points; the MLE optimizer in statsmodels
will refine these estimates during model fitting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class NoiseEstimates:
    """Estimated noise parameters for Kalman filter.

    Attributes:
        measurement_noise: Diagonal of R matrix (measurement variances).
        process_noise_level: Variance for level state.
        process_noise_trend: Variance for trend state.
        signal_to_noise: Ratio of signal variance to measurement noise.
    """

    measurement_noise: np.ndarray
    process_noise_level: float
    process_noise_trend: float
    signal_to_noise: float

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"NoiseEstimates(R_diag={self.measurement_noise.tolist()}, "
            f"Q_level={self.process_noise_level:.4f}, "
            f"Q_trend={self.process_noise_trend:.6f}, "
            f"SNR={self.signal_to_noise:.2f})"
        )


class KalmanTuner:
    """Estimate Q (process noise) and R (measurement noise) matrices.

    Provides heuristic estimation methods for noise covariance matrices
    used in the Kalman filter. These serve as starting points for MLE
    optimization.

    Default measurement error assumptions (based on data source reliability):
    - TGA: +/- $0.5B (Treasury reports accurately)
    - RRP: +/- $1B (NY Fed reports accurately)
    - SOFR: +/- 1bp (highly precise)
    - VIX: +/- 0.5 points
    - WALCL: +/- $1B (weekly Fed release)

    Example:
        tuner = KalmanTuner()

        # Estimate from historical data
        estimates = tuner.estimate_from_data(historical_series)
        print(f"Recommended Q_level: {estimates.process_noise_level}")

        # Use domain knowledge for measurement noise
        R = tuner.estimate_measurement_noise()
        print(f"Measurement noise diagonal: {R}")
    """

    # Default measurement error standard deviations (in native units)
    DEFAULT_MEASUREMENT_ERRORS = {
        "TGA": 0.5,       # $0.5B
        "RRP": 1.0,       # $1B
        "SOFR": 0.01,     # 1bp
        "VIX": 0.5,       # 0.5 points
        "WALCL": 1.0,     # $1B
        "NET_LIQUIDITY": 2.0,  # $2B (composite)
    }

    # Process noise scaling factors
    LEVEL_NOISE_SCALE = 0.05    # 5% of volatility
    TREND_NOISE_SCALE = 0.001   # Trend changes very slowly

    def __init__(
        self,
        measurement_errors: dict[str, float] | None = None,
        level_noise_scale: float | None = None,
        trend_noise_scale: float | None = None,
    ) -> None:
        """Initialize the tuner.

        Args:
            measurement_errors: Override default measurement error assumptions.
                Keys are series names, values are standard deviations.
            level_noise_scale: Override level noise scaling factor.
            trend_noise_scale: Override trend noise scaling factor.
        """
        self._measurement_errors = {
            **self.DEFAULT_MEASUREMENT_ERRORS,
            **(measurement_errors or {}),
        }
        self._level_scale = level_noise_scale or self.LEVEL_NOISE_SCALE
        self._trend_scale = trend_noise_scale or self.TREND_NOISE_SCALE

    def estimate_measurement_noise(
        self,
        series_names: list[str] | None = None,
    ) -> np.ndarray:
        """Estimate measurement noise (R matrix diagonal).

        Uses predefined error assumptions based on data source reliability.

        Args:
            series_names: List of series to include. If None, uses
                ["TGA", "RRP", "SOFR"].

        Returns:
            Diagonal elements of R matrix (variances = std^2).
        """
        if series_names is None:
            series_names = ["TGA", "RRP", "SOFR"]

        variances = []
        for name in series_names:
            std = self._measurement_errors.get(name, 1.0)
            variances.append(std ** 2)
            logger.debug(
                "Measurement noise for %s: std=%.4f, var=%.6f",
                name, std, std ** 2
            )

        return np.array(variances)

    def estimate_process_noise(
        self,
        historical_data: pd.Series,
        detrend: bool = True,
    ) -> tuple[float, float]:
        """Estimate process noise (Q matrix) from innovation variance.

        The process noise represents how much the underlying state changes
        between observations. For liquidity data, this is typically small
        as central bank balance sheets change gradually.

        Args:
            historical_data: Time series of the target variable.
            detrend: Whether to detrend before computing volatility.

        Returns:
            Tuple of (level_variance, trend_variance).
        """
        # Remove NaN values
        data = historical_data.dropna()

        if len(data) < 20:
            logger.warning(
                "Insufficient data for process noise estimation "
                "(n=%d < 20), using defaults", len(data)
            )
            # Use conservative defaults based on typical liquidity volatility
            mean_level = abs(data.mean()) if len(data) > 0 else 5000.0
            return (mean_level * 0.01) ** 2, (mean_level * 0.001) ** 2

        # Compute returns/changes
        returns = data.pct_change().dropna()

        if detrend:
            # Remove linear trend from returns
            x = np.arange(len(returns))
            coeffs = np.polyfit(x, returns.values, 1)
            trend = np.polyval(coeffs, x)
            detrended = returns.values - trend
            volatility = float(np.std(detrended))
        else:
            volatility = float(returns.std())

        # Mean level for scaling
        mean_level = abs(data.mean())

        # Level noise: scaled by volatility and mean
        level_variance = (volatility * mean_level * self._level_scale) ** 2

        # Trend noise: much smaller (trend is persistent)
        trend_variance = (volatility * mean_level * self._trend_scale) ** 2

        logger.info(
            "Process noise estimated: level_var=%.4f, trend_var=%.6f "
            "(vol=%.4f%%, mean=%.2f)",
            level_variance, trend_variance, volatility * 100, mean_level
        )

        return level_variance, trend_variance

    def estimate_from_data(
        self,
        historical_data: pd.Series,
        series_name: str = "NET_LIQUIDITY",
    ) -> NoiseEstimates:
        """Estimate all noise parameters from historical data.

        Combines measurement noise assumptions with data-driven process
        noise estimation.

        Args:
            historical_data: Time series of the target variable.
            series_name: Name of the series for measurement noise lookup.

        Returns:
            NoiseEstimates with all parameters.
        """
        # Measurement noise
        measurement_var = self._measurement_errors.get(series_name, 2.0) ** 2
        measurement_noise = np.array([measurement_var])

        # Process noise
        level_var, trend_var = self.estimate_process_noise(historical_data)

        # Signal-to-noise ratio
        data = historical_data.dropna()
        if len(data) > 1:
            signal_var = float(data.var())
            snr = signal_var / measurement_var if measurement_var > 0 else 0.0
        else:
            snr = 0.0

        return NoiseEstimates(
            measurement_noise=measurement_noise,
            process_noise_level=level_var,
            process_noise_trend=trend_var,
            signal_to_noise=snr,
        )

    @staticmethod
    def estimate_from_residuals(
        residuals: pd.Series,
        lag: int = 1,
    ) -> tuple[float, float]:
        """Estimate noise from model residuals using autocorrelation.

        This method uses the autocorrelation structure of residuals to
        separate measurement noise from process noise.

        Args:
            residuals: Model residuals from initial fit.
            lag: Lag for autocorrelation computation.

        Returns:
            Tuple of (measurement_variance, process_variance).
        """
        resid = residuals.dropna()

        if len(resid) < lag + 10:
            logger.warning("Insufficient residuals for noise decomposition")
            var = float(resid.var()) if len(resid) > 1 else 1.0
            return var * 0.5, var * 0.5

        # Total variance
        total_var = float(resid.var())

        # Autocovariance at lag
        mean = resid.mean()
        autocov = float(
            ((resid.iloc[:-lag] - mean) * (resid.iloc[lag:].values - mean)).mean()
        )

        # Autocorrelation
        autocorr = autocov / total_var if total_var > 0 else 0

        # Decomposition (based on AR(1) assumption)
        # If residuals are AR(1): r_t = phi * r_{t-1} + e_t
        # Then: process_var = phi * total_var, measurement_var = (1 - phi) * total_var
        phi = max(0, min(autocorr, 0.99))  # Bound to [0, 0.99]

        process_var = phi * total_var
        measurement_var = (1 - phi) * total_var

        logger.debug(
            "Noise from residuals: autocorr=%.3f, meas_var=%.4f, proc_var=%.4f",
            autocorr, measurement_var, process_var
        )

        return measurement_var, process_var

    def adaptive_tuning(
        self,
        historical_data: pd.Series,
        initial_estimates: NoiseEstimates | None = None,
        n_iterations: int = 3,
    ) -> NoiseEstimates:
        """Iteratively refine noise estimates using model residuals.

        Performs adaptive tuning by:
        1. Fit model with initial estimates
        2. Analyze residuals to refine estimates
        3. Repeat for n_iterations

        Args:
            historical_data: Time series of target variable.
            initial_estimates: Starting noise estimates (or use heuristics).
            n_iterations: Number of refinement iterations.

        Returns:
            Refined NoiseEstimates.
        """
        from liquidity.nowcasting.kalman.liquidity_state_space import LiquidityStateSpace

        # Start with initial estimates or heuristics
        if initial_estimates is None:
            estimates = self.estimate_from_data(historical_data)
        else:
            estimates = initial_estimates

        for i in range(n_iterations):
            logger.debug("Adaptive tuning iteration %d/%d", i + 1, n_iterations)

            # Fit model
            model = LiquidityStateSpace()
            model.fit(historical_data)

            # Get residuals
            in_sample = model.predict_in_sample()
            residuals = in_sample["residual"]

            # Update estimates from residuals
            meas_var, proc_var = self.estimate_from_residuals(residuals)

            # Blend with previous estimates (weighted average)
            weight = 0.5
            new_meas = weight * meas_var + (1 - weight) * estimates.measurement_noise[0]
            new_level = weight * proc_var + (1 - weight) * estimates.process_noise_level

            estimates = NoiseEstimates(
                measurement_noise=np.array([new_meas]),
                process_noise_level=new_level,
                process_noise_trend=estimates.process_noise_trend * 0.9,
                signal_to_noise=float(historical_data.var()) / new_meas
                if new_meas > 0
                else 0.0,
            )

        logger.info("Adaptive tuning complete: %s", estimates)
        return estimates

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"KalmanTuner(level_scale={self._level_scale}, "
            f"trend_scale={self._trend_scale})"
        )
