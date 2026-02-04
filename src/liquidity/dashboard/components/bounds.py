"""Sanity bounds for chart visualization.

Provides historical min/max ranges for charts to help identify
outliers and anomalies.

QA-10: Charts include sanity bounds (historical min/max ranges).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import plotly.graph_objects as go


class BoundStatus(Enum):
    """Status of a value relative to historical bounds."""

    NORMAL = "normal"
    BELOW_NORMAL = "below_normal"
    ABOVE_NORMAL = "above_normal"
    UNKNOWN = "unknown"


@dataclass
class BoundInfo:
    """Information about bounds for a metric.

    Attributes:
        low: Lower bound value.
        high: Upper bound value.
        unit: Unit of measurement (e.g., "$", "%").
        description: Human-readable description of the range.
    """

    low: float
    high: float
    unit: str = ""
    description: str = ""


class SanityBounds:
    """Add historical min/max bounds to charts.

    Historical bounds are based on multi-year data analysis
    to establish "normal" operating ranges for each metric.

    Example:
        bounds = SanityBounds()

        # Add bounds to a chart
        fig = bounds.add_bounds(fig, 'net_liquidity')

        # Check if value is outside bounds
        is_outlier = bounds.is_outside_bounds('vix', 85)

        # Get detailed status
        status = bounds.get_bound_status('dxy', 120)  # ABOVE_NORMAL
    """

    # Historical bounds based on multi-year data analysis
    # Format: metric_name: (low, high)
    BOUNDS: dict[str, BoundInfo] = {
        # Liquidity metrics (in USD)
        "net_liquidity": BoundInfo(
            low=4.5e12,
            high=7.0e12,
            unit="$",
            description="Fed Net Liquidity ($4.5T - $7T)",
        ),
        "global_liquidity": BoundInfo(
            low=25e12,
            high=35e12,
            unit="$",
            description="Global CB Liquidity ($25T - $35T)",
        ),
        "walcl": BoundInfo(
            low=6.5e12,
            high=9.0e12,
            unit="$",
            description="Fed Total Assets ($6.5T - $9T)",
        ),
        "tga": BoundInfo(
            low=100e9,
            high=1.5e12,
            unit="$",
            description="Treasury General Account ($100B - $1.5T)",
        ),
        "rrp": BoundInfo(
            low=0,
            high=2.5e12,
            unit="$",
            description="Reverse Repo ($0 - $2.5T)",
        ),
        # Market indicators
        "dxy": BoundInfo(
            low=90,
            high=115,
            description="Dollar Index (90 - 115)",
        ),
        "vix": BoundInfo(
            low=10,
            high=80,
            description="VIX (10 - 80)",
        ),
        "move": BoundInfo(
            low=50,
            high=200,
            description="MOVE Index (50 - 200)",
        ),
        # Rates
        "sofr": BoundInfo(
            low=0,
            high=10,
            unit="%",
            description="SOFR Rate (0% - 10%)",
        ),
        "sofr_ois": BoundInfo(
            low=-50,
            high=50,
            unit="bps",
            description="SOFR-OIS Spread (-50bps - +50bps)",
        ),
        "fed_funds": BoundInfo(
            low=0,
            high=10,
            unit="%",
            description="Fed Funds Rate (0% - 10%)",
        ),
        # Commodities
        "gold": BoundInfo(
            low=1500,
            high=2500,
            unit="$",
            description="Gold ($/oz: $1500 - $2500)",
        ),
        "copper": BoundInfo(
            low=3,
            high=5,
            unit="$",
            description="Copper ($/lb: $3 - $5)",
        ),
        "wti": BoundInfo(
            low=40,
            high=120,
            unit="$",
            description="WTI Crude ($/bbl: $40 - $120)",
        ),
        "brent": BoundInfo(
            low=45,
            high=125,
            unit="$",
            description="Brent Crude ($/bbl: $45 - $125)",
        ),
        # FX
        "eurusd": BoundInfo(
            low=0.95,
            high=1.25,
            description="EUR/USD (0.95 - 1.25)",
        ),
        "usdjpy": BoundInfo(
            low=100,
            high=160,
            description="USD/JPY (100 - 160)",
        ),
        "usdcny": BoundInfo(
            low=6.3,
            high=7.5,
            description="USD/CNY (6.3 - 7.5)",
        ),
    }

    @classmethod
    def add_bounds(
        cls,
        fig: go.Figure,
        metric: str,
        show_annotation: bool = True,
        opacity: float = 0.1,
    ) -> go.Figure:
        """Add horizontal bands for historical bounds to a chart.

        Args:
            fig: Plotly Figure to modify.
            metric: Metric name (must be in BOUNDS).
            show_annotation: Whether to add annotation label.
            opacity: Fill opacity for the shaded region.

        Returns:
            Modified Plotly Figure with bounds added.
        """
        if metric not in cls.BOUNDS:
            return fig

        bound_info = cls.BOUNDS[metric]
        low, high = bound_info.low, bound_info.high

        # Add shaded region for "normal" range
        fig.add_hrect(
            y0=low,
            y1=high,
            fillcolor=f"rgba(0, 255, 136, {opacity})",
            line_width=0,
            annotation_text="Historical Range" if show_annotation else None,
            annotation_position="top left" if show_annotation else None,
            annotation_font={"color": "rgba(255,255,255,0.5)", "size": 10},
            layer="below",
        )

        # Add dashed lines at bounds
        fig.add_hline(
            y=low,
            line_dash="dot",
            line_color="rgba(255, 255, 255, 0.2)",
            line_width=1,
        )
        fig.add_hline(
            y=high,
            line_dash="dot",
            line_color="rgba(255, 255, 255, 0.2)",
            line_width=1,
        )

        return fig

    @classmethod
    def add_bounds_with_alert_zones(
        cls,
        fig: go.Figure,
        metric: str,
        opacity: float = 0.15,
    ) -> go.Figure:
        """Add bounds with color-coded alert zones.

        Shows green for normal range, yellow for warning zone,
        red for extreme zone.

        Args:
            fig: Plotly Figure to modify.
            metric: Metric name.
            opacity: Fill opacity for regions.

        Returns:
            Modified Plotly Figure with alert zones.
        """
        if metric not in cls.BOUNDS:
            return fig

        bound_info = cls.BOUNDS[metric]
        low, high = bound_info.low, bound_info.high

        # Calculate warning and extreme thresholds
        range_size = high - low
        warning_margin = range_size * 0.1  # 10% beyond normal
        extreme_margin = range_size * 0.2  # 20% beyond normal

        # Extreme low zone (red)
        fig.add_hrect(
            y0=low - extreme_margin,
            y1=low - warning_margin,
            fillcolor=f"rgba(255, 68, 68, {opacity})",
            line_width=0,
            layer="below",
        )

        # Warning low zone (yellow)
        fig.add_hrect(
            y0=low - warning_margin,
            y1=low,
            fillcolor=f"rgba(255, 170, 0, {opacity})",
            line_width=0,
            layer="below",
        )

        # Normal zone (green)
        fig.add_hrect(
            y0=low,
            y1=high,
            fillcolor=f"rgba(0, 255, 136, {opacity})",
            line_width=0,
            layer="below",
        )

        # Warning high zone (yellow)
        fig.add_hrect(
            y0=high,
            y1=high + warning_margin,
            fillcolor=f"rgba(255, 170, 0, {opacity})",
            line_width=0,
            layer="below",
        )

        # Extreme high zone (red)
        fig.add_hrect(
            y0=high + warning_margin,
            y1=high + extreme_margin,
            fillcolor=f"rgba(255, 68, 68, {opacity})",
            line_width=0,
            layer="below",
        )

        return fig

    @classmethod
    def is_outside_bounds(cls, metric: str, value: float) -> bool:
        """Check if a value is outside historical bounds.

        Args:
            metric: Metric name.
            value: Current value to check.

        Returns:
            True if value is outside normal range.
        """
        if metric not in cls.BOUNDS:
            return False

        bound_info = cls.BOUNDS[metric]
        return value < bound_info.low or value > bound_info.high

    @classmethod
    def get_bound_status(cls, metric: str, value: float) -> BoundStatus:
        """Get the status of a value relative to bounds.

        Args:
            metric: Metric name.
            value: Current value to check.

        Returns:
            BoundStatus enum indicating position relative to bounds.
        """
        if metric not in cls.BOUNDS:
            return BoundStatus.UNKNOWN

        bound_info = cls.BOUNDS[metric]

        if value < bound_info.low:
            return BoundStatus.BELOW_NORMAL
        elif value > bound_info.high:
            return BoundStatus.ABOVE_NORMAL
        return BoundStatus.NORMAL

    @classmethod
    def get_bounds(cls, metric: str) -> tuple[float, float] | None:
        """Get the bounds tuple for a metric.

        Args:
            metric: Metric name.

        Returns:
            Tuple of (low, high) or None if metric not found.
        """
        if metric not in cls.BOUNDS:
            return None
        bound_info = cls.BOUNDS[metric]
        return (bound_info.low, bound_info.high)

    @classmethod
    def get_bound_info(cls, metric: str) -> BoundInfo | None:
        """Get full bound information for a metric.

        Args:
            metric: Metric name.

        Returns:
            BoundInfo object or None if metric not found.
        """
        return cls.BOUNDS.get(metric)

    @classmethod
    def format_bound_status(
        cls,
        metric: str,
        value: float,
        include_delta: bool = True,
    ) -> dict[str, Any]:
        """Get formatted bound status with details for UI display.

        Args:
            metric: Metric name.
            value: Current value.
            include_delta: Whether to include distance from bounds.

        Returns:
            Dictionary with status information for UI rendering.
        """
        status = cls.get_bound_status(metric, value)
        bound_info = cls.BOUNDS.get(metric)

        result: dict[str, Any] = {
            "status": status.value,
            "is_normal": status == BoundStatus.NORMAL,
            "metric": metric,
            "value": value,
        }

        if bound_info:
            result["low"] = bound_info.low
            result["high"] = bound_info.high
            result["description"] = bound_info.description

            if include_delta:
                if status == BoundStatus.BELOW_NORMAL:
                    result["delta"] = value - bound_info.low
                    result["delta_pct"] = (
                        (value - bound_info.low) / bound_info.low * 100
                    )
                elif status == BoundStatus.ABOVE_NORMAL:
                    result["delta"] = value - bound_info.high
                    result["delta_pct"] = (
                        (value - bound_info.high) / bound_info.high * 100
                    )
                else:
                    result["delta"] = 0
                    result["delta_pct"] = 0

        return result

    @classmethod
    def get_all_metrics(cls) -> list[str]:
        """Get list of all metrics with defined bounds.

        Returns:
            List of metric names.
        """
        return list(cls.BOUNDS.keys())
