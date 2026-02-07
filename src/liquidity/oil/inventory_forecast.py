"""Oil inventory forecaster with YoY and seasonal analysis.

Analyzes US crude oil inventory data from EIA to calculate:
- Year-over-year changes (vs same week last year)
- Comparison to 5-year seasonal average
- Days of supply calculation
- Weekly trend classification
- 4-week inventory forecast

Based on EIA Weekly Petroleum Status Report data (WCESTUS1 series).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from liquidity.collectors.eia import EIACollector

logger = logging.getLogger(__name__)


class TrendDirection(str, Enum):
    """Weekly inventory trend direction."""

    BUILDING = "building"  # Stocks increasing
    DRAWING = "drawing"  # Stocks decreasing
    STABLE = "stable"  # Minimal change


@dataclass
class InventoryForecast:
    """Container for inventory analysis results."""

    date: datetime
    current_stocks: float  # million barrels
    yoy_change: float  # vs last year (million barrels)
    yoy_change_pct: float  # vs last year (%)
    vs_5yr_avg: float  # vs 5-year average (million barrels)
    vs_5yr_avg_pct: float  # vs 5-year average (%)
    days_of_supply: float  # stocks / daily refinery inputs
    weekly_trend: TrendDirection  # building, drawing, stable
    forecast_4wk: float  # 4-week forecast (million barrels)


# Default refinery input rate (thousand b/d) when actual data unavailable
# Source: EIA average US refinery crude inputs ~15-17 million b/d
DEFAULT_REFINERY_INPUTS_KBD: float = 16_000.0

# Threshold for trend classification (million barrels per week)
TREND_THRESHOLD_MB: float = 1.0  # +/- 1 MB/week is stable


class InventoryForecaster:
    """Analyze crude oil inventory with YoY and seasonal comparisons.

    Fetches EIA data and calculates:
    - Year-over-year changes (shift 52 weeks)
    - 5-year seasonal average for same week of year
    - Days of supply based on refinery inputs
    - Trend classification (building/drawing/stable)
    - 4-week linear forecast

    Example:
        from liquidity.collectors.eia import EIACollector

        forecaster = InventoryForecaster()
        analysis = await forecaster.get_current_analysis()

        print(f"Current stocks: {analysis.current_stocks:.1f} MB")
        print(f"YoY change: {analysis.yoy_change_pct:+.1f}%")
        print(f"Trend: {analysis.weekly_trend.value}")
    """

    def __init__(
        self,
        eia_collector: "EIACollector | None" = None,
        trend_threshold: float = TREND_THRESHOLD_MB,
    ) -> None:
        """Initialize inventory forecaster.

        Args:
            eia_collector: Optional EIA collector instance. If None, creates new.
            trend_threshold: Threshold for trend classification in million barrels.
        """
        self._collector = eia_collector
        self._trend_threshold = trend_threshold

    async def _get_collector(self) -> "EIACollector":
        """Get or create EIA collector instance.

        Returns:
            Configured EIACollector instance.
        """
        if self._collector is None:
            from liquidity.collectors.eia import EIACollector

            self._collector = EIACollector()
        return self._collector

    async def analyze_inventory(
        self,
        lookback_years: int = 5,
    ) -> pd.DataFrame:
        """Analyze inventory data with YoY and seasonal metrics.

        Fetches historical data and calculates:
        - Year-over-year change for each data point
        - 5-year average for same week of year
        - Days of supply calculation

        Args:
            lookback_years: Years of historical data to fetch. Defaults to 5.

        Returns:
            DataFrame with columns:
            - timestamp: Data date
            - stocks_mb: Crude stocks in million barrels
            - stocks_kbd: Original value in thousand barrels
            - week_of_year: ISO week number
            - yoy_change_mb: Change vs same week last year (MB)
            - yoy_change_pct: Change vs same week last year (%)
            - avg_5yr_mb: 5-year average for this week (MB)
            - vs_5yr_avg_mb: Difference from 5-year average (MB)
            - vs_5yr_avg_pct: Difference from 5-year average (%)
            - change_1wk_mb: Week-over-week change (MB)
            - change_4wk_avg_mb: 4-week average change (MB)
        """
        collector = await self._get_collector()

        # Fetch extended history for 5-year average calculation
        start_date = datetime.now(UTC) - timedelta(weeks=52 * (lookback_years + 1))
        end_date = datetime.now(UTC)

        df = await collector.collect(["WCESTUS1"], start_date, end_date)

        if df.empty:
            logger.warning("No inventory data returned from EIA")
            return pd.DataFrame()

        # Filter to crude stocks series
        stocks = df[df["series_id"] == "WCESTUS1"].copy()
        if stocks.empty:
            logger.warning("WCESTUS1 series not found in data")
            return pd.DataFrame()

        # Sort by date
        stocks = stocks.sort_values("timestamp").reset_index(drop=True)

        # Convert to million barrels (from thousand barrels)
        stocks["stocks_mb"] = stocks["value"] / 1000.0
        stocks["stocks_kbd"] = stocks["value"]

        # Add week of year for seasonal analysis
        stocks["week_of_year"] = stocks["timestamp"].dt.isocalendar().week.astype(int)
        stocks["year"] = stocks["timestamp"].dt.year

        # Calculate year-over-year change (shift 52 weeks)
        stocks["stocks_yoy"] = stocks["stocks_mb"].shift(52)
        stocks["yoy_change_mb"] = stocks["stocks_mb"] - stocks["stocks_yoy"]
        stocks["yoy_change_pct"] = (
            stocks["yoy_change_mb"] / stocks["stocks_yoy"] * 100
        ).replace([np.inf, -np.inf], np.nan)

        # Calculate 5-year average for each week of year
        stocks = self._add_5yr_average(stocks)

        # Calculate week-over-week and 4-week average change
        stocks["change_1wk_mb"] = stocks["stocks_mb"].diff()
        stocks["change_4wk_avg_mb"] = stocks["change_1wk_mb"].rolling(4).mean()

        # Select output columns
        output_cols = [
            "timestamp",
            "stocks_mb",
            "stocks_kbd",
            "week_of_year",
            "yoy_change_mb",
            "yoy_change_pct",
            "avg_5yr_mb",
            "vs_5yr_avg_mb",
            "vs_5yr_avg_pct",
            "change_1wk_mb",
            "change_4wk_avg_mb",
        ]

        return stocks[output_cols].copy()

    def _add_5yr_average(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add 5-year seasonal average columns.

        Calculates the average inventory level for the same week of year
        across the prior 5 years.

        Args:
            df: DataFrame with week_of_year, year, stocks_mb columns.

        Returns:
            DataFrame with added avg_5yr_mb, vs_5yr_avg_mb, vs_5yr_avg_pct columns.
        """
        result = df.copy()
        avg_5yr = []
        vs_avg = []
        vs_avg_pct = []

        for _, row in result.iterrows():
            current_week = row["week_of_year"]
            current_year = row["year"]
            current_stocks = row["stocks_mb"]

            # Get same week from prior 5 years
            mask = (result["week_of_year"] == current_week) & (
                result["year"].between(current_year - 5, current_year - 1)
            )
            historical = result.loc[mask, "stocks_mb"]

            if len(historical) >= 3:  # Need at least 3 years for meaningful average
                avg_val = historical.mean()
                diff = current_stocks - avg_val
                pct = (diff / avg_val * 100) if avg_val != 0 else 0.0
            else:
                avg_val = np.nan
                diff = np.nan
                pct = np.nan

            avg_5yr.append(avg_val)
            vs_avg.append(diff)
            vs_avg_pct.append(pct)

        result["avg_5yr_mb"] = avg_5yr
        result["vs_5yr_avg_mb"] = vs_avg
        result["vs_5yr_avg_pct"] = vs_avg_pct

        return result

    async def get_current_analysis(self) -> InventoryForecast:
        """Get current inventory analysis with all metrics.

        Returns:
            InventoryForecast dataclass with current analysis.

        Raises:
            ValueError: If insufficient data for analysis.
        """
        df = await self.analyze_inventory()

        if df.empty:
            raise ValueError("No inventory data available for analysis")

        # Get latest row with valid data
        latest = df.dropna(subset=["stocks_mb"]).iloc[-1]

        # Calculate days of supply
        days_of_supply = await self._calculate_days_of_supply(latest["stocks_kbd"])

        # Determine trend from 4-week average change
        weekly_trend = self._classify_trend(latest.get("change_4wk_avg_mb", 0))

        # Calculate 4-week forecast
        forecast_4wk = await self.forecast_4wk(df)

        return InventoryForecast(
            date=latest["timestamp"].to_pydatetime()
            if hasattr(latest["timestamp"], "to_pydatetime")
            else latest["timestamp"],
            current_stocks=float(latest["stocks_mb"]),
            yoy_change=float(latest.get("yoy_change_mb", 0) or 0),
            yoy_change_pct=float(latest.get("yoy_change_pct", 0) or 0),
            vs_5yr_avg=float(latest.get("vs_5yr_avg_mb", 0) or 0),
            vs_5yr_avg_pct=float(latest.get("vs_5yr_avg_pct", 0) or 0),
            days_of_supply=days_of_supply,
            weekly_trend=weekly_trend,
            forecast_4wk=forecast_4wk,
        )

    async def _calculate_days_of_supply(
        self,
        stocks_kbd: float,
    ) -> float:
        """Calculate days of supply based on refinery inputs.

        Days of supply = Total stocks / Daily refinery inputs

        Args:
            stocks_kbd: Current stocks in thousand barrels.

        Returns:
            Days of supply at current consumption rate.
        """
        collector = await self._get_collector()

        # Try to get actual refinery input data
        # For now, use default since we don't have refinery inputs in the series
        # In production, this would fetch WCRRIUS2 (refinery crude oil inputs)
        refinery_inputs_kbd = DEFAULT_REFINERY_INPUTS_KBD

        try:
            # Attempt to get refinery utilization as proxy
            util_df = await collector.collect_refinery_utilization(
                regions=["us"], lookback_weeks=4
            )
            if not util_df.empty:
                latest_util = (
                    util_df.sort_values("timestamp").iloc[-1]["value"] / 100.0
                )
                # Adjust inputs based on utilization (max capacity ~18M b/d)
                refinery_inputs_kbd = 18_000.0 * latest_util
        except Exception as e:
            logger.debug("Could not get refinery utilization: %s", e)

        # Calculate days of supply
        days = stocks_kbd / refinery_inputs_kbd if refinery_inputs_kbd > 0 else 0.0

        return round(days, 1)

    def _classify_trend(self, change_4wk_avg: float | None) -> TrendDirection:
        """Classify weekly trend based on 4-week average change.

        Args:
            change_4wk_avg: 4-week average weekly change in million barrels.

        Returns:
            TrendDirection enum value.
        """
        if change_4wk_avg is None or np.isnan(change_4wk_avg):
            return TrendDirection.STABLE

        if change_4wk_avg > self._trend_threshold:
            return TrendDirection.BUILDING
        elif change_4wk_avg < -self._trend_threshold:
            return TrendDirection.DRAWING
        else:
            return TrendDirection.STABLE

    async def forecast_4wk(
        self,
        df: pd.DataFrame | None = None,
    ) -> float:
        """Generate 4-week inventory forecast.

        Uses linear regression on recent trend to project inventory
        4 weeks forward.

        Args:
            df: Optional pre-computed analysis DataFrame. If None, fetches data.

        Returns:
            Forecasted inventory level in million barrels.
        """
        if df is None:
            df = await self.analyze_inventory()

        if df.empty or len(df) < 8:
            logger.warning("Insufficient data for 4-week forecast")
            return 0.0

        # Use last 8 weeks for trend calculation
        recent = df.tail(8).copy()

        # Simple linear regression for forecast
        x = np.arange(len(recent))
        y = recent["stocks_mb"].values

        # Remove any NaN values
        mask = ~np.isnan(y)
        if mask.sum() < 4:
            # Not enough valid data, use simple average change
            avg_change = recent["change_1wk_mb"].mean()
            if np.isnan(avg_change):
                avg_change = 0.0
            return float(y[mask][-1] + avg_change * 4) if mask.any() else 0.0

        x_valid = x[mask]
        y_valid = y[mask]

        # Calculate slope and intercept
        n = len(x_valid)
        sum_x = x_valid.sum()
        sum_y = y_valid.sum()
        sum_xy = (x_valid * y_valid).sum()
        sum_xx = (x_valid * x_valid).sum()

        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            # Flat trend, return current value
            return float(y_valid[-1])

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

        # Forecast 4 weeks ahead (x = len(recent) + 3 for 4 weeks out)
        forecast_x = len(recent) + 3
        forecast_value = slope * forecast_x + intercept

        return round(forecast_value, 2)

    async def close(self) -> None:
        """Close the underlying EIA collector."""
        if self._collector is not None:
            await self._collector.close()
