"""Unit tests for PositioningAnalyzer."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from liquidity.analyzers.positioning import (
    DEFAULT_COMMODITIES,
    ExtremeType,
    PositioningAnalyzer,
    PositioningMetrics,
)


class TestExtremeType:
    """Tests for ExtremeType enum."""

    def test_spec_extreme_long_value(self):
        """Test SPEC_EXTREME_LONG enum value."""
        assert ExtremeType.SPEC_EXTREME_LONG == "SPEC_EXTREME_LONG"
        assert ExtremeType.SPEC_EXTREME_LONG.value == "SPEC_EXTREME_LONG"

    def test_spec_extreme_short_value(self):
        """Test SPEC_EXTREME_SHORT enum value."""
        assert ExtremeType.SPEC_EXTREME_SHORT == "SPEC_EXTREME_SHORT"
        assert ExtremeType.SPEC_EXTREME_SHORT.value == "SPEC_EXTREME_SHORT"

    def test_comm_extreme_long_value(self):
        """Test COMM_EXTREME_LONG enum value."""
        assert ExtremeType.COMM_EXTREME_LONG == "COMM_EXTREME_LONG"
        assert ExtremeType.COMM_EXTREME_LONG.value == "COMM_EXTREME_LONG"

    def test_comm_extreme_short_value(self):
        """Test COMM_EXTREME_SHORT enum value."""
        assert ExtremeType.COMM_EXTREME_SHORT == "COMM_EXTREME_SHORT"
        assert ExtremeType.COMM_EXTREME_SHORT.value == "COMM_EXTREME_SHORT"

    def test_all_extreme_types(self):
        """Test all extreme types are present."""
        extreme_values = [e.value for e in ExtremeType]
        assert len(extreme_values) == 4
        assert "SPEC_EXTREME_LONG" in extreme_values
        assert "SPEC_EXTREME_SHORT" in extreme_values
        assert "COMM_EXTREME_LONG" in extreme_values
        assert "COMM_EXTREME_SHORT" in extreme_values


class TestPositioningMetrics:
    """Tests for PositioningMetrics dataclass."""

    def test_dataclass_creation(self):
        """Test metrics dataclass can be created."""
        metrics = PositioningMetrics(
            commodity="WTI",
            timestamp=date(2026, 2, 4),
            comm_net=-150000,
            spec_net=120000,
            swap_net=30000,
            open_interest=500000,
            comm_spec_ratio=-1.25,
            spec_long_short_ratio=1.5,
            comm_pct_of_oi=45.0,
            spec_pct_of_oi=35.0,
            comm_net_percentile=25.0,
            spec_net_percentile=75.0,
            is_spec_extreme_long=False,
            is_spec_extreme_short=False,
            is_comm_extreme_long=False,
            is_comm_extreme_short=False,
        )

        assert metrics.commodity == "WTI"
        assert metrics.comm_net == -150000
        assert metrics.spec_net == 120000
        assert metrics.comm_spec_ratio == -1.25

    def test_extreme_flags(self):
        """Test extreme flags in metrics."""
        metrics = PositioningMetrics(
            commodity="GOLD",
            timestamp=date(2026, 2, 4),
            comm_net=100000,
            spec_net=200000,
            swap_net=50000,
            open_interest=400000,
            comm_spec_ratio=0.5,
            spec_long_short_ratio=2.0,
            comm_pct_of_oi=40.0,
            spec_pct_of_oi=50.0,
            comm_net_percentile=15.0,
            spec_net_percentile=92.0,
            is_spec_extreme_long=True,
            is_spec_extreme_short=False,
            is_comm_extreme_long=False,
            is_comm_extreme_short=False,
        )

        assert metrics.is_spec_extreme_long is True
        assert metrics.is_spec_extreme_short is False
        assert metrics.spec_net_percentile == 92.0


class TestDefaultCommodities:
    """Tests for default commodities list."""

    def test_default_commodities(self):
        """Test default commodities list."""
        assert "WTI" in DEFAULT_COMMODITIES
        assert "GOLD" in DEFAULT_COMMODITIES
        assert "COPPER" in DEFAULT_COMMODITIES
        assert "SILVER" in DEFAULT_COMMODITIES
        assert "NATGAS" in DEFAULT_COMMODITIES
        assert len(DEFAULT_COMMODITIES) == 5


class TestPositioningAnalyzerInit:
    """Tests for PositioningAnalyzer initialization."""

    def test_default_initialization(self):
        """Test analyzer initializes with default values."""
        analyzer = PositioningAnalyzer()
        assert analyzer.lookback_weeks == 52
        assert analyzer.EXTREME_HIGH == 90
        assert analyzer.EXTREME_LOW == 10

    def test_custom_lookback(self):
        """Test analyzer with custom lookback."""
        analyzer = PositioningAnalyzer(lookback_weeks=156)
        assert analyzer.lookback_weeks == 156

    def test_custom_thresholds(self):
        """Test analyzer with custom extreme thresholds."""
        analyzer = PositioningAnalyzer(extreme_high=95, extreme_low=5)
        assert analyzer.EXTREME_HIGH == 95
        assert analyzer.EXTREME_LOW == 5


class TestCalculateRatios:
    """Tests for ratio calculations."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer for tests."""
        return PositioningAnalyzer()

    def test_basic_ratios(self, analyzer):
        """Test basic ratio calculations."""
        row = {
            "comm_long": 100000,
            "comm_short": 50000,
            "spec_long": 80000,
            "spec_short": 60000,
            "open_interest": 300000,
        }
        ratios = analyzer.calculate_ratios(row)

        assert ratios["comm_net"] == 50000  # 100000 - 50000
        assert ratios["spec_net"] == 20000  # 80000 - 60000
        assert ratios["comm_spec_ratio"] == pytest.approx(2.5)  # 50000 / 20000
        assert ratios["spec_long_short_ratio"] == pytest.approx(1.333, rel=0.01)
        assert ratios["comm_pct_of_oi"] == 50.0  # (100000 + 50000) / 300000 * 100
        assert ratios["spec_pct_of_oi"] == pytest.approx(46.67, rel=0.01)

    def test_negative_net_positions(self, analyzer):
        """Test when commercial is net short."""
        row = {
            "comm_long": 30000,
            "comm_short": 80000,
            "spec_long": 100000,
            "spec_short": 50000,
            "open_interest": 200000,
        }
        ratios = analyzer.calculate_ratios(row)

        assert ratios["comm_net"] == -50000
        assert ratios["spec_net"] == 50000
        assert ratios["comm_spec_ratio"] == -1.0

    def test_zero_spec_net(self, analyzer):
        """Test when speculator net is zero (avoid division by zero)."""
        row = {
            "comm_long": 50000,
            "comm_short": 30000,
            "spec_long": 40000,
            "spec_short": 40000,
            "open_interest": 160000,
        }
        ratios = analyzer.calculate_ratios(row)

        assert ratios["spec_net"] == 0
        assert ratios["comm_spec_ratio"] == 0.0  # Default when spec_net is 0

    def test_zero_spec_short(self, analyzer):
        """Test when spec_short is zero."""
        row = {
            "comm_long": 50000,
            "comm_short": 30000,
            "spec_long": 40000,
            "spec_short": 0,
            "open_interest": 120000,
        }
        ratios = analyzer.calculate_ratios(row)

        assert ratios["spec_long_short_ratio"] == float("inf")

    def test_zero_open_interest(self, analyzer):
        """Test handling of zero open interest."""
        row = {
            "comm_long": 50000,
            "comm_short": 30000,
            "spec_long": 40000,
            "spec_short": 20000,
            "open_interest": 0,
        }
        ratios = analyzer.calculate_ratios(row)

        # Should use 1 as denominator to avoid div by zero
        assert ratios["comm_pct_of_oi"] > 0
        assert ratios["spec_pct_of_oi"] > 0

    def test_missing_keys(self, analyzer):
        """Test with missing keys uses defaults."""
        row = {}
        ratios = analyzer.calculate_ratios(row)

        assert ratios["comm_net"] == 0
        assert ratios["spec_net"] == 0
        assert ratios["comm_spec_ratio"] == 0.0


