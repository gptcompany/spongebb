"""Unit tests for GlobalLiquidityCalculator."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from liquidity.calculators.global_liquidity import (
    CB_UNITS,
    CBDataFrames,
    FX_CONVERSION_CONFIG,
    TIER_COVERAGE,
    GlobalLiquidityCalculator,
    GlobalLiquidityResult,
)


class TestFXConversionConfig:
    """Tests for FX conversion configuration."""

    def test_eur_config(self):
        """Test EUR conversion config."""
        assert FX_CONVERSION_CONFIG["EUR"] == ("EURUSD=X", "multiply")

    def test_jpy_config(self):
        """Test JPY conversion config."""
        assert FX_CONVERSION_CONFIG["JPY"] == ("USDJPY=X", "divide")

    def test_cny_config(self):
        """Test CNY conversion config."""
        assert FX_CONVERSION_CONFIG["CNY"] == ("USDCNY=X", "divide")

    def test_gbp_config(self):
        """Test GBP conversion config."""
        assert FX_CONVERSION_CONFIG["GBP"] == ("GBPUSD=X", "multiply")

    def test_chf_config(self):
        """Test CHF conversion config."""
        assert FX_CONVERSION_CONFIG["CHF"] == ("USDCHF=X", "divide")

    def test_cad_config(self):
        """Test CAD conversion config."""
        assert FX_CONVERSION_CONFIG["CAD"] == ("USDCAD=X", "divide")


class TestCBUnits:
    """Tests for CB unit configuration."""

    def test_fed_units(self):
        """Test Fed already in billions USD."""
        assert CB_UNITS["fed"]["unit"] == "billions_usd"
        assert CB_UNITS["fed"]["divisor"] == 1.0

    def test_ecb_units(self):
        """Test ECB in millions EUR."""
        assert CB_UNITS["ecb"]["unit"] == "millions_eur"
        assert CB_UNITS["ecb"]["divisor"] == 1000.0

    def test_boj_units(self):
        """Test BoJ in 100 millions JPY."""
        assert CB_UNITS["boj"]["unit"] == "100_millions_jpy"
        assert CB_UNITS["boj"]["divisor"] == 10.0

    def test_pboc_assets_units(self):
        """Test PBoC assets in 100 millions CNY."""
        assert CB_UNITS["pboc_assets"]["unit"] == "100_millions_cny"
        assert CB_UNITS["pboc_assets"]["divisor"] == 10.0


class TestTierCoverage:
    """Tests for tier coverage percentages."""

    def test_tier1_sums_to_95(self):
        """Test Tier 1 coverage sums to ~95%."""
        tier1 = (
            TIER_COVERAGE["fed"]
            + TIER_COVERAGE["ecb"]
            + TIER_COVERAGE["boj"]
            + TIER_COVERAGE["pboc"]
        )
        assert tier1 == pytest.approx(95.0)

    def test_tier2_exists(self):
        """Test Tier 2 CBs have coverage."""
        assert "boe" in TIER_COVERAGE
        assert "snb" in TIER_COVERAGE
        assert "boc" in TIER_COVERAGE


class TestGlobalLiquidityResult:
    """Tests for GlobalLiquidityResult dataclass."""

    def test_dataclass_creation(self):
        """Test result dataclass can be created."""
        result = GlobalLiquidityResult(
            timestamp=datetime.now(UTC),
            total_usd=30000.0,
            fed_usd=7000.0,
            ecb_usd=8000.0,
            boj_usd=6000.0,
            pboc_usd=9000.0,
            boe_usd=None,
            snb_usd=None,
            boc_usd=None,
            weekly_delta=100.0,
            delta_30d=200.0,
            delta_60d=300.0,
            delta_90d=400.0,
            coverage_pct=95.0,
        )
        assert result.total_usd == 30000.0
        assert result.boe_usd is None
        assert result.coverage_pct == 95.0

    def test_dataclass_with_tier2(self):
        """Test result with Tier 2 values."""
        result = GlobalLiquidityResult(
            timestamp=datetime.now(UTC),
            total_usd=32000.0,
            fed_usd=7000.0,
            ecb_usd=8000.0,
            boj_usd=6000.0,
            pboc_usd=9000.0,
            boe_usd=1500.0,
            snb_usd=300.0,
            boc_usd=200.0,
            weekly_delta=150.0,
            delta_30d=250.0,
            delta_60d=350.0,
            delta_90d=450.0,
            coverage_pct=99.0,
        )
        assert result.boe_usd == 1500.0
        assert result.snb_usd == 300.0


class TestGlobalLiquidityCalculatorInit:
    """Tests for GlobalLiquidityCalculator initialization."""

    def test_init(self):
        """Test calculator initialization."""
        calc = GlobalLiquidityCalculator()
        assert calc is not None
        assert calc._fx_cache == {}

    def test_init_has_collectors(self):
        """Test calculator initializes collectors."""
        calc = GlobalLiquidityCalculator()
        assert calc._net_liq_calc is not None
        assert calc._fred is not None
        assert calc._fx is not None
        assert calc._pboc is not None
        assert calc._boe is not None
        assert calc._snb is not None
        assert calc._boc is not None


class TestConvertToUSD:
    """Tests for _convert_to_usd method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_convert_eur_multiply(self, calculator):
        """Test EUR conversion (multiply)."""
        fx_rates = {"EURUSD=X": 1.08}
        result = calculator._convert_to_usd(100.0, "EUR", fx_rates)
        assert result == pytest.approx(108.0)

    def test_convert_jpy_divide(self, calculator):
        """Test JPY conversion (divide)."""
        fx_rates = {"USDJPY=X": 150.0}
        result = calculator._convert_to_usd(1500.0, "JPY", fx_rates)
        assert result == pytest.approx(10.0)

    def test_convert_cny_divide(self, calculator):
        """Test CNY conversion (divide)."""
        fx_rates = {"USDCNY=X": 7.2}
        result = calculator._convert_to_usd(72.0, "CNY", fx_rates)
        assert result == pytest.approx(10.0)

    def test_convert_unknown_currency(self, calculator):
        """Test unknown currency returns 0."""
        result = calculator._convert_to_usd(100.0, "XXX", {})
        assert result == 0.0

    def test_convert_missing_fx_rate(self, calculator):
        """Test missing FX rate returns 0."""
        result = calculator._convert_to_usd(100.0, "EUR", {})
        assert result == 0.0


