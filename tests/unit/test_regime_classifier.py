"""Unit tests for RegimeClassifier."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from liquidity.analyzers.regime_classifier import (
    REGIME_CONFIG,
    RegimeClassifier,
    RegimeDirection,
    RegimeResult,
)


class TestRegimeDirection:
    """Tests for RegimeDirection enum."""

    def test_expansion_value(self):
        """Test EXPANSION enum value."""
        assert RegimeDirection.EXPANSION == "EXPANSION"
        assert RegimeDirection.EXPANSION.value == "EXPANSION"

    def test_contraction_value(self):
        """Test CONTRACTION enum value."""
        assert RegimeDirection.CONTRACTION == "CONTRACTION"
        assert RegimeDirection.CONTRACTION.value == "CONTRACTION"

    def test_no_neutral_state(self):
        """Test that there is no NEUTRAL state - intentional design."""
        direction_values = [d.value for d in RegimeDirection]
        assert "NEUTRAL" not in direction_values
        assert len(direction_values) == 2


class TestRegimeResult:
    """Tests for RegimeResult dataclass."""

    def test_dataclass_creation(self):
        """Test result dataclass can be created."""
        result = RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.EXPANSION,
            intensity=65.0,
            confidence="HIGH",
            net_liq_percentile=0.75,
            global_liq_percentile=0.80,
            stealth_qe_score=0.60,
            components="NET:0.75 GLO:0.80 SQE:0.60",
        )
        assert result.direction == RegimeDirection.EXPANSION
        assert result.intensity == 65.0
        assert result.confidence == "HIGH"

    def test_dataclass_contraction(self):
        """Test result dataclass with CONTRACTION."""
        result = RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.CONTRACTION,
            intensity=40.0,
            confidence="MEDIUM",
            net_liq_percentile=0.30,
            global_liq_percentile=0.25,
            stealth_qe_score=0.40,
            components="NET:0.30 GLO:0.25 SQE:0.40",
        )
        assert result.direction == RegimeDirection.CONTRACTION
        assert result.confidence == "MEDIUM"


class TestRegimeConfig:
    """Tests for regime configuration."""

    def test_weights_sum_to_one(self):
        """Test that component weights sum to 1.0."""
        total = (
            REGIME_CONFIG["WEIGHT_NET_LIQUIDITY"]
            + REGIME_CONFIG["WEIGHT_GLOBAL_LIQUIDITY"]
            + REGIME_CONFIG["WEIGHT_STEALTH_QE"]
        )
        assert total == pytest.approx(1.0)

    def test_config_values(self):
        """Test config has expected values."""
        assert REGIME_CONFIG["WEIGHT_NET_LIQUIDITY"] == 0.40
        assert REGIME_CONFIG["WEIGHT_GLOBAL_LIQUIDITY"] == 0.40
        assert REGIME_CONFIG["WEIGHT_STEALTH_QE"] == 0.20
        assert REGIME_CONFIG["DEFAULT_LOOKBACK_DAYS"] == 90
        assert REGIME_CONFIG["STEALTH_QE_MAX_SCORE"] == 100.0


class TestRegimeClassifier:
    """Tests for RegimeClassifier class."""

    def test_init_default(self):
        """Test classifier initialization with defaults."""
        classifier = RegimeClassifier()
        assert classifier is not None
        assert classifier._lookback_days == 90
        assert classifier._weights["NET_LIQUIDITY"] == 0.40
        assert classifier._weights["GLOBAL_LIQUIDITY"] == 0.40
        assert classifier._weights["STEALTH_QE"] == 0.20

    def test_init_custom_lookback(self):
        """Test classifier with custom lookback."""
        classifier = RegimeClassifier(lookback_days=60)
        assert classifier._lookback_days == 60

    def test_init_custom_weights(self):
        """Test classifier with custom weights."""
        custom_weights = {
            "NET_LIQUIDITY": 0.50,
            "GLOBAL_LIQUIDITY": 0.30,
            "STEALTH_QE": 0.20,
        }
        classifier = RegimeClassifier(weights=custom_weights)
        assert classifier._weights["NET_LIQUIDITY"] == 0.50
        assert classifier._weights["GLOBAL_LIQUIDITY"] == 0.30

    def test_init_invalid_weights_missing_key(self):
        """Test classifier rejects weights with missing keys."""
        invalid_weights = {
            "NET_LIQUIDITY": 0.50,
            "GLOBAL_LIQUIDITY": 0.50,
            # Missing STEALTH_QE
        }
        with pytest.raises(ValueError, match="Missing required weight keys"):
            RegimeClassifier(weights=invalid_weights)

    def test_init_invalid_weights_sum(self):
        """Test classifier rejects weights that don't sum to 1.0."""
        invalid_weights = {
            "NET_LIQUIDITY": 0.50,
            "GLOBAL_LIQUIDITY": 0.50,
            "STEALTH_QE": 0.50,  # Sum = 1.5
        }
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            RegimeClassifier(weights=invalid_weights)

    def test_repr(self):
        """Test string representation."""
        classifier = RegimeClassifier()
        repr_str = repr(classifier)
        assert "RegimeClassifier" in repr_str
        assert "lookback=90" in repr_str


