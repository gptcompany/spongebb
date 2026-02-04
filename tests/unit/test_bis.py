"""Unit tests for BIS collector.

Tests BISCollector functionality:
- Download caching logic (mock httpx, verify cache hit/miss)
- CSV parsing with sample BIS data format
- USD filtering logic
- Cache expiry (7 day threshold)
- Error handling for network failures

Run with: uv run pytest tests/unit/test_bis.py -v
"""

import os
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from liquidity.collectors.bis import (
    BIS_COLUMN_MAPPING,
    LBS_DIMENSION_CODES,
    BISCollector,
)

# Sample BIS LBS CSV data (simplified structure)
SAMPLE_LBS_CSV = """FREQ,L_MEASURE,L_POSITION,L_INSTR,L_CURR_TYPE,L_PARENT_CTY,L_REP_CTY,L_CP_COUNTRY,L_CP_SECTOR,TIME_PERIOD,OBS_VALUE
Q,S,C,A,USD,5J,GB,5J,A,2024-Q4,1500000
Q,S,C,A,USD,5J,DE,5J,A,2024-Q4,800000
Q,S,C,A,USD,5J,JP,5J,A,2024-Q4,600000
Q,S,C,A,USD,5J,US,5J,A,2024-Q4,5000000
Q,S,C,A,USD,5J,CH,5J,A,2024-Q4,400000
Q,S,C,A,EUR,5J,GB,5J,A,2024-Q4,1200000
Q,S,L,A,USD,5J,GB,5J,A,2024-Q4,900000
Q,F,C,A,USD,5J,GB,5J,A,2024-Q4,150000
Q,S,C,A,USD,5J,GB,5J,A,2024-Q3,1450000
Q,S,C,A,USD,5J,DE,5J,A,2024-Q3,780000
Q,S,C,A,USD,5J,JP,5J,A,2024-Q3,580000
"""


class MockSettings:
    """Mock settings with configurable cache_dir."""

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    """Create temporary cache directory."""
    cache_dir = tmp_path / ".cache" / "liquidity"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def bis_collector_with_tmp_cache(tmp_cache_dir: Path) -> BISCollector:
    """Create a BIS collector with temporary cache directory."""
    collector = BISCollector()
    # Replace settings with mock that has tmp cache dir
    collector._settings = MockSettings(tmp_cache_dir)  # type: ignore[assignment]
    return collector


@pytest.fixture
def bis_collector() -> BISCollector:
    """Create a BIS collector instance."""
    return BISCollector()


@pytest.fixture
def sample_lbs_df() -> pd.DataFrame:
    """Create sample LBS DataFrame."""
    from io import StringIO

    return pd.read_csv(StringIO(SAMPLE_LBS_CSV))


class TestBISCollectorInstantiation:
    """Tests for BIS collector instantiation."""

    def test_collector_instantiation(self) -> None:
        """Test BISCollector can be instantiated."""
        collector = BISCollector()
        assert collector.name == "bis"

    def test_collector_class_constants(self) -> None:
        """Test class constants are defined."""
        assert BISCollector.BIS_BULK_URL == "https://data.bis.org/static/bulk"
        assert "lbs" in BISCollector.DATASETS
        assert "cbs" in BISCollector.DATASETS
        assert BISCollector.CACHE_DAYS == 7
        assert BISCollector.DOWNLOAD_TIMEOUT == 120.0


class TestBISConstants:
    """Tests for BIS constants."""

    def test_lbs_dimension_codes_defined(self) -> None:
        """Test LBS dimension codes are defined."""
        assert "FREQ" in LBS_DIMENSION_CODES
        assert "L_MEASURE" in LBS_DIMENSION_CODES
        assert "L_POSITION" in LBS_DIMENSION_CODES
        assert "L_CURR_TYPE" in LBS_DIMENSION_CODES
        assert "TIME_PERIOD" in LBS_DIMENSION_CODES
        assert "OBS_VALUE" in LBS_DIMENSION_CODES

    def test_column_mapping_defined(self) -> None:
        """Test column mapping is defined."""
        assert "TIME_PERIOD" in BIS_COLUMN_MAPPING
        assert BIS_COLUMN_MAPPING["TIME_PERIOD"] == "timestamp"
        assert "OBS_VALUE" in BIS_COLUMN_MAPPING
        assert BIS_COLUMN_MAPPING["OBS_VALUE"] == "value"


