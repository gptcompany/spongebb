"""QA-05/06/07: Regression tests for formula validation.

Validates Hayes formula against known historical values and
cross-validates against Apps Script v3.4.1 output.
"""

import logging
from dataclasses import dataclass

from .config import DEFAULT_CONFIG, RegressionConfig

logger = logging.getLogger(__name__)


@dataclass
class RegressionTestResult:
    """Result of a single regression test.

    Attributes:
        test_name: Name of the regression test.
        expected: Expected value (from historical data or Apps Script).
        actual: Actual computed value.
        passed: Whether the test passed within tolerance.
        tolerance_pct: Tolerance percentage used.
        difference_pct: Actual percentage difference.
        message: Human-readable description.
    """

    test_name: str
    expected: float
    actual: float
    passed: bool
    tolerance_pct: float
    difference_pct: float
    message: str


@dataclass
class RegressionSuiteResult:
    """Result of running a full regression test suite.

    Attributes:
        total_tests: Total number of tests run.
        passed_tests: Number of tests that passed.
        failed_tests: Number of tests that failed.
        pass_rate: Percentage of tests that passed.
        results: List of individual test results.
    """

    total_tests: int
    passed_tests: int
    failed_tests: int
    pass_rate: float
    results: list[RegressionTestResult]


@dataclass
class RegressionInputs:
    """Input data for regression test suite.

    Attributes:
        walcl: Fed Total Assets (for Hayes formula test).
        tga: Treasury General Account.
        rrp: Reverse Repo.
        net_liquidity: Calculated/reported Net Liquidity.
        fed_usd: Fed balance sheet in USD.
        ecb_usd: ECB balance sheet in USD.
        boj_usd: BoJ balance sheet in USD.
        pboc_usd: PBoC balance sheet in USD.
        global_liquidity: Calculated/reported Global Liquidity.
        stealth_qe: Calculated Stealth QE score.
        historical_date: Date for historical comparison.
    """

    walcl: float | None = None
    tga: float | None = None
    rrp: float | None = None
    net_liquidity: float | None = None
    fed_usd: float | None = None
    ecb_usd: float | None = None
    boj_usd: float | None = None
    pboc_usd: float | None = None
    global_liquidity: float | None = None
    stealth_qe: float | None = None
    historical_date: str | None = None


