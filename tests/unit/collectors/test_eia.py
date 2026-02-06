"""Unit tests for EIA API v2 collector.

Tests EIACollector with mocked httpx responses.
Run with: uv run pytest tests/unit/collectors/test_eia.py -v
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from liquidity.collectors.eia import (
    CUSHING_CAPACITY_KB,
    ROUTE_MAP,
    SERIES_MAP,
    UNIT_MAP,
    UTILIZATION_THRESHOLDS,
    EIACollector,
)


@pytest.fixture
def eia_collector() -> EIACollector:
    """Create an EIA collector instance with mock API key."""
    with patch("liquidity.collectors.eia.get_settings") as mock_settings:
        mock_settings.return_value.eia_api_key.get_secret_value.return_value = (
            "test_api_key"
        )
        mock_settings.return_value.circuit_breaker.threshold = 5
        mock_settings.return_value.circuit_breaker.ttl = 60
        mock_settings.return_value.retry.max_attempts = 3
        mock_settings.return_value.retry.multiplier = 1.0
        mock_settings.return_value.retry.min_wait = 1
        mock_settings.return_value.retry.max_wait = 10
        return EIACollector()


@pytest.fixture
def mock_stocks_response() -> dict:
    """Sample crude stocks API response from EIA."""
    return {
        "response": {
            "total": 3,
            "dateFormat": "YYYY-MM-DD",
            "frequency": "weekly",
            "data": [
                {
                    "period": "2026-02-05",
                    "series": "WCESTUS1",
                    "value": 425000,
                    "units": "thousand barrels",
                },
                {
                    "period": "2026-01-29",
                    "series": "WCESTUS1",
                    "value": 423500,
                    "units": "thousand barrels",
                },
                {
                    "period": "2026-01-22",
                    "series": "WCESTUS1",
                    "value": 422000,
                    "units": "thousand barrels",
                },
            ],
        }
    }


@pytest.fixture
def mock_production_response() -> dict:
    """Sample crude production API response from EIA."""
    return {
        "response": {
            "total": 2,
            "dateFormat": "YYYY-MM-DD",
            "frequency": "weekly",
            "data": [
                {
                    "period": "2026-02-05",
                    "series": "WCRFPUS2",
                    "value": 13100,
                    "units": "thousand b/d",
                },
                {
                    "period": "2026-01-29",
                    "series": "WCRFPUS2",
                    "value": 13050,
                    "units": "thousand b/d",
                },
            ],
        }
    }


@pytest.fixture
def mock_imports_response() -> dict:
    """Sample crude imports API response from EIA."""
    return {
        "response": {
            "total": 2,
            "dateFormat": "YYYY-MM-DD",
            "frequency": "weekly",
            "data": [
                {
                    "period": "2026-02-05",
                    "series": "WCRIMUS2",
                    "value": 6200,
                    "units": "thousand b/d",
                },
                {
                    "period": "2026-01-29",
                    "series": "WCRIMUS2",
                    "value": 6150,
                    "units": "thousand b/d",
                },
            ],
        }
    }


class TestSeriesMapping:
    """Tests for EIA series mapping constants."""

    def test_series_map_contains_core_series(self) -> None:
        """Test SERIES_MAP contains required core series."""
        assert "crude_stocks_total" in SERIES_MAP
        assert "crude_production" in SERIES_MAP
        assert "crude_imports" in SERIES_MAP

    def test_series_map_values_are_eia_ids(self) -> None:
        """Test SERIES_MAP values are valid EIA series IDs."""
        assert SERIES_MAP["crude_stocks_total"] == "WCESTUS1"
        assert SERIES_MAP["crude_production"] == "WCRFPUS2"
        assert SERIES_MAP["crude_imports"] == "WCRIMUS2"

    def test_unit_map_covers_all_series(self) -> None:
        """Test UNIT_MAP has entries for core series."""
        core_series = ["WCESTUS1", "WCRFPUS2", "WCRIMUS2"]
        for series_id in core_series:
            assert series_id in UNIT_MAP

    def test_unit_map_values(self) -> None:
        """Test UNIT_MAP has correct units."""
        assert UNIT_MAP["WCESTUS1"] == "thousand_barrels"
        assert UNIT_MAP["WCRFPUS2"] == "thousand_bpd"
        assert UNIT_MAP["WCRIMUS2"] == "thousand_bpd"

    def test_route_map_covers_all_series(self) -> None:
        """Test ROUTE_MAP has entries for core series."""
        core_series = ["WCESTUS1", "WCRFPUS2", "WCRIMUS2"]
        for series_id in core_series:
            assert series_id in ROUTE_MAP


class TestEIACollectorInit:
    """Tests for EIACollector initialization."""

    def test_collector_name_default(self, eia_collector: EIACollector) -> None:
        """Test default collector name is 'eia'."""
        assert eia_collector.name == "eia"

    def test_collector_base_url(self, eia_collector: EIACollector) -> None:
        """Test BASE_URL is correct."""
        assert EIACollector.BASE_URL == "https://api.eia.gov/v2"

    def test_collector_series_map_attached(self, eia_collector: EIACollector) -> None:
        """Test SERIES_MAP is attached to class."""
        assert EIACollector.SERIES_MAP == SERIES_MAP


class TestResponseParsing:
    """Tests for EIA API response parsing."""

    @pytest.mark.asyncio
    async def test_collect_returns_dataframe(
        self, eia_collector: EIACollector, mock_stocks_response: dict
    ) -> None:
        """Test collect returns properly formatted DataFrame."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_stocks_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(["WCESTUS1"])

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 3
            assert "timestamp" in result.columns
            assert "series_id" in result.columns
            assert "source" in result.columns
            assert "value" in result.columns
            assert "unit" in result.columns

    @pytest.mark.asyncio
    async def test_collect_correct_source(
        self, eia_collector: EIACollector, mock_stocks_response: dict
    ) -> None:
        """Test collect sets source to 'eia'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_stocks_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(["WCESTUS1"])

            assert all(result["source"] == "eia")

    @pytest.mark.asyncio
    async def test_collect_correct_series_id(
        self, eia_collector: EIACollector, mock_stocks_response: dict
    ) -> None:
        """Test collect preserves series_id."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_stocks_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(["WCESTUS1"])

            assert all(result["series_id"] == "WCESTUS1")

    @pytest.mark.asyncio
    async def test_collect_correct_unit(
        self, eia_collector: EIACollector, mock_stocks_response: dict
    ) -> None:
        """Test collect applies correct unit from UNIT_MAP."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_stocks_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(["WCESTUS1"])

            assert all(result["unit"] == "thousand_barrels")

    @pytest.mark.asyncio
    async def test_collect_parses_values_correctly(
        self, eia_collector: EIACollector, mock_stocks_response: dict
    ) -> None:
        """Test collect parses numeric values correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_stocks_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(["WCESTUS1"])

            # Values should match mock data
            assert 425000.0 in result["value"].values
            assert 423500.0 in result["value"].values
            assert 422000.0 in result["value"].values

    @pytest.mark.asyncio
    async def test_collect_parses_dates_correctly(
        self, eia_collector: EIACollector, mock_stocks_response: dict
    ) -> None:
        """Test collect parses dates correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_stocks_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(["WCESTUS1"])

            # Check timestamps are parsed
            assert pd.Timestamp("2026-02-05") in result["timestamp"].values


class TestEmptyResponses:
    """Tests for handling empty or error responses."""

    @pytest.mark.asyncio
    async def test_collect_empty_response(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect handles empty API response."""
        empty_response = {"response": {"total": 0, "data": []}}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = empty_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(["WCESTUS1"])

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0
            assert "timestamp" in result.columns

    @pytest.mark.asyncio
    async def test_collect_no_api_key(self, eia_collector: EIACollector) -> None:
        """Test collect handles missing API key gracefully."""
        with patch("liquidity.collectors.eia.get_settings") as mock_settings:
            mock_settings.return_value.eia_api_key.get_secret_value.return_value = ""

            # Create new collector with empty API key
            collector = EIACollector()
            collector._settings = mock_settings.return_value

            result = await collector._fetch_series(
                ["WCESTUS1"],
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 2, 1, tzinfo=UTC),
            )

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_collect_malformed_response(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect handles malformed API response."""
        malformed_response = {"error": "something went wrong"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = malformed_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(["WCESTUS1"])

            # Should return empty DataFrame, not raise
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_collect_null_values_skipped(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect skips records with null values."""
        response_with_nulls = {
            "response": {
                "total": 3,
                "data": [
                    {"period": "2026-02-05", "series": "WCESTUS1", "value": 425000},
                    {"period": "2026-01-29", "series": "WCESTUS1", "value": None},
                    {"period": "2026-01-22", "series": "WCESTUS1", "value": 422000},
                ],
            }
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_with_nulls
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(["WCESTUS1"])

            # Should have 2 records (null value skipped)
            assert len(result) == 2


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_http_error_returns_empty_df(
        self, eia_collector: EIACollector
    ) -> None:
        """Test single series HTTP error returns empty DataFrame (graceful degradation)."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            # When a single series fails, the collector gracefully returns an empty df
            result = await eia_collector.collect(["WCESTUS1"])
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_partial_failure_returns_available_data(
        self, eia_collector: EIACollector, mock_stocks_response: dict
    ) -> None:
        """Test partial series failure returns available data."""
        import httpx

        # First call succeeds, second fails
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = mock_stocks_response
        mock_success.raise_for_status = MagicMock()

        mock_failure = MagicMock()
        mock_failure.status_code = 500
        mock_failure.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_failure
        )

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            # Return success for first, failure for second
            mock_client.get = AsyncMock(side_effect=[mock_success, mock_failure])
            mock_get_client.return_value = mock_client

            # Even though second series fails, we should get data from first
            result = await eia_collector.collect(["WCESTUS1", "WCRFPUS2"])
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 3  # Got data from first series


class TestConvenienceMethods:
    """Tests for convenience collection methods."""

    @pytest.mark.asyncio
    async def test_collect_stocks_calls_collect(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_stocks calls collect with correct series."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_stocks()
            mock.assert_called_once()
            call_args = mock.call_args
            assert "WCESTUS1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_collect_production_calls_collect(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_production calls collect with correct series."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_production()
            mock.assert_called_once()
            call_args = mock.call_args
            assert "WCRFPUS2" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_collect_imports_calls_collect(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_imports calls collect with correct series."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_imports()
            mock.assert_called_once()
            call_args = mock.call_args
            assert "WCRIMUS2" in call_args[0][0]


class TestCollectorRegistry:
    """Tests for collector registry integration."""

    def test_eia_collector_registered(self) -> None:
        """Test that EIA collector is registered."""
        from liquidity.collectors import registry

        assert "eia" in registry.list_collectors()
        assert registry.get("eia") is EIACollector

    def test_collector_instantiation_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        with patch("liquidity.collectors.eia.get_settings") as mock_settings:
            mock_settings.return_value.eia_api_key.get_secret_value.return_value = (
                "test_key"
            )
            mock_settings.return_value.circuit_breaker.threshold = 5
            mock_settings.return_value.circuit_breaker.ttl = 60
            mock_settings.return_value.retry.max_attempts = 3
            mock_settings.return_value.retry.multiplier = 1.0
            mock_settings.return_value.retry.min_wait = 1
            mock_settings.return_value.retry.max_wait = 10

            eia = registry.get("eia")()

            assert isinstance(eia, EIACollector)
            assert eia.name == "eia"


class TestCollectorClose:
    """Tests for collector cleanup."""

    @pytest.mark.asyncio
    async def test_close_releases_client(
        self, eia_collector: EIACollector
    ) -> None:
        """Test close method releases HTTP client."""
        # Initialize client by calling _get_client
        client = await eia_collector._get_client()
        assert client is not None
        assert not client.is_closed

        # Close should release client
        await eia_collector.close()
        assert eia_collector._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self, eia_collector: EIACollector) -> None:
        """Test close can be called multiple times safely."""
        await eia_collector.close()  # First call (no client yet)
        await eia_collector.close()  # Second call (still safe)
        # Should not raise


class TestDateParameters:
    """Tests for date parameter handling."""

    @pytest.mark.asyncio
    async def test_collect_accepts_date_parameters(
        self, eia_collector: EIACollector, mock_stocks_response: dict
    ) -> None:
        """Test collect accepts start_date and end_date parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_stocks_response
        mock_response.raise_for_status = MagicMock()

        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 2, 1, tzinfo=UTC)

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect(
                ["WCESTUS1"], start_date=start, end_date=end
            )

            assert isinstance(result, pd.DataFrame)
            # Verify get was called with date params
            mock_client.get.assert_called()
            call_kwargs = mock_client.get.call_args[1]
            assert "params" in call_kwargs
            assert call_kwargs["params"]["start"] == "2026-01-01"
            assert call_kwargs["params"]["end"] == "2026-02-01"


class TestCushingSeriesMapping:
    """Tests for Cushing series mapping in constants."""

    def test_cushing_inventory_in_series_map(self) -> None:
        """Test cushing_inventory is in SERIES_MAP."""
        assert "cushing_inventory" in SERIES_MAP
        assert SERIES_MAP["cushing_inventory"] == "W_EPC0_SAX_YCUOK_MBBL"

    def test_cushing_series_in_unit_map(self) -> None:
        """Test Cushing series has unit mapping."""
        assert "W_EPC0_SAX_YCUOK_MBBL" in UNIT_MAP
        assert UNIT_MAP["W_EPC0_SAX_YCUOK_MBBL"] == "thousand_barrels"

    def test_cushing_series_in_route_map(self) -> None:
        """Test Cushing series has route mapping."""
        assert "W_EPC0_SAX_YCUOK_MBBL" in ROUTE_MAP
        assert ROUTE_MAP["W_EPC0_SAX_YCUOK_MBBL"] == "/petroleum/stoc/wstk/data"

    def test_cushing_capacity_constant(self) -> None:
        """Test Cushing capacity is correct (70,800 thousand barrels = 70.8M bbls)."""
        assert CUSHING_CAPACITY_KB == 70_800


@pytest.fixture
def mock_cushing_response() -> dict:
    """Sample Cushing inventory API response from EIA."""
    return {
        "response": {
            "total": 52,
            "dateFormat": "YYYY-MM-DD",
            "frequency": "weekly",
            "data": [
                {
                    "period": "2026-02-05",
                    "series": "W_EPC0_SAX_YCUOK_MBBL",
                    "value": 35400,  # 35.4M barrels
                    "units": "thousand barrels",
                },
                {
                    "period": "2026-01-29",
                    "series": "W_EPC0_SAX_YCUOK_MBBL",
                    "value": 34800,
                    "units": "thousand barrels",
                },
                {
                    "period": "2026-01-22",
                    "series": "W_EPC0_SAX_YCUOK_MBBL",
                    "value": 34200,
                    "units": "thousand barrels",
                },
            ],
        }
    }


class TestCushingCollect:
    """Tests for collect_cushing method."""

    @pytest.mark.asyncio
    async def test_collect_cushing_calls_collect(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_cushing calls collect with correct Cushing series."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_cushing()
            mock.assert_called_once()
            call_args = mock.call_args
            assert "W_EPC0_SAX_YCUOK_MBBL" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_collect_cushing_default_lookback(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_cushing uses 52 week default lookback."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_cushing()
            mock.assert_called_once()
            # Check the date range is approximately 52 weeks
            call_args = mock.call_args
            start_date = call_args[1].get("start_date") or call_args[0][1]
            end_date = call_args[1].get("end_date") or call_args[0][2]
            weeks_diff = (end_date - start_date).days / 7
            assert 51 <= weeks_diff <= 53

    @pytest.mark.asyncio
    async def test_collect_cushing_custom_lookback(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_cushing with custom lookback_weeks."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_cushing(lookback_weeks=26)
            mock.assert_called_once()
            call_args = mock.call_args
            start_date = call_args[0][1]
            end_date = call_args[0][2]
            weeks_diff = (end_date - start_date).days / 7
            assert 25 <= weeks_diff <= 27

    @pytest.mark.asyncio
    async def test_collect_cushing_returns_dataframe(
        self, eia_collector: EIACollector, mock_cushing_response: dict
    ) -> None:
        """Test collect_cushing returns properly formatted DataFrame."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_cushing_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect_cushing()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 3
            assert all(result["series_id"] == "W_EPC0_SAX_YCUOK_MBBL")
            assert all(result["unit"] == "thousand_barrels")


class TestCushingUtilization:
    """Tests for calculate_cushing_utilization method."""

    def test_utilization_calculation_basic(
        self, eia_collector: EIACollector
    ) -> None:
        """Test utilization calculation produces correct percentages."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-01", "2026-01-08"]),
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"] * 2,
                "source": ["eia"] * 2,
                "value": [35400, 42480],  # 50% and 60% of 70,800
                "unit": ["thousand_barrels"] * 2,
            }
        )

        result = eia_collector.calculate_cushing_utilization(df)

        assert "utilization_pct" in result.columns
        assert len(result) == 2
        # 35400 / 70800 * 100 = 50%
        assert abs(result["utilization_pct"].iloc[0] - 50.0) < 0.01
        # 42480 / 70800 * 100 = 60%
        assert abs(result["utilization_pct"].iloc[1] - 60.0) < 0.01

    def test_utilization_preserves_original_columns(
        self, eia_collector: EIACollector
    ) -> None:
        """Test utilization calculation preserves all original columns."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-01"]),
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"],
                "source": ["eia"],
                "value": [35400],
                "unit": ["thousand_barrels"],
            }
        )

        result = eia_collector.calculate_cushing_utilization(df)

        assert "timestamp" in result.columns
        assert "series_id" in result.columns
        assert "source" in result.columns
        assert "value" in result.columns
        assert "unit" in result.columns
        assert "utilization_pct" in result.columns

    def test_utilization_does_not_mutate_input(
        self, eia_collector: EIACollector
    ) -> None:
        """Test utilization calculation does not mutate input DataFrame."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-01"]),
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"],
                "source": ["eia"],
                "value": [35400],
                "unit": ["thousand_barrels"],
            }
        )
        original_columns = list(df.columns)

        eia_collector.calculate_cushing_utilization(df)

        # Original df should not have utilization_pct column
        assert list(df.columns) == original_columns
        assert "utilization_pct" not in df.columns

    def test_utilization_at_capacity_is_100_percent(
        self, eia_collector: EIACollector
    ) -> None:
        """Test utilization at full capacity is 100%."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-01"]),
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"],
                "source": ["eia"],
                "value": [70800],  # Full capacity
                "unit": ["thousand_barrels"],
            }
        )

        result = eia_collector.calculate_cushing_utilization(df)

        assert abs(result["utilization_pct"].iloc[0] - 100.0) < 0.01

    def test_utilization_at_zero_is_0_percent(
        self, eia_collector: EIACollector
    ) -> None:
        """Test utilization at zero inventory is 0%."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-01"]),
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"],
                "source": ["eia"],
                "value": [0],
                "unit": ["thousand_barrels"],
            }
        )

        result = eia_collector.calculate_cushing_utilization(df)

        assert abs(result["utilization_pct"].iloc[0] - 0.0) < 0.01


