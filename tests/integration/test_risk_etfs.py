"""Integration tests for Risk ETF collector.

Tests RiskETFCollector functionality:
- Current shares outstanding fetch
- Historical price fetch
- Batch download for prices
- Equity vs Bond ETF convenience methods
- Risk appetite ratio calculation

Run with: uv run pytest tests/integration/test_risk_etfs.py -v
"""

import asyncio

import pandas as pd
import pytest

from liquidity.collectors.risk_etfs import (
    RISK_ETF_TICKERS,
    RISK_ETF_TYPE,
    RiskETFCollector,
)


@pytest.fixture
def risk_etf_collector() -> RiskETFCollector:
    """Create a Risk ETF collector instance."""
    return RiskETFCollector()


class TestRiskETFSymbols:
    """Tests for Risk ETF symbols mapping."""

    def test_risk_etf_tickers_defined(self) -> None:
        """Test all 5 risk ETFs are mapped."""
        assert len(RISK_ETF_TICKERS) == 5
        assert "SPY" in RISK_ETF_TICKERS
        assert "TLT" in RISK_ETF_TICKERS
        assert "HYG" in RISK_ETF_TICKERS
        assert "IEF" in RISK_ETF_TICKERS
        assert "LQD" in RISK_ETF_TICKERS

    def test_risk_etf_ticker_values(self) -> None:
        """Test Risk ETF ticker values are correct."""
        assert RISK_ETF_TICKERS["SPY"] == "SPY"
        assert RISK_ETF_TICKERS["TLT"] == "TLT"
        assert RISK_ETF_TICKERS["HYG"] == "HYG"
        assert RISK_ETF_TICKERS["IEF"] == "IEF"
        assert RISK_ETF_TICKERS["LQD"] == "LQD"

    def test_risk_etf_type_mapping(self) -> None:
        """Test all ETFs have risk type mapping."""
        for ticker in RISK_ETF_TICKERS.values():
            assert ticker in RISK_ETF_TYPE, f"Missing risk_type for {ticker}"

    def test_risk_etf_type_values(self) -> None:
        """Test risk type values are correct."""
        assert RISK_ETF_TYPE["SPY"] == "equity"
        assert RISK_ETF_TYPE["TLT"] == "treasury_long"
        assert RISK_ETF_TYPE["HYG"] == "high_yield"
        assert RISK_ETF_TYPE["IEF"] == "treasury_mid"
        assert RISK_ETF_TYPE["LQD"] == "investment_grade"


class TestRiskETFCollector:
    """Tests for RiskETFCollector instantiation and basic methods."""

    def test_collector_instantiation(self) -> None:
        """Test RiskETFCollector can be instantiated."""
        collector = RiskETFCollector()
        assert collector.name == "risk_etfs"

    def test_collector_class_attributes(self) -> None:
        """Test class attributes are accessible."""
        assert RiskETFCollector.RISK_ETF_TICKERS == RISK_ETF_TICKERS
        assert RiskETFCollector.RISK_ETF_TYPE == RISK_ETF_TYPE


