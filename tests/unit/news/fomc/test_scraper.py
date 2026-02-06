"""Unit tests for FOMC Statement Scraper.

Tests the FOMCStatementScraper with mocked HTTP responses.
Run with: uv run pytest tests/unit/news/fomc/test_scraper.py -v
"""

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from liquidity.news.fomc.schemas import FOMCStatement, FOMCStatementCollection
from liquidity.news.fomc.scraper import (
    FOMCScraperError,
    FOMCStatementNotFoundError,
    FOMCStatementScraper,
)

# Sample FOMC statement HTML (simulating Fed website)
SAMPLE_FED_HTML = """
<!DOCTYPE html>
<html>
<head><title>FOMC Statement</title></head>
<body>
<nav>Navigation that should be removed</nav>
<div class="col-xs-12 col-sm-8 col-md-8">
    <h1>Federal Reserve Press Release</h1>
    <p>For release at 2:00 p.m. EST</p>
    <p>The Federal Open Market Committee decided to maintain the target range
    for the federal funds rate at 5-1/4 to 5-1/2 percent. The Committee judges
    that the risks to achieving its employment and inflation goals are moving
    into better balance. Economic activity has been expanding at a solid pace.
    Job gains have moderated but remain strong. Inflation has eased over the
    past year but remains elevated. The Committee remains highly attentive to
    inflation risks.</p>
    <p>In support of its goals, the Committee decided to maintain the target
    range for the federal funds rate at 5-1/4 to 5-1/2 percent.</p>
</div>
<footer>Footer that should be removed</footer>
</body>
</html>
"""

SAMPLE_GITHUB_TEXT = """
Federal Reserve Press Release
January 31, 2024

The Federal Open Market Committee decided to maintain the target range
for the federal funds rate at 5-1/4 to 5-1/2 percent. The Committee judges
that the risks to achieving its employment and inflation goals are moving
into better balance. Economic activity has been expanding at a solid pace.
"""


