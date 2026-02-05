"""CVaR / Expected Shortfall calculator."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from .var.parametric import Distribution


@dataclass
class CVaRResult:
    """CVaR calculation result."""

    cvar_95: float
    cvar_99: float
    var_95: float
    var_99: float
    tail_observations: int
    method: str
    as_of_date: pd.Timestamp | None = None


class ExpectedShortfall:
    """Expected Shortfall (CVaR) calculator.

    Computes the average loss beyond VaR threshold.
    More conservative than VaR for tail risk management.

    CVaR answers: "What is the average loss when we exceed VaR?"

    Example:
        >>> es = ExpectedShortfall(window=252)
        >>> result = es.calculate_historical(returns_series)
        >>> print(f"CVaR 95%: {result.cvar_95:.2%}")
    """

    def __init__(self, window: int = 252) -> None:
        """Initialize calculator.

        Args:
            window: Rolling window for calculations
        """
        self.window = window

    def calculate_historical(
        self,
        returns: pd.Series,
        as_of: pd.Timestamp | None = None,
    ) -> CVaRResult:
        """Calculate historical CVaR (empirical).

        Args:
            returns: Series of returns
            as_of: Optional point-in-time date

        Returns:
            CVaRResult with historical CVaR
        """
        if as_of is not None:
            returns = returns[returns.index <= as_of]

        if len(returns) > self.window:
            returns = returns.iloc[-self.window :]

        clean_returns = returns.dropna()

        if len(clean_returns) == 0:
            return CVaRResult(
                cvar_95=0.0,
                cvar_99=0.0,
                var_95=0.0,
                var_99=0.0,
                tail_observations=0,
                method="historical",
                as_of_date=as_of,
            )

        # VaR thresholds (percentiles)
        var_95_threshold = float(np.percentile(clean_returns, 5))
        var_99_threshold = float(np.percentile(clean_returns, 1))

        # CVaR = mean of returns below VaR threshold
        tail_95 = clean_returns[clean_returns <= var_95_threshold]
        tail_99 = clean_returns[clean_returns <= var_99_threshold]

        cvar_95 = -float(tail_95.mean()) if len(tail_95) > 0 else -var_95_threshold
        cvar_99 = -float(tail_99.mean()) if len(tail_99) > 0 else -var_99_threshold

        as_of_date = pd.Timestamp(clean_returns.index[-1]) if len(clean_returns) > 0 else as_of

        return CVaRResult(
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            var_95=-var_95_threshold,
            var_99=-var_99_threshold,
            tail_observations=len(tail_95),
            method="historical",
            as_of_date=as_of_date,
        )

    def calculate_parametric(
        self,
        returns: pd.Series,
        distribution: Distribution = Distribution.NORMAL,
        as_of: pd.Timestamp | None = None,
    ) -> CVaRResult:
        """Calculate parametric CVaR.

        For Normal distribution:
        CVaR(α) = μ + σ × φ(z_α) / (1-α)

        Args:
            returns: Series of returns
            distribution: NORMAL or T_STUDENT
            as_of: Optional point-in-time date

        Returns:
            CVaRResult with parametric CVaR
        """
        if as_of is not None:
            returns = returns[returns.index <= as_of]

        if len(returns) > self.window:
            returns = returns.iloc[-self.window :]

        clean_returns = returns.dropna()

        if len(clean_returns) == 0:
            return CVaRResult(
                cvar_95=0.0,
                cvar_99=0.0,
                var_95=0.0,
                var_99=0.0,
                tail_observations=0,
                method=f"parametric-{distribution.value}",
                as_of_date=as_of,
            )

        mu = float(clean_returns.mean())
        sigma = float(clean_returns.std())

        as_of_date = pd.Timestamp(clean_returns.index[-1]) if len(clean_returns) > 0 else as_of

        if distribution == Distribution.NORMAL:
            # Normal CVaR formula: CVaR = -μ + σ × φ(z_α) / α
            # where z_α = Φ^{-1}(α) is the quantile (negative)
            z_95 = float(stats.norm.ppf(0.05))  # ~ -1.645
            z_99 = float(stats.norm.ppf(0.01))  # ~ -2.326

            phi_95 = float(stats.norm.pdf(z_95))
            phi_99 = float(stats.norm.pdf(z_99))

            # VaR = -μ - σz_α (loss is positive)
            var_95 = -(mu + sigma * z_95)
            var_99 = -(mu + sigma * z_99)

            # CVaR = -μ + σφ(z_α)/α (average of losses beyond VaR)
            cvar_95 = -mu + sigma * phi_95 / 0.05
            cvar_99 = -mu + sigma * phi_99 / 0.01

        else:  # T_STUDENT
            # Fit t-distribution
            df, loc, scale = stats.t.fit(clean_returns.values)
            df = float(df)
            loc = float(loc)
            scale = float(scale)

            t_95 = float(stats.t.ppf(0.05, df))  # Negative
            t_99 = float(stats.t.ppf(0.01, df))  # Negative

            pdf_95 = float(stats.t.pdf(t_95, df))
            pdf_99 = float(stats.t.pdf(t_99, df))

            # VaR = -loc - scale × t_α
            var_95 = -(loc + scale * t_95)
            var_99 = -(loc + scale * t_99)

            # CVaR for t-distribution: ES = -loc + scale × f(t_α) × (df + t_α²) / (α × (df-1))
            if df > 1:
                factor_95 = (df + t_95**2) / (df - 1)
                factor_99 = (df + t_99**2) / (df - 1)
                cvar_95 = -loc + scale * pdf_95 / 0.05 * factor_95
                cvar_99 = -loc + scale * pdf_99 / 0.01 * factor_99
            else:
                # df <= 1, ES doesn't exist, use VaR * 1.5 approximation
                cvar_95 = var_95 * 1.5
                cvar_99 = var_99 * 1.5

        return CVaRResult(
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            var_95=var_95,
            var_99=var_99,
            tail_observations=int(len(clean_returns) * 0.05),
            method=f"parametric-{distribution.value}",
            as_of_date=as_of_date,
        )

    def calculate_rolling(
        self,
        returns: pd.Series,
        method: str = "historical",
    ) -> pd.DataFrame:
        """Calculate rolling CVaR time series.

        Args:
            returns: Series of returns
            method: 'historical' or 'parametric'

        Returns:
            DataFrame with cvar_95, cvar_99 columns
        """
        results: list[dict[str, object]] = []

        for i in range(self.window, len(returns) + 1):
            window_returns = returns.iloc[i - self.window : i]

            if method == "historical":
                result = self.calculate_historical(window_returns)
            else:
                result = self.calculate_parametric(window_returns)

            results.append(
                {
                    "date": returns.index[i - 1],
                    "cvar_95": result.cvar_95,
                    "cvar_99": result.cvar_99,
                    "var_95": result.var_95,
                    "var_99": result.var_99,
                }
            )

        return pd.DataFrame(results).set_index("date")

    def compare_var_cvar(
        self,
        returns: pd.Series,
    ) -> pd.DataFrame:
        """Compare VaR and CVaR across methods.

        Args:
            returns: Series of returns

        Returns:
            DataFrame comparing metrics
        """
        historical = self.calculate_historical(returns)
        param_normal = self.calculate_parametric(returns, Distribution.NORMAL)
        param_t = self.calculate_parametric(returns, Distribution.T_STUDENT)

        data = {
            "Method": ["Historical", "Parametric-Normal", "Parametric-t"],
            "VaR_95": [historical.var_95, param_normal.var_95, param_t.var_95],
            "CVaR_95": [historical.cvar_95, param_normal.cvar_95, param_t.cvar_95],
            "VaR_99": [historical.var_99, param_normal.var_99, param_t.var_99],
            "CVaR_99": [historical.cvar_99, param_normal.cvar_99, param_t.cvar_99],
            "CVaR/VaR_99": [
                historical.cvar_99 / historical.var_99 if historical.var_99 > 0 else 1.0,
                param_normal.cvar_99 / param_normal.var_99 if param_normal.var_99 > 0 else 1.0,
                param_t.cvar_99 / param_t.var_99 if param_t.var_99 > 0 else 1.0,
            ],
        }

        return pd.DataFrame(data).set_index("Method")
