"""TIC collector for Treasury International Capital data.

Tracks foreign holdings of US Treasury securities:
- Major holders: Top 25 countries holding US Treasuries
- Treasury holdings by country and type
- Aggregate foreign holdings

Data sources:
- Primary: US Treasury TIC CSV/TXT files (no auth required)
- Fallback: FRED quarterly series

TIC data shows foreign capital flows into US Treasuries, a key indicator
of global dollar demand and reserve manager behavior.

Data is typically released monthly with a 2-month lag.
"""

import asyncio
import io
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

# US Treasury TIC data URLs
TIC_URLS = {
    # Major Foreign Holders of Treasury Securities (text format - most reliable)
    "mfh": "https://ticdata.treasury.gov/Publish/mfh.txt",
    # Securities held by foreign residents (SLT data)
    "holdings": "https://ticdata.treasury.gov/Publish/slt3d.txt",
    # Alternative CSV format
    "mfh_csv": "https://ticdata.treasury.gov/Publish/mfh.csv",
}

# FRED series for TIC aggregate data (fallback)
FRED_TIC_SERIES = {
    "official": "BOGZ1FL263061130Q",  # Foreign official holdings (quarterly)
    "private": "BOGZ1FL263061145Q",  # Foreign private holdings (quarterly)
}

# Country code normalization
COUNTRY_CODES: dict[str, str] = {
    "Japan": "japan",
    "JAPAN": "japan",
    "China, Mainland": "china",
    "CHINA, MAINLAND": "china",
    "China": "china",
    "United Kingdom": "uk",
    "UNITED KINGDOM": "uk",
    "U.K.": "uk",
    "Cayman Islands": "cayman",
    "CAYMAN ISLANDS": "cayman",
    "Luxembourg": "luxembourg",
    "LUXEMBOURG": "luxembourg",
    "Belgium": "belgium",
    "BELGIUM": "belgium",
    "Ireland": "ireland",
    "IRELAND": "ireland",
    "Switzerland": "switzerland",
    "SWITZERLAND": "switzerland",
    "Taiwan": "taiwan",
    "TAIWAN": "taiwan",
    "Hong Kong": "hongkong",
    "HONG KONG": "hongkong",
    "Brazil": "brazil",
    "BRAZIL": "brazil",
    "Canada": "canada",
    "CANADA": "canada",
    "France": "france",
    "FRANCE": "france",
    "Singapore": "singapore",
    "SINGAPORE": "singapore",
    "India": "india",
    "INDIA": "india",
    "Norway": "norway",
    "NORWAY": "norway",
    "Korea, South": "korea",
    "KOREA, SOUTH": "korea",
    "Saudi Arabia": "saudi",
    "SAUDI ARABIA": "saudi",
    "Germany": "germany",
    "GERMANY": "germany",
    "All Other": "other",
    "ALL OTHER": "other",
    "Grand Total": "total",
    "GRAND TOTAL": "total",
}


def _normalize_country(country: str) -> str:
    """Normalize country name to lowercase code.

    Args:
        country: Raw country name from TIC data.

    Returns:
        Normalized lowercase country code.
    """
    country = country.strip()
    if country in COUNTRY_CODES:
        return COUNTRY_CODES[country]
    # Generate code from name
    return re.sub(r"[^a-z]", "", country.lower())


def _parse_value(value: str | float) -> float | None:
    """Parse TIC value, handling special cases.

    Args:
        value: Raw value from TIC data.

    Returns:
        Parsed float or None if unparseable.
    """
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    # Remove commas and whitespace
    value_str = str(value).strip().replace(",", "")
    if value_str in ("", "n.a.", "N.A.", "*", "**"):
        return None
    try:
        return float(value_str)
    except ValueError:
        return None


