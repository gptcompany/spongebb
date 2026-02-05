"""PBoC balance sheet estimator using MIDAS regression.

This module provides a Mixed-Data Sampling (MIDAS) regression estimator for
predicting PBoC total assets before official monthly releases. By using
high-frequency predictors (daily SHIBOR, weekly DR007), we can nowcast
the monthly balance sheet 15-20 days before official publication.

Reference:
    Ghysels, E., Santa-Clara, P., & Valkanov, R. (2004). "The MIDAS Touch:
    Mixed Data Sampling Regression Models." Finance Working Paper.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from liquidity.nowcasting.midas.features import MIDASFeatures

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class PBoCEstimate:
    """PBoC balance sheet estimate with uncertainty bounds.

    Attributes:
        timestamp: Timestamp of the estimate.
        estimate: Point estimate in trillion CNY.
        std: Standard error of the estimate.
        ci_lower: 95% confidence interval lower bound.
        ci_upper: 95% confidence interval upper bound.
        days_ahead: Days before expected official release.
        confidence: Model confidence score (0-1).
        feature_importance: Optional dict of top feature importances.
    """

    timestamp: pd.Timestamp
    estimate: float
    std: float
    ci_lower: float
    ci_upper: float
    days_ahead: int
    confidence: float
    feature_importance: dict[str, float] | None = None

    def __post_init__(self) -> None:
        """Validate estimate values."""
        if self.estimate < 0:
            raise ValueError(f"estimate must be >= 0, got {self.estimate}")
        if self.std < 0:
            raise ValueError(f"std must be >= 0, got {self.std}")
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "estimate": self.estimate,
            "std": self.std,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "days_ahead": self.days_ahead,
            "confidence": self.confidence,
            "feature_importance": self.feature_importance,
        }


@dataclass
class BacktestResult:
    """Result from a single backtest period."""

    date: pd.Timestamp
    estimate: float
    official: float
    error: float
    error_pct: float
    ci_lower: float
    ci_upper: float
    in_ci: bool


class PBoCEstimator:
    """MIDAS regression estimator for PBoC balance sheet.

    Uses SHIBOR (daily), DR007 (weekly), and CNY-CNH spread to
    estimate monthly PBoC total assets before official release.

    The model uses Ridge regression with Almon polynomial distributed
    lag features to preserve high-frequency information in the
    monthly prediction target.

    Attributes:
        alpha: Ridge regularization parameter.
        n_daily_lags: Number of daily lag features.
        n_weekly_lags: Number of weekly lag features.
        daily_decay: Almon decay parameter for daily weights.

    Example:
        >>> estimator = PBoCEstimator(alpha=10.0)
        >>> estimator.fit(shibor_daily, dr007_weekly, spread, pboc_monthly)
        >>> estimate = estimator.estimate(shibor_latest, dr007_latest, spread_latest)
        >>> print(f"PBoC estimate: {estimate.estimate:.2f} +/- {estimate.std:.2f}")
    """

    # Default hyperparameters
    DEFAULT_ALPHA = 10.0
    DEFAULT_DAILY_LAGS = 30
    DEFAULT_WEEKLY_LAGS = 4
    DEFAULT_DAILY_DECAY = 30.0

    # PBoC release schedule: typically 15th of following month
    RELEASE_DAY = 15

    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        n_daily_lags: int = DEFAULT_DAILY_LAGS,
        n_weekly_lags: int = DEFAULT_WEEKLY_LAGS,
        daily_decay: float = DEFAULT_DAILY_DECAY,
    ) -> None:
        """Initialize the PBoC estimator.

        Args:
            alpha: Ridge regularization parameter. Higher values = more regularization.
            n_daily_lags: Number of daily lag features to create. Default 30.
            n_weekly_lags: Number of weekly lag features. Default 4.
            daily_decay: Almon decay parameter. Default 30.0.
        """
        self.alpha = alpha
        self.n_daily_lags = n_daily_lags
        self.n_weekly_lags = n_weekly_lags
        self.daily_decay = daily_decay

        self.model = Ridge(alpha=alpha)
        self.scaler = StandardScaler()
        self.feature_builder = MIDASFeatures()

        self._is_fitted = False
        self._feature_names: list[str] = []
        self._train_residual_std: float = 0.0
        self._train_mean: float = 0.0
        self._train_r2: float = 0.0

    @property
    def is_fitted(self) -> bool:
        """Return whether the model has been fitted."""
        return self._is_fitted

    def fit(
        self,
        shibor_daily: pd.Series,
        dr007_weekly: pd.Series,
        cny_cnh_spread: pd.Series | None,
        pboc_monthly: pd.Series,
        tune_alpha: bool = False,
    ) -> PBoCEstimator:
        """Fit MIDAS regression on historical data.

        Args:
            shibor_daily: Daily SHIBOR overnight rate (index: DatetimeIndex).
            dr007_weekly: Weekly DR007 repo rate (index: DatetimeIndex).
            cny_cnh_spread: Optional CNY-CNH spot spread (index: DatetimeIndex).
            pboc_monthly: Official PBoC total assets (target, monthly frequency).
            tune_alpha: Whether to tune alpha via CV. Default False.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If input series are empty or have incompatible indices.
        """
        if shibor_daily.empty or dr007_weekly.empty or pboc_monthly.empty:
            raise ValueError("Input series cannot be empty")

        logger.info("Fitting PBoC estimator on %d monthly observations", len(pboc_monthly))

        # Create features
        X, self._feature_names = self._create_features(
            shibor_daily, dr007_weekly, cny_cnh_spread
        )

        # Align with monthly target (resample to month-end)
        X_monthly = X.resample("ME").last()
        y = pboc_monthly.reindex(X_monthly.index)

        # Drop NaN observations
        mask = ~(X_monthly.isna().any(axis=1) | y.isna())
        X_clean = X_monthly[mask]
        y_clean = y[mask]

        if len(X_clean) < 10:
            raise ValueError(
                f"Need at least 10 observations for fitting, got {len(X_clean)}"
            )

        # Optional: tune alpha via cross-validation
        if tune_alpha and len(X_clean) >= 20:
            logger.info("Tuning alpha via time-series cross-validation")
            self.alpha = self._tune_alpha_cv(X_clean, y_clean)
            self.model = Ridge(alpha=self.alpha)
            logger.info("Selected alpha: %.2f", self.alpha)

        # Scale features
        X_scaled = self.scaler.fit_transform(X_clean)

        # Fit Ridge regression
        self.model.fit(X_scaled, y_clean)

        # Compute training metrics
        y_pred = self.model.predict(X_scaled)
        residuals = y_clean.values - y_pred
        self._train_residual_std = float(np.std(residuals))
        self._train_mean = float(y_clean.mean())
        self._train_r2 = float(self.model.score(X_scaled, y_clean))

        self._is_fitted = True

        logger.info(
            "Model fitted: R^2=%.4f, residual_std=%.4f trillion CNY",
            self._train_r2,
            self._train_residual_std,
        )

        return self

    def estimate(
        self,
        shibor_daily: pd.Series,
        dr007_weekly: pd.Series,
        cny_cnh_spread: pd.Series | None = None,
        as_of_date: pd.Timestamp | None = None,
    ) -> PBoCEstimate:
        """Generate PBoC estimate using latest available data.

        Returns estimate for current month before official release.

        Args:
            shibor_daily: Daily SHIBOR data (should include recent observations).
            dr007_weekly: Weekly DR007 data.
            cny_cnh_spread: Optional CNY-CNH spread.
            as_of_date: Optional date to estimate as of. Default: latest data date.

        Returns:
            PBoCEstimate with point estimate and uncertainty bounds.

        Raises:
            ValueError: If model not fitted or insufficient data.
        """
        if not self._is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        # Create features from latest data
        X, _ = self._create_features(shibor_daily, dr007_weekly, cny_cnh_spread)

        if as_of_date is not None:
            # Filter to data available as of the specified date
            X = X[X.index <= as_of_date]

        if X.empty:
            raise ValueError("No valid features could be created from input data")

        X_latest = X.iloc[[-1]]  # Most recent observation
        latest_date = X_latest.index[0]

        # Handle NaN in features
        if X_latest.isna().any().any():
            logger.warning("Some features contain NaN, forward-filling")
            X_latest = X_latest.ffill(axis=1).bfill(axis=1)

        # Scale and predict
        X_scaled = self.scaler.transform(X_latest)
        estimate = float(self.model.predict(X_scaled)[0])

        # Estimate uncertainty
        std = self._estimate_uncertainty(X_scaled, X_latest)

        # Calculate days until official release (typically 15th of next month)
        today = pd.Timestamp(latest_date)
        next_month = today + pd.offsets.MonthEnd(1)
        next_release = next_month + pd.Timedelta(days=self.RELEASE_DAY)
        days_ahead = max(0, (next_release - today).days)

        # Calculate confidence based on data quality and model fit
        confidence = self._calculate_confidence(X_latest, std)

        # Get feature importance
        feature_importance = self._get_feature_importance(top_n=5)

        return PBoCEstimate(
            timestamp=today,
            estimate=estimate,
            std=std,
            ci_lower=estimate - 1.96 * std,
            ci_upper=estimate + 1.96 * std,
            days_ahead=days_ahead,
            confidence=confidence,
            feature_importance=feature_importance,
        )

    def backtest(
        self,
        shibor_daily: pd.Series,
        dr007_weekly: pd.Series,
        cny_cnh_spread: pd.Series | None,
        pboc_official: pd.Series,
        train_months: int = 24,
        test_start: pd.Timestamp | None = None,
    ) -> tuple[pd.DataFrame, dict]:
        """Walk-forward backtest of the estimator.

        Args:
            shibor_daily: Full history of daily SHIBOR.
            dr007_weekly: Full history of weekly DR007.
            cny_cnh_spread: Full history of CNY-CNH spread (optional).
            pboc_official: Full history of official PBoC monthly releases.
            train_months: Minimum months of training data. Default 24.
            test_start: Start date for testing. Default: after train_months.

        Returns:
            Tuple of (results DataFrame, summary metrics dict).
        """
        if test_start is None:
            test_start = pboc_official.index[train_months]

        results: list[BacktestResult] = []

        for test_date in pboc_official.index[pboc_official.index >= test_start]:
            # Training cutoff: 45 days before test date (to simulate realistic lag)
            train_end = test_date - pd.Timedelta(days=45)

            # Fit on training data
            train_estimator = PBoCEstimator(
                alpha=self.alpha,
                n_daily_lags=self.n_daily_lags,
                n_weekly_lags=self.n_weekly_lags,
                daily_decay=self.daily_decay,
            )

            try:
                train_estimator.fit(
                    shibor_daily.loc[:train_end],
                    dr007_weekly.loc[:train_end],
                    cny_cnh_spread.loc[:train_end] if cny_cnh_spread is not None else None,
                    pboc_official.loc[:train_end],
                )

                # Estimate for test date
                estimate = train_estimator.estimate(
                    shibor_daily.loc[:test_date],
                    dr007_weekly.loc[:test_date],
                    cny_cnh_spread.loc[:test_date] if cny_cnh_spread is not None else None,
                    as_of_date=test_date,
                )

                official = float(pboc_official.loc[test_date])
                error = estimate.estimate - official
                error_pct = abs(error) / official * 100

                results.append(
                    BacktestResult(
                        date=test_date,
                        estimate=estimate.estimate,
                        official=official,
                        error=error,
                        error_pct=error_pct,
                        ci_lower=estimate.ci_lower,
                        ci_upper=estimate.ci_upper,
                        in_ci=estimate.ci_lower <= official <= estimate.ci_upper,
                    )
                )

            except Exception as e:
                logger.warning("Backtest failed for %s: %s", test_date, e)
                continue

        # Convert to DataFrame
        df = pd.DataFrame([r.__dict__ for r in results])

        # Calculate summary metrics
        if not df.empty:
            summary = {
                "n_periods": len(df),
                "mape": df["error_pct"].mean(),
                "max_error_pct": df["error_pct"].max(),
                "mean_error": df["error"].mean(),
                "std_error": df["error"].std(),
                "ci_coverage": df["in_ci"].mean() * 100,
            }
        else:
            summary = {"n_periods": 0, "mape": float("nan")}

        return df, summary

    def _create_features(
        self,
        shibor: pd.Series,
        dr007: pd.Series,
        spread: pd.Series | None,
    ) -> tuple[pd.DataFrame, list[str]]:
        """Create MIDAS feature matrix."""
        return self.feature_builder.create_midas_features(
            daily_series=shibor,
            weekly_series=dr007,
            spread_series=spread,
            n_daily_lags=self.n_daily_lags,
            n_weekly_lags=self.n_weekly_lags,
            daily_decay=self.daily_decay,
        )

    def _tune_alpha_cv(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        alphas: list[float] | None = None,
        n_splits: int = 5,
    ) -> float:
        """Tune Ridge alpha via time-series cross-validation.

        Uses expanding window CV to respect temporal order.

        Args:
            X: Feature matrix.
            y: Target variable.
            alphas: List of alpha values to try. Default: [0.1, 1, 10, 100, 1000].
            n_splits: Number of CV splits. Default 5.

        Returns:
            Best alpha value.
        """
        if alphas is None:
            alphas = [0.1, 1.0, 10.0, 100.0, 1000.0]

        tscv = TimeSeriesSplit(n_splits=n_splits)

        best_alpha = self.DEFAULT_ALPHA
        best_score = -np.inf

        # Scale features for CV
        X_scaled = self.scaler.fit_transform(X)

        for alpha in alphas:
            model = Ridge(alpha=alpha)
            scores: list[float] = []

            for train_idx, val_idx in tscv.split(X_scaled):
                X_train, X_val = X_scaled[train_idx], X_scaled[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

                model.fit(X_train, y_train)
                score = model.score(X_val, y_val)
                scores.append(score)

            mean_score = float(np.mean(scores))
            logger.debug("Alpha=%.2f, mean R^2=%.4f", alpha, mean_score)

            if mean_score > best_score:
                best_score = mean_score
                best_alpha = alpha

        return best_alpha

    def _estimate_uncertainty(
        self,
        X_scaled: NDArray[np.float64],
        X_raw: pd.DataFrame,
    ) -> float:
        """Estimate prediction uncertainty.

        Uses training residual standard deviation as base uncertainty,
        adjusted for feature quality.

        Args:
            X_scaled: Scaled feature array.
            X_raw: Raw feature DataFrame.

        Returns:
            Standard deviation of prediction.
        """
        # Base uncertainty from training residuals
        base_std = self._train_residual_std

        # Adjust for data quality
        missing_ratio = X_raw.isna().sum().sum() / X_raw.size
        stale_penalty = 1.0 + missing_ratio * 2.0  # Up to 3x if all stale

        return base_std * stale_penalty

    def _calculate_confidence(
        self,
        X: pd.DataFrame,
        std: float,
    ) -> float:
        """Calculate model confidence based on feature quality and uncertainty.

        Args:
            X: Feature DataFrame.
            std: Prediction standard deviation.

        Returns:
            Confidence score between 0 and 1.
        """
        # Start with base confidence from R^2
        base_confidence = min(0.95, max(0.5, self._train_r2))

        # Penalize for missing features
        missing_ratio = X.isna().sum().sum() / X.size
        data_penalty = 1.0 - min(0.3, missing_ratio * 0.5)

        # Penalize for high uncertainty relative to mean
        if self._train_mean > 0:
            cv = std / self._train_mean  # Coefficient of variation
            uncertainty_penalty = max(0.6, 1.0 - cv * 2)
        else:
            uncertainty_penalty = 0.7

        confidence = base_confidence * data_penalty * uncertainty_penalty
        return float(np.clip(confidence, 0.1, 0.95))

    def _get_feature_importance(self, top_n: int = 5) -> dict[str, float]:
        """Get top feature importances from Ridge coefficients.

        Args:
            top_n: Number of top features to return.

        Returns:
            Dict mapping feature names to importance scores.
        """
        if not self._is_fitted or not self._feature_names:
            return {}

        # Get absolute coefficients (Ridge doesn't have feature_importances_)
        coefs = np.abs(self.model.coef_)

        # Pair with feature names and sort
        importance = dict(zip(self._feature_names, coefs, strict=False))
        sorted_importance = dict(
            sorted(importance.items(), key=lambda x: x[1], reverse=True)[:top_n]
        )

        # Normalize to sum to 1
        total = sum(sorted_importance.values())
        if total > 0:
            sorted_importance = {k: v / total for k, v in sorted_importance.items()}

        return sorted_importance

    def get_diagnostics(self) -> dict:
        """Get model diagnostics and metadata.

        Returns:
            Dict with model diagnostics.
        """
        if not self._is_fitted:
            return {"fitted": False}

        return {
            "fitted": True,
            "alpha": self.alpha,
            "n_daily_lags": self.n_daily_lags,
            "n_weekly_lags": self.n_weekly_lags,
            "daily_decay": self.daily_decay,
            "train_r2": self._train_r2,
            "train_residual_std": self._train_residual_std,
            "train_mean": self._train_mean,
            "n_features": len(self._feature_names),
            "feature_importance": self._get_feature_importance(top_n=10),
        }
