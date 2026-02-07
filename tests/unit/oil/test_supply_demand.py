"""Unit tests for oil supply-demand balance calculator.

Tests SupplyDemandCalculator and SupplyDemandBalance dataclass.
Run with: uv run pytest tests/unit/oil/test_supply_demand.py -v
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from liquidity.oil.supply_demand import (
    BUILD_THRESHOLD,
    DAYS_PER_WEEK,
    DRAW_THRESHOLD,
    SUPPLY_DEMAND_SERIES,
    SupplyDemandBalance,
    SupplyDemandCalculator,
)


class TestSupplyDemandConstants:
    """Tests for supply-demand constants."""

    def test_supply_demand_series_contains_production(self) -> None:
        """Test SUPPLY_DEMAND_SERIES contains production."""
        assert "production" in SUPPLY_DEMAND_SERIES
        assert SUPPLY_DEMAND_SERIES["production"] == "WCRFPUS2"

    def test_supply_demand_series_contains_imports(self) -> None:
        """Test SUPPLY_DEMAND_SERIES contains imports."""
        assert "imports" in SUPPLY_DEMAND_SERIES
        assert SUPPLY_DEMAND_SERIES["imports"] == "WCRIMUS2"

    def test_supply_demand_series_contains_exports(self) -> None:
        """Test SUPPLY_DEMAND_SERIES contains exports."""
        assert "exports" in SUPPLY_DEMAND_SERIES
        assert SUPPLY_DEMAND_SERIES["exports"] == "WCREXUS2"

    def test_supply_demand_series_contains_refinery_inputs(self) -> None:
        """Test SUPPLY_DEMAND_SERIES contains refinery_inputs."""
        assert "refinery_inputs" in SUPPLY_DEMAND_SERIES
        assert SUPPLY_DEMAND_SERIES["refinery_inputs"] == "WCRRIUS2"

    def test_build_threshold_is_positive(self) -> None:
        """Test BUILD_THRESHOLD is positive (100 thousand b/d)."""
        assert BUILD_THRESHOLD == 100.0
        assert BUILD_THRESHOLD > 0

    def test_draw_threshold_is_negative(self) -> None:
        """Test DRAW_THRESHOLD is negative (-100 thousand b/d)."""
        assert DRAW_THRESHOLD == -100.0
        assert DRAW_THRESHOLD < 0

    def test_days_per_week(self) -> None:
        """Test DAYS_PER_WEEK is 7."""
        assert DAYS_PER_WEEK == 7


class TestSupplyDemandBalance:
    """Tests for SupplyDemandBalance dataclass."""

    def test_balance_dataclass_fields(self) -> None:
        """Test SupplyDemandBalance has all required fields."""
        balance = SupplyDemandBalance(
            date=datetime(2026, 2, 5, tzinfo=UTC),
            production=13100.0,
            imports=6200.0,
            exports=4000.0,
            refinery_inputs=15000.0,
            total_supply=19300.0,
            total_demand=19000.0,
            balance=300.0,
            balance_barrels=2.1,
            signal="build",
        )

        assert balance.date == datetime(2026, 2, 5, tzinfo=UTC)
        assert balance.production == 13100.0
        assert balance.imports == 6200.0
        assert balance.exports == 4000.0
        assert balance.refinery_inputs == 15000.0
        assert balance.total_supply == 19300.0
        assert balance.total_demand == 19000.0
        assert balance.balance == 300.0
        assert balance.balance_barrels == 2.1
        assert balance.signal == "build"

    def test_balance_signal_types(self) -> None:
        """Test SupplyDemandBalance accepts valid signal types."""
        for signal in ["build", "draw", "flat"]:
            balance = SupplyDemandBalance(
                date=datetime(2026, 2, 5, tzinfo=UTC),
                production=13000.0,
                imports=6000.0,
                exports=4000.0,
                refinery_inputs=15000.0,
                total_supply=19000.0,
                total_demand=19000.0,
                balance=0.0,
                balance_barrels=0.0,
                signal=signal,
            )
            assert balance.signal == signal


class TestSupplyDemandCalculatorInit:
    """Tests for SupplyDemandCalculator initialization."""

    def test_init_default_collector(self) -> None:
        """Test init creates calculator without collector."""
        calc = SupplyDemandCalculator()
        assert calc._collector is None
        assert calc._owns_collector is True

    def test_init_with_collector(self) -> None:
        """Test init accepts external collector."""
        mock_collector = AsyncMock()
        calc = SupplyDemandCalculator(eia_collector=mock_collector)
        assert calc._collector is mock_collector
        assert calc._owns_collector is False


class TestSignalClassification:
    """Tests for signal classification logic."""

    @pytest.fixture
    def calculator(self) -> SupplyDemandCalculator:
        """Create a calculator instance."""
        return SupplyDemandCalculator()

    def test_classify_signal_build(self, calculator: SupplyDemandCalculator) -> None:
        """Test balance > 100 returns 'build'."""
        assert calculator._classify_signal(150.0) == "build"
        assert calculator._classify_signal(101.0) == "build"
        assert calculator._classify_signal(1000.0) == "build"

    def test_classify_signal_draw(self, calculator: SupplyDemandCalculator) -> None:
        """Test balance < -100 returns 'draw'."""
        assert calculator._classify_signal(-150.0) == "draw"
        assert calculator._classify_signal(-101.0) == "draw"
        assert calculator._classify_signal(-1000.0) == "draw"

    def test_classify_signal_flat(self, calculator: SupplyDemandCalculator) -> None:
        """Test -100 <= balance <= 100 returns 'flat'."""
        assert calculator._classify_signal(0.0) == "flat"
        assert calculator._classify_signal(50.0) == "flat"
        assert calculator._classify_signal(-50.0) == "flat"
        assert calculator._classify_signal(100.0) == "flat"
        assert calculator._classify_signal(-100.0) == "flat"

    def test_classify_signal_at_boundary(
        self, calculator: SupplyDemandCalculator
    ) -> None:
        """Test signal at exact boundaries."""
        # At 100: flat (not > 100)
        assert calculator._classify_signal(100.0) == "flat"
        # Just above 100: build
        assert calculator._classify_signal(100.01) == "build"
        # At -100: flat (not < -100)
        assert calculator._classify_signal(-100.0) == "flat"
        # Just below -100: draw
        assert calculator._classify_signal(-100.01) == "draw"


class TestBalanceToWeeklyBarrels:
    """Tests for balance to weekly barrels conversion."""

    @pytest.fixture
    def calculator(self) -> SupplyDemandCalculator:
        """Create a calculator instance."""
        return SupplyDemandCalculator()

    def test_positive_balance_conversion(
        self, calculator: SupplyDemandCalculator
    ) -> None:
        """Test positive balance converts correctly."""
        # 100 thousand b/d * 7 days / 1000 = 0.7 million barrels/week
        result = calculator._balance_to_weekly_barrels(100.0)
        assert abs(result - 0.7) < 0.001

    def test_negative_balance_conversion(
        self, calculator: SupplyDemandCalculator
    ) -> None:
        """Test negative balance converts correctly."""
        # -100 thousand b/d * 7 days / 1000 = -0.7 million barrels/week
        result = calculator._balance_to_weekly_barrels(-100.0)
        assert abs(result - (-0.7)) < 0.001

    def test_zero_balance_conversion(
        self, calculator: SupplyDemandCalculator
    ) -> None:
        """Test zero balance converts to zero."""
        result = calculator._balance_to_weekly_barrels(0.0)
        assert result == 0.0

    def test_large_balance_conversion(
        self, calculator: SupplyDemandCalculator
    ) -> None:
        """Test large balance converts correctly."""
        # 1000 thousand b/d * 7 days / 1000 = 7.0 million barrels/week
        result = calculator._balance_to_weekly_barrels(1000.0)
        assert abs(result - 7.0) < 0.001


@pytest.fixture
def mock_eia_response_df() -> pd.DataFrame:
    """Create mock EIA data for supply-demand calculation."""
    dates = pd.date_range("2026-01-01", periods=4, freq="W")
    rows = []

    # Create data for each series at each date
    for date in dates:
        rows.extend(
            [
                {
                    "timestamp": date,
                    "series_id": "WCRFPUS2",  # production
                    "source": "eia",
                    "value": 13100.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": date,
                    "series_id": "WCRIMUS2",  # imports
                    "source": "eia",
                    "value": 6200.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": date,
                    "series_id": "WCREXUS2",  # exports
                    "source": "eia",
                    "value": 4000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": date,
                    "series_id": "WCRRIUS2",  # refinery inputs
                    "source": "eia",
                    "value": 15000.0,
                    "unit": "thousand_bpd",
                },
            ]
        )

    return pd.DataFrame(rows)


class TestCalculateBalance:
    """Tests for calculate_balance method."""

    @pytest.fixture
    def calculator_with_mock_collector(
        self, mock_eia_response_df: pd.DataFrame
    ) -> SupplyDemandCalculator:
        """Create calculator with mocked EIA collector."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_eia_response_df)
        return SupplyDemandCalculator(eia_collector=mock_collector)

    @pytest.mark.asyncio
    async def test_calculate_balance_returns_dataframe(
        self, calculator_with_mock_collector: SupplyDemandCalculator
    ) -> None:
        """Test calculate_balance returns DataFrame."""
        result = await calculator_with_mock_collector.calculate_balance()
        assert isinstance(result, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_calculate_balance_columns(
        self, calculator_with_mock_collector: SupplyDemandCalculator
    ) -> None:
        """Test calculate_balance returns correct columns."""
        result = await calculator_with_mock_collector.calculate_balance()

        expected_columns = [
            "date",
            "production",
            "imports",
            "exports",
            "refinery_inputs",
            "total_supply",
            "total_demand",
            "balance",
            "balance_barrels",
            "signal",
        ]
        for col in expected_columns:
            assert col in result.columns

    @pytest.mark.asyncio
    async def test_calculate_balance_formulas(
        self, calculator_with_mock_collector: SupplyDemandCalculator
    ) -> None:
        """Test calculate_balance applies correct formulas."""
        result = await calculator_with_mock_collector.calculate_balance()

        # Check each row
        for _, row in result.iterrows():
            # total_supply = production + imports
            expected_supply = row["production"] + row["imports"]
            assert abs(row["total_supply"] - expected_supply) < 0.01

            # total_demand = refinery_inputs + exports
            expected_demand = row["refinery_inputs"] + row["exports"]
            assert abs(row["total_demand"] - expected_demand) < 0.01

            # balance = total_supply - total_demand
            expected_balance = row["total_supply"] - row["total_demand"]
            assert abs(row["balance"] - expected_balance) < 0.01

    @pytest.mark.asyncio
    async def test_calculate_balance_with_build_signal(self) -> None:
        """Test calculate_balance with data that produces build signal."""
        # Create data where supply > demand by > 100 kb/d
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRFPUS2",
                    "source": "eia",
                    "value": 14000.0,  # Higher production
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRIMUS2",
                    "source": "eia",
                    "value": 6000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCREXUS2",
                    "source": "eia",
                    "value": 4000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRRIUS2",
                    "source": "eia",
                    "value": 15000.0,
                    "unit": "thousand_bpd",
                },
            ]
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_df)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.calculate_balance()

        # supply = 14000 + 6000 = 20000
        # demand = 15000 + 4000 = 19000
        # balance = 20000 - 19000 = 1000 kb/d (build)
        assert result.iloc[0]["signal"] == "build"
        assert result.iloc[0]["balance"] == 1000.0

    @pytest.mark.asyncio
    async def test_calculate_balance_with_draw_signal(self) -> None:
        """Test calculate_balance with data that produces draw signal."""
        # Create data where supply < demand by > 100 kb/d
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRFPUS2",
                    "source": "eia",
                    "value": 12000.0,  # Lower production
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRIMUS2",
                    "source": "eia",
                    "value": 5000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCREXUS2",
                    "source": "eia",
                    "value": 4000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRRIUS2",
                    "source": "eia",
                    "value": 16000.0,  # Higher refinery inputs
                    "unit": "thousand_bpd",
                },
            ]
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_df)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.calculate_balance()

        # supply = 12000 + 5000 = 17000
        # demand = 16000 + 4000 = 20000
        # balance = 17000 - 20000 = -3000 kb/d (draw)
        assert result.iloc[0]["signal"] == "draw"
        assert result.iloc[0]["balance"] == -3000.0

    @pytest.mark.asyncio
    async def test_calculate_balance_with_flat_signal(self) -> None:
        """Test calculate_balance with data that produces flat signal."""
        # Create data where supply ~= demand (within +/- 100 kb/d)
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRFPUS2",
                    "source": "eia",
                    "value": 13000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRIMUS2",
                    "source": "eia",
                    "value": 6000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCREXUS2",
                    "source": "eia",
                    "value": 4000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRRIUS2",
                    "source": "eia",
                    "value": 15000.0,
                    "unit": "thousand_bpd",
                },
            ]
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_df)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.calculate_balance()

        # supply = 13000 + 6000 = 19000
        # demand = 15000 + 4000 = 19000
        # balance = 19000 - 19000 = 0 kb/d (flat)
        assert result.iloc[0]["signal"] == "flat"
        assert result.iloc[0]["balance"] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_balance_empty_data(self) -> None:
        """Test calculate_balance with empty EIA data."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=pd.DataFrame())
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.calculate_balance()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_calculate_balance_sorted_by_date(
        self, calculator_with_mock_collector: SupplyDemandCalculator
    ) -> None:
        """Test calculate_balance returns data sorted by date."""
        result = await calculator_with_mock_collector.calculate_balance()

        # Check dates are in ascending order
        dates = result["date"].tolist()
        assert dates == sorted(dates)


class TestGetCurrentBalance:
    """Tests for get_current_balance method."""

    @pytest.mark.asyncio
    async def test_get_current_balance_returns_dataclass(self) -> None:
        """Test get_current_balance returns SupplyDemandBalance."""
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRFPUS2",
                    "source": "eia",
                    "value": 13100.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRIMUS2",
                    "source": "eia",
                    "value": 6200.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCREXUS2",
                    "source": "eia",
                    "value": 4000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRRIUS2",
                    "source": "eia",
                    "value": 15000.0,
                    "unit": "thousand_bpd",
                },
            ]
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_df)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.get_current_balance()

        assert isinstance(result, SupplyDemandBalance)

    @pytest.mark.asyncio
    async def test_get_current_balance_correct_values(self) -> None:
        """Test get_current_balance returns correct values."""
        mock_df = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRFPUS2",
                    "source": "eia",
                    "value": 13100.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRIMUS2",
                    "source": "eia",
                    "value": 6200.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCREXUS2",
                    "source": "eia",
                    "value": 4000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRRIUS2",
                    "source": "eia",
                    "value": 15000.0,
                    "unit": "thousand_bpd",
                },
            ]
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_df)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.get_current_balance()

        assert result.production == 13100.0
        assert result.imports == 6200.0
        assert result.exports == 4000.0
        assert result.refinery_inputs == 15000.0
        assert result.total_supply == 19300.0  # 13100 + 6200
        assert result.total_demand == 19000.0  # 15000 + 4000
        assert result.balance == 300.0  # 19300 - 19000
        # balance_barrels = 300 * 7 / 1000 = 2.1
        assert abs(result.balance_barrels - 2.1) < 0.01
        assert result.signal == "build"  # 300 > 100

    @pytest.mark.asyncio
    async def test_get_current_balance_raises_on_empty(self) -> None:
        """Test get_current_balance raises ValueError on empty data."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=pd.DataFrame())
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        with pytest.raises(ValueError, match="No supply-demand data available"):
            await calculator.get_current_balance()

    @pytest.mark.asyncio
    async def test_get_current_balance_uses_latest(self) -> None:
        """Test get_current_balance uses the most recent data."""
        # Create data for two weeks
        mock_df = pd.DataFrame(
            [
                # Week 1 - older
                {
                    "timestamp": pd.Timestamp("2026-01-29"),
                    "series_id": "WCRFPUS2",
                    "source": "eia",
                    "value": 12000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-01-29"),
                    "series_id": "WCRIMUS2",
                    "source": "eia",
                    "value": 5000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-01-29"),
                    "series_id": "WCREXUS2",
                    "source": "eia",
                    "value": 3000.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-01-29"),
                    "series_id": "WCRRIUS2",
                    "source": "eia",
                    "value": 14000.0,
                    "unit": "thousand_bpd",
                },
                # Week 2 - newer (should be used)
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRFPUS2",
                    "source": "eia",
                    "value": 13500.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRIMUS2",
                    "source": "eia",
                    "value": 6500.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCREXUS2",
                    "source": "eia",
                    "value": 4500.0,
                    "unit": "thousand_bpd",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-05"),
                    "series_id": "WCRRIUS2",
                    "source": "eia",
                    "value": 15500.0,
                    "unit": "thousand_bpd",
                },
            ]
        )

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_df)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.get_current_balance()

        # Should use 2026-02-05 data (the latest)
        assert result.production == 13500.0
        assert result.imports == 6500.0