class TestCushingPercentile:
    """Tests for calculate_cushing_percentile method."""

    def test_percentile_calculation_basic(
        self, eia_collector: EIACollector
    ) -> None:
        """Test percentile calculation produces expected results."""
        # Create 52+ weeks of data
        dates = pd.date_range(start="2025-01-01", periods=60, freq="W")
        # Values from 30000 to 40000 linearly (older to newer)
        values = [30000 + i * 170 for i in range(60)]

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"] * 60,
                "source": ["eia"] * 60,
                "value": values,
                "unit": ["thousand_barrels"] * 60,
            }
        )

        result = eia_collector.calculate_cushing_percentile(df)

        assert "percentile_52w" in result.columns
        # First 51 rows should be NaN (not enough data for 52-week rolling)
        assert result["percentile_52w"].iloc[:51].isna().all()
        # Row 51 (52nd row, index 51) should have a valid percentile
        assert not pd.isna(result["percentile_52w"].iloc[51])
        # Last row should have high percentile (near 100) since values increase
        assert result["percentile_52w"].iloc[-1] > 90

    def test_percentile_preserves_original_columns(
        self, eia_collector: EIACollector
    ) -> None:
        """Test percentile calculation preserves all original columns."""
        dates = pd.date_range(start="2025-01-01", periods=60, freq="W")
        values = [35000 + i * 100 for i in range(60)]

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"] * 60,
                "source": ["eia"] * 60,
                "value": values,
                "unit": ["thousand_barrels"] * 60,
            }
        )

        result = eia_collector.calculate_cushing_percentile(df)

        assert "timestamp" in result.columns
        assert "series_id" in result.columns
        assert "source" in result.columns
        assert "value" in result.columns
        assert "unit" in result.columns
        assert "percentile_52w" in result.columns

    def test_percentile_does_not_mutate_input(
        self, eia_collector: EIACollector
    ) -> None:
        """Test percentile calculation does not mutate input DataFrame."""
        dates = pd.date_range(start="2025-01-01", periods=60, freq="W")
        values = [35000 + i * 100 for i in range(60)]

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"] * 60,
                "source": ["eia"] * 60,
                "value": values,
                "unit": ["thousand_barrels"] * 60,
            }
        )
        original_columns = list(df.columns)

        eia_collector.calculate_cushing_percentile(df)

        # Original df should not have percentile_52w column
        assert list(df.columns) == original_columns
        assert "percentile_52w" not in df.columns

    def test_percentile_at_minimum_is_0(
        self, eia_collector: EIACollector
    ) -> None:
        """Test percentile at 52-week minimum is 0."""
        # Create data where current value is the minimum
        dates = pd.date_range(start="2025-01-01", periods=60, freq="W")
        # Decreasing values so the last one is the minimum
        values = [40000 - i * 100 for i in range(60)]

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"] * 60,
                "source": ["eia"] * 60,
                "value": values,
                "unit": ["thousand_barrels"] * 60,
            }
        )

        result = eia_collector.calculate_cushing_percentile(df)

        # Last row is the minimum value, so percentile should be 0
        assert abs(result["percentile_52w"].iloc[-1] - 0.0) < 0.01

    def test_percentile_at_maximum_is_100(
        self, eia_collector: EIACollector
    ) -> None:
        """Test percentile at 52-week maximum is 100."""
        # Create data where current value is the maximum
        dates = pd.date_range(start="2025-01-01", periods=60, freq="W")
        # Increasing values so the last one is the maximum
        values = [30000 + i * 100 for i in range(60)]

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"] * 60,
                "source": ["eia"] * 60,
                "value": values,
                "unit": ["thousand_barrels"] * 60,
            }
        )

        result = eia_collector.calculate_cushing_percentile(df)

        # Last row is the maximum value, so percentile should be 100
        assert abs(result["percentile_52w"].iloc[-1] - 100.0) < 0.01

    def test_percentile_handles_constant_values(
        self, eia_collector: EIACollector
    ) -> None:
        """Test percentile handles constant values (no range) gracefully."""
        # Create data where all values are the same
        dates = pd.date_range(start="2025-01-01", periods=60, freq="W")
        values = [35000] * 60  # All same value

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["W_EPC0_SAX_YCUOK_MBBL"] * 60,
                "source": ["eia"] * 60,
                "value": values,
                "unit": ["thousand_barrels"] * 60,
            }
        )

        result = eia_collector.calculate_cushing_percentile(df)

        # When min == max, we default to 50% (neutral)
        assert abs(result["percentile_52w"].iloc[-1] - 50.0) < 0.01