class TICCollector(BaseCollector[pd.DataFrame]):
    """TIC (Treasury International Capital) data collector.

    Tracks foreign holdings of US Treasury securities:
    - Major foreign holders (monthly, 2-month lag)
    - Holdings by country and security type
    - Aggregate via FRED (quarterly fallback)

    Example:
        collector = TICCollector()

        # Get major holders (latest month)
        df = await collector.collect_major_holders()

        # Get all treasury holdings
        df = await collector.collect_treasury_holdings()

        # Fallback to FRED quarterly
        df = await collector.collect_aggregate()
    """

    TIC_URLS = TIC_URLS
    FRED_TIC_SERIES = FRED_TIC_SERIES
    COUNTRY_CODES = COUNTRY_CODES

    def __init__(
        self,
        name: str = "tic",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize TIC collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()

    async def collect(
        self,
        method: str = "major_holders",
    ) -> pd.DataFrame:
        """Collect TIC data.

        Args:
            method: Collection method - "major_holders", "holdings", or "aggregate".

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails.
        """
        if method == "major_holders":
            return await self.collect_major_holders()
        elif method == "holdings":
            return await self.collect_treasury_holdings()
        elif method == "aggregate":
            return await self.collect_aggregate()
        else:
            return await self.collect_major_holders()

    async def collect_major_holders(
        self,
        top_n: int = 25,
    ) -> pd.DataFrame:
        """Fetch major foreign holders of US Treasury securities.

        Args:
            top_n: Number of top holders to return. Defaults to 25.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
            series_id format: tic_{country}_holdings (e.g., tic_japan_holdings)

        Raises:
            CollectorFetchError: If data fetch fails.
        """

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(self._fetch_major_holders_sync, top_n)

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("TIC major holders fetch failed: %s", e)
            raise CollectorFetchError(f"TIC major holders fetch failed: {e}") from e

    def _fetch_major_holders_sync(self, top_n: int = 25) -> pd.DataFrame:
        """Synchronous fetch for major holders.

        Args:
            top_n: Number of top holders to return.

        Returns:
            Normalized DataFrame.
        """
        logger.info("Fetching TIC major foreign holders (top %d)", top_n)

        # Try TXT format first (more reliable)
        try:
            df = self._fetch_mfh_txt()
            if not df.empty:
                return self._normalize_major_holders(df, top_n)
        except Exception as e:
            logger.warning("TIC TXT fetch failed, trying CSV: %s", e)

        # Fallback to CSV format
        try:
            df = self._fetch_mfh_csv()
            if not df.empty:
                return self._normalize_major_holders(df, top_n)
        except Exception as e:
            logger.warning("TIC CSV fetch also failed: %s", e)

        # Return empty DataFrame
        logger.warning("No TIC data available from any source")
        return pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

    def _fetch_mfh_csv(self) -> pd.DataFrame:
        """Fetch major holders from CSV endpoint.

        Returns:
            Raw DataFrame from CSV.
        """
        url = TIC_URLS["mfh_csv"]
        logger.debug("Fetching TIC CSV from: %s", url)

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        # Parse CSV - Treasury CSVs often have header rows to skip
        content = response.text
        lines = content.split("\n")

        # Find header row (contains "Country" or date patterns)
        header_idx = 0
        for i, line in enumerate(lines):
            if "Country" in line or re.search(r"\d{4}", line):
                header_idx = i
                break

        # Read CSV starting from header
        df = pd.read_csv(
            io.StringIO("\n".join(lines[header_idx:])),
            skipinitialspace=True,
        )

        return df

    def _fetch_mfh_txt(self) -> pd.DataFrame:
        """Fetch major holders from TXT endpoint.

        Returns:
            Raw DataFrame from TXT.
        """
        url = TIC_URLS["mfh"]
        logger.debug("Fetching TIC TXT from: %s", url)

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        content = response.text
        lines = content.split("\n")

        # Find the data section - look for column headers with months/years
        data_start = 0
        date_header_line = None
        for i, line in enumerate(lines):
            # Look for the line that contains month headers (e.g., "Jan  Feb  Mar")
            if re.search(
                r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", line
            ):
                date_header_line = i
                # Data typically starts 2-3 lines after the date header
                continue
            # Look for country data lines (start with country name)
            if date_header_line and i > date_header_line:
                if re.match(r"^\s*[A-Za-z]", line) and not any(
                    x in line.upper()
                    for x in ["MAJOR", "HOLDINGS", "TREASURY", "BILLION"]
                ):
                    data_start = i
                    break

        if data_start == 0:
            # Try alternative parsing - look for "Japan" as first country
            for i, line in enumerate(lines):
                if "Japan" in line or "JAPAN" in line:
                    data_start = i
                    break

        if data_start == 0:
            logger.warning("Could not find data start in TIC TXT")
            return pd.DataFrame()

        # Extract data lines (until we hit footer or empty lines)
        data_lines = []
        for line in lines[data_start:]:
            stripped = line.strip()
            if not stripped:
                continue
            # Stop at footer
            if any(
                x in stripped.lower() for x in ["note:", "source:", "/1", "/2", "/3"]
            ):
                continue
            if "Department" in stripped or "Federal Reserve" in stripped:
                break
            data_lines.append(line)

        if not data_lines:
            return pd.DataFrame()

        # Parse as fixed-width format
        # The MFH.txt has country names followed by numeric columns
        df = pd.read_fwf(
            io.StringIO("\n".join(data_lines)),
            header=None,
            widths=None,  # Auto-detect column widths
        )

        return df

    def _normalize_major_holders(
        self, df: pd.DataFrame, top_n: int = 25
    ) -> pd.DataFrame:
        """Normalize major holders data to standard format.

        Args:
            df: Raw DataFrame from TIC source.
            top_n: Number of top holders to include.

        Returns:
            Normalized DataFrame with timestamp, series_id, source, value, unit.
        """
        if df.empty:
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        # Handle fixed-width parsed data (numeric column names 0, 1, 2...)
        # vs CSV with named columns
        columns = list(df.columns)
        is_numeric_cols = all(isinstance(c, int) for c in columns)

        if is_numeric_cols:
            # Fixed-width format: column 0 is country, last column is most recent value
            country_col = 0
            value_col = columns[-1]
            timestamp = datetime.now(UTC)
        else:
            # CSV format with named columns
            # Find country column
            country_col = None
            for col in df.columns:
                col_str = str(col).strip().lower()
                if col_str in ("country", "name", "country/region"):
                    country_col = col
                    break
                # First column is often country
                if df.columns.get_loc(col) == 0:  # type: ignore[union-attr]
                    country_col = col

            if country_col is None:
                country_col = df.columns[0]

            # Find most recent date column (usually last numeric column)
            date_cols = []
            for col in df.columns:
                col_str = str(col)
                # Look for date-like columns (e.g., "Jan 2024", "2024-01", etc.)
                if re.search(r"\d{4}", col_str) or re.search(
                    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", col_str
                ):
                    date_cols.append(col)

            if not date_cols:
                # Use last non-country column
                date_cols = [c for c in df.columns if c != country_col]

            if not date_cols:
                logger.warning("No value columns found in TIC data")
                return pd.DataFrame(
                    columns=["timestamp", "series_id", "source", "value", "unit"]
                )

            # Use most recent date column
            value_col = date_cols[-1]

            # Parse the date from column name
            col_str = str(value_col)
            timestamp = datetime.now(UTC)

            # Try to parse date from column name
            date_match = re.search(
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(\d{4})",
                col_str,
            )
            if date_match:
                month_str = date_match.group(1)[:3]
                year_str = date_match.group(2)
                try:
                    timestamp = datetime.strptime(f"{month_str} {year_str}", "%b %Y")
                    timestamp = timestamp.replace(tzinfo=UTC)
                except ValueError:
                    pass
            else:
                # Try YYYY-MM format
                date_match = re.search(r"(\d{4})-(\d{2})", col_str)
                if date_match:
                    try:
                        timestamp = datetime.strptime(
                            f"{date_match.group(1)}-{date_match.group(2)}", "%Y-%m"
                        )
                        timestamp = timestamp.replace(tzinfo=UTC)
                    except ValueError:
                        pass

        # Patterns to exclude (aggregate rows, not individual countries)
        exclude_patterns = [
            "total",
            "grand total",
            "foreign official",
            "foreign private",
            "for. official",  # Handles "For. Official" row
            "for official",  # Without period
            "forofficial",  # Concatenated version
            "t-bonds",
            "tbonds",
            "t bonds",
            "t-bonds & notes",
            "treasury bills",
            "country",
            "region",
            "all other",
            "of which",
            "memo:",
            "note:",
            "source:",
        ]

        # Build result DataFrame
        results = []
        total_value = None
        for _, row in df.iterrows():
            country = str(row[country_col]).strip()
            if not country or country.lower() in ("nan", ""):
                continue

            # Skip aggregate rows
            country_lower = country.lower()
            if any(pat in country_lower for pat in exclude_patterns):
                # Capture grand total separately
                if "grand total" in country_lower:
                    total_value = _parse_value(row[value_col])
                continue

            value = _parse_value(row[value_col])
            if value is None:
                continue

            country_code = _normalize_country(country)
            series_id = f"tic_{country_code}_holdings"

            results.append(
                {
                    "timestamp": timestamp,
                    "series_id": series_id,
                    "source": "treasury",
                    "value": value,
                    "unit": "billions_usd",
                }
            )

        if not results:
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        result_df = pd.DataFrame(results)

        # Sort by value descending and take top_n
        result_df = result_df.sort_values("value", ascending=False).head(top_n)

        # Add total row if captured
        if total_value is not None:
            total_row = pd.DataFrame(
                [
                    {
                        "timestamp": timestamp,
                        "series_id": "tic_total_holdings",
                        "source": "treasury",
                        "value": total_value,
                        "unit": "billions_usd",
                    }
                ]
            )
            result_df = pd.concat([result_df, total_row], ignore_index=True)

        logger.info("Normalized %d TIC major holder records", len(result_df))

        return result_df.reset_index(drop=True)

    async def collect_treasury_holdings(self) -> pd.DataFrame:
        """Fetch detailed treasury holdings by country.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
            series_id format: tic_{country}_holdings

        Raises:
            CollectorFetchError: If data fetch fails.
        """

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(self._fetch_treasury_holdings_sync)

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("TIC treasury holdings fetch failed: %s", e)
            raise CollectorFetchError(f"TIC treasury holdings fetch failed: {e}") from e

    def _fetch_treasury_holdings_sync(self) -> pd.DataFrame:
        """Synchronous fetch for treasury holdings.

        Returns:
            Normalized DataFrame.
        """
        logger.info("Fetching TIC detailed treasury holdings")

        url = TIC_URLS["holdings"]

        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()

            content = response.text
            lines = content.split("\n")

            # Find header row
            header_idx = 0
            for i, line in enumerate(lines):
                if "Country" in line or re.search(r"\d{4}", line):
                    header_idx = i
                    break

            df = pd.read_csv(
                io.StringIO("\n".join(lines[header_idx:])),
                skipinitialspace=True,
            )

            return self._normalize_major_holders(df, top_n=50)

        except Exception as e:
            logger.warning("TIC holdings fetch failed: %s", e)
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

    async def collect_aggregate(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch aggregate foreign holdings from FRED (fallback).

        Args:
            start_date: Start date for data fetch. Defaults to 1 year ago.
            end_date: End date for data fetch. Defaults to today.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch fails.
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=365)
        if end_date is None:
            end_date = datetime.now(UTC)

        async def _fetch() -> pd.DataFrame:
            return await asyncio.to_thread(
                self._fetch_aggregate_sync, start_date, end_date
            )

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("TIC FRED aggregate fetch failed: %s", e)
            raise CollectorFetchError(f"TIC FRED aggregate fetch failed: {e}") from e

    def _fetch_aggregate_sync(
        self, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Synchronous fetch for FRED aggregate.

        Args:
            start_date: Start date.
            end_date: End date.

        Returns:
            Normalized DataFrame.
        """
        logger.info("Fetching TIC aggregate from FRED")

        from openbb import obb

        # Set FRED API key if available
        api_key = self._settings.fred_api_key.get_secret_value()
        if api_key:
            obb.user.credentials.fred_api_key = api_key

        symbols = list(FRED_TIC_SERIES.values())

        try:
            result = obb.economy.fred_series(
                symbol=",".join(symbols),
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                provider="fred",
            )

            df = result.to_df().reset_index()

            if df.empty:
                return pd.DataFrame(
                    columns=["timestamp", "series_id", "source", "value", "unit"]
                )

            # Find date column
            date_col = "date" if "date" in df.columns else df.columns[0]

            # Get available series columns
            value_vars = [col for col in df.columns if col in symbols]

            if not value_vars:
                return pd.DataFrame(
                    columns=["timestamp", "series_id", "source", "value", "unit"]
                )

            # Melt to long format
            df_long = df.melt(
                id_vars=[date_col],
                value_vars=value_vars,
                var_name="fred_series",
                value_name="value",
            )

            # Map FRED series to our series_id format
            series_map = {
                FRED_TIC_SERIES["official"]: "tic_official_holdings",
                FRED_TIC_SERIES["private"]: "tic_private_holdings",
            }

            df_long["series_id"] = df_long["fred_series"].map(series_map)
            df_long = df_long.rename(columns={date_col: "timestamp"})
            df_long["timestamp"] = pd.to_datetime(df_long["timestamp"])
            df_long["source"] = "fred"
            df_long["unit"] = "millions_usd"

            # Clean and sort
            df_long = (
                df_long.dropna(subset=["value", "series_id"])
                .sort_values("timestamp")
                .reset_index(drop=True)
            )

            logger.info("Fetched %d TIC aggregate data points from FRED", len(df_long))

            return df_long[["timestamp", "series_id", "source", "value", "unit"]]

        except Exception as e:
            logger.warning("FRED TIC fetch failed: %s", e)
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

    async def get_japan_holdings(self) -> float | None:
        """Get latest Japan Treasury holdings.

        Returns:
            Japan holdings in millions USD, or None if unavailable.
        """
        try:
            df = await self.collect_major_holders()
            japan = df[df["series_id"] == "tic_japan_holdings"]
            if japan.empty:
                return None
            return float(japan["value"].iloc[0])
        except Exception as e:
            logger.warning("Failed to get Japan holdings: %s", e)
            return None

    async def get_china_holdings(self) -> float | None:
        """Get latest China Treasury holdings.

        Returns:
            China holdings in millions USD, or None if unavailable.
        """
        try:
            df = await self.collect_major_holders()
            china = df[df["series_id"] == "tic_china_holdings"]
            if china.empty:
                return None
            return float(china["value"].iloc[0])
        except Exception as e:
            logger.warning("Failed to get China holdings: %s", e)
            return None

    async def get_total_foreign_holdings(self) -> float | None:
        """Get total foreign Treasury holdings.

        Returns:
            Total holdings in millions USD, or None if unavailable.
        """
        try:
            df = await self.collect_major_holders()
            total = df[df["series_id"] == "tic_total_holdings"]
            if total.empty:
                # Sum individual holdings
                non_total = df[df["series_id"] != "tic_total_holdings"]
                if non_total.empty:
                    return None
                return float(non_total["value"].sum())
            return float(total["value"].iloc[0])
        except Exception as e:
            logger.warning("Failed to get total foreign holdings: %s", e)
            return None


# Register collector with the registry
registry.register("tic", TICCollector)
