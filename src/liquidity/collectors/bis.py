"""BIS International Banking Statistics collector via bulk CSV downloads.

BIS publishes quarterly data for international banking activity:
- LBS: Locational Banking Statistics (cross-border claims/liabilities by location)
- CBS: Consolidated Banking Statistics (claims on ultimate risk basis)

Data sources:
- LBS: https://data.bis.org/static/bulk/WS_LBS_D_PUB_csv_col.zip
- CBS: https://data.bis.org/static/bulk/WS_CBS_PUB_csv_col.zip

Data characteristics:
- Quarterly frequency with ~3 month lag
- Large files (~50-100MB compressed)
- Cache for 7 days (quarterly data doesn't change frequently)

Key metrics for Hayes framework:
- USD cross-border claims (offshore USD / Eurodollar system)
- Total: ~$19+ trillion (Q2 2025)
"""

import logging
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)


# BIS Locational Banking Statistics dimension codes
LBS_DIMENSION_CODES = {
    "FREQ": "Frequency",
    "L_MEASURE": "Measure",
    "L_POSITION": "Balance sheet position",
    "L_INSTR": "Type of instruments",
    "L_CURR_TYPE": "Currency type of reporting country",
    "L_PARENT_CTY": "Parent country",
    "L_REP_CTY": "Reporting country",
    "L_CP_COUNTRY": "Counterparty country",
    "L_CP_SECTOR": "Counterparty sector",
    "TIME_PERIOD": "Time period",
    "OBS_VALUE": "Observation value",
}

# Column mapping from verbose BIS names to short names
BIS_COLUMN_MAPPING = {
    "TIME_PERIOD": "timestamp",
    "OBS_VALUE": "value",
    "Frequency": "freq",
    "Measure": "measure",
    "Balance sheet position": "position",
    "Currency type of reporting country": "curr_type",
    "Type of instruments": "instruments",
    "Parent country": "parent_cty",
    "Reporting country": "rep_cty",
    "Counterparty country": "cp_country",
    "Counterparty sector": "cp_sector",
}


