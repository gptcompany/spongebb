"""Global Liquidity Index calculator aggregating major central bank balance sheets.

Implements the Global Liquidity formula:
    Global Liquidity = Fed Net Liq + ECB_USD + BoJ_USD + PBoC_USD (Tier 1)
                     + BoE_USD + SNB_USD + BoC_USD (Tier 2, optional)

Tier 1 CBs cover >85% of global central bank assets (~$35T total).
All values are converted to USD using FX rates for consistent aggregation.

FX Conversion:
- ECB (EUR) -> multiply by EUR/USD
- BoJ (JPY) -> divide by USD/JPY
- PBoC (CNY) -> divide by USD/CNY
- BoE (GBP) -> multiply by GBP/USD
- SNB (CHF) -> divide by USD/CHF
- BoC (CAD) -> divide by USD/CAD
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from liquidity.calculators.net_liquidity import NetLiquidityCalculator
from liquidity.collectors.boc import BOCCollector
from liquidity.collectors.boe import BOECollector
from liquidity.collectors.fred import FredCollector
from liquidity.collectors.fx import FXCollector
from liquidity.collectors.pboc import PBOCCollector
from liquidity.collectors.snb import SNBCollector
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# FX pairs needed for conversion
# Format: (internal_name, yahoo_ticker, conversion_type)
# "multiply" = multiply local currency value by rate to get USD
# "divide" = divide local currency value by rate to get USD
FX_CONVERSION_CONFIG: dict[str, tuple[str, str]] = {
    "EUR": ("EURUSD=X", "multiply"),  # EUR -> USD: multiply by EUR/USD
    "JPY": ("USDJPY=X", "divide"),  # JPY -> USD: divide by USD/JPY
    "CNY": ("USDCNY=X", "divide"),  # CNY -> USD: divide by USD/CNY
    "GBP": ("GBPUSD=X", "multiply"),  # GBP -> USD: multiply by GBP/USD
    "CHF": ("USDCHF=X", "divide"),  # CHF -> USD: divide by USD/CHF
    "CAD": ("USDCAD=X", "divide"),  # CAD -> USD: divide by USD/CAD
}

# Central bank data units (for conversion to billions USD)
# All values will be converted to billions USD for final output
CB_UNITS: dict[str, dict[str, Any]] = {
    "fed": {"unit": "billions_usd", "divisor": 1.0},  # Already in billions from NetLiq
    "ecb": {"unit": "millions_eur", "divisor": 1000.0},  # millions -> billions
    "boj": {"unit": "100_millions_jpy", "divisor": 10.0},  # 100M -> billions
    "pboc_assets": {"unit": "100_millions_cny", "divisor": 10.0},  # 100M -> billions
    "pboc_reserves": {
        "unit": "millions_usd",
        "divisor": 1000.0,
    },  # millions -> billions
    "boe": {"unit": "millions_gbp", "divisor": 1000.0},  # millions -> billions
    "snb": {"unit": "millions_chf", "divisor": 1000.0},  # millions -> billions
    "boc": {"unit": "millions_cad", "divisor": 1000.0},  # millions -> billions
}

# Coverage percentages (approximate, based on IMF data)
# Tier 1: Fed ~30%, ECB ~20%, BoJ ~25%, PBoC ~20% = ~95%
# Tier 2: BoE ~3%, SNB ~0.5%, BoC ~0.5% = ~4%
TIER_COVERAGE: dict[str, float] = {
    "fed": 30.0,
    "ecb": 20.0,
    "boj": 25.0,
    "pboc": 20.0,
    "boe": 3.0,
    "snb": 0.5,
    "boc": 0.5,
}


@dataclass
class GlobalLiquidityResult:
    """Result of Global Liquidity calculation with CB breakdown.

    All monetary values are in billions USD.

    Attributes:
        timestamp: Timestamp of the calculation.
        total_usd: Total Global Liquidity in billions USD.
        fed_usd: Fed Net Liquidity component in billions USD.
        ecb_usd: ECB total assets in billions USD.
        boj_usd: BoJ total assets in billions USD.
        pboc_usd: PBoC total assets in billions USD.
        boe_usd: BoE total assets in billions USD (Tier 2, optional).
        snb_usd: SNB total assets in billions USD (Tier 2, optional).
        boc_usd: BoC total assets in billions USD (Tier 2, optional).
        weekly_delta: Change over past 7 days in billions USD.
        delta_30d: Change over past 30 days in billions USD.
        delta_60d: Change over past 60 days in billions USD.
        delta_90d: Change over past 90 days in billions USD.
        coverage_pct: Percentage of global CB assets covered.
    """

    timestamp: datetime
    total_usd: float
    fed_usd: float
    ecb_usd: float
    boj_usd: float
    pboc_usd: float
    boe_usd: float | None
    snb_usd: float | None
    boc_usd: float | None
    weekly_delta: float
    delta_30d: float
    delta_60d: float
    delta_90d: float
    coverage_pct: float


@dataclass
class CBDataFrames:
    """Central bank DataFrames for aggregation."""

    fed: pd.DataFrame
    ecb: pd.DataFrame
    boj: pd.DataFrame
    pboc: pd.DataFrame
    fx: pd.DataFrame
    boe: pd.DataFrame
    snb: pd.DataFrame
    boc: pd.DataFrame


class GlobalLiquidityCalculator:
    """Calculate Global Liquidity Index from major central banks.

    Aggregates balance sheet data from Fed, ECB, BoJ, PBoC (Tier 1)
    and optionally BoE, SNB, BoC (Tier 2). All values converted to USD.

    Example:
        calculator = GlobalLiquidityCalculator()

        # Get current Global Liquidity
        result = await calculator.get_current()
        print(f"Global Liquidity: ${result.total_usd:.1f}B")
        print(f"Weekly delta: ${result.weekly_delta:.1f}B")

        # Get time series
        df = await calculator.calculate(tier=1)  # Tier 1 only
        df = await calculator.calculate(tier=2)  # Include Tier 2
    """

    def __init__(
        self,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Global Liquidity calculator.

        Args:
            settings: Optional settings override.
            **kwargs: Additional arguments passed to collectors.
        """
        self._settings = settings or get_settings()
        self._kwargs = kwargs

        # Initialize collectors
        self._net_liq_calc = NetLiquidityCalculator(settings=self._settings, **kwargs)
        self._fred = FredCollector(settings=self._settings, **kwargs)
        self._fx = FXCollector(settings=self._settings, **kwargs)
        self._pboc = PBOCCollector(settings=self._settings, **kwargs)
        self._boe = BOECollector(settings=self._settings, **kwargs)
        self._snb = SNBCollector(settings=self._settings, **kwargs)
        self._boc = BOCCollector(settings=self._settings, **kwargs)

        # Cache for FX rates
        self._fx_cache: dict[str, float] = {}

    async def calculate(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        tier: int = 1,
    ) -> pd.DataFrame:
        """Calculate Global Liquidity time series.

        Args:
            start_date: Start date for calculation. Defaults to 120 days ago.
            end_date: End date for calculation. Defaults to today.
            tier: 1 = Tier 1 CBs only (Fed, ECB, BoJ, PBoC)
                  2 = Include Tier 2 CBs (BoE, SNB, BoC)

        Returns:
            DataFrame with columns:
                - timestamp: Date of observation
                - global_liquidity: Total Global Liquidity in billions USD
                - fed_usd: Fed Net Liquidity in billions USD
                - ecb_usd: ECB in billions USD
                - boj_usd: BoJ in billions USD
                - pboc_usd: PBoC in billions USD
                - boe_usd: BoE in billions USD (if tier=2)
                - snb_usd: SNB in billions USD (if tier=2)
                - boc_usd: BoC in billions USD (if tier=2)
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=120)
        if end_date is None:
            end_date = datetime.now(UTC)

        logger.info(
            "Calculating Global Liquidity (tier=%d) from %s to %s",
            tier,
            start_date.date(),
            end_date.date(),
        )

        # Fetch all data in parallel
        tasks: list[Any] = [
            self._net_liq_calc.calculate(start_date, end_date),
            self._fred.collect_ecb_assets(start_date, end_date),
            self._fred.collect_boj_assets(start_date, end_date),
            self._pboc.collect(start_date, end_date),
            self._get_fx_rates(start_date, end_date),
        ]

        if tier >= 2:
            tasks.extend(
                [
                    self._boe.collect(start_date, end_date),
                    self._snb.collect(start_date, end_date),
                    self._boc.collect_total_assets(start_date, end_date),
                ]
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Unpack results - cast to DataFrame after checking for exceptions
        def safe_df(result: pd.DataFrame | BaseException) -> pd.DataFrame:
            if isinstance(result, BaseException):
                return pd.DataFrame()
            return result

        fed_df = safe_df(results[0])
        ecb_df = safe_df(results[1])
        boj_df = safe_df(results[2])
        pboc_df = safe_df(results[3])
        fx_df = safe_df(results[4])

        # Log any errors
        for i, r in enumerate(results[:5]):
            if isinstance(r, Exception):
                logger.warning("Tier 1 data fetch %d failed: %s", i, r)

        boe_df = pd.DataFrame()
        snb_df = pd.DataFrame()
        boc_df = pd.DataFrame()

        if tier >= 2 and len(results) > 5:
            boe_df = safe_df(results[5])
            snb_df = safe_df(results[6])
            boc_df = safe_df(results[7])

            for i, r in enumerate(results[5:8]):
                if isinstance(r, Exception):
                    logger.warning("Tier 2 data fetch %d failed: %s", i, r)

        # Build the result DataFrame
        cb_data = CBDataFrames(
            fed=fed_df, ecb=ecb_df, boj=boj_df, pboc=pboc_df,
            fx=fx_df, boe=boe_df, snb=snb_df, boc=boc_df,
        )
        return self._aggregate_data(cb_data, tier=tier)

    async def get_current(self, tier: int = 1) -> GlobalLiquidityResult:
        """Get current Global Liquidity with breakdown and deltas.

        Args:
            tier: 1 = Tier 1 only, 2 = Include Tier 2.

        Returns:
            GlobalLiquidityResult with current values and deltas.

        Raises:
            ValueError: If no data available for calculation.
        """
        df = await self.calculate(tier=tier)

        if df.empty:
            raise ValueError("No data available for Global Liquidity calculation")

        # Get the latest row
        latest = df.iloc[-1]
        latest_ts = pd.Timestamp(latest["timestamp"])

        # Calculate deltas
        weekly_delta = self._calculate_delta(df, days=7)
        delta_30d = self._calculate_delta(df, days=30)
        delta_60d = self._calculate_delta(df, days=60)
        delta_90d = self._calculate_delta(df, days=90)

        # Calculate coverage
        coverage = self._calculate_coverage(tier)

        # Convert timestamp to UTC datetime
        ts_pydatetime = (
            datetime.now(UTC)
            if pd.isna(latest_ts)
            else latest_ts.to_pydatetime().replace(tzinfo=UTC)
        )

        result = GlobalLiquidityResult(
            timestamp=ts_pydatetime,
            total_usd=float(latest["global_liquidity"]),
            fed_usd=float(latest["fed_usd"]),
            ecb_usd=float(latest["ecb_usd"]),
            boj_usd=float(latest["boj_usd"]),
            pboc_usd=float(latest["pboc_usd"]),
            boe_usd=float(latest["boe_usd"]) if "boe_usd" in latest else None,
            snb_usd=float(latest["snb_usd"]) if "snb_usd" in latest else None,
            boc_usd=float(latest["boc_usd"]) if "boc_usd" in latest else None,
            weekly_delta=weekly_delta,
            delta_30d=delta_30d,
            delta_60d=delta_60d,
            delta_90d=delta_90d,
            coverage_pct=coverage,
        )

        logger.info(
            "Current Global Liquidity: $%.1fT USD, weekly delta: $%.1fB",
            result.total_usd / 1000,  # Convert to trillions for display
            result.weekly_delta,
        )

        return result

    async def _get_fx_rates(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch FX rates needed for currency conversion.

        Args:
            start_date: Start date for rates.
            end_date: End date for rates.

        Returns:
            DataFrame with FX rates for all required pairs.
        """
        symbols = [config[0] for config in FX_CONVERSION_CONFIG.values()]
        return await self._fx.collect(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )

    def _convert_to_usd(
        self,
        value: float,
        currency: str,
        fx_rates: dict[str, float],
    ) -> float:
        """Convert a value from local currency to USD.

        Args:
            value: Value in local currency (in billions after unit conversion).
            currency: Currency code (EUR, JPY, CNY, GBP, CHF, CAD).
            fx_rates: Dictionary of current FX rates.

        Returns:
            Value in billions USD.
        """
        if currency not in FX_CONVERSION_CONFIG:
            logger.warning("Unknown currency %s, returning 0", currency)
            return 0.0

        ticker, conversion = FX_CONVERSION_CONFIG[currency]

        if ticker not in fx_rates:
            logger.warning("FX rate for %s not available", ticker)
            return 0.0

        rate = fx_rates[ticker]

        return value * rate if conversion == "multiply" else value / rate

    def _aggregate_data(
        self,
        cb: CBDataFrames,
        tier: int,
    ) -> pd.DataFrame:
        """Aggregate all CB data into Global Liquidity time series.

        Args:
            cb: Central bank DataFrames.
            tier: Tier level (1 or 2).

        Returns:
            Aggregated DataFrame with Global Liquidity.
        """
        # Get latest FX rates for conversion
        fx_rates = self._get_latest_fx_rates(cb.fx)

        # Process each CB dataset
        dfs: dict[str, pd.DataFrame] = {}

        # Fed Net Liquidity (already in billions USD)
        if not cb.fed.empty and "net_liquidity" in cb.fed.columns:
            dfs["fed"] = cb.fed[["timestamp", "net_liquidity"]].rename(
                columns={"net_liquidity": "fed_usd"}
            )
            dfs["fed"]["timestamp"] = pd.to_datetime(dfs["fed"]["timestamp"])

        # Tier 1 CBs
        tier1_cbs = [
            (cb.ecb, "ecb_usd", "EUR", "ecb"),
            (cb.boj, "boj_usd", "JPY", "boj"),
        ]
        for cb_df, col_name, currency, unit_key in tier1_cbs:
            if not cb_df.empty:
                processed = self._process_cb_data(
                    cb_df, col_name, currency, CB_UNITS[unit_key]["divisor"], fx_rates
                )
                if not processed.empty:
                    dfs[unit_key] = processed

        # PBoC - handle both asset types
        if not cb.pboc.empty:
            pboc_processed = self._process_pboc_data(cb.pboc, fx_rates)
            if not pboc_processed.empty:
                dfs["pboc"] = pboc_processed

        # Tier 2 CBs
        if tier >= 2:
            tier2_cbs = [
                (cb.boe, "boe_usd", "GBP", "boe"),
                (cb.snb, "snb_usd", "CHF", "snb"),
                (cb.boc, "boc_usd", "CAD", "boc"),
            ]
            for cb_df, col_name, currency, unit_key in tier2_cbs:
                if not cb_df.empty:
                    processed = self._process_cb_data(
                        cb_df, col_name, currency, CB_UNITS[unit_key]["divisor"], fx_rates
                    )
                    if not processed.empty:
                        dfs[unit_key] = processed

        if not dfs:
            logger.warning("No data available for aggregation")
            return pd.DataFrame()

        # Merge all dataframes on timestamp
        result = None
        for df in dfs.values():
            df = df.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
            result = (
                df
                if result is None
                else pd.merge(result, df, on="timestamp", how="outer")
            )

        if result is None or result.empty:
            return pd.DataFrame()

        # Sort by timestamp
        result = result.sort_values("timestamp").reset_index(drop=True)

        # Forward fill missing values (CBs report at different frequencies)
        value_cols = [c for c in result.columns if c.endswith("_usd")]
        result[value_cols] = result[value_cols].ffill()

        # Drop rows with any NaN in required Tier 1 columns
        tier1_cols = ["fed_usd", "ecb_usd", "boj_usd", "pboc_usd"]
        available_tier1 = [c for c in tier1_cols if c in result.columns]
        if available_tier1:
            result = result.dropna(subset=available_tier1)

        # Calculate global liquidity
        result["global_liquidity"] = result[value_cols].sum(axis=1)

        # Reorder columns
        cols = ["timestamp", "global_liquidity"] + sorted(value_cols)
        result = result[[c for c in cols if c in result.columns]]

        logger.info(
            "Aggregated Global Liquidity: %d observations, latest=$%.1fT USD",
            len(result),
            result["global_liquidity"].iloc[-1] / 1000 if len(result) > 0 else 0,
        )

        return result

    def _process_cb_data(
        self,
        df: pd.DataFrame,
        col_name: str,
        currency: str,
        divisor: float,
        fx_rates: dict[str, float],
    ) -> pd.DataFrame:
        """Process CB data and convert to billions USD.

        Args:
            df: Raw CB data with timestamp and value columns.
            col_name: Output column name (e.g., "ecb_usd").
            currency: Currency code for FX conversion.
            divisor: Divisor to convert to billions (e.g., 1000 for millions).
            fx_rates: FX rate dictionary.

        Returns:
            DataFrame with timestamp and converted USD value.
        """
        if df.empty:
            return pd.DataFrame()

        result = df.copy()

        # Ensure timestamp column
        if "timestamp" not in result.columns:
            return pd.DataFrame()

        # Get value column
        if "value" in result.columns:
            value_col = "value"
        else:
            # Try to find a value column
            value_cols = [
                c
                for c in result.columns
                if c not in ["timestamp", "series_id", "source", "unit"]
            ]
            if not value_cols:
                return pd.DataFrame()
            value_col = value_cols[0]

        # Convert to billions in local currency
        result["local_billions"] = result[value_col] / divisor

        # Convert to USD
        result[col_name] = result["local_billions"].apply(
            lambda x: self._convert_to_usd(x, currency, fx_rates)
        )

        return result[["timestamp", col_name]].dropna()

    def _process_pboc_data(
        self,
        df: pd.DataFrame,
        fx_rates: dict[str, float],
    ) -> pd.DataFrame:
        """Process PBoC data which may be in CNY or USD (reserves proxy).

        Args:
            df: PBoC data from collector.
            fx_rates: FX rates for conversion.

        Returns:
            DataFrame with timestamp and pboc_usd column.
        """
        if df.empty:
            return pd.DataFrame()

        result = df.copy()

        if "series_id" not in result.columns:
            return pd.DataFrame()

        # Check which series we have
        series = result["series_id"].unique()

        if "PBOC_TOTAL_ASSETS" in series:
            # Total assets in 100 million CNY
            assets = result[result["series_id"] == "PBOC_TOTAL_ASSETS"].copy()
            assets["local_billions"] = (
                assets["value"] / CB_UNITS["pboc_assets"]["divisor"]
            )
            assets["pboc_usd"] = assets["local_billions"].apply(
                lambda x: self._convert_to_usd(x, "CNY", fx_rates)
            )
            return assets[["timestamp", "pboc_usd"]].dropna()

        if "CHINA_FOREIGN_RESERVES" in series:
            # Foreign reserves in millions USD - use as proxy
            # Note: This is a proxy, not actual balance sheet, but correlates well
            reserves = result[result["series_id"] == "CHINA_FOREIGN_RESERVES"].copy()
            reserves["pboc_usd"] = (
                reserves["value"] / CB_UNITS["pboc_reserves"]["divisor"]
            )
            # Scale up: reserves are ~3T, total assets ~47T -> multiply by ~15
            reserves["pboc_usd"] = reserves["pboc_usd"] * 15
            return reserves[["timestamp", "pboc_usd"]].dropna()

        return pd.DataFrame()

    def _get_latest_fx_rates(self, fx_df: pd.DataFrame) -> dict[str, float]:
        """Extract latest FX rates from DataFrame.

        Args:
            fx_df: FX rates DataFrame with series_id and value columns.

        Returns:
            Dictionary mapping ticker to latest rate.
        """
        if fx_df.empty:
            logger.warning("No FX data available, using fallback rates")
            # Fallback rates (approximate as of 2025)
            return {
                "EURUSD=X": 1.05,
                "USDJPY=X": 155.0,
                "USDCNY=X": 7.25,
                "GBPUSD=X": 1.25,
                "USDCHF=X": 0.90,
                "USDCAD=X": 1.40,
            }

        rates = {}
        for ticker in fx_df["series_id"].unique():
            ticker_data = fx_df[fx_df["series_id"] == ticker]
            if not ticker_data.empty:
                # Get latest value
                latest = ticker_data.loc[ticker_data["timestamp"].idxmax()]
                rates[ticker] = float(latest["value"])

        logger.debug("FX rates: %s", rates)
        return rates

    def _calculate_delta(self, df: pd.DataFrame, days: int) -> float:
        """Calculate change in Global Liquidity over a given period.

        Args:
            df: DataFrame with global_liquidity and timestamp columns.
            days: Number of days to look back.

        Returns:
            Change in global_liquidity in billions USD. Returns 0.0 if not enough data.
        """
        if len(df) < 2 or "global_liquidity" not in df.columns:
            return 0.0

        latest_ts = pd.Timestamp(df.iloc[-1]["timestamp"])
        target_ts = latest_ts - pd.Timedelta(days=days)

        df_ts = pd.to_datetime(df["timestamp"])
        mask = df_ts <= target_ts
        if not mask.any():
            logger.debug("Not enough data for %d-day delta", days)
            return 0.0

        past_idx = df_ts[mask].idxmax()
        past_value = df.loc[past_idx, "global_liquidity"]
        current_value = df.iloc[-1]["global_liquidity"]

        return float(current_value - past_value)

    @staticmethod
    def _calculate_coverage(tier: int) -> float:
        """Calculate coverage percentage based on tier.

        Args:
            tier: Tier level (1 or 2).

        Returns:
            Coverage percentage of global CB assets.
        """
        tier1_coverage = sum(TIER_COVERAGE[cb] for cb in ["fed", "ecb", "boj", "pboc"])

        if tier >= 2:
            tier2_coverage = sum(TIER_COVERAGE[cb] for cb in ["boe", "snb", "boc"])
            return tier1_coverage + tier2_coverage

        return tier1_coverage

    def __repr__(self) -> str:
        """Return string representation of the calculator."""
        return "GlobalLiquidityCalculator(tier1=Fed+ECB+BoJ+PBoC)"
