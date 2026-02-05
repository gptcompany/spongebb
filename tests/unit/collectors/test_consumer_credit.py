"""Unit tests for consumer credit collector.

Tests use mocked FRED responses to verify:
- DataFrame structure and normalization
- Convenience method delegation
- YoY growth calculation
- Sentiment interpretation
- Error handling for empty/invalid responses
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from liquidity.collectors.consumer_credit import (
    ALL_CONSUMER_SERIES,
    CONSUMER_SERIES,
    SENTIMENT_THRESHOLDS,
    WEEKLY_HF_SERIES,
    ConsumerCreditCollector,
)


@pytest.fixture
def mock_spending_data() -> pd.DataFrame:
    """Sample FRED spending response."""
    return pd.DataFrame([
        {
            "timestamp": pd.Timestamp("2026-01-01"),
            "series_id": "RSAFS",
            "source": "fred",
            "value": 700000.0,
            "unit": "millions_usd",
        },
        {
            "timestamp": pd.Timestamp("2026-01-01"),
            "series_id": "RRSFS",
            "source": "fred",
            "value": 550000.0,
            "unit": "millions_usd",
        },
        {
            "timestamp": pd.Timestamp("2026-01-01"),
            "series_id": "PCE",
            "source": "fred",
            "value": 18500.0,
            "unit": "billions_usd_saar",
        },
    ])


@pytest.fixture
def mock_credit_data() -> pd.DataFrame:
    """Sample FRED credit response."""
    return pd.DataFrame([
        {
            "timestamp": pd.Timestamp("2026-01-01"),
            "series_id": "TOTALSL",
            "source": "fred",
            "value": 5000.0,
            "unit": "billions_usd",
        },
        {
            "timestamp": pd.Timestamp("2026-01-01"),
            "series_id": "CCLACBW027SBOG",
            "source": "fred",
            "value": 1200000.0,
            "unit": "millions_usd",
        },
        {
            "timestamp": pd.Timestamp("2026-01-01"),
            "series_id": "CLSACBW027SBOG",
            "source": "fred",
            "value": 1800000.0,
            "unit": "millions_usd",
        },
    ])


@pytest.fixture
def mock_sentiment_data() -> pd.DataFrame:
    """Sample FRED sentiment response."""
    return pd.DataFrame([
        {
            "timestamp": pd.Timestamp("2025-12-01"),
            "series_id": "UMCSENT",
            "source": "fred",
            "value": 72.5,
            "unit": "index",
        },
        {
            "timestamp": pd.Timestamp("2026-01-01"),
            "series_id": "UMCSENT",
            "source": "fred",
            "value": 75.5,
            "unit": "index",
        },
    ])


@pytest.fixture
def mock_all_data(
    mock_spending_data: pd.DataFrame,
    mock_credit_data: pd.DataFrame,
    mock_sentiment_data: pd.DataFrame,
) -> pd.DataFrame:
    """Combined mock data for all consumer series."""
    return pd.concat(
        [mock_spending_data, mock_credit_data, mock_sentiment_data],
        ignore_index=True,
    )


class TestConsumerCreditCollectorInit:
    """Tests for ConsumerCreditCollector initialization."""

    @pytest.mark.unit
    def test_default_initialization(self) -> None:
        """Test default collector initialization."""
        collector = ConsumerCreditCollector()

        assert collector.name == "consumer_credit"
        assert collector._fred is not None

    @pytest.mark.unit
    def test_custom_name(self) -> None:
        """Test collector with custom name."""
        collector = ConsumerCreditCollector(name="custom_consumer")

        assert collector.name == "custom_consumer"

    @pytest.mark.unit
    def test_injected_fred_collector(self) -> None:
        """Test dependency injection of FREDCollector."""
        mock_fred = MagicMock()
        collector = ConsumerCreditCollector(fred_collector=mock_fred)

        assert collector._fred is mock_fred


class TestCollectMethods:
    """Tests for collection methods."""

    @pytest.mark.unit
    async def test_collect_all_calls_fred(self, mock_all_data: pd.DataFrame) -> None:
        """Test collect() delegates to FRED collector."""
        mock_fred = MagicMock()
        mock_fred.collect = AsyncMock(return_value=mock_all_data)

        collector = ConsumerCreditCollector(fred_collector=mock_fred)
        result = await collector.collect()

        mock_fred.collect.assert_called_once()
        call_args = mock_fred.collect.call_args
        assert set(call_args.kwargs["symbols"]) == set(ALL_CONSUMER_SERIES)
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.unit
    async def test_collect_spending_calls_fred(
        self, mock_spending_data: pd.DataFrame
    ) -> None:
        """Test spending collection delegates to FRED."""
        mock_fred = MagicMock()
        mock_fred.collect = AsyncMock(return_value=mock_spending_data)

        collector = ConsumerCreditCollector(fred_collector=mock_fred)
        await collector.collect_spending()

        mock_fred.collect.assert_called_once()
        call_args = mock_fred.collect.call_args
        assert set(call_args.kwargs["symbols"]) == set(CONSUMER_SERIES["spending"])
        assert "RSAFS" in call_args.kwargs["symbols"]
        assert "PCE" in call_args.kwargs["symbols"]

    @pytest.mark.unit
    async def test_collect_credit_calls_fred(
        self, mock_credit_data: pd.DataFrame
    ) -> None:
        """Test credit collection delegates to FRED."""
        mock_fred = MagicMock()
        mock_fred.collect = AsyncMock(return_value=mock_credit_data)

        collector = ConsumerCreditCollector(fred_collector=mock_fred)
        await collector.collect_credit()

        mock_fred.collect.assert_called_once()
        call_args = mock_fred.collect.call_args
        assert set(call_args.kwargs["symbols"]) == set(CONSUMER_SERIES["credit"])
        assert "TOTALSL" in call_args.kwargs["symbols"]

    @pytest.mark.unit
    async def test_collect_sentiment_calls_fred(
        self, mock_sentiment_data: pd.DataFrame
    ) -> None:
        """Test sentiment collection delegates to FRED."""
        mock_fred = MagicMock()
        mock_fred.collect = AsyncMock(return_value=mock_sentiment_data)

        collector = ConsumerCreditCollector(fred_collector=mock_fred)
        await collector.collect_sentiment()

        mock_fred.collect.assert_called_once()
        call_args = mock_fred.collect.call_args
        assert call_args.kwargs["symbols"] == ["UMCSENT"]

    @pytest.mark.unit
    async def test_collect_weekly_hf_calls_fred(
        self, mock_credit_data: pd.DataFrame
    ) -> None:
        """Test weekly HF collection delegates to FRED."""
        mock_fred = MagicMock()
        mock_fred.collect = AsyncMock(return_value=mock_credit_data)

        collector = ConsumerCreditCollector(fred_collector=mock_fred)
        await collector.collect_weekly_hf()

        mock_fred.collect.assert_called_once()
        call_args = mock_fred.collect.call_args
        assert set(call_args.kwargs["symbols"]) == set(WEEKLY_HF_SERIES)

    @pytest.mark.unit
    async def test_collect_with_date_range(
        self, mock_all_data: pd.DataFrame
    ) -> None:
        """Test collection with custom date range."""
        mock_fred = MagicMock()
        mock_fred.collect = AsyncMock(return_value=mock_all_data)

        collector = ConsumerCreditCollector(fred_collector=mock_fred)

        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 1, tzinfo=UTC)

        await collector.collect(start_date=start, end_date=end)

        call_args = mock_fred.collect.call_args
        assert call_args.kwargs["start_date"] == start
        assert call_args.kwargs["end_date"] == end


class TestYoYGrowthCalculation:
    """Tests for YoY growth calculation."""

    @pytest.mark.unit
    def test_calculate_yoy_growth_basic(self) -> None:
        """Test basic YoY growth calculation."""
        # Monthly data: 12-month shift
        df = pd.DataFrame([
            {"timestamp": pd.Timestamp("2025-01-01"), "series_id": "RSAFS", "value": 100.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-02-01"), "series_id": "RSAFS", "value": 102.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-03-01"), "series_id": "RSAFS", "value": 104.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-04-01"), "series_id": "RSAFS", "value": 106.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-05-01"), "series_id": "RSAFS", "value": 108.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-06-01"), "series_id": "RSAFS", "value": 110.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-07-01"), "series_id": "RSAFS", "value": 112.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-08-01"), "series_id": "RSAFS", "value": 114.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-09-01"), "series_id": "RSAFS", "value": 116.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-10-01"), "series_id": "RSAFS", "value": 118.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-11-01"), "series_id": "RSAFS", "value": 120.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2025-12-01"), "series_id": "RSAFS", "value": 122.0, "source": "fred", "unit": "millions_usd"},
            {"timestamp": pd.Timestamp("2026-01-01"), "series_id": "RSAFS", "value": 110.0, "source": "fred", "unit": "millions_usd"},
        ])

        result = ConsumerCreditCollector.calculate_yoy_growth(df)

        assert "yoy_growth" in result.columns

        # First 12 rows should have NaN YoY (no prior year data)
        assert pd.isna(result.iloc[0]["yoy_growth"])

        # 13th row (2026-01) should have YoY growth: (110 - 100) / 100 * 100 = 10%
        yoy_jan_2026 = result.iloc[12]["yoy_growth"]
        assert abs(yoy_jan_2026 - 10.0) < 0.01

    @pytest.mark.unit
    def test_calculate_yoy_growth_empty_df(self) -> None:
        """Test YoY calculation with empty DataFrame."""
        df = pd.DataFrame(columns=["timestamp", "series_id", "value"])
        result = ConsumerCreditCollector.calculate_yoy_growth(df)

        assert isinstance(result, pd.DataFrame)
        assert "yoy_growth" in result.columns

    @pytest.mark.unit
    def test_calculate_yoy_growth_multiple_series(self) -> None:
        """Test YoY calculation with multiple series."""
        # Create 13 months of data for two series
        months = pd.date_range("2025-01-01", periods=13, freq="MS")
        df = pd.DataFrame([
            {"timestamp": m, "series_id": "RSAFS", "value": 100.0 + i, "source": "fred", "unit": "millions_usd"}
            for i, m in enumerate(months)
        ] + [
            {"timestamp": m, "series_id": "PCE", "value": 18000.0 + i * 100, "source": "fred", "unit": "billions_usd_saar"}
            for i, m in enumerate(months)
        ])

        result = ConsumerCreditCollector.calculate_yoy_growth(df)

        # Should have data for both series
        assert len(result["series_id"].unique()) == 2
        assert "RSAFS" in result["series_id"].values
        assert "PCE" in result["series_id"].values


class TestSentimentInterpretation:
    """Tests for sentiment interpretation."""

    @pytest.mark.unit
    def test_interpret_sentiment_very_optimistic(self) -> None:
        """Test very optimistic sentiment."""
        assert ConsumerCreditCollector.interpret_sentiment(105.0) == "very_optimistic"
        assert ConsumerCreditCollector.interpret_sentiment(111.8) == "very_optimistic"

    @pytest.mark.unit
    def test_interpret_sentiment_optimistic(self) -> None:
        """Test optimistic sentiment."""
        assert ConsumerCreditCollector.interpret_sentiment(85.0) == "optimistic"
        assert ConsumerCreditCollector.interpret_sentiment(99.0) == "optimistic"
        assert ConsumerCreditCollector.interpret_sentiment(80.1) == "optimistic"

    @pytest.mark.unit
    def test_interpret_sentiment_neutral(self) -> None:
        """Test neutral sentiment."""
        assert ConsumerCreditCollector.interpret_sentiment(70.0) == "neutral"
        assert ConsumerCreditCollector.interpret_sentiment(75.0) == "neutral"
        assert ConsumerCreditCollector.interpret_sentiment(60.1) == "neutral"

    @pytest.mark.unit
    def test_interpret_sentiment_pessimistic(self) -> None:
        """Test pessimistic sentiment (recession territory)."""
        assert ConsumerCreditCollector.interpret_sentiment(55.0) == "pessimistic"
        assert ConsumerCreditCollector.interpret_sentiment(50.0) == "pessimistic"  # GFC trough
        assert ConsumerCreditCollector.interpret_sentiment(60.0) == "pessimistic"

    @pytest.mark.unit
    def test_interpret_sentiment_boundary_values(self) -> None:
        """Test boundary values for sentiment thresholds."""
        # Exactly at thresholds
        assert ConsumerCreditCollector.interpret_sentiment(100.0) == "optimistic"  # <= 100
        assert ConsumerCreditCollector.interpret_sentiment(80.0) == "neutral"  # <= 80
        assert ConsumerCreditCollector.interpret_sentiment(60.0) == "pessimistic"  # <= 60

    @pytest.mark.unit
    async def test_get_latest_sentiment_level(
        self, mock_sentiment_data: pd.DataFrame
    ) -> None:
        """Test getting latest sentiment level from data."""
        collector = ConsumerCreditCollector()
        level = collector.get_latest_sentiment_level(mock_sentiment_data)

        # Latest value is 75.5 -> neutral
        assert level == "neutral"

    @pytest.mark.unit
    async def test_get_latest_sentiment_level_empty(self) -> None:
        """Test getting sentiment level from empty data."""
        collector = ConsumerCreditCollector()
        level = collector.get_latest_sentiment_level(pd.DataFrame())

        assert level == "neutral"

    @pytest.mark.unit
    async def test_get_latest_sentiment_level_missing_umcsent(self) -> None:
        """Test getting sentiment level when UMCSENT is missing."""
        collector = ConsumerCreditCollector()
        df = pd.DataFrame([
            {"timestamp": pd.Timestamp("2026-01-01"), "series_id": "RSAFS", "value": 100.0}
        ])
        level = collector.get_latest_sentiment_level(df)

        assert level == "neutral"


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.unit
    async def test_collect_handles_fred_error(self) -> None:
        """Test collect handles FRED errors gracefully."""
        from liquidity.collectors.base import CollectorFetchError

        mock_fred = MagicMock()
        mock_fred.collect = AsyncMock(side_effect=Exception("FRED API error"))

        collector = ConsumerCreditCollector(fred_collector=mock_fred)

        with pytest.raises(CollectorFetchError, match="Consumer credit data fetch failed"):
            await collector.collect()

    @pytest.mark.unit
    async def test_collect_spending_handles_error(self) -> None:
        """Test collect_spending handles errors."""
        from liquidity.collectors.base import CollectorFetchError

        mock_fred = MagicMock()
        mock_fred.collect = AsyncMock(side_effect=Exception("Network error"))

        collector = ConsumerCreditCollector(fred_collector=mock_fred)

        with pytest.raises(CollectorFetchError, match="Spending data fetch failed"):
            await collector.collect_spending()


class TestRegistration:
    """Tests for collector registration."""

    @pytest.mark.unit
    async def test_collector_registered(self) -> None:
        """Test that consumer_credit collector is registered."""
        from liquidity.collectors import registry

        assert "consumer_credit" in registry.list_collectors()
        collector_cls = registry.get("consumer_credit")
        assert collector_cls is ConsumerCreditCollector

    @pytest.mark.unit
    def test_series_constants(self) -> None:
        """Test series constants are properly defined."""
        # Check all expected series are present
        assert "RSAFS" in CONSUMER_SERIES["spending"]
        assert "RRSFS" in CONSUMER_SERIES["spending"]
        assert "PCE" in CONSUMER_SERIES["spending"]

        assert "TOTALSL" in CONSUMER_SERIES["credit"]
        assert "CCLACBW027SBOG" in CONSUMER_SERIES["credit"]
        assert "CLSACBW027SBOG" in CONSUMER_SERIES["credit"]

        assert "UMCSENT" in CONSUMER_SERIES["sentiment"]

        # Check ALL_CONSUMER_SERIES is complete
        expected_count = sum(len(v) for v in CONSUMER_SERIES.values())
        assert len(ALL_CONSUMER_SERIES) == expected_count

    @pytest.mark.unit
    def test_threshold_constants(self) -> None:
        """Test sentiment threshold constants."""
        assert SENTIMENT_THRESHOLDS["very_optimistic"] == 100.0
        assert SENTIMENT_THRESHOLDS["optimistic"] == 80.0
        assert SENTIMENT_THRESHOLDS["neutral"] == 60.0
