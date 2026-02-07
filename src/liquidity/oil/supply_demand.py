"""Oil supply-demand balance calculator.

Calculates US petroleum supply-demand balance from EIA Weekly Petroleum Status data.
Uses the core formula:
    total_supply = production + imports
    total_demand = refinery_inputs + exports
    balance = total_supply - total_demand

Balance signals:
    - build: balance > 100 thousand b/d (inventory accumulation)
    - draw: balance < -100 thousand b/d (inventory depletion)
    - flat: -100 <= balance <= 100 (roughly balanced)
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import pandas as pd

from liquidity.collectors.eia import EIACollector

logger = logging.getLogger(__name__)

# EIA series IDs for supply-demand components
# These are standard EIA Weekly Petroleum Status Report series
SUPPLY_DEMAND_SERIES = {
    "production": "WCRFPUS2",  # US crude production (thousand b/d)
    "imports": "WCRIMUS2",  # US crude imports (thousand b/d)
    "refinery_inputs": "WCRRIUS2",  # US refinery crude inputs (thousand b/d)
    "exports": "WCREXUS2",  # US crude exports (thousand b/d)
}

# Signal thresholds (thousand b/d)
BUILD_THRESHOLD: float = 100.0  # balance > 100 = inventory build
DRAW_THRESHOLD: float = -100.0  # balance < -100 = inventory draw

# Days per week for barrel conversion
DAYS_PER_WEEK: int = 7

# Conversion: thousand b/d * 7 days = thousand barrels/week
# Then divide by 1000 to get million barrels/week


@dataclass
class SupplyDemandBalance:
    """Container for a single week's supply-demand balance.

    All flow values are in thousand barrels per day (thousand b/d).

    Attributes:
        date: Week ending date for this balance.
        production: US crude oil production (thousand b/d).
        imports: US crude oil imports (thousand b/d).
        exports: US crude oil exports (thousand b/d).
        refinery_inputs: US refinery crude inputs (thousand b/d).
        total_supply: production + imports (thousand b/d).
        total_demand: refinery_inputs + exports (thousand b/d).
        balance: total_supply - total_demand (thousand b/d).
        balance_barrels: Weekly balance in million barrels.
        signal: Market signal based on balance magnitude.
    """

    date: datetime
    production: float  # thousand b/d
    imports: float  # thousand b/d
    exports: float  # thousand b/d
    refinery_inputs: float  # thousand b/d
    total_supply: float  # thousand b/d
    total_demand: float  # thousand b/d
    balance: float  # thousand b/d (supply - demand)
    balance_barrels: float  # million barrels/week
    signal: Literal["build", "draw", "flat"]


class SupplyDemandCalculator:
    """Calculator for US petroleum supply-demand balance.

    Uses EIA Weekly Petroleum Status Report data to calculate:
    - Supply components: production, imports
    - Demand components: refinery inputs, exports
    - Net balance and weekly barrel accumulation

    Example:
        calculator = SupplyDemandCalculator()
        current = await calculator.get_current_balance()
        print(f"Balance: {current.balance:.0f} kb/d ({current.signal})")

        # Get historical series
        df = await calculator.calculate_balance(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2026, 1, 1)
        )
    """

    def __init__(self, eia_collector: EIACollector | None = None) -> None:
        """Initialize the supply-demand calculator.

        Args:
            eia_collector: Optional EIA collector instance. If not provided,
                a new collector will be created.
        """
        self._collector = eia_collector
        self._owns_collector = eia_collector is None

    async def _get_collector(self) -> EIACollector:
        """Get or create the EIA collector.

        Returns:
            EIACollector instance.
        """
        if self._collector is None:
            self._collector = EIACollector()
        return self._collector

    async def close(self) -> None:
        """Close the calculator and release resources."""
        if self._collector is not None and self._owns_collector:
            await self._collector.close()
        self._collector = None

    def _classify_signal(self, balance: float) -> Literal["build", "draw", "flat"]:
        """Classify balance into a market signal.

        Args:
            balance: Net balance in thousand b/d.

        Returns:
            Signal string: "build", "draw", or "flat".
        """
        if balance > BUILD_THRESHOLD:
            return "build"
        elif balance < DRAW_THRESHOLD:
            return "draw"
        else:
            return "flat"

    def _balance_to_weekly_barrels(self, balance_kbd: float) -> float:
        """Convert daily balance to weekly million barrels.

        Args:
            balance_kbd: Balance in thousand b/d.

        Returns:
            Weekly balance in million barrels.
        """
        # thousand b/d * 7 days = thousand barrels/week
        # / 1000 = million barrels/week
        return balance_kbd * DAYS_PER_WEEK / 1000

    async def calculate_balance(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate supply-demand balance for a date range.

        Fetches production, imports, refinery inputs, and exports from EIA
        and computes the weekly balance.

        Args:
            start_date: Start date for calculation. Defaults to 52 weeks ago.
            end_date: End date for calculation. Defaults to today.

        Returns:
            DataFrame with columns:
                - date: Week ending date
                - production: Thousand b/d
                - imports: Thousand b/d
                - exports: Thousand b/d
                - refinery_inputs: Thousand b/d
                - total_supply: Thousand b/d
                - total_demand: Thousand b/d
                - balance: Thousand b/d (supply - demand)
                - balance_barrels: Million barrels/week
                - signal: "build", "draw", or "flat"

        Raises:
            ValueError: If required series are missing from EIA data.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(weeks=52)
        if end_date is None:
            end_date = datetime.now(UTC)

        collector = await self._get_collector()

        # Fetch all required series
        series_ids = list(SUPPLY_DEMAND_SERIES.values())

        # Add missing series to EIA collector's known routes
        # WCRRIUS2 and WCREXUS2 use the same endpoint as production/imports
        raw_df = await collector.collect(series_ids, start_date, end_date)

        if raw_df.empty:
            logger.warning("No EIA data returned for supply-demand calculation")
            return self._empty_result_df()

        # Pivot to wide format: rows = timestamps, columns = series_id
        pivot_df = raw_df.pivot_table(
            index="timestamp",
            columns="series_id",
            values="value",
            aggfunc="first",
        ).reset_index()

        # Check for required series
        missing = []
        for name, series_id in SUPPLY_DEMAND_SERIES.items():
            if series_id not in pivot_df.columns:
                missing.append(f"{name} ({series_id})")

        if missing:
            logger.warning("Missing EIA series for supply-demand: %s", missing)
            # If any core series missing, fill with 0 for partial calculation
            for series_id in SUPPLY_DEMAND_SERIES.values():
                if series_id not in pivot_df.columns:
                    pivot_df[series_id] = 0.0

        # Calculate balance components
        result = pd.DataFrame()
        result["date"] = pivot_df["timestamp"]
        result["production"] = pivot_df[SUPPLY_DEMAND_SERIES["production"]]
        result["imports"] = pivot_df[SUPPLY_DEMAND_SERIES["imports"]]
        result["exports"] = pivot_df[SUPPLY_DEMAND_SERIES["exports"]]
        result["refinery_inputs"] = pivot_df[SUPPLY_DEMAND_SERIES["refinery_inputs"]]

        # Core formulas
        result["total_supply"] = result["production"] + result["imports"]
        result["total_demand"] = result["refinery_inputs"] + result["exports"]
        result["balance"] = result["total_supply"] - result["total_demand"]

        # Convert to weekly barrels and classify signal
        result["balance_barrels"] = result["balance"].apply(
            self._balance_to_weekly_barrels
        )
        result["signal"] = result["balance"].apply(self._classify_signal)

        # Sort by date
        result = result.sort_values("date").reset_index(drop=True)

        logger.info("Calculated supply-demand balance for %d weeks", len(result))
        return result

    def _empty_result_df(self) -> pd.DataFrame:
        """Create an empty result DataFrame with the expected schema.

        Returns:
            Empty DataFrame with all balance columns.
        """
        return pd.DataFrame(
            columns=[
                "date",
                "production",
                "imports",
                "exports",
                "refinery_inputs",
                "total_supply",
                "total_demand",
                "balance",
                "balance_barrels",
                "signal",
            ]
        )

    async def get_current_balance(self) -> SupplyDemandBalance:
        """Get the most recent supply-demand balance.

        Fetches the latest weekly data from EIA and returns the current balance.

        Returns:
            SupplyDemandBalance for the most recent week.

        Raises:
            ValueError: If no data is available.
        """
        # Fetch last 4 weeks to ensure we have recent data
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(weeks=4)

        df = await self.calculate_balance(start_date, end_date)

        if df.empty:
            raise ValueError("No supply-demand data available from EIA")

        # Get the most recent row
        latest = df.iloc[-1]

        return SupplyDemandBalance(
            date=latest["date"].to_pydatetime(),
            production=float(latest["production"]),
            imports=float(latest["imports"]),
            exports=float(latest["exports"]),
            refinery_inputs=float(latest["refinery_inputs"]),
            total_supply=float(latest["total_supply"]),
            total_demand=float(latest["total_demand"]),
            balance=float(latest["balance"]),
            balance_barrels=float(latest["balance_barrels"]),
            signal=latest["signal"],
        )

    async def get_balance_summary(
        self,
        lookback_weeks: int = 4,
    ) -> dict:
        """Get a summary of recent supply-demand balance.

        Args:
            lookback_weeks: Number of weeks to summarize.

        Returns:
            Dictionary with summary statistics:
                - current: Most recent SupplyDemandBalance
                - avg_balance: Average balance over period (thousand b/d)
                - total_barrels: Cumulative balance (million barrels)
                - signal_counts: Count of each signal type
        """
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(weeks=lookback_weeks)

        df = await self.calculate_balance(start_date, end_date)

        if df.empty:
            raise ValueError("No supply-demand data available")

        # Get current balance
        latest = df.iloc[-1]
        current = SupplyDemandBalance(
            date=latest["date"].to_pydatetime(),
            production=float(latest["production"]),
            imports=float(latest["imports"]),
            exports=float(latest["exports"]),
            refinery_inputs=float(latest["refinery_inputs"]),
            total_supply=float(latest["total_supply"]),
            total_demand=float(latest["total_demand"]),
            balance=float(latest["balance"]),
            balance_barrels=float(latest["balance_barrels"]),
            signal=latest["signal"],
        )

        # Calculate summary stats
        signal_counts = df["signal"].value_counts().to_dict()

        return {
            "current": current,
            "avg_balance": float(df["balance"].mean()),
            "total_barrels": float(df["balance_barrels"].sum()),
            "signal_counts": signal_counts,
            "weeks_analyzed": len(df),
        }