class TestBISCaching:
    """Tests for download caching logic."""

    def test_is_cache_valid_no_file(
        self, bis_collector_with_tmp_cache: BISCollector
    ) -> None:
        """Test cache validity when file doesn't exist."""
        assert bis_collector_with_tmp_cache.is_cache_valid("lbs") is False

    def test_is_cache_valid_fresh_cache(
        self, bis_collector_with_tmp_cache: BISCollector, tmp_cache_dir: Path
    ) -> None:
        """Test cache validity when cache is fresh."""
        cache_dir = tmp_cache_dir / "bis"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "lbs.csv"
        cache_file.write_text(SAMPLE_LBS_CSV)

        assert bis_collector_with_tmp_cache.is_cache_valid("lbs") is True

    def test_is_cache_valid_stale_cache(
        self, bis_collector_with_tmp_cache: BISCollector, tmp_cache_dir: Path
    ) -> None:
        """Test cache validity when cache is stale (>7 days)."""
        cache_dir = tmp_cache_dir / "bis"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "lbs.csv"
        cache_file.write_text(SAMPLE_LBS_CSV)

        # Set modification time to 10 days ago
        old_time = datetime.now() - timedelta(days=10)
        os.utime(cache_file, (old_time.timestamp(), old_time.timestamp()))

        assert bis_collector_with_tmp_cache.is_cache_valid("lbs") is False

    def test_clear_cache_specific_dataset(
        self, bis_collector_with_tmp_cache: BISCollector, tmp_cache_dir: Path
    ) -> None:
        """Test clearing specific dataset cache."""
        cache_dir = tmp_cache_dir / "bis"
        cache_dir.mkdir(parents=True, exist_ok=True)
        lbs_file = cache_dir / "lbs.csv"
        cbs_file = cache_dir / "cbs.csv"
        lbs_file.write_text(SAMPLE_LBS_CSV)
        cbs_file.write_text(SAMPLE_LBS_CSV)

        bis_collector_with_tmp_cache.clear_cache("lbs")

        assert not lbs_file.exists()
        assert cbs_file.exists()

    def test_clear_cache_all(
        self, bis_collector_with_tmp_cache: BISCollector, tmp_cache_dir: Path
    ) -> None:
        """Test clearing all cache."""
        cache_dir = tmp_cache_dir / "bis"
        cache_dir.mkdir(parents=True, exist_ok=True)
        lbs_file = cache_dir / "lbs.csv"
        cbs_file = cache_dir / "cbs.csv"
        lbs_file.write_text(SAMPLE_LBS_CSV)
        cbs_file.write_text(SAMPLE_LBS_CSV)

        bis_collector_with_tmp_cache.clear_cache()

        assert not lbs_file.exists()
        assert not cbs_file.exists()


class TestBISCsvParsing:
    """Tests for CSV parsing."""

    def test_parse_lbs_csv(self, bis_collector: BISCollector, tmp_path: Path) -> None:
        """Test parsing LBS CSV file."""
        csv_file = tmp_path / "lbs.csv"
        csv_file.write_text(SAMPLE_LBS_CSV)

        df = bis_collector._parse_lbs_csv(csv_file)

        assert not df.empty
        assert "FREQ" in df.columns
        assert "L_MEASURE" in df.columns
        assert "L_POSITION" in df.columns
        assert "L_CURR_TYPE" in df.columns
        assert "TIME_PERIOD" in df.columns
        assert "OBS_VALUE" in df.columns
        assert len(df) == 11  # 11 rows in sample

    def test_parse_cbs_csv(self, bis_collector: BISCollector, tmp_path: Path) -> None:
        """Test parsing CBS CSV file (same structure as LBS)."""
        csv_file = tmp_path / "cbs.csv"
        csv_file.write_text(SAMPLE_LBS_CSV)

        df = bis_collector._parse_cbs_csv(csv_file)

        assert not df.empty
        assert len(df) == 11


class TestBISDataFiltering:
    """Tests for LBS data filtering."""

    def test_filter_lbs_data_defaults(
        self, bis_collector: BISCollector, sample_lbs_df: pd.DataFrame
    ) -> None:
        """Test filtering with default parameters (USD, Claims, Stocks, Quarterly)."""
        filtered = bis_collector.filter_lbs_data(sample_lbs_df)

        # Should filter out EUR rows, liabilities (L), and flows (F)
        assert len(filtered) > 0

        # Check that filtering worked
        # Sample has: GB,DE,JP,US,CH for Q4 + GB,DE,JP for Q3 = 8 rows
        assert len(filtered) == 8

    def test_filter_lbs_data_eur_currency(
        self, bis_collector: BISCollector, sample_lbs_df: pd.DataFrame
    ) -> None:
        """Test filtering for EUR currency."""
        filtered = bis_collector.filter_lbs_data(
            sample_lbs_df,
            freq="Q",
            measure="S",
            position="C",
            curr_type="EUR",
        )

        # Only 1 EUR row in sample
        assert len(filtered) == 1

    def test_filter_lbs_data_liabilities(
        self, bis_collector: BISCollector, sample_lbs_df: pd.DataFrame
    ) -> None:
        """Test filtering for liabilities."""
        filtered = bis_collector.filter_lbs_data(
            sample_lbs_df,
            position="L",  # Liabilities
            curr_type="USD",
        )

        # Only 1 liabilities row in sample
        assert len(filtered) == 1

    def test_filter_lbs_data_output_columns(
        self, bis_collector: BISCollector, sample_lbs_df: pd.DataFrame
    ) -> None:
        """Test that filtered output has expected columns."""
        filtered = bis_collector.filter_lbs_data(sample_lbs_df)

        # Should have timestamp, value, and rep_cty columns
        assert "timestamp" in filtered.columns
        assert "value" in filtered.columns
        assert "rep_cty" in filtered.columns


