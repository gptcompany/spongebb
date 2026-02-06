"""Real rates and breakeven inflation analysis.

Calculates breakeven inflation rates (BEI) and real yields using TIPS spreads:
- BEI = Nominal yield - TIPS yield (market's inflation expectation)
- 5Y5Y Forward = 2 * BEI_10Y - BEI_5Y (forward inflation expectation)

References:
- Federal Reserve: https://fred.stlouisfed.org/series/DFII10
- Cleveland Fed: Inflation expectations decomposition
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from liquidity.collectors.fred import FredCollector
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)


# FRED series for TIPS and nominal yields
REAL_RATES_SERIES: dict[str, str] = {
    # TIPS (real) yields - Treasury Inflation-Protected Securities
    "tips_10y": "DFII10",  # 10-Year Treasury Inflation-Indexed Security, Constant Maturity
    "tips_5y": "DFII5",  # 5-Year Treasury Inflation-Indexed Security, Constant Maturity
    # Nominal yields (for BEI calculation)
    "nominal_10y": "DGS10",  # 10-Year Treasury Constant Maturity Rate
    "nominal_5y": "DGS5",  # 5-Year Treasury Constant Maturity Rate
}


@dataclass
class RealRatesState:
    """Current state of real rates and breakeven inflation.

    Attributes:
        timestamp: Observation timestamp.
        tips_10y: 10-year TIPS yield (real rate).
        tips_5y: 5-year TIPS yield (real rate).
        nominal_10y: 10-year nominal Treasury yield.
        nominal_5y: 5-year nominal Treasury yield.
        bei_10y: 10-year breakeven inflation (nominal_10y - tips_10y).
        bei_5y: 5-year breakeven inflation (nominal_5y - tips_5y).
        forward_5y5y: 5-year forward breakeven starting in 5 years.
    """

    timestamp: datetime
    tips_10y: float
    tips_5y: float
    nominal_10y: float
    nominal_5y: float
    bei_10y: float  # nominal_10y - tips_10y
    bei_5y: float  # nominal_5y - tips_5y
    forward_5y5y: float  # 2 * bei_10y - bei_5y (linearized approximation)


class RealRatesAnalyzer:
    """Analyze real rates and breakeven inflation expectations.

    Breakeven inflation (BEI) represents the market's inflation expectation,
    derived from the spread between nominal and real (TIPS) yields.

    The 5Y5Y forward rate shows the market's expected average inflation
    from 5 years to 10 years in the future, filtering out near-term noise.

    Example:
        analyzer = RealRatesAnalyzer()

        # Get current state
        state = await analyzer.get_current_state()
        print(f"10Y BEI: {state.bei_10y:.2f}%")
        print(f"5Y5Y Forward: {state.forward_5y5y:.2f}%")

        # Get historical data
        df = await analyzer.calculate_breakeven(
            start_date=datetime(2020, 1, 1),
            end_date=datetime(2024, 1, 1),
        )
    """

    def __init__(
        self,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize real rates analyzer.

        Args:
            settings: Optional settings override.
            **kwargs: Additional arguments passed to FREDCollector.
        """
        self._settings = settings or get_settings()
        self._collector = FredCollector(
            name="real_rates",
            settings=self._settings,
            **kwargs,
        )

    async def calculate_breakeven(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate breakeven inflation rates over a date range.

        BEI = Nominal yield - TIPS yield (real yield)

        The breakeven represents the inflation rate at which an investor
        would be indifferent between holding a nominal bond or a TIPS.

        Args:
            start_date: Start date for calculation. Defaults to 1 year ago.
            end_date: End date for calculation. Defaults to today.

        Returns:
            DataFrame with columns:
                - timestamp: Date
                - tips_10y: 10-year TIPS yield
                - tips_5y: 5-year TIPS yield
                - nominal_10y: 10-year nominal yield
                - nominal_5y: 5-year nominal yield
                - bei_10y: 10-year breakeven inflation
                - bei_5y: 5-year breakeven inflation
                - forward_5y5y: 5Y5Y forward inflation rate
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now(UTC)

        # Fetch all required series
        series_ids = list(REAL_RATES_SERIES.values())
        raw_data = await self._collector.collect(
            symbols=series_ids,
            start_date=start_date,
            end_date=end_date,
        )

        if raw_data.empty:
            logger.warning("No data returned for real rates calculation")
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "tips_10y",
                    "tips_5y",
                    "nominal_10y",
                    "nominal_5y",
                    "bei_10y",
                    "bei_5y",
                    "forward_5y5y",
                ]
            )

        # Pivot to wide format
        pivot = raw_data.pivot(
            index="timestamp",
            columns="series_id",
            values="value",
        )

        # Check for required columns
        required = {"DFII10", "DFII5", "DGS10", "DGS5"}
        available = set(pivot.columns)
        if not required.issubset(available):
            missing = required - available
            logger.warning("Missing required series for BEI calculation: %s", missing)
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "tips_10y",
                    "tips_5y",
                    "nominal_10y",
                    "nominal_5y",
                    "bei_10y",
                    "bei_5y",
                    "forward_5y5y",
                ]
            )

        # Calculate breakeven inflation
        # BEI = Nominal - Real (TIPS)
        result = pd.DataFrame(
            {
                "timestamp": pivot.index,
                "tips_10y": pivot["DFII10"].values,
                "tips_5y": pivot["DFII5"].values,
                "nominal_10y": pivot["DGS10"].values,
                "nominal_5y": pivot["DGS5"].values,
                "bei_10y": (pivot["DGS10"] - pivot["DFII10"]).values,
                "bei_5y": (pivot["DGS5"] - pivot["DFII5"]).values,
            }
        )

        # Calculate 5Y5Y forward inflation rate
        # Forward_5Y5Y = 2 * BEI_10Y - BEI_5Y (linearized approximation)
        result["forward_5y5y"] = 2 * result["bei_10y"] - result["bei_5y"]

        # Drop rows with NaN values and sort
        result = result.dropna().sort_values("timestamp").reset_index(drop=True)

        logger.info(
            "Calculated BEI for %d observations. "
            "Latest 10Y BEI: %.2f%%, 5Y5Y Forward: %.2f%%",
            len(result),
            result["bei_10y"].iloc[-1] if len(result) > 0 else 0,
            result["forward_5y5y"].iloc[-1] if len(result) > 0 else 0,
        )

        return result

    async def get_current_state(self) -> RealRatesState:
        """Get the current state of real rates and breakeven inflation.

        Fetches the most recent available data point for all series.

        Returns:
            RealRatesState with current values.

        Raises:
            ValueError: If no data is available.
        """
        # Fetch recent data (last 7 days to account for holidays/weekends)
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=7)

        df = await self.calculate_breakeven(start_date=start_date, end_date=end_date)

        if df.empty:
            raise ValueError("No real rates data available")

        # Get the latest row
        latest = df.iloc[-1]

        return RealRatesState(
            timestamp=latest["timestamp"],
            tips_10y=float(latest["tips_10y"]),
            tips_5y=float(latest["tips_5y"]),
            nominal_10y=float(latest["nominal_10y"]),
            nominal_5y=float(latest["nominal_5y"]),
            bei_10y=float(latest["bei_10y"]),
            bei_5y=float(latest["bei_5y"]),
            forward_5y5y=float(latest["forward_5y5y"]),
        )

    async def get_bei_history(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        resample: str | None = None,
    ) -> pd.DataFrame:
        """Get breakeven inflation history with optional resampling.

        Args:
            start_date: Start date. Defaults to 1 year ago.
            end_date: End date. Defaults to today.
            resample: Optional resample frequency (e.g., 'W', 'M', 'Q').

        Returns:
            DataFrame with BEI series.
        """
        df = await self.calculate_breakeven(start_date, end_date)

        if df.empty or resample is None:
            return df

        # Set timestamp as index for resampling
        df = df.set_index("timestamp")

        # Resample using mean
        resampled = df.resample(resample).mean()

        return resampled.dropna().reset_index()

    def interpret_bei(self, bei_10y: float) -> str:
        """Interpret the 10-year breakeven inflation level.

        Args:
            bei_10y: 10-year breakeven inflation rate.

        Returns:
            Interpretation string.
        """
        if bei_10y < 1.5:
            return "Deflationary pressure / Very low inflation expectations"
        elif bei_10y < 2.0:
            return "Below Fed target / Subdued inflation expectations"
        elif bei_10y < 2.5:
            return "Near Fed target / Well-anchored expectations"
        elif bei_10y < 3.0:
            return "Above Fed target / Elevated inflation concerns"
        else:
            return "High inflation expectations / Potential unanchoring"

    def interpret_forward_5y5y(self, forward_5y5y: float) -> str:
        """Interpret the 5Y5Y forward inflation rate.

        The 5Y5Y forward is closely watched by the Fed as a measure
        of long-term inflation expectations anchoring.

        Args:
            forward_5y5y: 5-year forward breakeven starting in 5 years.

        Returns:
            Interpretation string.
        """
        if forward_5y5y < 1.8:
            return "Well below target / Potential deflation concerns"
        elif forward_5y5y < 2.2:
            return "Near Fed target / Expectations well-anchored"
        elif forward_5y5y < 2.5:
            return "Slightly elevated / Monitor for persistence"
        else:
            return "Elevated / Potential unanchoring of expectations"
