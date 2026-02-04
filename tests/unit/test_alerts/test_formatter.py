"""Tests for alert formatters."""

from discord_webhook import DiscordEmbed

from liquidity.alerts.formatter import AlertColors, AlertFormatter, LiquidityMetrics


class TestAlertColors:
    """Tests for AlertColors constants."""

    def test_color_values(self) -> None:
        """Test that color constants are valid hex values."""
        assert AlertColors.EXPANSION == 0x00FF88
        assert AlertColors.CONTRACTION == 0xFF4444
        assert AlertColors.STRESS_ELEVATED == 0xFFAA00
        assert AlertColors.STRESS_CRITICAL == 0xFF4444
        assert AlertColors.DXY_UP == 0x00AAFF
        assert AlertColors.DXY_DOWN == 0xFFAA00
        assert AlertColors.CORRELATION == 0x9933FF


class TestLiquidityMetrics:
    """Tests for LiquidityMetrics dataclass."""

    def test_default_values(self) -> None:
        """Test default metrics values."""
        metrics = LiquidityMetrics(net_liquidity=5.8)

        assert metrics.net_liquidity == 5.8
        assert metrics.net_liquidity_change == 0.0
        assert metrics.global_liquidity == 0.0
        assert metrics.global_liquidity_change == 0.0
        assert metrics.dxy == 0.0
        assert metrics.dxy_change_pct == 0.0

    def test_full_metrics(self) -> None:
        """Test with all metrics provided."""
        metrics = LiquidityMetrics(
            net_liquidity=5.8,
            net_liquidity_change=-120,
            global_liquidity=28.2,
            global_liquidity_change=-450,
            dxy=104.5,
            dxy_change_pct=0.8,
        )

        assert metrics.net_liquidity == 5.8
        assert metrics.net_liquidity_change == -120
        assert metrics.global_liquidity == 28.2
        assert metrics.global_liquidity_change == -450
        assert metrics.dxy == 104.5
        assert metrics.dxy_change_pct == 0.8


class TestAlertFormatterRegimeChange:
    """Tests for regime change alert formatting."""

    def test_expansion_regime(self) -> None:
        """Test formatting expansion regime change."""
        embed = AlertFormatter.regime_change(
            previous="CONTRACTION",
            current="EXPANSION",
            prev_intensity=35,
            curr_intensity=72,
            confidence="HIGH",
        )

        assert isinstance(embed, DiscordEmbed)
        assert "EXPANSION" in embed.title
        assert embed.color == AlertColors.EXPANSION

    def test_contraction_regime(self) -> None:
        """Test formatting contraction regime change."""
        embed = AlertFormatter.regime_change(
            previous="EXPANSION",
            current="CONTRACTION",
            prev_intensity=72,
            curr_intensity=35,
            confidence="HIGH",
        )

        assert isinstance(embed, DiscordEmbed)
        assert "CONTRACTION" in embed.title
        assert embed.color == AlertColors.CONTRACTION

    def test_with_metrics(self) -> None:
        """Test formatting with liquidity metrics."""
        metrics = LiquidityMetrics(
            net_liquidity=5.8,
            net_liquidity_change=-120,
            global_liquidity=28.2,
            global_liquidity_change=-450,
            dxy=104.5,
            dxy_change_pct=0.8,
        )

        embed = AlertFormatter.regime_change(
            previous="EXPANSION",
            current="CONTRACTION",
            prev_intensity=72,
            curr_intensity=35,
            confidence="HIGH",
            metrics=metrics,
        )

        assert isinstance(embed, DiscordEmbed)
        # Check that fields were added
        assert len(embed.fields) >= 4  # Previous, Current, Confidence, Key Metrics

    def test_confidence_levels(self) -> None:
        """Test all confidence levels are accepted."""
        for confidence in ["HIGH", "MEDIUM", "LOW"]:
            embed = AlertFormatter.regime_change(
                previous="EXPANSION",
                current="CONTRACTION",
                prev_intensity=50,
                curr_intensity=50,
                confidence=confidence,
            )

            assert isinstance(embed, DiscordEmbed)