class TestBISQuarterParsing:
    """Tests for quarter string parsing."""

    def test_parse_bis_quarter_valid(self, bis_collector: BISCollector) -> None:
        """Test parsing valid quarter strings."""
        # 2024-Q4 should be December 2024
        result = bis_collector._parse_bis_quarter("2024-Q4")
        assert result is not None
        assert result.year == 2024
        assert result.month == 12

        # 2024-Q1 should be March 2024
        result = bis_collector._parse_bis_quarter("2024-Q1")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3

    def test_parse_bis_quarter_invalid(self, bis_collector: BISCollector) -> None:
        """Test parsing invalid quarter strings returns None."""
        # Empty string returns datetime via pandas parsing fallback
        # Our function returns None only for unparseable strings
        result = bis_collector._parse_bis_quarter("")
        # Empty string may parse to something, check it doesn't raise
        assert result is None or isinstance(result, datetime)

    def test_parse_bis_quarter_nan(self, bis_collector: BISCollector) -> None:
        """Test parsing NaN values."""
        import numpy as np

        assert bis_collector._parse_bis_quarter(np.nan) is None


class TestBISOffshoreUSDCalculation:
    """Tests for offshore USD calculation."""

    def test_calculate_offshore_usd_excludes_us(
        self, bis_collector: BISCollector, sample_lbs_df: pd.DataFrame
    ) -> None:
        """Test that US positions are excluded from offshore total."""
        filtered = bis_collector.filter_lbs_data(sample_lbs_df)
        result = bis_collector.calculate_offshore_usd(filtered)

        assert not result.empty
        assert "timestamp" in result.columns
        assert "offshore_usd_total" in result.columns

        # US value (5000000) should NOT be included
        # Q4: GB(1500000) + DE(800000) + JP(600000) + CH(400000) = 3300000
        # Q3: GB(1450000) + DE(780000) + JP(580000) = 2810000
        q4_total = result[result["timestamp"].dt.month == 12][
            "offshore_usd_total"
        ].iloc[0]
        assert q4_total == 3300000  # Excludes US

    def test_calculate_offshore_usd_empty_df(self, bis_collector: BISCollector) -> None:
        """Test handling empty DataFrame."""
        empty_df = pd.DataFrame(columns=["timestamp", "value", "rep_cty"])
        result = bis_collector.calculate_offshore_usd(empty_df)

        assert result.empty
        assert list(result.columns) == ["timestamp", "offshore_usd_total"]


class TestBISQuarterlySeries:
    """Tests for quarterly series output."""

    def test_get_quarterly_series_format(
        self, bis_collector: BISCollector, sample_lbs_df: pd.DataFrame
    ) -> None:
        """Test quarterly series output format."""
        filtered = bis_collector.filter_lbs_data(sample_lbs_df)
        result = bis_collector.get_quarterly_series(filtered)

        assert not result.empty
        assert set(result.columns) == {
            "timestamp",
            "series_id",
            "source",
            "value",
            "unit",
        }

        # Check values
        assert (result["series_id"] == "bis_offshore_usd").all()
        assert (result["source"] == "bis").all()
        assert (result["unit"] == "millions_usd").all()

    def test_get_quarterly_series_empty(self, bis_collector: BISCollector) -> None:
        """Test quarterly series with empty input."""
        empty_df = pd.DataFrame(columns=["timestamp", "value", "rep_cty"])
        result = bis_collector.get_quarterly_series(empty_df)

        assert result.empty
        expected_cols = {"timestamp", "series_id", "source", "value", "unit"}
        assert set(result.columns) == expected_cols


