"""VIX Term Structure calculator.

Computes the VIX/VIX3M ratio to classify volatility term structure,
replicating logic from Apps Script v3.4.1:
- Ratio = VIX / VIX3M
- < 0.90: Contango (bullish — near-term vol lower than 3-month)
- 0.90–1.05: Flat (neutral)
- > 1.05: Backwardation (bearish — near-term vol spikes above 3-month)

Data sources:
- VIX: FRED series VIXCLS (daily, percent)
- VIX3M: FRED series VXVCLS (daily, percent)
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

# Term structure thresholds (from Apps Script v3.4.1)
CONTANGO_THRESHOLD = 0.90  # Ratio < 0.90 = strong contango (bullish)
BACKWARDATION_THRESHOLD = 1.05  # Ratio > 1.05 = backwardation (bearish)


class TermStructure(str, Enum):
    """VIX term structure classification."""

    CONTANGO = "CONTANGO"  # Ratio < 0.90: bullish (normal market)
    FLAT = "FLAT"  # 0.90 <= ratio <= 1.05: neutral
    BACKWARDATION = "BACKWARDATION"  # Ratio > 1.05: bearish (stress)


# FRED series for VIX data
VIX_SERIES = {
    "vix": "VIXCLS",  # VIX (percent, daily)
    "vix3m": "VXVCLS",  # VIX3M (percent, daily)
}


@dataclass
class VIXTermStructureResult:
    """Result of VIX term structure analysis.

    Attributes:
        timestamp: Timestamp of the calculation (UTC).
        vix: Current VIX value.
        vix3m: Current VIX3M value.
        ratio: VIX/VIX3M ratio.
        structure: Term structure classification.
        spread: VIX - VIX3M absolute spread.
    """

    timestamp: datetime
    vix: float
    vix3m: float
    ratio: float
    structure: TermStructure
    spread: float


def classify_structure(ratio: float) -> TermStructure:
    """Classify VIX/VIX3M ratio into term structure.

    Args:
        ratio: VIX / VIX3M ratio.

    Returns:
        Term structure classification.
    """
    if ratio < CONTANGO_THRESHOLD:
        return TermStructure.CONTANGO
    if ratio > BACKWARDATION_THRESHOLD:
        return TermStructure.BACKWARDATION
    return TermStructure.FLAT


class VIXTermStructureCalculator:
    """Calculate VIX/VIX3M term structure and classify market regime.

    Fetches VIX and VIX3M from FRED, computes the ratio, and classifies
    the volatility term structure for use in liquidity regime analysis.

    Example:
        calculator = VIXTermStructureCalculator()
        result = await calculator.get_current()
        print(f"VIX/VIX3M: {result.ratio:.3f} ({result.structure.value})")

        # Get time series
        df = await calculator.calculate()
    """

    def __init__(
        self,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize VIX Term Structure calculator.

        Args:
            settings: Optional settings override.
            **kwargs: Additional arguments passed to FredCollector.
        """
        self._settings = settings or get_settings()
        self._collector = FredCollector(settings=self._settings, **kwargs)

    async def calculate(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Calculate VIX term structure time series.

        Args:
            start_date: Start date. Defaults to 90 days ago.
            end_date: End date. Defaults to today.

        Returns:
            DataFrame with columns:
                - timestamp: Date of observation
                - vix: VIX value
                - vix3m: VIX3M value
                - ratio: VIX/VIX3M
                - spread: VIX - VIX3M
                - structure: Term structure classification string
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now(UTC)

        logger.info(
            "Calculating VIX term structure from %s to %s",
            start_date.date(),
            end_date.date(),
        )

        # Fetch VIX and VIX3M from FRED
        symbols = list(VIX_SERIES.values())
        df = await self._collector.collect(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            logger.warning("No VIX data returned from FRED")
            return pd.DataFrame(
                columns=["timestamp", "vix", "vix3m", "ratio", "spread", "structure"]
            )

        # Pivot to wide format
        pivot = df.pivot(index="timestamp", columns="series_id", values="value")

        # Check for required series
        vix_col = VIX_SERIES["vix"]
        vix3m_col = VIX_SERIES["vix3m"]

        if vix_col not in pivot.columns or vix3m_col not in pivot.columns:
            available = list(pivot.columns)
            logger.warning(
                "Missing VIX series. Need %s and %s, have %s",
                vix_col,
                vix3m_col,
                available,
            )
            return pd.DataFrame(
                columns=["timestamp", "vix", "vix3m", "ratio", "spread", "structure"]
            )

        # Forward fill sparse data and drop NaN
        pivot = pivot.ffill().dropna()

        if pivot.empty:
            logger.warning("No data after forward fill")
            return pd.DataFrame(
                columns=["timestamp", "vix", "vix3m", "ratio", "spread", "structure"]
            )

        # Calculate ratio and spread
        vix = pivot[vix_col]
        vix3m = pivot[vix3m_col]

        # Avoid division by zero
        ratio = vix / vix3m.replace(0, float("nan"))
        spread = vix - vix3m

        result = pd.DataFrame(
            {
                "timestamp": pivot.index,
                "vix": vix.values,
                "vix3m": vix3m.values,
                "ratio": ratio.values,
                "spread": spread.values,
            }
        )

        # Classify term structure
        result["structure"] = result["ratio"].apply(
            lambda r: classify_structure(r).value if pd.notna(r) else "FLAT"
        )

        result = result.dropna(subset=["ratio"]).sort_values("timestamp").reset_index(drop=True)

        logger.info(
            "Calculated VIX term structure: %d observations, latest ratio=%.3f (%s)",
            len(result),
            result["ratio"].iloc[-1] if len(result) > 0 else 0,
            result["structure"].iloc[-1] if len(result) > 0 else "N/A",
        )

        return result

    async def get_current(self) -> VIXTermStructureResult:
        """Get current VIX term structure classification.

        Returns:
            VIXTermStructureResult with current values.

        Raises:
            ValueError: If no data available.
        """
        df = await self.calculate()

        if df.empty:
            raise ValueError("No VIX data available for term structure calculation")

        latest = df.iloc[-1]

        return VIXTermStructureResult(
            timestamp=datetime.now(UTC),
            vix=float(latest["vix"]),
            vix3m=float(latest["vix3m"]),
            ratio=float(latest["ratio"]),
            structure=TermStructure(latest["structure"]),
            spread=float(latest["spread"]),
        )