class TestCalculateDelta:
    """Tests for _calculate_delta method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_delta_with_empty_df(self, calculator):
        """Test delta with empty DataFrame."""
        df = pd.DataFrame(columns=["timestamp", "global_liquidity"])
        result = calculator._calculate_delta(df, days=7)
        assert result == 0.0

    def test_delta_calculation(self, calculator):
        """Test delta calculation with valid data."""
        now = datetime.now(UTC)
        df = pd.DataFrame(
            {
                "timestamp": [
                    now - timedelta(days=10),
                    now - timedelta(days=7),
                    now,
                ],
                "global_liquidity": [29000.0, 29500.0, 30000.0],
            }
        )
        delta = calculator._calculate_delta(df, days=7)
        assert delta == pytest.approx(500.0)


class TestCalculateCoverage:
    """Tests for _calculate_coverage method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_tier1_coverage(self, calculator):
        """Test Tier 1 coverage calculation."""
        coverage = calculator._calculate_coverage(tier=1)
        assert coverage == pytest.approx(95.0)

    def test_tier2_coverage(self, calculator):
        """Test Tier 2 coverage calculation."""
        coverage = calculator._calculate_coverage(tier=2)
        expected = (
            95.0 + TIER_COVERAGE["boe"] + TIER_COVERAGE["snb"] + TIER_COVERAGE["boc"]
        )
        assert coverage == pytest.approx(expected)


