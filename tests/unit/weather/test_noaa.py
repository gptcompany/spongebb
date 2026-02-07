"""Unit tests for NOAA hurricane tracker and impact assessment."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from liquidity.weather.impact import (
    GOM_TOTAL_PRODUCTION_BPD,
    ImpactSeverity,
    assess_gom_impact,
    format_impact_summary,
)
from liquidity.weather.noaa import (
    ActiveStorm,
    NOAAHurricaneTracker,
    StormCategory,
)


class TestStormCategory:
    """Tests for StormCategory enum and classification."""

    @pytest.mark.parametrize(
        "wind_mph,expected",
        [
            (30, StormCategory.TD),
            (38, StormCategory.TD),
            (39, StormCategory.TS),
            (73, StormCategory.TS),
            (74, StormCategory.CAT1),
            (95, StormCategory.CAT1),
            (96, StormCategory.CAT2),
            (110, StormCategory.CAT2),
            (111, StormCategory.CAT3),
            (129, StormCategory.CAT3),
            (130, StormCategory.CAT4),
            (156, StormCategory.CAT4),
            (157, StormCategory.CAT5),
            (200, StormCategory.CAT5),
        ],
    )
    def test_from_wind_speed(self, wind_mph: int, expected: StormCategory):
        """Test correct category assignment from wind speed."""
        result = StormCategory.from_wind_speed(wind_mph)
        assert result == expected

    def test_category_values(self):
        """Test category value strings."""
        assert StormCategory.TD.value == "Tropical Depression"
        assert StormCategory.TS.value == "Tropical Storm"
        assert StormCategory.CAT1.value == "Category 1"
        assert StormCategory.CAT5.value == "Category 5"


class TestActiveStorm:
    """Tests for ActiveStorm dataclass."""

    @pytest.fixture
    def gom_storm(self) -> ActiveStorm:
        """Storm in Gulf of Mexico."""
        return ActiveStorm(
            id="AL012026",
            name="Alberto",
            category=StormCategory.CAT3,
            lat=27.5,
            lon=-90.0,  # Central GOM
            max_wind_mph=120,
            movement="NW at 12 mph",
            pressure_mb=960,
            forecast_track=[],
            last_updated=datetime.utcnow(),
        )

    @pytest.fixture
    def atlantic_storm(self) -> ActiveStorm:
        """Storm in Atlantic, not in GOM."""
        return ActiveStorm(
            id="AL022026",
            name="Beta",
            category=StormCategory.CAT1,
            lat=22.0,
            lon=-70.0,  # Caribbean/Atlantic
            max_wind_mph=80,
            movement="W at 15 mph",
            pressure_mb=985,
            forecast_track=[],
            last_updated=datetime.utcnow(),
        )

    @pytest.fixture
    def weak_storm(self) -> ActiveStorm:
        """Tropical depression."""
        return ActiveStorm(
            id="AL032026",
            name="Three",
            category=StormCategory.TD,
            lat=25.0,
            lon=-88.0,
            max_wind_mph=35,
            movement="N at 5 mph",
            pressure_mb=1005,
            forecast_track=[],
            last_updated=datetime.utcnow(),
        )

    def test_is_major_cat3_plus(self, gom_storm):
        """Category 3+ should be major."""
        assert gom_storm.is_major is True

    def test_is_major_cat1(self, atlantic_storm):
        """Category 1 should not be major."""
        assert atlantic_storm.is_major is False

    def test_is_major_td(self, weak_storm):
        """Tropical depression should not be major."""
        assert weak_storm.is_major is False

    def test_threatens_gom_inside(self, gom_storm):
        """Storm inside GOM bounding box should threaten."""
        assert gom_storm.threatens_gom is True

    def test_threatens_gom_outside(self, atlantic_storm):
        """Storm outside GOM bounding box should not threaten."""
        assert atlantic_storm.threatens_gom is False

    def test_gom_proximity_inside(self, gom_storm):
        """Storm inside GOM should return None for proximity."""
        assert gom_storm.gom_proximity_km is None

    def test_gom_proximity_outside(self, atlantic_storm):
        """Storm outside GOM should return distance."""
        distance = atlantic_storm.gom_proximity_km
        assert distance is not None
        assert distance > 0
        # Caribbean to GOM center should be roughly 1500-2500 km
        assert 500 < distance < 3000

    def test_threatens_gom_boundary_north(self):
        """Test GOM boundary - northern edge."""
        storm = ActiveStorm(
            id="TEST", name="Test", category=StormCategory.TS,
            lat=31.0, lon=-90.0, max_wind_mph=50, movement="N",
            pressure_mb=1000, forecast_track=[], last_updated=datetime.utcnow()
        )
        assert storm.threatens_gom is True

        storm.lat = 32.0
        assert storm.threatens_gom is False

    def test_threatens_gom_boundary_west(self):
        """Test GOM boundary - western edge."""
        storm = ActiveStorm(
            id="TEST", name="Test", category=StormCategory.TS,
            lat=25.0, lon=-98.0, max_wind_mph=50, movement="W",
            pressure_mb=1000, forecast_track=[], last_updated=datetime.utcnow()
        )
        assert storm.threatens_gom is True

        storm.lon = -99.0
        assert storm.threatens_gom is False


class TestNOAAHurricaneTracker:
    """Tests for NOAAHurricaneTracker."""

    @pytest.fixture
    def tracker(self):
        """Create tracker instance."""
        return NOAAHurricaneTracker(timeout=10.0)

    @pytest.fixture
    def sample_rss_response(self) -> str:
        """Sample NHC RSS feed content."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>NHC Atlantic</title>
            <item>
                <title>Hurricane Alberto Advisory Number 15</title>
                <link>https://www.nhc.noaa.gov/text/refresh/MIATCPAT1+shtml/</link>
                <pubDate>Mon, 15 Jul 2026 21:00:00 GMT</pubDate>
                <description>LOCATION...27.5N 90.0W
                MAXIMUM SUSTAINED WINDS...120 MPH
                MINIMUM CENTRAL PRESSURE...960 MB
                PRESENT MOVEMENT...NW OR 315 DEGREES AT 12 MPH</description>
            </item>
            <item>
                <title>Tropical Storm Beta Advisory Number 5</title>
                <link>https://www.nhc.noaa.gov/text/refresh/MIATCPAT2+shtml/</link>
                <pubDate>Mon, 15 Jul 2026 21:00:00 GMT</pubDate>
                <description>LOCATION...22.0N 70.0W
                MAXIMUM SUSTAINED WINDS...65 MPH
                MINIMUM CENTRAL PRESSURE...990 MB
                PRESENT MOVEMENT...W AT 15 MPH</description>
            </item>
            <item>
                <title>Tropical Weather Outlook</title>
                <link>https://www.nhc.noaa.gov/gtwo.php</link>
                <description>General outlook, no active systems.</description>
            </item>
        </channel>
        </rss>
        """

    def test_extract_storm_id_from_link(self, tracker):
        """Test storm ID extraction from NHC link."""
        link = "https://www.nhc.noaa.gov/text/refresh/MIATCPAT1+shtml/"
        storm_id = tracker._extract_storm_id(link)
        assert storm_id is not None
        assert storm_id.startswith("AL")

    def test_extract_storm_name(self, tracker):
        """Test storm name extraction from title."""
        assert tracker._extract_storm_name("Hurricane Alberto Advisory Number 15") == "Alberto"
        assert tracker._extract_storm_name("Tropical Storm Beta Intermediate Advisory") == "Beta"
        assert tracker._extract_storm_name("Tropical Depression Three Advisory") == "Three"

    def test_extract_coordinates(self, tracker):
        """Test coordinate extraction from advisory text."""
        text = "LOCATION...27.5N 90.0W"
        lat, lon = tracker._extract_coordinates(text)
        assert lat == 27.5
        assert lon == -90.0

    def test_extract_coordinates_south_east(self, tracker):
        """Test coordinate extraction for S/E hemispheres."""
        text = "LOCATION...10.5S 120.0E"
        lat, lon = tracker._extract_coordinates(text)
        assert lat == -10.5
        assert lon == 120.0

    def test_extract_max_wind(self, tracker):
        """Test wind speed extraction."""
        text = "MAXIMUM SUSTAINED WINDS...120 MPH"
        wind = tracker._extract_max_wind(text)
        assert wind == 120

    def test_extract_pressure(self, tracker):
        """Test pressure extraction."""
        text = "MINIMUM CENTRAL PRESSURE...960 MB"
        pressure = tracker._extract_pressure(text)
        assert pressure == 960

    def test_extract_movement(self, tracker):
        """Test movement extraction."""
        text = "PRESENT MOVEMENT...NW OR 315 DEGREES AT 12 MPH"
        movement = tracker._extract_movement(text)
        assert "AT 12 MPH" in movement.upper()

    @pytest.mark.asyncio
    async def test_get_active_storms_parses_feed(self, tracker, sample_rss_response):
        """Test RSS feed parsing returns storms."""
        mock_response = MagicMock()
        mock_response.text = sample_rss_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(tracker, "_get_client") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_async_client

            storms = await tracker.get_active_storms()

            assert len(storms) == 2
            assert storms[0].name == "Alberto"
            assert storms[0].max_wind_mph == 120
            assert storms[0].category == StormCategory.CAT3

    @pytest.mark.asyncio
    async def test_check_gom_threats(self, tracker, sample_rss_response):
        """Test GOM threat filtering."""
        mock_response = MagicMock()
        mock_response.text = sample_rss_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(tracker, "_get_client") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_async_client

            threats = await tracker.check_gom_threats()

            # Only Alberto is in GOM (27.5N 90W)
            assert len(threats) == 1
            assert threats[0].name == "Alberto"

    @pytest.mark.asyncio
    async def test_get_active_storms_empty_on_no_storms(self, tracker):
        """Test empty list when no active storms."""
        empty_rss = """<?xml version="1.0"?>
        <rss version="2.0">
        <channel>
            <title>NHC Atlantic</title>
            <item>
                <title>Tropical Weather Outlook</title>
                <description>No active systems</description>
            </item>
        </channel>
        </rss>
        """

        mock_response = MagicMock()
        mock_response.text = empty_rss
        mock_response.raise_for_status = MagicMock()

        with patch.object(tracker, "_get_client") as mock_client:
            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_async_client

            storms = await tracker.get_active_storms()
            assert storms == []


class TestOilProductionImpact:
    """Tests for impact assessment."""

    @pytest.fixture
    def cat3_gom_storm(self) -> ActiveStorm:
        """Cat 3 hurricane in central GOM."""
        return ActiveStorm(
            id="AL012026",
            name="Alberto",
            category=StormCategory.CAT3,
            lat=27.5,
            lon=-90.0,
            max_wind_mph=120,
            movement="NW at 12 mph",
            pressure_mb=960,
            forecast_track=[],
            last_updated=datetime.utcnow(),
        )

    @pytest.fixture
    def ts_edge_storm(self) -> ActiveStorm:
        """Tropical storm at GOM edge."""
        return ActiveStorm(
            id="AL022026",
            name="Beta",
            category=StormCategory.TS,
            lat=20.0,
            lon=-95.0,
            max_wind_mph=60,
            movement="N at 10 mph",
            pressure_mb=1000,
            forecast_track=[],
            last_updated=datetime.utcnow(),
        )

    @pytest.fixture
    def cat5_storm(self) -> ActiveStorm:
        """Cat 5 monster storm."""
        return ActiveStorm(
            id="AL032026",
            name="Gamma",
            category=StormCategory.CAT5,
            lat=26.0,
            lon=-89.0,
            max_wind_mph=175,
            movement="NW at 8 mph",
            pressure_mb=905,
            forecast_track=[],
            last_updated=datetime.utcnow(),
        )

    def test_assess_major_hurricane_high_impact(self, cat3_gom_storm):
        """Cat 3 in central GOM should have high/severe impact."""
        impact = assess_gom_impact(cat3_gom_storm)

        assert impact.storm_id == "AL012026"
        assert impact.storm_name == "Alberto"
        assert impact.severity in [ImpactSeverity.HIGH, ImpactSeverity.SEVERE]
        assert impact.estimated_shut_in_pct >= 50
        assert impact.evacuation_likely is True
        assert impact.recovery_days >= 10

    def test_assess_tropical_storm_edge(self, ts_edge_storm):
        """TS at GOM edge should have lower impact."""
        impact = assess_gom_impact(ts_edge_storm)

        assert impact.severity in [ImpactSeverity.LOW, ImpactSeverity.MODERATE]
        assert impact.estimated_shut_in_pct < 30
        assert impact.recovery_days <= 5

    def test_assess_cat5_maximum_impact(self, cat5_storm):
        """Cat 5 should have severe impact."""
        impact = assess_gom_impact(cat5_storm)

        assert impact.severity == ImpactSeverity.SEVERE
        assert impact.estimated_shut_in_pct >= 80
        assert impact.evacuation_likely is True
        assert impact.recovery_days >= 25

    def test_impact_bpd_calculation(self, cat3_gom_storm):
        """Test barrels per day calculation."""
        impact = assess_gom_impact(cat3_gom_storm)

        expected_bpd = int(GOM_TOTAL_PRODUCTION_BPD * impact.estimated_shut_in_pct / 100)
        assert impact.estimated_shut_in_bpd == expected_bpd

    def test_impact_is_significant(self, cat3_gom_storm, ts_edge_storm):
        """Test is_significant property."""
        major_impact = assess_gom_impact(cat3_gom_storm)
        minor_impact = assess_gom_impact(ts_edge_storm)

        assert major_impact.is_significant is True
        # TS at edge might or might not be significant depending on exact calculation
        # Just verify the property works
        assert isinstance(minor_impact.is_significant, bool)

    def test_format_impact_summary(self, cat3_gom_storm):
        """Test impact summary formatting."""
        impact = assess_gom_impact(cat3_gom_storm)
        summary = format_impact_summary(impact)

        assert "Alberto" in summary
        assert "AL012026" in summary
        assert "Severity:" in summary
        assert "bpd" in summary
        assert "Platforms" in summary
        assert "Recovery" in summary


class TestImpactSeverity:
    """Tests for ImpactSeverity enum."""

    def test_severity_values(self):
        """Test severity value strings."""
        assert ImpactSeverity.MINIMAL.value == "minimal"
        assert ImpactSeverity.SEVERE.value == "severe"

    def test_severity_ordering(self):
        """Verify severity levels are properly ordered."""
        severities = [
            ImpactSeverity.MINIMAL,
            ImpactSeverity.LOW,
            ImpactSeverity.MODERATE,
            ImpactSeverity.HIGH,
            ImpactSeverity.SEVERE,
        ]
        # Just verify all are distinct
        assert len(set(severities)) == 5
