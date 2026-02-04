"""Message formatters for Discord embeds.

Creates rich Discord embeds for each alert type with appropriate colors,
fields, and formatting.
"""

from dataclasses import dataclass

from discord_webhook import DiscordEmbed


# Color constants (Discord hex format without #)
class AlertColors:
    """Color constants for alert embeds."""

    EXPANSION = 0x00FF88  # Green - favorable liquidity
    CONTRACTION = 0xFF4444  # Red - unfavorable liquidity
    STRESS_ELEVATED = 0xFFAA00  # Orange - elevated stress
    STRESS_CRITICAL = 0xFF4444  # Red - critical stress
    DXY_UP = 0x00AAFF  # Blue - USD strengthening
    DXY_DOWN = 0xFFAA00  # Orange - USD weakening
    CORRELATION = 0x9933FF  # Purple - correlation shift


@dataclass
class LiquidityMetrics:
    """Key liquidity metrics for regime change alerts.

    Attributes:
        net_liquidity: Net liquidity value in trillions USD.
        net_liquidity_change: Change from previous value in billions USD.
        global_liquidity: Global liquidity in trillions USD.
        global_liquidity_change: Change from previous value in billions USD.
        dxy: Current DXY value.
        dxy_change_pct: DXY change percentage.
    """

    net_liquidity: float
    net_liquidity_change: float = 0.0
    global_liquidity: float = 0.0
    global_liquidity_change: float = 0.0
    dxy: float = 0.0
    dxy_change_pct: float = 0.0


