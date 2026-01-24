"""Unit tests for CreditCollector.

Tests credit market data collection:
- SLOOS (Senior Loan Officer Opinion Survey)
- Commercial paper rates
- Lending standards regime classification

Run with: uv run pytest tests/collectors/test_credit.py -v
"""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from liquidity.collectors.credit import (
    CP_SERIES,
    LENDING_THRESHOLDS,
    SLOOS_SERIES,
    CreditCollector,
)

# Mark for tests that require FRED API key
requires_fred_api = pytest.mark.skipif(
    not os.environ.get("LIQUIDITY_FRED_API_KEY"),
    reason="LIQUIDITY_FRED_API_KEY not set - skipping FRED API tests",
)


@pytest.fixture
def mock_fred_collector() -> MagicMock:
    """Create a mock FredCollector for testing."""
    mock = MagicMock()
    mock.collect = AsyncMock()
    return mock


@pytest.fixture
def credit_collector(mock_fred_collector: MagicMock) -> CreditCollector:
    """Create a CreditCollector with mocked FredCollector."""
    return CreditCollector(fred_collector=mock_fred_collector)


@pytest.fixture
def sample_sloos_data() -> pd.DataFrame:
    """Create sample SLOOS data for testing."""
    return pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2025-10-01"),
                pd.Timestamp("2025-10-01"),
                pd.Timestamp("2025-10-01"),
                pd.Timestamp("2025-10-01"),
            ],
            "series_id": ["DRTSCILM", "DRTSCIS", "DRTSROM", "DRSDCILM"],
            "source": ["fred"] * 4,
            "value": [15.0, 18.0, 12.0, -5.0],
            "unit": ["net_percent"] * 4,
        }
    )


@pytest.fixture
def sample_cp_data() -> pd.DataFrame:
    """Create sample CP rate data for testing."""
    return pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2026-01-20"),
                pd.Timestamp("2026-01-20"),
                pd.Timestamp("2026-01-21"),
                pd.Timestamp("2026-01-21"),
            ],
            "series_id": ["DCPF3M", "DCPN3M", "DCPF3M", "DCPN3M"],
            "source": ["fred"] * 4,
            "value": [5.25, 5.15, 5.28, 5.18],
            "unit": ["percent"] * 4,
        }
    )


class TestCreditCollectorInstantiation:
    """Tests for CreditCollector instantiation."""

    def test_default_instantiation(self) -> None:
        """Test default instantiation creates collector."""
        collector = CreditCollector()
        assert collector.name == "credit"

    def test_custom_name(self) -> None:
        """Test custom name is applied."""
        collector = CreditCollector(name="custom_credit")
        assert collector.name == "custom_credit"

    def test_fred_collector_injection(self, mock_fred_collector: MagicMock) -> None:
        """Test FredCollector can be injected."""
        collector = CreditCollector(fred_collector=mock_fred_collector)
        assert collector._fred is mock_fred_collector

    def test_class_attributes(self) -> None:
        """Test class attributes are set correctly."""
        assert CreditCollector.SLOOS_SERIES == SLOOS_SERIES
        assert CreditCollector.CP_SERIES == CP_SERIES
        assert CreditCollector.THRESHOLDS == LENDING_THRESHOLDS


class TestSLOOSCollection:
    """Tests for SLOOS data collection."""

    @pytest.mark.asyncio
    async def test_collect_sloos_success(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
        sample_sloos_data: pd.DataFrame,
    ) -> None:
        """Test successful SLOOS data collection."""
        mock_fred_collector.collect.return_value = sample_sloos_data

        df = await credit_collector.collect_sloos()

        assert not df.empty
        mock_fred_collector.collect.assert_called_once()
        # Verify correct series were requested
        call_kwargs = mock_fred_collector.collect.call_args.kwargs
        assert set(call_kwargs["symbols"]) == set(SLOOS_SERIES)

    @pytest.mark.asyncio
    async def test_collect_sloos_date_range(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
        sample_sloos_data: pd.DataFrame,
    ) -> None:
        """Test SLOOS collection with custom date range."""
        mock_fred_collector.collect.return_value = sample_sloos_data

        start_date = datetime(2024, 1, 1, tzinfo=UTC)
        end_date = datetime(2024, 6, 30, tzinfo=UTC)

        await credit_collector.collect_sloos(start_date, end_date)

        call_kwargs = mock_fred_collector.collect.call_args.kwargs
        assert call_kwargs["start_date"] == start_date
        assert call_kwargs["end_date"] == end_date

    @pytest.mark.asyncio
    async def test_collect_sloos_empty_response(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
    ) -> None:
        """Test SLOOS collection with empty response."""
        mock_fred_collector.collect.return_value = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        df = await credit_collector.collect_sloos()
        assert df.empty