class TestRefineryUtilizationSeriesMapping:
    """Tests for refinery utilization series mapping in constants."""

    def test_refinery_utilization_us_in_series_map(self) -> None:
        """Test refinery_utilization_us is in SERIES_MAP."""
        assert "refinery_utilization_us" in SERIES_MAP
        assert SERIES_MAP["refinery_utilization_us"] == "WPULEUS3"

    def test_refinery_utilization_padd1_in_series_map(self) -> None:
        """Test refinery_utilization_padd1 (East Coast) is in SERIES_MAP."""
        assert "refinery_utilization_padd1" in SERIES_MAP
        assert SERIES_MAP["refinery_utilization_padd1"] == "W_NA_YUP_R10_PER"

    def test_refinery_utilization_padd3_in_series_map(self) -> None:
        """Test refinery_utilization_padd3 (Gulf Coast) is in SERIES_MAP."""
        assert "refinery_utilization_padd3" in SERIES_MAP
        assert SERIES_MAP["refinery_utilization_padd3"] == "W_NA_YUP_R30_PER"

    def test_refinery_utilization_padd5_in_series_map(self) -> None:
        """Test refinery_utilization_padd5 (West Coast) is in SERIES_MAP."""
        assert "refinery_utilization_padd5" in SERIES_MAP
        assert SERIES_MAP["refinery_utilization_padd5"] == "W_NA_YUP_R50_PER"

    def test_all_refinery_series_in_unit_map(self) -> None:
        """Test all refinery utilization series have unit mappings."""
        refinery_series = ["WPULEUS3", "W_NA_YUP_R10_PER", "W_NA_YUP_R30_PER", "W_NA_YUP_R50_PER"]
        for series_id in refinery_series:
            assert series_id in UNIT_MAP
            assert UNIT_MAP[series_id] == "percent"

    def test_all_refinery_series_in_route_map(self) -> None:
        """Test all refinery utilization series have route mappings."""
        refinery_series = ["WPULEUS3", "W_NA_YUP_R10_PER", "W_NA_YUP_R30_PER", "W_NA_YUP_R50_PER"]
        for series_id in refinery_series:
            assert series_id in ROUTE_MAP
            assert ROUTE_MAP[series_id] == "/petroleum/sum/sndw/data"

    def test_utilization_thresholds_defined(self) -> None:
        """Test UTILIZATION_THRESHOLDS are correctly defined."""
        assert "TIGHT" in UTILIZATION_THRESHOLDS
        assert "NORMAL" in UTILIZATION_THRESHOLDS
        assert "SOFT" in UTILIZATION_THRESHOLDS
        assert UTILIZATION_THRESHOLDS["TIGHT"] == 95.0
        assert UTILIZATION_THRESHOLDS["NORMAL"] == 90.0
        assert UTILIZATION_THRESHOLDS["SOFT"] == 85.0