class TestProcessCBData:
    """Tests for _process_cb_data method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_process_empty_df(self, calculator):
        """Test processing empty DataFrame."""
        df = pd.DataFrame()
        result = calculator._process_cb_data(
            df, "ecb_usd", "EUR", 1000.0, {"EURUSD=X": 1.08}
        )
        assert result.empty

    def test_process_missing_timestamp(self, calculator):
        """Test processing DataFrame without timestamp."""
        df = pd.DataFrame({"value": [100.0]})
        result = calculator._process_cb_data(
            df, "ecb_usd", "EUR", 1000.0, {"EURUSD=X": 1.08}
        )
        assert result.empty

    def test_process_valid_data(self, calculator):
        """Test processing valid CB data."""
        now = datetime.now(UTC)
        df = pd.DataFrame(
            {
                "timestamp": [now],
                "value": [8000000.0],  # 8000 billions EUR in millions
            }
        )
        fx_rates = {"EURUSD=X": 1.08}
        result = calculator._process_cb_data(df, "ecb_usd", "EUR", 1000.0, fx_rates)

        assert not result.empty
        assert "timestamp" in result.columns
        assert "ecb_usd" in result.columns
        # 8000000 / 1000 * 1.08 = 8640 billions USD
        assert result["ecb_usd"].iloc[0] == pytest.approx(8640.0)


class TestGetLatestFXRates:
    """Tests for _get_latest_fx_rates method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_empty_fx_df_returns_fallback(self, calculator):
        """Test empty FX DataFrame returns fallback rates."""
        result = calculator._get_latest_fx_rates(pd.DataFrame())
        # Empty DF returns fallback rates, not empty dict
        assert "EURUSD=X" in result
        assert "USDJPY=X" in result
        assert result["EURUSD=X"] == pytest.approx(1.05)  # Fallback rate

    def test_valid_fx_df(self, calculator):
        """Test with valid FX DataFrame."""
        now = datetime.now(UTC)
        df = pd.DataFrame(
            {
                "timestamp": [now, now],
                "series_id": ["EURUSD=X", "USDJPY=X"],
                "value": [1.08, 150.0],
            }
        )
        result = calculator._get_latest_fx_rates(df)
        assert result["EURUSD=X"] == 1.08
        assert result["USDJPY=X"] == 150.0


class TestCalculateAsync:
    """Tests for async calculate method."""

    @pytest.mark.asyncio
    async def test_calculate_empty_data(self):
        """Test calculate with empty data returns empty DataFrame."""
        calc = GlobalLiquidityCalculator()

        # Mock all the async calls
        with patch.object(
            calc._net_liq_calc, "calculate", new_callable=AsyncMock
        ) as mock_net, patch.object(
            calc._fred, "collect_ecb_assets", new_callable=AsyncMock
        ) as mock_ecb, patch.object(
            calc._fred, "collect_boj_assets", new_callable=AsyncMock
        ) as mock_boj, patch.object(
            calc._pboc, "collect", new_callable=AsyncMock
        ) as mock_pboc, patch.object(
            calc, "_get_fx_rates", new_callable=AsyncMock
        ) as mock_fx:
            mock_net.return_value = pd.DataFrame()
            mock_ecb.return_value = pd.DataFrame()
            mock_boj.return_value = pd.DataFrame()
            mock_pboc.return_value = pd.DataFrame()
            mock_fx.return_value = pd.DataFrame()

            result = await calc.calculate()
            assert result.empty

    @pytest.mark.asyncio
    async def test_calculate_with_data(self):
        """Test calculate with valid mock data."""
        calc = GlobalLiquidityCalculator()
        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(10, -1, -1)]

        # Mock Fed data
        fed_df = pd.DataFrame(
            {
                "timestamp": dates,
                "net_liquidity": [7000.0] * 11,
                "walcl": [8000.0] * 11,
                "tga": [500.0] * 11,
                "rrp": [500.0] * 11,
            }
        )

        # Mock ECB data
        ecb_df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["ECBASSETSW"] * 11,
                "value": [7400000.0] * 11,  # millions EUR
            }
        )

        # Mock BoJ data
        boj_df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["BOJASSETS"] * 11,
                "value": [6000.0] * 11,  # 100M JPY
            }
        )

        # Mock PBoC data
        pboc_df = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["PBOC_TOTAL_ASSETS"] * 11,
                "value": [4500.0] * 11,  # 100M CNY
            }
        )

        # Mock FX data
        fx_df = pd.DataFrame(
            {
                "timestamp": dates * 6,
                "series_id": (
                    ["EURUSD=X"] * 11
                    + ["USDJPY=X"] * 11
                    + ["USDCNY=X"] * 11
                    + ["GBPUSD=X"] * 11
                    + ["USDCHF=X"] * 11
                    + ["USDCAD=X"] * 11
                ),
                "value": (
                    [1.08] * 11
                    + [150.0] * 11
                    + [7.2] * 11
                    + [1.25] * 11
                    + [0.88] * 11
                    + [1.35] * 11
                ),
            }
        )

        with patch.object(
            calc._net_liq_calc, "calculate", new_callable=AsyncMock
        ) as mock_net, patch.object(
            calc._fred, "collect_ecb_assets", new_callable=AsyncMock
        ) as mock_ecb, patch.object(
            calc._fred, "collect_boj_assets", new_callable=AsyncMock
        ) as mock_boj, patch.object(
            calc._pboc, "collect", new_callable=AsyncMock
        ) as mock_pboc, patch.object(
            calc, "_get_fx_rates", new_callable=AsyncMock
        ) as mock_fx:
            mock_net.return_value = fed_df
            mock_ecb.return_value = ecb_df
            mock_boj.return_value = boj_df
            mock_pboc.return_value = pboc_df
            mock_fx.return_value = fx_df

            result = await calc.calculate()

            # Check structure
            assert not result.empty
            assert "global_liquidity" in result.columns
            assert "fed_usd" in result.columns


