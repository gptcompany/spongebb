"""Historical simulation VaR calculator."""

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd


@dataclass
class VaRResult:
    """VaR calculation result."""

    var_95: float
    var_99: float
    observation_count: int
    window_days: int
    as_of_date: pd.Timestamp | None


class HistoricalVaR:
    """Historical simulation VaR calculator.

    Uses empirical distribution of returns to estimate VaR.
    No distributional assumptions required.

    Example:
        >>> calculator = HistoricalVaR(window=252)
        >>> result = calculator.calculate(returns_series)
        >>> print(f"VaR 95%: {result.var_95:.2%}")
    """

    def __init__(
        self,
        window: int = 252,
        confidence_levels: tuple[float, ...] = (0.95, 0.99),
    ) -> None:
        """Initialize calculator.

        Args:
            window: Rolling window size in trading days
            confidence_levels: Tuple of confidence levels (e.g., 0.95, 0.99)
        """
        self.window = window
        self.confidence_levels = confidence_levels

    def calculate(
        self,
        returns: pd.Series,
        as_of: pd.Timestamp | None = None,
    ) -> VaRResult:
        """Calculate historical VaR.

        Args:
            returns: Series of returns (log or simple)
            as_of: Optional date for point-in-time VaR

        Returns:
            VaRResult with VaR at each confidence level
        """
        if as_of is not None:
            returns = returns[returns.index <= as_of]

        # Use last `window` observations
        if len(returns) > self.window:
            returns = returns.iloc[-self.window :]

        clean_returns = returns.dropna()

        if len(clean_returns) == 0:
            return VaRResult(
                var_95=0.0,
                var_99=0.0,
                observation_count=0,
                window_days=self.window,
                as_of_date=as_of,
            )

        # VaR is the negative percentile (loss)
        # At 95% confidence, we look at the 5th percentile
        var_95 = -float(np.percentile(clean_returns, 5))
        var_99 = -float(np.percentile(clean_returns, 1))

        as_of_date = clean_returns.index[-1] if len(clean_returns) > 0 else as_of
        if isinstance(as_of_date, datetime) and not isinstance(as_of_date, pd.Timestamp):
            as_of_date = pd.Timestamp(as_of_date)

        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            observation_count=len(clean_returns),
            window_days=self.window,
            as_of_date=as_of_date,
        )

    def calculate_rolling(
        self,
        returns: pd.Series,
    ) -> pd.DataFrame:
        """Calculate rolling VaR time series.

        Args:
            returns: Series of returns

        Returns:
            DataFrame with var_95, var_99 columns
        """
        results: list[dict[str, object]] = []

        for i in range(self.window, len(returns) + 1):
            window_returns = returns.iloc[i - self.window : i]
            clean_returns = window_returns.dropna()

            if len(clean_returns) > 0:
                var_95 = -float(np.percentile(clean_returns, 5))
                var_99 = -float(np.percentile(clean_returns, 1))
            else:
                var_95 = 0.0
                var_99 = 0.0

            results.append(
                {
                    "date": returns.index[i - 1],
                    "var_95": var_95,
                    "var_99": var_99,
                }
            )

        return pd.DataFrame(results).set_index("date")

    def calculate_multi_asset(
        self,
        returns_df: pd.DataFrame,
    ) -> dict[str, VaRResult]:
        """Calculate VaR for multiple assets.

        Args:
            returns_df: DataFrame with asset returns as columns

        Returns:
            Dict mapping asset names to VaRResult
        """
        results: dict[str, VaRResult] = {}
        for col in returns_df.columns:
            results[str(col)] = self.calculate(returns_df[col])
        return results
