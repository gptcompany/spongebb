"""Oil market analysis module for Global Liquidity Monitor.

This module provides tools for analyzing US petroleum supply-demand balance:
- Supply-Demand Balance Calculator: Calculates weekly balance from EIA data
- Balance signals: build, draw, flat based on imbalance magnitude
- Inventory Forecaster: YoY and seasonal inventory analysis with 4-week forecast
- Regime Classifier: Classifies market into TIGHT/BALANCED/LOOSE regimes
"""

from liquidity.oil.inventory_forecast import (
    InventoryForecast,
    InventoryForecaster,
    TrendDirection,
)
from liquidity.oil.regime import (
    OilRegime,
    OilRegimeClassifier,
    OilRegimeState,
)
from liquidity.oil.supply_demand import (
    SupplyDemandBalance,
    SupplyDemandCalculator,
)

__all__ = [
    "InventoryForecast",
    "InventoryForecaster",
    "OilRegime",
    "OilRegimeClassifier",
    "OilRegimeState",
    "SupplyDemandBalance",
    "SupplyDemandCalculator",
    "TrendDirection",
]
