"""Double-Entry Validation & Coverage Verification for Liquidity Calculations.

Implements data validation to ensure calculation integrity and verify
coverage requirements for Global Liquidity monitoring.

Validation Checks:
1. Net Liquidity Formula: WALCL - TGA - RRP = reported Net Liquidity
2. Global Liquidity Sum: Fed + ECB + BoJ + PBoC = total
3. Coverage Verification: Tier 1 covers >85% of estimated global CB assets
4. Data Freshness: Data is not stale based on expected update frequency
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a single validation check.

    Attributes:
        name: Name of the validation check.
        passed: Whether the check passed.
        expected: Expected value or condition.
        actual: Actual value observed.
        tolerance: Tolerance used for numeric comparisons (if applicable).
        message: Human-readable description of the result.
    """

    name: str
    passed: bool
    expected: Any
    actual: Any
    tolerance: float | None
    message: str


@dataclass
class ValidationResult:
    """Aggregated result of all validation checks.

    Attributes:
        timestamp: When the validation was performed.
        checks: List of individual check results.
        passed: Number of checks that passed.
        failed: Number of checks that failed.
        warnings: Number of checks that generated warnings.
        coverage_pct: Coverage percentage of global CB assets.
        all_passed: True if all checks passed.
    """

    timestamp: datetime
    checks: list[CheckResult] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    coverage_pct: float = 0.0
    all_passed: bool = False