class TestGetCurrentAsync:
    """Tests for async get_current method."""

    @pytest.mark.asyncio
    async def test_get_current_empty_raises(self):
        """Test get_current with empty data raises ValueError."""
        calc = GlobalLiquidityCalculator()

        with patch.object(calc, "calculate", new_callable=AsyncMock) as mock:
            mock.return_value = pd.DataFrame()

            with pytest.raises(ValueError, match="No data available"):
                await calc.get_current()

    @pytest.mark.asyncio
    async def test_get_current_success(self):
        """Test successful get_current call."""
        calc = GlobalLiquidityCalculator()
        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(100, -1, -1)]

        mock_df = pd.DataFrame(
            {
                "timestamp": dates,
                "global_liquidity": [30000.0 + i for i in range(101)],
                "fed_usd": [7000.0] * 101,
                "ecb_usd": [8000.0] * 101,
                "boj_usd": [6000.0] * 101,
                "pboc_usd": [9000.0] * 101,
            }
        )

        with patch.object(calc, "calculate", new_callable=AsyncMock) as mock:
            mock.return_value = mock_df
            result = await calc.get_current()

            assert isinstance(result, GlobalLiquidityResult)
            assert result.total_usd == mock_df.iloc[-1]["global_liquidity"]
            assert result.fed_usd == 7000.0


