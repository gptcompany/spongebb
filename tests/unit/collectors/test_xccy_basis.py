"""Unit tests for cross-currency basis collector.

Tests XCcyBasisCollector with mocked API responses.
Run with: uv run pytest tests/unit/collectors/test_xccy_basis.py -v
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd
import pytest

from liquidity.collectors.xccy_basis import (
    STRESS_THRESHOLDS,
    XCcyBasisCollector,
)


@pytest.fixture
def xccy_collector() -> XCcyBasisCollector:
    """Create a cross-currency basis collector instance."""
    return XCcyBasisCollector()


@pytest.fixture
def mock_ecb_response() -> dict:
    """Sample ECB SDW response for money market rates."""
    return {
        "dataSets": [
            {
                "series": {
                    "0:0:0:0:0:0:0": {
                        "observations": {
                            "0": [2.5],  # EURIBOR 2.5%
                            "1": [2.6],  # EURIBOR 2.6%
                            "2": [2.55],
                        }
                    }
                }
            }
        ],
        "structure": {
            "dimensions": {
                "observation": [
                    {
                        "values": [
                            {"id": "2026-01"},
                            {"id": "2026-02"},
                            {"id": "2026-03"},
                        ]
                    }
                ]
            }
        },
    }


@pytest.fixture
def mock_basis_df() -> pd.DataFrame:
    """Sample cross-currency basis DataFrame."""
    return pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-02-03"),
                "series_id": "XCCY_EURUSD_3M",
                "source": "ecb_sdw",
                "value": -18.5,
                "unit": "bps",
            },
            {
                "timestamp": pd.Timestamp("2026-02-04"),
                "series_id": "XCCY_EURUSD_3M",
                "source": "ecb_sdw",
                "value": -15.2,
                "unit": "bps",
            },
        ]
    )


class TestXCcyBasisCollectorBasic:
    """Basic tests for XCcyBasisCollector."""

    @pytest.mark.asyncio
    async def test_collect_returns_dataframe(
        self, xccy_collector: XCcyBasisCollector, mock_basis_df: pd.DataFrame
    ) -> None:
        """Test collection returns properly formatted DataFrame."""
        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", return_value=mock_basis_df
        ):
            result = await xccy_collector.collect()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 2
            assert "timestamp" in result.columns
            assert "series_id" in result.columns
            assert "source" in result.columns
            assert "value" in result.columns
            assert "unit" in result.columns

    @pytest.mark.asyncio
    async def test_collect_with_dates(
        self, xccy_collector: XCcyBasisCollector, mock_basis_df: pd.DataFrame
    ) -> None:
        """Test collection accepts date parameters."""
        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 12, 31, tzinfo=UTC)

        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", return_value=mock_basis_df
        ) as mock:
            await xccy_collector.collect(start_date=start, end_date=end, tenor="3M")
            mock.assert_called_once_with(start, end, "3M")

    @pytest.mark.asyncio
    async def test_collect_with_tenor(
        self, xccy_collector: XCcyBasisCollector, mock_basis_df: pd.DataFrame
    ) -> None:
        """Test collection accepts tenor parameter."""
        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", return_value=mock_basis_df
        ) as mock:
            await xccy_collector.collect(tenor="1Y")
            # Verify tenor was passed
            call_args = mock.call_args
            assert call_args[0][2] == "1Y"  # Third positional argument

    @pytest.mark.asyncio
    async def test_collect_series_id_format(
        self, xccy_collector: XCcyBasisCollector, mock_basis_df: pd.DataFrame
    ) -> None:
        """Test series_id follows expected format."""
        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", return_value=mock_basis_df
        ):
            result = await xccy_collector.collect()

            assert all(s.startswith("XCCY_EURUSD_") for s in result["series_id"])

    @pytest.mark.asyncio
    async def test_collect_unit_is_bps(
        self, xccy_collector: XCcyBasisCollector, mock_basis_df: pd.DataFrame
    ) -> None:
        """Test values are in basis points."""
        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", return_value=mock_basis_df
        ):
            result = await xccy_collector.collect()

            assert (result["unit"] == "bps").all()


class TestXCcyBasisCollectorFallback:
    """Tests for fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_to_calculated_on_ecb_failure(
        self, xccy_collector: XCcyBasisCollector, mock_basis_df: pd.DataFrame
    ) -> None:
        """Test fallback to calculated spread when ECB fails."""
        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", side_effect=Exception("ECB error")
        ), patch.object(
            xccy_collector,
            "_fetch_calculated_spread",
            return_value=mock_basis_df,
        ) as mock_calc:
            result = await xccy_collector.collect()

            mock_calc.assert_called_once()
            assert isinstance(result, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_fallback_to_cached_on_all_failures(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test fallback to cached baseline when all sources fail."""
        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", side_effect=Exception("ECB error")
        ), patch.object(
            xccy_collector,
            "_fetch_calculated_spread",
            side_effect=Exception("Calc error"),
        ):
            result = await xccy_collector.collect()

            # Should return cached baseline
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1
            assert result["source"].iloc[0] == "cached_baseline"
            assert result["value"].iloc[0] == xccy_collector.BASELINE_VALUE

    @pytest.mark.asyncio
    async def test_cached_baseline_has_stale_flag(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test cached baseline includes stale flag."""
        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", side_effect=Exception("error")
        ), patch.object(
            xccy_collector, "_fetch_calculated_spread", side_effect=Exception("error")
        ):
            result = await xccy_collector.collect()

            assert "stale" in result.columns
            assert bool(result["stale"].iloc[0]) is True


class TestStressClassification:
    """Tests for stress level classification."""

    def test_classify_stress_normal(self) -> None:
        """Test classification of normal conditions (positive basis)."""
        assert XCcyBasisCollector.classify_stress(10) == "normal"
        assert XCcyBasisCollector.classify_stress(5) == "normal"
        assert XCcyBasisCollector.classify_stress(0.1) == "normal"

    def test_classify_stress_mild(self) -> None:
        """Test classification of mild stress (-10 to 0 bps)."""
        assert XCcyBasisCollector.classify_stress(-5) == "mild"
        assert XCcyBasisCollector.classify_stress(-9.9) == "mild"
        assert XCcyBasisCollector.classify_stress(0) == "mild"

    def test_classify_stress_moderate(self) -> None:
        """Test classification of moderate stress (-30 to -10 bps)."""
        assert XCcyBasisCollector.classify_stress(-10) == "moderate"
        assert XCcyBasisCollector.classify_stress(-15) == "moderate"
        assert XCcyBasisCollector.classify_stress(-20) == "moderate"
        assert XCcyBasisCollector.classify_stress(-29.9) == "moderate"

    def test_classify_stress_severe(self) -> None:
        """Test classification of severe stress (< -30 bps)."""
        assert XCcyBasisCollector.classify_stress(-30) == "severe"
        assert XCcyBasisCollector.classify_stress(-50) == "severe"
        assert XCcyBasisCollector.classify_stress(-100) == "severe"

    def test_classify_stress_historical_crises(self) -> None:
        """Test classification matches historical crisis levels."""
        # GFC 2008: basis reached approximately -100 bps
        assert XCcyBasisCollector.classify_stress(-100) == "severe"

        # COVID March 2020: basis reached approximately -50 bps
        assert XCcyBasisCollector.classify_stress(-50) == "severe"

        # Typical stressed conditions: -20 to -30 bps
        assert XCcyBasisCollector.classify_stress(-25) == "moderate"

    def test_get_stress_thresholds(self) -> None:
        """Test stress thresholds are accessible."""
        thresholds = XCcyBasisCollector.get_stress_thresholds()

        assert "normal" in thresholds
        assert "mild" in thresholds
        assert "moderate" in thresholds
        assert "severe" in thresholds
        assert thresholds == STRESS_THRESHOLDS


class TestCollectLatest:
    """Tests for collect_latest convenience method."""

    @pytest.mark.asyncio
    async def test_collect_latest_returns_single_row(
        self, xccy_collector: XCcyBasisCollector, mock_basis_df: pd.DataFrame
    ) -> None:
        """Test collect_latest returns only most recent observation."""
        with patch.object(xccy_collector, "collect", return_value=mock_basis_df):
            result = await xccy_collector.collect_latest()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_collect_latest_returns_most_recent(
        self, xccy_collector: XCcyBasisCollector, mock_basis_df: pd.DataFrame
    ) -> None:
        """Test collect_latest returns the most recent timestamp."""
        with patch.object(xccy_collector, "collect", return_value=mock_basis_df):
            result = await xccy_collector.collect_latest()

            # Should be 2026-02-04 (the latest)
            assert result["timestamp"].iloc[0] == pd.Timestamp("2026-02-04")

    @pytest.mark.asyncio
    async def test_collect_latest_empty_source(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test collect_latest handles empty source data."""
        empty_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )
        with patch.object(xccy_collector, "collect", return_value=empty_df):
            result = await xccy_collector.collect_latest()

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0


class TestEmptyDataFrame:
    """Tests for empty DataFrame handling."""

    def test_empty_df_has_correct_columns(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test _empty_df has expected schema."""
        empty_df = xccy_collector._empty_df()

        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert set(empty_df.columns) == expected_columns
        assert len(empty_df) == 0

    def test_cached_baseline_schema(self, xccy_collector: XCcyBasisCollector) -> None:
        """Test cached baseline has expected schema."""
        baseline = xccy_collector._get_cached_baseline()

        assert "timestamp" in baseline.columns
        assert "series_id" in baseline.columns
        assert "source" in baseline.columns
        assert "value" in baseline.columns
        assert "unit" in baseline.columns
        assert "stale" in baseline.columns
        assert len(baseline) == 1


class TestCollectorRegistry:
    """Tests for collector registry integration."""

    def test_xccy_basis_collector_registered(self) -> None:
        """Test that XCcyBasisCollector is registered."""
        from liquidity.collectors import registry

        assert "xccy_basis" in registry.list_collectors()
        assert registry.get("xccy_basis") is XCcyBasisCollector

    def test_collector_instantiation_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector = registry.get("xccy_basis")()

        assert isinstance(collector, XCcyBasisCollector)
        assert collector.name == "xccy_basis"


class TestCollectorClose:
    """Tests for collector cleanup."""

    @pytest.mark.asyncio
    async def test_close_releases_client(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test close method releases HTTP client."""
        # Initialize client by calling _get_client
        client = await xccy_collector._get_client()
        assert client is not None
        assert not client.is_closed

        # Close should release client
        await xccy_collector.close()
        assert xccy_collector._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self, xccy_collector: XCcyBasisCollector) -> None:
        """Test close can be called multiple times safely."""
        await xccy_collector.close()  # First call (no client yet)
        await xccy_collector.close()  # Second call (still safe)
        # Should not raise

    @pytest.mark.asyncio
    async def test_client_recreated_after_close(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test client is recreated after close."""
        # Get initial client
        client1 = await xccy_collector._get_client()
        assert client1 is not None

        # Close
        await xccy_collector.close()
        assert xccy_collector._client is None

        # Get new client
        client2 = await xccy_collector._get_client()
        assert client2 is not None
        assert client2 is not client1

        # Cleanup
        await xccy_collector.close()


class TestDataValidation:
    """Tests for data validation."""

    @pytest.mark.asyncio
    async def test_basis_values_are_reasonable(
        self, xccy_collector: XCcyBasisCollector, mock_basis_df: pd.DataFrame
    ) -> None:
        """Test basis values are in reasonable range."""
        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", return_value=mock_basis_df
        ):
            result = await xccy_collector.collect()

            # Basis typically ranges from -200 to +50 bps
            # (extreme crisis to rare USD discount)
            assert (result["value"] > -200).all()
            assert (result["value"] < 100).all()

    @pytest.mark.asyncio
    async def test_timestamps_are_sorted(
        self, xccy_collector: XCcyBasisCollector
    ) -> None:
        """Test timestamps in result are sorted ascending."""
        # Mock returns pre-sorted data (as _fetch_ecb_money_market does internally)
        df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-03"),
                    "series_id": "XCCY_EURUSD_3M",
                    "source": "ecb_sdw",
                    "value": -18.0,
                    "unit": "bps",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "XCCY_EURUSD_3M",
                    "source": "ecb_sdw",
                    "value": -15.0,
                    "unit": "bps",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "XCCY_EURUSD_3M",
                    "source": "ecb_sdw",
                    "value": -12.0,
                    "unit": "bps",
                },
            ]
        )

        with patch.object(
            xccy_collector, "_fetch_ecb_money_market", return_value=df
        ):
            result = await xccy_collector.collect()

            timestamps = result["timestamp"].tolist()
            assert timestamps == sorted(timestamps)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
