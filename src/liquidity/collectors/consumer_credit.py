"""Consumer credit and spending collector.

Wraps FREDCollector for consumer-focused series:
- Retail sales (RSAFS, RRSFS)
- Consumer sentiment (UMCSENT)
- Consumer credit (TOTALSL)
- Personal consumption (PCE)
- Weekly bank credit proxies (CCLACBW027SBOG, CLSACBW027SBOG)

These indicators complement liquidity monitoring by showing how the real economy
responds to monetary conditions.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.fred import FredCollector
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Consumer series groups
CONSUMER_SERIES: dict[str, list[str]] = {
    "spending": ["RSAFS", "RRSFS", "PCE"],
    "credit": ["TOTALSL", "CCLACBW027SBOG", "CLSACBW027SBOG"],
    "sentiment": ["UMCSENT"],
}

# All consumer series
ALL_CONSUMER_SERIES: list[str] = [
    s for group in CONSUMER_SERIES.values() for s in group
]

# Weekly high-frequency series (for more timely data)
WEEKLY_HF_SERIES: list[str] = ["CCLACBW027SBOG", "CLSACBW027SBOG"]

# Sentiment interpretation thresholds
# Historical context:
# - Peak: 111.8 (Jan 2000)
# - Trough: 50.0 (Nov 2008 GFC)
# - COVID low: 71.8 (Apr 2020)
SENTIMENT_THRESHOLDS = {
    "very_optimistic": 100.0,
    "optimistic": 80.0,
    "neutral": 60.0,
    # Below 60 = pessimistic
}

SentimentLevel = Literal["very_optimistic", "optimistic", "neutral", "pessimistic"]


class ConsumerCreditCollector(BaseCollector[pd.DataFrame]):
    """Convenience wrapper for consumer credit/spending data.

    Uses FREDCollector under the hood but provides consumer-focused
    methods and data interpretation.

    Example:
        collector = ConsumerCreditCollector()

        # Get spending data
        spending_df = await collector.collect_spending()

        # Get weekly high-frequency proxies
        weekly_df = await collector.collect_weekly_hf()

        # Interpret sentiment
        sentiment_df = await collector.collect_sentiment()
        level = collector.interpret_sentiment(75.5)  # "neutral"
    """

    CONSUMER_SERIES = CONSUMER_SERIES
    ALL_CONSUMER_SERIES = ALL_CONSUMER_SERIES
    WEEKLY_HF_SERIES = WEEKLY_HF_SERIES
    THRESHOLDS = SENTIMENT_THRESHOLDS

    def __init__(
        self,
        name: str = "consumer_credit",
        settings: Settings | None = None,
        fred_collector: FredCollector | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize consumer credit collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            fred_collector: Optional FredCollector instance for dependency injection.
                If not provided, a new one will be created.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()
        self._fred = fred_collector or FredCollector(
            name="consumer_credit_fred", settings=self._settings
        )

    async def collect(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect all consumer credit/spending data.

        Args:
            start_date: Start date for data fetch. Defaults to 1 year ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fred.collect(
                symbols=self.ALL_CONSUMER_SERIES,
                start_date=start_date,
                end_date=end_date,
            )

        try:
            df = await self.fetch_with_retry(_fetch, breaker_name="consumer_credit")
            logger.info("Collected %d consumer data points", len(df))
            return df
        except Exception as e:
            logger.error("Consumer credit fetch failed: %s", e)
            raise CollectorFetchError(f"Consumer credit data fetch failed: {e}") from e

    async def collect_spending(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect consumer spending data.

        Series:
        - RSAFS: Retail Sales Total (millions USD, SA)
        - RRSFS: Retail Sales ex Autos (millions USD, SA)
        - PCE: Personal Consumption Expenditures (billions USD, SAAR)

        Args:
            start_date: Start date for data fetch. Defaults to 1 year ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with spending series.

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fred.collect(
                symbols=self.CONSUMER_SERIES["spending"],
                start_date=start_date,
                end_date=end_date,
            )

        try:
            df = await self.fetch_with_retry(_fetch, breaker_name="consumer_spending")
            logger.info("Collected %d spending data points", len(df))
            return df
        except Exception as e:
            logger.error("Spending data fetch failed: %s", e)
            raise CollectorFetchError(f"Spending data fetch failed: {e}") from e

    async def collect_credit(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect consumer credit data.

        Series:
        - TOTALSL: Total Consumer Credit (monthly, billions USD)
        - CCLACBW027SBOG: Credit Card Loans at Banks (weekly, millions USD)
        - CLSACBW027SBOG: Consumer Loans at Banks (weekly, millions USD)

        Args:
            start_date: Start date for data fetch. Defaults to 1 year ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with credit series.

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fred.collect(
                symbols=self.CONSUMER_SERIES["credit"],
                start_date=start_date,
                end_date=end_date,
            )

        try:
            df = await self.fetch_with_retry(_fetch, breaker_name="consumer_credit_data")
            logger.info("Collected %d credit data points", len(df))
            return df
        except Exception as e:
            logger.error("Credit data fetch failed: %s", e)
            raise CollectorFetchError(f"Credit data fetch failed: {e}") from e

    async def collect_sentiment(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect consumer sentiment data.

        Series:
        - UMCSENT: University of Michigan Consumer Sentiment Index

        Historical context:
        - Peak: 111.8 (Jan 2000)
        - Trough: 50.0 (Nov 2008 GFC)
        - COVID low: 71.8 (Apr 2020)
        - Typical range: 70-100

        Args:
            start_date: Start date for data fetch. Defaults to 1 year ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with sentiment series.

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fred.collect(
                symbols=self.CONSUMER_SERIES["sentiment"],
                start_date=start_date,
                end_date=end_date,
            )

        try:
            df = await self.fetch_with_retry(_fetch, breaker_name="consumer_sentiment")
            logger.info("Collected %d sentiment data points", len(df))
            return df
        except Exception as e:
            logger.error("Sentiment data fetch failed: %s", e)
            raise CollectorFetchError(f"Sentiment data fetch failed: {e}") from e

    async def collect_weekly_hf(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect weekly high-frequency credit proxies.

        Provides more timely data than monthly series. Updated weekly by the Fed.

        Series:
        - CCLACBW027SBOG: Credit Card Loans at Commercial Banks
        - CLSACBW027SBOG: Consumer Loans at Commercial Banks

        Args:
            start_date: Start date for data fetch. Defaults to 90 days ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with weekly bank credit data.

        Raises:
            CollectorFetchError: If data fetch fails after retries.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await self._fred.collect(
                symbols=self.WEEKLY_HF_SERIES,
                start_date=start_date,
                end_date=end_date,
            )

        try:
            df = await self.fetch_with_retry(_fetch, breaker_name="consumer_weekly_hf")
            logger.info("Collected %d weekly HF data points", len(df))
            return df
        except Exception as e:
            logger.error("Weekly HF data fetch failed: %s", e)
            raise CollectorFetchError(f"Weekly HF data fetch failed: {e}") from e

    @staticmethod
    def calculate_yoy_growth(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate year-over-year growth rates.

        For monthly series, compares to 12 months ago.
        For weekly series, compares to 52 weeks ago.

        Args:
            df: DataFrame with timestamp, series_id, value columns.

        Returns:
            DataFrame with YoY growth rates added as 'yoy_growth' column (in %).
        """
        if df.empty:
            return df.assign(yoy_growth=pd.Series(dtype=float))

        result_rows = []

        for series_id in df["series_id"].unique():
            series_df = df[df["series_id"] == series_id].copy()
            series_df = series_df.sort_values("timestamp")

            # Determine frequency: weekly series have 'W027SBOG' suffix
            is_weekly = "W027SBOG" in series_id
            shift_periods = 52 if is_weekly else 12

            # Calculate YoY growth
            series_df["value_1y_ago"] = series_df["value"].shift(shift_periods)
            series_df["yoy_growth"] = (
                (series_df["value"] - series_df["value_1y_ago"])
                / series_df["value_1y_ago"]
                * 100
            )

            # Keep relevant columns
            cols = ["timestamp", "series_id", "source", "value", "unit", "yoy_growth"]
            available_cols = [c for c in cols if c in series_df.columns]
            result_rows.append(series_df[available_cols])

        result = pd.concat(result_rows, ignore_index=True)
        logger.debug("Calculated YoY growth for %d series", len(df["series_id"].unique()))
        return result

    @staticmethod
    def interpret_sentiment(value: float) -> SentimentLevel:
        """Interpret consumer sentiment level.

        Historical context:
        - > 100: Very optimistic (pre-bubble periods)
        - 80-100: Optimistic (normal expansion)
        - 60-80: Neutral/cautious (slowdown signals)
        - < 60: Pessimistic (recession territory)

        Args:
            value: UMCSENT index value.

        Returns:
            Interpretation string: "very_optimistic", "optimistic", "neutral", or "pessimistic"
        """
        if value > SENTIMENT_THRESHOLDS["very_optimistic"]:
            return "very_optimistic"
        elif value > SENTIMENT_THRESHOLDS["optimistic"]:
            return "optimistic"
        elif value > SENTIMENT_THRESHOLDS["neutral"]:
            return "neutral"
        else:
            return "pessimistic"

    def get_latest_sentiment_level(self, df: pd.DataFrame | None = None) -> SentimentLevel:
        """Get the latest sentiment level from data.

        Args:
            df: DataFrame with UMCSENT data. If None, returns "neutral".

        Returns:
            Current sentiment level interpretation.
        """
        if df is None or df.empty:
            logger.warning("No data provided for sentiment level")
            return "neutral"

        umcsent_df = df[df["series_id"] == "UMCSENT"]
        if umcsent_df.empty:
            logger.warning("UMCSENT not found in data")
            return "neutral"

        latest = umcsent_df.sort_values("timestamp").iloc[-1]
        value = float(latest["value"])
        level = self.interpret_sentiment(value)

        logger.info("Latest UMCSENT: %.1f -> %s", value, level)
        return level


# Register collector with the registry
registry.register("consumer_credit", ConsumerCreditCollector)
