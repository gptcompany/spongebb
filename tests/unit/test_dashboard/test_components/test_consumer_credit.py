"""Tests for consumer credit dashboard component."""

from __future__ import annotations

from datetime import datetime

import dash_bootstrap_components as dbc
import pandas as pd


class TestConsumerCreditPanel:
    """Panel construction tests."""

    def test_create_panel(self) -> None:
        """Panel should be created as a Bootstrap card."""
        from liquidity.dashboard.components.consumer_credit import (
            create_consumer_credit_panel,
        )

        panel = create_consumer_credit_panel()
        assert panel is not None
        assert isinstance(panel, dbc.Card)


class TestConsumerCreditCharts:
    """Chart generation tests."""

    def test_create_xlp_xly_ratio_chart_empty(self) -> None:
        """Empty input should still produce a valid figure."""
        from liquidity.dashboard.components.consumer_credit import (
            create_xlp_xly_ratio_chart,
        )

        fig = create_xlp_xly_ratio_chart(None)
        assert fig is not None
        assert hasattr(fig, "data")

    def test_create_xlp_xly_ratio_chart_with_data(self) -> None:
        """Valid ratio data should create at least one trace."""
        from liquidity.dashboard.components.consumer_credit import (
            create_xlp_xly_ratio_chart,
        )

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(end=datetime.now(), periods=30, freq="D"),
                "xlp_xly_ratio": [0.42 + i * 0.001 for i in range(30)],
            }
        )
        fig = create_xlp_xly_ratio_chart(df)
        assert len(fig.data) >= 1

    def test_create_axp_igv_spread_chart_with_data(self) -> None:
        """AXP/IGV data should produce traces."""
        from liquidity.dashboard.components.consumer_credit import (
            create_axp_igv_spread_chart,
        )

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(end=datetime.now(), periods=30, freq="D"),
                "axp_rebased": [100 + i * 0.4 for i in range(30)],
                "igv_rebased": [100 + i * 0.2 for i in range(30)],
                "relative_spread_pct": [i * 0.2 for i in range(30)],
            }
        )
        fig = create_axp_igv_spread_chart(df)
        assert len(fig.data) >= 2


class TestConsumerCreditWidgets:
    """Metrics and table tests."""

    def test_create_consumer_credit_metrics(self) -> None:
        """Metrics widget should render with values."""
        from liquidity.dashboard.components.consumer_credit import (
            create_consumer_credit_metrics,
        )

        metrics = create_consumer_credit_metrics(
            {
                "consumer_credit_total_b": 5070.0,
                "student_loans_b": 1835.0,
                "consumer_credit_ex_students_b": 3235.0,
                "debt_in_default_est_b": 65.0,
                "debt_default_rate_pct": 2.0,
                "mortgage_chargeoff_rate_pct": 0.35,
                "loan_loss_reserves_b": 280.0,
                "usd_liquidity_index": 104.2,
            }
        )
        assert metrics is not None

    def test_create_sensitive_stocks_table(self) -> None:
        """Sensitivity table should render top rows."""
        from liquidity.dashboard.components.consumer_credit import (
            create_sensitive_stocks_table,
        )

        df = pd.DataFrame(
            {
                "symbol": ["TSLA", "AMZN", "WMT"],
                "corr_to_stress": [-0.65, -0.40, 0.10],
                "beta_to_stress": [-1.10, -0.70, 0.20],
                "sensitivity_score": [0.65, 0.40, -0.10],
            }
        )

        table = create_sensitive_stocks_table(df, top_n=2)
        assert table is not None