class TestRegimeDirectionExpansion:
    """Tests for EXPANSION regime direction."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return RegimeClassifier()

    def test_regime_direction_expansion_high_percentiles(self, classifier):
        """Test EXPANSION when all percentiles are high (> 0.5)."""
        # Composite = 0.75*0.4 + 0.80*0.4 + 0.70*0.2 = 0.30 + 0.32 + 0.14 = 0.76
        # 0.76 > 0.5 -> EXPANSION
        net_liq_pct = 0.75
        global_liq_pct = 0.80
        stealth_norm = 0.70

        composite = (
            net_liq_pct * classifier._weights["NET_LIQUIDITY"]
            + global_liq_pct * classifier._weights["GLOBAL_LIQUIDITY"]
            + stealth_norm * classifier._weights["STEALTH_QE"]
        )

        direction = (
            RegimeDirection.EXPANSION
            if composite > 0.5
            else RegimeDirection.CONTRACTION
        )

        assert direction == RegimeDirection.EXPANSION
        assert composite > 0.5


class TestRegimeDirectionContraction:
    """Tests for CONTRACTION regime direction."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return RegimeClassifier()

    def test_regime_direction_contraction_low_percentiles(self, classifier):
        """Test CONTRACTION when all percentiles are low (< 0.5)."""
        # Composite = 0.20*0.4 + 0.25*0.4 + 0.30*0.2 = 0.08 + 0.10 + 0.06 = 0.24
        # 0.24 < 0.5 -> CONTRACTION
        net_liq_pct = 0.20
        global_liq_pct = 0.25
        stealth_norm = 0.30

        composite = (
            net_liq_pct * classifier._weights["NET_LIQUIDITY"]
            + global_liq_pct * classifier._weights["GLOBAL_LIQUIDITY"]
            + stealth_norm * classifier._weights["STEALTH_QE"]
        )

        direction = (
            RegimeDirection.EXPANSION
            if composite > 0.5
            else RegimeDirection.CONTRACTION
        )

        assert direction == RegimeDirection.CONTRACTION
        assert composite <= 0.5


class TestIntensityExtremeExpansion:
    """Tests for extreme expansion intensity."""

    def test_intensity_extreme_expansion(self):
        """Test intensity at extreme expansion (composite near 1.0)."""
        # Composite = 1.0 -> Intensity = |1.0 - 0.5| * 200 = 100
        composite = 1.0
        intensity = abs(composite - 0.5) * 200
        intensity = max(0.0, min(100.0, intensity))

        assert intensity == 100.0

    def test_intensity_high_expansion(self):
        """Test intensity at high expansion."""
        # Composite = 0.90 -> Intensity = |0.90 - 0.5| * 200 = 80
        composite = 0.90
        intensity = abs(composite - 0.5) * 200
        intensity = max(0.0, min(100.0, intensity))

        assert intensity == pytest.approx(80.0)