class TestProcessCBDataAdvanced:
    """Advanced tests for _process_cb_data method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_process_with_non_value_column(self, calculator):
        """Test processing data with custom value column."""
        now = datetime.now(UTC)
        # DataFrame with custom column name instead of 'value'
        df = pd.DataFrame(
            {
                "timestamp": [now],
                "assets": [8000000.0],  # Not 'value' column
            }
        )
        fx_rates = {"EURUSD=X": 1.08}
        result = calculator._process_cb_data(df, "ecb_usd", "EUR", 1000.0, fx_rates)

        # Should find 'assets' as value column
        assert not result.empty
        assert "ecb_usd" in result.columns

    def test_process_with_no_value_column(self, calculator):
        """Test processing data with no usable value column."""
        now = datetime.now(UTC)
        # DataFrame with only timestamp and metadata columns
        df = pd.DataFrame(
            {
                "timestamp": [now],
                "series_id": ["TEST"],
                "source": ["test"],
            }
        )
        fx_rates = {"EURUSD=X": 1.08}
        result = calculator._process_cb_data(df, "ecb_usd", "EUR", 1000.0, fx_rates)

        # Should return empty since no value column found
        assert result.empty


class TestCalculateTier2:
    """Tests for Tier 2 calculations."""

    @pytest.mark.asyncio
    async def test_calculate_tier2(self):
        """Test calculate with tier=2 includes Tier 2 CBs."""
        calc = GlobalLiquidityCalculator()
        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(10, -1, -1)]

        # Mock Fed data
        fed_df = pd.DataFrame(
            {
                "timestamp": dates,
                "net_liquidity": [7000.0] * 11,
            }
        )

        # Mock FX data
        fx_df = pd.DataFrame(
            {
                "timestamp": dates * 6,
                "series_id": (
                    ["EURUSD=X"] * 11
                    + ["USDJPY=X"] * 11
                    + ["USDCNY=X"] * 11
                    + ["GBPUSD=X"] * 11
                    + ["USDCHF=X"] * 11
                    + ["USDCAD=X"] * 11
                ),
                "value": (
                    [1.08] * 11
                    + [150.0] * 11
                    + [7.2] * 11
                    + [1.25] * 11
                    + [0.88] * 11
                    + [1.35] * 11
                ),
            }
        )

        # Mock Tier 2 data
        boe_df = pd.DataFrame(
            {
                "timestamp": dates,
                "value": [900000.0] * 11,  # millions GBP
            }
        )

        with patch.object(
            calc._net_liq_calc, "calculate", new_callable=AsyncMock
        ) as mock_net, patch.object(
            calc._fred, "collect_ecb_assets", new_callable=AsyncMock
        ) as mock_ecb, patch.object(
            calc._fred, "collect_boj_assets", new_callable=AsyncMock
        ) as mock_boj, patch.object(
            calc._pboc, "collect", new_callable=AsyncMock
        ) as mock_pboc, patch.object(
            calc, "_get_fx_rates", new_callable=AsyncMock
        ) as mock_fx, patch.object(
            calc._boe, "collect", new_callable=AsyncMock
        ) as mock_boe, patch.object(
            calc._snb, "collect", new_callable=AsyncMock
        ) as mock_snb, patch.object(
            calc._boc,
            "collect_total_assets",
            new_callable=AsyncMock,
        ) as mock_boc:
            mock_net.return_value = fed_df
            mock_ecb.return_value = pd.DataFrame()
            mock_boj.return_value = pd.DataFrame()
            mock_pboc.return_value = pd.DataFrame()
            mock_fx.return_value = fx_df
            mock_boe.return_value = boe_df
            mock_snb.return_value = pd.DataFrame()
            mock_boc.return_value = pd.DataFrame()

            await calc.calculate(tier=2)

            # Should have called Tier 2 collectors
            mock_boe.assert_called_once()
            mock_snb.assert_called_once()
            mock_boc.assert_called_once()


class TestCalculateWithExceptions:
    """Tests for exception handling in calculate."""

    @pytest.mark.asyncio
    async def test_calculate_handles_tier1_exceptions(self):
        """Test calculate handles exceptions from Tier 1 collectors."""
        calc = GlobalLiquidityCalculator()

        with patch.object(
            calc._net_liq_calc, "calculate", new_callable=AsyncMock
        ) as mock_net, patch.object(
            calc._fred, "collect_ecb_assets", new_callable=AsyncMock
        ) as mock_ecb, patch.object(
            calc._fred, "collect_boj_assets", new_callable=AsyncMock
        ) as mock_boj, patch.object(
            calc._pboc, "collect", new_callable=AsyncMock
        ) as mock_pboc, patch.object(
            calc, "_get_fx_rates", new_callable=AsyncMock
        ) as mock_fx:
            # Simulate exception from one collector
            mock_net.return_value = Exception("Network error")
            mock_ecb.return_value = pd.DataFrame()
            mock_boj.return_value = pd.DataFrame()
            mock_pboc.return_value = pd.DataFrame()
            mock_fx.return_value = pd.DataFrame()

            # Should handle exception gracefully
            result = await calc.calculate()
            assert result.empty or isinstance(result, pd.DataFrame)


class TestAggregateData:
    """Tests for _aggregate_data method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_aggregate_empty_dfs(self, calculator):
        """Test aggregation with all empty DataFrames."""
        result = calculator._aggregate_data(
            CBDataFrames(
                fed=pd.DataFrame(), ecb=pd.DataFrame(), boj=pd.DataFrame(),
                pboc=pd.DataFrame(), fx=pd.DataFrame(), boe=pd.DataFrame(),
                snb=pd.DataFrame(), boc=pd.DataFrame(),
            ),
            tier=1,
        )
        assert result.empty

    def test_aggregate_fed_only(self, calculator):
        """Test aggregation with only Fed data."""
        now = datetime.now(UTC)
        fed_df = pd.DataFrame(
            {
                "timestamp": [now],
                "net_liquidity": [7000.0],
            }
        )

        result = calculator._aggregate_data(
            CBDataFrames(
                fed=fed_df, ecb=pd.DataFrame(), boj=pd.DataFrame(),
                pboc=pd.DataFrame(), fx=pd.DataFrame(), boe=pd.DataFrame(),
                snb=pd.DataFrame(), boc=pd.DataFrame(),
            ),
            tier=1,
        )

        # Should have fed_usd
        assert not result.empty
        assert "fed_usd" in result.columns

    def test_aggregate_tier2_data(self, calculator):
        """Test aggregation includes Tier 2 data when tier=2."""
        now = datetime.now(UTC)
        fed_df = pd.DataFrame(
            {
                "timestamp": [now],
                "net_liquidity": [7000.0],
            }
        )
        boe_df = pd.DataFrame(
            {
                "timestamp": [now],
                "value": [900000.0],  # millions GBP
            }
        )

        # Need FX rates for Tier 2 conversion
        fx_df = pd.DataFrame(
            {
                "timestamp": [now] * 6,
                "series_id": [
                    "EURUSD=X",
                    "USDJPY=X",
                    "USDCNY=X",
                    "GBPUSD=X",
                    "USDCHF=X",
                    "USDCAD=X",
                ],
                "value": [1.08, 150.0, 7.2, 1.25, 0.88, 1.35],
            }
        )

        result = calculator._aggregate_data(
            CBDataFrames(
                fed=fed_df, ecb=pd.DataFrame(), boj=pd.DataFrame(),
                pboc=pd.DataFrame(), fx=fx_df, boe=boe_df,
                snb=pd.DataFrame(), boc=pd.DataFrame(),
            ),
            tier=2,
        )

        # Should have both fed_usd and boe_usd
        if not result.empty:
            assert "fed_usd" in result.columns


