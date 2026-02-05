"""Integration tests for consumer credit collector with real FRED API.

These tests verify:
- Real consumer spending data fetching from FRED
- Real consumer credit data fetching
- Real sentiment data fetching
- Data quality and format validation
- Value reasonableness checks

Run with: uv run pytest tests/integration/collectors/test_consumer_credit_integration.py -v

Note: These tests require:
- Network access
- Valid FRED_API_KEY in environment
"""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from liquidity.collectors.consumer_credit import (
    CONSUMER_SERIES,
    ConsumerCreditCollector,
)


@pytest.mark.integration
class TestSpendingIntegration:
    """Integration tests for spending data collection."""

    @pytest.mark.asyncio
    async def test_collect_spending_real_api(self) -> None:
        """Test fetching real spending data from FRED."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=365)
        df = await collector.collect_spending(start_date=start)

        # Should have data for spending series
        assert len(df) > 0, "Expected spending data"

        # Check DataFrame structure
        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert expected_columns.issubset(set(df.columns)), (
            f"Missing columns: {expected_columns - set(df.columns)}"
        )

        # Check at least one spending series present
        series_ids = df["series_id"].unique()
        spending_series_found = [s for s in series_ids if s in CONSUMER_SERIES["spending"]]
        assert len(spending_series_found) >= 1, (
            f"Expected at least one spending series, got: {series_ids}"
        )

        # Check source
        assert (df["source"] == "fred").all(), "Source should be 'fred'"

        print("\nSpending Integration Test Results:")
        print(f"  Records fetched: {len(df)}")
        print(f"  Series: {sorted(series_ids)}")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    @pytest.mark.asyncio
    async def test_retail_sales_value_range(self) -> None:
        """Test retail sales values are in reasonable range."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=90)
        df = await collector.collect_spending(start_date=start)

        rsafs = df[df["series_id"] == "RSAFS"]
        if len(rsafs) > 0:
            # RSAFS in millions USD, should be 500,000-1,000,000 (=$500B-$1T monthly)
            latest = rsafs["value"].iloc[-1]
            assert 300000 < latest < 1500000, (
                f"RSAFS value {latest} outside expected range (300k-1.5M millions USD)"
            )
            print(f"\nLatest RSAFS (Retail Sales): ${latest/1000:.0f}B")


@pytest.mark.integration
class TestCreditIntegration:
    """Integration tests for credit data collection."""

    @pytest.mark.asyncio
    async def test_collect_credit_real_api(self) -> None:
        """Test fetching real credit data from FRED."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=365)
        df = await collector.collect_credit(start_date=start)

        # Should have data for credit series
        assert len(df) > 0, "Expected credit data"

        # Check DataFrame structure
        expected_columns = {"timestamp", "series_id", "source", "value", "unit"}
        assert expected_columns.issubset(set(df.columns))

        # Check at least one credit series present
        series_ids = df["series_id"].unique()
        credit_series_found = [s for s in series_ids if s in CONSUMER_SERIES["credit"]]
        assert len(credit_series_found) >= 1, (
            f"Expected at least one credit series, got: {series_ids}"
        )

        print("\nCredit Integration Test Results:")
        print(f"  Records fetched: {len(df)}")
        print(f"  Series: {sorted(series_ids)}")

    @pytest.mark.asyncio
    async def test_total_consumer_credit_range(self) -> None:
        """Test total consumer credit values are in reasonable range."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=90)
        df = await collector.collect_credit(start_date=start)

        totalsl = df[df["series_id"] == "TOTALSL"]
        if len(totalsl) > 0:
            # TOTALSL in billions USD, should be 4,000-7,000 (=$4-7T total)
            latest = totalsl["value"].iloc[-1]
            assert 3000 < latest < 10000, (
                f"TOTALSL value {latest} outside expected range (3k-10k billions USD)"
            )
            print(f"\nLatest TOTALSL (Total Consumer Credit): ${latest:.0f}B")


