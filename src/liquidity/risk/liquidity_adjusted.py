"""Liquidity-Adjusted Risk Metrics."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .var.historical import HistoricalVaR


@dataclass
class LiquidityParams:
    """Liquidity parameters for an asset."""

    spread_bps: float = 10.0
    avg_daily_volume: float = 1e6
    position_size: float = 10000
    liquidation_days: int = 1


@dataclass
class LAVaRResult:
    """Liquidity-Adjusted VaR result."""

    base_var_95: float
    base_var_99: float
    liquidity_cost_95: float
    liquidity_cost_99: float
    lavar_95: float
    lavar_99: float
    spread_cost: float
    market_impact: float
    liquidation_adjustment: float
    params: LiquidityParams = field(default_factory=LiquidityParams)


class LiquidityAdjustedRisk:
    """Calculator for Liquidity-Adjusted VaR (LAVaR).

    Incorporates liquidity risk into standard VaR:
    - Spread cost: Half bid-ask spread
    - Market impact: Price movement from own trade
    - Liquidation time: Extended exposure during exit

    Example:
        >>> calc = LiquidityAdjustedRisk()
        >>> params = LiquidityParams(spread_bps=20, position_size=50000)
        >>> result = calc.calculate(returns, params)
        >>> print(f"LAVaR 95%: {result.lavar_95:.2%}")
    """

    def __init__(
        self,
        window: int = 252,
        kyle_lambda: float = 0.001,
    ) -> None:
        """Initialize calculator.

        Args:
            window: Observation window
            kyle_lambda: Kyle's lambda for market impact (default estimate)
        """
        self.window = window
        self.kyle_lambda = kyle_lambda
        self.var_calc = HistoricalVaR(window=window)

    def estimate_spread_cost(self, params: LiquidityParams) -> float:
        """Estimate spread cost as percentage of position.

        Args:
            params: Liquidity parameters

        Returns:
            Spread cost as decimal (e.g., 0.001 for 10 bps)
        """
        return params.spread_bps / 10000 / 2

    def estimate_market_impact(
        self,
        params: LiquidityParams,
        volatility: float,
    ) -> float:
        """Estimate market impact using Kyle's lambda.

        Market Impact = λ × sqrt(position / ADV) × σ

        Args:
            params: Liquidity parameters
            volatility: Asset volatility (daily)

        Returns:
            Market impact as decimal
        """
        if params.avg_daily_volume <= 0:
            return 0.0

        participation_rate = params.position_size / params.avg_daily_volume
        impact = self.kyle_lambda * np.sqrt(participation_rate) * volatility

        return float(impact)

    def liquidation_time_adjustment(
        self,
        base_var: float,
        params: LiquidityParams,
    ) -> float:
        """Adjust VaR for liquidation period.

        Longer liquidation = more time for adverse moves.
        Adjustment = VaR × sqrt(liquidation_days)

        Args:
            base_var: Base VaR
            params: Liquidity parameters

        Returns:
            Adjustment amount
        """
        if params.liquidation_days <= 1:
            return 0.0

        time_factor = np.sqrt(params.liquidation_days) - 1
        return float(base_var * time_factor)

    def calculate(
        self,
        returns: pd.Series,
        params: LiquidityParams,
    ) -> LAVaRResult:
        """Calculate Liquidity-Adjusted VaR.

        Args:
            returns: Series of returns
            params: Liquidity parameters for the asset

        Returns:
            LAVaRResult with base and adjusted VaR
        """
        base_result = self.var_calc.calculate(returns)

        # Get volatility from recent returns
        recent_returns = returns.iloc[-self.window :] if len(returns) > self.window else returns
        volatility = float(recent_returns.std())

        # Liquidity costs
        spread_cost = self.estimate_spread_cost(params)
        market_impact = self.estimate_market_impact(params, volatility)
        liq_time_adj_95 = self.liquidation_time_adjustment(base_result.var_95, params)
        liq_time_adj_99 = self.liquidation_time_adjustment(base_result.var_99, params)

        # Total liquidity cost
        liquidity_cost_95 = spread_cost + market_impact + liq_time_adj_95
        liquidity_cost_99 = spread_cost + market_impact + liq_time_adj_99

        return LAVaRResult(
            base_var_95=base_result.var_95,
            base_var_99=base_result.var_99,
            liquidity_cost_95=liquidity_cost_95,
            liquidity_cost_99=liquidity_cost_99,
            lavar_95=base_result.var_95 + liquidity_cost_95,
            lavar_99=base_result.var_99 + liquidity_cost_99,
            spread_cost=spread_cost,
            market_impact=market_impact,
            liquidation_adjustment=liq_time_adj_95,
            params=params,
        )

    def calculate_stress(
        self,
        returns: pd.Series,
        params: LiquidityParams,
        stress_multipliers: dict[str, float] | None = None,
    ) -> dict[str, LAVaRResult]:
        """Calculate LAVaR under stress scenarios.

        Args:
            returns: Series of returns
            params: Base liquidity parameters
            stress_multipliers: Dict of scenario -> multiplier

        Returns:
            Dict of scenario -> LAVaRResult
        """
        if stress_multipliers is None:
            stress_multipliers = {
                "normal": 1.0,
                "moderate_stress": 2.0,
                "severe_stress": 5.0,
                "crisis": 10.0,
            }

        results: dict[str, LAVaRResult] = {}

        for scenario, multiplier in stress_multipliers.items():
            stressed_params = LiquidityParams(
                spread_bps=params.spread_bps * multiplier,
                avg_daily_volume=params.avg_daily_volume / max(multiplier, 0.1),
                position_size=params.position_size,
                liquidation_days=max(1, int(params.liquidation_days * np.sqrt(multiplier))),
            )
            results[scenario] = self.calculate(returns, stressed_params)

        return results

    def calculate_multi_asset(
        self,
        returns_df: pd.DataFrame,
        params_dict: dict[str, LiquidityParams],
    ) -> dict[str, LAVaRResult]:
        """Calculate LAVaR for multiple assets.

        Args:
            returns_df: DataFrame with asset returns as columns
            params_dict: Dict mapping asset name to LiquidityParams

        Returns:
            Dict mapping asset name to LAVaRResult
        """
        results: dict[str, LAVaRResult] = {}

        for asset in returns_df.columns:
            asset_str = str(asset)
            if asset_str in params_dict:
                results[asset_str] = self.calculate(returns_df[asset], params_dict[asset_str])
            else:
                results[asset_str] = self.calculate(
                    returns_df[asset],
                    LiquidityParams(),
                )

        return results


# Default liquidity parameters for common assets
DEFAULT_LIQUIDITY_PARAMS: dict[str, LiquidityParams] = {
    "BTC": LiquidityParams(spread_bps=5, avg_daily_volume=1e9, liquidation_days=1),
    "ETH": LiquidityParams(spread_bps=8, avg_daily_volume=5e8, liquidation_days=1),
    "SPY": LiquidityParams(spread_bps=1, avg_daily_volume=1e10, liquidation_days=1),
    "TLT": LiquidityParams(spread_bps=2, avg_daily_volume=1e9, liquidation_days=1),
    "GLD": LiquidityParams(spread_bps=2, avg_daily_volume=5e8, liquidation_days=1),
    "HYG": LiquidityParams(spread_bps=5, avg_daily_volume=5e8, liquidation_days=2),
}