class TestRiskETFCollectorIntegration:
    """Integration tests with real Yahoo Finance data."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_current_shares(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test fetching current shares outstanding for all 5 ETFs."""
        df = await risk_etf_collector.collect_current_shares()

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        expected_cols = {
            "timestamp",
            "etf",
            "risk_type",
            "source",
            "shares_outstanding",
            "total_assets",
            "nav_price",
        }
        assert set(df.columns) == expected_cols

        # Verify all 5 ETFs present
        etfs = df["etf"].unique().tolist()
        print(f"\nRisk ETFs fetched: {etfs}")

        for ticker in RISK_ETF_TICKERS.values():
            assert ticker in etfs, f"Missing {ticker}"

        # Verify source is yfinance
        assert (df["source"] == "yfinance").all()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_current_shares_spy_valid(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test SPY shares outstanding is > 500M (huge ETF)."""
        df = await risk_etf_collector.collect_current_shares(etfs=["SPY"])

        spy_row = df[df["etf"] == "SPY"]
        assert not spy_row.empty, "SPY data should be present"

        shares = spy_row["shares_outstanding"].values[0]
        if shares is not None:
            # SPY typically has 900M+ shares outstanding
            assert shares > 500_000_000, f"SPY shares too low: {shares:,.0f}"
            print(f"\nSPY shares outstanding: {shares:,.0f}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_historical_prices(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test batch download for historical prices."""
        df = await risk_etf_collector.collect_historical_prices(period="5d")

        # Verify DataFrame structure
        assert not df.empty, "DataFrame should not be empty"
        expected_cols = {
            "timestamp",
            "etf",
            "risk_type",
            "source",
            "close",
            "volume",
        }
        assert set(df.columns) == expected_cols

        # Verify all 5 ETFs present
        etfs = df["etf"].unique().tolist()
        print(f"\nRisk ETFs with price history: {etfs}")

        for ticker in RISK_ETF_TICKERS.values():
            assert ticker in etfs, f"Missing {ticker}"

        # Verify data types
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
        assert pd.api.types.is_numeric_dtype(df["close"])
        assert pd.api.types.is_numeric_dtype(df["volume"])

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_historical_prices_no_nan(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test forward fill handles gaps - no NaN in close prices."""
        df = await risk_etf_collector.collect_historical_prices(period="5d")

        # Forward fill should have removed all NaNs
        assert df["close"].isna().sum() == 0, "No NaN values should remain after ffill"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_equity_etfs(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test collecting equity ETFs returns SPY only."""
        df = await risk_etf_collector.collect_equity_etfs(period="5d")

        # Verify only SPY
        etfs = df["etf"].unique().tolist()
        assert "SPY" in etfs, "SPY should be present"
        assert len(etfs) == 1, "Should only have 1 ETF (SPY)"

        # Verify risk_type
        assert (df["risk_type"] == "equity").all()

        # Verify SPY price is reasonable (400-700 range typical)
        spy_close = df["close"]
        assert spy_close.min() > 300, f"SPY too low: {spy_close.min()}"
        assert spy_close.max() < 1000, f"SPY too high: {spy_close.max()}"
        print(f"\nSPY (latest): ${spy_close.iloc[-1]:.2f}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_bond_etfs(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test collecting bond ETFs returns TLT, IEF, HYG, LQD."""
        df = await risk_etf_collector.collect_bond_etfs(period="5d")

        # Verify 4 bond ETFs
        etfs = df["etf"].unique().tolist()
        assert "TLT" in etfs, "TLT should be present"
        assert "IEF" in etfs, "IEF should be present"
        assert "HYG" in etfs, "HYG should be present"
        assert "LQD" in etfs, "LQD should be present"
        assert len(etfs) == 4, "Should have 4 bond ETFs"

        # Verify risk_types
        expected_types = {
            "treasury_long",
            "treasury_mid",
            "high_yield",
            "investment_grade",
        }
        assert set(df["risk_type"].unique()) == expected_types

        # Verify TLT price is reasonable (80-130 range typical)
        tlt = df[df["etf"] == "TLT"]["close"]
        assert tlt.min() > 50, f"TLT too low: {tlt.min()}"
        assert tlt.max() < 200, f"TLT too high: {tlt.max()}"
        print(f"\nTLT (latest): ${tlt.iloc[-1]:.2f}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_estimate_daily_flows(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test share change calculation with mock historical data."""
        mock_data = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3).tolist() * 2,
                "etf": ["SPY"] * 3 + ["TLT"] * 3,
                "shares_outstanding": [
                    900_000_000,
                    905_000_000,
                    903_000_000,  # SPY
                    400_000_000,
                    402_000_000,
                    401_000_000,  # TLT
                ],
            }
        )

        result = RiskETFCollector.estimate_daily_flows(mock_data)

        # Should have shares_change column
        assert "shares_change" in result.columns

        # SPY changes: NaN, +5M, -2M
        spy_changes = result[result["etf"] == "SPY"]["shares_change"].tolist()
        assert pd.isna(spy_changes[0])
        assert spy_changes[1] == 5_000_000
        assert spy_changes[2] == -2_000_000

        # TLT changes: NaN, +2M, -1M
        tlt_changes = result[result["etf"] == "TLT"]["shares_change"].tolist()
        assert pd.isna(tlt_changes[0])
        assert tlt_changes[1] == 2_000_000
        assert tlt_changes[2] == -1_000_000

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_risk_appetite_ratio(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test SPY/TLT risk appetite calculation."""
        # Use real data - now method can fetch automatically
        result = await risk_etf_collector.calculate_risk_appetite()

        # Verify structure
        assert "spy_shares" in result
        assert "tlt_shares" in result
        assert "spy_tlt_ratio" in result
        assert "sentiment" in result

        # If data is valid, verify ratio makes sense
        if result["spy_shares"] is not None and result["tlt_shares"] is not None:
            ratio = result["spy_tlt_ratio"]
            assert ratio is not None
            # SPY/TLT ratio typically 5-15 (SPY ~900M shares, TLT ~100M shares)
            assert 3.0 < ratio < 20.0, f"Unexpected SPY/TLT ratio: {ratio}"
            assert result["sentiment"] in ["risk_on", "risk_off", "neutral"]
            print(f"\nSPY/TLT ratio: {ratio:.2f}")
            print(f"Sentiment: {result['sentiment']}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_output_format_shares(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test current shares DataFrame has correct columns."""
        df = await risk_etf_collector.collect_current_shares()

        # Verify required columns for shares output
        expected_cols = {
            "timestamp",
            "etf",
            "risk_type",
            "source",
            "shares_outstanding",
            "total_assets",
            "nav_price",
        }
        assert set(df.columns) == expected_cols

        # Verify column types
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
        assert pd.api.types.is_string_dtype(df["etf"])
        assert pd.api.types.is_string_dtype(df["risk_type"])
        assert pd.api.types.is_string_dtype(df["source"])

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_output_format_prices(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test historical prices DataFrame has correct columns."""
        df = await risk_etf_collector.collect_historical_prices(period="5d")

        # Verify required columns for prices output
        expected_cols = {
            "timestamp",
            "etf",
            "risk_type",
            "source",
            "close",
            "volume",
        }
        assert set(df.columns) == expected_cols

        # Verify column types
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
        assert pd.api.types.is_string_dtype(df["etf"])
        assert pd.api.types.is_string_dtype(df["risk_type"])
        assert pd.api.types.is_string_dtype(df["source"])
        assert pd.api.types.is_numeric_dtype(df["close"])
        assert pd.api.types.is_numeric_dtype(df["volume"])

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_etf_type_mapping(self, risk_etf_collector: RiskETFCollector) -> None:
        """Test risk_type column is populated correctly."""
        df = await risk_etf_collector.collect_historical_prices(period="5d")

        # Each ETF should have its correct risk_type
        for etf, expected_type in RISK_ETF_TYPE.items():
            etf_data = df[df["etf"] == etf]
            if not etf_data.empty:
                assert (etf_data["risk_type"] == expected_type).all(), (
                    f"{etf} should have risk_type={expected_type}"
                )


class TestRiskETFCollectorConvenience:
    """Tests for convenience methods."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_collect_all(self, risk_etf_collector: RiskETFCollector) -> None:
        """Test collect_all method returns all 5 ETFs."""
        df = await risk_etf_collector.collect_all(period="5d")

        # Should return historical prices
        expected_cols = {
            "timestamp",
            "etf",
            "risk_type",
            "source",
            "close",
            "volume",
        }
        assert set(df.columns) == expected_cols

        # All 5 ETFs should be present
        assert len(df["etf"].unique()) == 5


class TestFlowEstimation:
    """Tests for flow estimation methods."""

    def test_estimate_daily_flows_single_timestamp(self) -> None:
        """Test flow estimation with single timestamp returns unchanged."""
        mock_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01")],
                "etf": ["SPY"],
                "shares_outstanding": [900_000_000],
            }
        )

        result = RiskETFCollector.estimate_daily_flows(mock_data)

        # Should return unchanged (no historical data to compare)
        assert len(result) == 1
        assert (
            "shares_change" not in result.columns
            or result["shares_change"].isna().all()
        )

    def test_estimate_daily_flows_multiple_timestamps(self) -> None:
        """Test flow estimation with multiple timestamps."""
        mock_data = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=3),
                "etf": ["SPY", "SPY", "SPY"],
                "shares_outstanding": [900_000_000, 910_000_000, 905_000_000],
            }
        )

        result = RiskETFCollector.estimate_daily_flows(mock_data)

        # Should have shares_change column
        assert "shares_change" in result.columns

        # First value should be NaN (no previous to compare)
        assert pd.isna(result["shares_change"].iloc[0])

        # Second value: 910M - 900M = 10M
        assert result["shares_change"].iloc[1] == 10_000_000

        # Third value: 905M - 910M = -5M
        assert result["shares_change"].iloc[2] == -5_000_000


