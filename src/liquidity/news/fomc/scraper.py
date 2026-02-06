"""FOMC Statement Scraper with 3-tier fallback.

Implements robust FOMC statement fetching with:
- Tier 1: Federal Reserve official website (primary)
- Tier 2: FedTools library (secondary)
- Tier 3: GitHub archive (tertiary)

All tiers include local JSON caching with 30-day TTL.
"""

import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from pydantic import HttpUrl

from liquidity.news.fomc.schemas import FOMCStatement

logger = logging.getLogger(__name__)

# Data source URLs
FED_STATEMENT_PATTERN = (
    "https://www.federalreserve.gov/newsevents/pressreleases/monetary{date}a.htm"
)
GITHUB_FOMC_REPO = "https://raw.githubusercontent.com/fomc/statements/main/"

# Cache configuration
CACHE_TTL_DAYS = 30
DEFAULT_CACHE_DIR = Path(".cache/fomc")


class FOMCScraperError(Exception):
    """Base exception for FOMC scraper errors."""

    pass


class FOMCStatementNotFoundError(FOMCScraperError):
    """Statement not found in any source."""

    pass


class FOMCStatementScraper:
    """FOMC Statement Scraper with 3-tier fallback and caching.

    Fetches FOMC monetary policy statements with robust fallback:
    1. Federal Reserve official website (primary)
    2. FedTools Python library (secondary)
    3. GitHub archive (tertiary)

    All fetched statements are cached locally with 30-day TTL.

    Example:
        async with FOMCStatementScraper() as scraper:
            statement = await scraper.fetch(date(2024, 1, 31))
            print(f"Word count: {statement.word_count}")
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl_days: int = CACHE_TTL_DAYS,
        http_timeout: float = 30.0,
    ) -> None:
        """Initialize the FOMC statement scraper.

        Args:
            cache_dir: Directory for cached statements. Default: .cache/fomc/
            cache_ttl_days: Cache TTL in days. Default: 30.
            http_timeout: HTTP request timeout in seconds. Default: 30.
        """
        self._cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._cache_ttl_days = cache_ttl_days
        self._http_timeout = http_timeout
        self._client: httpx.AsyncClient | None = None

        # Ensure cache directory exists
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self) -> "FOMCStatementScraper":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=self._http_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Returns:
            Configured httpx.AsyncClient instance.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._http_timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_cache_path(self, statement_date: date) -> Path:
        """Get cache file path for a statement date.

        Args:
            statement_date: Date of the FOMC statement.

        Returns:
            Path to cache JSON file.
        """
        return self._cache_dir / f"fomc_{statement_date.isoformat()}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cached file exists and is within TTL.

        Args:
            cache_path: Path to cache file.

        Returns:
            True if cache is valid and within TTL.
        """
        if not cache_path.exists():
            return False

        # Check modification time against TTL
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime
        return age < timedelta(days=self._cache_ttl_days)

    def _load_from_cache(self, statement_date: date) -> FOMCStatement | None:
        """Load statement from local cache.

        Args:
            statement_date: Date of the FOMC statement.

        Returns:
            FOMCStatement if cached and valid, None otherwise.
        """
        cache_path = self._get_cache_path(statement_date)

        if not self._is_cache_valid(cache_path):
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            logger.debug("Loaded statement from cache: %s", cache_path)
            return FOMCStatement.from_cache_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to load cache %s: %s", cache_path, e)
            return None

    def _save_to_cache(self, statement: FOMCStatement) -> None:
        """Save statement to local cache.

        Args:
            statement: FOMCStatement to cache.
        """
        cache_path = self._get_cache_path(statement.date)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(statement.to_cache_dict(), f, indent=2)
            logger.debug("Saved statement to cache: %s", cache_path)
        except OSError as e:
            logger.warning("Failed to save cache %s: %s", cache_path, e)

    @staticmethod
    def _clean_text(html_text: str) -> str:
        """Clean HTML and normalize whitespace.

        Args:
            html_text: Raw HTML or text content.

        Returns:
            Cleaned text with normalized whitespace.
        """
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_text, "lxml")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator=" ", strip=True)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    @staticmethod
    def _extract_statement_text(soup: BeautifulSoup) -> str:
        """Extract statement text from Fed website HTML.

        Args:
            soup: Parsed BeautifulSoup object.

        Returns:
            Extracted and cleaned statement text.

        Raises:
            FOMCScraperError: If statement content cannot be found.
        """
        # Try multiple selectors for statement content
        selectors = [
            "div.col-xs-12.col-sm-8.col-md-8",  # Current Fed layout
            "div#article",  # Legacy layout
            "div.article",
            "article",
            "div.content",
        ]

        for selector in selectors:
            content = soup.select_one(selector)
            if content:
                # Remove navigation and non-content elements
                for nav in content.find_all(["nav", "aside", "footer"]):
                    nav.decompose()

                text = content.get_text(separator=" ", strip=True)
                # Normalize whitespace
                text = re.sub(r"\s+", " ", text)

                # Validate it looks like FOMC content
                if "Federal Reserve" in text or "Committee" in text:
                    return text.strip()

        raise FOMCScraperError("Could not extract statement content from HTML")

    async def _fetch_from_fed(
        self, statement_date: date, meeting_date: date | None = None
    ) -> FOMCStatement:
        """Tier 1: Fetch from Federal Reserve website.

        Args:
            statement_date: Publication date of the statement.
            meeting_date: FOMC meeting date (defaults to statement_date).

        Returns:
            FOMCStatement from Fed website.

        Raises:
            FOMCScraperError: If fetch fails.
        """
        date_str = statement_date.strftime("%Y%m%d")
        url = FED_STATEMENT_PATTERN.format(date=date_str)

        logger.info("Tier 1: Fetching from Fed website: %s", url)

        client = await self._get_client()
        response = await client.get(url)

        if response.status_code == 404:
            raise FOMCScraperError(f"Statement not found at Fed website: {url}")

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        raw_text = self._extract_statement_text(soup)

        return FOMCStatement(
            date=statement_date,
            meeting_date=meeting_date or statement_date,
            raw_text=raw_text,
            source="fed",
            url=HttpUrl(url),
            fetched_at=datetime.utcnow(),
        )

    async def _fetch_from_fedtools(
        self, statement_date: date, meeting_date: date | None = None
    ) -> FOMCStatement:
        """Tier 2: Fetch using FedTools library.

        FedTools provides parsed FOMC statements with historical data.

        Args:
            statement_date: Publication date of the statement.
            meeting_date: FOMC meeting date (defaults to statement_date).

        Returns:
            FOMCStatement from FedTools.

        Raises:
            FOMCScraperError: If FedTools is not available or fetch fails.
        """
        try:
            from FedTools import MonetaryPolicyCommittee
        except ImportError as e:
            raise FOMCScraperError(
                "FedTools not installed. Install with: pip install FedTools"
            ) from e

        logger.info("Tier 2: Fetching from FedTools for date: %s", statement_date)

        try:
            # FedTools fetches all statements, we filter by date
            fed = MonetaryPolicyCommittee()
            statements_df = fed.historical_statements()

            if statements_df is None or statements_df.empty:
                raise FOMCScraperError("FedTools returned no statements")

            # FedTools uses date column, convert to date objects
            statements_df["date"] = statements_df["date"].apply(
                lambda x: x.date() if hasattr(x, "date") else x
            )

            # Find matching statement
            match = statements_df[statements_df["date"] == statement_date]

            if match.empty:
                raise FOMCScraperError(
                    f"Statement for {statement_date} not found in FedTools"
                )

            row = match.iloc[0]
            raw_text = self._clean_text(row.get("content", row.get("statement", "")))

            if len(raw_text) < 100:
                raise FOMCScraperError("FedTools returned insufficient content")

            # Construct URL (FedTools provides links)
            url = row.get("link", row.get("url", f"https://fedtools.org/fomc/{statement_date}"))

            return FOMCStatement(
                date=statement_date,
                meeting_date=meeting_date or statement_date,
                raw_text=raw_text,
                source="fedtools",
                url=HttpUrl(url),
                fetched_at=datetime.utcnow(),
            )

        except Exception as e:
            if isinstance(e, FOMCScraperError):
                raise
            raise FOMCScraperError(f"FedTools fetch failed: {e}") from e

    async def _fetch_from_github(
        self, statement_date: date, meeting_date: date | None = None
    ) -> FOMCStatement:
        """Tier 3: Fetch from GitHub archive.

        Uses community-maintained FOMC statement archive.

        Args:
            statement_date: Publication date of the statement.
            meeting_date: FOMC meeting date (defaults to statement_date).

        Returns:
            FOMCStatement from GitHub archive.

        Raises:
            FOMCScraperError: If fetch fails.
        """
        # GitHub archive typically uses YYYY-MM-DD format
        filename = f"{statement_date.isoformat()}.txt"
        url = f"{GITHUB_FOMC_REPO}{filename}"

        logger.info("Tier 3: Fetching from GitHub archive: %s", url)

        client = await self._get_client()
        response = await client.get(url)

        if response.status_code == 404:
            # Try alternative filename format
            alt_filename = f"{statement_date.strftime('%Y%m%d')}.txt"
            alt_url = f"{GITHUB_FOMC_REPO}{alt_filename}"

            logger.debug("Trying alternative GitHub path: %s", alt_url)
            response = await client.get(alt_url)

            if response.status_code == 404:
                raise FOMCScraperError(f"Statement not found in GitHub archive: {url}")

            url = alt_url

        response.raise_for_status()
        raw_text = self._clean_text(response.text)

        if len(raw_text) < 100:
            raise FOMCScraperError("GitHub archive returned insufficient content")

        return FOMCStatement(
            date=statement_date,
            meeting_date=meeting_date or statement_date,
            raw_text=raw_text,
            source="github",
            url=HttpUrl(url),
            fetched_at=datetime.utcnow(),
        )

    async def fetch(
        self,
        statement_date: date,
        meeting_date: date | None = None,
        skip_cache: bool = False,
    ) -> FOMCStatement:
        """Fetch FOMC statement with 3-tier fallback.

        Attempts to fetch in order:
        1. Local cache (if valid)
        2. Federal Reserve website
        3. FedTools library
        4. GitHub archive

        Args:
            statement_date: Publication date of the statement.
            meeting_date: FOMC meeting date (defaults to statement_date).
            skip_cache: If True, skip cache and fetch fresh data.

        Returns:
            FOMCStatement from first successful source.

        Raises:
            FOMCStatementNotFoundError: If all sources fail.
        """
        # Check cache first
        if not skip_cache:
            cached = self._load_from_cache(statement_date)
            if cached:
                logger.info("Returning cached statement for %s", statement_date)
                return cached

        errors: list[str] = []

        # Tier 1: Federal Reserve website
        try:
            statement = await self._fetch_from_fed(statement_date, meeting_date)
            self._save_to_cache(statement)
            return statement
        except FOMCScraperError as e:
            errors.append(f"Tier 1 (Fed): {e}")
            logger.warning("Tier 1 failed: %s", e)

        # Tier 2: FedTools library
        try:
            statement = await self._fetch_from_fedtools(statement_date, meeting_date)
            self._save_to_cache(statement)
            return statement
        except FOMCScraperError as e:
            errors.append(f"Tier 2 (FedTools): {e}")
            logger.warning("Tier 2 failed: %s", e)

        # Tier 3: GitHub archive
        try:
            statement = await self._fetch_from_github(statement_date, meeting_date)
            self._save_to_cache(statement)
            return statement
        except FOMCScraperError as e:
            errors.append(f"Tier 3 (GitHub): {e}")
            logger.warning("Tier 3 failed: %s", e)

        # All tiers failed
        error_summary = "; ".join(errors)
        raise FOMCStatementNotFoundError(
            f"Failed to fetch FOMC statement for {statement_date}. Errors: {error_summary}"
        )

    async def fetch_latest(self) -> FOMCStatement:
        """Fetch the most recent FOMC statement.

        Attempts to find and fetch the latest available statement.
        FOMC meets ~8 times per year, so searches recent dates.

        Returns:
            Most recent FOMCStatement.

        Raises:
            FOMCStatementNotFoundError: If no recent statement found.
        """
        # FOMC typically meets every 6-8 weeks
        # Try recent dates going backwards
        today = date.today()

        # Known FOMC meeting pattern: usually ends on Wednesday
        # Search last 60 days for potential statement dates
        for days_back in range(60):
            check_date = today - timedelta(days=days_back)

            # FOMC statements typically released on Wednesday
            # but can vary, so check all dates
            try:
                return await self.fetch(check_date)
            except FOMCStatementNotFoundError:
                continue

        raise FOMCStatementNotFoundError(
            "No recent FOMC statement found in the last 60 days"
        )

    def clear_cache(self, older_than_days: int | None = None) -> int:
        """Clear cached statements.

        Args:
            older_than_days: Only clear files older than this. If None, clear all.

        Returns:
            Number of cache files deleted.
        """
        deleted = 0
        cutoff = None
        if older_than_days is not None:
            cutoff = datetime.now() - timedelta(days=older_than_days)

        for cache_file in self._cache_dir.glob("fomc_*.json"):
            if cutoff:
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if mtime >= cutoff:
                    continue

            try:
                cache_file.unlink()
                deleted += 1
            except OSError as e:
                logger.warning("Failed to delete cache file %s: %s", cache_file, e)

        logger.info("Cleared %d cache files", deleted)
        return deleted

    def list_cached(self) -> list[date]:
        """List all cached statement dates.

        Returns:
            List of dates for cached statements.
        """
        dates = []
        for cache_file in self._cache_dir.glob("fomc_*.json"):
            # Extract date from filename: fomc_YYYY-MM-DD.json
            try:
                date_str = cache_file.stem.replace("fomc_", "")
                dates.append(date.fromisoformat(date_str))
            except ValueError:
                continue

        return sorted(dates, reverse=True)