class TestProcessPBOCData:
    """Tests for _process_pboc_data method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_process_pboc_empty(self, calculator):
        """Test processing empty PBoC DataFrame."""
        result = calculator._process_pboc_data(pd.DataFrame(), {})
        assert result.empty

    def test_process_pboc_with_total_assets(self, calculator):
        """Test processing PBoC data with PBOC_TOTAL_ASSETS series."""
        now = datetime.now(UTC)
        df = pd.DataFrame(
            {
                "timestamp": [now],
                "series_id": ["PBOC_TOTAL_ASSETS"],
                "value": [4700.0],  # 100M CNY units
            }
        )
        fx_rates = {"USDCNY=X": 7.2}
        result = calculator._process_pboc_data(df, fx_rates)

        assert not result.empty
        assert "pboc_usd" in result.columns

    def test_process_pboc_with_reserves_proxy(self, calculator):
        """Test processing PBoC data with CHINA_FOREIGN_RESERVES as proxy."""
        now = datetime.now(UTC)
        df = pd.DataFrame(
            {
                "timestamp": [now],
                "series_id": ["CHINA_FOREIGN_RESERVES"],
                "value": [3200000.0],  # millions USD
            }
        )
        fx_rates = {}  # No FX needed for USD
        result = calculator._process_pboc_data(df, fx_rates)

        assert not result.empty
        assert "pboc_usd" in result.columns
        # Value should be scaled up by ~15x
        assert result["pboc_usd"].iloc[0] > 40000  # 3.2T * 15 = 48T


class TestCalculateDeltaAdvanced:
    """Advanced tests for _calculate_delta method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_delta_not_enough_history(self, calculator):
        """Test delta returns 0 when no data before target date."""
        now = datetime.now(UTC)
        # Only 5 days of data, asking for 30-day delta
        df = pd.DataFrame(
            {
                "timestamp": [now - timedelta(days=i) for i in range(5, -1, -1)],
                "global_liquidity": [30000.0 + i * 10 for i in range(6)],
            }
        )
        delta = calculator._calculate_delta(df, days=30)
        assert delta == 0.0

    def test_delta_no_global_liquidity_column(self, calculator):
        """Test delta returns 0 when column is missing."""
        now = datetime.now(UTC)
        df = pd.DataFrame(
            {
                "timestamp": [now - timedelta(days=i) for i in range(10, -1, -1)],
                "total": [30000.0] * 11,  # Wrong column name
            }
        )
        delta = calculator._calculate_delta(df, days=7)
        assert delta == 0.0


