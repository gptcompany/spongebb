"""MOVE Index Z-Score calculator.

Computes a rolling Z-Score for the MOVE Bond Volatility Index,
replicating the logic from Apps Script v3.4.1:
- Rolling window: 20 trading days
- Minimum data threshold: 30% (vs 80% for VIX)
- Signal classification: EXTREME_HIGH, HIGH, NORMAL, LOW, EXTREME_LOW

The MOVE index measures US Treasury bond market volatility.
High MOVE = bond stress = potential liquidity drain.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from liquidity.collectors.yahoo import YahooCollector
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Rolling window for Z-Score calculation (trading days)
ZSCORE_WINDOW = 20
# Minimum data fraction required in rolling window (Apps Script: 30% for MOVE)
MIN_DATA_THRESHOLD = 0.30


class MOVESignal(str, Enum):
    """MOVE Z-Score signal classification."""

    EXTREME_HIGH = "EXTREME_HIGH"  # Z > 2.0: severe bond stress
    HIGH = "HIGH"  # 1.0 < Z <= 2.0: elevated volatility
    NORMAL = "NORMAL"  # -1.0 <= Z <= 1.0: normal conditions
    LOW = "LOW"  # -2.0 <= Z < -1.0: calm markets
    EXTREME_LOW = "EXTREME_LOW"  # Z < -2.0: complacency risk


# Z-Score thresholds for signal classification
SIGNAL_THRESHOLDS = {
    "extreme_high": 2.0,
    "high": 1.0,
    "low": -1.0,
    "extreme_low": -2.0,
}


@dataclass
class MOVEZScoreResult:
    """Result of MOVE Z-Score calculation.

    Attributes:
        timestamp: Timestamp of the calculation (UTC).
        current_move: Latest MOVE index value.
        mean_move: Rolling mean over ZSCORE_WINDOW days.
        std_move: Rolling standard deviation.
        zscore: Z-Score value.
        percentile: Percentile rank (0-100) within the window.
        signal: Signal classification.
    """

    timestamp: datetime
    current_move: float
    mean_move: float
    std_move: float
    zscore: float
    percentile: float
    signal: MOVESignal


def classify_signal(zscore: float) -> MOVESignal:
    """Classify Z-Score into a signal.

    Args:
        zscore: The Z-Score value.

    Returns:
        Signal classification.
    """
    if zscore > SIGNAL_THRESHOLDS["extreme_high"]:
        return MOVESignal.EXTREME_HIGH
    if zscore > SIGNAL_THRESHOLDS["high"]:
        return MOVESignal.HIGH
    if zscore < SIGNAL_THRESHOLDS["extreme_low"]:
        return MOVESignal.EXTREME_LOW
    if zscore < SIGNAL_THRESHOLDS["low"]:
        return MOVESignal.LOW
    return MOVESignal.NORMAL


class MOVEZScoreCalculator:
    """Calculate rolling Z-Score for the MOVE Bond Volatility Index.

    Fetches MOVE data from Yahoo Finance via the YahooCollector,
    computes a rolling Z-Score with a 20-day window, and classifies
    the signal for use in liquidity regime analysis.

    Example:
        calculator = MOVEZScoreCalculator()
        result = await calculator.get_current()
        print(f"MOVE: {result.current_move:.1f}")
        print(f"Z-Score: {result.zscore:.2f} ({result.signal.value})")

        # Get time series
        df = await calculator.calculate()
    """

    def __init__(
        self,
        settings: Settings | None = None,
        window: int = ZSCORE_WINDOW,
        min_threshold: float = MIN_DATA_THRESHOLD,
        **kwargs: Any,
    ) -> None:
        """Initialize MOVE Z-Score calculator.

        Args:
            settings: Optional settings override.
            window: Rolling window size in trading days.
            min_threshold: Minimum data fraction required in window.
            **kwargs: Additional arguments passed to YahooCollector.
        """
        self._settings = settings or get_settings()
        self._collector = YahooCollector(settings=self._settings, **kwargs)
        self._window = window
        self._min_threshold = min_threshold

    async def calculate(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate MOVE Z-Score time series.

        Args:
            start_date: Start date. Defaults to 90 days ago (enough for window warmup).
            end_date: End date. Defaults to today.

        Returns:
            DataFrame with columns:
                - timestamp: Date of observation
                - move: Raw MOVE index value
                - mean: Rolling mean
                - std: Rolling standard deviation
                - zscore: Z-Score
                - percentile: Percentile rank (0-100)
                - signal: Signal classification string
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now(UTC)

        logger.info(
            "Calculating MOVE Z-Score from %s to %s (window=%d)",
            start_date.date(),
            end_date.date(),
            self._window,
        )

        # Fetch MOVE data from Yahoo
        df = await self._collector.collect(
            symbols=["^MOVE"],
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            logger.warning("No MOVE data returned from Yahoo Finance")
            return pd.DataFrame(
                columns=["timestamp", "move", "mean", "std", "zscore", "percentile", "signal"]
            )

        # Extract MOVE values
        move_df = (
            df[["timestamp", "value"]]
            .rename(columns={"value": "move"})
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        # Calculate rolling statistics with minimum data threshold
        min_periods = max(1, int(self._window * self._min_threshold))
        move_df["mean"] = move_df["move"].rolling(
            window=self._window, min_periods=min_periods
        ).mean()
        move_df["std"] = move_df["move"].rolling(
            window=self._window, min_periods=min_periods
        ).std()

        # Calculate Z-Score (avoid division by zero)
        move_df["zscore"] = np.where(
            move_df["std"] > 0,
            (move_df["move"] - move_df["mean"]) / move_df["std"],
            0.0,
        )

        # Calculate percentile rank within the rolling window
        move_df["percentile"] = (
            move_df["move"]
            .rolling(window=self._window, min_periods=min_periods)
            .apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=False)
        )

        # Classify signals
        move_df["signal"] = move_df["zscore"].apply(
            lambda z: classify_signal(z).value
        )

        # Drop warmup rows (NaN from rolling)
        move_df = move_df.dropna(subset=["zscore"]).reset_index(drop=True)

        logger.info(
            "Calculated MOVE Z-Score: %d observations, latest Z=%.2f (%s)",
            len(move_df),
            move_df["zscore"].iloc[-1] if len(move_df) > 0 else 0,
            move_df["signal"].iloc[-1] if len(move_df) > 0 else "N/A",
        )

        return move_df

    async def get_current(self) -> MOVEZScoreResult:
        """Get current MOVE Z-Score with signal classification.

        Returns:
            MOVEZScoreResult with current values.

        Raises:
            ValueError: If no data available.
        """
        df = await self.calculate()

        if df.empty:
            raise ValueError("No MOVE data available for Z-Score calculation")

        latest = df.iloc[-1]

        return MOVEZScoreResult(
            timestamp=datetime.now(UTC),
            current_move=float(latest["move"]),
            mean_move=float(latest["mean"]),
            std_move=float(latest["std"]),
            zscore=float(latest["zscore"]),
            percentile=float(latest["percentile"]),
            signal=MOVESignal(latest["signal"]),
        )
