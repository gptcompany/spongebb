"""Unit tests for StealthQECalculator."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from liquidity.calculators.stealth_qe import (
    SCORE_CONFIG,
    StealthQECalculator,
    StealthQEResult,
    StealthQEStatus,
)


class TestScoreConfig:
    """Tests for score configuration."""

    def test_weights_sum_to_one(self):
        """Test that component weights sum to 1.0."""
        total = (
            SCORE_CONFIG["WEIGHT_RRP"]
            + SCORE_CONFIG["WEIGHT_TGA"]
            + SCORE_CONFIG["WEIGHT_FED"]
        )
        assert total == pytest.approx(1.0)

    def test_config_values(self):
        """Test config has expected values."""
        assert SCORE_CONFIG["RRP_VELOCITY_MAX"] == 20
        assert SCORE_CONFIG["TGA_SPENDING_MAX"] == 200
        assert SCORE_CONFIG["FED_CHANGE_MAX"] == 100
        assert SCORE_CONFIG["WEIGHT_RRP"] == 0.40
        assert SCORE_CONFIG["WEIGHT_TGA"] == 0.40
        assert SCORE_CONFIG["WEIGHT_FED"] == 0.20
        assert SCORE_CONFIG["MAX_DAILY_CHANGE"] == 25


class TestStealthQEStatus:
    """Tests for StealthQEStatus enum."""

    def test_status_values(self):
        """Test status enum has correct values."""
        assert StealthQEStatus.VERY_ACTIVE == "VERY_ACTIVE"
        assert StealthQEStatus.ACTIVE == "ACTIVE"
        assert StealthQEStatus.MODERATE == "MODERATE"
        assert StealthQEStatus.LOW == "LOW"
        assert StealthQEStatus.MINIMAL == "MINIMAL"


class TestStealthQEResult:
    """Tests for StealthQEResult dataclass."""

    def test_dataclass_creation(self):
        """Test result dataclass can be created."""
        result = StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=50.0,
            score_weekly=45.0,
            rrp_level=100.0,
            rrp_velocity=-5.0,
            tga_level=800.0,
            tga_spending=50.0,
            fed_total=8000.0,
            fed_change=25.0,
            components="RRP:25% TGA:25% FED:25%",
            status="ACTIVE",
        )
        assert result.score_daily == 50.0
        assert result.status == "ACTIVE"

    def test_dataclass_with_none_weekly(self):
        """Test result with None weekly score."""
        result = StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=30.0,
            score_weekly=None,
            rrp_level=100.0,
            rrp_velocity=None,
            tga_level=800.0,
            tga_spending=None,
            fed_total=8000.0,
            fed_change=None,
            components="RRP:0% TGA:0% FED:0%",
            status="MODERATE",
        )
        assert result.score_weekly is None


class TestStealthQECalculator:
    """Tests for StealthQECalculator class."""

    def test_init(self):
        """Test calculator initialization."""
        calc = StealthQECalculator()
        assert calc is not None
        assert calc.SCORE_CONFIG == SCORE_CONFIG

    def test_repr(self):
        """Test string representation."""
        calc = StealthQECalculator()
        assert "StealthQECalculator" in repr(calc)


class TestGetStatus:
    """Tests for status classification."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return StealthQECalculator()

    def test_very_active(self, calculator):
        """Test VERY_ACTIVE status (70-100)."""
        assert calculator.get_status(70.0) == StealthQEStatus.VERY_ACTIVE
        assert calculator.get_status(85.0) == StealthQEStatus.VERY_ACTIVE
        assert calculator.get_status(100.0) == StealthQEStatus.VERY_ACTIVE

    def test_active(self, calculator):
        """Test ACTIVE status (50-70)."""
        assert calculator.get_status(50.0) == StealthQEStatus.ACTIVE
        assert calculator.get_status(60.0) == StealthQEStatus.ACTIVE
        assert calculator.get_status(69.9) == StealthQEStatus.ACTIVE

    def test_moderate(self, calculator):
        """Test MODERATE status (30-50)."""
        assert calculator.get_status(30.0) == StealthQEStatus.MODERATE
        assert calculator.get_status(40.0) == StealthQEStatus.MODERATE
        assert calculator.get_status(49.9) == StealthQEStatus.MODERATE

    def test_low(self, calculator):
        """Test LOW status (10-30)."""
        assert calculator.get_status(10.0) == StealthQEStatus.LOW
        assert calculator.get_status(20.0) == StealthQEStatus.LOW
        assert calculator.get_status(29.9) == StealthQEStatus.LOW

    def test_minimal(self, calculator):
        """Test MINIMAL status (0-10)."""
        assert calculator.get_status(0.0) == StealthQEStatus.MINIMAL
        assert calculator.get_status(5.0) == StealthQEStatus.MINIMAL
        assert calculator.get_status(9.9) == StealthQEStatus.MINIMAL