class TestAlertFormatterStressBreach:
    """Tests for stress breach alert formatting."""

    def test_elevated_severity(self) -> None:
        """Test formatting elevated stress alert."""
        embed = AlertFormatter.stress_breach(
            indicator="SOFR-OIS Spread",
            value=15.5,
            threshold=10.0,
            severity="elevated",
        )

        assert isinstance(embed, DiscordEmbed)
        assert "SOFR-OIS Spread" in embed.title
        assert embed.color == AlertColors.STRESS_ELEVATED

    def test_critical_severity(self) -> None:
        """Test formatting critical stress alert."""
        embed = AlertFormatter.stress_breach(
            indicator="SOFR-OIS Spread",
            value=30.0,
            threshold=25.0,
            severity="critical",
        )

        assert isinstance(embed, DiscordEmbed)
        assert embed.color == AlertColors.STRESS_CRITICAL

    def test_bps_unit(self) -> None:
        """Test formatting with basis points unit."""
        embed = AlertFormatter.stress_breach(
            indicator="SOFR-OIS",
            value=15.5,
            threshold=10.0,
            severity="elevated",
            unit="bps",
        )

        assert isinstance(embed, DiscordEmbed)
        # Check that fields contain "bps"
        field_values = [f["value"] for f in embed.fields if "value" in f]
        assert any("bps" in str(v) for v in field_values)

    def test_percent_unit(self) -> None:
        """Test formatting with percent unit."""
        embed = AlertFormatter.stress_breach(
            indicator="Repo Stress",
            value=3.5,
            threshold=3.0,
            severity="critical",
            unit="percent",
        )

        assert isinstance(embed, DiscordEmbed)
        field_values = [f["value"] for f in embed.fields if "value" in f]
        assert any("%" in str(v) for v in field_values)


class TestAlertFormatterDxyMove:
    """Tests for DXY move alert formatting."""

    def test_dxy_up_move(self) -> None:
        """Test formatting DXY upward move."""
        embed = AlertFormatter.dxy_move(
            current=105.5,
            change_pct=1.5,
        )

        assert isinstance(embed, DiscordEmbed)
        assert "+1.50%" in embed.title
        assert embed.color == AlertColors.DXY_UP

    def test_dxy_down_move(self) -> None:
        """Test formatting DXY downward move."""
        embed = AlertFormatter.dxy_move(
            current=103.0,
            change_pct=-1.2,
        )

        assert isinstance(embed, DiscordEmbed)
        assert "-1.20%" in embed.title
        assert embed.color == AlertColors.DXY_DOWN

    def test_with_previous_value(self) -> None:
        """Test formatting with previous value."""
        embed = AlertFormatter.dxy_move(
            current=105.5,
            change_pct=1.5,
            previous=104.0,
        )

        assert isinstance(embed, DiscordEmbed)
        # Check Previous field is present
        field_names = [f["name"] for f in embed.fields if "name" in f]
        assert "Previous" in field_names


class TestAlertFormatterCorrelationShift:
    """Tests for correlation shift alert formatting."""

    def test_correlation_shift(self) -> None:
        """Test formatting correlation shift alert."""
        embed = AlertFormatter.correlation_shift(
            asset="BTC",
            previous=0.5,
            current=0.2,
            change=-0.3,
        )

        assert isinstance(embed, DiscordEmbed)
        assert "BTC" in embed.title
        assert embed.color == AlertColors.CORRELATION

    def test_positive_to_negative_shift(self) -> None:
        """Test formatting positive to negative correlation shift."""
        embed = AlertFormatter.correlation_shift(
            asset="SPX",
            previous=0.3,
            current=-0.2,
            change=-0.5,
        )

        assert isinstance(embed, DiscordEmbed)

    def test_custom_liquidity_metric(self) -> None:
        """Test formatting with custom liquidity metric name."""
        embed = AlertFormatter.correlation_shift(
            asset="GOLD",
            previous=0.1,
            current=0.5,
            change=0.4,
            liquidity_metric="Net Liquidity",
        )

        assert isinstance(embed, DiscordEmbed)


class TestAlertFormatterCustomAlert:
    """Tests for custom alert formatting."""

    def test_basic_custom_alert(self) -> None:
        """Test formatting basic custom alert."""
        embed = AlertFormatter.custom_alert(
            title="Custom Alert",
            message="This is a test message",
        )

        assert isinstance(embed, DiscordEmbed)
        assert embed.title == "Custom Alert"
        assert embed.description == "This is a test message"

    def test_custom_alert_with_color(self) -> None:
        """Test formatting custom alert with color."""
        embed = AlertFormatter.custom_alert(
            title="Custom Alert",
            message="Test",
            color=0xFF0000,
        )

        assert isinstance(embed, DiscordEmbed)
        assert embed.color == 0xFF0000

    def test_custom_alert_with_fields(self) -> None:
        """Test formatting custom alert with fields."""
        embed = AlertFormatter.custom_alert(
            title="Custom Alert",
            message="Test",
            fields={"Field1": "Value1", "Field2": "Value2"},
        )

        assert isinstance(embed, DiscordEmbed)
        assert len(embed.fields) == 2
