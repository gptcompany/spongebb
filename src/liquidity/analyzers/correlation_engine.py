"""Correlation Engine for analyzing asset-liquidity relationships.

Computes rolling and EWMA correlations between asset returns and liquidity metrics
to identify which assets are most sensitive to liquidity conditions.

Key features:
- Rolling correlations (30d, 90d windows)
- EWMA correlations (exponentially weighted, configurable halflife)
- P-value calculation for statistical significance
- Multi-asset correlation matrices

Anti-patterns avoided:
- DON'T use deprecated pandas.rolling_corr() - use Series.rolling().corr()
- DON'T correlate raw prices - use pct_change() for returns
- DON'T ignore timezone alignment - always handle tz-aware timestamps
"""

import contextlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from scipy import stats

from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)


# Default assets to track for liquidity correlation
DEFAULT_ASSETS = ["BTC-USD", "^GSPC", "GC=F", "TLT", "DX-Y.NYB", "HG=F", "HYG"]
ASSET_NAMES = {
    "BTC-USD": "BTC",
    "^GSPC": "SPX",
    "GC=F": "GOLD",
    "TLT": "TLT",
    "DX-Y.NYB": "DXY",
    "HG=F": "COPPER",
    "HYG": "HYG",
}


@dataclass
class CorrelationResult:
    """Result of a single asset-liquidity correlation calculation.

    Attributes:
        timestamp: Timestamp of the calculation.
        asset: Asset symbol (e.g., "BTC", "SPX").
        liquidity_metric: Name of the liquidity metric used.
        corr_30d: 30-day rolling correlation.
        corr_90d: 90-day rolling correlation.
        corr_ewma: EWMA correlation (exponentially weighted).
        p_value_30d: P-value for 30-day correlation.
        p_value_90d: P-value for 90-day correlation.
        sample_size: Number of observations used.
    """

    timestamp: datetime
    asset: str
    liquidity_metric: str
    corr_30d: float | None
    corr_90d: float | None
    corr_ewma: float | None
    p_value_30d: float | None
    p_value_90d: float | None
    sample_size: int


@dataclass
class CorrelationMatrix:
    """Correlation matrix for multiple assets.

    Attributes:
        timestamp: Timestamp of the calculation.
        assets: List of asset names.
        correlations: DataFrame with pairwise correlations.
        p_values: DataFrame with pairwise p-values.
    """

    timestamp: datetime
    assets: list[str] = field(default_factory=list)
    correlations: pd.DataFrame = field(default_factory=pd.DataFrame)
    p_values: pd.DataFrame = field(default_factory=pd.DataFrame)


