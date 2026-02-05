"""Unit tests for TGA Daily collector.

Tests use mocked HTTP responses to verify collector behavior without
requiring network access.

Run with: uv run pytest tests/unit/collectors/test_tga_daily.py -v
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from liquidity.collectors.tga_daily import (
    ENDPOINT,
    FISCALDATA_BASE_URL,
    TGA_ACCOUNT_TYPE,
    TGADailyCollector,
)


@pytest.fixture
def mock_response_data() -> dict:
    """Sample FiscalData API response."""
    return {
        "data": [
            {
                "record_date": "2026-02-04",
                "account_type": "Treasury General Account (TGA) Closing Balance",
                "open_today_bal": "845123",
                "open_month_bal": "714000",
            },
            {
                "record_date": "2026-02-03",
                "account_type": "Treasury General Account (TGA) Closing Balance",
                "open_today_bal": "832541",
                "open_month_bal": "714000",
            },
            {
                "record_date": "2026-01-31",
                "account_type": "Treasury General Account (TGA) Closing Balance",
                "open_today_bal": "714000",
                "open_month_bal": "714000",
            },
        ],
        "meta": {
            "count": 3,
            "total-count": 3,
            "total-pages": 1,
        },
    }


@pytest.fixture
def empty_response_data() -> dict:
    """Empty FiscalData API response."""
    return {
        "data": [],
        "meta": {
            "count": 0,
            "total-count": 0,
            "total-pages": 0,
        },
    }


@pytest.fixture
def collector() -> TGADailyCollector:
    """Create a TGA Daily collector instance."""
    return TGADailyCollector()


class TestTGADailyCollectorInit:
    """Tests for TGADailyCollector initialization."""

    def test_default_name(self) -> None:
        """Test default collector name."""
        collector = TGADailyCollector()
        assert collector.name == "tga_daily"

    def test_custom_name(self) -> None:
        """Test custom collector name."""
        collector = TGADailyCollector(name="custom_tga")
        assert collector.name == "custom_tga"

    def test_client_initially_none(self) -> None:
        """Test HTTP client is None on init."""
        collector = TGADailyCollector()
        assert collector._client is None


class TestTGADailyCollectorCollect:
    """Tests for TGADailyCollector.collect() method."""

    @pytest.mark.asyncio
    async def test_collect_returns_dataframe(
        self, collector: TGADailyCollector, mock_response_data: dict
    ) -> None:
        """Test that collect returns properly formatted DataFrame."""
        with patch.object(collector, "_fetch_tga") as mock_fetch:
            mock_df = pd.DataFrame(
                [
                    {
                        "timestamp": pd.Timestamp("2026-02-04"),
                        "series_id": "TGA_DAILY",
                        "source": "fiscaldata",
                        "value": 845123.0,
                        "unit": "millions_usd",
                    },
                    {
                        "timestamp": pd.Timestamp("2026-02-03"),
                        "series_id": "TGA_DAILY",
                        "source": "fiscaldata",
                        "value": 832541.0,
                        "unit": "millions_usd",
                    },
                ]
            )
            mock_fetch.return_value = mock_df

            result = await collector.collect()

            assert isinstance(result, pd.DataFrame)
            assert "timestamp" in result.columns
            assert "series_id" in result.columns
            assert "source" in result.columns
            assert "value" in result.columns
            assert "unit" in result.columns
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_collect_handles_empty_response(self, collector: TGADailyCollector) -> None:
        """Test handling of empty API response."""
        with patch.object(collector, "_fetch_tga") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

            result = await collector.collect()

            assert len(result) == 0
            assert list(result.columns) == ["timestamp", "series_id", "source", "value", "unit"]

    @pytest.mark.asyncio
    async def test_collect_default_date_range(self, collector: TGADailyCollector) -> None:
        """Test that collect uses 90-day default date range."""
        with patch.object(collector, "_fetch_tga") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

            await collector.collect()

            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args[0]
            start_date, end_date = call_args[0], call_args[1]

            # Verify date range is approximately 90 days
            date_diff = (end_date - start_date).days
            assert 89 <= date_diff <= 91

    @pytest.mark.asyncio
    async def test_collect_custom_date_range(self, collector: TGADailyCollector) -> None:
        """Test collect with custom date range."""
        with patch.object(collector, "_fetch_tga") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

            start = datetime(2026, 1, 1, tzinfo=UTC)
            end = datetime(2026, 1, 31, tzinfo=UTC)

            await collector.collect(start_date=start, end_date=end)

            mock_fetch.assert_called_once_with(start, end)


class TestTGADailyCollectorFetchTGA:
    """Tests for TGADailyCollector._fetch_tga() method."""

    @pytest.mark.asyncio
    async def test_fetch_tga_parses_response(
        self, collector: TGADailyCollector, mock_response_data: dict
    ) -> None:
        """Test that _fetch_tga correctly parses API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(collector, "_get_client", return_value=mock_client):
            start = datetime(2026, 1, 1, tzinfo=UTC)
            end = datetime(2026, 2, 4, tzinfo=UTC)

            result = await collector._fetch_tga(start, end)

            assert len(result) == 3
            assert result["series_id"].unique().tolist() == ["TGA_DAILY"]
            assert result["source"].unique().tolist() == ["fiscaldata"]
            assert result["unit"].unique().tolist() == ["millions_usd"]

            # Values should be floats
            assert result["value"].dtype == float
            assert result["value"].iloc[0] == 714000.0  # Sorted ascending
            assert result["value"].iloc[-1] == 845123.0

    @pytest.mark.asyncio
    async def test_fetch_tga_constructs_correct_url(self, collector: TGADailyCollector) -> None:
        """Test that _fetch_tga constructs correct API URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(collector, "_get_client", return_value=mock_client):
            start = datetime(2026, 1, 1, tzinfo=UTC)
            end = datetime(2026, 1, 31, tzinfo=UTC)

            await collector._fetch_tga(start, end)

            expected_url = f"{FISCALDATA_BASE_URL}/{ENDPOINT}"
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert call_args[0][0] == expected_url

            # Check params
            params = call_args[1]["params"]
            assert f"account_type:eq:{TGA_ACCOUNT_TYPE}" in params["filter"]
            assert "record_date:gte:2026-01-01" in params["filter"]
            assert "record_date:lte:2026-01-31" in params["filter"]

    @pytest.mark.asyncio
    async def test_fetch_tga_handles_null_values(self, collector: TGADailyCollector) -> None:
        """Test that _fetch_tga skips records with null open_today_bal."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "record_date": "2026-02-04",
                    "account_type": "Treasury General Account (TGA) Closing Balance",
                    "open_today_bal": "845123",
                    "open_month_bal": "714000",
                },
                {
                    "record_date": "2026-02-03",
                    "account_type": "Treasury General Account (TGA) Closing Balance",
                    "open_today_bal": None,  # null value
                    "open_month_bal": "714000",
                },
            ],
            "meta": {"count": 2, "total-count": 2},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(collector, "_get_client", return_value=mock_client):
            result = await collector._fetch_tga(
                datetime(2026, 2, 1, tzinfo=UTC),
                datetime(2026, 2, 4, tzinfo=UTC),
            )

            # Should only have 1 row (null value skipped)
            assert len(result) == 1
            assert result["value"].iloc[0] == 845123.0

    @pytest.mark.asyncio
    async def test_fetch_tga_empty_response(
        self, collector: TGADailyCollector, empty_response_data: dict
    ) -> None:
        """Test _fetch_tga with empty API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = empty_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False

        with patch.object(collector, "_get_client", return_value=mock_client):
            result = await collector._fetch_tga(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 31, tzinfo=UTC),
            )

            assert len(result) == 0
            assert list(result.columns) == ["timestamp", "series_id", "source", "value", "unit"]


class TestTGADailyCollectorCollectLatest:
    """Tests for TGADailyCollector.collect_latest() method."""

    @pytest.mark.asyncio
    async def test_collect_latest_returns_single_row(
        self, collector: TGADailyCollector, mock_response_data: dict
    ) -> None:
        """Test that collect_latest returns exactly one row."""
        with patch.object(collector, "collect") as mock_collect:
            mock_df = pd.DataFrame(
                [
                    {
                        "timestamp": pd.Timestamp("2026-02-03"),
                        "series_id": "TGA_DAILY",
                        "source": "fiscaldata",
                        "value": 832541.0,
                        "unit": "millions_usd",
                    },
                    {
                        "timestamp": pd.Timestamp("2026-02-04"),
                        "series_id": "TGA_DAILY",
                        "source": "fiscaldata",
                        "value": 845123.0,
                        "unit": "millions_usd",
                    },
                ]
            )
            mock_collect.return_value = mock_df

            result = await collector.collect_latest()

            assert len(result) == 1
            assert result["value"].iloc[0] == 845123.0  # Latest value

    @pytest.mark.asyncio
    async def test_collect_latest_handles_empty(self, collector: TGADailyCollector) -> None:
        """Test collect_latest with empty data."""
        with patch.object(collector, "collect") as mock_collect:
            mock_collect.return_value = pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

            result = await collector.collect_latest()

            assert len(result) == 0


class TestTGADailyCollectorClose:
    """Tests for TGADailyCollector.close() method."""

    @pytest.mark.asyncio
    async def test_close_closes_client(self, collector: TGADailyCollector) -> None:
        """Test that close() properly closes the HTTP client."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        collector._client = mock_client

        await collector.close()

        mock_client.aclose.assert_called_once()
        assert collector._client is None

    @pytest.mark.asyncio
    async def test_close_handles_none_client(self, collector: TGADailyCollector) -> None:
        """Test that close() handles None client gracefully."""
        collector._client = None

        # Should not raise
        await collector.close()

    @pytest.mark.asyncio
    async def test_close_handles_already_closed_client(self, collector: TGADailyCollector) -> None:
        """Test that close() handles already closed client."""
        mock_client = AsyncMock()
        mock_client.is_closed = True
        collector._client = mock_client

        await collector.close()

        mock_client.aclose.assert_not_called()