class TestPercentileRank:
    """Tests for percentile rank calculation."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer for tests."""
        return PositioningAnalyzer()

    def test_percentile_rank_basic(self, analyzer):
        """Test basic percentile calculation."""
        window = pd.Series([10, 20, 30, 40, 50])
        pctl = analyzer._percentile_rank(window)

        # Last value (50) is highest, should be high percentile
        assert pctl >= 80

    def test_percentile_rank_low(self, analyzer):
        """Test percentile for lowest value."""
        window = pd.Series([50, 40, 30, 20, 10])
        pctl = analyzer._percentile_rank(window)

        # Last value (10) is lowest, should be low percentile
        assert pctl <= 20

    def test_percentile_rank_middle(self, analyzer):
        """Test percentile for middle value."""
        window = pd.Series([10, 30, 50, 70, 40])
        pctl = analyzer._percentile_rank(window)

        # Last value (40) is in middle range
        assert 25 <= pctl <= 75

    def test_percentile_rank_single_value(self, analyzer):
        """Test percentile with single value returns default."""
        window = pd.Series([100])
        pctl = analyzer._percentile_rank(window)

        assert pctl == 50.0  # Default to median

    def test_percentile_rank_two_values(self, analyzer):
        """Test percentile with two values."""
        window = pd.Series([100, 200])
        pctl = analyzer._percentile_rank(window)

        # 200 is higher than 100
        assert pctl == 100.0

    def test_percentile_rank_with_nan(self, analyzer):
        """Test percentile with NaN values."""
        window = pd.Series([10, np.nan, 30, np.nan, 50])
        pctl = analyzer._percentile_rank(window)

        # Should handle NaN gracefully
        assert 0 <= pctl <= 100