class TestRiskAppetiteCalculation:
    """Tests for risk appetite calculation."""

    def test_risk_appetite_empty_df(self) -> None:
        """Test risk appetite with empty DataFrame."""
        result = RiskETFCollector._calculate_risk_appetite_from_df(pd.DataFrame())

        assert result["spy_shares"] is None
        assert result["tlt_shares"] is None
        assert result["spy_tlt_ratio"] is None
        assert result["sentiment"] == "unknown"

    def test_risk_appetite_missing_spy(self) -> None:
        """Test risk appetite when SPY is missing."""
        df = pd.DataFrame(
            {
                "etf": ["TLT"],
                "shares_outstanding": [400_000_000],
            }
        )

        result = RiskETFCollector._calculate_risk_appetite_from_df(df)
        assert result["sentiment"] == "unknown"

    def test_risk_appetite_missing_tlt(self) -> None:
        """Test risk appetite when TLT is missing."""
        df = pd.DataFrame(
            {
                "etf": ["SPY"],
                "shares_outstanding": [900_000_000],
            }
        )

        result = RiskETFCollector._calculate_risk_appetite_from_df(df)
        assert result["sentiment"] == "unknown"

    def test_risk_appetite_risk_on(self) -> None:
        """Test risk_on sentiment calculation."""
        df = pd.DataFrame(
            {
                "etf": ["SPY", "TLT"],
                "shares_outstanding": [1_100_000_000, 100_000_000],  # ratio > 10
            }
        )

        result = RiskETFCollector._calculate_risk_appetite_from_df(df)

        assert result["spy_tlt_ratio"] is not None
        assert result["spy_tlt_ratio"] > 10.0
        assert result["sentiment"] == "risk_on"

    def test_risk_appetite_risk_off(self) -> None:
        """Test risk_off sentiment calculation."""
        df = pd.DataFrame(
            {
                "etf": ["SPY", "TLT"],
                "shares_outstanding": [500_000_000, 100_000_000],  # ratio < 6
            }
        )

        result = RiskETFCollector._calculate_risk_appetite_from_df(df)

        assert result["spy_tlt_ratio"] is not None
        assert result["spy_tlt_ratio"] < 6.0
        assert result["sentiment"] == "risk_off"

    def test_risk_appetite_neutral(self) -> None:
        """Test neutral sentiment calculation."""
        df = pd.DataFrame(
            {
                "etf": ["SPY", "TLT"],
                "shares_outstanding": [800_000_000, 100_000_000],  # ratio ~8
            }
        )

        result = RiskETFCollector._calculate_risk_appetite_from_df(df)

        assert result["spy_tlt_ratio"] is not None
        assert 6.0 <= result["spy_tlt_ratio"] <= 10.0
        assert result["sentiment"] == "neutral"


