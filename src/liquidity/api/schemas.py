"""Pydantic response models for the Liquidity API.

Defines the response schemas for all API endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class APIMetadata(BaseModel):
    """Metadata included in all API responses."""

    timestamp: datetime = Field(description="Response generation timestamp")
    source: str = Field(default="spongebb", description="Data source identifier")
    version: str = Field(default="1.0.0", description="API version")


class NetLiquidityResponse(BaseModel):
    """Response model for /liquidity/net endpoint.

    Contains the Hayes Net Liquidity Index: WALCL - TGA - RRP
    All values in billions USD.
    """

    value: float = Field(description="Net Liquidity value in billions USD")
    walcl: float = Field(description="Fed Total Assets in billions USD")
    tga: float = Field(description="Treasury General Account in billions USD")
    rrp: float = Field(description="Reverse Repo in billions USD")
    weekly_delta: float = Field(description="Change over past 7 days in billions USD")
    sentiment: str = Field(description="Liquidity sentiment: BULLISH, NEUTRAL, or BEARISH")
    as_of_date: datetime = Field(description="Data timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


class GlobalLiquidityComponent(BaseModel):
    """Individual central bank component of global liquidity."""

    fed_usd: float = Field(description="Fed Net Liquidity in billions USD")
    ecb_usd: float = Field(description="ECB total assets in billions USD")
    boj_usd: float = Field(description="BoJ total assets in billions USD")
    pboc_usd: float = Field(description="PBoC total assets in billions USD")
    boe_usd: float | None = Field(default=None, description="BoE total assets (Tier 2)")
    snb_usd: float | None = Field(default=None, description="SNB total assets (Tier 2)")
    boc_usd: float | None = Field(default=None, description="BoC total assets (Tier 2)")


class GlobalLiquidityResponse(BaseModel):
    """Response model for /liquidity/global endpoint.

    Contains aggregated global liquidity from major central banks.
    All values in billions USD.
    """

    value: float = Field(description="Total Global Liquidity in billions USD")
    components: GlobalLiquidityComponent = Field(description="Individual CB contributions")
    weekly_delta: float = Field(description="Change over past 7 days in billions USD")
    coverage_pct: float = Field(description="Percentage of global CB assets covered")
    as_of_date: datetime = Field(description="Data timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


class RegimeResponse(BaseModel):
    """Response model for /regime/current endpoint.

    Binary regime classification: EXPANSION or CONTRACTION.
    """

    regime: str = Field(description="Regime direction: EXPANSION or CONTRACTION")
    intensity: float = Field(ge=0, le=100, description="Signal strength (0-100)")
    confidence: str = Field(description="Confidence level: HIGH, MEDIUM, or LOW")
    components: str = Field(description="Component contributions string")
    as_of_date: datetime = Field(description="Classification timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


class CombinedRegimeResponse(BaseModel):
    """Response model for /regime/combined endpoint.

    Combined liquidity-oil regime classification for macro signals.
    """

    liquidity_regime: str = Field(description="Liquidity regime: EXPANSION or CONTRACTION")
    oil_regime: str = Field(description="Oil supply-demand regime: TIGHT, BALANCED, or LOOSE")
    combined_regime: str = Field(
        description="Combined regime: very_bullish, bullish, neutral, bearish, very_bearish"
    )
    confidence: float = Field(ge=0, le=1, description="Combined confidence score (0-1)")
    commodity_signal: str = Field(description="Trading signal: long, short, or neutral")
    drivers: list[str] = Field(description="Factors driving the current regime")
    as_of_date: datetime = Field(description="Classification timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


class StealthQEResponse(BaseModel):
    """Response model for /metrics/stealth-qe endpoint.

    Detects hidden liquidity injections via RRP, TGA, and Fed changes.
    """

    score: float = Field(ge=0, le=100, description="Stealth QE score (0-100)")
    status: str = Field(
        description="Activity level: VERY_ACTIVE, ACTIVE, MODERATE, LOW, MINIMAL"
    )
    rrp_level: float = Field(description="Current RRP in billions USD")
    rrp_velocity: float | None = Field(description="RRP weekly % change (negative=bullish)")
    tga_level: float = Field(description="Current TGA in billions USD")
    tga_spending: float | None = Field(description="TGA weekly spending in billions USD")
    fed_total: float = Field(description="Fed total assets in billions USD")
    fed_change: float | None = Field(description="Fed weekly change in billions USD")
    components: str = Field(description="Component contribution string")
    as_of_date: datetime = Field(description="Data timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


class HealthResponse(BaseModel):
    """Response model for /health endpoint."""

    status: str = Field(description="Service health status")
    questdb_connected: bool = Field(description="QuestDB connection status")
    version: str = Field(default="1.0.0", description="API version")


class ErrorResponse(BaseModel):
    """Response model for error responses."""

    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    detail: str | None = Field(default=None, description="Additional error details")


# =============================================================================
# FX Schemas
# =============================================================================


class DXYDataPoint(BaseModel):
    """Single DXY data point."""

    timestamp: str = Field(description="Timestamp in ISO format")
    value: float = Field(description="DXY index value")


class DXYResponse(BaseModel):
    """Response model for /fx/dxy endpoint.

    Contains DXY index with current value and recent history.
    """

    current: float = Field(description="Current DXY index value")
    change_1d: float | None = Field(description="1-day % change")
    change_1w: float | None = Field(description="1-week % change")
    data: list[DXYDataPoint] = Field(description="Recent historical data points")
    as_of_date: datetime = Field(description="Data timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


class FXPairData(BaseModel):
    """Data for a single FX pair."""

    current: float = Field(description="Current exchange rate")
    change_1d: float | None = Field(description="1-day % change")


class FXPairsResponse(BaseModel):
    """Response model for /fx/pairs endpoint.

    Contains major FX pairs vs USD.
    """

    pairs: dict[str, FXPairData] = Field(description="FX pair data keyed by pair name")
    as_of_date: datetime = Field(description="Data timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


# =============================================================================
# Stress Indicators Schemas
# =============================================================================


class StressIndicatorsResponse(BaseModel):
    """Response model for /stress/indicators endpoint.

    Contains funding market stress metrics.
    """

    sofr_ois_spread: float | None = Field(
        description="SOFR-OIS spread in basis points (normal: 0-10, stress: >25)"
    )
    sofr_percentile: int | None = Field(
        description="SOFR spread percentile vs 60-day history (0-100)"
    )
    repo_stress: str = Field(
        description="Repo stress level: low, medium, high, unknown"
    )
    cp_spread: float | None = Field(
        description="CP-Treasury spread in basis points (normal: 20-40, stress: >100)"
    )
    sofr_width: float | None = Field(
        description="SOFR distribution width (99th-1st percentile) in bps"
    )
    repo_ratio: float | None = Field(
        description="Repo stress ratio: RRP as % of Fed balance sheet"
    )
    overall_stress: str = Field(
        description="Overall stress regime: normal, elevated, critical"
    )
    as_of_date: datetime = Field(description="Data timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


# =============================================================================
# Correlation Schemas
# =============================================================================


class AssetCorrelation(BaseModel):
    """Correlation data for a single asset."""

    value: float | None = Field(description="Correlation coefficient (-1 to 1)")
    p_value: float | None = Field(description="Statistical significance p-value")


class CorrelationResponse(BaseModel):
    """Response model for /correlations endpoint.

    Contains asset vs net liquidity correlations.
    """

    window: str = Field(description="Correlation window (30d or 90d)")
    correlations: dict[str, AssetCorrelation] = Field(
        description="Per-asset correlations with liquidity"
    )
    as_of_date: datetime = Field(description="Calculation timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


class CorrelationMatrixResponse(BaseModel):
    """Response model for /correlations/matrix endpoint.

    Contains full cross-asset correlation matrix.
    """

    assets: list[str] = Field(description="List of asset names in matrix order")
    matrix: dict[str, dict[str, float | None]] = Field(
        description="Correlation matrix as nested dict [row][col]"
    )
    as_of_date: datetime = Field(description="Calculation timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


# =============================================================================
# Calendar Schemas
# =============================================================================


class CalendarEventData(BaseModel):
    """Single calendar event."""

    date: str = Field(description="Event date in ISO format (YYYY-MM-DD)")
    event_type: str = Field(description="Event type (treasury_auction, fed_meeting, etc.)")
    title: str = Field(description="Event title")
    description: str | None = Field(default=None, description="Event description")
    settlement_date: str | None = Field(
        default=None, description="Settlement date for auctions (T+1/T+2)"
    )
    impact: str = Field(description="Impact level: low, medium, high")


class CalendarEventsResponse(BaseModel):
    """Response model for /calendar/events endpoint.

    Contains calendar events within a date range.
    """

    start: str = Field(description="Start date of range (YYYY-MM-DD)")
    end: str = Field(description="End date of range (YYYY-MM-DD)")
    count: int = Field(description="Number of events returned")
    events: list[CalendarEventData] = Field(description="List of calendar events")
    metadata: APIMetadata = Field(description="Response metadata")


class MOVEZScoreResponse(BaseModel):
    """Response model for /volatility/move-zscore endpoint."""

    current_move: float = Field(description="Current MOVE index value")
    mean_move: float = Field(description="Rolling 20-day mean")
    std_move: float = Field(description="Rolling 20-day standard deviation")
    zscore: float = Field(description="Z-Score value")
    percentile: float = Field(ge=0, le=100, description="Percentile rank (0-100)")
    signal: str = Field(
        description="Signal: EXTREME_HIGH, HIGH, NORMAL, LOW, EXTREME_LOW"
    )
    as_of_date: datetime = Field(description="Data timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


class VIXTermStructureResponse(BaseModel):
    """Response model for /volatility/vix-term-structure endpoint."""

    vix: float = Field(description="Current VIX value")
    vix3m: float = Field(description="Current VIX3M value")
    ratio: float = Field(description="VIX/VIX3M ratio")
    spread: float = Field(description="VIX - VIX3M absolute spread")
    structure: str = Field(description="Term structure: CONTANGO, FLAT, BACKWARDATION")
    as_of_date: datetime = Field(description="Data timestamp")
    metadata: APIMetadata = Field(description="Response metadata")


class VolatilitySignalResponse(BaseModel):
    """Response model for /volatility/signal endpoint."""

    composite_score: float = Field(
        ge=-100, le=100, description="Composite volatility score (-100 to +100)"
    )
    regime: str = Field(description="Volatility regime: RISK_ON, NEUTRAL, RISK_OFF")
    move_zscore: float = Field(description="MOVE Z-Score value")
    move_signal: str = Field(description="MOVE signal classification")
    vix: float = Field(description="Current VIX value")
    vix3m: float = Field(description="Current VIX3M value")
    vix_ratio: float = Field(description="VIX/VIX3M ratio")
    vix_structure: str = Field(description="VIX term structure classification")
    move_component: float = Field(description="MOVE contribution to composite score")
    term_component: float = Field(description="VIX term contribution to composite score")
    level_component: float = Field(description="VIX level contribution to composite score")
    as_of_date: datetime = Field(description="Data timestamp")
    metadata: APIMetadata = Field(description="Response metadata")