class TestCalculatePercentileRanks:
    """Tests for calculate_percentile_ranks method."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with short lookback for testing."""
        return PositioningAnalyzer(lookback_weeks=5)

    @pytest.fixture
    def sample_data(self):
        """Create sample COT data."""
        dates = pd.date_range("2025-01-01", periods=10, freq="W")
        records = []

        # Commercial net positions (trending up)
        for i, ts in enumerate(dates):
            records.append(
                {
                    "timestamp": ts,
                    "series_id": "cot_wti_comm_net",
                    "source": "cftc",
                    "value": -100000 + i * 10000,  # -100k to -10k
                    "unit": "contracts",
                }
            )

        # Speculator net positions (trending up)
        for i, ts in enumerate(dates):
            records.append(
                {
                    "timestamp": ts,
                    "series_id": "cot_wti_spec_net",
                    "source": "cftc",
                    "value": 50000 + i * 5000,  # 50k to 95k
                    "unit": "contracts",
                }
            )

        return pd.DataFrame(records)

    def test_percentile_ranks_output_schema(self, analyzer, sample_data):
        """Test output has correct schema."""
        result = analyzer.calculate_percentile_ranks(sample_data, "WTI")

        assert "timestamp" in result.columns
        assert "series_id" in result.columns
        assert "source" in result.columns
        assert "value" in result.columns
        assert "unit" in result.columns

        assert all(result["source"] == "calculated")
        assert all(result["unit"] == "percentile")

    def test_percentile_ranks_series_ids(self, analyzer, sample_data):
        """Test correct series IDs are generated."""
        result = analyzer.calculate_percentile_ranks(sample_data, "WTI")

        series_ids = result["series_id"].unique()
        assert "cot_wti_comm_pctl" in series_ids
        assert "cot_wti_spec_pctl" in series_ids

    def test_percentile_ranks_values_in_range(self, analyzer, sample_data):
        """Test percentile values are between 0 and 100."""
        result = analyzer.calculate_percentile_ranks(sample_data, "WTI")

        assert all(result["value"] >= 0)
        assert all(result["value"] <= 100)

    def test_percentile_ranks_empty_commodity(self, analyzer, sample_data):
        """Test with commodity not in data."""
        result = analyzer.calculate_percentile_ranks(sample_data, "GOLD")

        assert result.empty

    def test_percentile_ranks_case_insensitive(self, analyzer, sample_data):
        """Test commodity name is case insensitive."""
        result1 = analyzer.calculate_percentile_ranks(sample_data, "WTI")
        result2 = analyzer.calculate_percentile_ranks(sample_data, "wti")

        assert len(result1) == len(result2)


class TestCalculateAllPercentiles:
    """Tests for calculate_all_percentiles method."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer for tests."""
        return PositioningAnalyzer(lookback_weeks=5)

    @pytest.fixture
    def multi_commodity_data(self):
        """Create sample data for multiple commodities."""
        dates = pd.date_range("2025-01-01", periods=10, freq="W")
        records = []

        for commodity in ["wti", "gold"]:
            for i, ts in enumerate(dates):
                records.extend(
                    [
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_comm_net",
                            "source": "cftc",
                            "value": -100000 + i * 10000,
                            "unit": "contracts",
                        },
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_spec_net",
                            "source": "cftc",
                            "value": 50000 + i * 5000,
                            "unit": "contracts",
                        },
                    ]
                )

        return pd.DataFrame(records)

    def test_all_percentiles_multiple_commodities(self, analyzer, multi_commodity_data):
        """Test percentile calculation for multiple commodities."""
        result = analyzer.calculate_all_percentiles(
            multi_commodity_data, commodities=["WTI", "GOLD"]
        )

        series_ids = result["series_id"].unique()
        assert "cot_wti_comm_pctl" in series_ids
        assert "cot_wti_spec_pctl" in series_ids
        assert "cot_gold_comm_pctl" in series_ids
        assert "cot_gold_spec_pctl" in series_ids