@pytest.mark.integration
class TestSentimentIntegration:
    """Integration tests for sentiment data collection."""

    @pytest.mark.asyncio
    async def test_collect_sentiment_real_api(self) -> None:
        """Test fetching real sentiment data from FRED."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=365)
        df = await collector.collect_sentiment(start_date=start)

        # Should have sentiment data
        assert len(df) > 0, "Expected sentiment data"

        # Check UMCSENT is present
        assert "UMCSENT" in df["series_id"].values, "Expected UMCSENT series"

        # Check value ranges (UMCSENT typically 50-110)
        umcsent = df[df["series_id"] == "UMCSENT"]
        assert umcsent["value"].min() > 30, "UMCSENT should be > 30"
        assert umcsent["value"].max() < 130, "UMCSENT should be < 130"

        print("\nSentiment Integration Test Results:")
        print(f"  Records fetched: {len(df)}")
        print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"  Value range: {umcsent['value'].min():.1f} to {umcsent['value'].max():.1f}")

    @pytest.mark.asyncio
    async def test_sentiment_interpretation(self) -> None:
        """Test sentiment interpretation with real data."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=90)
        df = await collector.collect_sentiment(start_date=start)

        if len(df) > 0:
            level = collector.get_latest_sentiment_level(df)
            assert level in ["very_optimistic", "optimistic", "neutral", "pessimistic"]

            latest_value = df[df["series_id"] == "UMCSENT"]["value"].iloc[-1]
            print(f"\nLatest UMCSENT: {latest_value:.1f} -> {level}")


@pytest.mark.integration
class TestWeeklyHFIntegration:
    """Integration tests for weekly high-frequency data."""

    @pytest.mark.asyncio
    async def test_collect_weekly_hf_real_api(self) -> None:
        """Test fetching weekly high-frequency data from FRED."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=90)
        df = await collector.collect_weekly_hf(start_date=start)

        # Should have weekly data
        assert len(df) > 0, "Expected weekly HF data"

        # Check at least one weekly series
        series_ids = df["series_id"].unique()
        assert (
            "CCLACBW027SBOG" in series_ids or "CLSACBW027SBOG" in series_ids
        ), f"Expected weekly series, got: {series_ids}"

        print("\nWeekly HF Integration Test Results:")
        print(f"  Records fetched: {len(df)}")
        print(f"  Series: {sorted(series_ids)}")

    @pytest.mark.asyncio
    async def test_weekly_data_frequency(self) -> None:
        """Test that weekly data has expected frequency."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=90)
        df = await collector.collect_weekly_hf(start_date=start)

        if len(df) > 5:
            # Check one series for weekly frequency
            cclacb = df[df["series_id"] == "CCLACBW027SBOG"]
            if len(cclacb) > 3:
                cclacb = cclacb.sort_values("timestamp")
                # Difference between consecutive dates should be ~7 days
                diffs = cclacb["timestamp"].diff().dropna()
                avg_days = diffs.mean().days
                assert 5 <= avg_days <= 10, (
                    f"Expected weekly frequency (~7 days), got avg {avg_days} days"
                )
                print(f"\nWeekly data frequency: avg {avg_days} days between observations")


@pytest.mark.integration
class TestCollectAllIntegration:
    """Integration tests for combined data collection."""

    @pytest.mark.asyncio
    async def test_collect_all_real_api(self) -> None:
        """Test fetching all consumer data."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=180)
        df = await collector.collect(start_date=start)

        # Should have data from multiple series
        assert len(df) > 0, "Expected data from collect()"

        series_ids = df["series_id"].unique()
        assert len(series_ids) >= 3, (
            f"Expected at least 3 series, got {len(series_ids)}: {series_ids}"
        )

        print("\ncollect() Results:")
        print(f"  Total records: {len(df)}")
        print(f"  Series: {sorted(series_ids)}")

    @pytest.mark.asyncio
    async def test_collect_all_data_quality(self) -> None:
        """Test data quality from collect()."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=90)
        df = await collector.collect(start_date=start)

        if not df.empty:
            # No NaN in critical columns
            assert not df["timestamp"].isna().any(), "timestamp has NaN"
            assert not df["series_id"].isna().any(), "series_id has NaN"
            assert not df["value"].isna().any(), "value has NaN"

            # All values should be positive (these are all positive indicators)
            assert (df["value"] > 0).all(), "All values should be positive"