@pytest.fixture
def mock_refinery_utilization_response_us() -> dict:
    """Sample US refinery utilization API response from EIA."""
    return {
        "response": {
            "total": 3,
            "dateFormat": "YYYY-MM-DD",
            "frequency": "weekly",
            "data": [
                {
                    "period": "2026-02-05",
                    "series": "WPULEUS3",
                    "value": 92.5,  # NORMAL range
                    "units": "percent",
                },
                {
                    "period": "2026-01-29",
                    "series": "WPULEUS3",
                    "value": 91.8,
                    "units": "percent",
                },
                {
                    "period": "2026-01-22",
                    "series": "WPULEUS3",
                    "value": 90.5,
                    "units": "percent",
                },
            ],
        }
    }


@pytest.fixture
def mock_refinery_utilization_response_padd3() -> dict:
    """Sample PADD 3 (Gulf Coast) refinery utilization API response."""
    return {
        "response": {
            "total": 2,
            "dateFormat": "YYYY-MM-DD",
            "frequency": "weekly",
            "data": [
                {
                    "period": "2026-02-05",
                    "series": "W_NA_YUP_R30_PER",
                    "value": 96.2,  # TIGHT range - Gulf Coast typically runs high
                    "units": "percent",
                },
                {
                    "period": "2026-01-29",
                    "series": "W_NA_YUP_R30_PER",
                    "value": 95.8,
                    "units": "percent",
                },
            ],
        }
    }


