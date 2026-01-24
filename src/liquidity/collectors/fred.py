"""FRED collector for Fed balance sheet and macro data.

Fetches economic data from FRED (Federal Reserve Economic Data) via OpenBB SDK:
- WALCL: Fed Total Assets
- WLRRAL: Reverse Repo (RRP)
- WDTGAL: Treasury General Account (TGA)
- WRESBAL: Bank Reserves
- SOFR: Secured Overnight Financing Rate

Implements the Hayes Net Liquidity formula:
Net Liquidity = WALCL - WLRRAL - WDTGAL
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from openbb import obb

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _find_date_column(df: pd.DataFrame) -> str:
    """Find the date column in a DataFrame.

    Args:
        df: DataFrame to search.

    Returns:
        Name of the date column.

    Raises:
        ValueError: If no date column can be identified.
    """
    for col in ["date", "index", "timestamp"]:
        if col in df.columns:
            return str(col)

    if df.index.name:
        return str(df.index.name)

    if len(df.columns) > 0:
        return str(df.columns[0])

    raise ValueError("Could not identify date column in DataFrame")


# FRED series mapping
# Keys are internal names, values are FRED series IDs
SERIES_MAP: dict[str, str] = {
    # Fed Balance Sheet (Phase 1 core)
    "fed_total_assets": "WALCL",  # Fed Total Assets (millions USD, weekly)
    "rrp": "WLRRAL",  # Reverse Repo (billions USD, weekly)
    "tga": "WDTGAL",  # Treasury General Account (billions USD, weekly)
    "bank_reserves": "WRESBAL",  # Reserve Balances (millions USD, biweekly)
    "sofr": "SOFR",  # Secured Overnight Financing Rate (percent, daily)
    # Volatility (Phase 1 market indicators)
    "vix": "VIXCLS",  # VIX (percent, daily)
    "vix3m": "VXVCLS",  # VIX3M for term structure (percent, daily)
    # Yield Curve (Phase 1 market indicators)
    "dgs2": "DGS2",  # 2-Year Treasury (percent, daily)
    "dgs10": "DGS10",  # 10-Year Treasury (percent, daily)
    "t10y2y": "T10Y2Y",  # 10Y-2Y Spread, pre-calculated (percent, daily)
    # Credit Spreads (Phase 1 market indicators)
    "hy_oas": "BAMLH0A0HYM2",  # High Yield OAS (bps, daily)
    "ig_oas": "BAMLC0A0CM",  # Investment Grade OAS (bps, daily)
    # Phase 2: Global CB totals via FRED
    "ecb_total_assets": "ECBASSETSW",  # Weekly, millions EUR
    "boj_total_assets": "JPNASSETS",  # Monthly, 100 million JPY (not millions!)
    # Phase 6: SLOOS - Senior Loan Officer Opinion Survey (quarterly)
    # Net % of banks tightening standards (positive = tightening, negative = easing)
    "sloos_ci_large": "DRTSCILM",  # C&I loans to large/middle firms (main indicator)
    "sloos_ci_small": "DRTSCIS",  # C&I loans to small firms
    "sloos_cre": "DRTSROM",  # Commercial real estate loans
    "sloos_demand_ci": "DRSDCILM",  # Demand for C&I from large firms (complement)
    # Phase 6: Commercial Paper rates (daily)
    "cp_nonfinancial_3m": "DCPN3M",  # 90-day AA Nonfinancial CP
}

# Unit conversions for standardization
UNIT_MAP: dict[str, str] = {
    # Fed Balance Sheet
    "WALCL": "millions_usd",
    "WLRRAL": "billions_usd",
    "WDTGAL": "billions_usd",
    "WRESBAL": "millions_usd",
    "SOFR": "percent",
    # Volatility
    "VIXCLS": "percent",
    "VXVCLS": "percent",
    # Yield Curve
    "DGS2": "percent",
    "DGS10": "percent",
    "T10Y2Y": "percent",
    # Credit Spreads
    "BAMLH0A0HYM2": "bps",  # Basis points
    "BAMLC0A0CM": "bps",  # Basis points
    # Global CB totals (Phase 2)
    "ECBASSETSW": "millions_eur",
    "JPNASSETS": "100_millions_jpy",  # FRED unit is "100 Million Yen"
    # SLOOS - Net % of banks tightening (range: -30% to +70%)
    "DRTSCILM": "net_percent",  # C&I loans to large/middle firms
    "DRTSCIS": "net_percent",  # C&I loans to small firms
    "DRTSROM": "net_percent",  # Commercial real estate loans
    "DRSDCILM": "net_percent",  # Demand for C&I from large firms
    # Commercial Paper rates
    "DCPN3M": "percent",  # 90-day AA Nonfinancial CP
}


class FredCollector(BaseCollector[pd.DataFrame]):
    """FRED data collector using OpenBB SDK.

    Fetches Fed balance sheet data and calculates Net Liquidity (Hayes formula).

    Example:
        collector = FredCollector()
        df = await collector.collect(["WALCL", "WLRRAL", "WDTGAL"])

        # Calculate Net Liquidity
        net_liq = FredCollector.calculate_net_liquidity(df)
    """

    SERIES_MAP = SERIES_MAP

    def __init__(
        self,
        name: str = "fred",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize FRED collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()

        # Set OpenBB FRED API key if available
        api_key = self._settings.fred_api_key.get_secret_value()
        if api_key:
            obb.user.credentials.fred_api_key = api_key
            logger.debug("FRED API key configured from settings")

    async def collect(
        self,
        symbols: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect FRED series data.

        Args:
            symbols: List of FRED series IDs to fetch. Defaults to all balance sheet series.
            start_date: Start date for data fetch. Defaults to 30 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if symbols is None:
            symbols = ["WALCL", "WLRRAL", "WDTGAL", "WRESBAL"]
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_sync, symbols, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("FRED fetch failed: %s", e)
            raise CollectorFetchError(f"FRED data fetch failed: {e}") from e

    def _fetch_sync(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Synchronous fetch implementation using OpenBB.

        Args:
            symbols: FRED series IDs.
            start_date: Start date.
            end_date: End date.

        Returns:
            Normalized DataFrame with timestamp, series_id, source, value, unit columns.
        """
        logger.info("Fetching FRED series: %s", symbols)

        # Fetch data using OpenBB
        result = obb.economy.fred_series(
            symbol=",".join(symbols),
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            provider="fred",
        )

        # Convert to DataFrame
        df = result.to_df().reset_index()

        if df.empty:
            logger.warning("No data returned from FRED for symbols: %s", symbols)
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Find date column
        date_col = _find_date_column(df)

        # Melt to long format
        value_vars = [col for col in df.columns if col in symbols]

        if not value_vars:
            logger.warning("No value columns found matching symbols: %s", symbols)
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        df_long = df.melt(
            id_vars=[date_col],
            value_vars=value_vars,
            var_name="series_id",
            value_name="value",
        )

        # Normalize columns
        df_long = df_long.rename(columns={date_col: "timestamp"})
        df_long["timestamp"] = pd.to_datetime(df_long["timestamp"])
        df_long["source"] = "fred"
        df_long["unit"] = df_long["series_id"].map(UNIT_MAP).fillna("unknown")

        # Clean and sort
        df_long = (
            df_long.dropna(subset=["value"])
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        logger.info("Fetched %d data points from FRED", len(df_long))

        return df_long[["timestamp", "series_id", "source", "value", "unit"]]

    @staticmethod
    def calculate_net_liquidity(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Net Liquidity using the Hayes formula.

        Net Liquidity = WALCL - WLRRAL - WDTGAL

        Note: WLRRAL and WDTGAL are in billions, WALCL in millions.
        Converts all to millions USD before calculation.

        Args:
            df: DataFrame with timestamp, series_id, value columns.

        Returns:
            DataFrame with timestamp, net_liquidity columns (in millions USD).
        """
        required = {"WALCL", "WLRRAL", "WDTGAL"}
        available = set(df["series_id"].unique())

        if not required.issubset(available):
            missing = required - available
            raise ValueError(f"Missing required series for Net Liquidity: {missing}")

        # Pivot to wide format for calculation
        pivot = df.pivot(index="timestamp", columns="series_id", values="value")

        # Convert units: WLRRAL and WDTGAL are in billions, convert to millions
        # Hayes formula: WALCL - RRP - TGA
        net_liquidity = (
            pivot["WALCL"] - (pivot["WLRRAL"] * 1000) - (pivot["WDTGAL"] * 1000)
        )

        result = pd.DataFrame(
            {
                "timestamp": net_liquidity.index,
                "net_liquidity": net_liquidity.values,
                "unit": "millions_usd",
            }
        ).dropna()

        logger.info(
            "Calculated Net Liquidity: min=%.0f, max=%.0f, latest=%.0f (millions USD)",
            result["net_liquidity"].min(),
            result["net_liquidity"].max(),
            result["net_liquidity"].iloc[-1] if len(result) > 0 else 0,
        )

        return result

    @staticmethod
    def calculate_yield_spread(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate yield spread from DGS10 and DGS2.

        Yield Spread = DGS10 - DGS2

        Useful for custom calculations if T10Y2Y is unavailable or for validation.

        Args:
            df: DataFrame with timestamp, series_id, value columns.

        Returns:
            DataFrame with timestamp, yield_spread columns (in percent).
        """
        required = {"DGS10", "DGS2"}
        available = set(df["series_id"].unique())

        if not required.issubset(available):
            missing = required - available
            raise ValueError(f"Missing required series for yield spread: {missing}")

        # Pivot to wide format for calculation
        pivot = df.pivot(index="timestamp", columns="series_id", values="value")
        yield_spread = pivot["DGS10"] - pivot["DGS2"]

        result = pd.DataFrame(
            {
                "timestamp": yield_spread.index,
                "yield_spread": yield_spread.values,
                "unit": "percent",
            }
        ).dropna()

        logger.info(
            "Calculated Yield Spread: min=%.2f, max=%.2f, latest=%.2f (percent)",
            result["yield_spread"].min(),
            result["yield_spread"].max(),
            result["yield_spread"].iloc[-1] if len(result) > 0 else 0,
        )

        return result

    async def collect_volatility(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect volatility series (VIX, VIX3M).

        Args:
            start_date: Start date for data fetch. Defaults to 30 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with volatility data.
        """
        return await self.collect(["VIXCLS", "VXVCLS"], start_date, end_date)

    async def collect_yields(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect yield curve series.

        Fetches DGS2, DGS10, and T10Y2Y (pre-calculated spread).

        Args:
            start_date: Start date for data fetch. Defaults to 30 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with yield curve data.
        """
        return await self.collect(["DGS2", "DGS10", "T10Y2Y"], start_date, end_date)

    async def collect_credit(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect credit spread series.

        Fetches HY OAS and IG OAS (ICE BofA indices).

        Args:
            start_date: Start date for data fetch. Defaults to 30 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with credit spread data (in basis points).
        """
        return await self.collect(["BAMLH0A0HYM2", "BAMLC0A0CM"], start_date, end_date)

    async def collect_ecb_assets(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect ECB total assets.

        Fetches ECBASSETSW (ECB Total Assets, weekly, millions EUR).

        Note: ECB balance sheet is typically 5-10 trillion EUR (5-10 million in FRED units).

        Args:
            start_date: Start date for data fetch. Defaults to 30 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with ECB total assets data (in millions EUR).
        """
        return await self.collect(["ECBASSETSW"], start_date, end_date)

    async def collect_boj_assets(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect BoJ total assets.

        Fetches JPNASSETS (BoJ Total Assets, monthly, 100 million JPY).

        Note: BoJ balance sheet is typically 700+ trillion JPY.
        FRED reports in 100 million JPY units, so 7,000,000 = 700 trillion JPY.

        Args:
            start_date: Start date for data fetch. Defaults to 30 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with BoJ total assets data (in 100 million JPY).
        """
        return await self.collect(["JPNASSETS"], start_date, end_date)

    async def collect_global_cb_totals(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Convenience method to collect all central bank total assets.

        Fetches Fed (WALCL), ECB (ECBASSETSW), and BoJ (JPNASSETS) total assets.

        Note on units:
        - WALCL: millions USD (weekly)
        - ECBASSETSW: millions EUR (weekly)
        - JPNASSETS: 100 million JPY (monthly)

        For Global Liquidity Index calculation, these need to be converted to a common
        currency (typically USD) using current exchange rates.

        Args:
            start_date: Start date for data fetch. Defaults to 30 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with all CB total assets data.
        """
        return await self.collect(
            ["WALCL", "ECBASSETSW", "JPNASSETS"], start_date, end_date
        )


# Register collector with the registry
registry.register("fred", FredCollector)