class RegressionTester:
    """Run regression tests against known historical values.

    QA-05: Unit tests validate Hayes formula against known historical values.
    QA-06: System cross-validates results vs Apps Script v3.4.1 output.
    QA-07: Regression tests run on each data refresh.

    Example:
        tester = RegressionTester()

        # Test Hayes formula
        result = tester.test_hayes_formula(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            expected_net_liquidity=6200e9,
        )
        print(f"Hayes formula: {'PASS' if result.passed else 'FAIL'}")

        # Test against historical
        results = tester.test_against_historical(
            date="2024-01-15",
            net_liquidity=5.82e12,
            global_liquidity=28.5e12,
            stealth_qe=15.0,
        )

        # Run full suite
        suite_result = tester.run_all_regression_tests(
            RegressionInputs(walcl=7500e9, tga=800e9, rrp=500e9, net_liquidity=6200e9)
        )
    """

    def __init__(self, config: RegressionConfig | None = None) -> None:
        """Initialize the regression tester.

        Args:
            config: Regression test configuration. Uses default if not provided.
        """
        self.config = config or DEFAULT_CONFIG.regression

    def test_hayes_formula(
        self,
        walcl: float,
        tga: float,
        rrp: float,
        expected_net_liquidity: float,
        tolerance_pct: float | None = None,
    ) -> RegressionTestResult:
        """Validate Hayes formula calculation: WALCL - TGA - RRP = Net Liquidity.

        Args:
            walcl: Fed Total Assets.
            tga: Treasury General Account.
            rrp: Reverse Repo.
            expected_net_liquidity: Expected Net Liquidity result.
            tolerance_pct: Tolerance for comparison. Uses config default if None.

        Returns:
            RegressionTestResult with test outcome.
        """
        tolerance = tolerance_pct or self.config.tolerance_pct

        # Calculate Net Liquidity
        actual = walcl - tga - rrp

        # Calculate difference
        if expected_net_liquidity == 0:
            diff_pct = 100.0 if actual != 0 else 0.0
        else:
            diff_pct = abs(actual - expected_net_liquidity) / abs(expected_net_liquidity) * 100

        passed = diff_pct <= tolerance

        if passed:
            message = (
                f"Hayes formula PASS: calculated={actual:.2e}, "
                f"expected={expected_net_liquidity:.2e} (diff={diff_pct:.3f}%)"
            )
        else:
            message = (
                f"Hayes formula FAIL: calculated={actual:.2e}, "
                f"expected={expected_net_liquidity:.2e} (diff={diff_pct:.3f}% > {tolerance}%)"
            )

        logger.debug(
            "Hayes formula test: %s (diff=%.3f%%, tolerance=%.1f%%)",
            "PASS" if passed else "FAIL",
            diff_pct,
            tolerance,
        )

        return RegressionTestResult(
            test_name="hayes_formula",
            expected=expected_net_liquidity,
            actual=actual,
            passed=passed,
            tolerance_pct=tolerance,
            difference_pct=diff_pct,
            message=message,
        )

    def test_global_liquidity_sum(
        self,
        fed_usd: float,
        ecb_usd: float,
        boj_usd: float,
        pboc_usd: float,
        expected_global_liquidity: float,
        tolerance_pct: float | None = None,
    ) -> RegressionTestResult:
        """Validate Global Liquidity sum: Fed + ECB + BoJ + PBoC = Total.

        Args:
            fed_usd: Fed balance sheet in USD.
            ecb_usd: ECB balance sheet in USD.
            boj_usd: BoJ balance sheet in USD.
            pboc_usd: PBoC balance sheet in USD.
            expected_global_liquidity: Expected total.
            tolerance_pct: Tolerance for comparison.

        Returns:
            RegressionTestResult with test outcome.
        """
        tolerance = tolerance_pct or self.config.tolerance_pct

        actual = fed_usd + ecb_usd + boj_usd + pboc_usd

        if expected_global_liquidity == 0:
            diff_pct = 100.0 if actual != 0 else 0.0
        else:
            diff_pct = abs(actual - expected_global_liquidity) / abs(expected_global_liquidity) * 100

        passed = diff_pct <= tolerance

        message = (
            f"Global Liquidity sum {'PASS' if passed else 'FAIL'}: "
            f"calculated={actual:.2e}, expected={expected_global_liquidity:.2e} "
            f"(diff={diff_pct:.3f}%)"
        )

        return RegressionTestResult(
            test_name="global_liquidity_sum",
            expected=expected_global_liquidity,
            actual=actual,
            passed=passed,
            tolerance_pct=tolerance,
            difference_pct=diff_pct,
            message=message,
        )

    def test_against_historical(
        self,
        date_str: str,
        net_liquidity: float,
        global_liquidity: float,
        stealth_qe: float,
        tolerance_pct: float | None = None,
    ) -> list[RegressionTestResult]:
        """Test current calculations against known historical values.

        Args:
            date_str: Date string in format YYYY-MM-DD.
            net_liquidity: Calculated Net Liquidity.
            global_liquidity: Calculated Global Liquidity.
            stealth_qe: Calculated Stealth QE score.
            tolerance_pct: Tolerance for comparison.

        Returns:
            List of RegressionTestResult, one for each metric.
        """
        tolerance = tolerance_pct or self.config.tolerance_pct

        if date_str not in self.config.historical_values:
            logger.warning("No historical values for date: %s", date_str)
            return []

        expected_values = self.config.historical_values[date_str]
        metrics = [
            ("net_liquidity", net_liquidity, expected_values[0]),
            ("global_liquidity", global_liquidity, expected_values[1]),
            ("stealth_qe", stealth_qe, expected_values[2]),
        ]

        results = []
        for name, actual, expected in metrics:
            if expected == 0:
                diff_pct = 100.0 if actual != 0 else 0.0
            else:
                diff_pct = abs(actual - expected) / abs(expected) * 100

            passed = diff_pct <= tolerance

            results.append(
                RegressionTestResult(
                    test_name=f"historical_{name}_{date_str}",
                    expected=expected,
                    actual=actual,
                    passed=passed,
                    tolerance_pct=tolerance,
                    difference_pct=diff_pct,
                    message=f"{name} ({date_str}): {'PASS' if passed else 'FAIL'} (diff={diff_pct:.3f}%)",
                )
            )

        return results

    def test_apps_script_cross_validation(
        self,
        calculated_values: dict[str, float],
        apps_script_values: dict[str, float],
        tolerance_pct: float | None = None,
    ) -> list[RegressionTestResult]:
        """Cross-validate against Apps Script v3.4.1 output.

        QA-06: System cross-validates results vs Apps Script v3.4.1 output.

        Args:
            calculated_values: Values from Python implementation.
            apps_script_values: Values from Apps Script v3.4.1.
            tolerance_pct: Tolerance for comparison.

        Returns:
            List of RegressionTestResult for each metric.
        """
        tolerance = tolerance_pct or self.config.tolerance_pct

        results = []

        # Find common metrics
        common_metrics = set(calculated_values.keys()) & set(apps_script_values.keys())

        for metric in sorted(common_metrics):
            actual = calculated_values[metric]
            expected = apps_script_values[metric]

            if expected == 0:
                diff_pct = 100.0 if actual != 0 else 0.0
            else:
                diff_pct = abs(actual - expected) / abs(expected) * 100

            passed = diff_pct <= tolerance

            results.append(
                RegressionTestResult(
                    test_name=f"apps_script_{metric}",
                    expected=expected,
                    actual=actual,
                    passed=passed,
                    tolerance_pct=tolerance,
                    difference_pct=diff_pct,
                    message=f"Apps Script {metric}: {'PASS' if passed else 'FAIL'} (diff={diff_pct:.3f}%)",
                )
            )

        return results

    def run_all_regression_tests(
        self,
        inputs: RegressionInputs,
    ) -> RegressionSuiteResult:
        """Run full regression test suite.

        Args:
            inputs: RegressionInputs with all test data.

        Returns:
            RegressionSuiteResult with all test outcomes.
        """
        results: list[RegressionTestResult] = []

        # Test Hayes formula if data provided
        if all(v is not None for v in [inputs.walcl, inputs.tga, inputs.rrp, inputs.net_liquidity]):
            result = self.test_hayes_formula(
                walcl=inputs.walcl,  # type: ignore
                tga=inputs.tga,  # type: ignore
                rrp=inputs.rrp,  # type: ignore
                expected_net_liquidity=inputs.net_liquidity,  # type: ignore
            )
            results.append(result)

        # Test Global Liquidity sum if data provided
        if all(v is not None for v in [inputs.fed_usd, inputs.ecb_usd, inputs.boj_usd, inputs.pboc_usd, inputs.global_liquidity]):
            result = self.test_global_liquidity_sum(
                fed_usd=inputs.fed_usd,  # type: ignore
                ecb_usd=inputs.ecb_usd,  # type: ignore
                boj_usd=inputs.boj_usd,  # type: ignore
                pboc_usd=inputs.pboc_usd,  # type: ignore
                expected_global_liquidity=inputs.global_liquidity,  # type: ignore
            )
            results.append(result)

        # Test against historical values if date provided
        if inputs.historical_date and all(
            v is not None for v in [inputs.net_liquidity, inputs.global_liquidity, inputs.stealth_qe]
        ):
            historical_results = self.test_against_historical(
                date_str=inputs.historical_date,
                net_liquidity=inputs.net_liquidity,  # type: ignore
                global_liquidity=inputs.global_liquidity,  # type: ignore
                stealth_qe=inputs.stealth_qe,  # type: ignore
            )
            results.extend(historical_results)

        # Calculate summary
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 100.0

        logger.info(
            "Regression suite: %d/%d passed (%.1f%%)",
            passed,
            total,
            pass_rate,
        )

        return RegressionSuiteResult(
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            pass_rate=pass_rate,
            results=results,
        )

    def calculate_regression_score(self, suite_result: RegressionSuiteResult) -> float:
        """Calculate regression score for quality assessment.

        Args:
            suite_result: Result from running regression suite.

        Returns:
            Score between 0 and 100 based on pass rate.
        """
        return suite_result.pass_rate
