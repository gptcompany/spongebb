"""Positioning metrics analyzer for CFTC COT data.

Calculates commercial/speculator ratios, percentile ranks, and detects extreme
positioning conditions for trading signals.

Reference: CFTC Commitment of Traders Disaggregated Futures Only report.
"""

import logging
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class ExtremeType(str, Enum):
    """Types of extreme positioning conditions."""

    SPEC_EXTREME_LONG = "SPEC_EXTREME_LONG"
    SPEC_EXTREME_SHORT = "SPEC_EXTREME_SHORT"
    COMM_EXTREME_LONG = "COMM_EXTREME_LONG"
    COMM_EXTREME_SHORT = "COMM_EXTREME_SHORT"


@dataclass
class PositioningMetrics:
    """Container for positioning analysis results."""

    commodity: str
    timestamp: date
    comm_net: int
    spec_net: int
    swap_net: int
    open_interest: int

    # Derived metrics
    comm_spec_ratio: float
    spec_long_short_ratio: float
    comm_pct_of_oi: float
    spec_pct_of_oi: float

    # Percentile ranks (0-100)
    comm_net_percentile: float
    spec_net_percentile: float

    # Extreme flags
    is_spec_extreme_long: bool
    is_spec_extreme_short: bool
    is_comm_extreme_long: bool
    is_comm_extreme_short: bool


# Default commodities tracked
DEFAULT_COMMODITIES = ["WTI", "GOLD", "COPPER", "SILVER", "NATGAS"]