@pytest.fixture
def temp_cache_dir() -> Path:
    """Create a temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def scraper(temp_cache_dir: Path) -> FOMCStatementScraper:
    """Create a scraper instance with temporary cache."""
    return FOMCStatementScraper(cache_dir=temp_cache_dir)


@pytest.fixture
def sample_statement() -> FOMCStatement:
    """Create a sample FOMC statement for testing."""
    return FOMCStatement(
        date=date(2024, 1, 31),
        meeting_date=date(2024, 1, 31),
        raw_text=(
            "The Federal Open Market Committee decided to maintain the target range "
            "for the federal funds rate at 5-1/4 to 5-1/2 percent. The Committee judges "
            "that the risks to achieving its employment and inflation goals are moving "
            "into better balance."
        ),
        source="fed",
        url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20240131a.htm",
        fetched_at=datetime(2024, 1, 31, 14, 0, 0),
    )


class TestFOMCStatementSchema:
    """Tests for FOMCStatement Pydantic model."""

    def test_statement_creation(self, sample_statement: FOMCStatement) -> None:
        """Test creating a valid statement."""
        assert sample_statement.date == date(2024, 1, 31)
        assert sample_statement.source == "fed"
        assert "federal funds rate" in sample_statement.raw_text.lower()

    def test_word_count_computed(self, sample_statement: FOMCStatement) -> None:
        """Test word count is computed correctly."""
        assert sample_statement.word_count > 0
        # Count words manually
        expected = len(sample_statement.raw_text.split())
        assert sample_statement.word_count == expected

    def test_statement_is_frozen(self, sample_statement: FOMCStatement) -> None:
        """Test statement is immutable (frozen)."""
        with pytest.raises(ValidationError):
            sample_statement.date = date(2024, 2, 1)  # type: ignore

    def test_to_cache_dict(self, sample_statement: FOMCStatement) -> None:
        """Test conversion to cache dictionary."""
        cache_dict = sample_statement.to_cache_dict()

        assert cache_dict["date"] == "2024-01-31"
        assert cache_dict["source"] == "fed"
        assert "raw_text" in cache_dict
        assert "cached_at" in cache_dict  # Should be set during conversion
        assert cache_dict["word_count"] == sample_statement.word_count

    def test_from_cache_dict(self, sample_statement: FOMCStatement) -> None:
        """Test round-trip through cache dict."""
        cache_dict = sample_statement.to_cache_dict()
        restored = FOMCStatement.from_cache_dict(cache_dict)

        assert restored.date == sample_statement.date
        assert restored.source == sample_statement.source
        assert restored.raw_text == sample_statement.raw_text
        assert restored.word_count == sample_statement.word_count
        assert restored.cached_at is not None

    def test_source_literal_validation(self) -> None:
        """Test source must be valid literal value."""
        with pytest.raises(ValidationError):
            FOMCStatement(
                date=date(2024, 1, 31),
                meeting_date=date(2024, 1, 31),
                raw_text="A" * 100,
                source="invalid_source",  # type: ignore
                url="https://example.com",
                fetched_at=datetime.utcnow(),
            )

    def test_min_text_length(self) -> None:
        """Test raw_text must be at least 100 characters."""
        with pytest.raises(ValidationError):
            FOMCStatement(
                date=date(2024, 1, 31),
                meeting_date=date(2024, 1, 31),
                raw_text="Too short",
                source="fed",
                url="https://example.com",
                fetched_at=datetime.utcnow(),
            )


class TestFOMCStatementCollection:
    """Tests for FOMCStatementCollection."""

    def test_empty_collection(self) -> None:
        """Test creating empty collection."""
        collection = FOMCStatementCollection()
        assert collection.count == 0
        assert collection.date_range is None

    def test_collection_with_statements(
        self, sample_statement: FOMCStatement
    ) -> None:
        """Test collection with multiple statements."""
        stmt2 = FOMCStatement(
            date=date(2024, 3, 20),
            meeting_date=date(2024, 3, 20),
            raw_text=sample_statement.raw_text,
            source="fed",
            url="https://example.com/2",
            fetched_at=datetime.utcnow(),
        )

        collection = FOMCStatementCollection(statements=[sample_statement, stmt2])

        assert collection.count == 2
        assert collection.date_range == (date(2024, 1, 31), date(2024, 3, 20))

    def test_get_by_date(self, sample_statement: FOMCStatement) -> None:
        """Test getting statement by date."""
        collection = FOMCStatementCollection(statements=[sample_statement])

        found = collection.get_by_date(date(2024, 1, 31))
        assert found == sample_statement

        not_found = collection.get_by_date(date(2024, 2, 1))
        assert not_found is None


class TestFOMCStatementScraperInit:
    """Tests for scraper initialization."""

    def test_default_init(self, temp_cache_dir: Path) -> None:
        """Test scraper with default settings."""
        scraper = FOMCStatementScraper(cache_dir=temp_cache_dir)

        assert scraper._cache_dir == temp_cache_dir
        assert scraper._cache_ttl_days == 30
        assert scraper._http_timeout == 30.0

    def test_custom_ttl(self, temp_cache_dir: Path) -> None:
        """Test scraper with custom TTL."""
        scraper = FOMCStatementScraper(
            cache_dir=temp_cache_dir,
            cache_ttl_days=7,
        )

        assert scraper._cache_ttl_days == 7

    def test_cache_dir_created(self) -> None:
        """Test cache directory is created if not exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "nested" / "cache"
            assert not cache_dir.exists()

            FOMCStatementScraper(cache_dir=cache_dir)
            assert cache_dir.exists()