class TestRefineryUtilizationCollect:
    """Tests for collect_refinery_utilization method."""

    @pytest.mark.asyncio
    async def test_collect_refinery_utilization_default_regions(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_refinery_utilization calls collect with all regions by default."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_refinery_utilization()
            mock.assert_called_once()
            call_args = mock.call_args
            series_ids = call_args[0][0]
            # Should include all 4 regions
            assert "WPULEUS3" in series_ids
            assert "W_NA_YUP_R10_PER" in series_ids
            assert "W_NA_YUP_R30_PER" in series_ids
            assert "W_NA_YUP_R50_PER" in series_ids

    @pytest.mark.asyncio
    async def test_collect_refinery_utilization_single_region(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_refinery_utilization with single region."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_refinery_utilization(regions=["padd3"])
            mock.assert_called_once()
            call_args = mock.call_args
            series_ids = call_args[0][0]
            # Should only include PADD 3
            assert series_ids == ["W_NA_YUP_R30_PER"]

    @pytest.mark.asyncio
    async def test_collect_refinery_utilization_multiple_regions(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_refinery_utilization with specific regions."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_refinery_utilization(regions=["us", "padd3"])
            mock.assert_called_once()
            call_args = mock.call_args
            series_ids = call_args[0][0]
            assert "WPULEUS3" in series_ids
            assert "W_NA_YUP_R30_PER" in series_ids
            assert len(series_ids) == 2

    @pytest.mark.asyncio
    async def test_collect_refinery_utilization_custom_lookback(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_refinery_utilization with custom lookback_weeks."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(eia_collector, "collect", return_value=mock_df) as mock:
            await eia_collector.collect_refinery_utilization(lookback_weeks=26)
            mock.assert_called_once()
            call_args = mock.call_args
            start_date = call_args[0][1]
            end_date = call_args[0][2]
            weeks_diff = (end_date - start_date).days / 7
            assert 25 <= weeks_diff <= 27

    @pytest.mark.asyncio
    async def test_collect_refinery_utilization_invalid_region_logs_warning(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_refinery_utilization logs warning for invalid region."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with (
            patch.object(eia_collector, "collect", return_value=mock_df),
            patch("liquidity.collectors.eia.logger") as mock_logger,
        ):
            await eia_collector.collect_refinery_utilization(regions=["invalid_region"])
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_collect_refinery_utilization_empty_regions(
        self, eia_collector: EIACollector
    ) -> None:
        """Test collect_refinery_utilization with only invalid regions returns empty df."""
        with patch("liquidity.collectors.eia.logger"):
            result = await eia_collector.collect_refinery_utilization(
                regions=["invalid1", "invalid2"]
            )
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_collect_refinery_utilization_returns_dataframe(
        self,
        eia_collector: EIACollector,
        mock_refinery_utilization_response_us: dict,
    ) -> None:
        """Test collect_refinery_utilization returns properly formatted DataFrame."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_refinery_utilization_response_us
        mock_response.raise_for_status = MagicMock()

        with patch.object(eia_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await eia_collector.collect_refinery_utilization(regions=["us"])

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 3
            assert all(result["series_id"] == "WPULEUS3")
            assert all(result["unit"] == "percent")


class TestUtilizationSignalCalculation:
    """Tests for calculate_utilization_signal method."""

    def test_signal_tight_above_95(self, eia_collector: EIACollector) -> None:
        """Test signal is TIGHT when utilization > 95%."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WPULEUS3"],
                "source": ["eia"],
                "value": [96.5],  # Above 95%
                "unit": ["percent"],
            }
        )

        signal = eia_collector.calculate_utilization_signal(df)
        assert signal == "TIGHT"

    def test_signal_tight_at_boundary(self, eia_collector: EIACollector) -> None:
        """Test signal is NORMAL at exactly 95% (threshold is >95)."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WPULEUS3"],
                "source": ["eia"],
                "value": [95.0],  # Exactly at threshold
                "unit": ["percent"],
            }
        )

        signal = eia_collector.calculate_utilization_signal(df)
        assert signal == "NORMAL"  # 95.0 is not > 95, so falls to NORMAL

    def test_signal_normal_between_90_and_95(self, eia_collector: EIACollector) -> None:
        """Test signal is NORMAL when 90 < utilization <= 95."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WPULEUS3"],
                "source": ["eia"],
                "value": [92.0],
                "unit": ["percent"],
            }
        )

        signal = eia_collector.calculate_utilization_signal(df)
        assert signal == "NORMAL"

    def test_signal_normal_at_boundary(self, eia_collector: EIACollector) -> None:
        """Test signal is SOFT at exactly 90% (threshold is >90)."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WPULEUS3"],
                "source": ["eia"],
                "value": [90.0],  # Exactly at threshold
                "unit": ["percent"],
            }
        )

        signal = eia_collector.calculate_utilization_signal(df)
        assert signal == "SOFT"  # 90.0 is not > 90, so falls to SOFT

    def test_signal_soft_between_85_and_90(self, eia_collector: EIACollector) -> None:
        """Test signal is SOFT when 85 < utilization <= 90."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WPULEUS3"],
                "source": ["eia"],
                "value": [87.5],
                "unit": ["percent"],
            }
        )

        signal = eia_collector.calculate_utilization_signal(df)
        assert signal == "SOFT"

    def test_signal_soft_at_boundary(self, eia_collector: EIACollector) -> None:
        """Test signal is WEAK at exactly 85% (threshold is >85)."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WPULEUS3"],
                "source": ["eia"],
                "value": [85.0],  # Exactly at threshold
                "unit": ["percent"],
            }
        )

        signal = eia_collector.calculate_utilization_signal(df)
        assert signal == "WEAK"  # 85.0 is not > 85, so falls to WEAK

    def test_signal_weak_below_85(self, eia_collector: EIACollector) -> None:
        """Test signal is WEAK when utilization <= 85%."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["WPULEUS3"],
                "source": ["eia"],
                "value": [80.0],
                "unit": ["percent"],
            }
        )

        signal = eia_collector.calculate_utilization_signal(df)
        assert signal == "WEAK"

    def test_signal_uses_latest_value(self, eia_collector: EIACollector) -> None:
        """Test signal calculation uses the latest timestamp value."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-01-15"]),
                "series_id": ["WPULEUS3"] * 3,
                "source": ["eia"] * 3,
                "value": [96.0, 88.0, 92.0],  # Out of order timestamps
                "unit": ["percent"] * 3,
            }
        )

        signal = eia_collector.calculate_utilization_signal(df)
        # Feb 1 is latest, value=88.0 which is SOFT
        assert signal == "SOFT"

    def test_signal_raises_on_missing_us_series(
        self, eia_collector: EIACollector
    ) -> None:
        """Test signal calculation raises ValueError if US series is missing."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2026-02-05"]),
                "series_id": ["W_NA_YUP_R30_PER"],  # PADD 3, not US
                "source": ["eia"],
                "value": [92.0],
                "unit": ["percent"],
            }
        )

        with pytest.raises(ValueError, match="US refinery utilization series"):
            eia_collector.calculate_utilization_signal(df)

    def test_signal_raises_on_empty_dataframe(
        self, eia_collector: EIACollector
    ) -> None:
        """Test signal calculation raises ValueError on empty DataFrame."""
        df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with pytest.raises(ValueError, match="US refinery utilization series"):
            eia_collector.calculate_utilization_signal(df)

    def test_signal_with_multiple_series(self, eia_collector: EIACollector) -> None:
        """Test signal calculation works with multiple series in DataFrame."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    ["2026-02-05", "2026-02-05", "2026-02-05", "2026-02-05"]
                ),
                "series_id": [
                    "WPULEUS3",
                    "W_NA_YUP_R10_PER",
                    "W_NA_YUP_R30_PER",
                    "W_NA_YUP_R50_PER",
                ],
                "source": ["eia"] * 4,
                "value": [93.0, 88.0, 97.0, 91.0],  # US at 93% = NORMAL
                "unit": ["percent"] * 4,
            }
        )

        signal = eia_collector.calculate_utilization_signal(df)
        # Should only use US series (93% = NORMAL), not PADD 3's 97%
        assert signal == "NORMAL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