class TestGetBalanceSummary:
    """Tests for get_balance_summary method."""

    @pytest.fixture
    def mock_balance_data(self) -> pd.DataFrame:
        """Create mock data for balance summary."""
        dates = pd.date_range("2026-01-08", periods=4, freq="W")
        rows = []

        # Create varying data for interesting summary
        production_values = [13000.0, 13100.0, 13200.0, 13150.0]
        imports_values = [6000.0, 6100.0, 6200.0, 6150.0]
        exports_values = [4000.0, 4000.0, 4000.0, 4000.0]
        refinery_values = [15000.0, 15100.0, 15200.0, 15100.0]

        for i, date in enumerate(dates):
            rows.extend(
                [
                    {
                        "timestamp": date,
                        "series_id": "WCRFPUS2",
                        "source": "eia",
                        "value": production_values[i],
                        "unit": "thousand_bpd",
                    },
                    {
                        "timestamp": date,
                        "series_id": "WCRIMUS2",
                        "source": "eia",
                        "value": imports_values[i],
                        "unit": "thousand_bpd",
                    },
                    {
                        "timestamp": date,
                        "series_id": "WCREXUS2",
                        "source": "eia",
                        "value": exports_values[i],
                        "unit": "thousand_bpd",
                    },
                    {
                        "timestamp": date,
                        "series_id": "WCRRIUS2",
                        "source": "eia",
                        "value": refinery_values[i],
                        "unit": "thousand_bpd",
                    },
                ]
            )

        return pd.DataFrame(rows)

    @pytest.mark.asyncio
    async def test_balance_summary_returns_dict(
        self, mock_balance_data: pd.DataFrame
    ) -> None:
        """Test get_balance_summary returns dictionary."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_balance_data)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.get_balance_summary()

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_balance_summary_contains_current(
        self, mock_balance_data: pd.DataFrame
    ) -> None:
        """Test get_balance_summary contains current balance."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_balance_data)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.get_balance_summary()

        assert "current" in result
        assert isinstance(result["current"], SupplyDemandBalance)

    @pytest.mark.asyncio
    async def test_balance_summary_contains_avg_balance(
        self, mock_balance_data: pd.DataFrame
    ) -> None:
        """Test get_balance_summary contains average balance."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_balance_data)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.get_balance_summary()

        assert "avg_balance" in result
        assert isinstance(result["avg_balance"], float)

    @pytest.mark.asyncio
    async def test_balance_summary_contains_total_barrels(
        self, mock_balance_data: pd.DataFrame
    ) -> None:
        """Test get_balance_summary contains total barrels."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_balance_data)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.get_balance_summary()

        assert "total_barrels" in result
        assert isinstance(result["total_barrels"], float)

    @pytest.mark.asyncio
    async def test_balance_summary_contains_signal_counts(
        self, mock_balance_data: pd.DataFrame
    ) -> None:
        """Test get_balance_summary contains signal counts."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_balance_data)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.get_balance_summary()

        assert "signal_counts" in result
        assert isinstance(result["signal_counts"], dict)

    @pytest.mark.asyncio
    async def test_balance_summary_contains_weeks_analyzed(
        self, mock_balance_data: pd.DataFrame
    ) -> None:
        """Test get_balance_summary contains weeks_analyzed."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_balance_data)
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        result = await calculator.get_balance_summary()

        assert "weeks_analyzed" in result
        assert isinstance(result["weeks_analyzed"], int)

    @pytest.mark.asyncio
    async def test_balance_summary_raises_on_empty(self) -> None:
        """Test get_balance_summary raises ValueError on empty data."""
        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=pd.DataFrame())
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        with pytest.raises(ValueError, match="No supply-demand data available"):
            await calculator.get_balance_summary()