class TestCPRatesCollection:
    """Tests for commercial paper rate collection."""

    @pytest.mark.asyncio
    async def test_collect_cp_rates_success(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
        sample_cp_data: pd.DataFrame,
    ) -> None:
        """Test successful CP rate collection."""
        mock_fred_collector.collect.return_value = sample_cp_data

        df = await credit_collector.collect_cp_rates()

        assert not df.empty
        mock_fred_collector.collect.assert_called_once()
        call_kwargs = mock_fred_collector.collect.call_args.kwargs
        assert set(call_kwargs["symbols"]) == set(CP_SERIES)

    @pytest.mark.asyncio
    async def test_collect_cp_rates_date_range(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
        sample_cp_data: pd.DataFrame,
    ) -> None:
        """Test CP rate collection with custom date range."""
        mock_fred_collector.collect.return_value = sample_cp_data

        start_date = datetime(2026, 1, 1, tzinfo=UTC)
        end_date = datetime(2026, 1, 15, tzinfo=UTC)

        await credit_collector.collect_cp_rates(start_date, end_date)

        call_kwargs = mock_fred_collector.collect.call_args.kwargs
        assert call_kwargs["start_date"] == start_date
        assert call_kwargs["end_date"] == end_date


class TestLendingStandardsRegime:
    """Tests for lending standards regime classification."""

    def test_tightening_regime(self, credit_collector: CreditCollector) -> None:
        """Test TIGHTENING regime when DRTSCILM > 20%."""
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")],
                "series_id": ["DRTSCILM"],
                "source": ["fred"],
                "value": [25.0],  # Above 20% threshold
                "unit": ["net_percent"],
            }
        )

        regime = credit_collector.get_lending_standards_regime(test_data)
        assert regime == "TIGHTENING"

    def test_easing_regime(self, credit_collector: CreditCollector) -> None:
        """Test EASING regime when DRTSCILM < -10%."""
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")],
                "series_id": ["DRTSCILM"],
                "source": ["fred"],
                "value": [-15.0],  # Below -10% threshold
                "unit": ["net_percent"],
            }
        )

        regime = credit_collector.get_lending_standards_regime(test_data)
        assert regime == "EASING"

    def test_neutral_regime(self, credit_collector: CreditCollector) -> None:
        """Test NEUTRAL regime when DRTSCILM between -10% and 20%."""
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")],
                "series_id": ["DRTSCILM"],
                "source": ["fred"],
                "value": [10.0],  # Between -10% and 20%
                "unit": ["net_percent"],
            }
        )

        regime = credit_collector.get_lending_standards_regime(test_data)
        assert regime == "NEUTRAL"

    def test_regime_at_tightening_boundary(
        self, credit_collector: CreditCollector
    ) -> None:
        """Test regime at exactly 20% boundary is NEUTRAL (not strictly greater)."""
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")],
                "series_id": ["DRTSCILM"],
                "source": ["fred"],
                "value": [20.0],  # Exactly at threshold
                "unit": ["net_percent"],
            }
        )

        regime = credit_collector.get_lending_standards_regime(test_data)
        assert regime == "NEUTRAL"

    def test_regime_at_easing_boundary(self, credit_collector: CreditCollector) -> None:
        """Test regime at exactly -10% boundary is NEUTRAL."""
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")],
                "series_id": ["DRTSCILM"],
                "source": ["fred"],
                "value": [-10.0],  # Exactly at threshold
                "unit": ["net_percent"],
            }
        )

        regime = credit_collector.get_lending_standards_regime(test_data)
        assert regime == "NEUTRAL"

    def test_regime_empty_dataframe(self, credit_collector: CreditCollector) -> None:
        """Test NEUTRAL regime with empty DataFrame."""
        empty_df = pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

        regime = credit_collector.get_lending_standards_regime(empty_df)
        assert regime == "NEUTRAL"

    def test_regime_none_returns_neutral(
        self, credit_collector: CreditCollector
    ) -> None:
        """Test NEUTRAL regime when None is passed."""
        regime = credit_collector.get_lending_standards_regime(None)
        assert regime == "NEUTRAL"

    def test_regime_missing_drtscilm(self, credit_collector: CreditCollector) -> None:
        """Test NEUTRAL regime when DRTSCILM is not in data."""
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-22")],
                "series_id": ["DRTSCIS"],  # Wrong series
                "source": ["fred"],
                "value": [50.0],  # Would be tightening if it were DRTSCILM
                "unit": ["net_percent"],
            }
        )

        regime = credit_collector.get_lending_standards_regime(test_data)
        assert regime == "NEUTRAL"

    def test_regime_uses_latest_value(self, credit_collector: CreditCollector) -> None:
        """Test that regime uses the latest DRTSCILM value."""
        test_data = pd.DataFrame(
            {
                "timestamp": [
                    pd.Timestamp("2026-01-01"),
                    pd.Timestamp("2026-01-15"),
                    pd.Timestamp("2026-01-22"),
                ],
                "series_id": ["DRTSCILM", "DRTSCILM", "DRTSCILM"],
                "source": ["fred"] * 3,
                "value": [50.0, 30.0, 5.0],  # Latest is 5.0 -> NEUTRAL
                "unit": ["net_percent"] * 3,
            }
        )

        regime = credit_collector.get_lending_standards_regime(test_data)
        assert regime == "NEUTRAL"