class TestRiskETFCollectorRegistry:
    """Tests for Risk ETF collector registry."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_registry_integration(self) -> None:
        """Test that Risk ETF collector is registered as 'risk_etfs'."""
        from liquidity.collectors import registry

        assert "risk_etfs" in registry.list_collectors()
        collector_cls = registry.get("risk_etfs")
        assert collector_cls is RiskETFCollector


class TestRiskAppetiteEdgeCases:
    """Edge case tests for risk appetite calculation."""

    @pytest.fixture
    def risk_etf_collector(self) -> RiskETFCollector:
        """Create Risk ETF collector."""
        return RiskETFCollector()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_calculate_risk_appetite_real_data(
        self, risk_etf_collector: RiskETFCollector
    ) -> None:
        """Test calculate_risk_appetite with real data."""
        result = await risk_etf_collector.calculate_risk_appetite()

        assert "spy_shares" in result
        assert "tlt_shares" in result
        assert "spy_tlt_ratio" in result
        assert "sentiment" in result

        # Verify reasonable values
        assert result["spy_shares"] > 0, "SPY shares should be positive"
        assert result["tlt_shares"] > 0, "TLT shares should be positive"
        assert result["spy_tlt_ratio"] > 0, "Ratio should be positive"
        assert result["sentiment"] in ["risk_on", "risk_off", "neutral"]

        print(f"\nRisk appetite: {result['sentiment']}")
        print(f"SPY/TLT ratio: {result['spy_tlt_ratio']:.2f}")

    def test_calculate_risk_appetite_from_df_full(self) -> None:
        """Test _calculate_risk_appetite_from_df with complete data."""
        mock_data = pd.DataFrame(
            {
                "timestamp": pd.Timestamp("2024-01-01"),
                "etf": ["SPY", "TLT", "IEF", "HYG", "LQD"],
                "shares_outstanding": [
                    900_000_000,
                    400_000_000,
                    200_000_000,
                    300_000_000,
                    250_000_000,
                ],
            }
        )

        result = RiskETFCollector._calculate_risk_appetite_from_df(mock_data)

        assert result["spy_shares"] == 900_000_000
        assert result["tlt_shares"] == 400_000_000
        assert result["spy_tlt_ratio"] == 900_000_000 / 400_000_000

    def test_calculate_risk_appetite_empty_df(self) -> None:
        """Test _calculate_risk_appetite_from_df with empty DataFrame."""
        empty_df = pd.DataFrame(columns=["timestamp", "etf", "shares_outstanding"])

        result = RiskETFCollector._calculate_risk_appetite_from_df(empty_df)

        # Empty DataFrame returns None values
        assert result["spy_shares"] is None
        assert result["tlt_shares"] is None
        assert result["spy_tlt_ratio"] is None
        assert result["sentiment"] == "unknown"

    def test_calculate_risk_appetite_missing_spy(self) -> None:
        """Test risk appetite when SPY is missing."""
        mock_data = pd.DataFrame(
            {
                "timestamp": pd.Timestamp("2024-01-01"),
                "etf": ["TLT", "IEF"],
                "shares_outstanding": [400_000_000, 200_000_000],
            }
        )

        result = RiskETFCollector._calculate_risk_appetite_from_df(mock_data)

        # Missing SPY returns None values
        assert result["spy_shares"] is None
        assert result["spy_tlt_ratio"] is None
        assert result["sentiment"] == "unknown"

    def test_calculate_risk_appetite_missing_tlt(self) -> None:
        """Test risk appetite when TLT is missing."""
        mock_data = pd.DataFrame(
            {
                "timestamp": pd.Timestamp("2024-01-01"),
                "etf": ["SPY", "IEF"],
                "shares_outstanding": [900_000_000, 200_000_000],
            }
        )

        result = RiskETFCollector._calculate_risk_appetite_from_df(mock_data)

        # Missing TLT returns None values
        assert result["tlt_shares"] is None
        assert result["spy_tlt_ratio"] is None
        assert result["sentiment"] == "unknown"


class TestFlowEstimationEdgeCases:
    """Edge case tests for flow estimation."""

    def test_estimate_daily_flows_empty(self) -> None:
        """Test flow estimation with empty DataFrame."""
        empty_df = pd.DataFrame(columns=["timestamp", "etf", "shares_outstanding"])

        result = RiskETFCollector.estimate_daily_flows(empty_df)

        assert result.empty

    def test_estimate_daily_flows_single_timestamp(self) -> None:
        """Test flow estimation with single timestamp per ETF."""
        mock_data = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01")] * 2,
                "etf": ["SPY", "TLT"],
                "shares_outstanding": [900_000_000, 400_000_000],
            }
        )

        result = RiskETFCollector.estimate_daily_flows(mock_data)

        # With only one timestamp per ETF, no diff can be calculated
        # Result should have NaN for shares_change
        assert "shares_change" in result.columns


class TestRiskETFCollectorInstantiation:
    """Tests for RiskETFCollector instantiation."""

    def test_collector_instantiation(self) -> None:
        """Test default instantiation."""
        collector = RiskETFCollector()
        assert collector.name == "risk_etfs"

    def test_collector_custom_name(self) -> None:
        """Test custom name instantiation."""
        collector = RiskETFCollector(name="custom_risk")
        assert collector.name == "custom_risk"

    def test_collector_class_attributes(self) -> None:
        """Test class attributes are accessible."""
        assert RiskETFCollector.RISK_ETF_TICKERS == RISK_ETF_TICKERS
        assert RiskETFCollector.RISK_ETF_TYPE == RISK_ETF_TYPE


if __name__ == "__main__":
    # Run a quick sanity check
    async def main() -> None:
        collector = RiskETFCollector()

        print("Fetching current shares outstanding...")
        shares_df = await collector.collect_current_shares()
        print(shares_df.to_string())

        print("\n\nRisk Appetite Calculation...")
        risk_appetite = RiskETFCollector._calculate_risk_appetite_from_df(shares_df)
        print(f"SPY shares: {risk_appetite['spy_shares']:,.0f}")
        print(f"TLT shares: {risk_appetite['tlt_shares']:,.0f}")
        print(f"SPY/TLT ratio: {risk_appetite['spy_tlt_ratio']:.2f}")
        print(f"Sentiment: {risk_appetite['sentiment']}")

        print("\n\nFetching historical prices (5d)...")
        prices_df = await collector.collect_historical_prices(period="5d")
        print(f"Total data points: {len(prices_df)}")

        for etf in prices_df["etf"].unique():
            etf_data = prices_df[prices_df["etf"] == etf]
            latest = etf_data["close"].iloc[-1]
            print(f"{etf}: ${latest:.2f}")

        print("\n\nFetching equity ETFs (SPY)...")
        equity_df = await collector.collect_equity_etfs(period="5d")
        print(f"SPY latest: ${equity_df['close'].iloc[-1]:.2f}")

        print("\n\nFetching bond ETFs...")
        bond_df = await collector.collect_bond_etfs(period="5d")
        print(f"Bond ETFs: {bond_df['etf'].unique().tolist()}")

    asyncio.run(main())
