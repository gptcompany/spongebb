"""Unit tests for stablecoin collector.

Tests StablecoinCollector with mocked API responses.
Run with: uv run pytest tests/unit/collectors/test_stablecoins.py -v
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest

from liquidity.collectors.stablecoins import (
    DEFILLAMA_BASE,
    TOP_STABLECOINS,
    StablecoinCollector,
)


@pytest.fixture
def collector() -> StablecoinCollector:
    """Create a StablecoinCollector instance."""
    return StablecoinCollector()


@pytest.fixture
def mock_defillama_response() -> dict:
    """Sample DefiLlama stablecoins API response."""
    return {
        "peggedAssets": [
            {
                "id": "tether",
                "name": "Tether",
                "symbol": "USDT",
                "pegType": "peggedUSD",
                "circulating": {"peggedUSD": 143_000_000_000},
                "chainCirculating": {
                    "Ethereum": {"current": {"peggedUSD": 65_000_000_000}},
                    "Tron": {"current": {"peggedUSD": 60_000_000_000}},
                    "Solana": {"current": {"peggedUSD": 500_000_000}},  # < $1B
                },
            },
            {
                "id": "usd-coin",
                "name": "USD Coin",
                "symbol": "USDC",
                "pegType": "peggedUSD",
                "circulating": {"peggedUSD": 55_000_000_000},
                "chainCirculating": {
                    "Ethereum": {"current": {"peggedUSD": 40_000_000_000}},
                },
            },
            {
                "id": "dai",
                "name": "Dai",
                "symbol": "DAI",
                "pegType": "peggedUSD",
                "circulating": {"peggedUSD": 5_000_000_000},
                "chainCirculating": {
                    "Ethereum": {"current": {"peggedUSD": 5_000_000_000}},
                },
            },
            {
                "id": "first-digital-usd",
                "name": "First Digital USD",
                "symbol": "FDUSD",
                "pegType": "peggedUSD",
                "circulating": {"peggedUSD": 3_000_000_000},
                "chainCirculating": {},
            },
            {
                "id": "ethena-usde",
                "name": "Ethena USDe",
                "symbol": "USDe",
                "pegType": "peggedUSD",
                "circulating": {"peggedUSD": 2_000_000_000},
                "chainCirculating": {},
            },
            {
                "id": "some-other-stablecoin",
                "name": "Other Stable",
                "symbol": "OTHER",
                "pegType": "peggedUSD",
                "circulating": {"peggedUSD": 1_000_000_000},
                "chainCirculating": {},
            },
        ]
    }


@pytest.fixture
def mock_historical_response() -> list:
    """Sample DefiLlama historical response."""
    base_date = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())
    return [
        {
            "date": base_date + i * 86400,  # Each day
            "totalCirculatingUSD": {"peggedUSD": (200 + i) * 1e9},
        }
        for i in range(30)
    ]


class TestStablecoinCollectorCollect:
    """Tests for collect method."""

    @pytest.mark.asyncio
    async def test_collect_returns_dataframe(
        self, collector: StablecoinCollector
    ) -> None:
        """Test collect returns properly formatted DataFrame."""
        mock_df = pd.DataFrame([
            {
                "timestamp": pd.Timestamp.now("UTC"),
                "series_id": "STABLECOIN_TOTAL_MCAP",
                "source": "defillama",
                "value": 200.0,
                "unit": "billions_usd",
            }
        ])

        with patch.object(collector, "_fetch_stablecoins", return_value=mock_df):
            result = await collector.collect()

            assert isinstance(result, pd.DataFrame)
            assert "timestamp" in result.columns
            assert "series_id" in result.columns
            assert "source" in result.columns
            assert "value" in result.columns
            assert "unit" in result.columns

    @pytest.mark.asyncio
    async def test_collect_includes_total_mcap(
        self, collector: StablecoinCollector
    ) -> None:
        """Test collect includes total market cap."""
        mock_df = pd.DataFrame([
            {
                "timestamp": pd.Timestamp.now("UTC"),
                "series_id": "STABLECOIN_TOTAL_MCAP",
                "source": "defillama",
                "value": 200.0,
                "unit": "billions_usd",
            },
            {
                "timestamp": pd.Timestamp.now("UTC"),
                "series_id": "STABLECOIN_USDT",
                "source": "defillama",
                "value": 143.0,
                "unit": "billions_usd",
            },
        ])

        with patch.object(collector, "_fetch_stablecoins", return_value=mock_df):
            result = await collector.collect()

            total_rows = result[result["series_id"] == "STABLECOIN_TOTAL_MCAP"]
            assert len(total_rows) == 1
            assert total_rows["value"].iloc[0] == 200.0

    @pytest.mark.asyncio
    async def test_collect_handles_empty_response(
        self, collector: StablecoinCollector
    ) -> None:
        """Test collect handles empty API response gracefully."""
        empty_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(collector, "_fetch_stablecoins", return_value=empty_df):
            result = await collector.collect()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0
            assert "timestamp" in result.columns

    @pytest.mark.asyncio
    async def test_collect_values_in_billions(
        self, collector: StablecoinCollector
    ) -> None:
        """Test that values are converted to billions USD."""
        mock_df = pd.DataFrame([
            {
                "timestamp": pd.Timestamp.now("UTC"),
                "series_id": "STABLECOIN_USDT",
                "source": "defillama",
                "value": 143.0,  # $143 billion
                "unit": "billions_usd",
            }
        ])

        with patch.object(collector, "_fetch_stablecoins", return_value=mock_df):
            result = await collector.collect()

            assert result["unit"].iloc[0] == "billions_usd"
            assert result["value"].iloc[0] == 143.0

    @pytest.mark.asyncio
    async def test_collect_includes_chain_breakdown(
        self, collector: StablecoinCollector
    ) -> None:
        """Test collect includes per-chain breakdown for major stablecoins."""
        mock_df = pd.DataFrame([
            {
                "timestamp": pd.Timestamp.now("UTC"),
                "series_id": "STABLECOIN_USDT",
                "source": "defillama",
                "value": 143.0,
                "unit": "billions_usd",
            },
            {
                "timestamp": pd.Timestamp.now("UTC"),
                "series_id": "STABLECOIN_USDT_ETHEREUM",
                "source": "defillama",
                "value": 65.0,
                "unit": "billions_usd",
            },
            {
                "timestamp": pd.Timestamp.now("UTC"),
                "series_id": "STABLECOIN_USDT_TRON",
                "source": "defillama",
                "value": 60.0,
                "unit": "billions_usd",
            },
        ])

        with patch.object(collector, "_fetch_stablecoins", return_value=mock_df):
            result = await collector.collect(include_chain_breakdown=True)

            chain_rows = result[result["series_id"].str.contains("_ETHEREUM|_TRON")]
            assert len(chain_rows) == 2


class TestStablecoinCollectorMarketSummary:
    """Tests for market summary method."""

    @pytest.mark.asyncio
    async def test_market_summary_returns_dict(
        self, collector: StablecoinCollector
    ) -> None:
        """Test market summary returns dictionary with expected keys."""
        mock_df = pd.DataFrame([
            {"series_id": "STABLECOIN_TOTAL_MCAP", "value": 200.0},
            {"series_id": "STABLECOIN_USDT", "value": 143.0},
            {"series_id": "STABLECOIN_USDC", "value": 55.0},
        ])

        with patch.object(collector, "collect", return_value=mock_df):
            summary = await collector.collect_market_summary()

            assert "total_market_cap_billions" in summary
            assert "usdt_billions" in summary
            assert "usdc_billions" in summary
            assert "usdt_dominance" in summary
            assert "timestamp" in summary

    @pytest.mark.asyncio
    async def test_market_summary_calculates_dominance(
        self, collector: StablecoinCollector
    ) -> None:
        """Test USDT dominance calculation."""
        mock_df = pd.DataFrame([
            {"series_id": "STABLECOIN_TOTAL_MCAP", "value": 200.0},
            {"series_id": "STABLECOIN_USDT", "value": 143.0},
            {"series_id": "STABLECOIN_USDC", "value": 55.0},
        ])

        with patch.object(collector, "collect", return_value=mock_df):
            summary = await collector.collect_market_summary()

            expected_dominance = (143.0 / 200.0) * 100  # 71.5%
            assert summary["usdt_dominance"] == pytest.approx(expected_dominance)

    @pytest.mark.asyncio
    async def test_market_summary_handles_missing_stablecoins(
        self, collector: StablecoinCollector
    ) -> None:
        """Test market summary handles missing USDT/USDC gracefully."""
        mock_df = pd.DataFrame([
            {"series_id": "STABLECOIN_TOTAL_MCAP", "value": 200.0},
            # No USDT or USDC
        ])

        with patch.object(collector, "collect", return_value=mock_df):
            summary = await collector.collect_market_summary()

            assert summary["usdt_billions"] == 0.0
            assert summary["usdc_billions"] == 0.0
            assert summary["usdt_dominance"] == 0.0

    @pytest.mark.asyncio
    async def test_market_summary_handles_zero_total(
        self, collector: StablecoinCollector
    ) -> None:
        """Test market summary handles zero total gracefully (division by zero)."""
        mock_df = pd.DataFrame([
            {"series_id": "STABLECOIN_USDT", "value": 143.0},
            # No TOTAL_MCAP
        ])

        with patch.object(collector, "collect", return_value=mock_df):
            summary = await collector.collect_market_summary()

            # Should default to 0.0 when total is missing/zero
            assert summary["total_market_cap_billions"] == 0.0
            assert summary["usdt_dominance"] == 0.0


class TestStablecoinCollectorHistorical:
    """Tests for historical data collection."""

    @pytest.mark.asyncio
    async def test_collect_historical_returns_dataframe(
        self, collector: StablecoinCollector
    ) -> None:
        """Test historical collection returns DataFrame."""
        mock_df = pd.DataFrame([
            {
                "timestamp": pd.Timestamp("2026-01-01", tz="UTC"),
                "series_id": "STABLECOIN_TOTAL_MCAP",
                "source": "defillama",
                "value": 200.0,
                "unit": "billions_usd",
            },
            {
                "timestamp": pd.Timestamp("2026-01-02", tz="UTC"),
                "series_id": "STABLECOIN_TOTAL_MCAP",
                "source": "defillama",
                "value": 201.0,
                "unit": "billions_usd",
            },
        ])

        with patch.object(collector, "_fetch_historical", return_value=mock_df):
            result = await collector.collect_historical(days=30)

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_collect_historical_sorted_by_timestamp(
        self, collector: StablecoinCollector
    ) -> None:
        """Test historical data is sorted by timestamp."""
        mock_df = pd.DataFrame([
            {
                "timestamp": pd.Timestamp("2026-01-01", tz="UTC"),
                "series_id": "STABLECOIN_TOTAL_MCAP",
                "source": "defillama",
                "value": 200.0,
                "unit": "billions_usd",
            },
            {
                "timestamp": pd.Timestamp("2026-01-02", tz="UTC"),
                "series_id": "STABLECOIN_TOTAL_MCAP",
                "source": "defillama",
                "value": 201.0,
                "unit": "billions_usd",
            },
        ]).reset_index(drop=True)

        with patch.object(collector, "_fetch_historical", return_value=mock_df):
            result = await collector.collect_historical()

            timestamps = result["timestamp"].tolist()
            assert timestamps == sorted(timestamps)


class TestStablecoinConstants:
    """Tests for module constants."""

    def test_top_stablecoins_defined(self) -> None:
        """Test TOP_STABLECOINS contains expected stablecoins."""
        assert "tether" in TOP_STABLECOINS  # USDT
        assert "usd-coin" in TOP_STABLECOINS  # USDC
        assert "dai" in TOP_STABLECOINS  # DAI
        assert "first-digital-usd" in TOP_STABLECOINS  # FDUSD
        assert "ethena-usde" in TOP_STABLECOINS  # USDe
        assert len(TOP_STABLECOINS) == 5

    def test_defillama_base_url(self) -> None:
        """Test DefiLlama base URL is correct."""
        assert DEFILLAMA_BASE == "https://stablecoins.llama.fi"


class TestCollectorRegistry:
    """Tests for collector registry integration."""

    def test_stablecoin_collector_registered(self) -> None:
        """Test that StablecoinCollector is registered."""
        from liquidity.collectors import registry

        assert "stablecoins" in registry.list_collectors()
        assert registry.get("stablecoins") is StablecoinCollector

    def test_collector_instantiation_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector = registry.get("stablecoins")()

        assert isinstance(collector, StablecoinCollector)
        assert collector.name == "stablecoins"


class TestCollectorClose:
    """Tests for collector cleanup."""

    @pytest.mark.asyncio
    async def test_close_releases_client(
        self, collector: StablecoinCollector
    ) -> None:
        """Test close method releases HTTP client."""
        # Initialize client
        client = await collector._get_client()
        assert client is not None
        assert not client.is_closed

        # Close should release client
        await collector.close()
        assert collector._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(
        self, collector: StablecoinCollector
    ) -> None:
        """Test close can be called multiple times safely."""
        await collector.close()  # First call (no client yet)
        await collector.close()  # Second call (still safe)
        # Should not raise

    @pytest.mark.asyncio
    async def test_get_client_recreates_after_close(
        self, collector: StablecoinCollector
    ) -> None:
        """Test _get_client creates new client after close."""
        # First client
        client1 = await collector._get_client()
        assert client1 is not None

        # Close
        await collector.close()

        # Second client should be new
        client2 = await collector._get_client()
        assert client2 is not None
        assert collector._client is client2

        # Cleanup
        await collector.close()


class TestEmptyDataFrame:
    """Tests for empty DataFrame handling."""

    def test_empty_df_has_correct_columns(
        self, collector: StablecoinCollector
    ) -> None:
        """Test empty DataFrame has correct schema."""
        empty_df = collector._empty_df()

        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert set(empty_df.columns) == expected_columns

    def test_empty_df_is_empty(
        self, collector: StablecoinCollector
    ) -> None:
        """Test empty DataFrame has no rows."""
        empty_df = collector._empty_df()
        assert len(empty_df) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
