"""Unit tests for LiquidityValidator."""

from datetime import UTC, datetime, timedelta

import pytest

from liquidity.calculators.validation import (
    CheckResult,
    LiquidityValidator,
    ValidationResult,
)


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_dataclass_creation_passed(self):
        """Test creating a passed check result."""
        result = CheckResult(
            name="test_check",
            passed=True,
            expected=100.0,
            actual=100.0,
            tolerance=0.01,
            message="Check passed",
        )
        assert result.passed is True
        assert result.name == "test_check"

    def test_dataclass_creation_failed(self):
        """Test creating a failed check result."""
        result = CheckResult(
            name="test_check",
            passed=False,
            expected=100.0,
            actual=90.0,
            tolerance=0.01,
            message="Check failed: expected 100.0, got 90.0",
        )
        assert result.passed is False

    def test_dataclass_with_none_tolerance(self):
        """Test result with None tolerance."""
        result = CheckResult(
            name="freshness_check",
            passed=True,
            expected="< 7 days",
            actual="3 days",
            tolerance=None,
            message="Data is fresh",
        )
        assert result.tolerance is None


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_dataclass_creation(self):
        """Test creating validation result."""
        checks = [
            CheckResult("check1", True, 1.0, 1.0, 0.01, "OK"),
            CheckResult("check2", False, 2.0, 1.5, 0.01, "Failed"),
        ]
        result = ValidationResult(
            timestamp=datetime.now(UTC),
            checks=checks,
            passed=1,
            failed=1,
            warnings=0,
            coverage_pct=90.0,
            all_passed=False,
        )
        assert result.passed == 1
        assert result.failed == 1
        assert result.all_passed is False
        assert len(result.checks) == 2

    def test_all_passed_true(self):
        """Test all_passed when all checks pass."""
        checks = [
            CheckResult("check1", True, 1.0, 1.0, 0.01, "OK"),
            CheckResult("check2", True, 2.0, 2.0, 0.01, "OK"),
        ]
        result = ValidationResult(
            timestamp=datetime.now(UTC),
            checks=checks,
            passed=2,
            failed=0,
            warnings=0,
            coverage_pct=95.0,
            all_passed=True,
        )
        assert result.all_passed is True


class TestLiquidityValidator:
    """Tests for LiquidityValidator class."""

    def test_init(self):
        """Test validator initialization."""
        validator = LiquidityValidator()
        assert validator is not None
        assert validator.GLOBAL_CB_ESTIMATE == 35_000

    def test_max_age_config(self):
        """Test MAX_AGE configuration."""
        validator = LiquidityValidator()
        assert validator.MAX_AGE["WALCL"] == timedelta(days=7)
        assert validator.MAX_AGE["TGA"] == timedelta(days=2)
        assert validator.MAX_AGE["RRP"] == timedelta(days=2)
        assert validator.MAX_AGE["ECB"] == timedelta(days=7)


class TestValidateNetLiquidity:
    """Tests for Net Liquidity formula validation."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return LiquidityValidator()

    def test_valid_formula(self, validator):
        """Test valid Net Liquidity formula."""
        result = validator.validate_net_liquidity(
            walcl=8000.0,
            tga=800.0,
            rrp=500.0,
            reported_net_liq=6700.0,  # 8000 - 800 - 500 = 6700
        )
        assert result.passed is True
        assert "net_liquidity" in result.name.lower()

    def test_invalid_formula(self, validator):
        """Test invalid Net Liquidity formula."""
        result = validator.validate_net_liquidity(
            walcl=8000.0,
            tga=800.0,
            rrp=500.0,
            reported_net_liq=7000.0,  # Wrong: should be 6700
        )
        assert result.passed is False

    def test_within_tolerance(self, validator):
        """Test value within tolerance passes."""
        # 6700 * 0.01 = 67, so 6750 is within tolerance
        result = validator.validate_net_liquidity(
            walcl=8000.0,
            tga=800.0,
            rrp=500.0,
            reported_net_liq=6750.0,  # Within 1% of 6700
            tolerance=0.01,
        )
        assert result.passed is True

    def test_custom_tolerance(self, validator):
        """Test with custom tolerance."""
        result = validator.validate_net_liquidity(
            walcl=8000.0,
            tga=800.0,
            rrp=500.0,
            reported_net_liq=6800.0,  # ~1.5% off from 6700
            tolerance=0.02,  # 2% tolerance
        )
        assert result.passed is True

    def test_zero_values(self, validator):
        """Test with zero components."""
        result = validator.validate_net_liquidity(
            walcl=1000.0,
            tga=0.0,
            rrp=0.0,
            reported_net_liq=1000.0,
        )
        assert result.passed is True


class TestValidateGlobalSum:
    """Tests for Global Liquidity sum validation."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return LiquidityValidator()

    def test_valid_sum(self, validator):
        """Test valid Global Liquidity sum."""
        components = {
            "fed_usd": 6000.0,
            "ecb_usd": 7000.0,
            "boj_usd": 4000.0,
            "pboc_usd": 3000.0,
        }
        result = validator.validate_global_sum(
            components=components,
            reported_total=20000.0,  # Sum is exactly 20000
        )
        assert result.passed is True

    def test_invalid_sum(self, validator):
        """Test invalid Global Liquidity sum."""
        components = {
            "fed_usd": 6000.0,
            "ecb_usd": 7000.0,
            "boj_usd": 4000.0,
            "pboc_usd": 3000.0,
        }
        result = validator.validate_global_sum(
            components=components,
            reported_total=25000.0,  # Wrong: should be 20000
        )
        assert result.passed is False

    def test_alternative_key_names(self, validator):
        """Test with alternative key names (fed vs fed_usd)."""
        components = {
            "fed": 6000.0,
            "ecb": 7000.0,
            "boj": 4000.0,
            "pboc": 3000.0,
        }
        result = validator.validate_global_sum(
            components=components,
            reported_total=20000.0,
        )
        assert result.passed is True