class TestCollectAll:
    """Tests for combined credit data collection."""

    @pytest.mark.asyncio
    async def test_collect_all_success(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
        sample_sloos_data: pd.DataFrame,
        sample_cp_data: pd.DataFrame,
    ) -> None:
        """Test collecting all credit data successfully."""
        # Mock returns different data on each call
        mock_fred_collector.collect.side_effect = [sample_sloos_data, sample_cp_data]

        df = await credit_collector.collect()

        assert not df.empty
        assert mock_fred_collector.collect.call_count == 2
        # Should contain both SLOOS and CP series
        series_ids = set(df["series_id"].unique())
        assert "DRTSCILM" in series_ids or "DCPF3M" in series_ids

    @pytest.mark.asyncio
    async def test_collect_all_partial_failure(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
        sample_sloos_data: pd.DataFrame,
    ) -> None:
        """Test collecting continues when one source fails."""
        # SLOOS succeeds, CP fails
        mock_fred_collector.collect.side_effect = [
            sample_sloos_data,
            Exception("CP fetch failed"),
        ]

        df = await credit_collector.collect()

        # Should still have SLOOS data
        assert not df.empty
        assert "DRTSCILM" in df["series_id"].values

    @pytest.mark.asyncio
    async def test_collect_all_both_fail(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
    ) -> None:
        """Test empty DataFrame when all sources fail."""
        mock_fred_collector.collect.side_effect = [
            Exception("SLOOS failed"),
            Exception("CP failed"),
        ]

        df = await credit_collector.collect()
        assert df.empty


class TestCPSpread:
    """Tests for CP spread calculation."""

    @pytest.mark.asyncio
    async def test_collect_cp_spread_success(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
        sample_cp_data: pd.DataFrame,
    ) -> None:
        """Test CP spread calculation."""
        mock_fred_collector.collect.return_value = sample_cp_data

        df = await credit_collector.collect_ci_spread()

        assert not df.empty
        assert df["series_id"].unique().tolist() == ["credit_cp_spread"]
        assert df["unit"].unique().tolist() == ["basis_points"]
        assert df["source"].unique().tolist() == ["calculated"]

    @pytest.mark.asyncio
    async def test_collect_cp_spread_values(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
    ) -> None:
        """Test CP spread values are correct."""
        # Financial CP at 5.25%, Nonfinancial at 5.15%
        # Spread should be (5.25 - 5.15) * 100 = 10 bps
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-20"), pd.Timestamp("2026-01-20")],
                "series_id": ["DCPF3M", "DCPN3M"],
                "source": ["fred", "fred"],
                "value": [5.25, 5.15],
                "unit": ["percent", "percent"],
            }
        )
        mock_fred_collector.collect.return_value = test_data

        df = await credit_collector.collect_ci_spread()

        assert len(df) == 1
        assert abs(df.iloc[0]["value"] - 10.0) < 0.01  # 10 bps spread

    @pytest.mark.asyncio
    async def test_collect_cp_spread_missing_series(
        self,
        credit_collector: CreditCollector,
        mock_fred_collector: MagicMock,
    ) -> None:
        """Test CP spread returns empty when missing series."""
        # Only one series present
        test_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2026-01-20")],
                "series_id": ["DCPF3M"],
                "source": ["fred"],
                "value": [5.25],
                "unit": ["percent"],
            }
        )
        mock_fred_collector.collect.return_value = test_data

        df = await credit_collector.collect_ci_spread()
        assert df.empty


