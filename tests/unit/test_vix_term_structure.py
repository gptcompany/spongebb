"""Unit tests for VIX Term Structure calculator."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from liquidity.calculators.vix_term_structure import (
    BACKWARDATION_THRESHOLD,
    CONTANGO_THRESHOLD,
    VIX_SERIES,
    TermStructure,
    VIXTermStructureCalculator,
    VIXTermStructureResult,
    classify_structure,
)


class TestTermStructure:
    """Tests for TermStructure enum."""

    def test_enum_values(self):
        assert TermStructure.CONTANGO.value == "CONTANGO"
        assert TermStructure.FLAT.value == "FLAT"
        assert TermStructure.BACKWARDATION.value == "BACKWARDATION"


class TestClassifyStructure:
    """Tests for term structure classification."""

    def test_contango(self):
        assert classify_structure(0.85) == TermStructure.CONTANGO

    def test_flat(self):
        assert classify_structure(0.95) == TermStructure.FLAT

    def test_backwardation(self):
        assert classify_structure(1.10) == TermStructure.BACKWARDATION

    def test_boundary_contango(self):
        """Ratio < 0.90 is contango."""
        assert classify_structure(0.899) == TermStructure.CONTANGO

    def test_boundary_flat_lower(self):
        """Ratio == 0.90 is flat."""
        assert classify_structure(0.90) == TermStructure.FLAT

    def test_boundary_flat_upper(self):
        """Ratio == 1.05 is flat."""
        assert classify_structure(1.05) == TermStructure.FLAT

    def test_boundary_backwardation(self):
        """Ratio > 1.05 is backwardation."""
        assert classify_structure(1.051) == TermStructure.BACKWARDATION


class TestThresholds:
    """Tests for module constants."""

    def test_contango_threshold(self):
        assert CONTANGO_THRESHOLD == 0.90

    def test_backwardation_threshold(self):
        assert BACKWARDATION_THRESHOLD == 1.05

    def test_vix_series(self):
        assert VIX_SERIES["vix"] == "VIXCLS"
        assert VIX_SERIES["vix3m"] == "VXVCLS"


class TestVIXTermStructureResult:
    """Tests for VIXTermStructureResult dataclass."""

    def test_dataclass_creation(self):
        result = VIXTermStructureResult(
            timestamp=datetime.now(UTC),
            vix=18.5,
            vix3m=20.0,
            ratio=0.925,
            structure=TermStructure.FLAT,
            spread=-1.5,
        )
        assert result.vix == 18.5
        assert result.ratio == 0.925
        assert result.structure == TermStructure.FLAT
        assert result.spread == -1.5


class TestVIXTermStructureCalculator:
    """Tests for VIXTermStructureCalculator."""

    @pytest.fixture()
    def calculator(self):
        return VIXTermStructureCalculator()

    @pytest.fixture()
    def sample_vix_data(self):
        """Create sample VIX/VIX3M data in FRED long format."""
        dates = pd.date_range("2026-01-01", periods=30, freq="B")
        vix_data = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": "VIXCLS",
                "source": "fred",
                "value": [18.0 + i * 0.1 for i in range(30)],
                "unit": "percent",
            }
        )
        vix3m_data = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": "VXVCLS",
                "source": "fred",
                "value": [20.0 + i * 0.05 for i in range(30)],
                "unit": "percent",
            }
        )
        return pd.concat([vix_data, vix3m_data], ignore_index=True)

    @pytest.mark.asyncio()
    async def test_calculate_returns_dataframe(self, calculator, sample_vix_data):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = sample_vix_data
            df = await calculator.calculate()

            assert not df.empty
            assert "vix" in df.columns
            assert "vix3m" in df.columns
            assert "ratio" in df.columns
            assert "spread" in df.columns
            assert "structure" in df.columns

    @pytest.mark.asyncio()
    async def test_calculate_ratio_values(self, calculator, sample_vix_data):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = sample_vix_data
            df = await calculator.calculate()

            # Ratio should be VIX / VIX3M
            for _, row in df.iterrows():
                expected = row["vix"] / row["vix3m"]
                assert row["ratio"] == pytest.approx(expected, rel=1e-6)

    @pytest.mark.asyncio()
    async def test_calculate_spread_values(self, calculator, sample_vix_data):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = sample_vix_data
            df = await calculator.calculate()

            for _, row in df.iterrows():
                expected = row["vix"] - row["vix3m"]
                assert row["spread"] == pytest.approx(expected, rel=1e-6)

    @pytest.mark.asyncio()
    async def test_calculate_structure_classification(self, calculator, sample_vix_data):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = sample_vix_data
            df = await calculator.calculate()

            valid = {s.value for s in TermStructure}
            assert set(df["structure"].unique()).issubset(valid)

    @pytest.mark.asyncio()
    async def test_calculate_empty_data(self, calculator):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )
            df = await calculator.calculate()
            assert df.empty

    @pytest.mark.asyncio()
    async def test_get_current(self, calculator, sample_vix_data):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = sample_vix_data
            result = await calculator.get_current()

            assert isinstance(result, VIXTermStructureResult)
            assert isinstance(result.structure, TermStructure)
            assert result.ratio > 0
            assert result.vix > 0
            assert result.vix3m > 0

    @pytest.mark.asyncio()
    async def test_get_current_empty_raises(self, calculator):
        with patch.object(
            calculator._collector, "collect", new_callable=AsyncMock
        ) as mock_collect:
            mock_collect.return_value = pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )
            with pytest.raises(ValueError, match="No VIX data"):
                await calculator.get_current()

    @pytest.mark.asyncio()
    async def test_contango_scenario(self, calculator):
        """Test scenario where VIX << VIX3M (contango)."""
        dates = pd.date_range("2026-01-01", periods=10, freq="B")
        data = pd.concat([
            pd.DataFrame({"timestamp": dates, "series_id": "VIXCLS", "source": "fred", "value": 15.0, "unit": "percent"}),
            pd.DataFrame({"timestamp": dates, "series_id": "VXVCLS", "source": "fred", "value": 20.0, "unit": "percent"}),
        ], ignore_index=True)
        with patch.object(calculator._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = data
            result = await calculator.get_current()
            assert result.structure == TermStructure.CONTANGO
            assert result.ratio == pytest.approx(0.75, rel=0.01)

    @pytest.mark.asyncio()
    async def test_backwardation_scenario(self, calculator):
        """Test scenario where VIX >> VIX3M (backwardation/stress)."""
        dates = pd.date_range("2026-01-01", periods=10, freq="B")
        data = pd.concat([
            pd.DataFrame({"timestamp": dates, "series_id": "VIXCLS", "source": "fred", "value": 35.0, "unit": "percent"}),
            pd.DataFrame({"timestamp": dates, "series_id": "VXVCLS", "source": "fred", "value": 25.0, "unit": "percent"}),
        ], ignore_index=True)
        with patch.object(calculator._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = data
            result = await calculator.get_current()
            assert result.structure == TermStructure.BACKWARDATION
            assert result.ratio == pytest.approx(1.4, rel=0.01)
