"""Oil vs Real Rates Correlation Analyzer.

Analyzes the relationship between oil prices (WTI) and real interest rates (10Y TIPS yield).

Historical relationship:
- Oil and real rates typically have a negative correlation (-0.4 to -0.6 range)
- The relationship operates through three main channels:
  1. USD channel: Real rates up -> USD up -> Oil down (oil priced in USD)
  2. Growth channel: Real rates up -> Growth expectations down -> Oil demand down
  3. Inflation channel: Oil up -> Inflation up -> Real rates down (feedback)

Key regime classifications:
- "surge": Unusually strong negative correlation (< -0.7)
- "normal": Expected range (-0.7 to -0.3)
- "breakdown": Correlation breakdown, positive or weak (> -0.3)

Anti-patterns avoided:
- DON'T correlate price levels - use returns (pct_change for oil, diff for rates)
- DON'T ignore p-values - check statistical significance
- DON'T use too-short windows - need min 15 obs for 30d, 45 for 90d
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from scipy import stats

from liquidity.collectors.commodities import COMMODITY_SYMBOLS, CommodityCollector
from liquidity.collectors.fred import FredCollector
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class OilRealRatesCorrelation:
    """Oil vs Real Rates correlation analysis result.

    Attributes:
        timestamp: Timestamp of the analysis.
        corr_30d: 30-day rolling correlation.
        corr_90d: 90-day rolling correlation.
        corr_ewma: EWMA correlation (halflife=30 days).
        p_value_30d: P-value for 30-day correlation (statistical significance).
        p_value_90d: P-value for 90-day correlation.
        regime: Classification: "normal", "breakdown", or "surge".
    """

    timestamp: datetime
    corr_30d: float
    corr_90d: float
    corr_ewma: float
    p_value_30d: float
    p_value_90d: float
    regime: str  # "normal", "breakdown", "surge"

    def is_significant_30d(self, alpha: float = 0.05) -> bool:
        """Check if 30-day correlation is statistically significant."""
        return self.p_value_30d < alpha

    def is_significant_90d(self, alpha: float = 0.05) -> bool:
        """Check if 90-day correlation is statistically significant."""
        return self.p_value_90d < alpha


class OilRealRatesAnalyzer:
    """Analyzer for oil-real rates correlation.

    Computes rolling correlations between WTI oil prices and 10-Year TIPS yields
    to identify regime shifts in the relationship.

    Key methods:
    - compute_correlation(): Full time series of correlations
    - get_current_state(): Latest correlation snapshot

    Example:
        analyzer = OilRealRatesAnalyzer()

        # Get historical correlation
        df = await analyzer.compute_correlation(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2024, 1, 1)
        )

        # Get current state
        state = await analyzer.get_current_state()
        print(f"Regime: {state.regime}, Corr: {state.corr_30d:.2f}")
    """

    # Expected negative correlation range (historical)
    NORMAL_CORR_RANGE = (-0.7, -0.3)

    # Default EWMA halflife in days
    DEFAULT_EWMA_HALFLIFE = 30

    def __init__(
        self,
        settings: Settings | None = None,
        ewma_halflife: int = DEFAULT_EWMA_HALFLIFE,
    ) -> None:
        """Initialize the Oil-Real Rates Analyzer.

        Args:
            settings: Optional settings override.
            ewma_halflife: Halflife for EWMA correlation (days). Default 30.
        """
        self._settings = settings or get_settings()
        self._ewma_halflife = ewma_halflife
        self._commodity_collector = CommodityCollector(settings=self._settings)
        self._fred_collector = FredCollector(settings=self._settings)

    async def compute_correlation(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        window_30d: int = 30,
        window_90d: int = 90,
    ) -> pd.DataFrame:
        """Compute rolling oil-real rates correlation.

        Fetches WTI oil prices and 10Y TIPS yields, then calculates:
        - Rolling 30-day correlation (on returns)
        - Rolling 90-day correlation (on returns)
        - EWMA correlation
        - Regime classification

        Args:
            start_date: Start date for data. Defaults to 365 days ago.
            end_date: End date for data. Defaults to today.
            window_30d: Rolling window for 30-day correlation. Default 30.
            window_90d: Rolling window for 90-day correlation. Default 90.

        Returns:
            DataFrame with columns:
            - timestamp: Date
            - oil_price: WTI price ($/barrel)
            - real_10y: 10Y TIPS yield (%)
            - oil_ret: Oil price return
            - rates_diff: Real rates change
            - corr_30d: 30-day rolling correlation
            - corr_90d: 90-day rolling correlation
            - corr_ewma: EWMA correlation
            - regime: "normal", "breakdown", "surge", or "unknown"
        """
        if end_date is None:
            end_date = datetime.now(UTC)
        if start_date is None:
            # Need extra history for rolling windows
            start_date = end_date - timedelta(days=365 + window_90d)

        logger.info(
            "Computing oil-real rates correlation from %s to %s",
            start_date.date(),
            end_date.date(),
        )

        # Fetch oil data (WTI)
        oil_df = await self._fetch_oil_data(start_date, end_date)

        # Fetch real rates data (DFII10)
        rates_df = await self._fetch_real_rates(start_date, end_date)

        if oil_df.empty or rates_df.empty:
            logger.warning("Insufficient data for correlation calculation")
            return pd.DataFrame()

        # Merge on timestamp
        df = pd.merge(
            oil_df,
            rates_df,
            on="timestamp",
            how="inner",
        )

        if len(df) < window_30d:
            logger.warning(
                "Only %d aligned observations, need at least %d",
                len(df),
                window_30d,
            )
            return pd.DataFrame()

        # Calculate returns (correlation should be on returns, not levels)
        # Oil: use percentage returns
        df["oil_ret"] = df["oil_price"].pct_change()
        # Rates: use first difference (rates are already a rate, not a level)
        df["rates_diff"] = df["real_10y"].diff()

        # Drop NaN from returns calculation
        df = df.dropna(subset=["oil_ret", "rates_diff"])

        # Rolling correlations
        df["corr_30d"] = (
            df["oil_ret"]
            .rolling(window=window_30d, min_periods=int(window_30d * 0.5))
            .corr(df["rates_diff"])
        )

        df["corr_90d"] = (
            df["oil_ret"]
            .rolling(window=window_90d, min_periods=int(window_90d * 0.5))
            .corr(df["rates_diff"])
        )

        # EWMA correlation
        df["corr_ewma"] = self._calculate_ewma_correlation(df["oil_ret"], df["rates_diff"])

        # Classify regime based on 30-day correlation
        df["regime"] = df["corr_30d"].apply(self._classify_regime)

        logger.info(
            "Computed correlation for %d observations. Latest regime: %s",
            len(df),
            df["regime"].iloc[-1] if not df.empty else "unknown",
        )

        return df.reset_index(drop=True)

    async def get_current_state(self) -> OilRealRatesCorrelation:
        """Get current correlation state snapshot.

        Fetches recent data and returns the latest correlation metrics
        with p-values for statistical significance testing.

        Returns:
            OilRealRatesCorrelation with latest metrics.

        Raises:
            ValueError: If insufficient data to compute correlation.
        """
        df = await self.compute_correlation()

        if df.empty:
            raise ValueError("No data available for correlation calculation")

        # Get latest row with valid correlations
        df_valid = df.dropna(subset=["corr_30d", "corr_90d"])

        if df_valid.empty:
            raise ValueError("No valid correlation values computed")

        latest = df_valid.iloc[-1]

        # Calculate p-values for recent windows
        p_value_30d = self._calculate_pvalue(
            df["oil_ret"].iloc[-30:].dropna(),
            df["rates_diff"].iloc[-30:].dropna(),
        )

        p_value_90d = self._calculate_pvalue(
            df["oil_ret"].iloc[-90:].dropna(),
            df["rates_diff"].iloc[-90:].dropna(),
        )

        # Get EWMA correlation
        corr_ewma = float(latest["corr_ewma"]) if pd.notna(latest["corr_ewma"]) else 0.0

        # Parse timestamp
        timestamp = latest["timestamp"]
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime().replace(tzinfo=UTC)
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now(UTC)

        return OilRealRatesCorrelation(
            timestamp=timestamp,
            corr_30d=float(latest["corr_30d"]),
            corr_90d=float(latest["corr_90d"]),
            corr_ewma=corr_ewma,
            p_value_30d=p_value_30d,
            p_value_90d=p_value_90d,
            regime=str(latest["regime"]),
        )

    def _classify_regime(self, corr: float) -> str:
        """Classify correlation into regime.

        Args:
            corr: Correlation value.

        Returns:
            Regime classification:
            - "surge": Unusually strong negative correlation (< -0.7)
            - "normal": Expected range (-0.7 to -0.3)
            - "breakdown": Weak or positive correlation (> -0.3)
            - "unknown": NaN or invalid value
        """
        if pd.isna(corr):
            return "unknown"

        if corr < self.NORMAL_CORR_RANGE[0]:  # < -0.7
            return "surge"
        elif corr > self.NORMAL_CORR_RANGE[1]:  # > -0.3
            return "breakdown"
        else:  # -0.7 <= corr <= -0.3
            return "normal"

    async def _fetch_oil_data(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch WTI oil price data.

        Args:
            start_date: Start date.
            end_date: End date.

        Returns:
            DataFrame with timestamp and oil_price columns.
        """
        try:
            df = await self._commodity_collector.collect(
                symbols=[COMMODITY_SYMBOLS["wti"]],  # CL=F
                start_date=start_date,
                end_date=end_date,
            )

            if df.empty:
                logger.warning("No oil data returned")
                return pd.DataFrame()

            # Filter to WTI and rename
            wti_df = df[df["series_id"] == COMMODITY_SYMBOLS["wti"]].copy()
            wti_df = wti_df.rename(columns={"value": "oil_price"})
            wti_df = wti_df[["timestamp", "oil_price"]].copy()
            wti_df = wti_df.sort_values("timestamp").drop_duplicates(subset=["timestamp"])

            logger.debug("Fetched %d WTI observations", len(wti_df))
            return wti_df

        except Exception as e:
            logger.error("Failed to fetch oil data: %s", e)
            return pd.DataFrame()

    async def _fetch_real_rates(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch 10-Year TIPS yield (real rates) data.

        Args:
            start_date: Start date.
            end_date: End date.

        Returns:
            DataFrame with timestamp and real_10y columns.
        """
        try:
            df = await self._fred_collector.collect(
                symbols=["DFII10"],
                start_date=start_date,
                end_date=end_date,
            )

            if df.empty:
                logger.warning("No TIPS yield data returned")
                return pd.DataFrame()

            # Rename for clarity
            rates_df = df.rename(columns={"value": "real_10y"})
            rates_df = rates_df[["timestamp", "real_10y"]].copy()
            rates_df = rates_df.sort_values("timestamp").drop_duplicates(subset=["timestamp"])

            logger.debug("Fetched %d DFII10 observations", len(rates_df))
            return rates_df

        except Exception as e:
            logger.error("Failed to fetch real rates data: %s", e)
            return pd.DataFrame()

    def _calculate_ewma_correlation(
        self,
        x: pd.Series,
        y: pd.Series,
    ) -> pd.Series:
        """Calculate EWMA correlation between two series.

        Uses exponentially weighted covariance and standard deviations:
        corr = cov(x,y) / (std(x) * std(y))

        Args:
            x: First series (e.g., oil returns).
            y: Second series (e.g., rates diff).

        Returns:
            Series of EWMA correlations.
        """
        # Align series
        common_idx = x.index.intersection(y.index)
        x = x.loc[common_idx]
        y = y.loc[common_idx]

        # Mean-centered series
        x_mean = x.ewm(halflife=self._ewma_halflife).mean()
        y_mean = y.ewm(halflife=self._ewma_halflife).mean()

        x_centered = x - x_mean
        y_centered = y - y_mean

        # EWMA covariance and variances
        ewm_cov = (x_centered * y_centered).ewm(halflife=self._ewma_halflife).mean()
        ewm_var_x = (x_centered**2).ewm(halflife=self._ewma_halflife).mean()
        ewm_var_y = (y_centered**2).ewm(halflife=self._ewma_halflife).mean()

        # EWMA correlation = cov / (std_x * std_y)
        ewm_std_x = np.sqrt(ewm_var_x)
        ewm_std_y = np.sqrt(ewm_var_y)

        # Avoid division by zero
        denominator = ewm_std_x * ewm_std_y
        correlation = ewm_cov / denominator.replace(0, np.nan)

        return correlation

    def _calculate_pvalue(
        self,
        x: pd.Series,
        y: pd.Series,
    ) -> float:
        """Calculate p-value for Pearson correlation.

        Args:
            x: First series.
            y: Second series.

        Returns:
            P-value from scipy.stats.pearsonr, or 1.0 if calculation fails.
        """
        try:
            # Align series
            common_idx = x.index.intersection(y.index)
            x = x.loc[common_idx].dropna()
            y = y.loc[common_idx].dropna()

            # Re-align after dropna
            common_idx = x.index.intersection(y.index)
            x = x.loc[common_idx]
            y = y.loc[common_idx]

            if len(x) < 3:
                return 1.0

            result = stats.pearsonr(x, y)
            return float(result.pvalue)

        except (ValueError, FloatingPointError, TypeError) as e:
            logger.debug("P-value calculation failed: %s", e)
            return 1.0

    def __repr__(self) -> str:
        """Return string representation."""
        return f"OilRealRatesAnalyzer(ewma_halflife={self._ewma_halflife})"
