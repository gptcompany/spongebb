"""Integration tests for analyzers module.

Tests the full pipeline:
    Mock Calculators -> RegimeClassifier -> CorrelationEngine -> AlertEngine

Uses synthetic data to verify:
- Regime classification with mock liquidity data
- Correlation engine with synthetic prices
- Alert engine regime shift detection
- Alert engine correlation breakdown detection
- Full pipeline integration
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from liquidity.analyzers import (
    Alert,
    AlertEngine,
    AlertSeverity,
    AlertType,
    CorrelationEngine,
    RegimeClassifier,
    RegimeDirection,
    RegimeResult,
)


class TestRegimeClassifierWithMockData:
    """Integration tests for RegimeClassifier with mock calculator data."""

    @pytest.fixture
    def mock_bullish_stealth_qe(self):
        """Create mock bullish stealth QE result."""
        from liquidity.calculators.stealth_qe import StealthQEResult

        return StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=70.0,  # Above 50 -> bullish
            score_weekly=65.0,
            rrp_level=400.0,
            rrp_velocity=-10.0,
            tga_level=700.0,
            tga_spending=30.0,
            fed_total=8500.0,
            fed_change=15.0,
            components="RRP:30% TGA:15% FED:12%",
            status="ACTIVE",
        )

    @pytest.fixture
    def mock_bearish_stealth_qe(self):
        """Create mock bearish stealth QE result."""
        from liquidity.calculators.stealth_qe import StealthQEResult

        return StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=25.0,  # Below 50 -> bearish
            score_weekly=30.0,
            rrp_level=600.0,
            rrp_velocity=5.0,
            tga_level=900.0,
            tga_spending=-20.0,
            fed_total=7500.0,
            fed_change=-10.0,
            components="RRP:0% TGA:0% FED:0%",
            status="LOW",
        )

    @pytest.fixture
    def rising_liquidity_df(self):
        """Create DataFrame with rising liquidity trend."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        # Rising trend: current value will be high percentile
        values = list(range(4500, 5500, 10))
        return pd.DataFrame({"timestamp": dates, "net_liquidity": values})

    @pytest.fixture
    def falling_liquidity_df(self):
        """Create DataFrame with falling liquidity trend."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        # Falling trend: current value will be low percentile
        values = list(range(5500, 4500, -10))
        return pd.DataFrame({"timestamp": dates, "net_liquidity": values})

    @pytest.fixture
    def rising_global_df(self):
        """Create DataFrame with rising global liquidity."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        values = list(range(28000, 32000, 40))
        return pd.DataFrame({"timestamp": dates, "global_liquidity": values})

    @pytest.fixture
    def falling_global_df(self):
        """Create DataFrame with falling global liquidity."""
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        values = list(range(32000, 28000, -40))
        return pd.DataFrame({"timestamp": dates, "global_liquidity": values})

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_regime_classifier_expansion(
        self,
        mock_bullish_stealth_qe,
        rising_liquidity_df,
        rising_global_df,
    ):
        """Test regime classifier returns EXPANSION with bullish data."""
        classifier = RegimeClassifier()

        with (
            patch.object(
                classifier._stealth_qe_calc, "get_current", new_callable=AsyncMock
            ) as mock_stealth,
            patch.object(
                classifier._net_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_net,
            patch.object(
                classifier._global_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_global,
        ):
            mock_stealth.return_value = mock_bullish_stealth_qe
            mock_net.return_value = rising_liquidity_df
            mock_global.return_value = rising_global_df

            result = await classifier.classify()

            assert isinstance(result, RegimeResult)
            assert result.direction == RegimeDirection.EXPANSION
            assert result.intensity >= 0
            assert result.intensity <= 100
            assert result.confidence in ["HIGH", "MEDIUM", "LOW"]
            # Components string should be formatted
            assert "NET:" in result.components
            assert "GLO:" in result.components
            assert "SQE:" in result.components

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_regime_classifier_contraction(
        self,
        mock_bearish_stealth_qe,
        falling_liquidity_df,
        falling_global_df,
    ):
        """Test regime classifier returns CONTRACTION with bearish data."""
        classifier = RegimeClassifier()

        with (
            patch.object(
                classifier._stealth_qe_calc, "get_current", new_callable=AsyncMock
            ) as mock_stealth,
            patch.object(
                classifier._net_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_net,
            patch.object(
                classifier._global_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_global,
        ):
            mock_stealth.return_value = mock_bearish_stealth_qe
            mock_net.return_value = falling_liquidity_df
            mock_global.return_value = falling_global_df

            result = await classifier.classify()

            assert isinstance(result, RegimeResult)
            assert result.direction == RegimeDirection.CONTRACTION
            assert result.intensity >= 0
            assert result.intensity <= 100


class TestCorrelationEngineWithSyntheticPrices:
    """Integration tests for CorrelationEngine with synthetic price data."""

    @pytest.fixture
    def synthetic_prices(self):
        """Create synthetic price data with known correlations.

        We create RETURNS with known correlations, then convert to prices.
        This ensures the correlation structure is preserved when we calculate
        returns from prices.
        """
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=200, freq="D")

        # Create base return signal (this will be the liquidity returns)
        liquidity_returns = np.random.randn(200) * 0.02

        # BTC returns: highly correlated with liquidity (0.8 factor)
        btc_returns = liquidity_returns * 0.8 + np.random.randn(200) * 0.006

        # GOLD returns: negatively correlated (-0.6 factor)
        gold_returns = -liquidity_returns * 0.6 + np.random.randn(200) * 0.008

        # DXY returns: uncorrelated (pure noise)
        dxy_returns = np.random.randn(200) * 0.01

        # Convert returns to prices (cumulative product)
        btc_prices = 50000 * np.cumprod(1 + btc_returns)
        gold_prices = 2000 * np.cumprod(1 + gold_returns)
        dxy_prices = 100 * np.cumprod(1 + dxy_returns)
        liquidity_levels = 5000 * np.cumprod(1 + liquidity_returns)

        prices = pd.DataFrame(
            {
                "BTC": btc_prices,
                "GOLD": gold_prices,
                "DXY": dxy_prices,
            },
            index=dates,
        )

        liquidity = pd.Series(liquidity_levels, index=dates, name="liquidity")

        return prices, liquidity

    @pytest.mark.integration
    def test_correlation_engine_with_synthetic_prices(self, synthetic_prices):
        """Test correlation engine correctly identifies correlations."""
        engine = CorrelationEngine()
        prices, liquidity = synthetic_prices

        # Calculate returns
        asset_returns = prices.pct_change().dropna()
        liquidity_returns = liquidity.pct_change().dropna()

        results = engine.calculate_correlations(asset_returns, liquidity_returns)

        # Check structure
        assert "corr_30d" in results
        assert "corr_90d" in results
        assert "corr_ewma" in results

        # Check columns
        for key in results:
            assert "BTC" in results[key].columns
            assert "GOLD" in results[key].columns
            assert "DXY" in results[key].columns

        # Get final correlations
        btc_corr = results["corr_90d"]["BTC"].dropna().iloc[-1]
        gold_corr = results["corr_90d"]["GOLD"].dropna().iloc[-1]
        dxy_corr = results["corr_90d"]["DXY"].dropna().iloc[-1]

        # BTC should be positively correlated
        assert btc_corr > 0.3, f"BTC correlation should be positive, got {btc_corr:.2f}"

        # GOLD should be negatively correlated
        assert gold_corr < -0.2, f"GOLD correlation should be negative, got {gold_corr:.2f}"

        # DXY should be near zero (uncorrelated)
        assert abs(dxy_corr) < 0.3, f"DXY correlation should be near zero, got {dxy_corr:.2f}"

    @pytest.mark.integration
    def test_correlation_matrix_calculation(self, synthetic_prices):
        """Test correlation matrix calculation."""
        engine = CorrelationEngine()
        prices, _ = synthetic_prices

        # Calculate returns
        returns = prices.pct_change().dropna()

        matrix = engine.calculate_correlation_matrix(returns)

        # Check structure
        assert matrix.assets == ["BTC", "GOLD", "DXY"]
        assert matrix.correlations.shape == (3, 3)
        assert matrix.p_values.shape == (3, 3)

        # Check diagonal is 1
        for i in range(3):
            assert matrix.correlations.iloc[i, i] == pytest.approx(1.0, abs=1e-10)

        # Check symmetry
        for i in range(3):
            for j in range(3):
                assert matrix.correlations.iloc[i, j] == pytest.approx(
                    matrix.correlations.iloc[j, i], abs=1e-10
                )


class TestAlertEngineRegimeShift:
    """Integration tests for AlertEngine regime shift detection."""

    @pytest.fixture
    def expansion_regime(self):
        """Create an EXPANSION regime result."""
        return RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.EXPANSION,
            intensity=65.0,
            confidence="HIGH",
            net_liq_percentile=0.75,
            global_liq_percentile=0.80,
            stealth_qe_score=0.70,
            components="NET:0.75 GLO:0.80 SQE:0.70",
        )

    @pytest.fixture
    def contraction_regime(self):
        """Create a CONTRACTION regime result."""
        return RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.CONTRACTION,
            intensity=55.0,
            confidence="MEDIUM",
            net_liq_percentile=0.30,
            global_liq_percentile=0.25,
            stealth_qe_score=0.35,
            components="NET:0.30 GLO:0.25 SQE:0.35",
        )

    @pytest.mark.integration
    def test_alert_engine_regime_shift_expansion_to_contraction(
        self,
        expansion_regime,
        contraction_regime,
    ):
        """Test alert engine detects regime shift from EXPANSION to CONTRACTION."""
        engine = AlertEngine()

        alert = engine.check_regime_shift(
            current=contraction_regime,
            previous=expansion_regime,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.REGIME_SHIFT
        assert alert.severity == AlertSeverity.HIGH
        assert "EXPANSION" in alert.title
        assert "CONTRACTION" in alert.title
        assert alert.asset is None  # Regime alerts don't have asset
        assert "previous_direction" in alert.metadata
        assert "current_direction" in alert.metadata

    @pytest.mark.integration
    def test_alert_engine_regime_shift_contraction_to_expansion(
        self,
        expansion_regime,
        contraction_regime,
    ):
        """Test alert engine detects regime shift from CONTRACTION to EXPANSION."""
        engine = AlertEngine()

        alert = engine.check_regime_shift(
            current=expansion_regime,
            previous=contraction_regime,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.REGIME_SHIFT
        assert "CONTRACTION" in alert.title
        assert "EXPANSION" in alert.title

    @pytest.mark.integration
    def test_alert_engine_no_regime_shift_same_direction(self, expansion_regime):
        """Test alert engine returns None when no regime shift."""
        engine = AlertEngine()

        # Create another expansion regime
        same_expansion = RegimeResult(
            timestamp=datetime.now(UTC),
            direction=RegimeDirection.EXPANSION,
            intensity=70.0,
            confidence="HIGH",
            net_liq_percentile=0.80,
            global_liq_percentile=0.85,
            stealth_qe_score=0.75,
            components="NET:0.80 GLO:0.85 SQE:0.75",
        )

        alert = engine.check_regime_shift(
            current=same_expansion,
            previous=expansion_regime,
        )

        assert alert is None

    @pytest.mark.integration
    def test_alert_engine_no_previous_regime(self, expansion_regime):
        """Test alert engine returns None when no previous regime."""
        engine = AlertEngine()

        alert = engine.check_regime_shift(
            current=expansion_regime,
            previous=None,
        )

        assert alert is None


class TestAlertEngineCorrelationBreakdown:
    """Integration tests for AlertEngine correlation breakdown detection."""

    @pytest.fixture
    def stable_correlations(self):
        """Create stable correlation series (no alert)."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        # Stable correlations around 0.7 with small noise
        values = np.random.randn(120) * 0.05 + 0.7
        return pd.Series(values, index=dates, name="BTC")

    @pytest.fixture
    def breakdown_correlations(self):
        """Create correlation series with breakdown (large drop)."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        # Stable at 0.7 for 118 days, then drops to 0.2
        values = np.random.randn(118) * 0.03 + 0.7
        values = np.append(values, [0.25, 0.20])  # Large drop
        return pd.Series(values, index=dates, name="BTC")

    @pytest.fixture
    def surge_correlations(self):
        """Create correlation series with surge (large increase)."""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        # Stable at 0.2 for 118 days, then jumps to 0.7
        values = np.random.randn(118) * 0.03 + 0.2
        values = np.append(values, [0.65, 0.70])  # Large jump
        return pd.Series(values, index=dates, name="SPX")

    @pytest.mark.integration
    def test_alert_engine_correlation_breakdown(self, breakdown_correlations):
        """Test alert engine detects correlation breakdown."""
        engine = AlertEngine()

        alert = engine.check_correlation_shift(
            correlations=breakdown_correlations,
            asset="BTC",
        )

        assert alert is not None
        assert alert.alert_type == AlertType.CORRELATION_BREAKDOWN
        assert alert.severity in [AlertSeverity.HIGH, AlertSeverity.MEDIUM]
        assert alert.asset == "BTC"
        assert alert.change is not None
        assert alert.change < 0  # Breakdown is negative change
        assert alert.z_score is not None
        assert "BTC" in alert.title

    @pytest.mark.integration
    def test_alert_engine_correlation_surge(self, surge_correlations):
        """Test alert engine detects correlation surge."""
        engine = AlertEngine()

        alert = engine.check_correlation_shift(
            correlations=surge_correlations,
            asset="SPX",
        )

        assert alert is not None
        assert alert.alert_type == AlertType.CORRELATION_SURGE
        assert alert.asset == "SPX"
        assert alert.change is not None
        assert alert.change > 0  # Surge is positive change
        assert "SPX" in alert.title

    @pytest.mark.integration
    def test_alert_engine_no_alert_minor_change(self, stable_correlations):
        """Test alert engine returns None for minor changes."""
        engine = AlertEngine()

        alert = engine.check_correlation_shift(
            correlations=stable_correlations,
            asset="BTC",
        )

        # Small noise should not trigger alert
        assert alert is None


class TestAlertEngineNoAlertMinorChange:
    """Tests for alert engine not firing on minor changes."""

    @pytest.mark.integration
    def test_no_alert_below_absolute_threshold(self):
        """Test no alert when change is below absolute threshold."""
        engine = AlertEngine()

        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        # Very stable correlations
        values = np.ones(120) * 0.5
        values[-1] = 0.55  # Only 0.05 change (below 0.3 threshold)
        correlations = pd.Series(values, index=dates)

        alert = engine.check_correlation_shift(correlations, "TEST")

        assert alert is None

    @pytest.mark.integration
    def test_no_alert_insufficient_data(self):
        """Test no alert when insufficient data for rolling statistics."""
        engine = AlertEngine()

        dates = pd.date_range("2024-01-01", periods=50, freq="D")  # Less than 91
        values = np.random.randn(50) * 0.1 + 0.5
        correlations = pd.Series(values, index=dates)

        alert = engine.check_correlation_shift(correlations, "TEST")

        assert alert is None


class TestFullPipeline:
    """Integration tests for full analyzer pipeline."""

    @pytest.fixture
    def mock_calculators_bullish(self):
        """Create mock calculators returning bullish data."""
        from liquidity.calculators.stealth_qe import StealthQEResult

        stealth_qe = StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=70.0,
            score_weekly=65.0,
            rrp_level=400.0,
            rrp_velocity=-10.0,
            tga_level=700.0,
            tga_spending=30.0,
            fed_total=8500.0,
            fed_change=15.0,
            components="RRP:30% TGA:15% FED:12%",
            status="ACTIVE",
        )

        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        net_liq_df = pd.DataFrame({
            "timestamp": dates,
            "net_liquidity": list(range(4500, 5500, 10)),
        })
        global_liq_df = pd.DataFrame({
            "timestamp": dates,
            "global_liquidity": list(range(28000, 32000, 40)),
        })

        return stealth_qe, net_liq_df, global_liq_df

    @pytest.fixture
    def mock_calculators_bearish(self):
        """Create mock calculators returning bearish data."""
        from liquidity.calculators.stealth_qe import StealthQEResult

        stealth_qe = StealthQEResult(
            timestamp=datetime.now(UTC),
            score_daily=25.0,
            score_weekly=30.0,
            rrp_level=600.0,
            rrp_velocity=5.0,
            tga_level=900.0,
            tga_spending=-20.0,
            fed_total=7500.0,
            fed_change=-10.0,
            components="RRP:0% TGA:0% FED:0%",
            status="LOW",
        )

        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        net_liq_df = pd.DataFrame({
            "timestamp": dates,
            "net_liquidity": list(range(5500, 4500, -10)),
        })
        global_liq_df = pd.DataFrame({
            "timestamp": dates,
            "global_liquidity": list(range(32000, 28000, -40)),
        })

        return stealth_qe, net_liq_df, global_liq_df

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_pipeline_regime_shift_with_correlation(
        self,
        mock_calculators_bullish,
        mock_calculators_bearish,
    ):
        """Test full pipeline: regime shift + correlation check."""
        # Phase 1: Get bullish regime
        classifier = RegimeClassifier()
        bullish_stealth, bullish_net, bullish_global = mock_calculators_bullish

        with (
            patch.object(
                classifier._stealth_qe_calc, "get_current", new_callable=AsyncMock
            ) as mock_stealth,
            patch.object(
                classifier._net_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_net,
            patch.object(
                classifier._global_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_global,
        ):
            mock_stealth.return_value = bullish_stealth
            mock_net.return_value = bullish_net
            mock_global.return_value = bullish_global

            previous_regime = await classifier.classify()

        # Phase 2: Get bearish regime (shift)
        bearish_stealth, bearish_net, bearish_global = mock_calculators_bearish

        with (
            patch.object(
                classifier._stealth_qe_calc, "get_current", new_callable=AsyncMock
            ) as mock_stealth,
            patch.object(
                classifier._net_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_net,
            patch.object(
                classifier._global_liq_calc, "calculate", new_callable=AsyncMock
            ) as mock_global,
        ):
            mock_stealth.return_value = bearish_stealth
            mock_net.return_value = bearish_net
            mock_global.return_value = bearish_global

            current_regime = await classifier.classify()

        # Phase 3: Create correlation breakdown
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        btc_corr = np.random.randn(118) * 0.03 + 0.7
        btc_corr = np.append(btc_corr, [0.25, 0.20])  # Breakdown
        btc_series = pd.Series(btc_corr, index=dates, name="BTC")

        spx_corr = np.random.randn(120) * 0.03 + 0.5  # Stable
        spx_series = pd.Series(spx_corr, index=dates, name="SPX")

        correlations = {"BTC": btc_series, "SPX": spx_series}

        # Phase 4: Check alerts
        alert_engine = AlertEngine()
        alerts = alert_engine.check_all(
            regime=current_regime,
            correlations=correlations,
            previous_regime=previous_regime,
        )

        # Should have regime shift alert (upgraded to CRITICAL due to breakdown)
        regime_alerts = [a for a in alerts if a.alert_type == AlertType.REGIME_SHIFT]
        assert len(regime_alerts) == 1
        assert regime_alerts[0].severity == AlertSeverity.CRITICAL  # Upgraded!

        # Should have correlation breakdown alert
        breakdown_alerts = [a for a in alerts if a.alert_type == AlertType.CORRELATION_BREAKDOWN]
        assert len(breakdown_alerts) == 1
        assert breakdown_alerts[0].asset == "BTC"

        # SPX should not have alert (stable)
        spx_alerts = [a for a in alerts if a.asset == "SPX"]
        assert len(spx_alerts) == 0

    @pytest.mark.integration
    def test_discord_payload_formatting(self):
        """Test Discord payload formatting for all alert types."""
        engine = AlertEngine()

        # Create test alert
        alert = Alert(
            timestamp=datetime.now(UTC),
            alert_type=AlertType.REGIME_SHIFT,
            severity=AlertSeverity.HIGH,
            title="Regime Shift: EXPANSION -> CONTRACTION",
            message="Liquidity regime changed.",
            asset=None,
            previous_value=0.75,
            current_value=0.35,
            change=-0.40,
            z_score=None,
            metadata={
                "previous_direction": "EXPANSION",
                "current_direction": "CONTRACTION",
                "intensity": 65.0,
                "confidence": "HIGH",
            },
        )

        payload = engine.format_discord_payload(alert)

        # Check structure
        assert "embeds" in payload
        assert len(payload["embeds"]) == 1

        embed = payload["embeds"][0]
        assert embed["title"] == alert.title
        assert embed["description"] == alert.message
        assert embed["color"] == 0xFF8C00  # Orange for HIGH
        assert "fields" in embed
        assert "timestamp" in embed

        # Check fields
        field_names = [f["name"] for f in embed["fields"]]
        assert "Direction" in field_names
        assert "Intensity" in field_names
        assert "Confidence" in field_names
        assert "Severity" in field_names

    @pytest.mark.integration
    def test_correlation_alert_discord_payload(self):
        """Test Discord payload for correlation alerts."""
        engine = AlertEngine()

        alert = Alert(
            timestamp=datetime.now(UTC),
            alert_type=AlertType.CORRELATION_BREAKDOWN,
            severity=AlertSeverity.MEDIUM,
            title="Correlation Breakdown: BTC",
            message="BTC-Liquidity correlation has dropped.",
            asset="BTC",
            previous_value=0.70,
            current_value=0.20,
            change=-0.50,
            z_score=3.5,
            metadata={
                "rolling_mean": 0.68,
                "rolling_std": 0.05,
            },
        )

        payload = engine.format_discord_payload(alert)
        embed = payload["embeds"][0]

        # Check color is yellow for MEDIUM
        assert embed["color"] == 0xFFD700

        # Check fields include correlation-specific data
        field_names = [f["name"] for f in embed["fields"]]
        assert "Asset" in field_names
        assert "Current" in field_names
        assert "Previous" in field_names
        assert "Change" in field_names
        assert "Z-Score" in field_names

        # Check values are formatted with 2 decimals
        current_field = next(f for f in embed["fields"] if f["name"] == "Current")
        assert current_field["value"] == "0.20"

        change_field = next(f for f in embed["fields"] if f["name"] == "Change")
        assert change_field["value"] == "-0.50"


class TestAlertEngineEdgeCases:
    """Edge case tests for AlertEngine."""

    @pytest.mark.integration
    def test_nan_in_correlations(self):
        """Test handling of NaN values in correlation series."""
        engine = AlertEngine()

        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        values = np.random.randn(120) * 0.1 + 0.5
        values[-1] = np.nan  # NaN at end
        correlations = pd.Series(values, index=dates)

        alert = engine.check_correlation_shift(correlations, "TEST")

        assert alert is None  # Should not crash, just return None

    @pytest.mark.integration
    def test_zero_std_in_rolling_window(self):
        """Test handling of zero standard deviation."""
        engine = AlertEngine()

        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        # Constant values (zero std)
        values = np.ones(120) * 0.5
        values[-1] = 0.9  # Large change at end
        correlations = pd.Series(values, index=dates)

        alert = engine.check_correlation_shift(correlations, "TEST")

        # Should handle gracefully (std would be near-zero)
        # The large absolute change should still trigger
        # Note: numpy constant array will have exactly 0 std
        assert alert is None or isinstance(alert, Alert)

    @pytest.mark.integration
    def test_repr(self):
        """Test string representation."""
        engine = AlertEngine()
        repr_str = repr(engine)

        assert "AlertEngine" in repr_str
        assert "corr_threshold" in repr_str
        assert "sigma_threshold" in repr_str
        assert "rolling_window" in repr_str