class TestCalculateComponents:
    """Tests for component calculation."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return StealthQECalculator()

    def test_all_zero_when_positive_rrp(self, calculator):
        """Test RRP component is 0 when velocity is positive."""
        comp = calculator._calculate_components(
            rrp_velocity=5.0,  # Positive = no injection
            tga_spending=0.0,
            fed_change=0.0,
        )
        assert comp[0] == 0.0  # RRP component

    def test_rrp_component_negative_velocity(self, calculator):
        """Test RRP component with negative velocity."""
        # -10% velocity = 50% of max (20%)
        comp = calculator._calculate_components(
            rrp_velocity=-10.0,
            tga_spending=0.0,
            fed_change=0.0,
        )
        assert comp[0] == pytest.approx(50.0)

    def test_rrp_component_at_max(self, calculator):
        """Test RRP component at max velocity."""
        # -20% velocity = 100%
        comp = calculator._calculate_components(
            rrp_velocity=-20.0,
            tga_spending=0.0,
            fed_change=0.0,
        )
        assert comp[0] == pytest.approx(100.0)

    def test_rrp_component_exceeds_max(self, calculator):
        """Test RRP component capped at 100."""
        # -40% velocity should still be capped at 100
        comp = calculator._calculate_components(
            rrp_velocity=-40.0,
            tga_spending=0.0,
            fed_change=0.0,
        )
        assert comp[0] == 100.0

    def test_tga_component_positive_spending(self, calculator):
        """Test TGA component with positive spending."""
        # $100B spending = 50% of max ($200B)
        comp = calculator._calculate_components(
            rrp_velocity=0.0,
            tga_spending=100.0,
            fed_change=0.0,
        )
        assert comp[1] == pytest.approx(50.0)

    def test_tga_component_zero_when_negative(self, calculator):
        """Test TGA component is 0 when spending is negative."""
        comp = calculator._calculate_components(
            rrp_velocity=0.0,
            tga_spending=-50.0,  # TGA increasing, not spending
            fed_change=0.0,
        )
        assert comp[1] == 0.0

    def test_fed_component_positive_change(self, calculator):
        """Test Fed component with positive change."""
        # $50B change = 50% of max ($100B)
        comp = calculator._calculate_components(
            rrp_velocity=0.0,
            tga_spending=0.0,
            fed_change=50.0,
        )
        assert comp[2] == pytest.approx(50.0)

    def test_fed_component_zero_when_negative(self, calculator):
        """Test Fed component is 0 when change is negative."""
        comp = calculator._calculate_components(
            rrp_velocity=0.0,
            tga_spending=0.0,
            fed_change=-25.0,  # Fed shrinking, not expanding
        )
        assert comp[2] == 0.0

    def test_all_components_at_max(self, calculator):
        """Test maximum score calculation."""
        # All at threshold
        comp = calculator._calculate_components(
            rrp_velocity=-20.0,  # 100%
            tga_spending=200.0,  # 100%
            fed_change=100.0,  # 100%
        )
        assert comp[0] == 100.0
        assert comp[1] == 100.0
        assert comp[2] == 100.0

    def test_none_values(self, calculator):
        """Test handling of None values."""
        comp = calculator._calculate_components(
            rrp_velocity=None,
            tga_spending=None,
            fed_change=None,
        )
        assert comp[0] == 0.0
        assert comp[1] == 0.0
        assert comp[2] == 0.0


class TestScoreCalculation:
    """Tests for full score calculation."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return StealthQECalculator()

    def test_score_formula(self, calculator):
        """Test the weighted score formula."""
        # Components: RRP=50, TGA=50, FED=50
        # Score = 50*0.4 + 50*0.4 + 50*0.2 = 20 + 20 + 10 = 50
        comp = calculator._calculate_components(
            rrp_velocity=-10.0,  # 50%
            tga_spending=100.0,  # 50%
            fed_change=50.0,  # 50%
        )
        score = (
            comp[0] * SCORE_CONFIG["WEIGHT_RRP"]
            + comp[1] * SCORE_CONFIG["WEIGHT_TGA"]
            + comp[2] * SCORE_CONFIG["WEIGHT_FED"]
        )
        assert score == pytest.approx(50.0)