class TestValidateCoverage:
    """Tests for coverage verification."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return LiquidityValidator()

    def test_coverage_above_threshold(self, validator):
        """Test coverage above 85% threshold."""
        # 30000 / 35000 = 85.7%
        result = validator.validate_coverage(tier1_total=30_000.0)
        assert result.passed is True
        assert result.actual >= 85.0

    def test_coverage_below_threshold(self, validator):
        """Test coverage below 85% threshold."""
        # 25000 / 35000 = 71.4%
        result = validator.validate_coverage(tier1_total=25_000.0)
        assert result.passed is False
        assert result.actual < 85.0

    def test_coverage_exactly_at_threshold(self, validator):
        """Test coverage exactly at 85%."""
        # 29750 / 35000 = 85.0%
        result = validator.validate_coverage(tier1_total=29_750.0)
        assert result.passed is True

    def test_custom_threshold(self, validator):
        """Test with custom coverage threshold."""
        result = validator.validate_coverage(
            tier1_total=25_000.0,  # 71.4%
            min_coverage=70.0,  # Lower threshold
        )
        assert result.passed is True

    def test_coverage_calculation(self, validator):
        """Test coverage percentage is calculated correctly."""
        result = validator.validate_coverage(tier1_total=17_500.0)  # 50%
        assert result.actual == pytest.approx(50.0)


class TestValidateFreshness:
    """Tests for data freshness validation."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return LiquidityValidator()

    def test_fresh_data(self, validator):
        """Test all data is fresh."""
        now = datetime.now(UTC)
        timestamps = {
            "WALCL": now - timedelta(days=3),
            "TGA": now - timedelta(hours=12),
            "RRP": now - timedelta(hours=6),
        }
        results = validator.validate_freshness(timestamps)

        assert len(results) == 3
        assert all(r.passed for r in results)

    def test_stale_walcl(self, validator):
        """Test stale WALCL data."""
        now = datetime.now(UTC)
        timestamps = {
            "WALCL": now - timedelta(days=10),  # Stale: > 7 days
            "TGA": now - timedelta(hours=12),
            "RRP": now - timedelta(hours=6),
        }
        results = validator.validate_freshness(timestamps)

        walcl_results = [r for r in results if "WALCL" in r.name.upper()]
        assert len(walcl_results) >= 1
        assert walcl_results[0].passed is False

    def test_stale_tga(self, validator):
        """Test stale TGA data."""
        now = datetime.now(UTC)
        timestamps = {
            "TGA": now - timedelta(days=5),  # Stale: > 2 days
        }
        results = validator.validate_freshness(timestamps)

        assert len(results) == 1
        assert results[0].passed is False

    def test_unknown_series(self, validator):
        """Test unknown series uses default MAX_AGE."""
        now = datetime.now(UTC)
        timestamps = {
            "UNKNOWN_SERIES": now - timedelta(days=100),
        }
        results = validator.validate_freshness(timestamps)

        # Unknown series should still be checked with default age
        assert len(results) == 1
        # 100 days old should be stale
        assert results[0].passed is False


