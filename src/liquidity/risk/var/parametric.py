"""Parametric VaR calculator."""

from dataclasses import dataclass
from enum import Enum

import pandas as pd
from scipy import stats


class Distribution(str, Enum):
    """Supported distributions for parametric VaR."""

    NORMAL = "normal"
    T_STUDENT = "t-student"


@dataclass
class ParametricVaRResult:
    """Parametric VaR result with distribution info."""

    var_95: float
    var_99: float
    distribution: Distribution
    mean: float
    std: float
    df: float | None = None
    observation_count: int = 0
    as_of_date: pd.Timestamp | None = None


class ParametricVaR:
    """Parametric VaR using Normal or t-distribution.

    Normal VaR: VaR(α) = μ - σ × z_α
    t-dist VaR: VaR(α) = μ - σ × t_α(df)

    t-distribution handles fat tails better than normal.

    Example:
        >>> calculator = ParametricVaR(distribution=Distribution.T_STUDENT)
        >>> result = calculator.calculate(returns_series)
        >>> print(f"VaR 95%: {result.var_95:.2%}, df={result.df:.1f}")
    """

    def __init__(
        self,
        distribution: Distribution = Distribution.NORMAL,
        window: int = 252,
    ) -> None:
        """Initialize calculator.

        Args:
            distribution: NORMAL or T_STUDENT
            window: Observation window for parameter estimation
        """
        self.distribution = distribution
        self.window = window

    def estimate_parameters(
        self,
        returns: pd.Series,
    ) -> dict[str, float]:
        """Estimate distribution parameters from data.

        Args:
            returns: Series of returns

        Returns:
            Dict with 'mean', 'std', and optionally 'df', 'loc', 'scale'
        """
        clean_returns = returns.dropna()

        if len(clean_returns) > self.window:
            clean_returns = clean_returns.iloc[-self.window :]

        params: dict[str, float] = {
            "mean": float(clean_returns.mean()),
            "std": float(clean_returns.std()),
            "count": float(len(clean_returns)),
        }

        if self.distribution == Distribution.T_STUDENT and len(clean_returns) > 5:
            # Fit t-distribution to estimate degrees of freedom
            df, loc, scale = stats.t.fit(clean_returns.values)
            params["df"] = float(df)
            params["loc"] = float(loc)
            params["scale"] = float(scale)

        return params

    def calculate(
        self,
        returns: pd.Series,
        as_of: pd.Timestamp | None = None,
    ) -> ParametricVaRResult:
        """Calculate parametric VaR.

        Args:
            returns: Series of returns
            as_of: Optional point-in-time date

        Returns:
            ParametricVaRResult with VaR and distribution params
        """
        if as_of is not None:
            returns = returns[returns.index <= as_of]

        params = self.estimate_parameters(returns)

        # Get last date
        clean_returns = returns.dropna()
        as_of_date: pd.Timestamp | None = None
        if len(clean_returns) > 0:
            as_of_date = pd.Timestamp(clean_returns.index[-1])

        if self.distribution == Distribution.NORMAL:
            # Normal VaR: μ - σ × z_α
            z_95 = float(stats.norm.ppf(0.05))  # -1.645
            z_99 = float(stats.norm.ppf(0.01))  # -2.326

            var_95 = -(params["mean"] + params["std"] * z_95)
            var_99 = -(params["mean"] + params["std"] * z_99)

            return ParametricVaRResult(
                var_95=var_95,
                var_99=var_99,
                distribution=Distribution.NORMAL,
                mean=params["mean"],
                std=params["std"],
                observation_count=int(params["count"]),
                as_of_date=as_of_date,
            )

        else:  # T_STUDENT
            # t-dist VaR with fitted df
            df = params.get("df", 30.0)  # Default to high df if fit failed
            scale = params.get("scale", params["std"])
            loc = params.get("loc", params["mean"])

            t_95 = float(stats.t.ppf(0.05, df))
            t_99 = float(stats.t.ppf(0.01, df))

            var_95 = -(loc + scale * t_95)
            var_99 = -(loc + scale * t_99)

            return ParametricVaRResult(
                var_95=var_95,
                var_99=var_99,
                distribution=Distribution.T_STUDENT,
                mean=params["mean"],
                std=params["std"],
                df=df,
                observation_count=int(params["count"]),
                as_of_date=as_of_date,
            )

    def calculate_rolling(
        self,
        returns: pd.Series,
    ) -> pd.DataFrame:
        """Calculate rolling parametric VaR.

        Args:
            returns: Series of returns

        Returns:
            DataFrame with var_95, var_99, and params columns
        """
        results: list[dict[str, object]] = []

        for i in range(self.window, len(returns) + 1):
            window_returns = returns.iloc[:i]
            result = self.calculate(window_returns)

            results.append(
                {
                    "date": returns.index[i - 1],
                    "var_95": result.var_95,
                    "var_99": result.var_99,
                    "mean": result.mean,
                    "std": result.std,
                    "df": result.df,
                }
            )

        return pd.DataFrame(results).set_index("date")

    def compare_distributions(
        self,
        returns: pd.Series,
    ) -> dict[Distribution, ParametricVaRResult]:
        """Compare VaR across distributions.

        Args:
            returns: Series of returns

        Returns:
            Dict mapping distribution to result
        """
        results: dict[Distribution, ParametricVaRResult] = {}

        for dist in Distribution:
            calc = ParametricVaR(distribution=dist, window=self.window)
            results[dist] = calc.calculate(returns)

        return results
