"""Consumer credit risk collector and derived analytics.

Tracks a focused set of credit-stress indicators and market proxies:
- Consumer credit outstanding (TOTALSL / HCCSDODNS)
- Student loans outstanding (SLOASM)
- Loan delinquency / charge-off rates (DRALACBS, CORALACBS)
- Mortgage losses proxies (DRSFRMACBS, CORSFRMACBS)
- Bank loan loss reserves (QBPBSTASTLNLESSRES)
- Relative market indicators (XLP/XLY, AXP vs IGV)

This collector is designed for monitoring credit-cycle stress and links it
with equity/sector relative performance.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.fred import FredCollector
from liquidity.collectors.registry import registry
from liquidity.collectors.yahoo import YahooCollector
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Core FRED series for consumer-credit stress monitoring
CREDIT_RISK_SERIES_MAP: dict[str, str] = {
    "consumer_credit_total": "TOTALSL",  # billions USD
    "consumer_credit_total_millions": "HCCSDODNS",  # millions USD
    "student_loans": "SLOASM",  # millions USD
    "debt_default_rate": "DRALACBS",  # percent (quarterly)
    "debt_chargeoff_rate": "CORALACBS",  # percent (quarterly)
    "mortgage_delinquency_rate": "DRSFRMACBS",  # percent (quarterly)
    "mortgage_chargeoff_rate": "CORSFRMACBS",  # percent (quarterly)
    "loan_loss_reserves": "QBPBSTASTLNLESSRES",  # millions USD (quarterly)
    # USD liquidity proxy components
    "fed_assets": "WALCL",  # millions USD
    "tga": "WDTGAL",  # billions USD
    "rrp": "WLRRAL",  # billions USD
}

# Requested market pairs
MARKET_PAIR_SYMBOLS: list[str] = ["XLP", "XLY", "AXP", "IGV"]

# Default universe for "stocks sensitive to consumer credit losses"
DEFAULT_SENSITIVE_STOCKS: list[str] = [
    "TSLA",
    "AMZN",
    "HD",
    "LOW",
    "COF",
    "DFS",
    "SYF",
    "AXP",
    "GM",
    "F",
    "BKNG",
    "CCL",
]


class ConsumerCreditRiskCollector(BaseCollector[pd.DataFrame]):
    """Collector for consumer-credit stress and market sensitivity proxies."""

    CREDIT_RISK_SERIES_MAP = CREDIT_RISK_SERIES_MAP
    MARKET_PAIR_SYMBOLS = MARKET_PAIR_SYMBOLS
    DEFAULT_SENSITIVE_STOCKS = DEFAULT_SENSITIVE_STOCKS

    def __init__(
        self,
        name: str = "consumer_credit_risk",
        settings: Settings | None = None,
        fred_collector: FredCollector | None = None,
        yahoo_collector: YahooCollector | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize collector with FRED and Yahoo dependencies."""
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()
        self._fred = fred_collector or FredCollector(
            name="consumer_credit_risk_fred",
            settings=self._settings,
        )
        self._yahoo = yahoo_collector or YahooCollector(
            name="consumer_credit_risk_yahoo",
            settings=self._settings,
        )

    async def collect(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        period: str = "2y",
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """Collect combined credit-risk macro + market data.

        Returns a single normalized DataFrame:
        - FRED rows use `series_id`
        - Yahoo rows are normalized to `series_id` from `symbol`
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365 * 5)
        if end_date is None:
            end_date = datetime.now(UTC)

        if symbols is None:
            symbols = self.MARKET_PAIR_SYMBOLS + self.DEFAULT_SENSITIVE_STOCKS

        fred_df = await self.collect_credit_risk(start_date=start_date, end_date=end_date)
        market_df = await self.collect_market_prices(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            period=period,
        )

        market_norm = market_df.rename(columns={"symbol": "series_id"}).copy()
        market_norm["unit"] = market_norm.get("unit", "price")

        combined = pd.concat(
            [
                fred_df[["timestamp", "series_id", "source", "value", "unit"]],
                market_norm[["timestamp", "series_id", "source", "value", "unit"]],
            ],
            ignore_index=True,
        ).sort_values("timestamp")

        return combined.reset_index(drop=True)

    async def collect_credit_risk(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect credit-stress macro series from FRED."""
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365 * 5)
        if end_date is None:
            end_date = datetime.now(UTC)

        symbols = list(self.CREDIT_RISK_SERIES_MAP.values())

        async def _fetch() -> pd.DataFrame:
            return await self._fred.collect(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
            )

        try:
            return await self.fetch_with_retry(_fetch, breaker_name="consumer_credit_risk_fred")
        except Exception as e:
            logger.error("Consumer credit risk FRED fetch failed: %s", e)
            raise CollectorFetchError(f"Consumer credit risk FRED fetch failed: {e}") from e

    async def collect_market_prices(
        self,
        symbols: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        period: str = "2y",
    ) -> pd.DataFrame:
        """Collect market prices from Yahoo for relative-performance analytics."""
        if symbols is None:
            symbols = self.MARKET_PAIR_SYMBOLS

        # Keep symbol order but remove duplicates
        symbols = list(dict.fromkeys(symbols))

        async def _fetch() -> pd.DataFrame:
            return await self._yahoo.collect(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                period=period,
            )

        try:
            return await self.fetch_with_retry(_fetch, breaker_name="consumer_credit_risk_yahoo")
        except Exception as e:
            logger.error("Consumer credit risk Yahoo fetch failed: %s", e)
            raise CollectorFetchError(f"Consumer credit risk Yahoo fetch failed: {e}") from e

    @staticmethod
    def _pivot_series(df: pd.DataFrame) -> pd.DataFrame:
        """Pivot long-format `series_id/value` data to wide format."""
        if df.empty:
            return pd.DataFrame()

        if "series_id" not in df.columns:
            raise ValueError("Expected column 'series_id' in DataFrame")

        wide = (
            df.pivot_table(
                index="timestamp",
                columns="series_id",
                values="value",
                aggfunc="last",
            )
            .sort_index()
            .ffill()
        )
        wide.index = pd.to_datetime(wide.index)
        return wide

    @staticmethod
    def _pivot_market(df: pd.DataFrame) -> pd.DataFrame:
        """Pivot market data (`symbol` or `series_id`) to wide close-price matrix."""
        if df.empty:
            return pd.DataFrame()

        symbol_col = "symbol" if "symbol" in df.columns else "series_id"
        if symbol_col not in df.columns:
            raise ValueError("Expected 'symbol' or 'series_id' column in market DataFrame")

        wide = (
            df.pivot_table(
                index="timestamp",
                columns=symbol_col,
                values="value",
                aggfunc="last",
            )
            .sort_index()
            .ffill()
        )
        wide.index = pd.to_datetime(wide.index)
        return wide

    @staticmethod
    def build_tracking_series(fred_df: pd.DataFrame) -> pd.DataFrame:
        """Build unified tracking series for credit stress dashboard metrics.

        Output columns (billions USD where monetary):
        - consumer_credit_total_b
        - student_loans_b
        - consumer_credit_ex_students_b
        - debt_default_rate_pct
        - debt_in_default_est_b (proxy estimate)
        - debt_chargeoff_rate_pct
        - mortgage_delinquency_rate_pct
        - mortgage_chargeoff_rate_pct
        - loan_loss_reserves_b
        - usd_liquidity_b
        - usd_liquidity_index
        """
        wide = ConsumerCreditRiskCollector._pivot_series(fred_df)
        if wide.empty:
            return pd.DataFrame()

        result = pd.DataFrame(index=wide.index)

        # Prefer HCCSDODNS (millions) when available, otherwise TOTALSL (billions)
        if "HCCSDODNS" in wide.columns:
            consumer_credit_b = wide["HCCSDODNS"] / 1000.0
        elif "TOTALSL" in wide.columns:
            consumer_credit_b = wide["TOTALSL"]
        else:
            consumer_credit_b = pd.Series(index=wide.index, dtype=float)

        student_loans_b = (
            wide["SLOASM"] / 1000.0 if "SLOASM" in wide.columns else pd.Series(index=wide.index, dtype=float)
        )

        result["consumer_credit_total_b"] = consumer_credit_b
        result["student_loans_b"] = student_loans_b
        result["consumer_credit_ex_students_b"] = (
            result["consumer_credit_total_b"] - result["student_loans_b"]
        )

        result["debt_default_rate_pct"] = wide.get(
            "DRALACBS", pd.Series(index=wide.index, dtype=float)
        )
        result["debt_chargeoff_rate_pct"] = wide.get(
            "CORALACBS", pd.Series(index=wide.index, dtype=float)
        )
        result["mortgage_delinquency_rate_pct"] = wide.get(
            "DRSFRMACBS", pd.Series(index=wide.index, dtype=float)
        )
        result["mortgage_chargeoff_rate_pct"] = wide.get(
            "CORSFRMACBS", pd.Series(index=wide.index, dtype=float)
        )

        # FDIC reserves are published in millions USD
        result["loan_loss_reserves_b"] = wide.get(
            "QBPBSTASTLNLESSRES", pd.Series(index=wide.index, dtype=float)
        ) / 1000.0

        # Debt in default proxy estimate = consumer credit ex students * delinquency rate
        result["debt_in_default_est_b"] = (
            result["consumer_credit_ex_students_b"] * result["debt_default_rate_pct"] / 100.0
        )

        # USD liquidity proxy similar to "USDLIQ" style constructions
        walcl_b = wide.get("WALCL", pd.Series(index=wide.index, dtype=float)) / 1000.0
        tga_b = wide.get("WDTGAL", pd.Series(index=wide.index, dtype=float))
        rrp_b = wide.get("WLRRAL", pd.Series(index=wide.index, dtype=float))

        result["usd_liquidity_b"] = walcl_b - tga_b - rrp_b

        first_valid = result["usd_liquidity_b"].dropna()
        if not first_valid.empty and first_valid.iloc[0] != 0:
            result["usd_liquidity_index"] = (
                result["usd_liquidity_b"] / first_valid.iloc[0] * 100.0
            )
        else:
            result["usd_liquidity_index"] = np.nan

        result = result.ffill()
        return result.reset_index(names="timestamp")

    @staticmethod
    def get_latest_tracking_metrics(tracking_df: pd.DataFrame) -> dict[str, float | None]:
        """Get latest snapshot metrics from tracking series."""
        if tracking_df.empty:
            return {
                "consumer_credit_total_b": None,
                "student_loans_b": None,
                "consumer_credit_ex_students_b": None,
                "debt_default_rate_pct": None,
                "debt_in_default_est_b": None,
                "mortgage_chargeoff_rate_pct": None,
                "loan_loss_reserves_b": None,
                "usd_liquidity_index": None,
            }

        latest = tracking_df.sort_values("timestamp").iloc[-1]
        return {
            "consumer_credit_total_b": float(latest.get("consumer_credit_total_b"))
            if pd.notna(latest.get("consumer_credit_total_b"))
            else None,
            "student_loans_b": float(latest.get("student_loans_b"))
            if pd.notna(latest.get("student_loans_b"))
            else None,
            "consumer_credit_ex_students_b": float(latest.get("consumer_credit_ex_students_b"))
            if pd.notna(latest.get("consumer_credit_ex_students_b"))
            else None,
            "debt_default_rate_pct": float(latest.get("debt_default_rate_pct"))
            if pd.notna(latest.get("debt_default_rate_pct"))
            else None,
            "debt_in_default_est_b": float(latest.get("debt_in_default_est_b"))
            if pd.notna(latest.get("debt_in_default_est_b"))
            else None,
            "mortgage_chargeoff_rate_pct": float(latest.get("mortgage_chargeoff_rate_pct"))
            if pd.notna(latest.get("mortgage_chargeoff_rate_pct"))
            else None,
            "loan_loss_reserves_b": float(latest.get("loan_loss_reserves_b"))
            if pd.notna(latest.get("loan_loss_reserves_b"))
            else None,
            "usd_liquidity_index": float(latest.get("usd_liquidity_index"))
            if pd.notna(latest.get("usd_liquidity_index"))
            else None,
        }

    @staticmethod
    def calculate_xlp_xly_ratio(market_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate XLP/XLY defensive-vs-cyclical ratio."""
        prices = ConsumerCreditRiskCollector._pivot_market(market_df)
        if prices.empty or "XLP" not in prices.columns or "XLY" not in prices.columns:
            return pd.DataFrame(columns=["timestamp", "xlp_xly_ratio"])

        ratio = prices["XLP"] / prices["XLY"]
        return pd.DataFrame(
            {
                "timestamp": ratio.index,
                "xlp_xly_ratio": ratio.values,
            }
        ).dropna()

    @staticmethod
    def calculate_axp_igv_relative(market_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate AXP vs IGV relative spread in percent."""
        prices = ConsumerCreditRiskCollector._pivot_market(market_df)
        if prices.empty or "AXP" not in prices.columns or "IGV" not in prices.columns:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "axp_rebased",
                    "igv_rebased",
                    "relative_spread_pct",
                ]
            )

        axp = prices["AXP"].dropna()
        igv = prices["IGV"].dropna()
        common_idx = axp.index.intersection(igv.index)
        if len(common_idx) == 0:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "axp_rebased",
                    "igv_rebased",
                    "relative_spread_pct",
                ]
            )

        axp = axp.loc[common_idx]
        igv = igv.loc[common_idx]

        axp_rebased = axp / axp.iloc[0] * 100.0
        igv_rebased = igv / igv.iloc[0] * 100.0
        relative_spread_pct = (axp_rebased - igv_rebased)

        return pd.DataFrame(
            {
                "timestamp": common_idx,
                "axp_rebased": axp_rebased.values,
                "igv_rebased": igv_rebased.values,
                "relative_spread_pct": relative_spread_pct.values,
            }
        )

    @staticmethod
    def _build_credit_stress_factor(tracking_df: pd.DataFrame) -> pd.Series:
        """Build a composite stress factor from defaults/losses/reserves."""
        if tracking_df.empty:
            return pd.Series(dtype=float, name="credit_stress_factor")

        ts = tracking_df.copy()
        ts["timestamp"] = pd.to_datetime(ts["timestamp"])
        ts = ts.set_index("timestamp").sort_index().ffill()

        factor_parts = pd.DataFrame(index=ts.index)
        factor_parts["default_rate_change"] = ts["debt_default_rate_pct"].diff()
        factor_parts["chargeoff_rate_change"] = ts["debt_chargeoff_rate_pct"].diff()
        factor_parts["mortgage_loss_change"] = ts["mortgage_chargeoff_rate_pct"].diff()
        factor_parts["reserves_growth"] = ts["loan_loss_reserves_b"].pct_change()

        z_parts = factor_parts.copy()
        for col in z_parts.columns:
            std = z_parts[col].std(ddof=0)
            if pd.isna(std) or std == 0:
                z_parts[col] = np.nan
            else:
                z_parts[col] = (z_parts[col] - z_parts[col].mean()) / std

        factor = z_parts.mean(axis=1, skipna=True)
        factor.name = "credit_stress_factor"
        return factor.dropna()

    @staticmethod
    def rank_credit_sensitive_stocks(
        market_df: pd.DataFrame,
        tracking_df: pd.DataFrame,
        symbols: list[str] | None = None,
        min_observations: int = 12,
    ) -> pd.DataFrame:
        """Rank stocks by sensitivity to consumer-credit loss stress.

        Higher `sensitivity_score` means a stock tends to underperform when
        credit stress rises.
        """
        prices = ConsumerCreditRiskCollector._pivot_market(market_df)
        if prices.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "corr_to_stress",
                    "beta_to_stress",
                    "sensitivity_score",
                    "observations",
                ]
            )

        if symbols is None:
            symbols = [c for c in prices.columns if c not in {"XLP", "XLY", "AXP", "IGV"}]

        symbols = [s for s in symbols if s in prices.columns]
        if not symbols:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "corr_to_stress",
                    "beta_to_stress",
                    "sensitivity_score",
                    "observations",
                ]
            )

        stress_factor = ConsumerCreditRiskCollector._build_credit_stress_factor(tracking_df)
        if stress_factor.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "corr_to_stress",
                    "beta_to_stress",
                    "sensitivity_score",
                    "observations",
                ]
            )

        # Align on monthly observations to match macro frequency
        monthly_prices = prices[symbols].resample("ME").last().ffill()
        stock_returns = monthly_prices.pct_change().dropna(how="all")
        monthly_stress = stress_factor.resample("ME").last().dropna()

        combined = stock_returns.join(monthly_stress, how="inner").dropna(
            subset=["credit_stress_factor"]
        )

        rows: list[dict[str, float | int | str]] = []
        for symbol in symbols:
            s = combined[[symbol, "credit_stress_factor"]].dropna()
            n = len(s)
            if n < min_observations:
                continue

            corr = float(s[symbol].corr(s["credit_stress_factor"]))
            stress_var = float(s["credit_stress_factor"].var(ddof=0))
            if stress_var > 0:
                cov = float(np.cov(s[symbol].values, s["credit_stress_factor"].values, ddof=0)[0, 1])
                beta = cov / stress_var
            else:
                beta = np.nan

            # Negative correlation = vulnerable when stress rises -> high score
            sensitivity_score = -corr

            rows.append(
                {
                    "symbol": symbol,
                    "corr_to_stress": corr,
                    "beta_to_stress": beta,
                    "sensitivity_score": sensitivity_score,
                    "observations": n,
                }
            )

        if not rows:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "corr_to_stress",
                    "beta_to_stress",
                    "sensitivity_score",
                    "observations",
                ]
            )

        result = pd.DataFrame(rows).sort_values(
            "sensitivity_score",
            ascending=False,
        )
        return result.reset_index(drop=True)


# Register collector
registry.register("consumer_credit_risk", ConsumerCreditRiskCollector)