class AlertFormatter:
    """Format alerts into Discord embeds.

    Provides static methods for creating Discord embeds for each alert type
    with consistent styling and information.

    Example:
        embed = AlertFormatter.regime_change(
            previous="EXPANSION",
            current="CONTRACTION",
            prev_intensity=72,
            curr_intensity=35,
            confidence="HIGH",
            metrics=LiquidityMetrics(net_liquidity=5.8),
        )
    """

    @staticmethod
    def regime_change(
        previous: str,
        current: str,
        prev_intensity: float,
        curr_intensity: float,
        confidence: str,
        metrics: LiquidityMetrics | None = None,
    ) -> DiscordEmbed:
        """Format regime change alert.

        Args:
            previous: Previous regime (EXPANSION/CONTRACTION).
            current: Current regime.
            prev_intensity: Previous regime intensity (0-100).
            curr_intensity: Current regime intensity (0-100).
            confidence: Confidence level (HIGH/MEDIUM/LOW).
            metrics: Optional liquidity metrics to include.

        Returns:
            Formatted Discord embed.
        """
        color = AlertColors.EXPANSION if current == "EXPANSION" else AlertColors.CONTRACTION
        emoji = "\U0001f7e2" if current == "EXPANSION" else "\U0001f534"  # Green/Red circle

        embed = DiscordEmbed(
            title=f"{emoji} REGIME CHANGE: {current}",
            color=color,
        )

        # Add separator line effect using description
        embed.description = "\u2501" * 25  # Box drawing horizontal line

        # Previous/Current regime fields
        embed.add_embed_field(
            name="Previous",
            value=f"{previous} (intensity {prev_intensity:.0f})",
            inline=True,
        )
        embed.add_embed_field(
            name="Current",
            value=f"{current} (intensity {curr_intensity:.0f})",
            inline=True,
        )
        embed.add_embed_field(
            name="Confidence",
            value=confidence,
            inline=True,
        )

        # Key metrics if provided
        if metrics is not None:
            metrics_text = (
                f"\u2022 Net Liquidity: ${metrics.net_liquidity:.1f}T "
                f"({metrics.net_liquidity_change:+.0f}B)\n"
                f"\u2022 Global Liquidity: ${metrics.global_liquidity:.1f}T "
                f"({metrics.global_liquidity_change:+.0f}B)\n"
                f"\u2022 DXY: {metrics.dxy:.2f} ({metrics.dxy_change_pct:+.1f}%)"
            )
            embed.add_embed_field(
                name="Key Metrics",
                value=metrics_text,
                inline=False,
            )

        embed.set_timestamp()
        embed.set_footer(text="Liquidity Monitor")

        return embed

    @staticmethod
    def stress_breach(
        indicator: str,
        value: float,
        threshold: float,
        severity: str,
        unit: str = "bps",
    ) -> DiscordEmbed:
        """Format stress threshold breach alert.

        Args:
            indicator: Indicator name (e.g., "SOFR-OIS Spread").
            value: Current indicator value.
            threshold: Threshold that was breached.
            severity: Severity level (elevated/critical).
            unit: Unit of measurement (bps/percent).

        Returns:
            Formatted Discord embed.
        """
        is_critical = severity.lower() == "critical"
        color = AlertColors.STRESS_CRITICAL if is_critical else AlertColors.STRESS_ELEVATED
        emoji = "\U0001f6a8" if is_critical else "\u26a0\ufe0f"  # Siren or Warning

        embed = DiscordEmbed(
            title=f"{emoji} STRESS ALERT: {indicator}",
            color=color,
        )

        # Format value and threshold with appropriate unit
        if unit == "bps":
            value_str = f"{value:.1f} bps"
            threshold_str = f"{threshold:.1f} bps"
        elif unit == "percent":
            value_str = f"{value:.2f}%"
            threshold_str = f"{threshold:.2f}%"
        else:
            value_str = f"{value:.2f}"
            threshold_str = f"{threshold:.2f}"

        embed.add_embed_field(name="Current", value=value_str, inline=True)
        embed.add_embed_field(name="Threshold", value=threshold_str, inline=True)
        embed.add_embed_field(name="Severity", value=severity.upper(), inline=True)

        # Add interpretation
        if is_critical:
            embed.add_embed_field(
                name="Interpretation",
                value="\U0001f534 Funding stress detected - monitor closely",
                inline=False,
            )
        else:
            embed.add_embed_field(
                name="Interpretation",
                value="\U0001f7e1 Elevated stress - increased vigilance recommended",
                inline=False,
            )

        embed.set_timestamp()
        embed.set_footer(text="Liquidity Monitor")

        return embed

    @staticmethod
    def dxy_move(
        current: float,
        change_pct: float,
        previous: float | None = None,
    ) -> DiscordEmbed:
        """Format significant DXY move alert.

        Args:
            current: Current DXY value.
            change_pct: Percentage change.
            previous: Previous DXY value (optional).

        Returns:
            Formatted Discord embed.
        """
        direction = "up" if change_pct > 0 else "down"
        color = AlertColors.DXY_UP if direction == "up" else AlertColors.DXY_DOWN
        emoji = "\U0001f4c8" if direction == "up" else "\U0001f4c9"  # Chart up/down

        embed = DiscordEmbed(
            title=f"{emoji} DXY MOVE: {change_pct:+.2f}%",
            color=color,
        )

        embed.add_embed_field(name="DXY", value=f"{current:.2f}", inline=True)
        embed.add_embed_field(name="Change", value=f"{change_pct:+.2f}%", inline=True)

        if previous is not None:
            embed.add_embed_field(name="Previous", value=f"{previous:.2f}", inline=True)

        # Add market implication
        if direction == "up":
            implication = (
                "\U0001f4b5 USD strengthening (risk-off)\n"
                "\u2022 Potential headwind for risk assets\n"
                "\u2022 Dollar liquidity tightening"
            )
        else:
            implication = (
                "\U0001f4b5 USD weakening (risk-on)\n"
                "\u2022 Potential tailwind for risk assets\n"
                "\u2022 Dollar liquidity easing"
            )

        embed.add_embed_field(
            name="Market Implication",
            value=implication,
            inline=False,
        )

        embed.set_timestamp()
        embed.set_footer(text="Liquidity Monitor")

        return embed

    @staticmethod
    def correlation_shift(
        asset: str,
        previous: float,
        current: float,
        change: float,
        liquidity_metric: str = "Global Liquidity",
    ) -> DiscordEmbed:
        """Format correlation regime shift alert.

        Args:
            asset: Asset name (e.g., "BTC", "SPX").
            previous: Previous correlation value.
            current: Current correlation value.
            change: Change in correlation.
            liquidity_metric: Liquidity metric correlated with.

        Returns:
            Formatted Discord embed.
        """
        color = AlertColors.CORRELATION

        # Determine correlation direction change
        if previous >= 0 and current < 0:
            direction_change = "positive to negative"
        elif previous < 0 and current >= 0:
            direction_change = "negative to positive"
        elif abs(current) > abs(previous):
            direction_change = "strengthening"
        else:
            direction_change = "weakening"

        embed = DiscordEmbed(
            title=f"\U0001f504 CORRELATION SHIFT: {asset}",  # Counterclockwise arrows
            color=color,
        )

        embed.add_embed_field(name="Previous", value=f"{previous:.2f}", inline=True)
        embed.add_embed_field(name="Current", value=f"{current:.2f}", inline=True)
        embed.add_embed_field(name="Change", value=f"{change:+.2f}", inline=True)

        # Add interpretation
        if abs(current) > 0.5:
            strength = "Strong"
        elif abs(current) > 0.3:
            strength = "Moderate"
        else:
            strength = "Weak"

        direction = "positive" if current > 0 else "negative"

        interpretation = (
            f"\U0001f4ca {strength} {direction} correlation with {liquidity_metric}\n"
            f"\u2022 Correlation {direction_change}"
        )

        embed.add_embed_field(
            name="Interpretation",
            value=interpretation,
            inline=False,
        )

        embed.set_timestamp()
        embed.set_footer(text="Liquidity Monitor")

        return embed

    @staticmethod
    def custom_alert(
        title: str,
        message: str,
        color: int = 0x808080,
        fields: dict[str, str] | None = None,
    ) -> DiscordEmbed:
        """Create a custom alert embed.

        Args:
            title: Alert title.
            message: Alert message/description.
            color: Embed color (hex).
            fields: Optional dict of field name -> value pairs.

        Returns:
            Formatted Discord embed.
        """
        embed = DiscordEmbed(
            title=title,
            description=message,
            color=color,
        )

        if fields:
            for name, value in fields.items():
                embed.add_embed_field(name=name, value=value, inline=True)

        embed.set_timestamp()
        embed.set_footer(text="Liquidity Monitor")

        return embed