class TestEmptyDataFrames:
    """Tests for empty DataFrame handling."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return StealthQECalculator()

    def test_empty_daily_dataframe(self, calculator):
        """Test empty daily DataFrame has correct columns."""
        df = calculator._empty_daily_dataframe()
        expected_cols = [
            "timestamp",
            "score_daily",
            "rrp_level",
            "rrp_velocity",
            "tga_level",
            "tga_spending",
            "fed_total",
            "fed_change",
            "comp_rrp",
            "comp_tga",
            "comp_fed",
            "status",
        ]
        assert list(df.columns) == expected_cols
        assert df.empty

    def test_empty_weekly_dataframe(self, calculator):
        """Test empty weekly DataFrame has correct columns."""
        df = calculator._empty_weekly_dataframe()
        expected_cols = [
            "timestamp",
            "score_weekly",
            "rrp_level",
            "rrp_velocity",
            "tga_level",
            "tga_spending",
            "fed_total",
            "fed_change",
            "components",
            "status",
        ]
        assert list(df.columns) == expected_cols
        assert df.empty


class TestCalculateWeeklyChanges:
    """Tests for _calculate_weekly_changes method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return StealthQECalculator()

    def test_calculate_weekly_changes(self, calculator):
        """Test weekly changes calculation."""
        # Create mock series with 8 data points
        rrp_level = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 90.0])
        tga_level = pd.Series([800.0, 800.0, 800.0, 800.0, 800.0, 800.0, 800.0, 750.0])
        fed_total = pd.Series(
            [8000.0, 8000.0, 8000.0, 8000.0, 8000.0, 8000.0, 8000.0, 8050.0]
        )

        rrp_velocity, tga_spending, fed_change = calculator._calculate_weekly_changes(
            rrp_level, tga_level, fed_total, idx=7
        )

        # RRP: (90 - 100) / 100 * 100 = -10%
        assert rrp_velocity == pytest.approx(-10.0)
        # TGA spending: -(750 - 800) = 50 (positive when TGA decreases)
        assert tga_spending == pytest.approx(50.0)
        # Fed change: 8050 - 8000 = 50
        assert fed_change == pytest.approx(50.0)

    def test_calculate_weekly_changes_zero_rrp(self, calculator):
        """Test weekly changes with near-zero RRP."""
        rrp_level = pd.Series([0.1] * 7 + [0.05])
        tga_level = pd.Series([800.0] * 8)
        fed_total = pd.Series([8000.0] * 8)

        rrp_velocity, tga_spending, fed_change = calculator._calculate_weekly_changes(
            rrp_level, tga_level, fed_total, idx=7
        )

        # RRP velocity should be 0 when previous is near 0
        assert rrp_velocity == pytest.approx(0.0)


