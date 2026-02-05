"""Unit tests for NY Fed collectors.

Tests NYFedCollector and SwapLinesCollector with mocked API responses.
Run with: uv run pytest tests/unit/collectors/test_nyfed.py -v
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest

from liquidity.collectors.nyfed import NYFedCollector
from liquidity.collectors.swap_lines import SWAP_PARTNERS, SwapLinesCollector


@pytest.fixture
def nyfed_collector() -> NYFedCollector:
    """Create a NY Fed collector instance."""
    return NYFedCollector()


@pytest.fixture
def swap_collector() -> SwapLinesCollector:
    """Create a Swap Lines collector instance."""
    return SwapLinesCollector()


@pytest.fixture
def mock_rrp_response() -> dict:
    """Sample RRP API response from NY Fed."""
    return {
        "repo": {
            "operations": [
                {
                    "operationDate": "2026-02-04",
                    "operationType": "Overnight Reverse Repo",
                    "totalAmtSubmitted": 1500000000000,
                    "totalAmtAccepted": 1500000000000,
                    "awardRate": 4.55,
                },
                {
                    "operationDate": "2026-02-03",
                    "operationType": "Overnight Reverse Repo",
                    "totalAmtSubmitted": 1480000000000,
                    "totalAmtAccepted": 1480000000000,
                    "awardRate": 4.55,
                },
            ]
        }
    }


@pytest.fixture
def mock_soma_response() -> dict:
    """Sample SOMA API response from NY Fed."""
    return {
        "soma": {
            "asOfDate": "2026-02-04",
            "holdings": [
                {
                    "securityType": "Treasury Bills",
                    "parValue": 500000000000,
                },
                {
                    "securityType": "Treasury Notes and Bonds",
                    "parValue": 4500000000000,
                },
                {
                    "securityType": "Mortgage-Backed Securities",
                    "parValue": 2500000000000,
                },
            ],
        }
    }


@pytest.fixture
def mock_swap_response() -> dict:
    """Sample swap line API response from NY Fed."""
    return {
        "fxSwaps": {
            "operations": [
                {
                    "settlementDate": "2026-02-04",
                    "counterparty": "ECB",
                    "amount": 5000000000,
                },
                {
                    "settlementDate": "2026-02-04",
                    "counterparty": "BOJ",
                    "amount": 3000000000,
                },
            ]
        }
    }


class TestNYFedCollectorRRP:
    """Tests for RRP collection from NY Fed."""

    @pytest.mark.asyncio
    async def test_collect_rrp_returns_dataframe(
        self, nyfed_collector: NYFedCollector, mock_rrp_response: dict
    ) -> None:
        """Test RRP collection returns properly formatted DataFrame."""
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "RRP_DAILY",
                    "source": "nyfed",
                    "value": 1500.0,
                    "unit": "billions_usd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-03"),
                    "series_id": "RRP_DAILY",
                    "source": "nyfed",
                    "value": 1480.0,
                    "unit": "billions_usd",
                },
            ]
        )

        with patch.object(nyfed_collector, "_fetch_rrp", return_value=mock_df):
            result = await nyfed_collector.collect_rrp()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 2
            assert "timestamp" in result.columns
            assert "value" in result.columns
            assert result["series_id"].iloc[0] == "RRP_DAILY"
            assert result["source"].iloc[0] == "nyfed"
            assert result["unit"].iloc[0] == "billions_usd"

    @pytest.mark.asyncio
    async def test_collect_rrp_with_dates(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test RRP collection accepts date parameters."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 31, tzinfo=UTC)

        with patch.object(nyfed_collector, "_fetch_rrp", return_value=mock_df) as mock:
            await nyfed_collector.collect_rrp(start_date=start, end_date=end)
            mock.assert_called_once_with(start, end)

    @pytest.mark.asyncio
    async def test_collect_rrp_empty_response(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test RRP collection handles empty response."""
        empty_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(nyfed_collector, "_fetch_rrp", return_value=empty_df):
            result = await nyfed_collector.collect_rrp()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_collect_rrp_value_in_billions(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test RRP values are converted to billions."""
        # Mock with raw API response that returns trillion-scale values
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "RRP_DAILY",
                    "source": "nyfed",
                    "value": 1500.0,  # Should be 1500 billion = 1.5 trillion
                    "unit": "billions_usd",
                }
            ]
        )

        with patch.object(nyfed_collector, "_fetch_rrp", return_value=mock_df):
            result = await nyfed_collector.collect_rrp()

            # Value should be in billions
            assert result["value"].iloc[0] == 1500.0
            assert result["unit"].iloc[0] == "billions_usd"


class TestNYFedCollectorSOMA:
    """Tests for SOMA collection from NY Fed."""

    @pytest.mark.asyncio
    async def test_collect_soma_returns_dataframe(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test SOMA collection returns properly formatted DataFrame."""
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "SOMA_TREASURY_BILLS",
                    "source": "nyfed",
                    "value": 500.0,
                    "unit": "billions_usd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "SOMA_TREASURY_NOTES_AND_BONDS",
                    "source": "nyfed",
                    "value": 4500.0,
                    "unit": "billions_usd",
                },
            ]
        )

        with patch.object(nyfed_collector, "_fetch_soma", return_value=mock_df):
            result = await nyfed_collector.collect_soma()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 2
            assert "SOMA_" in result["series_id"].iloc[0]
            assert result["source"].iloc[0] == "nyfed"

    @pytest.mark.asyncio
    async def test_collect_soma_multiple_security_types(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test SOMA returns multiple security types."""
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "SOMA_TREASURY_BILLS",
                    "source": "nyfed",
                    "value": 500.0,
                    "unit": "billions_usd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "SOMA_MBS",
                    "source": "nyfed",
                    "value": 2500.0,
                    "unit": "billions_usd",
                },
            ]
        )

        with patch.object(nyfed_collector, "_fetch_soma", return_value=mock_df):
            result = await nyfed_collector.collect_soma()

            series_ids = result["series_id"].tolist()
            assert len(series_ids) >= 2


class TestNYFedCollectorGeneric:
    """Tests for generic collect method."""

    @pytest.mark.asyncio
    async def test_collect_default_is_rrp(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test generic collect defaults to RRP."""
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "RRP_DAILY",
                    "source": "nyfed",
                    "value": 1500.0,
                    "unit": "billions_usd",
                }
            ]
        )

        with patch.object(nyfed_collector, "collect_rrp", return_value=mock_df) as mock:
            await nyfed_collector.collect()
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_with_soma_type(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test generic collect with soma data_type."""
        mock_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        with patch.object(
            nyfed_collector, "collect_soma", return_value=mock_df
        ) as mock:
            await nyfed_collector.collect(data_type="soma")
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_invalid_type_raises(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test generic collect with invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown data_type"):
            await nyfed_collector.collect(data_type="invalid")


class TestSwapLinesCollector:
    """Tests for SwapLinesCollector."""

    @pytest.mark.asyncio
    async def test_collect_returns_dataframe(
        self, swap_collector: SwapLinesCollector
    ) -> None:
        """Test swap lines collection returns DataFrame."""
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "SWAP_ECB",
                    "source": "nyfed",
                    "value": 5.0,
                    "unit": "billions_usd",
                    "counterparty": "ECB",
                }
            ]
        )

        with patch.object(swap_collector, "_fetch_swap_lines", return_value=mock_df):
            result = await swap_collector.collect()

            assert isinstance(result, pd.DataFrame)
            assert "counterparty" in result.columns
            assert result["series_id"].iloc[0].startswith("SWAP_")

    @pytest.mark.asyncio
    async def test_collect_empty_in_calm_markets(
        self, swap_collector: SwapLinesCollector
    ) -> None:
        """Test swap lines handles empty response (calm markets)."""
        with patch.object(
            swap_collector, "_fetch_swap_lines", return_value=swap_collector._empty_df()
        ):
            result = await swap_collector.collect()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0
            assert "timestamp" in result.columns
            assert "counterparty" in result.columns

    @pytest.mark.asyncio
    async def test_empty_df_has_correct_schema(
        self, swap_collector: SwapLinesCollector
    ) -> None:
        """Test empty DataFrame has correct columns."""
        empty_df = swap_collector._empty_df()

        expected_columns = {
            "timestamp",
            "series_id",
            "source",
            "value",
            "unit",
            "counterparty",
        }
        assert set(empty_df.columns) == expected_columns

    def test_swap_partners_defined(self) -> None:
        """Test swap partners constant is defined correctly."""
        assert "ECB" in SWAP_PARTNERS
        assert "BOJ" in SWAP_PARTNERS
        assert "BOE" in SWAP_PARTNERS
        assert "SNB" in SWAP_PARTNERS
        assert "BOC" in SWAP_PARTNERS
        assert len(SWAP_PARTNERS) == 5


class TestCollectorRegistry:
    """Tests for collector registry integration."""

    def test_nyfed_collector_registered(self) -> None:
        """Test that NY Fed collector is registered."""
        from liquidity.collectors import registry

        assert "nyfed" in registry.list_collectors()
        assert registry.get("nyfed") is NYFedCollector

    def test_swap_lines_collector_registered(self) -> None:
        """Test that Swap Lines collector is registered."""
        from liquidity.collectors import registry

        assert "swap_lines" in registry.list_collectors()
        assert registry.get("swap_lines") is SwapLinesCollector

    def test_collector_instantiation_from_registry(self) -> None:
        """Test instantiating collectors from registry."""
        from liquidity.collectors import registry

        nyfed = registry.get("nyfed")()
        swap = registry.get("swap_lines")()

        assert isinstance(nyfed, NYFedCollector)
        assert isinstance(swap, SwapLinesCollector)
        assert nyfed.name == "nyfed"
        assert swap.name == "swap_lines"


class TestCollectorClose:
    """Tests for collector cleanup."""

    @pytest.mark.asyncio
    async def test_nyfed_close_releases_client(
        self, nyfed_collector: NYFedCollector
    ) -> None:
        """Test close method releases HTTP client."""
        # Initialize client by calling _get_client
        client = await nyfed_collector._get_client()
        assert client is not None
        assert not client.is_closed

        # Close should release client
        await nyfed_collector.close()
        assert nyfed_collector._client is None

    @pytest.mark.asyncio
    async def test_swap_close_releases_client(
        self, swap_collector: SwapLinesCollector
    ) -> None:
        """Test close method releases HTTP client."""
        # Initialize client
        client = await swap_collector._get_client()
        assert client is not None

        # Close should release client
        await swap_collector.close()
        assert swap_collector._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self, nyfed_collector: NYFedCollector) -> None:
        """Test close can be called multiple times safely."""
        await nyfed_collector.close()  # First call (no client yet)
        await nyfed_collector.close()  # Second call (still safe)
        # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