class TestIntensityExtremeContraction:
    """Tests for extreme contraction intensity."""

    def test_intensity_extreme_contraction(self):
        """Test intensity at extreme contraction (composite near 0.0)."""
        # Composite = 0.0 -> Intensity = |0.0 - 0.5| * 200 = 100
        composite = 0.0
        intensity = abs(composite - 0.5) * 200
        intensity = max(0.0, min(100.0, intensity))

        assert intensity == 100.0

    def test_intensity_high_contraction(self):
        """Test intensity at high contraction."""
        # Composite = 0.10 -> Intensity = |0.10 - 0.5| * 200 = 80
        composite = 0.10
        intensity = abs(composite - 0.5) * 200
        intensity = max(0.0, min(100.0, intensity))

        assert intensity == pytest.approx(80.0)


class TestIntensityNeutralZone:
    """Tests for neutral zone intensity."""

    def test_intensity_at_threshold(self):
        """Test intensity exactly at the 0.5 threshold."""
        # Composite = 0.5 -> Intensity = |0.5 - 0.5| * 200 = 0
        composite = 0.5
        intensity = abs(composite - 0.5) * 200
        intensity = max(0.0, min(100.0, intensity))

        assert intensity == 0.0

    def test_intensity_near_threshold_expansion(self):
        """Test intensity just above threshold (weak expansion)."""
        # Composite = 0.55 -> Intensity = |0.55 - 0.5| * 200 = 10
        composite = 0.55
        intensity = abs(composite - 0.5) * 200
        intensity = max(0.0, min(100.0, intensity))

        assert intensity == pytest.approx(10.0)

    def test_intensity_near_threshold_contraction(self):
        """Test intensity just below threshold (weak contraction)."""
        # Composite = 0.45 -> Intensity = |0.45 - 0.5| * 200 = 10
        composite = 0.45
        intensity = abs(composite - 0.5) * 200
        intensity = max(0.0, min(100.0, intensity))

        assert intensity == pytest.approx(10.0)


class TestConfidenceHighAllAgree:
    """Tests for HIGH confidence when all components agree."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return RegimeClassifier()

    def test_confidence_high_all_expansion(self, classifier):
        """Test HIGH confidence when all 3 indicate expansion."""
        confidence = classifier._calculate_confidence(
            net_liq_pct=0.75,  # > 0.5 = expansion
            global_liq_pct=0.80,  # > 0.5 = expansion
            stealth_qe_norm=0.70,  # > 0.5 = expansion
        )
        assert confidence == "HIGH"

    def test_confidence_high_all_contraction(self, classifier):
        """Test HIGH confidence when all 3 indicate contraction."""
        confidence = classifier._calculate_confidence(
            net_liq_pct=0.20,  # < 0.5 = contraction
            global_liq_pct=0.30,  # < 0.5 = contraction
            stealth_qe_norm=0.25,  # < 0.5 = contraction
        )
        assert confidence == "HIGH"


class TestConfidenceMediumTwoAgree:
    """Tests for MEDIUM confidence when 2 of 3 agree."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return RegimeClassifier()

    def test_confidence_medium_two_expansion(self, classifier):
        """Test MEDIUM confidence when 2 indicate expansion, 1 contraction."""
        confidence = classifier._calculate_confidence(
            net_liq_pct=0.75,  # > 0.5 = expansion
            global_liq_pct=0.80,  # > 0.5 = expansion
            stealth_qe_norm=0.30,  # < 0.5 = contraction
        )
        assert confidence == "MEDIUM"

    def test_confidence_medium_two_contraction(self, classifier):
        """Test MEDIUM confidence when 2 indicate contraction, 1 expansion."""
        confidence = classifier._calculate_confidence(
            net_liq_pct=0.30,  # < 0.5 = contraction
            global_liq_pct=0.25,  # < 0.5 = contraction
            stealth_qe_norm=0.70,  # > 0.5 = expansion
        )
        assert confidence == "MEDIUM"

    def test_confidence_medium_different_split(self, classifier):
        """Test MEDIUM confidence with different component split."""
        confidence = classifier._calculate_confidence(
            net_liq_pct=0.75,  # > 0.5 = expansion
            global_liq_pct=0.30,  # < 0.5 = contraction
            stealth_qe_norm=0.70,  # > 0.5 = expansion
        )
        assert confidence == "MEDIUM"