class TestValidateAll:
    """Tests for validate_all method."""

    @pytest.mark.asyncio
    async def test_validate_all_empty(self):
        """Test validate_all with no data."""
        validator = LiquidityValidator()
        result = await validator.validate_all()

        assert isinstance(result, ValidationResult)
        assert result.checks is not None

    @pytest.mark.asyncio
    async def test_validate_all_with_net_liquidity(self):
        """Test validate_all with net liquidity data."""
        validator = LiquidityValidator()

        result = await validator.validate_all(
            net_liq_data={
                "walcl": 8000.0,
                "tga": 800.0,
                "rrp": 500.0,
                "net_liquidity": 6700.0,
            }
        )

        assert isinstance(result, ValidationResult)
        # Should have at least one check for net liquidity
        net_liq_checks = [c for c in result.checks if "net" in c.name.lower()]
        assert len(net_liq_checks) >= 1

    @pytest.mark.asyncio
    async def test_validate_all_with_coverage(self):
        """Test validate_all with coverage data."""
        validator = LiquidityValidator()

        result = await validator.validate_all(tier1_total=30_000.0)

        assert isinstance(result, ValidationResult)
        # Should have coverage check
        coverage_checks = [c for c in result.checks if "coverage" in c.name.lower()]
        assert len(coverage_checks) >= 1

    @pytest.mark.asyncio
    async def test_validate_all_with_global_liquidity(self):
        """Test validate_all with global liquidity data."""
        validator = LiquidityValidator()

        result = await validator.validate_all(
            global_liq_data={
                "fed_usd": 7000.0,
                "ecb_usd": 8000.0,
                "boj_usd": 5000.0,
                "pboc_usd": 6000.0,
                "total": 26000.0,  # Sum of components
            }
        )

        assert isinstance(result, ValidationResult)
        # Should have global sum check and coverage check
        assert result.passed >= 1

    @pytest.mark.asyncio
    async def test_validate_all_global_calculates_tier1(self):
        """Test validate_all derives tier1_total from global_liq_data."""
        validator = LiquidityValidator()

        # No tier1_total provided, but global_liq_data has tier1 components
        result = await validator.validate_all(
            global_liq_data={
                "fed_usd": 7000.0,
                "ecb_usd": 8000.0,
                "boj_usd": 5000.0,
                "pboc_usd": 10000.0,  # Total = 30000
            }
        )

        assert isinstance(result, ValidationResult)
        # Should have coverage check calculated from global components
        coverage_checks = [c for c in result.checks if "coverage" in c.name.lower()]
        assert len(coverage_checks) >= 1

    @pytest.mark.asyncio
    async def test_validate_all_with_freshness(self):
        """Test validate_all with freshness data."""
        validator = LiquidityValidator()

        now = datetime.now(UTC)
        result = await validator.validate_all(
            series_timestamps={
                "WALCL": now - timedelta(days=3),
                "TGA": now - timedelta(hours=12),
            }
        )

        assert isinstance(result, ValidationResult)
        # Should have freshness checks
        freshness_checks = [c for c in result.checks if "fresh" in c.name.lower()]
        assert len(freshness_checks) >= 1

    @pytest.mark.asyncio
    async def test_validate_all_combined(self):
        """Test validate_all with all validation types combined."""
        validator = LiquidityValidator()

        now = datetime.now(UTC)
        result = await validator.validate_all(
            net_liq_data={
                "walcl": 8000.0,
                "tga": 800.0,
                "rrp": 500.0,
                "net_liquidity": 6700.0,
            },
            tier1_total=30_000.0,
            series_timestamps={
                "WALCL": now - timedelta(days=3),
            },
        )

        assert isinstance(result, ValidationResult)
        # Should have multiple check types
        assert len(result.checks) >= 3  # net_liq, coverage, freshness


class TestLatestResult:
    """Tests for latest_result property."""

    def test_latest_result_default(self):
        """Test latest_result is None initially."""
        validator = LiquidityValidator()
        assert validator.latest_result is None

    @pytest.mark.asyncio
    async def test_latest_result_after_validate_all(self):
        """Test latest_result is populated after validate_all."""
        validator = LiquidityValidator()
        await validator.validate_all(tier1_total=30_000.0)
        assert validator.latest_result is not None
        assert isinstance(validator.latest_result, ValidationResult)


class TestEdgeCases:
    """Tests for edge case inputs."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return LiquidityValidator()

    def test_net_liquidity_near_zero(self, validator):
        """Test net liquidity validation with near-zero reported value."""
        result = validator.validate_net_liquidity(
            walcl=0.0005,
            tga=0.0001,
            rrp=0.0001,
            reported_net_liq=0.0003,  # Near zero
        )
        # Should use absolute difference (line 260)
        assert result.passed is True

    def test_global_sum_near_zero(self, validator):
        """Test global sum validation with near-zero reported total."""
        components = {
            "fed_usd": 0.0001,
            "ecb_usd": 0.0001,
        }
        result = validator.validate_global_sum(
            components=components,
            reported_total=0.0002,  # Near zero
        )
        # Should use absolute difference (line 322)
        assert result.passed is True

    def test_freshness_naive_datetime(self, validator):
        """Test freshness validation with naive datetime."""
        # Create naive datetime (no tzinfo)
        naive_dt = datetime.now()  # No UTC
        assert naive_dt.tzinfo is None

        timestamps = {"WALCL": naive_dt}
        results = validator.validate_freshness(timestamps)

        # Should handle naive datetime (line 441)
        assert len(results) == 1
        assert results[0].passed is True