@pytest.mark.integration
class TestYoYGrowthIntegration:
    """Integration tests for YoY growth calculation with real data."""

    @pytest.mark.asyncio
    async def test_yoy_growth_with_real_data(self) -> None:
        """Test YoY growth calculation with real FRED data."""
        collector = ConsumerCreditCollector()

        # Need 13+ months of data for YoY calculation
        start = datetime.now(UTC) - timedelta(days=450)  # ~15 months
        df = await collector.collect_spending(start_date=start)

        if len(df) > 12:
            result = collector.calculate_yoy_growth(df)

            # Should have yoy_growth column
            assert "yoy_growth" in result.columns

            # Get rows with valid YoY
            valid_yoy = result.dropna(subset=["yoy_growth"])

            if len(valid_yoy) > 0:
                # Retail sales YoY should be reasonable (-20% to +30%)
                rsafs_yoy = valid_yoy[valid_yoy["series_id"] == "RSAFS"]
                if len(rsafs_yoy) > 0:
                    min_yoy = rsafs_yoy["yoy_growth"].min()
                    max_yoy = rsafs_yoy["yoy_growth"].max()
                    assert -50 < min_yoy < 50, f"RSAFS YoY min {min_yoy} seems extreme"
                    assert -50 < max_yoy < 50, f"RSAFS YoY max {max_yoy} seems extreme"

                    print(f"\nRSAFS YoY Growth Range: {min_yoy:.1f}% to {max_yoy:.1f}%")


@pytest.mark.integration
class TestCollectorRegistration:
    """Test collector is properly registered."""

    @pytest.mark.asyncio
    async def test_consumer_credit_in_registry(self) -> None:
        """Test that consumer_credit collector is registered."""
        from liquidity.collectors import registry

        assert "consumer_credit" in registry.list_collectors()
        collector_cls = registry.get("consumer_credit")
        assert collector_cls is ConsumerCreditCollector

    @pytest.mark.asyncio
    async def test_instantiate_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector_cls = registry.get("consumer_credit")
        collector = collector_cls()

        assert collector.name == "consumer_credit"


@pytest.mark.integration
class TestDataReasonableness:
    """Tests verifying data quality and reasonableness."""

    @pytest.mark.asyncio
    async def test_data_not_stale(self) -> None:
        """Test that fetched data is recent (not stale)."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=30)
        df = await collector.collect_spending(start_date=start)

        if df.empty:
            pytest.skip("No spending data available")

        # Latest data should be within last 45 days (monthly + delay)
        latest_date = df["timestamp"].max()
        today = pd.Timestamp.now(tz=None)

        days_old = (today - latest_date).days
        assert days_old < 60, f"Data is {days_old} days old, expected < 60"

        print(f"\nData freshness: Latest date is {latest_date} ({days_old} days old)")

    @pytest.mark.asyncio
    async def test_spending_vs_credit_values(self) -> None:
        """Test spending and credit values have expected relationship."""
        collector = ConsumerCreditCollector()

        start = datetime.now(UTC) - timedelta(days=30)
        spending_df = await collector.collect_spending(start_date=start)
        credit_df = await collector.collect_credit(start_date=start)

        if spending_df.empty or credit_df.empty:
            pytest.skip("Missing spending or credit data")

        # Get latest values
        rsafs = spending_df[spending_df["series_id"] == "RSAFS"]
        totalsl = credit_df[credit_df["series_id"] == "TOTALSL"]

        if len(rsafs) > 0 and len(totalsl) > 0:
            # RSAFS is monthly retail sales in millions
            # TOTALSL is total consumer credit outstanding in billions
            # Credit outstanding should be much larger than monthly sales

            rsafs_val = rsafs["value"].iloc[-1] / 1000  # Convert to billions
            totalsl_val = totalsl["value"].iloc[-1]

            # Total credit should be 5-15x monthly retail sales
            ratio = totalsl_val / rsafs_val
            assert 3 < ratio < 20, (
                f"Credit/Sales ratio {ratio:.1f} seems unusual (expected 5-15x)"
            )

            print(f"\nCredit to Sales Ratio: {ratio:.1f}x")
            print(f"  Monthly Retail Sales: ${rsafs_val:.0f}B")
            print(f"  Total Consumer Credit: ${totalsl_val:.0f}B")
