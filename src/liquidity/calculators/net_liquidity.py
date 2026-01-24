"""Net Liquidity Index calculator using the Hayes formula.

Implements the core liquidity calculation:
    Net Liquidity = WALCL - TGA - RRP

Where:
- WALCL: Fed Total Assets (weekly)
- TGA: Treasury General Account (WTREGEN daily, WDTGAL weekly)
- RRP: Reverse Repo (RRPONTSYD daily, WLRRAL weekly)

This is the foundation of Arthur Hayes' macro liquidity framework.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import pandas as pd

from liquidity.collectors.fred import FredCollector
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)


class Sentiment(str, Enum):
    """Liquidity sentiment classification based on weekly delta."""

    BULLISH = "BULLISH"  # Weekly delta > $50B
    NEUTRAL = "NEUTRAL"  # -$50B <= weekly delta <= $50B
    BEARISH = "BEARISH"  # Weekly delta < -$50B


# Sentiment thresholds in billions USD
SENTIMENT_THRESHOLDS = {
    "bullish": 50.0,  # Weekly delta > $50B
    "bearish": -50.0,  # Weekly delta < -$50B
}

# FRED series for Net Liquidity calculation
# Daily series (from AppScript reference)
DAILY_SERIES = {
    "walcl": "WALCL",  # Fed Total Assets (millions USD, weekly but ffill for daily)
    "tga": "WTREGEN",  # Treasury General Account (millions USD, daily)
    "rrp": "RRPONTSYD",  # Reverse Repo (billions USD, daily)
}

# Weekly series (from OpenBB example)
WEEKLY_SERIES = {
    "walcl": "WALCL",  # Fed Total Assets (millions USD, weekly)
    "tga": "WDTGAL",  # Treasury General Account (billions USD, weekly)
    "rrp": "WLRRAL",  # Reverse Repo (billions USD, weekly)
}

# Unit conversions to billions USD
UNIT_TO_BILLIONS: dict[str, float] = {
    "WALCL": 0.001,  # millions -> billions
    "WTREGEN": 0.001,  # millions -> billions
    "WDTGAL": 1.0,  # already billions
    "RRPONTSYD": 1.0,  # already billions
    "WLRRAL": 1.0,  # already billions
}


@dataclass
class NetLiquidityResult:
    """Result of Net Liquidity calculation with deltas and sentiment.

    All monetary values are in billions USD.

    Attributes:
        timestamp: Timestamp of the calculation.
        net_liquidity: Net Liquidity value (WALCL - TGA - RRP) in billions USD.
        walcl: Fed Total Assets in billions USD.
        tga: Treasury General Account in billions USD.
        rrp: Reverse Repo in billions USD.
        weekly_delta: Change over past 7 days in billions USD.
        monthly_delta: Change over past 30 days in billions USD.
        delta_60d: Change over past 60 days in billions USD.
        delta_90d: Change over past 90 days in billions USD.
        sentiment: Liquidity sentiment classification.
    """

    timestamp: datetime
    net_liquidity: float
    walcl: float
    tga: float
    rrp: float
    weekly_delta: float
    monthly_delta: float
    delta_60d: float
    delta_90d: float
    sentiment: Sentiment


class NetLiquidityCalculator:
    """Calculate Fed Net Liquidity using the Hayes formula.

    Net Liquidity = WALCL - TGA - RRP

    This calculator:
    - Fetches Fed balance sheet components from FRED
    - Calculates Net Liquidity in billions USD
    - Computes weekly, monthly, 60d, and 90d deltas
    - Classifies sentiment based on weekly change

    Example:
        calculator = NetLiquidityCalculator()
        result = await calculator.get_current()
        print(f"Net Liquidity: ${result.net_liquidity:.1f}B")
        print(f"Weekly delta: ${result.weekly_delta:.1f}B")
        print(f"Sentiment: {result.sentiment.value}")

        # Get time series
        df = await calculator.calculate()
    """

    def __init__(
        self,
        settings: Settings | None = None,
        use_daily_series: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the Net Liquidity calculator.

        Args:
            settings: Optional settings override.
            use_daily_series: If True, use daily FRED series (WTREGEN, RRPONTSYD).
                If False (default), use weekly series (WDTGAL, WLRRAL).
            **kwargs: Additional arguments passed to FredCollector.
        """
        self._settings = settings or get_settings()
        self._use_daily = use_daily_series
        self._series = DAILY_SERIES if use_daily_series else WEEKLY_SERIES
        self._collector = FredCollector(settings=self._settings, **kwargs)

    @property
    def series_config(self) -> dict[str, str]:
        """Get the FRED series configuration being used."""
        return self._series.copy()

    async def calculate(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate Net Liquidity time series.

        Net Liquidity = WALCL - TGA - RRP

        All values are converted to billions USD for consistency.

        Args:
            start_date: Start date for calculation. Defaults to 120 days ago
                (enough for 90-day delta calculation).
            end_date: End date for calculation. Defaults to today.

        Returns:
            DataFrame with columns:
                - timestamp: Date of observation
                - net_liquidity: Net Liquidity in billions USD
                - walcl: Fed Total Assets in billions USD
                - tga: TGA in billions USD
                - rrp: RRP in billions USD
        """
        if start_date is None:
            # Need 120 days for 90-day delta calculation
            start_date = datetime.now(UTC) - timedelta(days=120)
        if end_date is None:
            end_date = datetime.now(UTC)

        logger.info(
            "Calculating Net Liquidity from %s to %s using %s series",
            start_date.date(),
            end_date.date(),
            "daily" if self._use_daily else "weekly",
        )

        # Fetch all required series
        symbols = list(self._series.values())
        df = await self._collector.collect(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            logger.warning("No data returned from FRED")
            return pd.DataFrame(
                columns=["timestamp", "net_liquidity", "walcl", "tga", "rrp"]
            )

        # Pivot to wide format
        pivot = df.pivot(index="timestamp", columns="series_id", values="value")

        # Check for required series
        required = set(self._series.values())
        available = set(pivot.columns)
        if not required.issubset(available):
            missing = required - available
            logger.warning("Missing required series for Net Liquidity: %s", missing)
            # Return empty if critical series missing
            if self._series["walcl"] not in available:
                return pd.DataFrame(
                    columns=["timestamp", "net_liquidity", "walcl", "tga", "rrp"]
                )

        # Forward fill weekly WALCL data to match daily data frequency
        if self._series["walcl"] in pivot.columns:
            pivot[self._series["walcl"]] = pivot[self._series["walcl"]].ffill()

        # Forward fill other series that might be sparse
        pivot = pivot.ffill()

        # Drop rows with any NaN (at the start before data is available)
        pivot = pivot.dropna()

        if pivot.empty:
            logger.warning("No data after forward fill")
            return pd.DataFrame(
                columns=["timestamp", "net_liquidity", "walcl", "tga", "rrp"]
            )

        # Convert all to billions USD
        walcl_series = self._series["walcl"]
        tga_series = self._series["tga"]
        rrp_series = self._series["rrp"]

        walcl = pivot[walcl_series] * UNIT_TO_BILLIONS[walcl_series]
        tga = pivot[tga_series] * UNIT_TO_BILLIONS[tga_series]
        rrp = pivot[rrp_series] * UNIT_TO_BILLIONS[rrp_series]

        # Calculate Net Liquidity
        net_liquidity = walcl - tga - rrp

        result = pd.DataFrame(
            {
                "timestamp": pivot.index,
                "net_liquidity": net_liquidity.values,
                "walcl": walcl.values,
                "tga": tga.values,
                "rrp": rrp.values,
            }
        )

        result = result.sort_values("timestamp").reset_index(drop=True)

        logger.info(
            "Calculated Net Liquidity: %d observations, latest=%.1fB USD",
            len(result),
            result["net_liquidity"].iloc[-1] if len(result) > 0 else 0,
        )

        return result

    async def get_current(self) -> NetLiquidityResult:
        """Get current Net Liquidity with all deltas and sentiment.

        Returns:
            NetLiquidityResult with current values and deltas.

        Raises:
            ValueError: If no data available for calculation.
        """
        # Calculate with enough history for 90-day delta
        df = await self.calculate()

        if df.empty:
            raise ValueError("No data available for Net Liquidity calculation")

        # Get the latest row
        latest = df.iloc[-1]
        latest_ts = pd.Timestamp(latest["timestamp"])

        # Calculate deltas
        weekly_delta = self._calculate_delta(df, days=7)
        monthly_delta = self._calculate_delta(df, days=30)
        delta_60d = self._calculate_delta(df, days=60)
        delta_90d = self._calculate_delta(df, days=90)

        # Classify sentiment
        sentiment = self.get_sentiment(weekly_delta)

        result = NetLiquidityResult(
            timestamp=latest_ts.to_pydatetime().replace(tzinfo=UTC),
            net_liquidity=float(latest["net_liquidity"]),
            walcl=float(latest["walcl"]),
            tga=float(latest["tga"]),
            rrp=float(latest["rrp"]),
            weekly_delta=weekly_delta,
            monthly_delta=monthly_delta,
            delta_60d=delta_60d,
            delta_90d=delta_90d,
            sentiment=sentiment,
        )

        logger.info(
            "Current Net Liquidity: %.1fB USD, weekly delta: %.1fB, sentiment: %s",
            result.net_liquidity,
            result.weekly_delta,
            result.sentiment.value,
        )

        return result

    def _calculate_delta(self, df: pd.DataFrame, days: int) -> float:
        """Calculate the change in Net Liquidity over a given period.

        Args:
            df: DataFrame with net_liquidity and timestamp columns.
            days: Number of days to look back.

        Returns:
            Change in net_liquidity in billions USD. Returns 0.0 if not enough data.
        """
        if len(df) < 2:
            return 0.0

        latest_ts = pd.Timestamp(df.iloc[-1]["timestamp"])
        target_ts = latest_ts - pd.Timedelta(days=days)

        # Find the closest row to target date
        df_ts = pd.to_datetime(df["timestamp"])
        mask = df_ts <= target_ts
        if not mask.any():
            # Not enough historical data
            logger.debug("Not enough data for %d-day delta", days)
            return 0.0

        past_idx = df_ts[mask].idxmax()
        past_value = df.loc[past_idx, "net_liquidity"]
        current_value = df.iloc[-1]["net_liquidity"]

        return float(current_value - past_value)

    @staticmethod
    def get_sentiment(weekly_delta: float) -> Sentiment:
        """Classify liquidity sentiment based on weekly change.

        Args:
            weekly_delta: Weekly change in Net Liquidity (billions USD).

        Returns:
            Sentiment classification:
                - BULLISH if weekly_delta > $50B
                - BEARISH if weekly_delta < -$50B
                - NEUTRAL otherwise
        """
        if weekly_delta > SENTIMENT_THRESHOLDS["bullish"]:
            return Sentiment.BULLISH
        elif weekly_delta < SENTIMENT_THRESHOLDS["bearish"]:
            return Sentiment.BEARISH
        else:
            return Sentiment.NEUTRAL

    def __repr__(self) -> str:
        """Return string representation of the calculator."""
        return (
            f"NetLiquidityCalculator(series={'daily' if self._use_daily else 'weekly'})"
        )