class LiquidityValidator:
    """Validate liquidity calculations using double-entry checks.

    Provides validation for:
    - Net Liquidity formula: WALCL - TGA - RRP = Net Liquidity
    - Global Liquidity sum: Fed + ECB + BoJ + PBoC = total
    - Coverage requirement: Tier 1 >= 85% of global CB assets
    - Data freshness: Data not older than expected update frequency

    Example:
        validator = LiquidityValidator()

        # Validate Net Liquidity formula
        check = validator.validate_net_liquidity(
            walcl=7500.0,
            tga=800.0,
            rrp=500.0,
            reported_net_liq=6200.0,
        )
        print(f"Net Liquidity check: {'PASS' if check.passed else 'FAIL'}")

        # Validate Global Liquidity sum
        check = validator.validate_global_sum(
            components={"fed": 6200, "ecb": 8000, "boj": 4000, "pboc": 5000},
            reported_total=23200.0,
        )

        # Run all validations
        result = await validator.validate_all()
        print(f"All checks passed: {result.all_passed}")
    """

    # Estimated global central bank assets (~$35T)
    # Used for coverage percentage calculation
    GLOBAL_CB_ESTIMATE = 35_000  # billions USD

    # Maximum age for data freshness checks
    # Based on expected update frequencies from data sources
    MAX_AGE: dict[str, timedelta] = {
        "WALCL": timedelta(days=7),  # Weekly Fed balance sheet
        "TGA": timedelta(days=2),  # Daily with weekend buffer
        "RRP": timedelta(days=2),  # Daily with weekend buffer
        "ECB": timedelta(days=7),  # Weekly ECB data
        "BOJ": timedelta(days=14),  # Bi-weekly BoJ data
        "PBOC": timedelta(days=35),  # Monthly PBoC data
    }

    # Default tolerance for numeric comparisons (1% = 0.01)
    DEFAULT_TOLERANCE = 0.01

    def __init__(self) -> None:
        """Initialize the Liquidity Validator."""
        self._latest_result: ValidationResult | None = None

    @property
    def latest_result(self) -> ValidationResult | None:
        """Get the most recent validation result."""
        return self._latest_result

    async def validate_all(
        self,
        net_liq_data: dict[str, float] | None = None,
        global_liq_data: dict[str, float] | None = None,
        series_timestamps: dict[str, datetime] | None = None,
        tier1_total: float | None = None,
    ) -> ValidationResult:
        """Run all validation checks.

        Args:
            net_liq_data: Dict with keys 'walcl', 'tga', 'rrp', 'net_liquidity'
                for Net Liquidity validation. If None, skips this check.
            global_liq_data: Dict with component values and 'total' for
                Global Liquidity validation. If None, skips this check.
            series_timestamps: Dict mapping series names to their last update
                timestamps for freshness validation. If None, skips this check.
            tier1_total: Total Tier 1 CB assets in billions USD for coverage
                validation. If None, attempts to derive from global_liq_data.

        Returns:
            ValidationResult with all check results aggregated.
        """
        timestamp = datetime.now(UTC)
        checks: list[CheckResult] = []

        # 1. Net Liquidity Formula Validation
        if net_liq_data is not None:
            check = self.validate_net_liquidity(
                walcl=net_liq_data.get("walcl", 0.0),
                tga=net_liq_data.get("tga", 0.0),
                rrp=net_liq_data.get("rrp", 0.0),
                reported_net_liq=net_liq_data.get("net_liquidity", 0.0),
            )
            checks.append(check)

        # 2. Global Liquidity Sum Validation
        if global_liq_data is not None:
            total = global_liq_data.pop("total", None)
            if total is not None:
                check = self.validate_global_sum(
                    components=global_liq_data,
                    reported_total=total,
                )
                checks.append(check)
            # Restore total for tier1 calculation
            if total is not None:
                global_liq_data["total"] = total

        # 3. Coverage Validation
        if tier1_total is not None:
            check = self.validate_coverage(tier1_total=tier1_total)
            checks.append(check)
        elif global_liq_data is not None:
            # Calculate tier1 from global data (Fed + ECB + BoJ + PBoC)
            tier1_keys = [
                "fed",
                "fed_usd",
                "ecb",
                "ecb_usd",
                "boj",
                "boj_usd",
                "pboc",
                "pboc_usd",
            ]
            tier1_sum = sum(global_liq_data.get(k, 0.0) for k in tier1_keys if k in global_liq_data)
            if tier1_sum > 0:
                check = self.validate_coverage(tier1_total=tier1_sum)
                checks.append(check)

        # 4. Data Freshness Validation
        if series_timestamps is not None:
            freshness_checks = self.validate_freshness(series_timestamps)
            checks.extend(freshness_checks)

        # Aggregate results
        passed_count = sum(1 for c in checks if c.passed)
        failed_count = sum(1 for c in checks if not c.passed)
        warnings_count = 0  # Could be extended for soft failures

        # Calculate coverage percentage
        coverage_pct = 0.0
        coverage_check = next((c for c in checks if c.name == "coverage_verification"), None)
        if coverage_check and coverage_check.actual is not None:
            coverage_pct = coverage_check.actual

        result = ValidationResult(
            timestamp=timestamp,
            checks=checks,
            passed=passed_count,
            failed=failed_count,
            warnings=warnings_count,
            coverage_pct=coverage_pct,
            all_passed=(failed_count == 0 and len(checks) > 0),
        )

        self._latest_result = result

        logger.info(
            "Validation complete: %d passed, %d failed, coverage=%.1f%%",
            passed_count,
            failed_count,
            coverage_pct,
        )

        return result

    def validate_net_liquidity(
        self,
        walcl: float,
        tga: float,
        rrp: float,
        reported_net_liq: float,
        tolerance: float = 0.01,
    ) -> CheckResult:
        """Validate Net Liquidity formula: WALCL - TGA - RRP = Net Liquidity.

        This is the core Hayes formula check. The calculated Net Liquidity
        should match the reported value within the specified tolerance.

        Args:
            walcl: Fed Total Assets in billions USD.
            tga: Treasury General Account in billions USD.
            rrp: Reverse Repo in billions USD.
            reported_net_liq: Reported Net Liquidity in billions USD.
            tolerance: Maximum allowed relative difference (default 1%).

        Returns:
            CheckResult indicating whether the formula validates correctly.
        """
        # Calculate expected Net Liquidity
        calculated = walcl - tga - rrp

        # Calculate relative difference
        if abs(reported_net_liq) > 0.001:  # Avoid division by zero
            rel_diff = abs(calculated - reported_net_liq) / abs(reported_net_liq)
        else:
            rel_diff = abs(calculated - reported_net_liq)

        passed = rel_diff <= tolerance

        if passed:
            message = (
                f"Net Liquidity formula validates: "
                f"calculated={calculated:.2f}B, reported={reported_net_liq:.2f}B, "
                f"difference={rel_diff * 100:.3f}%"
            )
        else:
            message = (
                f"Net Liquidity MISMATCH: "
                f"calculated={calculated:.2f}B ({walcl:.2f} - {tga:.2f} - {rrp:.2f}), "
                f"reported={reported_net_liq:.2f}B, "
                f"difference={rel_diff * 100:.3f}% > tolerance {tolerance * 100:.1f}%"
            )

        logger.debug(
            "Net Liquidity validation: %s (calc=%.2f, reported=%.2f, diff=%.3f%%)",
            "PASS" if passed else "FAIL",
            calculated,
            reported_net_liq,
            rel_diff * 100,
        )

        return CheckResult(
            name="net_liquidity_formula",
            passed=passed,
            expected=reported_net_liq,
            actual=calculated,
            tolerance=tolerance,
            message=message,
        )

    def validate_global_sum(
        self,
        components: dict[str, float],
        reported_total: float,
        tolerance: float = 0.01,
    ) -> CheckResult:
        """Validate Global Liquidity sum: Fed + ECB + BoJ + PBoC = total.

        Verifies that the sum of individual central bank components
        matches the reported total Global Liquidity.

        Args:
            components: Dictionary of CB components in billions USD.
                Keys can be "fed", "ecb", "boj", "pboc" or with "_usd" suffix.
            reported_total: Reported total Global Liquidity in billions USD.
            tolerance: Maximum allowed relative difference (default 1%).

        Returns:
            CheckResult indicating whether the sum validates correctly.
        """
        # Calculate sum of components
        calculated = sum(components.values())

        # Calculate relative difference
        if abs(reported_total) > 0.001:  # Avoid division by zero
            rel_diff = abs(calculated - reported_total) / abs(reported_total)
        else:
            rel_diff = abs(calculated - reported_total)

        passed = rel_diff <= tolerance

        # Format component breakdown
        component_str = " + ".join(f"{k}={v:.1f}B" for k, v in sorted(components.items()))

        if passed:
            message = (
                f"Global Liquidity sum validates: "
                f"{component_str} = {calculated:.2f}B, "
                f"reported={reported_total:.2f}B, "
                f"difference={rel_diff * 100:.3f}%"
            )
        else:
            message = (
                f"Global Liquidity sum MISMATCH: "
                f"{component_str} = {calculated:.2f}B, "
                f"reported={reported_total:.2f}B, "
                f"difference={rel_diff * 100:.3f}% > tolerance {tolerance * 100:.1f}%"
            )

        logger.debug(
            "Global sum validation: %s (calc=%.2f, reported=%.2f, diff=%.3f%%)",
            "PASS" if passed else "FAIL",
            calculated,
            reported_total,
            rel_diff * 100,
        )

        return CheckResult(
            name="global_liquidity_sum",
            passed=passed,
            expected=reported_total,
            actual=calculated,
            tolerance=tolerance,
            message=message,
        )

    def validate_coverage(
        self,
        tier1_total: float,
        min_coverage: float = 85.0,
    ) -> CheckResult:
        """Validate coverage requirement: Tier 1 covers >85% of global CB assets.

        Verifies that the Tier 1 central banks (Fed, ECB, BoJ, PBoC) cover
        at least the minimum required percentage of estimated global CB assets.

        Args:
            tier1_total: Total Tier 1 CB assets in billions USD.
            min_coverage: Minimum required coverage percentage (default 85%).

        Returns:
            CheckResult indicating whether coverage requirement is met.
        """
        # Calculate coverage percentage
        if self.GLOBAL_CB_ESTIMATE > 0:
            coverage_pct = (tier1_total / self.GLOBAL_CB_ESTIMATE) * 100
        else:
            coverage_pct = 0.0

        passed = coverage_pct >= min_coverage

        if passed:
            message = (
                f"Coverage requirement MET: "
                f"{coverage_pct:.1f}% >= {min_coverage:.1f}% "
                f"(${tier1_total:.1f}B / ${self.GLOBAL_CB_ESTIMATE}B estimated)"
            )
        else:
            message = (
                f"Coverage requirement NOT MET: "
                f"{coverage_pct:.1f}% < {min_coverage:.1f}% "
                f"(${tier1_total:.1f}B / ${self.GLOBAL_CB_ESTIMATE}B estimated)"
            )

        logger.debug(
            "Coverage validation: %s (%.1f%% >= %.1f%%)",
            "PASS" if passed else "FAIL",
            coverage_pct,
            min_coverage,
        )

        return CheckResult(
            name="coverage_verification",
            passed=passed,
            expected=min_coverage,
            actual=coverage_pct,
            tolerance=None,
            message=message,
        )

    def validate_freshness(
        self,
        series_timestamps: dict[str, datetime],
    ) -> list[CheckResult]:
        """Validate data freshness for all provided series.

        Checks that each data series is not older than its expected
        update frequency. This helps detect stale data issues.

        Args:
            series_timestamps: Dictionary mapping series names to their
                last update timestamps. Series names should match keys
                in MAX_AGE (e.g., "WALCL", "TGA", "RRP", "ECB").

        Returns:
            List of CheckResults, one for each series checked.
        """
        now = datetime.now(UTC)
        checks: list[CheckResult] = []

        for series_name, last_update in series_timestamps.items():
            # Get max age for this series, default to 7 days if unknown
            max_age = self.MAX_AGE.get(series_name.upper(), timedelta(days=7))

            # Ensure timestamp is timezone-aware
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=UTC)

            # Calculate age
            age = now - last_update
            passed = age <= max_age

            if passed:
                message = (
                    f"Data freshness OK: {series_name} "
                    f"updated {age.days}d {age.seconds // 3600}h ago "
                    f"(max allowed: {max_age.days}d)"
                )
            else:
                message = (
                    f"Data STALE: {series_name} "
                    f"updated {age.days}d {age.seconds // 3600}h ago "
                    f"(max allowed: {max_age.days}d)"
                )

            logger.debug(
                "Freshness check %s: %s (age=%s, max=%s)",
                series_name,
                "PASS" if passed else "FAIL",
                age,
                max_age,
            )

            checks.append(
                CheckResult(
                    name=f"freshness_{series_name.lower()}",
                    passed=passed,
                    expected=max_age.total_seconds(),  # Max age in seconds
                    actual=age.total_seconds(),  # Actual age in seconds
                    tolerance=None,
                    message=message,
                )
            )

        return checks

    def __repr__(self) -> str:
        """Return string representation of the validator."""
        return (
            f"LiquidityValidator("
            f"global_cb_estimate=${self.GLOBAL_CB_ESTIMATE}B, "
            f"checks={list(self.MAX_AGE.keys())})"
        )
