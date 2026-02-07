"""NOAA Hurricane Tracker for Gulf of Mexico oil production impact.

Tracks active storms from the National Hurricane Center (NHC) RSS feed
to assess potential disruptions to Gulf of Mexico oil production.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
import logging
import re

import httpx
import feedparser

logger = logging.getLogger(__name__)


class StormCategory(Enum):
    """Saffir-Simpson Hurricane Wind Scale categories."""

    TD = "Tropical Depression"
    TS = "Tropical Storm"
    CAT1 = "Category 1"
    CAT2 = "Category 2"
    CAT3 = "Category 3"
    CAT4 = "Category 4"
    CAT5 = "Category 5"

    @classmethod
    def from_wind_speed(cls, max_wind_mph: int) -> "StormCategory":
        """Determine category from maximum sustained wind speed (mph)."""
        if max_wind_mph < 39:
            return cls.TD
        elif max_wind_mph < 74:
            return cls.TS
        elif max_wind_mph < 96:
            return cls.CAT1
        elif max_wind_mph < 111:
            return cls.CAT2
        elif max_wind_mph < 130:
            return cls.CAT3
        elif max_wind_mph < 157:
            return cls.CAT4
        else:
            return cls.CAT5


@dataclass
class ActiveStorm:
    """Active tropical cyclone data from NHC.

    Attributes:
        id: Storm identifier (e.g., "AL012026" for first Atlantic storm of 2026)
        name: Storm name (e.g., "Alberto")
        category: Current Saffir-Simpson category
        lat: Current latitude (decimal degrees, positive = North)
        lon: Current longitude (decimal degrees, negative = West)
        max_wind_mph: Maximum sustained wind speed in mph
        movement: Movement direction and speed (e.g., "NW at 12 mph")
        pressure_mb: Central pressure in millibars
        forecast_track: List of forecast points with lat, lon, time, wind
        last_updated: Timestamp of last NHC advisory
    """

    id: str
    name: str
    category: StormCategory
    lat: float
    lon: float
    max_wind_mph: int
    movement: str
    pressure_mb: int
    forecast_track: List[dict] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_major(self) -> bool:
        """Check if this is a major hurricane (Category 3+).

        Major hurricanes cause significantly more damage and are more likely
        to force offshore platform evacuations.
        """
        return self.category in [
            StormCategory.CAT3,
            StormCategory.CAT4,
            StormCategory.CAT5,
        ]

    @property
    def threatens_gom(self) -> bool:
        """Check if storm is in or near Gulf of Mexico region.

        GOM bounding box: 18-31 degrees N, 80-98 degrees W.
        This encompasses the main oil production areas including:
        - Deepwater Gulf (central)
        - Shelf areas (western and eastern Gulf)
        - Key approach corridors
        """
        in_lat_range = 18 <= self.lat <= 31
        # Longitude is negative for Western Hemisphere
        in_lon_range = -98 <= self.lon <= -80
        return in_lat_range and in_lon_range

    @property
    def gom_proximity_km(self) -> Optional[float]:
        """Approximate distance to GOM center if outside the box.

        Returns None if already in GOM, otherwise approximate km to center.
        GOM center is approximately 25.5N, 90W.
        """
        if self.threatens_gom:
            return None

        # Simple haversine approximation
        import math

        gom_center_lat = 25.5
        gom_center_lon = -90.0

        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2, lon2 = math.radians(gom_center_lat), math.radians(gom_center_lon)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Earth radius in km

        return r * c


class NOAAHurricaneTracker:
    """Fetches active storm data from National Hurricane Center.

    Uses NHC's Atlantic basin RSS feed to get current storm advisories.
    """

    NHC_RSS_URL = "https://www.nhc.noaa.gov/index-at.xml"
    NHC_GIS_URL = "https://www.nhc.noaa.gov/gis/"

    def __init__(self, timeout: float = 30.0):
        """Initialize tracker.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "OpenBB-Liquidity-Monitor/1.0 (weather-impact-tracker)"
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def get_active_storms(self) -> List[ActiveStorm]:
        """Fetch active storms from NHC RSS feed.

        Returns:
            List of ActiveStorm objects. Empty list if no active storms.

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        try:
            response = await client.get(self.NHC_RSS_URL)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch NHC RSS: {e}")
            raise

        feed = feedparser.parse(response.text)
        storms = []
        seen_storm_ids = set()

        for entry in feed.entries:
            storm = self._parse_entry(entry)
            if storm and storm.id not in seen_storm_ids:
                storms.append(storm)
                seen_storm_ids.add(storm.id)

        logger.info(f"Found {len(storms)} active storms")
        return storms

    def _parse_entry(self, entry: dict) -> Optional[ActiveStorm]:
        """Parse RSS entry into ActiveStorm if it contains storm data.

        Args:
            entry: feedparser entry dict

        Returns:
            ActiveStorm if entry is a storm advisory, None otherwise
        """
        title = entry.get("title", "")
        summary = entry.get("summary", "")

        # Look for storm advisories (skip general summaries)
        if not any(
            x in title.lower()
            for x in ["advisory", "tropical storm", "hurricane", "depression"]
        ):
            return None

        # Extract storm ID from link
        link = entry.get("link", "")
        storm_id = self._extract_storm_id(link)
        if not storm_id:
            return None

        # Extract name from title
        name = self._extract_storm_name(title)

        # Parse coordinates and wind from summary
        lat, lon = self._extract_coordinates(summary)
        max_wind = self._extract_max_wind(summary)
        pressure = self._extract_pressure(summary)
        movement = self._extract_movement(summary)

        if lat is None or lon is None or max_wind is None:
            logger.debug(f"Could not parse storm data from: {title}")
            return None

        category = StormCategory.from_wind_speed(max_wind)

        # Parse timestamp
        published = entry.get("published_parsed")
        if published:
            last_updated = datetime(*published[:6])
        else:
            last_updated = datetime.utcnow()

        return ActiveStorm(
            id=storm_id,
            name=name or "Unknown",
            category=category,
            lat=lat,
            lon=lon,
            max_wind_mph=max_wind,
            movement=movement or "Unknown",
            pressure_mb=pressure or 0,
            forecast_track=[],
            last_updated=last_updated,
        )

    def _extract_storm_id(self, link: str) -> Optional[str]:
        """Extract storm ID from NHC link.

        Example link: https://www.nhc.noaa.gov/text/refresh/MIATCPAT1+shtml/...
        Storm ID would be AL012026 format.
        """
        # Pattern for Atlantic (AT) or Eastern Pacific (EP) storm number
        match = re.search(r"(AL|EP|CP)(\d{2})(\d{4})", link)
        if match:
            return match.group(0)

        # Alternative: extract from path like MIATCPAT1
        match = re.search(r"MIATCP(AT|EP)(\d+)", link)
        if match:
            basin = "AL" if match.group(1) == "AT" else match.group(1)
            num = match.group(2).zfill(2)
            year = datetime.utcnow().year
            return f"{basin}{num}{year}"

        return None

    def _extract_storm_name(self, title: str) -> Optional[str]:
        """Extract storm name from title.

        Examples:
        - "Hurricane Alberto Advisory Number 15"
        - "Tropical Storm Beta Intermediate Advisory"
        - "Tropical Depression Three Advisory"
        """
        patterns = [
            r"Hurricane\s+(\w+)",
            r"Tropical Storm\s+(\w+)",
            r"Tropical Depression\s+(\w+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                name = match.group(1)
                # Skip if it's "Advisory" or a number word
                if name.lower() not in ["advisory", "intermediate"]:
                    return name

        return None

    def _extract_coordinates(self, text: str) -> tuple[Optional[float], Optional[float]]:
        """Extract latitude and longitude from advisory text.

        Examples:
        - "LOCATION...25.5N 90.0W"
        - "located near 25.5 North, 90.0 West"
        """
        # Pattern for "25.5N 90.0W" format
        match = re.search(
            r"(\d+\.?\d*)\s*([NS])\s+(\d+\.?\d*)\s*([EW])", text, re.IGNORECASE
        )
        if match:
            lat = float(match.group(1))
            if match.group(2).upper() == "S":
                lat = -lat

            lon = float(match.group(3))
            if match.group(4).upper() == "W":
                lon = -lon

            return lat, lon

        return None, None

    def _extract_max_wind(self, text: str) -> Optional[int]:
        """Extract maximum sustained wind speed from advisory text.

        Examples:
        - "MAXIMUM SUSTAINED WINDS...85 MPH"
        - "maximum sustained winds of 85 mph"
        """
        patterns = [
            r"MAXIMUM SUSTAINED WINDS[\.]+\s*(\d+)\s*MPH",
            r"maximum sustained winds[^\d]*(\d+)\s*mph",
            r"winds[^\d]*(\d+)\s*mph",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None

    def _extract_pressure(self, text: str) -> Optional[int]:
        """Extract central pressure from advisory text.

        Examples:
        - "MINIMUM CENTRAL PRESSURE...985 MB"
        - "central pressure of 985 mb"
        """
        patterns = [
            r"MINIMUM CENTRAL PRESSURE[\.]+\s*(\d+)\s*MB",
            r"central pressure[^\d]*(\d+)\s*mb",
            r"pressure[^\d]*(\d+)\s*mb",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None

    def _extract_movement(self, text: str) -> Optional[str]:
        """Extract storm movement from advisory text.

        Examples:
        - "PRESENT MOVEMENT...NW OR 315 DEGREES AT 12 MPH"
        - "moving northwest at 12 mph"
        """
        patterns = [
            r"PRESENT MOVEMENT[\.]+\s*([\w\s]+AT\s*\d+\s*MPH)",
            r"moving\s+([\w\s]+at\s*\d+\s*mph)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    async def check_gom_threats(self) -> List[ActiveStorm]:
        """Get storms currently threatening Gulf of Mexico.

        Returns:
            List of ActiveStorm objects that are in or near the GOM.
        """
        storms = await self.get_active_storms()
        gom_storms = [s for s in storms if s.threatens_gom]

        if gom_storms:
            logger.warning(
                f"GOM THREAT: {len(gom_storms)} storm(s) in Gulf of Mexico: "
                f"{', '.join(s.name for s in gom_storms)}"
            )

        return gom_storms

    async def get_approaching_storms(
        self, max_distance_km: float = 1000.0
    ) -> List[tuple[ActiveStorm, float]]:
        """Get storms approaching the Gulf of Mexico.

        Args:
            max_distance_km: Maximum distance from GOM center to consider

        Returns:
            List of (storm, distance_km) tuples for storms within range,
            sorted by distance (closest first)
        """
        storms = await self.get_active_storms()
        approaching = []

        for storm in storms:
            if storm.threatens_gom:
                approaching.append((storm, 0.0))
            else:
                distance = storm.gom_proximity_km
                if distance is not None and distance <= max_distance_km:
                    approaching.append((storm, distance))

        approaching.sort(key=lambda x: x[1])
        return approaching
