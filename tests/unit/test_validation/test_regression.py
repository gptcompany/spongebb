"""Unit tests for regression testing (QA-05/06/07)."""

import pytest

from liquidity.validation.config import RegressionConfig
from liquidity.validation.regression import (
    RegressionInputs,
    RegressionSuiteResult,
    RegressionTester,
)


class TestRegressionTester:
    """Tests for RegressionTester class."""

    def test_hayes_formula_pass(self) -> None:
        """Test Hayes formula validation with correct values."""
        tester = RegressionTester()

        # WALCL - TGA - RRP = Net Liquidity
        # 7500 - 800 - 500 = 6200
        result = tester.test_hayes_formula(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            expected_net_liquidity=6200e9,
        )

        assert result.passed is True
        assert result.test_name == "hayes_formula"
        assert result.difference_pct == pytest.approx(0.0)

    def test_hayes_formula_fail(self) -> None:
        """Test Hayes formula validation with incorrect values."""
        tester = RegressionTester()

        # Calculated: 7500 - 800 - 500 = 6200, but expected 7000 (12.9% diff)
        result = tester.test_hayes_formula(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            expected_net_liquidity=7000e9,
        )

        assert result.passed is False
        assert result.difference_pct > 5.0

    def test_hayes_formula_custom_tolerance(self) -> None:
        """Test Hayes formula with custom tolerance."""
        tester = RegressionTester()

        # 5% diff but 10% tolerance should pass
        result = tester.test_hayes_formula(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            expected_net_liquidity=6510e9,  # ~5% higher than calculated 6200
            tolerance_pct=10.0,
        )

        assert result.passed is True

    def test_global_liquidity_sum_pass(self) -> None:
        """Test Global Liquidity sum validation."""
        tester = RegressionTester()

        result = tester.test_global_liquidity_sum(
            fed_usd=7000e9,
            ecb_usd=8000e9,
            boj_usd=5000e9,
            pboc_usd=6000e9,
            expected_global_liquidity=26000e9,
        )

        assert result.passed is True
        assert result.test_name == "global_liquidity_sum"
        assert result.difference_pct == pytest.approx(0.0)

    def test_global_liquidity_sum_fail(self) -> None:
        """Test Global Liquidity sum validation with mismatch."""
        tester = RegressionTester()

        # Sum = 26000, expected = 30000 (15.4% diff)
        result = tester.test_global_liquidity_sum(
            fed_usd=7000e9,
            ecb_usd=8000e9,
            boj_usd=5000e9,
            pboc_usd=6000e9,
            expected_global_liquidity=30000e9,
        )

        assert result.passed is False

    def test_against_historical_known_date(self) -> None:
        """Test validation against known historical values."""
        tester = RegressionTester()

        # Using values from config defaults
        results = tester.test_against_historical(
            date_str="2024-01-15",
            net_liquidity=5.82e12,
            global_liquidity=28.5e12,
            stealth_qe=15.0,
        )

        assert len(results) == 3
        for result in results:
            assert result.passed is True
            assert "historical" in result.test_name

    def test_against_historical_slight_diff(self) -> None:
        """Test historical validation with slight differences."""
        tester = RegressionTester()

        # Within 5% tolerance
        results = tester.test_against_historical(
            date_str="2024-01-15",
            net_liquidity=5.82e12 * 1.03,  # 3% off
            global_liquidity=28.5e12 * 1.02,  # 2% off
            stealth_qe=15.0 * 1.04,  # 4% off
        )

        assert len(results) == 3
        for result in results:
            assert result.passed is True

    def test_against_historical_large_diff(self) -> None:
        """Test historical validation with large differences."""
        tester = RegressionTester()

        # More than 5% tolerance
        results = tester.test_against_historical(
            date_str="2024-01-15",
            net_liquidity=5.82e12 * 1.10,  # 10% off
            global_liquidity=28.5e12,
            stealth_qe=15.0,
        )

        # net_liquidity should fail
        net_liq_result = next(r for r in results if "net_liquidity" in r.test_name)
        assert net_liq_result.passed is False

    def test_against_historical_unknown_date(self) -> None:
        """Test historical validation with unknown date."""
        tester = RegressionTester()

        results = tester.test_against_historical(
            date_str="2000-01-01",  # Not in historical values
            net_liquidity=5.82e12,
            global_liquidity=28.5e12,
            stealth_qe=15.0,
        )

        assert results == []

    def test_apps_script_cross_validation(self) -> None:
        """Test Apps Script v3.4.1 cross-validation."""
        tester = RegressionTester()

        calculated = {
            "net_liquidity": 6200e9,
            "global_liquidity": 29000e9,
            "stealth_qe": 20.0,
        }
        apps_script = {
            "net_liquidity": 6200e9,
            "global_liquidity": 29000e9,
            "stealth_qe": 20.0,
        }

        results = tester.test_apps_script_cross_validation(calculated, apps_script)

        assert len(results) == 3
        for result in results:
            assert result.passed is True
            assert "apps_script" in result.test_name

    def test_apps_script_cross_validation_mismatch(self) -> None:
        """Test Apps Script cross-validation with mismatch."""
        tester = RegressionTester()

        calculated = {
            "net_liquidity": 6200e9,
        }
        apps_script = {
            "net_liquidity": 7000e9,  # Different
        }

        results = tester.test_apps_script_cross_validation(calculated, apps_script)

        assert len(results) == 1
        assert results[0].passed is False

    def test_run_all_regression_tests_hayes_only(self) -> None:
        """Test running full suite with Hayes formula only."""
        tester = RegressionTester()

        result = tester.run_all_regression_tests(RegressionInputs(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            net_liquidity=6200e9,
        ))

        assert result.total_tests == 1
        assert result.passed_tests == 1
        assert result.pass_rate == 100.0

    def test_run_all_regression_tests_full(self) -> None:
        """Test running full suite with all data."""
        tester = RegressionTester()

        result = tester.run_all_regression_tests(RegressionInputs(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            net_liquidity=6200e9,
            fed_usd=7000e9,
            ecb_usd=8000e9,
            boj_usd=5000e9,
            pboc_usd=6000e9,
            global_liquidity=26000e9,
        ))

        assert result.total_tests == 2  # Hayes + Global sum
        assert result.pass_rate >= 50.0  # At least one should pass

    def test_run_all_regression_tests_with_historical(self) -> None:
        """Test running full suite with historical comparison."""
        tester = RegressionTester()

        result = tester.run_all_regression_tests(RegressionInputs(
            walcl=5.82e12 + 800e9 + 500e9,  # ~7.12e12
            tga=800e9,
            rrp=500e9,
            net_liquidity=5.82e12,
            global_liquidity=28.5e12,
            stealth_qe=15.0,
            historical_date="2024-01-15",
        ))

        assert result.total_tests >= 4  # Hayes + 3 historical
        assert result.passed_tests >= 3  # Historical should pass

    def test_run_all_regression_tests_no_data(self) -> None:
        """Test running full suite with no data."""
        tester = RegressionTester()

        result = tester.run_all_regression_tests(RegressionInputs())

        assert result.total_tests == 0
        assert result.pass_rate == 100.0

    def test_calculate_regression_score(self) -> None:
        """Test regression score calculation."""
        tester = RegressionTester()

        suite_result = RegressionSuiteResult(
            total_tests=10,
            passed_tests=8,
            failed_tests=2,
            pass_rate=80.0,
            results=[],
        )

        score = tester.calculate_regression_score(suite_result)

        assert score == 80.0

    def test_custom_config(self) -> None:
        """Test using custom configuration."""
        config = RegressionConfig(
            tolerance_pct=10.0,  # 10% tolerance
        )
        tester = RegressionTester(config=config)

        # 8% diff should pass with 10% tolerance
        result = tester.test_hayes_formula(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            expected_net_liquidity=6696e9,  # 8% higher than 6200
        )

        assert result.passed is True

    def test_zero_expected_value(self) -> None:
        """Test handling of zero expected values."""
        tester = RegressionTester()

        result = tester.test_hayes_formula(
            walcl=0,
            tga=0,
            rrp=0,
            expected_net_liquidity=0,
        )

        assert result.passed is True
        assert result.difference_pct == 0.0

    def test_message_content(self) -> None:
        """Test that result messages contain useful information."""
        tester = RegressionTester()

        result = tester.test_hayes_formula(
            walcl=7500e9,
            tga=800e9,
            rrp=500e9,
            expected_net_liquidity=6200e9,
        )

        assert "Hayes" in result.message or "formula" in result.message
        assert "PASS" in result.message or "FAIL" in result.message