class TestApplySmoothing:
    """Tests for _apply_smoothing method."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return StealthQECalculator()

    def test_smoothing_first_week(self, calculator):
        """Test smoothing returns raw score during first week (idx <= 7)."""
        # Smoothing only applies after idx > 7
        result = calculator._apply_smoothing(raw_score=50.0, prev_score=0.0, idx=5)
        assert result == 50.0

    def test_smoothing_no_prev_score(self, calculator):
        """Test smoothing returns raw score when prev_score is 0."""
        # Smoothing requires prev_score > 0
        result = calculator._apply_smoothing(raw_score=50.0, prev_score=0.0, idx=10)
        assert result == 50.0

    def test_smoothing_limits_increase(self, calculator):
        """Test smoothing limits daily increase to MAX_DAILY_CHANGE."""
        # idx > 7 and prev_score > 0, so smoothing applies
        # prev=30, raw=80, max_change=25 -> result should be clamped to 55
        result = calculator._apply_smoothing(raw_score=80.0, prev_score=30.0, idx=10)
        assert result == pytest.approx(55.0)

    def test_smoothing_limits_decrease(self, calculator):
        """Test smoothing limits daily decrease to MAX_DAILY_CHANGE."""
        # idx > 7 and prev_score > 0, so smoothing applies
        # prev=50, raw=0, max_change=25 -> result should be clamped to 25
        result = calculator._apply_smoothing(raw_score=0.0, prev_score=50.0, idx=10)
        assert result == pytest.approx(25.0)

    def test_smoothing_small_change(self, calculator):
        """Test smoothing allows small changes within limit."""
        # prev=50, raw=60, change=10 < max_change=25 -> result should be 60
        result = calculator._apply_smoothing(raw_score=60.0, prev_score=50.0, idx=10)
        assert result == pytest.approx(60.0)


class TestCalculateDaily:
    """Tests for calculate_daily method."""

    @pytest.fixture
    def mock_fred_data(self):
        """Create mock FRED data for Stealth QE."""
        from datetime import timedelta

        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(30, -1, -1)]

        return pd.DataFrame(
            {
                "timestamp": dates * 3,
                "series_id": (["WALCL"] * 31 + ["WTREGEN"] * 31 + ["RRPONTSYD"] * 31),
                "value": (
                    [8000000.0] * 31  # WALCL in millions
                    + [800000.0] * 31  # WTREGEN (TGA) in millions
                    + [500.0] * 31  # RRPONTSYD in billions
                ),
                "source": ["fred"] * 93,
            }
        )

    @pytest.mark.asyncio
    async def test_calculate_daily_empty_data(self):
        """Test calculate_daily with empty data."""
        calc = StealthQECalculator()

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = pd.DataFrame()
            result = await calc.calculate_daily()

            assert result.empty

    @pytest.mark.asyncio
    async def test_calculate_daily_missing_series(self):
        """Test calculate_daily with missing required series."""
        calc = StealthQECalculator()
        from datetime import timedelta

        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(15, -1, -1)]

        # Only WALCL, missing TGA and RRP - pivot will create only one column
        mock_data = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["WALCL"] * 16,
                "value": [8000000.0] * 16,
            }
        )

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            result = await calc.calculate_daily()

            assert result.empty

    @pytest.mark.asyncio
    async def test_calculate_daily_insufficient_data(self):
        """Test calculate_daily with less than 8 days of data."""
        calc = StealthQECalculator()
        from datetime import timedelta

        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(5, -1, -1)]  # Only 6 days

        mock_data = pd.DataFrame(
            {
                "timestamp": dates * 3,
                "series_id": ["WALCL"] * 6 + ["WTREGEN"] * 6 + ["RRPONTSYD"] * 6,
                "value": [8000000.0] * 6 + [800000.0] * 6 + [500.0] * 6,
            }
        )

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            result = await calc.calculate_daily()

            assert result.empty

    @pytest.mark.asyncio
    async def test_calculate_daily_with_data(self, mock_fred_data):
        """Test calculate_daily with valid data."""
        calc = StealthQECalculator()

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_fred_data
            result = await calc.calculate_daily()

            assert not result.empty
            assert "score_daily" in result.columns
            assert "status" in result.columns
            assert "comp_rrp" in result.columns


class TestCalculateWeekly:
    """Tests for calculate_weekly method."""

    @pytest.mark.asyncio
    async def test_calculate_weekly_empty_data(self):
        """Test calculate_weekly with empty data."""
        calc = StealthQECalculator()

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = pd.DataFrame()
            result = await calc.calculate_weekly()

            assert result.empty

    @pytest.mark.asyncio
    async def test_calculate_weekly_missing_series(self):
        """Test calculate_weekly with missing required series."""
        calc = StealthQECalculator()
        from datetime import timedelta

        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(15, -1, -1)]

        # Only WALCL, missing TGA and RRP - pivot will create only one column
        mock_data = pd.DataFrame(
            {
                "timestamp": dates,
                "series_id": ["WALCL"] * 16,
                "value": [8000000.0] * 16,
            }
        )

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            result = await calc.calculate_weekly()

            assert result.empty

    @pytest.mark.asyncio
    async def test_calculate_weekly_with_wednesdays(self):
        """Test calculate_weekly returns data only for Wednesdays."""
        calc = StealthQECalculator()
        from datetime import timedelta

        # Create dates spanning multiple weeks, ensuring we hit Wednesdays
        now = datetime.now(UTC)
        # Go back far enough to ensure we have data before start_date
        dates = [now - timedelta(days=i) for i in range(60, -1, -1)]

        mock_data = pd.DataFrame(
            {
                "timestamp": dates * 3,
                "series_id": (["WALCL"] * 61 + ["WTREGEN"] * 61 + ["RRPONTSYD"] * 61),
                "value": ([8000000.0] * 61 + [800000.0] * 61 + [500.0] * 61),
            }
        )

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            result = await calc.calculate_weekly()

            # May be empty if no Wednesdays fall in the date range, but columns should be correct
            if not result.empty:
                assert "score_weekly" in result.columns
                assert "components" in result.columns
                # Verify all rows are Wednesdays
                for ts in result["timestamp"]:
                    assert pd.Timestamp(ts).weekday() == 2  # Wednesday


class TestGetCurrent:
    """Tests for get_current method."""

    @pytest.mark.asyncio
    async def test_get_current_empty_data(self):
        """Test get_current with empty data raises ValueError."""
        calc = StealthQECalculator()

        with patch.object(calc, "calculate_daily", new_callable=AsyncMock) as mock:
            mock.return_value = pd.DataFrame()

            with pytest.raises(ValueError, match="No data available"):
                await calc.get_current()

    @pytest.mark.asyncio
    async def test_get_current_success(self):
        """Test successful get_current call."""
        calc = StealthQECalculator()
        now = datetime.now(UTC)

        mock_daily = pd.DataFrame(
            {
                "timestamp": [now],
                "score_daily": [45.0],
                "rrp_level": [500.0],
                "rrp_velocity": [-5.0],
                "tga_level": [800.0],
                "tga_spending": [25.0],
                "fed_total": [8000.0],
                "fed_change": [10.0],
                "comp_rrp": [25.0],
                "comp_tga": [12.5],
                "comp_fed": [10.0],
                "status": ["MODERATE"],
            }
        )

        with patch.object(
            calc, "calculate_daily", new_callable=AsyncMock
        ) as mock_daily_call:
            mock_daily_call.return_value = mock_daily
            result = await calc.get_current()

            assert isinstance(result, StealthQEResult)
            assert result.score_daily == 45.0
            assert result.status == "MODERATE"
            assert result.rrp_level == 500.0

    @pytest.mark.asyncio
    async def test_get_current_with_wednesday(self):
        """Test get_current on a Wednesday includes weekly score."""
        calc = StealthQECalculator()

        # Find next Wednesday
        from datetime import timedelta

        now = datetime.now(UTC)
        days_until_wednesday = (2 - now.weekday()) % 7
        wednesday = now + timedelta(days=days_until_wednesday)

        mock_daily = pd.DataFrame(
            {
                "timestamp": [wednesday],
                "score_daily": [50.0],
                "rrp_level": [500.0],
                "rrp_velocity": [-5.0],
                "tga_level": [800.0],
                "tga_spending": [25.0],
                "fed_total": [8000.0],
                "fed_change": [10.0],
                "comp_rrp": [25.0],
                "comp_tga": [12.5],
                "comp_fed": [10.0],
                "status": ["ACTIVE"],
            }
        )

        mock_weekly = pd.DataFrame(
            {
                "timestamp": [wednesday],
                "score_weekly": [55.0],
                "rrp_level": [500.0],
                "rrp_velocity": [-5.0],
                "tga_level": [800.0],
                "tga_spending": [25.0],
                "fed_total": [8000.0],
                "fed_change": [10.0],
                "components": "RRP:25% TGA:12% FED:10%",
                "status": ["ACTIVE"],
            }
        )

        with patch.object(calc, "calculate_daily", new_callable=AsyncMock) as mock_d:
            with patch.object(
                calc, "calculate_weekly", new_callable=AsyncMock
            ) as mock_w:
                mock_d.return_value = mock_daily
                mock_w.return_value = mock_weekly
                result = await calc.get_current()

                assert isinstance(result, StealthQEResult)
                assert result.score_daily == 50.0
                # Weekly score should be included on Wednesday
                assert result.score_weekly == 55.0


class TestCalculateWeeklyEdgeCases:
    """Edge case tests for calculate_weekly."""

    @pytest.mark.asyncio
    async def test_calculate_weekly_not_enough_data(self):
        """Test calculate_weekly with less than 8 rows of data."""
        calc = StealthQECalculator()
        now = datetime.now(UTC)

        # Only 5 days of data - not enough for weekly calculation
        dates = [now - timedelta(days=i) for i in range(4, -1, -1)]

        mock_data = pd.DataFrame(
            {
                "timestamp": dates * 3,
                "series_id": (["WALCL"] * 5 + ["WTREGEN"] * 5 + ["RRPONTSYD"] * 5),
                "value": ([8000000.0] * 5 + [800000.0] * 5 + [500.0] * 5),
            }
        )

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            result = await calc.calculate_weekly()

            # Should return empty due to < 8 rows (lines 385-386)
            assert result.empty

    @pytest.mark.asyncio
    async def test_calculate_weekly_wed_before_start_date(self):
        """Test weekly calc when Wednesday falls before start_date."""
        calc = StealthQECalculator()
        now = datetime.now(UTC)

        # 30 days of data, but we only request last 7 days
        dates = [now - timedelta(days=i) for i in range(29, -1, -1)]

        mock_data = pd.DataFrame(
            {
                "timestamp": dates * 3,
                "series_id": (["WALCL"] * 30 + ["WTREGEN"] * 30 + ["RRPONTSYD"] * 30),
                "value": ([8000000.0] * 30 + [800000.0] * 30 + [500.0] * 30),
            }
        )

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            # Short start_date so Wednesdays before it are skipped (lines 411-412)
            result = await calc.calculate_weekly(start_date=now - timedelta(days=5))

            # Result depends on whether any Wednesday falls within the 5-day window
            assert isinstance(result, pd.DataFrame)


class TestRRPVelocityEdgeCases:
    """Tests for RRP velocity edge cases in _calculate_weekly_changes."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return StealthQECalculator()

    def test_rrp_velocity_both_low(self, calculator):
        """Test RRP velocity when both prev and current are < 0.5."""
        # This tests lines 432-435 and 588 - when prev_rrp <= 0.5 but current >= 0.5
        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(30, -1, -1)]

        # Create series with very low RRP values
        rrp_level = pd.Series([0.1] * 31, index=dates)  # All < 0.5
        tga_level = pd.Series([800.0] * 31, index=dates)
        fed_total = pd.Series([8000.0] * 31, index=dates)

        # Test _calculate_weekly_changes with low RRP
        rrp_vel, tga_spend, fed_chg = calculator._calculate_weekly_changes(
            rrp_level, tga_level, fed_total, idx=15
        )

        # With prev_rrp < 0.5 and current_rrp < 0.5, velocity should be 0
        assert rrp_vel == 0.0

    def test_rrp_velocity_prev_low_current_high(self, calculator):
        """Test RRP velocity when prev < 0.5 but current >= 0.5."""
        now = datetime.now(UTC)
        dates = [now - timedelta(days=i) for i in range(30, -1, -1)]

        # RRP goes from low to high mid-series
        rrp_values = [0.1] * 15 + [100.0] * 16  # Low then high
        rrp_level = pd.Series(rrp_values, index=dates)
        tga_level = pd.Series([800.0] * 31, index=dates)
        fed_total = pd.Series([8000.0] * 31, index=dates)

        # At idx=20, current is high (100) but lookback (idx=13) is low (0.1)
        rrp_vel, tga_spend, fed_chg = calculator._calculate_weekly_changes(
            rrp_level, tga_level, fed_total, idx=20
        )

        # With prev_rrp < 0.5 but current_rrp >= 0.5, velocity should be None (lines 432-435)
        assert rrp_vel is None


class TestDailyPreStartSmoothing:
    """Tests for pre-start-date smoothing in _calculate_daily."""

    @pytest.mark.asyncio
    async def test_daily_pre_start_smoothing(self):
        """Test daily calculation with data before start_date for smoothing."""
        calc = StealthQECalculator()
        now = datetime.now(UTC)

        # Create 60 days of data but request only last 30 days
        dates = [now - timedelta(days=i) for i in range(59, -1, -1)]

        mock_data = pd.DataFrame(
            {
                "timestamp": dates * 3,
                "series_id": (["WALCL"] * 60 + ["WTREGEN"] * 60 + ["RRPONTSYD"] * 60),
                "value": ([8000000.0] * 60 + [800000.0] * 60 + [500.0] * 60),
            }
        )

        with patch.object(calc._collector, "collect", new_callable=AsyncMock) as mock:
            mock.return_value = mock_data
            # This should trigger lines 239-252 for data before start_date
            result = await calc.calculate_daily(start_date=now - timedelta(days=30))

            # Result should have data
            assert isinstance(result, pd.DataFrame)