class TestDetectExtremes:
    """Tests for extreme positioning detection."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer for tests."""
        return PositioningAnalyzer()

    def test_detect_spec_extreme_long(self, analyzer):
        """Test detection of speculator extreme long."""
        data = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_spec_pctl",
                    "source": "calculated",
                    "value": 95.0,
                    "unit": "percentile",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_comm_pctl",
                    "source": "calculated",
                    "value": 30.0,
                    "unit": "percentile",
                },
            ]
        )

        extremes = analyzer.detect_extremes(data, commodities=["WTI"])

        assert len(extremes) == 1
        assert extremes.iloc[0]["commodity"] == "WTI"
        assert extremes.iloc[0]["extreme_type"] == "SPEC_EXTREME_LONG"

    def test_detect_spec_extreme_short(self, analyzer):
        """Test detection of speculator extreme short."""
        data = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_gold_spec_pctl",
                    "source": "calculated",
                    "value": 5.0,
                    "unit": "percentile",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_gold_comm_pctl",
                    "source": "calculated",
                    "value": 50.0,
                    "unit": "percentile",
                },
            ]
        )

        extremes = analyzer.detect_extremes(data, commodities=["GOLD"])

        assert len(extremes) == 1
        assert extremes.iloc[0]["extreme_type"] == "SPEC_EXTREME_SHORT"

    def test_detect_comm_extreme_long(self, analyzer):
        """Test detection of commercial extreme long."""
        data = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_copper_spec_pctl",
                    "source": "calculated",
                    "value": 50.0,
                    "unit": "percentile",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_copper_comm_pctl",
                    "source": "calculated",
                    "value": 92.0,
                    "unit": "percentile",
                },
            ]
        )

        extremes = analyzer.detect_extremes(data, commodities=["COPPER"])

        assert len(extremes) == 1
        assert extremes.iloc[0]["extreme_type"] == "COMM_EXTREME_LONG"

    def test_no_extremes(self, analyzer):
        """Test when no extreme conditions exist."""
        data = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_spec_pctl",
                    "source": "calculated",
                    "value": 50.0,
                    "unit": "percentile",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_comm_pctl",
                    "source": "calculated",
                    "value": 50.0,
                    "unit": "percentile",
                },
            ]
        )

        extremes = analyzer.detect_extremes(data, commodities=["WTI"])

        assert extremes.empty

    def test_spec_takes_priority_over_comm(self, analyzer):
        """Test that spec extreme takes priority when both are extreme."""
        data = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_spec_pctl",
                    "source": "calculated",
                    "value": 95.0,  # Spec extreme long
                    "unit": "percentile",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_comm_pctl",
                    "source": "calculated",
                    "value": 5.0,  # Comm extreme short (but lower priority)
                    "unit": "percentile",
                },
            ]
        )

        extremes = analyzer.detect_extremes(data, commodities=["WTI"])

        assert len(extremes) == 1
        assert extremes.iloc[0]["extreme_type"] == "SPEC_EXTREME_LONG"

    def test_custom_thresholds(self):
        """Test extreme detection with custom thresholds."""
        analyzer = PositioningAnalyzer(extreme_high=80, extreme_low=20)

        data = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_spec_pctl",
                    "source": "calculated",
                    "value": 85.0,  # Between 80-90
                    "unit": "percentile",
                },
                {
                    "timestamp": pd.Timestamp("2026-02-04"),
                    "series_id": "cot_wti_comm_pctl",
                    "source": "calculated",
                    "value": 50.0,
                    "unit": "percentile",
                },
            ]
        )

        extremes = analyzer.detect_extremes(data, commodities=["WTI"])

        # Should detect as extreme with 80 threshold but not with 90
        assert len(extremes) == 1
        assert extremes.iloc[0]["extreme_type"] == "SPEC_EXTREME_LONG"