class PositioningAnalyzer:
    """Analyze COT positioning data for trading signals.

    Provides:
    - Ratio calculations (commercial/speculator, long/short)
    - Rolling percentile ranks with configurable lookback
    - Extreme positioning detection at 10th/90th percentiles

    Example:
        analyzer = PositioningAnalyzer(lookback_weeks=52)

        # Get percentile ranks
        percentiles_df = analyzer.calculate_percentile_ranks(cot_data, "WTI")

        # Detect extremes
        extremes_df = analyzer.detect_extremes(all_data)
    """

    # Percentile thresholds for extremes
    EXTREME_HIGH = 90  # Top 10%
    EXTREME_LOW = 10  # Bottom 10%

    def __init__(
        self,
        lookback_weeks: int = 52,
        extreme_high: int = 90,
        extreme_low: int = 10,
    ) -> None:
        """Initialize positioning analyzer.

        Args:
            lookback_weeks: Rolling window for percentile calculation (default 52).
            extreme_high: Upper percentile threshold for extreme detection (default 90).
            extreme_low: Lower percentile threshold for extreme detection (default 10).
        """
        self.lookback_weeks = lookback_weeks
        self.EXTREME_HIGH = extreme_high
        self.EXTREME_LOW = extreme_low

    def calculate_ratios(self, row: dict[str, Any]) -> dict[str, float]:
        """Calculate positioning ratios from raw position data.

        Args:
            row: Dict with comm_long, comm_short, spec_long, spec_short, open_interest.

        Returns:
            Dict with calculated ratios:
            - comm_net: Commercial net position
            - spec_net: Speculator net position
            - comm_spec_ratio: Commercial/Speculator ratio
            - spec_long_short_ratio: Speculator long/short ratio
            - comm_pct_of_oi: Commercial positions as % of open interest
            - spec_pct_of_oi: Speculator positions as % of open interest
        """
        comm_long = row.get("comm_long", 0)
        comm_short = row.get("comm_short", 0)
        spec_long = row.get("spec_long", 0)
        spec_short = row.get("spec_short", 0)
        oi = row.get("open_interest", 1)  # Avoid div by zero

        if oi == 0:
            oi = 1  # Safety check

        comm_net = comm_long - comm_short
        spec_net = spec_long - spec_short

        # Handle division by zero for ratios
        if spec_net != 0:
            comm_spec_ratio = comm_net / spec_net
        else:
            comm_spec_ratio = 0.0

        if spec_short > 0:
            spec_long_short_ratio = spec_long / spec_short
        else:
            spec_long_short_ratio = float("inf") if spec_long > 0 else 0.0

        return {
            "comm_net": float(comm_net),
            "spec_net": float(spec_net),
            "comm_spec_ratio": comm_spec_ratio,
            "spec_long_short_ratio": spec_long_short_ratio,
            "comm_pct_of_oi": (comm_long + comm_short) / oi * 100,
            "spec_pct_of_oi": (spec_long + spec_short) / oi * 100,
        }

    def _percentile_rank(self, window: pd.Series) -> float:
        """Calculate percentile of last value vs prior values.

        Uses 'weak' method to avoid deprecation warning and ensure
        consistent behavior. Excludes current value from comparison
        set to avoid look-ahead bias.

        Args:
            window: Rolling window of values.

        Returns:
            Percentile rank (0-100) of the last value.
        """
        if len(window) < 2:
            return 50.0  # Default to median if not enough history

        historical = window.iloc[:-1].values  # All values except current
        current = window.iloc[-1]

        # Handle NaN values
        historical = historical[~np.isnan(historical)]
        if len(historical) == 0 or np.isnan(current):
            return 50.0

        return float(stats.percentileofscore(historical, current, kind="weak"))

    def calculate_percentile_ranks(
        self,
        df: pd.DataFrame,
        commodity: str,
    ) -> pd.DataFrame:
        """Add percentile ranks to positioning data.

        Args:
            df: DataFrame from CFTCCOTCollector with series_id, timestamp, value.
            commodity: Commodity code (e.g., "WTI", "GOLD").

        Returns:
            DataFrame with percentile series in standard format:
            timestamp, series_id, source, value, unit.
        """
        comm_series = f"cot_{commodity.lower()}_comm_net"
        spec_series = f"cot_{commodity.lower()}_spec_net"

        # Get historical values
        comm_data = df[df["series_id"] == comm_series].sort_values("timestamp")
        spec_data = df[df["series_id"] == spec_series].sort_values("timestamp")

        if comm_data.empty or spec_data.empty:
            logger.warning("No data found for %s", commodity)
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        comm_values = comm_data.set_index("timestamp")["value"]
        spec_values = spec_data.set_index("timestamp")["value"]

        # Calculate rolling percentiles
        # min_periods must be <= window size
        window = min(self.lookback_weeks, len(comm_values))
        min_periods = min(10, window)
        comm_pctl = comm_values.rolling(window, min_periods=min_periods).apply(
            self._percentile_rank, raw=False
        )

        window = min(self.lookback_weeks, len(spec_values))
        min_periods = min(10, window)
        spec_pctl = spec_values.rolling(window, min_periods=min_periods).apply(
            self._percentile_rank, raw=False
        )

        # Create percentile series for output
        result = []

        for ts, pctl in comm_pctl.items():
            if not np.isnan(pctl):
                result.append(
                    {
                        "timestamp": ts,
                        "series_id": f"cot_{commodity.lower()}_comm_pctl",
                        "source": "calculated",
                        "value": pctl,
                        "unit": "percentile",
                    }
                )

        for ts, pctl in spec_pctl.items():
            if not np.isnan(pctl):
                result.append(
                    {
                        "timestamp": ts,
                        "series_id": f"cot_{commodity.lower()}_spec_pctl",
                        "source": "calculated",
                        "value": pctl,
                        "unit": "percentile",
                    }
                )

        return pd.DataFrame(result)

    def calculate_all_percentiles(
        self,
        df: pd.DataFrame,
        commodities: list[str] | None = None,
    ) -> pd.DataFrame:
        """Calculate percentile ranks for all commodities.

        Args:
            df: DataFrame from CFTCCOTCollector.
            commodities: List of commodity codes. Defaults to all tracked.

        Returns:
            Combined DataFrame with all percentile series.
        """
        if commodities is None:
            commodities = DEFAULT_COMMODITIES

        all_percentiles = []
        for commodity in commodities:
            pctl_df = self.calculate_percentile_ranks(df, commodity)
            if not pctl_df.empty:
                all_percentiles.append(pctl_df)

        if not all_percentiles:
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        return pd.concat(all_percentiles, ignore_index=True)

    def detect_extremes(
        self,
        df: pd.DataFrame,
        commodities: list[str] | None = None,
    ) -> pd.DataFrame:
        """Detect extreme positioning conditions.

        Args:
            df: DataFrame with percentile series (from calculate_all_percentiles).
            commodities: List of commodity codes to check.

        Returns:
            DataFrame with extreme conditions:
            timestamp, commodity, extreme_type, spec_percentile, comm_percentile.
        """
        if commodities is None:
            commodities = DEFAULT_COMMODITIES

        extremes = []

        for commodity in commodities:
            spec_pctl_series = f"cot_{commodity.lower()}_spec_pctl"
            comm_pctl_series = f"cot_{commodity.lower()}_comm_pctl"

            spec_pctl = df[df["series_id"] == spec_pctl_series].sort_values("timestamp")
            comm_pctl = df[df["series_id"] == comm_pctl_series].sort_values("timestamp")

            if spec_pctl.empty or comm_pctl.empty:
                continue

            latest_spec = spec_pctl.iloc[-1]
            latest_comm = comm_pctl.iloc[-1]

            # Determine extreme type (only one per commodity)
            extreme_type = None
            if latest_spec["value"] >= self.EXTREME_HIGH:
                extreme_type = ExtremeType.SPEC_EXTREME_LONG
            elif latest_spec["value"] <= self.EXTREME_LOW:
                extreme_type = ExtremeType.SPEC_EXTREME_SHORT
            elif latest_comm["value"] >= self.EXTREME_HIGH:
                extreme_type = ExtremeType.COMM_EXTREME_LONG
            elif latest_comm["value"] <= self.EXTREME_LOW:
                extreme_type = ExtremeType.COMM_EXTREME_SHORT

            if extreme_type:
                extremes.append(
                    {
                        "timestamp": latest_spec["timestamp"],
                        "commodity": commodity,
                        "extreme_type": extreme_type.value,
                        "spec_percentile": latest_spec["value"],
                        "comm_percentile": latest_comm["value"],
                    }
                )

        return pd.DataFrame(extremes)

    def analyze_commodity(
        self,
        df: pd.DataFrame,
        commodity: str,
    ) -> PositioningMetrics | None:
        """Analyze positioning for a single commodity.

        Args:
            df: DataFrame from CFTCCOTCollector.
            commodity: Commodity code.

        Returns:
            PositioningMetrics dataclass with all calculated values, or None if
            insufficient data.
        """
        commodity_lower = commodity.lower()

        # Get latest values for each series
        latest_date = df["timestamp"].max()
        latest = df[df["timestamp"] == latest_date]

        def _get_value(suffix: str, default: int = 0) -> int:
            series_id = f"cot_{commodity_lower}_{suffix}"
            row = latest[latest["series_id"] == series_id]
            return int(row["value"].iloc[0]) if not row.empty else default

        comm_net = _get_value("comm_net")
        spec_net = _get_value("spec_net")
        swap_net = _get_value("swap_net")
        oi = _get_value("oi")
        comm_long = _get_value("comm_long")
        comm_short = _get_value("comm_short")
        spec_long = _get_value("spec_long")
        spec_short = _get_value("spec_short")

        if oi == 0:
            logger.warning("No open interest data for %s", commodity)
            return None

        # Calculate percentiles
        percentiles_df = self.calculate_percentile_ranks(df, commodity)
        if percentiles_df.empty:
            comm_pctl = 50.0
            spec_pctl = 50.0
        else:
            comm_pctl_data = percentiles_df[
                percentiles_df["series_id"] == f"cot_{commodity_lower}_comm_pctl"
            ]
            spec_pctl_data = percentiles_df[
                percentiles_df["series_id"] == f"cot_{commodity_lower}_spec_pctl"
            ]

            comm_pctl = (
                comm_pctl_data["value"].iloc[-1] if not comm_pctl_data.empty else 50.0
            )
            spec_pctl = (
                spec_pctl_data["value"].iloc[-1] if not spec_pctl_data.empty else 50.0
            )

        # Calculate ratios
        ratios = self.calculate_ratios(
            {
                "comm_long": comm_long,
                "comm_short": comm_short,
                "spec_long": spec_long,
                "spec_short": spec_short,
                "open_interest": oi,
            }
        )

        return PositioningMetrics(
            commodity=commodity,
            timestamp=latest_date.date()
            if hasattr(latest_date, "date")
            else latest_date,
            comm_net=comm_net,
            spec_net=spec_net,
            swap_net=swap_net,
            open_interest=oi,
            comm_spec_ratio=ratios["comm_spec_ratio"],
            spec_long_short_ratio=ratios["spec_long_short_ratio"],
            comm_pct_of_oi=ratios["comm_pct_of_oi"],
            spec_pct_of_oi=ratios["spec_pct_of_oi"],
            comm_net_percentile=float(comm_pctl),
            spec_net_percentile=float(spec_pctl),
            is_spec_extreme_long=bool(spec_pctl >= self.EXTREME_HIGH),
            is_spec_extreme_short=bool(spec_pctl <= self.EXTREME_LOW),
            is_comm_extreme_long=bool(comm_pctl >= self.EXTREME_HIGH),
            is_comm_extreme_short=bool(comm_pctl <= self.EXTREME_LOW),
        )

    def analyze_all(
        self,
        df: pd.DataFrame,
        commodities: list[str] | None = None,
    ) -> list[PositioningMetrics]:
        """Analyze positioning for all commodities.

        Args:
            df: DataFrame from CFTCCOTCollector.
            commodities: List of commodity codes. Defaults to all tracked.

        Returns:
            List of PositioningMetrics for each commodity.
        """
        if commodities is None:
            commodities = DEFAULT_COMMODITIES

        results = []
        for commodity in commodities:
            metrics = self.analyze_commodity(df, commodity)
            if metrics:
                results.append(metrics)

        return results
