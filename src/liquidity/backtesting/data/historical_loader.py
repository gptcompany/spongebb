"""Historical data loader with point-in-time support via ALFRED."""

from dataclasses import dataclass

import pandas as pd
from fredapi import Fred

from liquidity.config import get_settings


@dataclass
class PointInTimeData:
    """Point-in-time data snapshot."""

    series_id: str
    as_of_date: pd.Timestamp
    data: pd.Series
    publication_lag_days: int


# Publication lag mapping (days after reference period)
PUBLICATION_LAGS = {
    "WALCL": 7,  # Fed balance sheet: Thursday for prior week
    "WTREGEN": 2,  # TGA: T+1
    "RRPONTSYD": 2,  # RRP: T+1
    "ECBASSETSW": 8,  # ECB: ~1 week
    "JPNASSETS": 8,  # BoJ: ~1 week
    "TRESEGCNM052N": 35,  # PBoC proxy: ~1 month
}


class HistoricalLoader:
    """Load historical macro data with point-in-time accuracy.

    Uses ALFRED (Archival FRED) to get what was known at each point in time,
    avoiding look-ahead bias from data revisions.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize loader.

        Args:
            api_key: FRED API key. Uses LIQUIDITY_FRED_API_KEY if not provided.
        """
        self.api_key = api_key or get_settings().fred_api_key.get_secret_value()
        self._fred: Fred | None = None

    @property
    def fred(self) -> Fred:
        """Lazy-load Fred client."""
        if self._fred is None:
            if not self.api_key:
                raise ValueError("FRED API key required. Set LIQUIDITY_FRED_API_KEY.")
            self._fred = Fred(api_key=self.api_key)
        return self._fred

    def get_point_in_time(
        self,
        series_id: str,
        as_of: pd.Timestamp,
        start_date: pd.Timestamp | None = None,
    ) -> PointInTimeData:
        """Get data as it was known at a specific point in time.

        Args:
            series_id: FRED series ID (e.g., 'WALCL')
            as_of: Date to simulate (what was known then)
            start_date: Optional start date for the series

        Returns:
            PointInTimeData with the series as of that date
        """
        lag = PUBLICATION_LAGS.get(series_id, 7)

        # ALFRED call: get what was available at as_of
        data = self.fred.get_series(
            series_id,
            realtime_start=as_of.strftime("%Y-%m-%d"),
            realtime_end=as_of.strftime("%Y-%m-%d"),
            observation_start=start_date.strftime("%Y-%m-%d") if start_date else None,
        )

        return PointInTimeData(
            series_id=series_id,
            as_of_date=as_of,
            data=data,
            publication_lag_days=lag,
        )

    def get_series_with_lag(
        self,
        series_id: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pd.Series:
        """Get series with publication lag applied.

        Shifts data forward to simulate when it was actually available.

        Args:
            series_id: FRED series ID
            start_date: Start date
            end_date: End date

        Returns:
            Series shifted by publication lag
        """
        # Get raw data
        data = self.fred.get_series(
            series_id,
            observation_start=start_date.strftime("%Y-%m-%d"),
            observation_end=end_date.strftime("%Y-%m-%d"),
        )

        # Apply publication lag
        lag = PUBLICATION_LAGS.get(series_id, 7)
        lagged = data.shift(lag, freq="D")

        return lagged

    def load_liquidity_data(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pd.DataFrame:
        """Load all liquidity components with proper lags.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            DataFrame with WALCL, TGA, RRP, net_liquidity columns
        """
        walcl = self.get_series_with_lag("WALCL", start_date, end_date)
        tga = self.get_series_with_lag("WTREGEN", start_date, end_date)
        rrp = self.get_series_with_lag("RRPONTSYD", start_date, end_date)

        # Align to daily index
        daily_idx = pd.date_range(start_date, end_date, freq="B")

        df = pd.DataFrame(index=daily_idx)
        df["walcl"] = walcl.reindex(daily_idx, method="ffill")
        df["tga"] = tga.reindex(daily_idx, method="ffill")
        df["rrp"] = rrp.reindex(daily_idx, method="ffill")

        # Calculate net liquidity
        df["net_liquidity"] = df["walcl"] - df["tga"] - df["rrp"]

        return df

    def load_global_liquidity(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pd.DataFrame:
        """Load global CB balance sheets with proper lags.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            DataFrame with Fed, ECB, BoJ, PBoC, global_liquidity columns
        """
        fed = self.get_series_with_lag("WALCL", start_date, end_date)
        ecb = self.get_series_with_lag("ECBASSETSW", start_date, end_date)
        boj = self.get_series_with_lag("JPNASSETS", start_date, end_date)
        pboc = self.get_series_with_lag("TRESEGCNM052N", start_date, end_date)

        daily_idx = pd.date_range(start_date, end_date, freq="B")

        df = pd.DataFrame(index=daily_idx)
        df["fed"] = fed.reindex(daily_idx, method="ffill")
        df["ecb"] = ecb.reindex(daily_idx, method="ffill")
        df["boj"] = boj.reindex(daily_idx, method="ffill")
        df["pboc"] = pboc.reindex(daily_idx, method="ffill")

        # Global liquidity (all in USD - ECB/BoJ need FX conversion in real impl)
        df["global_liquidity"] = df["fed"] + df["ecb"] + df["boj"] + df["pboc"]

        return df
