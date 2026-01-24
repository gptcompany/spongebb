"""Stealth QE Score calculator based on Arthur Hayes' framework.

Detects hidden liquidity injections by monitoring:
1. RRP (Reverse Repo) velocity - declining RRP releases liquidity
2. TGA (Treasury General Account) spending - Treasury drawing down adds liquidity
3. Fed balance sheet changes - direct asset purchases

The Stealth QE Score combines these three signals to identify when central banks
are injecting liquidity through less obvious channels (not just direct QE).

Formula:
    Score = (RRP_comp * 0.40) + (TGA_comp * 0.40) + (FED_comp * 0.20)

Where each component is 0-100 based on weekly changes relative to thresholds.
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


class StealthQEStatus(str, Enum):
    """Stealth QE activity classification based on score."""

    VERY_ACTIVE = "VERY_ACTIVE"  # 70-100: Major liquidity injection in progress
    ACTIVE = "ACTIVE"  # 50-70: Stealth QE detected. Bullish
    MODERATE = "MODERATE"  # 30-50: Some injection signals. Neutral
    LOW = "LOW"  # 10-30: Minimal activity
    MINIMAL = "MINIMAL"  # 0-10: No hidden injection


# Configuration from Apps Script v3.4.1
SCORE_CONFIG = {
    "RRP_VELOCITY_MAX": 20,  # % weekly change threshold
    "TGA_SPENDING_MAX": 200,  # $B weekly spending threshold
    "FED_CHANGE_MAX": 100,  # $B weekly change threshold
    "WEIGHT_RRP": 0.40,
    "WEIGHT_TGA": 0.40,
    "WEIGHT_FED": 0.20,
    "MAX_DAILY_CHANGE": 25,  # Smoothing cap for daily score
    "WEEKLY_CALC_DAY": 2,  # Wednesday (0=Monday, 2=Wednesday)
}

# FRED series for Stealth QE calculation
# Daily series (higher frequency for daily score)
DAILY_SERIES = {
    "walcl": "WALCL",  # Fed Total Assets (millions USD, weekly but ffill for daily)
    "tga": "WTREGEN",  # Treasury General Account (millions USD, daily)
    "rrp": "RRPONTSYD",  # Reverse Repo (billions USD, daily)
}

# Unit conversions to billions USD
UNIT_TO_BILLIONS: dict[str, float] = {
    "WALCL": 0.001,  # millions -> billions
    "WTREGEN": 0.001,  # millions -> billions
    "RRPONTSYD": 1.0,  # already billions
}


@dataclass
class StealthQEResult:
    """Result of Stealth QE Score calculation.

    Attributes:
        timestamp: Timestamp of the calculation.
        score_daily: Daily smoothed score (0-100).
        score_weekly: Weekly score (0-100), only calculated on Wednesdays.
        rrp_level: Current RRP level in billions USD.
        rrp_velocity: RRP percentage change over past week (negative = bullish).
        tga_level: Current TGA level in billions USD.
        tga_spending: TGA spending over past week in billions USD (positive = bullish).
        fed_total: Fed total assets in billions USD.
        fed_change: Fed balance sheet change over past week in billions USD.
        components: String representation of component contributions.
        status: Activity classification (VERY_ACTIVE, ACTIVE, etc.).
    """

    timestamp: datetime
    score_daily: float  # 0-100
    score_weekly: float | None  # 0-100, None if not Wednesday
    rrp_level: float  # Current RRP in billions
    rrp_velocity: float | None  # % weekly change
    tga_level: float  # Current TGA in billions
    tga_spending: float | None  # $B weekly spending
    fed_total: float  # Fed total assets in billions
    fed_change: float | None  # $B weekly change
    components: str  # "RRP:40% TGA:30% FED:10%"
    status: str  # VERY_ACTIVE, ACTIVE, etc.


class StealthQECalculator:
    """Calculate Stealth QE Score to detect hidden liquidity injections.

    The Stealth QE Score combines three signals:
    1. RRP Velocity (40%): Declining RRP releases liquidity to markets
    2. TGA Spending (40%): Treasury spending adds liquidity
    3. Fed Changes (20%): Direct balance sheet expansion

    Score interpretation:
        70-100: VERY_ACTIVE - Major liquidity injection in progress
        50-70:  ACTIVE - Stealth QE detected. Bullish
        30-50:  MODERATE - Some injection signals. Neutral
        10-30:  LOW - Minimal activity
        0-10:   MINIMAL - No hidden injection

    Example:
        calculator = StealthQECalculator()
        result = await calculator.get_current()
        print(f"Stealth QE Score: {result.score_daily:.1f}")
        print(f"Status: {result.status}")
        print(f"Components: {result.components}")

        # Get time series
        df = await calculator.calculate_daily()
    """

    SCORE_CONFIG = SCORE_CONFIG

    def __init__(
        self,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Stealth QE Score calculator.

        Args:
            settings: Optional settings override.
            **kwargs: Additional arguments passed to FredCollector.
        """
        self._settings = settings or get_settings()
        self._collector = FredCollector(settings=self._settings, **kwargs)
        self._prev_daily_score: float | None = None

    async def calculate_daily(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate daily Stealth QE score time series.

        Daily scores use smoothing (MAX_DAILY_CHANGE cap) to prevent
        wild swings from one day to the next.

        Args:
            start_date: Start date for calculation. Defaults to 30 days ago.
            end_date: End date for calculation. Defaults to today.

        Returns:
            DataFrame with columns:
                - timestamp: Date of observation
                - score_daily: Daily smoothed score (0-100)
                - rrp_level: RRP in billions USD
                - rrp_velocity: % weekly change (None if < 7 days data)
                - tga_level: TGA in billions USD
                - tga_spending: $B weekly spending (None if < 7 days data)
                - fed_total: Fed assets in billions USD
                - fed_change: $B weekly change (None if < 7 days data)
                - comp_rrp: RRP component (0-100)
                - comp_tga: TGA component (0-100)
                - comp_fed: Fed component (0-100)
                - status: Activity classification
        """
        # Need extra history for 7-day lookback calculations
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(UTC)

        # Fetch extra history for calculations
        fetch_start = start_date - timedelta(days=14)

        logger.info(
            "Calculating daily Stealth QE scores from %s to %s",
            start_date.date(),
            end_date.date(),
        )

        # Fetch required series
        symbols = list(DAILY_SERIES.values())
        df = await self._collector.collect(
            symbols=symbols,
            start_date=fetch_start,
            end_date=end_date,
        )

        if df.empty:
            logger.warning("No data returned from FRED for Stealth QE calculation")
            return self._empty_daily_dataframe()

        # Pivot to wide format
        pivot = df.pivot(index="timestamp", columns="series_id", values="value")

        # Check for required series
        required = set(DAILY_SERIES.values())
        available = set(pivot.columns)
        if not required.issubset(available):
            missing = required - available
            logger.warning("Missing required series for Stealth QE: %s", missing)
            return self._empty_daily_dataframe()

        # Forward fill to align daily data with weekly Fed data
        pivot = pivot.ffill().dropna()

        if len(pivot) < 8:
            logger.warning(
                "Not enough data for Stealth QE calculation (need >= 8 days)"
            )
            return self._empty_daily_dataframe()

        # Convert to billions USD
        walcl_series = DAILY_SERIES["walcl"]
        tga_series = DAILY_SERIES["tga"]
        rrp_series = DAILY_SERIES["rrp"]

        fed_total = pivot[walcl_series] * UNIT_TO_BILLIONS[walcl_series]
        tga_level = pivot[tga_series] * UNIT_TO_BILLIONS[tga_series]
        rrp_level = pivot[rrp_series] * UNIT_TO_BILLIONS[rrp_series]

        # Calculate daily scores
        results = []
        prev_daily_score = 0.0

        for idx in range(len(pivot)):
            timestamp = pivot.index[idx]

            # Skip if before requested start date
            if pd.Timestamp(timestamp) < pd.Timestamp(start_date):
                # Still calculate for smoothing purposes
                if idx >= 7:
                    rrp_velocity, tga_spending, fed_change = (
                        self._calculate_weekly_changes(
                            rrp_level, tga_level, fed_total, idx
                        )
                    )
                    comp_rrp, comp_tga, comp_fed = self._calculate_components(
                        rrp_velocity, tga_spending, fed_change
                    )
                    raw_score = (
                        comp_rrp * SCORE_CONFIG["WEIGHT_RRP"]
                        + comp_tga * SCORE_CONFIG["WEIGHT_TGA"]
                        + comp_fed * SCORE_CONFIG["WEIGHT_FED"]
                    )
                    prev_daily_score = self._apply_smoothing(
                        raw_score, prev_daily_score, idx
                    )
                continue

            # Get current levels
            current_rrp = rrp_level.iloc[idx]
            current_tga = tga_level.iloc[idx]
            current_fed = fed_total.iloc[idx]

            # Calculate weekly changes (need 7 days of history)
            rrp_velocity = None
            tga_spending = None
            fed_change = None
            comp_rrp = 0.0
            comp_tga = 0.0
            comp_fed = 0.0

            if idx >= 7:
                rrp_velocity, tga_spending, fed_change = self._calculate_weekly_changes(
                    rrp_level, tga_level, fed_total, idx
                )
                comp_rrp, comp_tga, comp_fed = self._calculate_components(
                    rrp_velocity, tga_spending, fed_change
                )

            # Calculate raw score
            raw_score = (
                comp_rrp * SCORE_CONFIG["WEIGHT_RRP"]
                + comp_tga * SCORE_CONFIG["WEIGHT_TGA"]
                + comp_fed * SCORE_CONFIG["WEIGHT_FED"]
            )

            # Apply smoothing
            score_daily = self._apply_smoothing(raw_score, prev_daily_score, idx)
            prev_daily_score = score_daily

            # Clamp to 0-100
            score_daily = max(0.0, min(100.0, score_daily))

            # Get status
            status = self.get_status(score_daily)

            results.append(
                {
                    "timestamp": timestamp,
                    "score_daily": score_daily,
                    "rrp_level": current_rrp,
                    "rrp_velocity": rrp_velocity,
                    "tga_level": current_tga,
                    "tga_spending": tga_spending,
                    "fed_total": current_fed,
                    "fed_change": fed_change,
                    "comp_rrp": comp_rrp,
                    "comp_tga": comp_tga,
                    "comp_fed": comp_fed,
                    "status": status.value,
                }
            )

        result_df = pd.DataFrame(results)

        if not result_df.empty:
            logger.info(
                "Calculated %d daily Stealth QE scores, latest=%.1f (%s)",
                len(result_df),
                result_df["score_daily"].iloc[-1],
                result_df["status"].iloc[-1],
            )

        return result_df

    async def calculate_weekly(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate weekly Stealth QE score (Wednesday-to-Wednesday).

        Weekly scores are calculated without smoothing, using the actual
        Wednesday-to-Wednesday changes. This matches when the Fed updates
        its balance sheet data.

        Args:
            start_date: Start date for calculation. Defaults to 60 days ago.
            end_date: End date for calculation. Defaults to today.

        Returns:
            DataFrame with weekly scores (only Wednesday observations).
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=60)
        if end_date is None:
            end_date = datetime.now(UTC)

        # Fetch extra history for calculations
        fetch_start = start_date - timedelta(days=14)

        logger.info(
            "Calculating weekly Stealth QE scores from %s to %s",
            start_date.date(),
            end_date.date(),
        )

        # Fetch required series
        symbols = list(DAILY_SERIES.values())
        df = await self._collector.collect(
            symbols=symbols,
            start_date=fetch_start,
            end_date=end_date,
        )

        if df.empty:
            logger.warning(
                "No data returned from FRED for weekly Stealth QE calculation"
            )
            return self._empty_weekly_dataframe()

        # Pivot to wide format
        pivot = df.pivot(index="timestamp", columns="series_id", values="value")

        # Check for required series
        required = set(DAILY_SERIES.values())
        available = set(pivot.columns)
        if not required.issubset(available):
            missing = required - available
            logger.warning("Missing required series for Stealth QE: %s", missing)
            return self._empty_weekly_dataframe()

        # Forward fill and drop NaN
        pivot = pivot.ffill().dropna()

        if len(pivot) < 8:
            logger.warning("Not enough data for weekly Stealth QE calculation")
            return self._empty_weekly_dataframe()

        # Convert to billions USD
        walcl_series = DAILY_SERIES["walcl"]
        tga_series = DAILY_SERIES["tga"]
        rrp_series = DAILY_SERIES["rrp"]

        fed_total = pivot[walcl_series] * UNIT_TO_BILLIONS[walcl_series]
        tga_level = pivot[tga_series] * UNIT_TO_BILLIONS[tga_series]
        rrp_level = pivot[rrp_series] * UNIT_TO_BILLIONS[rrp_series]

        # Find Wednesday observations
        results = []
        prev_wed_idx = None

        for idx in range(len(pivot)):
            timestamp = pivot.index[idx]
            ts = pd.Timestamp(timestamp)

            # Check if Wednesday (weekday() returns 2 for Wednesday)
            if ts.weekday() != SCORE_CONFIG["WEEKLY_CALC_DAY"]:
                continue

            # Skip if before requested start date
            if ts < pd.Timestamp(start_date):
                prev_wed_idx = idx
                continue

            # Get current levels
            current_rrp = rrp_level.iloc[idx]
            current_tga = tga_level.iloc[idx]
            current_fed = fed_total.iloc[idx]

            # Need previous Wednesday for calculation
            if prev_wed_idx is None:
                prev_wed_idx = idx
                continue

            # Calculate Wednesday-to-Wednesday changes
            prev_rrp = rrp_level.iloc[prev_wed_idx]
            prev_tga = tga_level.iloc[prev_wed_idx]
            prev_fed = fed_total.iloc[prev_wed_idx]

            # RRP velocity (% change)
            if prev_rrp > 0.5:
                rrp_velocity = ((current_rrp - prev_rrp) / prev_rrp) * 100
            elif current_rrp < 0.5:
                rrp_velocity = 0.0
            else:
                rrp_velocity = None

            # TGA spending (positive when TGA decreases)
            tga_spending = -(current_tga - prev_tga)

            # Fed change
            fed_change = current_fed - prev_fed

            # Calculate components
            comp_rrp, comp_tga, comp_fed = self._calculate_components(
                rrp_velocity, tga_spending, fed_change
            )

            # Calculate weekly score (no smoothing)
            score_weekly = (
                comp_rrp * SCORE_CONFIG["WEIGHT_RRP"]
                + comp_tga * SCORE_CONFIG["WEIGHT_TGA"]
                + comp_fed * SCORE_CONFIG["WEIGHT_FED"]
            )
            score_weekly = max(0.0, min(100.0, score_weekly))

            # Get status
            status = self.get_status(score_weekly)

            # Format components string
            components = f"RRP:{comp_rrp:.0f}% TGA:{comp_tga:.0f}% FED:{comp_fed:.0f}%"

            results.append(
                {
                    "timestamp": timestamp,
                    "score_weekly": score_weekly,
                    "rrp_level": current_rrp,
                    "rrp_velocity": rrp_velocity,
                    "tga_level": current_tga,
                    "tga_spending": tga_spending,
                    "fed_total": current_fed,
                    "fed_change": fed_change,
                    "components": components,
                    "status": status.value,
                }
            )

            prev_wed_idx = idx

        result_df = pd.DataFrame(results)

        if not result_df.empty:
            logger.info(
                "Calculated %d weekly Stealth QE scores, latest=%.1f (%s)",
                len(result_df),
                result_df["score_weekly"].iloc[-1],
                result_df["status"].iloc[-1],
            )

        return result_df

    async def get_current(self) -> StealthQEResult:
        """Get current Stealth QE metrics.

        Returns:
            StealthQEResult with current values.

        Raises:
            ValueError: If no data available for calculation.
        """
        # Get daily scores to get the latest
        df_daily = await self.calculate_daily()

        if df_daily.empty:
            raise ValueError("No data available for Stealth QE calculation")

        # Get the latest row
        latest = df_daily.iloc[-1]
        latest_ts = pd.Timestamp(latest["timestamp"])

        # Check if it's Wednesday for weekly score
        score_weekly = None
        if latest_ts.weekday() == SCORE_CONFIG["WEEKLY_CALC_DAY"]:
            df_weekly = await self.calculate_weekly()
            if not df_weekly.empty:
                # Find matching Wednesday
                weekly_ts = pd.to_datetime(df_weekly["timestamp"])
                match = df_weekly[weekly_ts == latest_ts]
                if not match.empty:
                    score_weekly = float(match.iloc[-1]["score_weekly"])

        # Format components string
        components = (
            f"RRP:{latest['comp_rrp']:.0f}% "
            f"TGA:{latest['comp_tga']:.0f}% "
            f"FED:{latest['comp_fed']:.0f}%"
        )

        # Convert timestamp to UTC datetime
        ts_pydatetime = (
            datetime.now(UTC)
            if pd.isna(latest_ts)
            else latest_ts.to_pydatetime().replace(tzinfo=UTC)
        )

        result = StealthQEResult(
            timestamp=ts_pydatetime,
            score_daily=float(latest["score_daily"]),
            score_weekly=score_weekly,
            rrp_level=float(latest["rrp_level"]),
            rrp_velocity=latest["rrp_velocity"],
            tga_level=float(latest["tga_level"]),
            tga_spending=latest["tga_spending"],
            fed_total=float(latest["fed_total"]),
            fed_change=latest["fed_change"],
            components=components,
            status=latest["status"],
        )

        logger.info(
            "Current Stealth QE: daily=%.1f, weekly=%s, status=%s",
            result.score_daily,
            f"{result.score_weekly:.1f}" if result.score_weekly else "N/A",
            result.status,
        )

        return result

    def _calculate_weekly_changes(
        self,
        rrp_level: pd.Series,
        tga_level: pd.Series,
        fed_total: pd.Series,
        idx: int,
    ) -> tuple[float | None, float | None, float]:
        """Calculate the weekly changes for each component.

        Args:
            rrp_level: RRP level series in billions USD.
            tga_level: TGA level series in billions USD.
            fed_total: Fed total assets series in billions USD.
            idx: Current index in the series.

        Returns:
            Tuple of (rrp_velocity, tga_spending, fed_change).
        """
        # 7-day lookback
        lookback_idx = idx - 7

        # RRP velocity (% change)
        current_rrp = rrp_level.iloc[idx]
        prev_rrp = rrp_level.iloc[lookback_idx]

        if prev_rrp > 0.5:
            rrp_velocity = ((current_rrp - prev_rrp) / prev_rrp) * 100
        elif current_rrp < 0.5:
            rrp_velocity = 0.0
        else:
            rrp_velocity = None

        # TGA spending (positive when TGA decreases = spending)
        current_tga = tga_level.iloc[idx]
        prev_tga = tga_level.iloc[lookback_idx]
        tga_spending = -(current_tga - prev_tga)

        # Fed change
        current_fed = fed_total.iloc[idx]
        prev_fed = fed_total.iloc[lookback_idx]
        fed_change = current_fed - prev_fed

        return rrp_velocity, tga_spending, fed_change

    def _calculate_components(
        self,
        rrp_velocity: float | None,
        tga_spending: float | None,
        fed_change: float | None,
    ) -> tuple[float, float, float]:
        """Calculate the three score components (0-100 each).

        Args:
            rrp_velocity: RRP % weekly change (negative = bullish).
            tga_spending: TGA spending in $B (positive = bullish).
            fed_change: Fed change in $B (positive = bullish).

        Returns:
            Tuple of (comp_rrp, comp_tga, comp_fed) each 0-100.
        """
        # RRP component: Score when RRP is declining (negative velocity)
        comp_rrp = 0.0
        if rrp_velocity is not None and rrp_velocity < 0:
            comp_rrp = min(
                100.0,
                abs(rrp_velocity) / SCORE_CONFIG["RRP_VELOCITY_MAX"] * 100,
            )

        # TGA component: Score when TGA is declining (positive spending)
        comp_tga = 0.0
        if tga_spending is not None and tga_spending > 0:
            comp_tga = min(
                100.0,
                tga_spending / SCORE_CONFIG["TGA_SPENDING_MAX"] * 100,
            )

        # Fed component: Score when Fed is expanding (positive change)
        comp_fed = 0.0
        if fed_change is not None and fed_change > 0:
            comp_fed = min(
                100.0,
                fed_change / SCORE_CONFIG["FED_CHANGE_MAX"] * 100,
            )

        return comp_rrp, comp_tga, comp_fed

    def _apply_smoothing(
        self,
        raw_score: float,
        prev_score: float,
        idx: int,
    ) -> float:
        """Apply smoothing to prevent large daily swings.

        Args:
            raw_score: The raw calculated score.
            prev_score: Previous day's smoothed score.
            idx: Current index (smoothing only applied after first week).

        Returns:
            Smoothed score.
        """
        # Only apply smoothing after first week and if we have a previous score
        if idx > 7 and prev_score > 0:
            max_change = SCORE_CONFIG["MAX_DAILY_CHANGE"]
            return max(prev_score - max_change, min(prev_score + max_change, raw_score))
        return raw_score

    @staticmethod
    def get_status(score: float) -> StealthQEStatus:
        """Get status label for a score.

        Args:
            score: Stealth QE score (0-100).

        Returns:
            StealthQEStatus classification:
                - VERY_ACTIVE: 70-100
                - ACTIVE: 50-70
                - MODERATE: 30-50
                - LOW: 10-30
                - MINIMAL: 0-10
        """
        if score >= 70:
            return StealthQEStatus.VERY_ACTIVE
        if score >= 50:
            return StealthQEStatus.ACTIVE
        if score >= 30:
            return StealthQEStatus.MODERATE
        if score >= 10:
            return StealthQEStatus.LOW
        return StealthQEStatus.MINIMAL

    def _empty_daily_dataframe(self) -> pd.DataFrame:
        """Return an empty DataFrame with daily score columns."""
        return pd.DataFrame(
            columns=[
                "timestamp",
                "score_daily",
                "rrp_level",
                "rrp_velocity",
                "tga_level",
                "tga_spending",
                "fed_total",
                "fed_change",
                "comp_rrp",
                "comp_tga",
                "comp_fed",
                "status",
            ]
        )

    def _empty_weekly_dataframe(self) -> pd.DataFrame:
        """Return an empty DataFrame with weekly score columns."""
        return pd.DataFrame(
            columns=[
                "timestamp",
                "score_weekly",
                "rrp_level",
                "rrp_velocity",
                "tga_level",
                "tga_spending",
                "fed_total",
                "fed_change",
                "components",
                "status",
            ]
        )

    def __repr__(self) -> str:
        """Return string representation of the calculator."""
        return "StealthQECalculator()"