class TestTGADailyCollectorRegistry:
    """Tests for collector registry integration."""

    def test_collector_registered(self) -> None:
        """Test that TGA Daily collector is registered in the registry."""
        from liquidity.collectors import registry

        assert "tga_daily" in registry.list_collectors()
        collector_cls = registry.get("tga_daily")
        assert collector_cls is TGADailyCollector

    def test_collector_instantiation_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector_cls = registry.get("tga_daily")
        collector = collector_cls()

        assert isinstance(collector, TGADailyCollector)
        assert collector.name == "tga_daily"


class TestTGADailyCollectorDataValidation:
    """Tests for data structure validation."""

    @pytest.mark.asyncio
    async def test_output_columns(
        self, collector: TGADailyCollector, mock_response_data: dict
    ) -> None:
        """Test that output has correct column structure."""
        with patch.object(collector, "_fetch_tga") as mock_fetch:
            mock_df = pd.DataFrame(
                [
                    {
                        "timestamp": pd.Timestamp("2026-02-04"),
                        "series_id": "TGA_DAILY",
                        "source": "fiscaldata",
                        "value": 845123.0,
                        "unit": "millions_usd",
                    }
                ]
            )
            mock_fetch.return_value = mock_df

            result = await collector.collect()

            expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
            assert expected_columns == set(result.columns)

    @pytest.mark.asyncio
    async def test_series_id_is_tga_daily(self, collector: TGADailyCollector) -> None:
        """Test that series_id is always TGA_DAILY."""
        with patch.object(collector, "_fetch_tga") as mock_fetch:
            mock_df = pd.DataFrame(
                [
                    {
                        "timestamp": pd.Timestamp("2026-02-04"),
                        "series_id": "TGA_DAILY",
                        "source": "fiscaldata",
                        "value": 845123.0,
                        "unit": "millions_usd",
                    }
                ]
            )
            mock_fetch.return_value = mock_df

            result = await collector.collect()

            assert result["series_id"].unique().tolist() == ["TGA_DAILY"]

    @pytest.mark.asyncio
    async def test_source_is_fiscaldata(self, collector: TGADailyCollector) -> None:
        """Test that source is always fiscaldata."""
        with patch.object(collector, "_fetch_tga") as mock_fetch:
            mock_df = pd.DataFrame(
                [
                    {
                        "timestamp": pd.Timestamp("2026-02-04"),
                        "series_id": "TGA_DAILY",
                        "source": "fiscaldata",
                        "value": 845123.0,
                        "unit": "millions_usd",
                    }
                ]
            )
            mock_fetch.return_value = mock_df

            result = await collector.collect()

            assert result["source"].unique().tolist() == ["fiscaldata"]

    @pytest.mark.asyncio
    async def test_unit_is_millions_usd(self, collector: TGADailyCollector) -> None:
        """Test that unit is always millions_usd."""
        with patch.object(collector, "_fetch_tga") as mock_fetch:
            mock_df = pd.DataFrame(
                [
                    {
                        "timestamp": pd.Timestamp("2026-02-04"),
                        "series_id": "TGA_DAILY",
                        "source": "fiscaldata",
                        "value": 845123.0,
                        "unit": "millions_usd",
                    }
                ]
            )
            mock_fetch.return_value = mock_df

            result = await collector.collect()

            assert result["unit"].unique().tolist() == ["millions_usd"]