class TestFOMCStatementScraperCache:
    """Tests for caching functionality."""

    def test_cache_path_format(
        self, scraper: FOMCStatementScraper, temp_cache_dir: Path
    ) -> None:
        """Test cache file path format."""
        cache_path = scraper._get_cache_path(date(2024, 1, 31))

        assert cache_path == temp_cache_dir / "fomc_2024-01-31.json"

    def test_save_and_load_cache(
        self,
        scraper: FOMCStatementScraper,
        sample_statement: FOMCStatement,
    ) -> None:
        """Test saving and loading from cache."""
        scraper._save_to_cache(sample_statement)

        loaded = scraper._load_from_cache(sample_statement.date)

        assert loaded is not None
        assert loaded.date == sample_statement.date
        assert loaded.raw_text == sample_statement.raw_text
        assert loaded.cached_at is not None

    def test_cache_not_found(self, scraper: FOMCStatementScraper) -> None:
        """Test loading non-existent cache."""
        loaded = scraper._load_from_cache(date(2020, 1, 1))
        assert loaded is None

    def test_cache_ttl_expired(
        self,
        scraper: FOMCStatementScraper,
        sample_statement: FOMCStatement,
        temp_cache_dir: Path,
    ) -> None:
        """Test expired cache is not loaded."""
        # Save statement to cache
        scraper._save_to_cache(sample_statement)

        # Manually set file mtime to 31 days ago
        cache_path = scraper._get_cache_path(sample_statement.date)
        old_time = datetime.now() - timedelta(days=31)
        import os

        os.utime(cache_path, (old_time.timestamp(), old_time.timestamp()))

        # Should not load expired cache
        loaded = scraper._load_from_cache(sample_statement.date)
        assert loaded is None

    def test_cache_within_ttl(
        self,
        scraper: FOMCStatementScraper,
        sample_statement: FOMCStatement,
    ) -> None:
        """Test cache within TTL is loaded."""
        scraper._save_to_cache(sample_statement)

        # Should load valid cache
        loaded = scraper._load_from_cache(sample_statement.date)
        assert loaded is not None

    def test_list_cached_dates(
        self,
        scraper: FOMCStatementScraper,
        sample_statement: FOMCStatement,
    ) -> None:
        """Test listing cached dates."""
        # Initially empty
        assert scraper.list_cached() == []

        # Save a statement
        scraper._save_to_cache(sample_statement)

        dates = scraper.list_cached()
        assert date(2024, 1, 31) in dates

    def test_clear_cache(
        self,
        scraper: FOMCStatementScraper,
        sample_statement: FOMCStatement,
    ) -> None:
        """Test clearing all cache."""
        scraper._save_to_cache(sample_statement)
        assert len(scraper.list_cached()) == 1

        deleted = scraper.clear_cache()
        assert deleted == 1
        assert len(scraper.list_cached()) == 0


class TestFOMCStatementScraperTextCleaning:
    """Tests for HTML cleaning and text extraction."""

    def test_clean_text_removes_html(self) -> None:
        """Test HTML tags are removed."""
        html = "<p>Hello <strong>World</strong></p>"
        cleaned = FOMCStatementScraper._clean_text(html)

        assert "<" not in cleaned
        assert ">" not in cleaned
        assert "Hello" in cleaned
        assert "World" in cleaned

    def test_clean_text_normalizes_whitespace(self) -> None:
        """Test whitespace is normalized."""
        text = "Hello    World\n\n\tTest"
        cleaned = FOMCStatementScraper._clean_text(text)

        assert cleaned == "Hello World Test"

    def test_clean_text_removes_scripts(self) -> None:
        """Test script and style elements are removed."""
        html = """
        <html>
        <script>alert('bad');</script>
        <style>.hidden{display:none}</style>
        <p>Good content</p>
        </html>
        """
        cleaned = FOMCStatementScraper._clean_text(html)

        assert "alert" not in cleaned
        assert "display" not in cleaned
        assert "Good content" in cleaned