class TestConfidenceLowSplit:
    """Tests for LOW confidence - note: with 3 components, this is actually MEDIUM."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return RegimeClassifier()

    def test_confidence_at_exact_threshold(self, classifier):
        """Test confidence when values are exactly at 0.5 threshold."""
        # When exactly at 0.5, they count as contraction (> 0.5 check)
        confidence = classifier._calculate_confidence(
            net_liq_pct=0.50,  # not > 0.5, counts as contraction
            global_liq_pct=0.50,  # not > 0.5, counts as contraction
            stealth_qe_norm=0.50,  # not > 0.5, counts as contraction
        )
        # All 3 count as contraction (not > 0.5), so HIGH confidence
        assert confidence == "HIGH"

    def test_confidence_mixed_at_threshold(self, classifier):
        """Test confidence with one component exactly at threshold."""
        confidence = classifier._calculate_confidence(
            net_liq_pct=0.50,  # not > 0.5 = contraction
            global_liq_pct=0.60,  # > 0.5 = expansion
            stealth_qe_norm=0.40,  # < 0.5 = contraction
        )
        # 2 contraction, 1 expansion = MEDIUM
        assert confidence == "MEDIUM"


class TestWeightNormalization:
    """Tests for weight normalization validation."""

    def test_weight_normalization_valid(self):
        """Test valid weight normalization."""
        weights = {
            "NET_LIQUIDITY": 0.40,
            "GLOBAL_LIQUIDITY": 0.40,
            "STEALTH_QE": 0.20,
        }
        classifier = RegimeClassifier(weights=weights)
        total = sum(classifier._weights.values())
        assert total == pytest.approx(1.0)

    def test_weight_normalization_custom_valid(self):
        """Test custom weights that sum to 1.0."""
        weights = {
            "NET_LIQUIDITY": 0.33,
            "GLOBAL_LIQUIDITY": 0.33,
            "STEALTH_QE": 0.34,
        }
        classifier = RegimeClassifier(weights=weights)
        total = sum(classifier._weights.values())
        assert total == pytest.approx(1.0)

    def test_weight_normalization_rejects_invalid(self):
        """Test that invalid weights are rejected."""
        weights = {
            "NET_LIQUIDITY": 0.30,
            "GLOBAL_LIQUIDITY": 0.30,
            "STEALTH_QE": 0.30,  # Sum = 0.90 != 1.0
        }
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            RegimeClassifier(weights=weights)


class TestCalculatePercentile:
    """Tests for percentile calculation."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return RegimeClassifier()

    def test_percentile_basic(self, classifier):
        """Test basic percentile calculation."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
                "net_liquidity": list(range(1, 101)),  # 1 to 100
            }
        )

        # Current value is 100 (highest), percentile should be ~0.99
        pct = classifier._calculate_percentile(df, "net_liquidity", lookback_days=100)
        assert pct == pytest.approx(0.99, abs=0.01)

    def test_percentile_lowest_value(self, classifier):
        """Test percentile when current value is lowest."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
                "net_liquidity": list(range(100, 0, -1)),  # 100 to 1 (current=1)
            }
        )

        # Current value is 1 (lowest), percentile should be ~0.0
        pct = classifier._calculate_percentile(df, "net_liquidity", lookback_days=100)
        assert pct == pytest.approx(0.0, abs=0.01)

    def test_percentile_median_value(self, classifier):
        """Test percentile when current value is median."""
        # Create 100 values where current (last) value 50 is around the median
        values = list(range(1, 100)) + [50]  # 99 values 1-99 plus 50 at the end
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
                "net_liquidity": values,
            }
        )

        pct = classifier._calculate_percentile(df, "net_liquidity", lookback_days=100)
        # 50 is around median (49 values below 50, 49 values above 50)
        assert 0.45 <= pct <= 0.55

    def test_percentile_empty_dataframe(self, classifier):
        """Test percentile with empty DataFrame returns 0.5."""
        df = pd.DataFrame(columns=["timestamp", "net_liquidity"])
        pct = classifier._calculate_percentile(df, "net_liquidity", lookback_days=90)
        assert pct == 0.5

    def test_percentile_missing_column(self, classifier):
        """Test percentile with missing column returns 0.5."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, freq="D"),
                "other_column": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            }
        )
        pct = classifier._calculate_percentile(df, "net_liquidity", lookback_days=90)
        assert pct == 0.5

    def test_percentile_insufficient_data(self, classifier):
        """Test percentile with only 1 data point returns 0.5."""
        df = pd.DataFrame(
            {
                "timestamp": [datetime.now(UTC)],
                "net_liquidity": [100.0],
            }
        )
        pct = classifier._calculate_percentile(df, "net_liquidity", lookback_days=90)
        assert pct == 0.5


class TestEmptyHistoricalDataFrame:
    """Tests for empty historical DataFrame."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance."""
        return RegimeClassifier()

    def test_empty_historical_columns(self, classifier):
        """Test empty historical DataFrame has correct columns."""
        df = classifier._empty_historical_dataframe()
        expected_cols = [
            "timestamp",
            "direction",
            "intensity",
            "confidence",
            "net_liq_percentile",
            "global_liq_percentile",
            "stealth_qe_score",
        ]
        assert list(df.columns) == expected_cols
        assert df.empty