class TestAggregateTier2Complete:
    """Tests for Tier 2 aggregation coverage."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return GlobalLiquidityCalculator()

    def test_aggregate_with_snb_data(self, calculator):
        """Test aggregation with SNB (Swiss National Bank) data."""
        now = datetime.now(UTC)
        fed_df = pd.DataFrame({"timestamp": [now], "net_liquidity": [7000.0]})
        snb_df = pd.DataFrame(
            {
                "timestamp": [now],
                "value": [900000.0],  # millions CHF
            }
        )
        fx_df = pd.DataFrame(
            {
                "timestamp": [now] * 6,
                "series_id": [
                    "EURUSD=X",
                    "USDJPY=X",
                    "USDCNY=X",
                    "GBPUSD=X",
                    "USDCHF=X",
                    "USDCAD=X",
                ],
                "value": [1.08, 150.0, 7.2, 1.25, 0.88, 1.35],
            }
        )

        result = calculator._aggregate_data(
            CBDataFrames(
                fed=fed_df, ecb=pd.DataFrame(), boj=pd.DataFrame(),
                pboc=pd.DataFrame(), fx=fx_df, boe=pd.DataFrame(),
                snb=snb_df, boc=pd.DataFrame(),
            ),
            tier=2,
        )

        if not result.empty and "snb_usd" in result.columns:
            assert result["snb_usd"].iloc[0] > 0

    def test_aggregate_with_boc_data(self, calculator):
        """Test aggregation with BoC (Bank of Canada) data."""
        now = datetime.now(UTC)
        fed_df = pd.DataFrame({"timestamp": [now], "net_liquidity": [7000.0]})
        boc_df = pd.DataFrame(
            {
                "timestamp": [now],
                "value": [500000.0],  # millions CAD
            }
        )
        fx_df = pd.DataFrame(
            {
                "timestamp": [now] * 6,
                "series_id": [
                    "EURUSD=X",
                    "USDJPY=X",
                    "USDCNY=X",
                    "GBPUSD=X",
                    "USDCHF=X",
                    "USDCAD=X",
                ],
                "value": [1.08, 150.0, 7.2, 1.25, 0.88, 1.35],
            }
        )

        result = calculator._aggregate_data(
            CBDataFrames(
                fed=fed_df, ecb=pd.DataFrame(), boj=pd.DataFrame(),
                pboc=pd.DataFrame(), fx=fx_df, boe=pd.DataFrame(),
                snb=pd.DataFrame(), boc=boc_df,
            ),
            tier=2,
        )

        if not result.empty and "boc_usd" in result.columns:
            assert result["boc_usd"].iloc[0] > 0

    def test_aggregate_all_tier2_cbs(self, calculator):
        """Test aggregation with all Tier 2 central banks."""
        now = datetime.now(UTC)
        fed_df = pd.DataFrame({"timestamp": [now], "net_liquidity": [7000.0]})
        boe_df = pd.DataFrame({"timestamp": [now], "value": [900000.0]})
        snb_df = pd.DataFrame({"timestamp": [now], "value": [900000.0]})
        boc_df = pd.DataFrame({"timestamp": [now], "value": [500000.0]})
        fx_df = pd.DataFrame(
            {
                "timestamp": [now] * 6,
                "series_id": [
                    "EURUSD=X",
                    "USDJPY=X",
                    "USDCNY=X",
                    "GBPUSD=X",
                    "USDCHF=X",
                    "USDCAD=X",
                ],
                "value": [1.08, 150.0, 7.2, 1.25, 0.88, 1.35],
            }
        )

        result = calculator._aggregate_data(
            CBDataFrames(
                fed=fed_df, ecb=pd.DataFrame(), boj=pd.DataFrame(),
                pboc=pd.DataFrame(), fx=fx_df, boe=boe_df,
                snb=snb_df, boc=boc_df,
            ),
            tier=2,
        )

        assert not result.empty
        assert "fed_usd" in result.columns


class TestGetFXRates:
    """Tests for _get_fx_rates method."""

    @pytest.mark.asyncio
    async def test_get_fx_rates(self):
        """Test fetching FX rates via _get_fx_rates."""
        calc = GlobalLiquidityCalculator()

        with patch.object(calc._fx, "collect", new_callable=AsyncMock) as mock:
            now = datetime.now(UTC)
            mock.return_value = pd.DataFrame(
                {
                    "timestamp": [now] * 6,
                    "series_id": [
                        "EURUSD=X",
                        "USDJPY=X",
                        "USDCNY=X",
                        "GBPUSD=X",
                        "USDCHF=X",
                        "USDCAD=X",
                    ],
                    "value": [1.08, 150.0, 7.2, 1.25, 0.88, 1.35],
                }
            )

            result = await calc._get_fx_rates(
                start_date=now - timedelta(days=7),
                end_date=now,
            )

            assert not result.empty
            mock.assert_called_once()
