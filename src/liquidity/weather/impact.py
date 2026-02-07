"""Oil production impact assessment for Gulf of Mexico storms.

Estimates production disruptions based on storm characteristics and
historical evacuation patterns.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .noaa import ActiveStorm, StormCategory

logger = logging.getLogger(__name__)


class ImpactSeverity(Enum):
    """Severity levels for oil production impact."""

    MINIMAL = "minimal"  # < 5% production affected
    LOW = "low"  # 5-15% production affected
    MODERATE = "moderate"  # 15-30% production affected
    HIGH = "high"  # 30-50% production affected
    SEVERE = "severe"  # > 50% production affected


@dataclass
class OilProductionImpact:
    """Estimated oil production impact from a tropical system.

    Attributes:
        storm_id: NHC storm identifier
        storm_name: Storm name
        severity: Impact severity level
        estimated_shut_in_pct: Estimated percentage of GOM production shut in
        estimated_shut_in_bpd: Estimated barrels per day shut in
        platforms_at_risk: Estimated number of platforms at risk
        evacuation_likely: Whether platform evacuations are likely
        recovery_days: Estimated days to full recovery after storm passes
        assessment_time: When this assessment was made
        notes: Additional context or caveats
    """

    storm_id: str
    storm_name: str
    severity: ImpactSeverity
    estimated_shut_in_pct: float
    estimated_shut_in_bpd: int
    platforms_at_risk: int
    evacuation_likely: bool
    recovery_days: int
    assessment_time: datetime
    notes: str = ""

    @property
    def is_significant(self) -> bool:
        """Check if impact is significant (>15% production affected)."""
        return self.severity in [
            ImpactSeverity.MODERATE,
            ImpactSeverity.HIGH,
            ImpactSeverity.SEVERE,
        ]


# Gulf of Mexico production constants (approximate 2024-2026 values)
GOM_TOTAL_PRODUCTION_BPD = 1_800_000  # ~1.8 million bpd
GOM_PLATFORM_COUNT = 1800  # Active platforms (includes unmanned)
GOM_DEEPWATER_PCT = 0.97  # 97% of production from deepwater


def assess_gom_impact(storm: ActiveStorm) -> OilProductionImpact:
    """Assess Gulf of Mexico oil production impact from a storm.

    Uses storm characteristics and location to estimate production disruption.
    Based on historical evacuation patterns and BSEE shut-in data.

    Args:
        storm: ActiveStorm object with current storm data

    Returns:
        OilProductionImpact with estimated production effects

    Note:
        This is a simplified model. Actual impacts depend on:
        - Exact storm track (not just current position)
        - Time of year (peak production periods)
        - Current platform staffing levels
        - Operator-specific evacuation policies
        - Storm speed (slower = more damage)
    """
    notes_parts = []

    # Base impact factors
    shut_in_pct = 0.0
    platforms_at_risk = 0
    evacuation_likely = False
    recovery_days = 0

    # Factor 1: Storm intensity
    intensity_factor = _get_intensity_factor(storm.category)
    shut_in_pct += intensity_factor

    if storm.is_major:
        notes_parts.append("Major hurricane (Cat 3+) - expect significant evacuations")
        evacuation_likely = True

    # Factor 2: Location within GOM
    if storm.threatens_gom:
        location_factor = _get_location_factor(storm.lat, storm.lon)
        shut_in_pct *= (1 + location_factor)
        notes_parts.append(f"Currently in GOM at {storm.lat:.1f}N, {abs(storm.lon):.1f}W")
    else:
        # Approaching storm - reduced impact
        distance = storm.gom_proximity_km
        if distance is not None:
            if distance < 500:
                shut_in_pct *= 0.5
                notes_parts.append(f"Approaching GOM, ~{distance:.0f}km away")
            else:
                shut_in_pct *= 0.2
                notes_parts.append(f"Distant from GOM, ~{distance:.0f}km away")
        else:
            shut_in_pct *= 0.1

    # Factor 3: Storm pressure (lower = stronger = more impact)
    if storm.pressure_mb > 0:
        if storm.pressure_mb < 950:
            shut_in_pct *= 1.3
            notes_parts.append(f"Very low pressure ({storm.pressure_mb}mb) - intense system")
        elif storm.pressure_mb < 970:
            shut_in_pct *= 1.1

    # Clamp shut-in percentage
    shut_in_pct = min(max(shut_in_pct, 0.0), 100.0)

    # Calculate derived values
    estimated_shut_in_bpd = int(GOM_TOTAL_PRODUCTION_BPD * shut_in_pct / 100)
    platforms_at_risk = int(GOM_PLATFORM_COUNT * (shut_in_pct / 100) * 0.8)

    # Evacuation threshold: any named storm with >10% shut-in
    if shut_in_pct > 10 and storm.category != StormCategory.TD:
        evacuation_likely = True

    # Recovery time estimation
    recovery_days = _estimate_recovery_days(storm.category, shut_in_pct)

    # Determine severity level
    severity = _determine_severity(shut_in_pct)

    return OilProductionImpact(
        storm_id=storm.id,
        storm_name=storm.name,
        severity=severity,
        estimated_shut_in_pct=round(shut_in_pct, 1),
        estimated_shut_in_bpd=estimated_shut_in_bpd,
        platforms_at_risk=platforms_at_risk,
        evacuation_likely=evacuation_likely,
        recovery_days=recovery_days,
        assessment_time=datetime.utcnow(),
        notes="; ".join(notes_parts) if notes_parts else "Standard assessment",
    )


def _get_intensity_factor(category: StormCategory) -> float:
    """Get base shut-in percentage factor based on storm category.

    Based on historical BSEE shut-in data for storms crossing central GOM.
    """
    factors = {
        StormCategory.TD: 5.0,  # Precautionary evacuations only
        StormCategory.TS: 15.0,  # Partial evacuations common
        StormCategory.CAT1: 30.0,  # Significant evacuations
        StormCategory.CAT2: 45.0,  # Major evacuations
        StormCategory.CAT3: 65.0,  # Near-complete evacuation
        StormCategory.CAT4: 85.0,  # Complete evacuation likely
        StormCategory.CAT5: 95.0,  # Total evacuation
    }
    return factors.get(category, 10.0)


def _get_location_factor(lat: float, lon: float) -> float:
    """Get location multiplier based on position in GOM.

    Central GOM (where most deepwater production is) = higher factor.
    Eastern/Western edges = lower factor.
    """
    # Central GOM production area roughly: 26-29N, 87-93W
    central_lat = 27.5
    central_lon = -90.0

    # Distance from production center
    lat_offset = abs(lat - central_lat)
    lon_offset = abs(lon - central_lon)

    # Maximum factor of 0.5 if directly in central production area
    # Decreases with distance
    max_factor = 0.5
    decay = 0.05  # Factor reduction per degree

    factor = max_factor - (lat_offset + lon_offset) * decay
    return max(factor, 0.0)


def _estimate_recovery_days(category: StormCategory, shut_in_pct: float) -> int:
    """Estimate days to full production recovery after storm passes.

    Based on historical recovery patterns from major GOM storms.
    """
    if shut_in_pct < 5:
        return 0

    base_days = {
        StormCategory.TD: 1,
        StormCategory.TS: 2,
        StormCategory.CAT1: 4,
        StormCategory.CAT2: 7,
        StormCategory.CAT3: 14,
        StormCategory.CAT4: 21,
        StormCategory.CAT5: 30,
    }

    base = base_days.get(category, 3)

    # Higher shut-in = longer recovery
    if shut_in_pct > 50:
        base = int(base * 1.5)
    elif shut_in_pct > 75:
        base = int(base * 2.0)

    return base


def _determine_severity(shut_in_pct: float) -> ImpactSeverity:
    """Determine severity level from shut-in percentage."""
    if shut_in_pct < 5:
        return ImpactSeverity.MINIMAL
    elif shut_in_pct < 15:
        return ImpactSeverity.LOW
    elif shut_in_pct < 30:
        return ImpactSeverity.MODERATE
    elif shut_in_pct < 50:
        return ImpactSeverity.HIGH
    else:
        return ImpactSeverity.SEVERE


def format_impact_summary(impact: OilProductionImpact) -> str:
    """Format impact assessment as human-readable summary.

    Args:
        impact: OilProductionImpact to format

    Returns:
        Formatted multi-line summary string
    """
    lines = [
        f"=== GOM Impact Assessment: {impact.storm_name} ({impact.storm_id}) ===",
        f"Severity: {impact.severity.value.upper()}",
        f"Estimated Production Shut-In: {impact.estimated_shut_in_pct:.1f}% ({impact.estimated_shut_in_bpd:,} bpd)",
        f"Platforms at Risk: ~{impact.platforms_at_risk}",
        f"Evacuations Likely: {'Yes' if impact.evacuation_likely else 'No'}",
        f"Est. Recovery Time: {impact.recovery_days} days after passing",
        f"Assessment Time: {impact.assessment_time.strftime('%Y-%m-%d %H:%M UTC')}",
    ]

    if impact.notes:
        lines.append(f"Notes: {impact.notes}")

    return "\n".join(lines)