class TestFOMCStatementScraperFetch:
    """Tests for fetch methods with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_fetch_from_fed_success(
        self, scraper: FOMCStatementScraper
    ) -> None:
        """Test successful fetch from Fed website."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_FED_HTML
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            scraper,
            "_get_client",
            return_value=AsyncMock(get=AsyncMock(return_value=mock_response)),
        ):
            statement = await scraper._fetch_from_fed(date(2024, 1, 31))

        assert statement.source == "fed"
        assert statement.date == date(2024, 1, 31)
        assert "Federal Reserve" in statement.raw_text
        assert statement.word_count > 0

    @pytest.mark.asyncio
    async def test_fetch_from_fed_404(self, scraper: FOMCStatementScraper) -> None:
        """Test Fed website 404 raises error."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with (
            patch.object(
                scraper,
                "_get_client",
                return_value=AsyncMock(get=AsyncMock(return_value=mock_response)),
            ),
            pytest.raises(FOMCScraperError, match="not found"),
        ):
            await scraper._fetch_from_fed(date(2024, 1, 31))

    @pytest.mark.asyncio
    async def test_fetch_from_github_success(
        self, scraper: FOMCStatementScraper
    ) -> None:
        """Test successful fetch from GitHub archive."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_GITHUB_TEXT
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            scraper,
            "_get_client",
            return_value=AsyncMock(get=AsyncMock(return_value=mock_response)),
        ):
            statement = await scraper._fetch_from_github(date(2024, 1, 31))

        assert statement.source == "github"
        assert "Federal Reserve" in statement.raw_text

    @pytest.mark.asyncio
    async def test_fetch_with_fallback(
        self, scraper: FOMCStatementScraper
    ) -> None:
        """Test fallback to next tier on failure."""
        # Fed fails (404)
        mock_fed_response = MagicMock()
        mock_fed_response.status_code = 404

        # GitHub succeeds
        mock_github_response = MagicMock()
        mock_github_response.status_code = 200
        mock_github_response.text = SAMPLE_GITHUB_TEXT
        mock_github_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_get(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if "federalreserve.gov" in url:
                return mock_fed_response
            return mock_github_response

        mock_client = AsyncMock()
        mock_client.get = mock_get

        # Mock FedTools to also fail
        with (
            patch.object(scraper, "_get_client", return_value=mock_client),
            patch.object(
                scraper,
                "_fetch_from_fedtools",
                side_effect=FOMCScraperError("FedTools unavailable"),
            ),
        ):
            statement = await scraper.fetch(date(2024, 1, 31))

        # Should have fallen back to GitHub
        assert statement.source == "github"

    @pytest.mark.asyncio
    async def test_fetch_uses_cache(
        self,
        scraper: FOMCStatementScraper,
        sample_statement: FOMCStatement,
    ) -> None:
        """Test fetch returns cached statement."""
        # Pre-populate cache
        scraper._save_to_cache(sample_statement)

        # Fetch should return cached version without HTTP call
        statement = await scraper.fetch(date(2024, 1, 31))

        assert statement.date == sample_statement.date
        assert statement.cached_at is not None

    @pytest.mark.asyncio
    async def test_fetch_skip_cache(
        self,
        scraper: FOMCStatementScraper,
        sample_statement: FOMCStatement,
    ) -> None:
        """Test skip_cache bypasses cache."""
        # Pre-populate cache
        scraper._save_to_cache(sample_statement)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_FED_HTML
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            scraper,
            "_get_client",
            return_value=AsyncMock(get=AsyncMock(return_value=mock_response)),
        ):
            statement = await scraper.fetch(date(2024, 1, 31), skip_cache=True)

        # Should be fresh fetch (no cached_at initially)
        assert statement.cached_at is None

    @pytest.mark.asyncio
    async def test_fetch_all_tiers_fail(
        self, scraper: FOMCStatementScraper
    ) -> None:
        """Test error when all tiers fail."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with (
            patch.object(
                scraper,
                "_get_client",
                return_value=AsyncMock(get=AsyncMock(return_value=mock_response)),
            ),
            patch.object(
                scraper,
                "_fetch_from_fedtools",
                side_effect=FOMCScraperError("FedTools unavailable"),
            ),
            pytest.raises(
                FOMCStatementNotFoundError, match="Failed to fetch FOMC statement"
            ),
        ):
            await scraper.fetch(date(2024, 1, 31))


class TestFOMCStatementScraperContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_client(
        self, temp_cache_dir: Path
    ) -> None:
        """Test context manager creates HTTP client."""
        scraper = FOMCStatementScraper(cache_dir=temp_cache_dir)

        assert scraper._client is None

        async with scraper:
            assert scraper._client is not None
            assert not scraper._client.is_closed

        # Client should be closed after exit
        assert scraper._client is None

    @pytest.mark.asyncio
    async def test_close_releases_client(
        self, scraper: FOMCStatementScraper
    ) -> None:
        """Test close method releases client."""
        # Initialize client
        await scraper._get_client()
        assert scraper._client is not None

        await scraper.close()
        assert scraper._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(
        self, scraper: FOMCStatementScraper
    ) -> None:
        """Test close can be called multiple times."""
        await scraper.close()  # No client yet
        await scraper.close()  # Still safe
        # Should not raise


class TestFOMCStatementScraperFedTools:
    """Tests for FedTools integration (Tier 2)."""

    @pytest.mark.asyncio
    async def test_fedtools_import_error(
        self, scraper: FOMCStatementScraper
    ) -> None:
        """Test graceful handling when FedTools not installed."""
        with (
            patch.dict("sys.modules", {"FedTools": None}),
            pytest.raises(FOMCScraperError, match="FedTools not installed"),
        ):
            await scraper._fetch_from_fedtools(date(2024, 1, 31))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