class CorrelationEngine:
    """Engine for computing asset-liquidity correlations.

    Analyzes the relationship between asset returns and liquidity metrics
    using rolling and EWMA correlations. Helps identify which assets are
    most sensitive to liquidity conditions.

    Key methods:
    - calculate_correlations(): Full correlation analysis for all assets
    - calculate_single_correlation(): Correlation for one asset pair
    - calculate_correlation_matrix(): Cross-asset correlation matrix

    Example:
        engine = CorrelationEngine()
        # Calculate correlations between asset returns and liquidity
        results = engine.calculate_correlations(asset_returns, liquidity_returns)
        # Get correlation matrix
        matrix = engine.calculate_correlation_matrix(asset_returns)
    """

    # Default assets to track
    ASSETS = ["BTC", "SPX", "GOLD", "TLT", "DXY", "COPPER", "HYG"]

    # Yahoo Finance symbols for assets
    YAHOO_SYMBOLS = {
        "BTC": "BTC-USD",
        "SPX": "^GSPC",
        "GOLD": "GC=F",
        "TLT": "TLT",
        "DXY": "DX-Y.NYB",
        "COPPER": "HG=F",
        "HYG": "HYG",
    }

    # Rolling window sizes in days
    WINDOWS = [30, 90]

    # Default EWMA halflife in days
    DEFAULT_EWMA_HALFLIFE = 21

    def __init__(
        self,
        settings: Settings | None = None,
        ewma_halflife: int = DEFAULT_EWMA_HALFLIFE,
    ) -> None:
        """Initialize the Correlation Engine.

        Args:
            settings: Optional settings override.
            ewma_halflife: Halflife for EWMA correlation (days). Default 21.
        """
        self._settings = settings or get_settings()
        self._ewma_halflife = ewma_halflife

    def calculate_correlations(
        self,
        asset_returns: pd.DataFrame | pd.Series,
        liquidity_returns: pd.Series,
    ) -> dict[str, pd.DataFrame]:
        """Calculate correlations between asset returns and liquidity returns.

        Computes rolling correlations (30d, 90d) and EWMA correlations for
        all assets against the provided liquidity metric.

        Args:
            asset_returns: DataFrame with asset returns (columns=assets, index=dates)
                          or Series for single asset.
            liquidity_returns: Series of liquidity metric returns.

        Returns:
            Dictionary with correlation DataFrames:
                - 'corr_30d': 30-day rolling correlations
                - 'corr_90d': 90-day rolling correlations
                - 'corr_ewma': EWMA correlations
        """
        # Convert Series to DataFrame if needed
        if isinstance(asset_returns, pd.Series):
            asset_returns = asset_returns.to_frame(name="asset")

        # Align indices
        common_idx = asset_returns.index.intersection(liquidity_returns.index)
        asset_returns = asset_returns.loc[common_idx]
        liquidity_returns = liquidity_returns.loc[common_idx]

        logger.info(
            "Calculating correlations for %d assets over %d observations",
            len(asset_returns.columns),
            len(common_idx),
        )

        results: dict[str, pd.DataFrame] = {}

        # 30-day rolling correlation
        corr_30d = {}
        for col in asset_returns.columns:
            corr_30d[col] = asset_returns[col].rolling(
                window=30, min_periods=15
            ).corr(liquidity_returns)
        results["corr_30d"] = pd.DataFrame(corr_30d)

        # 90-day rolling correlation
        corr_90d = {}
        for col in asset_returns.columns:
            corr_90d[col] = asset_returns[col].rolling(
                window=90, min_periods=45
            ).corr(liquidity_returns)
        results["corr_90d"] = pd.DataFrame(corr_90d)

        # EWMA correlation
        corr_ewma = {}
        for col in asset_returns.columns:
            corr_ewma[col] = self._calculate_ewma_correlation(
                asset_returns[col], liquidity_returns
            )
        results["corr_ewma"] = pd.DataFrame(corr_ewma)

        return results

    def calculate_single_correlation(
        self,
        asset_returns: pd.Series,
        liquidity_returns: pd.Series,
        window: int = 30,
    ) -> CorrelationResult:
        """Calculate correlation for a single asset-liquidity pair.

        Args:
            asset_returns: Series of asset returns.
            liquidity_returns: Series of liquidity returns.
            window: Rolling window size (default 30).

        Returns:
            CorrelationResult with all correlation metrics.
        """
        # Align series
        common_idx = asset_returns.index.intersection(liquidity_returns.index)
        asset_ret = asset_returns.loc[common_idx].dropna()
        liq_ret = liquidity_returns.loc[common_idx].dropna()

        # Re-align after dropna
        common_idx = asset_ret.index.intersection(liq_ret.index)
        asset_ret = asset_ret.loc[common_idx]
        liq_ret = liq_ret.loc[common_idx]

        sample_size = len(common_idx)

        if sample_size < window // 2:
            logger.warning(
                "Insufficient data for correlation: %d observations (need %d)",
                sample_size,
                window // 2,
            )
            return CorrelationResult(
                timestamp=datetime.now(UTC),
                asset=str(asset_returns.name) if asset_returns.name else "unknown",
                liquidity_metric="liquidity",
                corr_30d=None,
                corr_90d=None,
                corr_ewma=None,
                p_value_30d=None,
                p_value_90d=None,
                sample_size=sample_size,
            )

        # Calculate rolling correlations
        min_periods_30 = min(15, sample_size)
        min_periods_90 = min(45, sample_size)

        corr_30d_series = asset_ret.rolling(
            window=30, min_periods=min_periods_30
        ).corr(liq_ret)
        corr_90d_series = asset_ret.rolling(
            window=90, min_periods=min_periods_90
        ).corr(liq_ret)
        corr_ewma_series = self._calculate_ewma_correlation(asset_ret, liq_ret)

        # Get latest values
        corr_30d = corr_30d_series.iloc[-1] if not corr_30d_series.empty else None
        corr_90d = corr_90d_series.iloc[-1] if not corr_90d_series.empty else None
        corr_ewma = corr_ewma_series.iloc[-1] if not corr_ewma_series.empty else None

        # Handle NaN - check scalar values
        corr_30d_val: float | None = None
        corr_90d_val: float | None = None
        corr_ewma_val: float | None = None

        if corr_30d is not None and not (isinstance(corr_30d, float) and np.isnan(corr_30d)):
            with contextlib.suppress(TypeError, ValueError):
                corr_30d_val = float(corr_30d)

        if corr_90d is not None and not (isinstance(corr_90d, float) and np.isnan(corr_90d)):
            with contextlib.suppress(TypeError, ValueError):
                corr_90d_val = float(corr_90d)

        if corr_ewma is not None and not (isinstance(corr_ewma, float) and np.isnan(corr_ewma)):
            with contextlib.suppress(TypeError, ValueError):
                corr_ewma_val = float(corr_ewma)

        # Calculate p-values using scipy.stats.pearsonr on recent data
        p_value_30d_val: float | None = None
        p_value_90d_val: float | None = None

        if sample_size >= 30:
            recent_30 = slice(-30, None)
            with contextlib.suppress(ValueError, FloatingPointError, TypeError):
                pearson_result = stats.pearsonr(
                    asset_ret.iloc[recent_30], liq_ret.iloc[recent_30]
                )
                # pearsonr returns (statistic, pvalue) tuple
                p_value_30d_val = float(pearson_result[1])  # type: ignore[arg-type]

        if sample_size >= 90:
            recent_90 = slice(-90, None)
            with contextlib.suppress(ValueError, FloatingPointError, TypeError):
                pearson_result = stats.pearsonr(
                    asset_ret.iloc[recent_90], liq_ret.iloc[recent_90]
                )
                # pearsonr returns (statistic, pvalue) tuple
                p_value_90d_val = float(pearson_result[1])  # type: ignore[arg-type]

        timestamp = (
            common_idx[-1].to_pydatetime().replace(tzinfo=UTC)
            if hasattr(common_idx[-1], "to_pydatetime")
            else datetime.now(UTC)
        )

        return CorrelationResult(
            timestamp=timestamp,
            asset=str(asset_returns.name) if asset_returns.name else "unknown",
            liquidity_metric="liquidity",
            corr_30d=corr_30d_val,
            corr_90d=corr_90d_val,
            corr_ewma=corr_ewma_val,
            p_value_30d=p_value_30d_val,
            p_value_90d=p_value_90d_val,
            sample_size=sample_size,
        )

    def calculate_correlation_matrix(
        self,
        returns: pd.DataFrame,
    ) -> CorrelationMatrix:
        """Calculate correlation matrix for multiple assets.

        Computes pairwise correlations and p-values for all assets.

        Args:
            returns: DataFrame with asset returns (columns=assets, index=dates).

        Returns:
            CorrelationMatrix with correlations and p-values.
        """
        returns = returns.dropna()
        assets: list[str] = [str(c) for c in returns.columns]
        n = len(assets)

        # Initialize matrices
        corr_matrix = np.eye(n)
        p_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                try:
                    # Get aligned data
                    x = returns.iloc[:, i].dropna()
                    y = returns.iloc[:, j].dropna()
                    common = x.index.intersection(y.index)
                    x = x.loc[common]
                    y = y.loc[common]

                    if len(common) >= 3:
                        pearson_result = stats.pearsonr(x, y)
                        # pearsonr returns (statistic, pvalue) tuple
                        corr_matrix[i, j] = float(pearson_result[0])  # type: ignore[arg-type]
                        corr_matrix[j, i] = float(pearson_result[0])  # type: ignore[arg-type]
                        p_matrix[i, j] = float(pearson_result[1])  # type: ignore[arg-type]
                        p_matrix[j, i] = float(pearson_result[1])  # type: ignore[arg-type]
                except (ValueError, FloatingPointError):
                    # Keep as 0 if calculation fails
                    pass

        correlations = pd.DataFrame(corr_matrix, index=pd.Index(assets), columns=pd.Index(assets))
        p_values = pd.DataFrame(p_matrix, index=pd.Index(assets), columns=pd.Index(assets))

        return CorrelationMatrix(
            timestamp=datetime.now(UTC),
            assets=assets,
            correlations=correlations,
            p_values=p_values,
        )

    async def _fetch_asset_prices(
        self,
        symbols: list[str] | None = None,
        start_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch asset prices from Yahoo Finance.

        Args:
            symbols: List of asset symbols. Defaults to self.ASSETS.
            start_date: Start date for data. Defaults to 365 days ago.

        Returns:
            DataFrame with adjusted close prices (columns=assets, index=dates).
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.error("yfinance not installed. Install with: pip install yfinance")
            return pd.DataFrame()

        if symbols is None:
            symbols = list(self.YAHOO_SYMBOLS.values())

        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365)

        logger.info(
            "Fetching asset prices for %d symbols from %s",
            len(symbols),
            start_date.date(),
        )

        try:
            # Download data from Yahoo Finance
            data = yf.download(
                symbols,
                start=start_date,
                progress=False,
                auto_adjust=True,
            )

            if data.empty:
                logger.warning("No data returned from Yahoo Finance")
                return pd.DataFrame()

            # Handle multi-level columns (multiple symbols)
            if isinstance(data.columns, pd.MultiIndex):
                # Use 'Close' column for each symbol
                prices = data["Close"]
            else:
                # Single symbol - wrap in DataFrame
                prices = data[["Close"]].rename(columns={"Close": symbols[0]})

            # Rename columns to friendly names
            rename_map = {v: k for k, v in self.YAHOO_SYMBOLS.items()}
            prices = prices.rename(columns=rename_map)

            logger.info(
                "Fetched %d observations for %d assets",
                len(prices),
                len(prices.columns),
            )

            return prices

        except Exception as e:
            logger.exception("Error fetching asset prices: %s", e)
            return pd.DataFrame()

    def _calculate_returns(
        self,
        prices: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate percentage returns from prices.

        Uses pct_change() to compute daily returns. First row is dropped
        as it will be NaN.

        Args:
            prices: DataFrame with asset prices.

        Returns:
            DataFrame with percentage returns.
        """
        returns = prices.pct_change().dropna()
        return returns

    def _calculate_ewma_correlation(
        self,
        x: pd.Series,
        y: pd.Series,
    ) -> pd.Series:
        """Calculate EWMA correlation between two series.

        Uses exponentially weighted covariance and standard deviations
        to compute correlation: corr = cov(x,y) / (std(x) * std(y))

        Args:
            x: First series.
            y: Second series.

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

    def __repr__(self) -> str:
        """Return string representation of the engine."""
        return f"CorrelationEngine(ewma_halflife={self._ewma_halflife})"