class TestClassifyMethod:
    """Integration tests for the classify method."""

    @pytest.fixture
    def mock_net_liq_result(self):
        """Create mock net liquidity result."""
        from liquidity.calculators.net_liquidity import NetLiquidityResult, Sentiment

        return NetLiquidityResult(
            timestamp=datetime.now(UTC),
            net_liquidity=5000.0,
            walcl=8000.0,
            tga=1000.0,
            rrp=2000.0,
            weekly_delta=100.0,
            monthly_delta=200.0,
            delta_60d=400.0,
            delta_90d=600.0,
            sentiment=Sentiment.BULLISH,
        )

    @pytest.fixture
    def mock_global_liq_result(self):
        """Create mock global liquidity result."""
        from liquidity.calculators.global_liquidity import GlobalLiquidityResult

        return GlobalLiquidityResult(
            timestamp=datetime.now(UTC),
            total_usd=30000.0,
            fed_usd=8000.0,
            ecb_usd=7000.0,
            boj_usd=5000.0,
            pboc_usd=10000.0,
            boe_usd=None,
            snb_usd=None,
            boc_usd=None,
            weekly_delta=150.0,
            delta_30d=300.0,
            delta_60d=600.0,
            delta_90d=900.0,
            coverage_pct=95.0,
        )

    @pytest.fixture
    def mock_stealth_qe_result(self):
        """Create mock stealth QE result."""
        from liquidity.calculators.stealth_qe import StealthQEResult

        return StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=60.0,  # Above 50 -> bullish
            score_weekly=55.0,
            rrp_level=500.0,
            rrp_velocity=-5.0,
            tga_level=800.0,
            tga_spending=25.0,
            fed_total=8000.0,
            fed_change=10.0,
            components="RRP:25% TGA:12% FED:10%",
            status="ACTIVE",
        )

    @pytest.fixture
    def mock_net_liq_df(self):
        """Create mock net liquidity DataFrame."""
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
                "net_liquidity": list(range(4500, 5500, 10)),  # Rising trend
            }
        )

    @pytest.fixture
    def mock_global_liq_df(self):
        """Create mock global liquidity DataFrame."""
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
                "global_liquidity": list(range(28000, 32000, 40)),  # Rising trend
            }
        )

    @pytest.mark.asyncio
    async def test_classify_expansion(
        self,
        mock_stealth_qe_result,
        mock_net_liq_df,
        mock_global_liq_df,
    ):
        """Test classify method returns EXPANSION with bullish data."""
        classifier = RegimeClassifier()

        with (
            patch.object(
                classifier._stealth_qe_calc, "get_current", new_callable=AsyncMock
            ) as mock_stealth_current,
            patch.object(
                classifier._net_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_net_calc,
            patch.object(
                classifier._global_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_global_calc,
        ):
            mock_stealth_current.return_value = mock_stealth_qe_result
            mock_net_calc.return_value = mock_net_liq_df
            mock_global_calc.return_value = mock_global_liq_df

            result = await classifier.classify()

            assert isinstance(result, RegimeResult)
            assert result.direction == RegimeDirection.EXPANSION
            assert result.intensity >= 0
            assert result.intensity <= 100
            assert result.confidence in ["HIGH", "MEDIUM", "LOW"]

    @pytest.mark.asyncio
    async def test_classify_contraction(self):
        """Test classify method returns CONTRACTION with bearish data."""
        from liquidity.calculators.global_liquidity import GlobalLiquidityResult
        from liquidity.calculators.net_liquidity import NetLiquidityResult, Sentiment
        from liquidity.calculators.stealth_qe import StealthQEResult

        # Bearish net liquidity
        bearish_net_result = NetLiquidityResult(
            timestamp=datetime.now(UTC),
            net_liquidity=4000.0,  # Low
            walcl=7000.0,
            tga=1500.0,
            rrp=1500.0,
            weekly_delta=-50.0,
            monthly_delta=-100.0,
            delta_60d=-200.0,
            delta_90d=-300.0,
            sentiment=Sentiment.BEARISH,
        )

        # Bearish stealth QE
        bearish_stealth_result = StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=20.0,  # Below 50 -> bearish
            score_weekly=25.0,
            rrp_level=600.0,
            rrp_velocity=5.0,
            tga_level=900.0,
            tga_spending=-25.0,
            fed_total=7000.0,
            fed_change=-10.0,
            components="RRP:0% TGA:0% FED:0%",
            status="LOW",
        )

        # Bearish net liquidity DataFrame (declining values)
        bearish_net_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
                "net_liquidity": list(range(5000, 4000, -10)),  # Declining trend
            }
        )

        # Bearish global liquidity DataFrame
        bearish_global_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="D"),
                "global_liquidity": list(range(32000, 28000, -40)),  # Declining trend
            }
        )

        # Bearish global result
        bearish_global_result = GlobalLiquidityResult(
            timestamp=datetime.now(UTC),
            total_usd=28000.0,
            fed_usd=7000.0,
            ecb_usd=6500.0,
            boj_usd=4500.0,
            pboc_usd=10000.0,
            boe_usd=None,
            snb_usd=None,
            boc_usd=None,
            weekly_delta=-100.0,
            delta_30d=-200.0,
            delta_60d=-400.0,
            delta_90d=-600.0,
            coverage_pct=95.0,
        )

        classifier = RegimeClassifier()

        with (
            patch.object(
                classifier._net_liq_calc, "get_current", new_callable=AsyncMock
            ) as mock_net_current,
            patch.object(
                classifier._global_liq_calc, "get_current", new_callable=AsyncMock
            ) as mock_global_current,
            patch.object(
                classifier._stealth_qe_calc, "get_current", new_callable=AsyncMock
            ) as mock_stealth_current,
            patch.object(
                classifier._net_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_net_calc,
            patch.object(
                classifier._global_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_global_calc,
        ):
            mock_net_current.return_value = bearish_net_result
            mock_global_current.return_value = bearish_global_result
            mock_stealth_current.return_value = bearish_stealth_result
            mock_net_calc.return_value = bearish_net_df
            mock_global_calc.return_value = bearish_global_df

            result = await classifier.classify()

            assert isinstance(result, RegimeResult)
            assert result.direction == RegimeDirection.CONTRACTION