class TestRegistryIntegration:
    """Tests for collector registry integration."""

    def test_registry_registration(self) -> None:
        """Test that CreditCollector is registered in the registry."""
        from liquidity.collectors import registry

        assert "credit" in registry.list_collectors()
        collector_cls = registry.get("credit")
        assert collector_cls is CreditCollector

    def test_instantiation_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector_cls = registry.get("credit")
        collector = collector_cls()

        assert isinstance(collector, CreditCollector)
        assert collector.name == "credit"


class TestThresholdsExport:
    """Tests for threshold constants export."""

    def test_thresholds_structure(self) -> None:
        """Test LENDING_THRESHOLDS constant structure."""
        assert "tightening" in LENDING_THRESHOLDS
        assert "easing" in LENDING_THRESHOLDS
        assert LENDING_THRESHOLDS["tightening"] == 20.0
        assert LENDING_THRESHOLDS["easing"] == -10.0

    def test_sloos_series_structure(self) -> None:
        """Test SLOOS_SERIES contains expected series."""
        expected = ["DRTSCILM", "DRTSCIS", "DRTSROM", "DRSDCILM"]
        assert SLOOS_SERIES == expected

    def test_cp_series_structure(self) -> None:
        """Test CP_SERIES contains expected series."""
        expected = ["DCPF3M", "DCPN3M"]
        assert CP_SERIES == expected


class TestIntegrationWithRealAPI:
    """Integration tests with real FRED API (skipped without API key)."""

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_sloos_real_api(self) -> None:
        """Test SLOOS collection with real FRED API."""
        collector = CreditCollector()
        df = await collector.collect_sloos()

        if not df.empty:
            assert set(df.columns) == {
                "timestamp",
                "series_id",
                "source",
                "value",
                "unit",
            }
            # SLOOS values should be in reasonable range
            assert df["value"].min() >= -50
            assert df["value"].max() <= 100
            print(f"\nCollected {len(df)} SLOOS data points")

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_cp_rates_real_api(self) -> None:
        """Test CP rate collection with real FRED API."""
        collector = CreditCollector()
        df = await collector.collect_cp_rates()

        if not df.empty:
            assert set(df.columns) == {
                "timestamp",
                "series_id",
                "source",
                "value",
                "unit",
            }
            # CP rates should be positive percentages
            assert df["value"].min() >= 0
            assert df["value"].max() <= 20
            print(f"\nCollected {len(df)} CP rate data points")

    @requires_fred_api
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_lending_regime_real_api(self) -> None:
        """Test regime classification with real SLOOS data."""
        collector = CreditCollector()
        df = await collector.collect_sloos()

        if not df.empty:
            regime = collector.get_lending_standards_regime(df)
            assert regime in ["TIGHTENING", "NEUTRAL", "EASING"]
            print(f"\nCurrent lending standards regime: {regime}")


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        collector = CreditCollector()

        print("Testing credit collector...")
        df = await collector.collect_sloos()
        print(f"Collected {len(df)} SLOOS data points")

        if not df.empty:
            regime = collector.get_lending_standards_regime(df)
            print(f"Current lending standards regime: {regime}")

            # Show latest values
            for series_id in df["series_id"].unique():
                latest = df[df["series_id"] == series_id].iloc[-1]
                print(f"  {series_id}: {latest['value']:.2f}%")

    asyncio.run(main())