class TestCalculatorClose:
    """Tests for calculator cleanup."""

    @pytest.mark.asyncio
    async def test_close_releases_owned_collector(self) -> None:
        """Test close releases collector when owned."""
        with patch("liquidity.oil.supply_demand.EIACollector") as mock_eia_class:
            mock_collector = AsyncMock()
            mock_eia_class.return_value = mock_collector

            calculator = SupplyDemandCalculator()
            # Create collector
            await calculator._get_collector()
            assert calculator._collector is not None

            await calculator.close()
            assert calculator._collector is None
            mock_collector.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_does_not_release_external_collector(self) -> None:
        """Test close does not release externally provided collector."""
        mock_collector = AsyncMock()
        calculator = SupplyDemandCalculator(eia_collector=mock_collector)

        await calculator.close()

        # Should not close external collector
        mock_collector.close.assert_not_called()
        # But should clear reference
        assert calculator._collector is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self) -> None:
        """Test close can be called multiple times safely."""
        calculator = SupplyDemandCalculator()
        await calculator.close()  # First call (no collector yet)
        await calculator.close()  # Second call (still safe)
        # Should not raise


class TestEmptyResultDataFrame:
    """Tests for _empty_result_df helper."""

    def test_empty_result_df_has_correct_columns(self) -> None:
        """Test _empty_result_df returns DataFrame with all columns."""
        calculator = SupplyDemandCalculator()
        result = calculator._empty_result_df()

        expected_columns = [
            "date",
            "production",
            "imports",
            "exports",
            "refinery_inputs",
            "total_supply",
            "total_demand",
            "balance",
            "balance_barrels",
            "signal",
        ]
        assert list(result.columns) == expected_columns

    def test_empty_result_df_has_zero_rows(self) -> None:
        """Test _empty_result_df returns empty DataFrame."""
        calculator = SupplyDemandCalculator()
        result = calculator._empty_result_df()

        assert len(result) == 0


class TestModuleExports:
    """Tests for module exports in oil/__init__.py."""

    def test_supply_demand_balance_exported(self) -> None:
        """Test SupplyDemandBalance is exported from oil module."""
        from liquidity.oil import SupplyDemandBalance as ExportedBalance

        assert ExportedBalance is SupplyDemandBalance

    def test_supply_demand_calculator_exported(self) -> None:
        """Test SupplyDemandCalculator is exported from oil module."""
        from liquidity.oil import SupplyDemandCalculator as ExportedCalculator

        assert ExportedCalculator is SupplyDemandCalculator


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