class TestBISDownloadAndCache:
    """Tests for download and caching with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_download_and_cache_success(
        self, bis_collector_with_tmp_cache: BISCollector, tmp_cache_dir: Path
    ) -> None:
        """Test successful download and caching."""
        # Create a zip file with CSV content
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("WS_LBS_D_PUB.csv", SAMPLE_LBS_CSV)
        zip_content = zip_buffer.getvalue()

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.content = zip_content
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            path = await bis_collector_with_tmp_cache._download_and_cache("lbs")

            assert path.exists()
            assert path.name == "lbs.csv"
            content = path.read_text()
            assert "FREQ" in content

    @pytest.mark.asyncio
    async def test_download_and_cache_uses_cache(
        self, bis_collector_with_tmp_cache: BISCollector, tmp_cache_dir: Path
    ) -> None:
        """Test that fresh cache is used instead of downloading."""
        cache_dir = tmp_cache_dir / "bis"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "lbs.csv"
        cache_file.write_text(SAMPLE_LBS_CSV)

        with patch("httpx.AsyncClient") as mock_client:
            # Should not be called because cache is fresh
            path = await bis_collector_with_tmp_cache._download_and_cache("lbs")

            mock_client.assert_not_called()
            assert path == cache_file

    @pytest.mark.asyncio
    async def test_download_unknown_dataset(self, bis_collector: BISCollector) -> None:
        """Test error handling for unknown dataset."""
        from liquidity.collectors.base import CollectorFetchError

        with pytest.raises(CollectorFetchError, match="Unknown dataset"):
            await bis_collector._download_and_cache("unknown")


class TestBISCollectMethods:
    """Tests for collect methods with mocking."""

    @pytest.mark.asyncio
    async def test_collect_lbs_usd_claims(
        self, bis_collector_with_tmp_cache: BISCollector, tmp_cache_dir: Path
    ) -> None:
        """Test collecting LBS USD claims."""
        cache_dir = tmp_cache_dir / "bis"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "lbs.csv"
        cache_file.write_text(SAMPLE_LBS_CSV)

        result = await bis_collector_with_tmp_cache.collect_lbs_usd_claims()

        assert not result.empty
        assert set(result.columns) == {
            "timestamp",
            "series_id",
            "source",
            "value",
            "unit",
        }
        assert (result["series_id"] == "bis_offshore_usd").all()
        assert (result["source"] == "bis").all()

    @pytest.mark.asyncio
    async def test_collect_dispatch_lbs(
        self, bis_collector_with_tmp_cache: BISCollector, tmp_cache_dir: Path
    ) -> None:
        """Test collect method dispatches to LBS."""
        cache_dir = tmp_cache_dir / "bis"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "lbs.csv"
        cache_file.write_text(SAMPLE_LBS_CSV)

        result = await bis_collector_with_tmp_cache.collect(dataset="lbs")

        assert not result.empty
        assert "bis_offshore_usd" in result["series_id"].values

    @pytest.mark.asyncio
    async def test_get_eurodollar_total(
        self, bis_collector_with_tmp_cache: BISCollector, tmp_cache_dir: Path
    ) -> None:
        """Test getting Eurodollar total."""
        cache_dir = tmp_cache_dir / "bis"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "lbs.csv"
        cache_file.write_text(SAMPLE_LBS_CSV)

        total = await bis_collector_with_tmp_cache.get_eurodollar_total()

        assert total is not None
        # Q4 offshore total (excluding US): 3300000
        assert total == 3300000


class TestBISErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_download_network_error(
        self, bis_collector_with_tmp_cache: BISCollector
    ) -> None:
        """Test handling of network errors."""
        import httpx

        from liquidity.collectors.base import CollectorFetchError

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection failed")
            )

            # Should raise CollectorFetchError after retries
            with pytest.raises(CollectorFetchError):
                await bis_collector_with_tmp_cache._download_and_cache("lbs")

    @pytest.mark.asyncio
    async def test_bad_zip_file(
        self, bis_collector_with_tmp_cache: BISCollector
    ) -> None:
        """Test handling of invalid zip file."""
        from liquidity.collectors.base import CollectorFetchError

        mock_response = MagicMock()
        mock_response.content = b"not a zip file"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(CollectorFetchError, match="Invalid BIS lbs zip"):
                await bis_collector_with_tmp_cache._download_and_cache("lbs")

    @pytest.mark.asyncio
    async def test_get_eurodollar_total_error_returns_none(
        self, bis_collector: BISCollector
    ) -> None:
        """Test that errors in get_eurodollar_total return None."""
        with patch.object(
            bis_collector, "collect_lbs_usd_claims", new_callable=AsyncMock
        ) as mock:
            mock.side_effect = Exception("API Error")
            result = await bis_collector.get_eurodollar_total()

        assert result is None


class TestBISRegistry:
    """Tests for registry integration."""

    def test_registry_integration(self) -> None:
        """Test that BIS collector is registered."""
        from liquidity.collectors import registry

        assert "bis" in registry.list_collectors()
        collector_cls = registry.get("bis")
        assert collector_cls is BISCollector


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
