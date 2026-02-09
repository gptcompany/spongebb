"""Unit tests for CFTC COT (Commitment of Traders) collector.

Tests CFTCCOTCollector with mocked httpx responses.
Run with: uv run pytest tests/unit/collectors/test_cftc_cot.py -v
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from liquidity.collectors.cftc_cot import (
    COMMODITY_MAP,
    POSITION_FIELDS,
    CFTCCOTCollector,
)


@pytest.fixture
def cftc_collector() -> CFTCCOTCollector:
    """Create a CFTC COT collector instance with mock settings."""
    with patch("liquidity.collectors.cftc_cot.get_settings") as mock_settings:
        mock_settings.return_value.circuit_breaker.threshold = 5
        mock_settings.return_value.circuit_breaker.ttl = 60
        mock_settings.return_value.retry.max_attempts = 3
        mock_settings.return_value.retry.multiplier = 1.0
        mock_settings.return_value.retry.min_wait = 1
        mock_settings.return_value.retry.max_wait = 10
        return CFTCCOTCollector()


@pytest.fixture
def mock_wti_response() -> list[dict]:
    """Sample WTI crude oil COT response from CFTC."""
    return [
        {
            "id": "260204067F",
            "report_date_as_yyyy_mm_dd": "2026-02-04T00:00:00.000",
            "market_and_exchange_names": "CRUDE OIL, LIGHT SWEET-WTI - NEW YORK MERCANTILE EXCHANGE",
            "cftc_commodity_code": "067",
            "contract_market_name": "CRUDE OIL, LIGHT SWEET-WTI",
            "cftc_market_code": "NYME",
            "open_interest_all": "1500000",
            "prod_merc_positions_long": "350000",
            "prod_merc_positions_short": "520000",
            "m_money_positions_long_all": "420000",
            "m_money_positions_short_all": "180000",
            "swap_positions_long_all": "280000",
            "swap__positions_short_all": "340000",
        },
        {
            "id": "260128067F",
            "report_date_as_yyyy_mm_dd": "2026-01-28T00:00:00.000",
            "market_and_exchange_names": "CRUDE OIL, LIGHT SWEET-WTI - NEW YORK MERCANTILE EXCHANGE",
            "cftc_commodity_code": "067",
            "contract_market_name": "CRUDE OIL, LIGHT SWEET-WTI",
            "cftc_market_code": "NYME",
            "open_interest_all": "1480000",
            "prod_merc_positions_long": "345000",
            "prod_merc_positions_short": "515000",
            "m_money_positions_long_all": "410000",
            "m_money_positions_short_all": "175000",
            "swap_positions_long_all": "275000",
            "swap__positions_short_all": "335000",
        },
    ]


@pytest.fixture
def mock_gold_response() -> list[dict]:
    """Sample Gold COT response from CFTC."""
    return [
        {
            "id": "260204088F",
            "report_date_as_yyyy_mm_dd": "2026-02-04T00:00:00.000",
            "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
            "cftc_commodity_code": "088",
            "contract_market_name": "GOLD",
            "cftc_market_code": "CMX",
            "open_interest_all": "520000",
            "prod_merc_positions_long": "45000",
            "prod_merc_positions_short": "120000",
            "m_money_positions_long_all": "280000",
            "m_money_positions_short_all": "65000",
            "swap_positions_long_all": "85000",
            "swap__positions_short_all": "135000",
        },
    ]


class TestCommodityMapping:
    """Tests for CFTC commodity mapping constants."""

    def test_commodity_map_contains_key_commodities(self) -> None:
        """Test COMMODITY_MAP contains required commodities."""
        required = ["WTI", "GOLD", "COPPER", "SILVER", "NATGAS"]
        for commodity in required:
            assert commodity in COMMODITY_MAP

    def test_commodity_map_has_required_fields(self) -> None:
        """Test each commodity has code, contract, and market fields."""
        for commodity, info in COMMODITY_MAP.items():
            assert "code" in info, f"Missing 'code' for {commodity}"
            assert "contract" in info, f"Missing 'contract' for {commodity}"
            assert "market" in info, f"Missing 'market' for {commodity}"

    def test_wti_mapping_values(self) -> None:
        """Test WTI commodity mapping values are correct."""
        assert COMMODITY_MAP["WTI"]["code"] == "067"
        assert COMMODITY_MAP["WTI"]["contract"] == "CRUDE OIL, LIGHT SWEET-WTI"
        assert COMMODITY_MAP["WTI"]["market"] == "NYME"

    def test_gold_mapping_values(self) -> None:
        """Test Gold commodity mapping values are correct."""
        assert COMMODITY_MAP["GOLD"]["code"] == "088"
        assert COMMODITY_MAP["GOLD"]["contract"] == "GOLD"
        assert COMMODITY_MAP["GOLD"]["market"] == "CMX"

    def test_copper_mapping_values(self) -> None:
        """Test Copper commodity mapping values are correct."""
        assert COMMODITY_MAP["COPPER"]["code"] == "085"
        assert COMMODITY_MAP["COPPER"]["contract"] == "COPPER- #1"
        assert COMMODITY_MAP["COPPER"]["market"] == "CMX"


class TestPositionFields:
    """Tests for position field mapping constants."""

    def test_position_fields_contains_required_fields(self) -> None:
        """Test POSITION_FIELDS contains all required position types."""
        required = [
            "comm_long",
            "comm_short",
            "spec_long",
            "spec_short",
            "swap_long",
            "swap_short",
            "open_interest",
        ]
        for field in required:
            assert field in POSITION_FIELDS

    def test_swap_short_has_double_underscore(self) -> None:
        """Test swap_short maps to field with double underscore (API quirk)."""
        assert POSITION_FIELDS["swap_short"] == "swap__positions_short_all"


class TestCFTCCOTCollectorInit:
    """Tests for CFTCCOTCollector initialization."""

    def test_collector_name_default(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test default collector name is 'cftc_cot'."""
        assert cftc_collector.name == "cftc_cot"

    def test_collector_base_url(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test BASE_URL is correct Socrata endpoint."""
        assert CFTCCOTCollector.BASE_URL == "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"

    def test_collector_commodity_map_attached(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test COMMODITY_MAP is attached to class."""
        assert CFTCCOTCollector.COMMODITY_MAP == COMMODITY_MAP


class TestSafeIntParsing:
    """Tests for _safe_int method."""

    def test_safe_int_with_integer(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test _safe_int handles integer input."""
        assert cftc_collector._safe_int(42) == 42

    def test_safe_int_with_string(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test _safe_int handles string input."""
        assert cftc_collector._safe_int("12345") == 12345

    def test_safe_int_with_string_spaces(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test _safe_int handles string with whitespace."""
        assert cftc_collector._safe_int("  12345  ") == 12345

    def test_safe_int_with_none(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test _safe_int returns default for None."""
        assert cftc_collector._safe_int(None) == 0
        assert cftc_collector._safe_int(None, default=99) == 99

    def test_safe_int_with_invalid_string(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test _safe_int returns default for invalid string."""
        assert cftc_collector._safe_int("not_a_number") == 0
        assert cftc_collector._safe_int("1.5.3", default=10) == 10


class TestResponseParsing:
    """Tests for CFTC API response parsing."""

    @pytest.mark.asyncio
    async def test_collect_returns_dataframe(
        self, cftc_collector: CFTCCOTCollector, mock_wti_response: list[dict]
    ) -> None:
        """Test collect returns properly formatted DataFrame."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wti_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect(commodities=["WTI"], weeks=2)

            assert isinstance(result, pd.DataFrame)
            assert len(result) > 0
            assert "timestamp" in result.columns
            assert "series_id" in result.columns
            assert "source" in result.columns
            assert "value" in result.columns
            assert "unit" in result.columns

    @pytest.mark.asyncio
    async def test_collect_correct_source(
        self, cftc_collector: CFTCCOTCollector, mock_wti_response: list[dict]
    ) -> None:
        """Test collect sets source to 'cftc'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wti_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect(commodities=["WTI"])

            assert all(result["source"] == "cftc")

    @pytest.mark.asyncio
    async def test_collect_correct_unit(
        self, cftc_collector: CFTCCOTCollector, mock_wti_response: list[dict]
    ) -> None:
        """Test collect sets unit to 'contracts'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wti_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect(commodities=["WTI"])

            assert all(result["unit"] == "contracts")

    @pytest.mark.asyncio
    async def test_collect_calculates_net_positions(
        self, cftc_collector: CFTCCOTCollector, mock_wti_response: list[dict]
    ) -> None:
        """Test collect correctly calculates net positions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wti_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect(commodities=["WTI"], weeks=2)

            # Check commercial net = long - short = 350000 - 520000 = -170000
            comm_net = result[result["series_id"] == "cot_wti_comm_net"]
            assert -170000 in comm_net["value"].values

            # Check speculator net = long - short = 420000 - 180000 = 240000
            spec_net = result[result["series_id"] == "cot_wti_spec_net"]
            assert 240000 in spec_net["value"].values

            # Check swap net = long - short = 280000 - 340000 = -60000
            swap_net = result[result["series_id"] == "cot_wti_swap_net"]
            assert -60000 in swap_net["value"].values

    @pytest.mark.asyncio
    async def test_collect_includes_open_interest(
        self, cftc_collector: CFTCCOTCollector, mock_wti_response: list[dict]
    ) -> None:
        """Test collect includes open interest."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wti_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect(commodities=["WTI"], weeks=2)

            oi = result[result["series_id"] == "cot_wti_oi"]
            assert 1500000 in oi["value"].values

    @pytest.mark.asyncio
    async def test_collect_includes_raw_long_short(
        self, cftc_collector: CFTCCOTCollector, mock_wti_response: list[dict]
    ) -> None:
        """Test collect includes raw long/short positions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wti_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect(commodities=["WTI"], weeks=2)

            # Check raw positions are included
            comm_long = result[result["series_id"] == "cot_wti_comm_long"]
            assert 350000 in comm_long["value"].values

            spec_short = result[result["series_id"] == "cot_wti_spec_short"]
            assert 180000 in spec_short["value"].values


class TestMultipleCommodities:
    """Tests for collecting multiple commodities."""

    @pytest.mark.asyncio
    async def test_collect_multiple_commodities(
        self,
        cftc_collector: CFTCCOTCollector,
        mock_wti_response: list[dict],
        mock_gold_response: list[dict],
    ) -> None:
        """Test collecting multiple commodities in one call."""

        def mock_get_response(_url: str, params: dict):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            # Return different data based on commodity code in params
            if "'067'" in params.get("$where", ""):
                mock_resp.json.return_value = mock_wti_response
            else:
                mock_resp.json.return_value = mock_gold_response
            return mock_resp

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=mock_get_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect(commodities=["WTI", "GOLD"], weeks=2)

            # Should have data for both commodities
            series_ids = result["series_id"].unique()
            wti_series = [s for s in series_ids if "wti" in s]
            gold_series = [s for s in series_ids if "gold" in s]

            assert len(wti_series) > 0
            assert len(gold_series) > 0


class TestEmptyResponses:
    """Tests for handling empty or error responses."""

    @pytest.mark.asyncio
    async def test_collect_empty_response(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test collect handles empty API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []  # Empty response
        mock_response.raise_for_status = MagicMock()

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect(commodities=["WTI"])

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0
            assert "timestamp" in result.columns


class TestInputValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_collect_invalid_commodity_raises(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test collect raises ValueError for invalid commodity."""
        with pytest.raises(ValueError, match="Unknown commodities"):
            await cftc_collector.collect(commodities=["INVALID"])

    @pytest.mark.asyncio
    async def test_collect_partial_invalid_raises(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test collect raises ValueError when any commodity is invalid."""
        with pytest.raises(ValueError, match="Unknown commodities"):
            await cftc_collector.collect(commodities=["WTI", "INVALID"])

    @pytest.mark.asyncio
    async def test_collect_default_commodities(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test collect uses all commodities when not specified."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            await cftc_collector.collect()

            # Should be called 5 times (once for each commodity)
            assert mock_client.get.call_count == 5


class TestDateFiltering:
    """Tests for date parameter handling."""

    @pytest.mark.asyncio
    async def test_collect_with_date_range(
        self, cftc_collector: CFTCCOTCollector, mock_wti_response: list[dict]
    ) -> None:
        """Test collect with explicit start_date and end_date."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wti_response
        mock_response.raise_for_status = MagicMock()

        start = date(2026, 1, 1)
        end = date(2026, 2, 1)

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect(
                commodities=["WTI"], start_date=start, end_date=end
            )

            assert isinstance(result, pd.DataFrame)
            # Verify date params were included in query
            mock_client.get.assert_called()
            call_args = mock_client.get.call_args
            params = call_args.kwargs.get("params", {})
            assert "2026-01-01" in params.get("$where", "")
            assert "2026-02-01" in params.get("$where", "")


class TestConvenienceMethods:
    """Tests for convenience methods."""

    @pytest.mark.asyncio
    async def test_collect_single(
        self, cftc_collector: CFTCCOTCollector, mock_gold_response: list[dict]
    ) -> None:
        """Test collect_single convenience method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_gold_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await cftc_collector.collect_single("GOLD", weeks=26)

            assert isinstance(result, pd.DataFrame)
            # Should only have gold series
            series_ids = result["series_id"].unique()
            assert all("gold" in s for s in series_ids)

    def test_get_latest(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test get_latest extracts latest values correctly."""
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    ["2026-02-04", "2026-02-04", "2026-02-04", "2026-02-04"]
                ),
                "series_id": [
                    "cot_wti_comm_net",
                    "cot_wti_spec_net",
                    "cot_wti_swap_net",
                    "cot_wti_oi",
                ],
                "source": ["cftc"] * 4,
                "value": [-170000, 240000, -60000, 1500000],
                "unit": ["contracts"] * 4,
            }
        )

        result = cftc_collector.get_latest(df, "WTI")

        assert result["comm_net"] == -170000
        assert result["spec_net"] == 240000
        assert result["swap_net"] == -60000
        assert result["oi"] == 1500000


class TestCollectorRegistry:
    """Tests for collector registry integration."""

    def test_cftc_cot_collector_registered(self) -> None:
        """Test that CFTC COT collector is registered."""
        from liquidity.collectors import registry

        assert "cftc_cot" in registry.list_collectors()
        assert registry.get("cftc_cot") is CFTCCOTCollector

    def test_collector_instantiation_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        with patch("liquidity.collectors.cftc_cot.get_settings") as mock_settings:
            mock_settings.return_value.circuit_breaker.threshold = 5
            mock_settings.return_value.circuit_breaker.ttl = 60
            mock_settings.return_value.retry.max_attempts = 3
            mock_settings.return_value.retry.multiplier = 1.0
            mock_settings.return_value.retry.min_wait = 1
            mock_settings.return_value.retry.max_wait = 10

            collector = registry.get("cftc_cot")()

            assert isinstance(collector, CFTCCOTCollector)
            assert collector.name == "cftc_cot"


class TestCollectorClose:
    """Tests for collector cleanup."""

    @pytest.mark.asyncio
    async def test_close_releases_client(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test close method releases HTTP client."""
        # Initialize client by calling _get_client
        client = await cftc_collector._get_client()
        assert client is not None
        assert not client.is_closed

        # Close should release client
        await cftc_collector.close()
        assert cftc_collector._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self, cftc_collector: CFTCCOTCollector) -> None:
        """Test close can be called multiple times safely."""
        await cftc_collector.close()  # First call (no client yet)
        await cftc_collector.close()  # Second call (still safe)
        # Should not raise


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_http_error_returns_empty_df(
        self, cftc_collector: CFTCCOTCollector
    ) -> None:
        """Test single commodity HTTP error returns empty DataFrame (graceful degradation)."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            # When a single commodity fails, collector returns empty df
            result = await cftc_collector.collect(commodities=["WTI"])
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_partial_failure_returns_available_data(
        self, cftc_collector: CFTCCOTCollector, mock_wti_response: list[dict]
    ) -> None:
        """Test partial commodity failure returns available data."""
        import httpx

        # First call succeeds, second fails
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = mock_wti_response
        mock_success.raise_for_status = MagicMock()

        mock_failure = MagicMock()
        mock_failure.status_code = 500
        mock_failure.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_failure
        )

        with patch.object(cftc_collector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            # Return success for WTI, failure for GOLD
            mock_client.get = AsyncMock(side_effect=[mock_success, mock_failure])
            mock_get_client.return_value = mock_client

            # Even though GOLD fails, we should get WTI data
            result = await cftc_collector.collect(commodities=["WTI", "GOLD"])
            assert isinstance(result, pd.DataFrame)
            assert len(result) > 0
            # Should only have WTI series
            assert all("wti" in s for s in result["series_id"].unique())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
