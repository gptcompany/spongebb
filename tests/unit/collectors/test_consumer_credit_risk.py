"""Unit tests for consumer credit risk collector calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from liquidity.collectors.consumer_credit_risk import ConsumerCreditRiskCollector


class TestTrackingSeries:
    """Tests for derived credit tracking series."""

    def test_build_tracking_series(self) -> None:
        """Build tracking series with unit normalization and derived fields."""
        df = pd.DataFrame(
            [
                {"timestamp": "2025-01-01", "series_id": "HCCSDODNS", "value": 5_000_000.0},
                {"timestamp": "2025-01-01", "series_id": "SLOASM", "value": 1_800_000.0},
                {"timestamp": "2025-01-01", "series_id": "DRALACBS", "value": 2.0},
                {"timestamp": "2025-01-01", "series_id": "CORALACBS", "value": 0.5},
                {"timestamp": "2025-01-01", "series_id": "DRSFRMACBS", "value": 1.8},
                {"timestamp": "2025-01-01", "series_id": "CORSFRMACBS", "value": 0.3},
                {"timestamp": "2025-01-01", "series_id": "QBPBSTASTLNLESSRES", "value": 300_000.0},
                {"timestamp": "2025-01-01", "series_id": "WALCL", "value": 7_000_000.0},
                {"timestamp": "2025-01-01", "series_id": "WDTGAL", "value": 700.0},
                {"timestamp": "2025-01-01", "series_id": "WLRRAL", "value": 500.0},
                {"timestamp": "2025-02-01", "series_id": "HCCSDODNS", "value": 5_020_000.0},
                {"timestamp": "2025-02-01", "series_id": "SLOASM", "value": 1_810_000.0},
                {"timestamp": "2025-02-01", "series_id": "WALCL", "value": 7_020_000.0},
                {"timestamp": "2025-02-01", "series_id": "WDTGAL", "value": 710.0},
                {"timestamp": "2025-02-01", "series_id": "WLRRAL", "value": 490.0},
            ]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["source"] = "fred"
        df["unit"] = "mixed"

        tracking = ConsumerCreditRiskCollector.build_tracking_series(df)
        assert not tracking.empty

        first = tracking.iloc[0]
        assert abs(float(first["consumer_credit_total_b"]) - 5000.0) < 1e-6
        assert abs(float(first["student_loans_b"]) - 1800.0) < 1e-6
        assert abs(float(first["consumer_credit_ex_students_b"]) - 3200.0) < 1e-6
        assert abs(float(first["debt_in_default_est_b"]) - 64.0) < 1e-6
        assert abs(float(first["loan_loss_reserves_b"]) - 300.0) < 1e-6
        assert abs(float(first["usd_liquidity_b"]) - 5800.0) < 1e-6

    def test_get_latest_tracking_metrics(self) -> None:
        """Latest metrics should expose expected keys."""
        tracking = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2025-01-01"),
                    "consumer_credit_total_b": 5000.0,
                    "student_loans_b": 1800.0,
                    "consumer_credit_ex_students_b": 3200.0,
                    "debt_default_rate_pct": 2.0,
                    "debt_in_default_est_b": 64.0,
                    "mortgage_chargeoff_rate_pct": 0.3,
                    "loan_loss_reserves_b": 300.0,
                    "usd_liquidity_index": 100.0,
                }
            ]
        )

        metrics = ConsumerCreditRiskCollector.get_latest_tracking_metrics(tracking)
        assert metrics["consumer_credit_ex_students_b"] == 3200.0
        assert metrics["usd_liquidity_index"] == 100.0


class TestRelativePerformance:
    """Tests for XLP/XLY and AXP/IGV calculations."""

    def test_calculate_xlp_xly_ratio(self) -> None:
        """XLP/XLY ratio should be computed from market price inputs."""
        dates = pd.date_range("2025-01-01", periods=3, freq="D")
        market_df = pd.DataFrame(
            {
                "timestamp": list(dates) * 2,
                "symbol": ["XLP"] * 3 + ["XLY"] * 3,
                "value": [80.0, 81.0, 82.0, 200.0, 202.0, 204.0],
                "source": "yahoo",
                "unit": "index",
            }
        )

        ratio = ConsumerCreditRiskCollector.calculate_xlp_xly_ratio(market_df)
        assert not ratio.empty
        assert "xlp_xly_ratio" in ratio.columns
        assert abs(float(ratio.iloc[0]["xlp_xly_ratio"]) - 0.4) < 1e-6

    def test_calculate_axp_igv_relative(self) -> None:
        """AXP/IGV relative spread should be rebased and in percent points."""
        dates = pd.date_range("2025-01-01", periods=3, freq="D")
        market_df = pd.DataFrame(
            {
                "timestamp": list(dates) * 2,
                "symbol": ["AXP"] * 3 + ["IGV"] * 3,
                "value": [100.0, 110.0, 121.0, 100.0, 105.0, 110.25],
                "source": "yahoo",
                "unit": "index",
            }
        )

        spread = ConsumerCreditRiskCollector.calculate_axp_igv_relative(market_df)
        assert not spread.empty
        assert "relative_spread_pct" in spread.columns
        # AXP grew faster than IGV in this synthetic sample.
        assert float(spread.iloc[-1]["relative_spread_pct"]) > 0


class TestSensitivityRanking:
    """Tests for ranking stocks by credit-stress sensitivity."""

    def test_rank_credit_sensitive_stocks(self) -> None:
        """Stocks with stronger negative relationship to stress should rank higher."""
        n = 30
        dates = pd.date_range("2023-01-31", periods=n, freq="ME")
        driver = np.sin(np.linspace(0, 3 * np.pi, n))

        tracking_df = pd.DataFrame(
            {
                "timestamp": dates,
                "debt_default_rate_pct": 2.0 + np.cumsum(driver * 0.06),
                "debt_chargeoff_rate_pct": 1.0 + np.cumsum(driver * 0.05),
                "mortgage_chargeoff_rate_pct": 0.5 + np.cumsum(driver * 0.04),
                "loan_loss_reserves_b": 250.0 + np.cumsum(1.5 + driver * 0.4),
            }
        )

        tsla_ret = -0.05 * driver
        amzn_ret = -0.03 * driver
        wmt_ret = 0.01 * driver

        tsla_price = 200 * np.cumprod(1 + tsla_ret / 10)
        amzn_price = 150 * np.cumprod(1 + amzn_ret / 10)
        wmt_price = 140 * np.cumprod(1 + wmt_ret / 10)

        market_df = pd.concat(
            [
                pd.DataFrame({"timestamp": dates, "symbol": "TSLA", "value": tsla_price}),
                pd.DataFrame({"timestamp": dates, "symbol": "AMZN", "value": amzn_price}),
                pd.DataFrame({"timestamp": dates, "symbol": "WMT", "value": wmt_price}),
            ],
            ignore_index=True,
        )
        market_df["source"] = "yahoo"
        market_df["unit"] = "index"

        ranked = ConsumerCreditRiskCollector.rank_credit_sensitive_stocks(
            market_df=market_df,
            tracking_df=tracking_df,
            symbols=["TSLA", "AMZN", "WMT"],
            min_observations=12,
        )

        assert not ranked.empty
        assert ranked.iloc[0]["symbol"] in {"TSLA", "AMZN"}
        tsla_row = ranked[ranked["symbol"] == "TSLA"].iloc[0]
        assert float(tsla_row["sensitivity_score"]) > 0