class BISCollector(BaseCollector[pd.DataFrame]):
    """BIS International Banking Statistics via bulk CSV downloads.

    Downloads quarterly data for:
    - LBS: Locational Banking Statistics (cross-border claims/liabilities by location)
    - CBS: Consolidated Banking Statistics (claims on ultimate risk basis)

    BIS bulk download URLs:
    - LBS: https://data.bis.org/static/bulk/WS_LBS_D_PUB_csv_col.zip
    - CBS: https://data.bis.org/static/bulk/WS_CBS_PUB_csv_col.zip

    Data characteristics:
    - Quarterly frequency with ~3 month lag
    - Large files (~50-100MB compressed)
    - Cache for 7 days (quarterly data doesn't change frequently)

    Key metrics for Hayes framework:
    - USD cross-border claims (L_CURR_TYPE=USD, L_POSITION=C)
    - Total: ~$19+ trillion (Q2 2025)

    Example:
        collector = BISCollector()

        # Get USD cross-border claims (offshore USD)
        df = await collector.collect_lbs_usd_claims()

        # Get latest Eurodollar total
        total = await collector.get_eurodollar_total()
    """

    BIS_BULK_URL = "https://data.bis.org/static/bulk"
    DATASETS = {
        "lbs": "WS_LBS_D_PUB_csv_col.zip",
        "cbs": "WS_CBS_PUB_csv_col.zip",
    }
    CACHE_DAYS = 7  # Quarterly data, cache for a week
    DOWNLOAD_TIMEOUT = 120.0  # Large files need longer timeout

    def __init__(
        self,
        name: str = "bis",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize BIS collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()

    async def collect(
        self,
        dataset: str = "lbs",
    ) -> pd.DataFrame:
        """Collect BIS data.

        Args:
            dataset: Dataset to collect - "lbs" or "cbs".

        Returns:
            DataFrame with BIS data.

        Raises:
            CollectorFetchError: If data fetch fails.
        """
        if dataset == "lbs":
            return await self.collect_lbs_usd_claims()
        elif dataset == "cbs":
            return await self.collect_cbs_usd_claims()
        else:
            return await self.collect_lbs_usd_claims()

    async def _download_and_cache(self, dataset: str) -> Path:
        """Download bulk CSV if not cached or stale.

        Args:
            dataset: Dataset key ("lbs" or "cbs").

        Returns:
            Path to the cached CSV file.

        Raises:
            CollectorFetchError: If download fails.
        """
        if dataset not in self.DATASETS:
            raise CollectorFetchError(f"Unknown dataset: {dataset}")

        cache_dir = self._settings.cache_dir / "bis"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{dataset}.csv"

        # Check if cache is fresh (quarterly data, cache for CACHE_DAYS)
        if cache_path.exists():
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=UTC)
            age = datetime.now(UTC) - mtime
            if age.days < self.CACHE_DAYS:
                logger.debug(
                    "Using cached BIS %s data (age: %d days)", dataset, age.days
                )
                return cache_path

        # Download and extract
        logger.info("Downloading BIS %s bulk data...", dataset)
        url = f"{self.BIS_BULK_URL}/{self.DATASETS[dataset]}"

        try:
            async with httpx.AsyncClient(timeout=self.DOWNLOAD_TIMEOUT) as client:
                response = await client.get(url)
                response.raise_for_status()
                content = response.content
        except Exception as e:
            logger.error("BIS %s download failed: %s", dataset, e)
            raise CollectorFetchError(f"BIS {dataset} download failed: {e}") from e

        # Extract CSV from zip
        try:
            with zipfile.ZipFile(BytesIO(content)) as zf:
                csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_names:
                    raise CollectorFetchError(f"No CSV found in BIS {dataset} zip")

                csv_name = csv_names[0]
                logger.debug("Extracting %s from BIS %s zip", csv_name, dataset)

                with zf.open(csv_name) as f:
                    csv_content = f.read()

            # Write to cache
            cache_path.write_bytes(csv_content)
            logger.info("Cached BIS %s data: %d bytes", dataset, len(csv_content))

        except zipfile.BadZipFile as e:
            raise CollectorFetchError(f"Invalid BIS {dataset} zip file: {e}") from e

        return cache_path

    def _parse_lbs_csv(self, path: Path) -> pd.DataFrame:
        """Parse LBS CSV with multi-level headers.

        BIS LBS CSV has verbose column names. We parse and normalize them.

        Args:
            path: Path to the CSV file.

        Returns:
            DataFrame with parsed LBS data.
        """
        logger.debug("Parsing LBS CSV: %s", path)

        # Read CSV - BIS uses standard headers, not multi-level
        df = pd.read_csv(path, low_memory=False)

        logger.debug("LBS CSV columns: %s", list(df.columns)[:10])
        logger.debug("LBS CSV shape: %s", df.shape)

        return df

    def _parse_cbs_csv(self, path: Path) -> pd.DataFrame:
        """Parse CBS CSV.

        Args:
            path: Path to the CSV file.

        Returns:
            DataFrame with parsed CBS data.
        """
        logger.debug("Parsing CBS CSV: %s", path)

        df = pd.read_csv(path, low_memory=False)

        logger.debug("CBS CSV columns: %s", list(df.columns)[:10])
        logger.debug("CBS CSV shape: %s", df.shape)

        return df

    @staticmethod
    def _detect_lbs_columns(df: pd.DataFrame) -> dict[str, str | None]:
        """Detect BIS LBS column names by keyword matching.

        Returns:
            Dict mapping logical names to actual column names (or None).
        """
        result: dict[str, str | None] = {
            "freq": None, "measure": None, "position": None,
            "curr": None, "time": None, "value": None, "rep_cty": None,
        }
        for col in df.columns:
            col_upper = col.upper()
            if "FREQ" in col_upper:
                result["freq"] = col
            elif "MEASURE" in col_upper:
                result["measure"] = col
            elif "POSITION" in col_upper:
                result["position"] = col
            elif "CURR" in col_upper and "TYPE" in col_upper:
                result["curr"] = col
            elif "TIME" in col_upper and "PERIOD" in col_upper:
                result["time"] = col
            elif col_upper == "OBS_VALUE" or "VALUE" in col_upper:
                result["value"] = col
            elif "REP" in col_upper and "CTY" in col_upper:
                result["rep_cty"] = col
        return result

    def filter_lbs_data(
        self,
        df: pd.DataFrame,
        freq: str = "Q",
        measure: str = "S",
        position: str = "C",
        curr_type: str = "USD",
    ) -> pd.DataFrame:
        """Filter LBS data by dimension codes.

        Args:
            df: Raw LBS DataFrame.
            freq: Frequency - Q (quarterly), A (annual). Default: Q.
            measure: Measure - S (stocks), F (flows). Default: S.
            position: Position - C (claims), L (liabilities). Default: C.
            curr_type: Currency type - USD, EUR, JPY, etc. Default: USD.

        Returns:
            Filtered DataFrame with columns: timestamp, value, rep_cty.
        """
        cols = self._detect_lbs_columns(df)
        freq_col = cols.get("freq")
        measure_col = cols.get("measure")
        position_col = cols.get("position")
        curr_col = cols.get("curr")
        time_col = cols.get("time")
        value_col = cols.get("value")
        rep_cty_col = cols.get("rep_cty")

        logger.debug(
            "LBS columns found: freq=%s, measure=%s, position=%s, curr=%s, "
            "time=%s, value=%s, rep_cty=%s",
            freq_col,
            measure_col,
            position_col,
            curr_col,
            time_col,
            value_col,
            rep_cty_col,
        )

        # Apply filters
        filtered = df.copy()
        filter_map = {freq_col: freq, measure_col: measure, position_col: position, curr_col: curr_type}
        for col, val in filter_map.items():
            if col and col in filtered.columns:
                filtered = filtered[filtered[col] == val]

        # Select and rename output columns
        output_cols = {}
        if time_col:
            output_cols["timestamp"] = time_col
        if value_col:
            output_cols["value"] = value_col
        if rep_cty_col:
            output_cols["rep_cty"] = rep_cty_col

        if not output_cols:
            logger.warning("No output columns found in LBS data")
            return pd.DataFrame(columns=["timestamp", "value", "rep_cty"])

        result = filtered[
            [v for v in output_cols.values() if v in filtered.columns]
        ].copy()
        result = result.rename(columns={v: k for k, v in output_cols.items()})

        # Convert timestamp to datetime (BIS uses YYYY-QN format)
        if "timestamp" in result.columns:
            result["timestamp"] = result["timestamp"].apply(self._parse_bis_quarter)

        # Convert value to numeric
        if "value" in result.columns:
            result["value"] = pd.to_numeric(result["value"], errors="coerce")

        logger.debug("Filtered LBS data: %d rows", len(result))

        return result

    def _parse_bis_quarter(self, quarter_str: str) -> datetime | None:
        """Parse BIS quarter string (YYYY-QN) to datetime.

        Args:
            quarter_str: Quarter string like "2024-Q4".

        Returns:
            Datetime for the end of the quarter, or None if parse fails.
        """
        if pd.isna(quarter_str):
            return None

        try:
            quarter_str_clean = str(quarter_str).strip()
            if "-Q" in quarter_str_clean:
                year_str, q_str = quarter_str_clean.split("-Q")
                year_int = int(year_str)
                q_int = int(q_str)
                # Return end of quarter
                month = q_int * 3
                return datetime(year_int, month, 1, tzinfo=UTC)
            # Fallback: try pandas parsing
            parsed = pd.to_datetime(quarter_str_clean)
            if pd.isna(parsed):
                return None
            return parsed.to_pydatetime().replace(tzinfo=UTC)
        except Exception:
            return None

    def calculate_offshore_usd(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate total offshore USD (excluding US domestic).

        This is the "Eurodollar" total that Hayes references - USD claims
        by non-US banks on non-US residents.

        Args:
            df: Filtered LBS DataFrame with rep_cty column.

        Returns:
            DataFrame with timestamp and offshore_usd_total columns.
        """
        if df.empty:
            return pd.DataFrame(columns=["timestamp", "offshore_usd_total"])

        # Filter out US positions (US = domestic, not offshore)
        offshore = df[~df.get("rep_cty", pd.Series()).isin(["US", "USA", "US1"])]

        if offshore.empty:
            logger.warning("No offshore USD data after filtering")
            return pd.DataFrame(columns=["timestamp", "offshore_usd_total"])

        # Group by timestamp and sum
        result = (
            offshore.groupby("timestamp")["value"]
            .sum()
            .reset_index()
            .rename(columns={"value": "offshore_usd_total"})
        )

        result = result.sort_values("timestamp").reset_index(drop=True)

        logger.info(
            "Calculated offshore USD: %d quarters, latest %.2f trillion",
            len(result),
            result["offshore_usd_total"].iloc[-1] / 1e6 if len(result) > 0 else 0,
        )

        return result

    def get_quarterly_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return time series of offshore USD totals.

        Args:
            df: Filtered LBS DataFrame.

        Returns:
            DataFrame with timestamp and value columns, normalized format.
        """
        offshore = self.calculate_offshore_usd(df)

        if offshore.empty:
            return pd.DataFrame(
                columns=["timestamp", "series_id", "source", "value", "unit"]
            )

        result = pd.DataFrame(
            {
                "timestamp": offshore["timestamp"],
                "series_id": "bis_offshore_usd",
                "source": "bis",
                "value": offshore["offshore_usd_total"],
                "unit": "millions_usd",  # BIS reports in millions
            }
        )

        return result

    async def collect_lbs_usd_claims(self) -> pd.DataFrame:
        """Collect USD cross-border claims from LBS.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch or parsing fails.
        """
        try:
            path = await self._download_and_cache("lbs")
            raw_df = self._parse_lbs_csv(path)

            # Filter for USD claims
            filtered = self.filter_lbs_data(
                raw_df,
                freq="Q",
                measure="S",  # Stocks
                position="C",  # Claims
                curr_type="USD",
            )

            # Calculate quarterly series
            result = self.get_quarterly_series(filtered)

            if result.empty:
                logger.warning("No USD claims data after filtering")
                return pd.DataFrame(
                    columns=["timestamp", "series_id", "source", "value", "unit"]
                )

            logger.info("Collected %d BIS LBS USD claims records", len(result))
            return result

        except Exception as e:
            logger.error("BIS LBS collection failed: %s", e)
            raise CollectorFetchError(f"BIS LBS collection failed: {e}") from e

    async def collect_cbs_usd_claims(self) -> pd.DataFrame:
        """Collect USD claims from CBS (Consolidated Banking Statistics).

        CBS provides claims on ultimate risk basis (accounting for guarantees).

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If data fetch or parsing fails.
        """
        try:
            path = await self._download_and_cache("cbs")
            raw_df = self._parse_cbs_csv(path)

            # CBS has similar structure to LBS
            filtered = self.filter_lbs_data(
                raw_df,
                freq="Q",
                measure="S",
                position="C",
                curr_type="USD",
            )

            # Calculate quarterly series
            result = self.get_quarterly_series(filtered)

            if not result.empty:
                result["series_id"] = "bis_cbs_usd_claims"

            logger.info("Collected %d BIS CBS USD claims records", len(result))
            return result

        except Exception as e:
            logger.error("BIS CBS collection failed: %s", e)
            raise CollectorFetchError(f"BIS CBS collection failed: {e}") from e

    async def get_eurodollar_total(self) -> float | None:
        """Get latest USD cross-border claims total (Eurodollar system size).

        This is the key metric for Hayes' framework - total offshore USD.

        Returns:
            Latest Eurodollar total in millions USD, or None if unavailable.
        """
        try:
            df = await self.collect_lbs_usd_claims()

            if df.empty:
                logger.warning("No Eurodollar data available")
                return None

            # Get most recent value
            latest = df.sort_values("timestamp").iloc[-1]
            value = float(latest["value"])

            logger.info(
                "Latest Eurodollar total: %.2f trillion USD (as of %s)",
                value / 1e6,
                latest["timestamp"],
            )

            return value

        except Exception as e:
            logger.warning("Failed to get Eurodollar total: %s", e)
            return None

    def is_cache_valid(self, dataset: str) -> bool:
        """Check if cache is valid for a dataset.

        Args:
            dataset: Dataset key ("lbs" or "cbs").

        Returns:
            True if cache exists and is fresh, False otherwise.
        """
        cache_path = self._settings.cache_dir / "bis" / f"{dataset}.csv"

        if not cache_path.exists():
            return False

        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=UTC)
        age = datetime.now(UTC) - mtime

        return age.days < self.CACHE_DAYS

    def clear_cache(self, dataset: str | None = None) -> None:
        """Clear cached BIS data.

        Args:
            dataset: Specific dataset to clear, or None for all.
        """
        cache_dir = self._settings.cache_dir / "bis"

        if dataset:
            cache_path = cache_dir / f"{dataset}.csv"
            if cache_path.exists():
                cache_path.unlink()
                logger.info("Cleared BIS %s cache", dataset)
        else:
            if cache_dir.exists():
                for f in cache_dir.glob("*.csv"):
                    f.unlink()
                logger.info("Cleared all BIS cache")


# Register collector with the registry
registry.register("bis", BISCollector)
