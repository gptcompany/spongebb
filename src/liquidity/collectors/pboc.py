"""People's Bank of China collector with ROBUST multi-tier fallback.

Primary: Scrape official HTM/XLS files from PBoC website
Fallback: Use FRED TRESEGCNM052N (China foreign reserves) as proxy

Note: PBoC data has ~1 month lag. This is accepted per project requirements.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# PBoC balance sheet page
PBOC_BALANCE_SHEET_URL = (
    "http://www.pbc.gov.cn/en/3688247/3688975/3718249/4503799/index.html"
)

# FRED fallback series (foreign reserves as proxy - same as Apps Script v3.4.1)
FRED_CHINA_RESERVES = "TRESEGCNM052N"

UNIT_MAP: dict[str, str] = {
    "PBOC_TOTAL_ASSETS": "hundreds_millions_cny",  # PBoC reports in 100 million CNY
    "CHINA_FOREIGN_RESERVES": "millions_usd",  # FRED series in millions USD
}


class PBOCCollector(BaseCollector[pd.DataFrame]):
    """PBoC collector with ROBUST multi-tier fallback (ALWAYS returns data)."""

    # Cached baseline for guaranteed fallback
    BASELINE_VALUE = 47_296_970  # 100 million CNY units (~47.3 trillion CNY)
    BASELINE_DATE = "2025-11-30"

    SERIES_MAP: dict[str, str] = {
        "pboc_total_assets": "PBOC_TOTAL_ASSETS",
        "china_foreign_reserves": "CHINA_FOREIGN_RESERVES",
    }

    def __init__(
        self,
        name: str = "pboc",
        use_fred_fallback: bool = True,
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()
        self._use_fred_fallback = use_fred_fallback

    async def collect(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Collect PBoC balance sheet data with multi-tier fallback.

        Tier 1: Try scraping PBoC website
        Tier 2: FRED foreign reserves (RELIABLE - same as Apps Script)
        Tier 3: Cached baseline (GUARANTEED)
        """
        # Tier 1: Try scraping
        try:
            logger.info("PBoC: Attempting Tier 1 (website scraping)")
            return await self._collect_via_scraping()
        except Exception as e:
            logger.warning("PBoC Tier 1 (scraping) failed: %s", e)

        # Tier 2: FRED foreign reserves (RELIABLE)
        if self._use_fred_fallback:
            try:
                logger.info("PBoC: Attempting Tier 2 (FRED foreign reserves)")
                return await self._collect_via_fred(start_date, end_date)
            except Exception as e:
                logger.warning("PBoC Tier 2 (FRED) failed: %s", e)

        # Tier 3: Cached baseline (GUARANTEED)
        logger.warning("All PBoC sources failed, returning cached baseline")
        return self._get_cached_baseline()

    async def _collect_via_scraping(self) -> pd.DataFrame:
        """Tier 1: Scrape PBoC balance sheet from official website."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # Fetch index page to find latest report links
            response = await client.get(PBOC_BALANCE_SHEET_URL)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Find HTM file links (balance sheet tables)
            htm_links: list[str] = []
            for a in soup.find_all("a", href=True):
                if hasattr(a, "get"):
                    href = a.get("href")
                    if isinstance(href, str) and href.endswith(".htm"):
                        htm_links.append(href)

            if not htm_links:
                raise CollectorFetchError("No HTM files found on PBoC page")

            # Get the latest HTM file URL
            latest_url = htm_links[0]
            if not latest_url.startswith("http"):
                latest_url = f"http://www.pbc.gov.cn{latest_url}"

            # Download and parse the HTM file
            htm_response = await client.get(latest_url)
            htm_response.raise_for_status()

            return self._parse_pboc_html(htm_response.text)

    @staticmethod
    def _extract_total_assets(table: pd.DataFrame) -> float | None:
        """Extract total assets value from a PBoC HTML table.

        Returns:
            Total assets in hundreds of millions CNY, or None if not found.
        """
        for _idx, row in table.iterrows():
            row_str = str(row.values).lower()
            if "total" not in row_str or "asset" not in row_str:
                continue
            for val in row.values:
                try:
                    if pd.notna(val):
                        num = float(str(val).replace(",", "").replace(" ", ""))
                        # Sanity check: PBoC assets 40-60T CNY (hundreds of millions: 400k-600k)
                        if 200_000 < num < 800_000:
                            return num
                except (ValueError, TypeError):
                    continue
        return None

    def _parse_pboc_html(self, html: str) -> pd.DataFrame:
        """Parse PBoC HTM balance sheet table."""
        # Use pandas.read_html to extract tables
        try:
            tables = pd.read_html(html)
        except Exception as e:
            raise CollectorFetchError(f"Failed to parse PBoC HTML tables: {e}") from e

        if not tables:
            raise CollectorFetchError("No tables found in PBoC HTML")

        # Find table with Total Assets row
        total_assets = None
        report_date = datetime.now(UTC)

        for table in tables:
            table_str = table.to_string().lower()
            if "total" not in table_str or "asset" not in table_str:
                continue
            total_assets = self._extract_total_assets(table)
            if total_assets is not None:
                break

        if total_assets is None:
            raise CollectorFetchError("Could not extract total assets from PBoC HTML")

        return pd.DataFrame(
            {
                "timestamp": [report_date],
                "series_id": ["PBOC_TOTAL_ASSETS"],
                "source": ["pboc_scraping"],
                "value": [total_assets],
                "unit": ["hundreds_millions_cny"],
            }
        )

    async def _collect_via_fred(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> pd.DataFrame:
        """Tier 2: Fetch China foreign reserves from FRED."""
        from liquidity.collectors.fred import FredCollector

        fred = FredCollector()
        df = await fred.collect([FRED_CHINA_RESERVES], start_date, end_date)

        if df.empty:
            raise CollectorFetchError("FRED China foreign reserves returned no data")

        # Relabel for PBoC context
        df = df.copy()
        df["series_id"] = "CHINA_FOREIGN_RESERVES"
        df["source"] = "fred_proxy"

        logger.info("Using FRED China foreign reserves as PBoC proxy")
        return df[["timestamp", "series_id", "source", "value", "unit"]]

    def _get_cached_baseline(self) -> pd.DataFrame:
        """Tier 3: Return cached baseline (GUARANTEED)."""
        return pd.DataFrame(
            {
                "timestamp": [pd.to_datetime(self.BASELINE_DATE)],
                "series_id": ["PBOC_TOTAL_ASSETS"],
                "source": ["cached_baseline"],
                "value": [float(self.BASELINE_VALUE)],
                "unit": ["hundreds_millions_cny"],
                "stale": [True],
            }
        )


# Register collector
registry.register("pboc", PBOCCollector)