class TestAnalyzeCommodity:
    """Tests for analyze_commodity method."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer for tests."""
        return PositioningAnalyzer(lookback_weeks=5)

    @pytest.fixture
    def full_commodity_data(self):
        """Create full sample data for a commodity."""
        dates = pd.date_range("2025-01-01", periods=10, freq="W")
        records = []

        for i, ts in enumerate(dates):
            # All series for WTI
            records.extend(
                [
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_comm_net",
                        "source": "cftc",
                        "value": -100000 + i * 10000,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_spec_net",
                        "source": "cftc",
                        "value": 50000 + i * 5000,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_swap_net",
                        "source": "cftc",
                        "value": 30000,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_oi",
                        "source": "cftc",
                        "value": 500000,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_comm_long",
                        "source": "cftc",
                        "value": 100000,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_comm_short",
                        "source": "cftc",
                        "value": 100000 - (-100000 + i * 10000),
                        "unit": "contracts",
                    },
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_spec_long",
                        "source": "cftc",
                        "value": 120000,
                        "unit": "contracts",
                    },
                    {
                        "timestamp": ts,
                        "series_id": "cot_wti_spec_short",
                        "source": "cftc",
                        "value": 120000 - (50000 + i * 5000),
                        "unit": "contracts",
                    },
                ]
            )

        return pd.DataFrame(records)

    def test_analyze_commodity_returns_metrics(self, analyzer, full_commodity_data):
        """Test that analyze_commodity returns PositioningMetrics."""
        result = analyzer.analyze_commodity(full_commodity_data, "WTI")

        assert isinstance(result, PositioningMetrics)
        assert result.commodity == "WTI"
        assert result.open_interest == 500000
        assert isinstance(result.comm_net_percentile, float)
        assert isinstance(result.spec_net_percentile, float)

    def test_analyze_commodity_extreme_flags(self, analyzer, full_commodity_data):
        """Test extreme flags are calculated."""
        result = analyzer.analyze_commodity(full_commodity_data, "WTI")

        # Flags should be bool
        assert isinstance(result.is_spec_extreme_long, bool)
        assert isinstance(result.is_spec_extreme_short, bool)
        assert isinstance(result.is_comm_extreme_long, bool)
        assert isinstance(result.is_comm_extreme_short, bool)


class TestAnalyzeAll:
    """Tests for analyze_all method."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer for tests."""
        return PositioningAnalyzer(lookback_weeks=5)

    @pytest.fixture
    def multi_full_data(self):
        """Create full data for multiple commodities."""
        dates = pd.date_range("2025-01-01", periods=10, freq="W")
        records = []

        for commodity in ["wti", "gold"]:
            for i, ts in enumerate(dates):
                records.extend(
                    [
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_comm_net",
                            "source": "cftc",
                            "value": -100000 + i * 10000,
                            "unit": "contracts",
                        },
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_spec_net",
                            "source": "cftc",
                            "value": 50000 + i * 5000,
                            "unit": "contracts",
                        },
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_swap_net",
                            "source": "cftc",
                            "value": 30000,
                            "unit": "contracts",
                        },
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_oi",
                            "source": "cftc",
                            "value": 500000,
                            "unit": "contracts",
                        },
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_comm_long",
                            "source": "cftc",
                            "value": 100000,
                            "unit": "contracts",
                        },
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_comm_short",
                            "source": "cftc",
                            "value": 200000 - i * 10000,
                            "unit": "contracts",
                        },
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_spec_long",
                            "source": "cftc",
                            "value": 120000,
                            "unit": "contracts",
                        },
                        {
                            "timestamp": ts,
                            "series_id": f"cot_{commodity}_spec_short",
                            "source": "cftc",
                            "value": 70000 - i * 5000,
                            "unit": "contracts",
                        },
                    ]
                )

        return pd.DataFrame(records)

    def test_analyze_all_returns_list(self, analyzer, multi_full_data):
        """Test analyze_all returns list of metrics."""
        results = analyzer.analyze_all(multi_full_data, commodities=["WTI", "GOLD"])

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, PositioningMetrics) for r in results)

    def test_analyze_all_commodities(self, analyzer, multi_full_data):
        """Test all requested commodities are analyzed."""
        results = analyzer.analyze_all(multi_full_data, commodities=["WTI", "GOLD"])

        commodities = [r.commodity for r in results]
        assert "WTI" in commodities
        assert "GOLD" in commodities
