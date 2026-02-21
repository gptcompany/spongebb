"""Tests for Fetcher TET pipeline (transform_query, aextract_data, transform_data)."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from liquidity.openbb_ext.models.global_liquidity import (
    LiquidityGlobalLiquidityData,
    LiquidityGlobalLiquidityFetcher,
    LiquidityGlobalLiquidityQueryParams,
)
from liquidity.openbb_ext.models.net_liquidity import (
    LiquidityNetLiquidityData,
    LiquidityNetLiquidityFetcher,
    LiquidityNetLiquidityQueryParams,
)
from liquidity.openbb_ext.models.stealth_qe import (
    LiquidityStealthQEData,
    LiquidityStealthQEFetcher,
    LiquidityStealthQEQueryParams,
)

# ── NetLiquidity Fetcher ─────────────────────────────────────────────────


class TestNetLiquidityFetcher:
    """Tests for NetLiquidity TET pipeline."""

    def test_transform_query_defaults(self):
        """Empty params get default start_date and end_date."""
        query = LiquidityNetLiquidityFetcher.transform_query({})
        assert isinstance(query, LiquidityNetLiquidityQueryParams)
        assert query.start_date is not None
        assert query.end_date is not None
        assert query.end_date == date.today()
        assert query.start_date < query.end_date

    def test_transform_query_preserves_explicit(self):
        """Explicit dates are preserved."""
        params = {"start_date": "2024-01-01", "end_date": "2024-06-30"}
        query = LiquidityNetLiquidityFetcher.transform_query(params)
        assert query.start_date == date(2024, 1, 1)
        assert query.end_date == date(2024, 6, 30)

    @pytest.mark.asyncio
    async def test_aextract_data_returns_list_of_dicts(self):
        """aextract_data returns list[dict] from mocked calculator."""
        mock_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="W"),
            "net_liquidity": [5800.0, 5850.0, 5900.0],
            "walcl": [7500.0] * 3,
            "tga": [800.0] * 3,
            "rrp": [900.0, 850.0, 800.0],
        })
        query = LiquidityNetLiquidityFetcher.transform_query({})
        with patch(
            "liquidity.calculators.net_liquidity.NetLiquidityCalculator.calculate",
            new_callable=AsyncMock,
            return_value=mock_df,
        ):
            result = await LiquidityNetLiquidityFetcher.aextract_data(query, None)
        assert isinstance(result, list)
        assert len(result) == 3
        assert "date" in result[0]
        assert "net_liquidity" in result[0]

    def test_transform_data_returns_annotated_result(self):
        """transform_data wraps dicts into AnnotatedResult[list[Data]]."""
        data = [
            {"date": "2024-01-07", "net_liquidity": 5800.0, "walcl": 7500.0, "tga": 800.0, "rrp": 900.0},
            {"date": "2024-01-14", "net_liquidity": 5850.0, "walcl": 7500.0, "tga": 800.0, "rrp": 850.0},
        ]
        query = LiquidityNetLiquidityFetcher.transform_query({})
        result = LiquidityNetLiquidityFetcher.transform_data(query, data)
        assert len(result.result) == 2
        assert isinstance(result.result[0], LiquidityNetLiquidityData)
        assert result.result[0].net_liquidity == 5800.0


# ── GlobalLiquidity Fetcher ──────────────────────────────────────────────


class TestGlobalLiquidityFetcher:
    """Tests for GlobalLiquidity TET pipeline."""

    def test_transform_query_defaults(self):
        """Empty params get defaults including tier=1."""
        query = LiquidityGlobalLiquidityFetcher.transform_query({})
        assert isinstance(query, LiquidityGlobalLiquidityQueryParams)
        assert query.tier == 1
        assert query.start_date is not None
        assert query.end_date is not None

    def test_transform_query_tier2(self):
        """tier=2 is preserved from params."""
        query = LiquidityGlobalLiquidityFetcher.transform_query({"tier": 2})
        assert query.tier == 2

    @pytest.mark.asyncio
    async def test_aextract_data_passes_tier(self):
        """aextract_data passes tier parameter to calculator."""
        mock_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=2, freq="W"),
            "global_liquidity": [30000.0, 30100.0],
            "fed_usd": [7500.0] * 2,
            "ecb_usd": [8000.0] * 2,
            "boj_usd": [5000.0] * 2,
            "pboc_usd": [9500.0] * 2,
        })
        query = LiquidityGlobalLiquidityFetcher.transform_query({"tier": 2})
        with patch(
            "liquidity.calculators.global_liquidity.GlobalLiquidityCalculator.calculate",
            new_callable=AsyncMock,
            return_value=mock_df,
        ) as mock_calc:
            await LiquidityGlobalLiquidityFetcher.aextract_data(query, None)
        _, call_kwargs = mock_calc.call_args
        assert call_kwargs["tier"] == 2

    def test_transform_data_tier2_optional_fields(self):
        """Tier 2 fields (boe_usd etc.) default to None when missing."""
        data = [
            {"date": "2024-01-07", "global_liquidity": 30000.0, "fed_usd": 7500.0,
             "ecb_usd": 8000.0, "boj_usd": 5000.0, "pboc_usd": 9500.0},
        ]
        query = LiquidityGlobalLiquidityFetcher.transform_query({})
        result = LiquidityGlobalLiquidityFetcher.transform_data(query, data)
        assert isinstance(result.result[0], LiquidityGlobalLiquidityData)
        assert result.result[0].boe_usd is None
        assert result.result[0].snb_usd is None
        assert result.result[0].boc_usd is None


# ── StealthQE Fetcher ────────────────────────────────────────────────────


class TestStealthQEFetcher:
    """Tests for StealthQE TET pipeline."""

    def test_transform_query_defaults(self):
        """Empty params get default dates."""
        query = LiquidityStealthQEFetcher.transform_query({})
        assert isinstance(query, LiquidityStealthQEQueryParams)
        assert query.start_date is not None
        assert query.end_date == date.today()

    @pytest.mark.asyncio
    async def test_aextract_data_calls_calculate_daily(self):
        """aextract_data calls calculate_daily (not calculate_weekly)."""
        mock_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=2, freq="D"),
            "score_daily": [45.0, 48.0],
            "rrp_level": [500.0, 490.0],
            "tga_level": [750.0, 740.0],
            "fed_total": [7500.0] * 2,
            "comp_rrp": [30.0, 32.0],
            "comp_tga": [35.0, 36.0],
            "comp_fed": [10.0, 10.0],
            "status": ["MODERATE", "MODERATE"],
        })
        query = LiquidityStealthQEFetcher.transform_query({})
        with patch(
            "liquidity.calculators.stealth_qe.StealthQECalculator.calculate_daily",
            new_callable=AsyncMock,
            return_value=mock_df,
        ) as mock_calc:
            result = await LiquidityStealthQEFetcher.aextract_data(query, None)
        mock_calc.assert_called_once()
        assert len(result) == 2
        assert "score_daily" in result[0]

    def test_transform_data_status_field(self):
        """transform_data preserves status string field."""
        data = [
            {"date": "2024-01-01", "score_daily": 45.0, "rrp_level": 500.0,
             "tga_level": 750.0, "fed_total": 7500.0, "comp_rrp": 30.0,
             "comp_tga": 35.0, "comp_fed": 10.0, "status": "MODERATE"},
        ]
        query = LiquidityStealthQEFetcher.transform_query({})
        result = LiquidityStealthQEFetcher.transform_data(query, data)
        assert isinstance(result.result[0], LiquidityStealthQEData)
        assert result.result[0].status == "MODERATE"
        assert result.result[0].score_daily == 45.0
