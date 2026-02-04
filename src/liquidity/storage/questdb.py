"""QuestDB storage layer with ILP ingestion.

Provides high-performance time-series storage using QuestDB:
- ILP (InfluxDB Line Protocol) for fast DataFrame ingestion (28-92x faster than SQL)
- PGWire for schema management and queries
- Automatic timestamp conversion and SYMBOL column handling
"""

import logging
from datetime import datetime
from typing import Any

import pandas as pd
import psycopg2
from questdb.ingress import Sender

from liquidity.config import Settings, get_settings
from liquidity.storage.schemas import (
    ALL_SCHEMAS,
    LIQUIDITY_INDEXES_SYMBOLS,
    LIQUIDITY_INDEXES_TABLE,
    RAW_DATA_SYMBOLS,
    RAW_DATA_TABLE,
)

logger = logging.getLogger(__name__)


class QuestDBStorageError(Exception):
    """Base exception for QuestDB storage errors."""

    pass


class QuestDBConnectionError(QuestDBStorageError):
    """Error connecting to QuestDB."""

    pass


class QuestDBIngestionError(QuestDBStorageError):
    """Error during data ingestion."""

    pass


class QuestDBStorage:
    """QuestDB storage layer for liquidity data.

    Provides methods for:
    - Table creation via PGWire (PostgreSQL wire protocol)
    - High-performance DataFrame ingestion via ILP
    - Data queries via PGWire

    Example:
        storage = QuestDBStorage()
        storage.create_tables()

        # Ingest DataFrame
        df = pd.DataFrame({
            "timestamp": [datetime.now()],
            "series_id": ["WALCL"],
            "source": ["fred"],
            "value": [7500000.0],
            "unit": ["millions_usd"]
        })
        storage.ingest_dataframe("raw_data", df, symbols=["series_id", "source", "unit"])

        # Query data
        result = storage.query("SELECT * FROM raw_data WHERE series_id = 'WALCL' LIMIT 10")
    """

    def __init__(
        self,
        host: str | None = None,
        ilp_port: int | None = None,
        pg_port: int | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize QuestDB storage.

        Args:
            host: QuestDB host address. Defaults to settings value.
            ilp_port: ILP port (9009 by default). Defaults to settings value.
            pg_port: PostgreSQL wire port (8812 by default). Defaults to 8812.
            settings: Optional settings override.
        """
        self._settings = settings or get_settings()
        self.host = host or self._settings.questdb_host
        self.ilp_port = ilp_port or self._settings.questdb_port
        self.pg_port = pg_port or 8812  # Default PGWire port

    def _get_pg_connection(self) -> psycopg2.extensions.connection:
        """Get a PostgreSQL wire protocol connection.

        Returns:
            psycopg2 connection to QuestDB.

        Raises:
            QuestDBConnectionError: If connection fails.
        """
        try:
            return psycopg2.connect(
                host=self.host,
                port=self.pg_port,
                user="admin",
                password="quest",  # nosec B106 - QuestDB default for local dev
                database="qdb",
            )
        except psycopg2.Error as e:
            logger.error("Failed to connect to QuestDB via PGWire: %s", e)
            raise QuestDBConnectionError(f"Failed to connect to QuestDB: {e}") from e

    def create_tables(self) -> None:
        """Create all required tables if they don't exist.

        Uses PGWire to execute DDL statements for table creation.
        Tables are created with WAL and DEDUP UPSERT KEYS.

        Raises:
            QuestDBStorageError: If table creation fails.
        """
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                for schema_sql in ALL_SCHEMAS:
                    # QuestDB doesn't support transactions for DDL, execute directly
                    try:
                        cur.execute(schema_sql)
                        conn.commit()
                        logger.info("Executed schema: %s...", schema_sql[:50])
                    except psycopg2.Error as e:
                        # Table may already exist, log and continue
                        logger.debug("Schema execution note: %s", e)
                        conn.rollback()
        finally:
            conn.close()

        logger.info("Table creation complete")

    def ingest_dataframe(
        self,
        table: str,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp",
        symbols: list[str] | None = None,
    ) -> int:
        """Ingest a DataFrame using ILP protocol.

        ILP is 28-92x faster than row-by-row SQL inserts for bulk data.

        Args:
            table: Target table name.
            df: DataFrame to ingest.
            timestamp_col: Name of the timestamp column.
            symbols: List of columns to treat as SYMBOL type (dictionary-encoded).
                If None, uses default symbols for known tables.

        Returns:
            Number of rows ingested.

        Raises:
            QuestDBIngestionError: If ingestion fails.
        """
        if df.empty:
            logger.warning("Empty DataFrame, nothing to ingest")
            return 0

        # Use default symbols for known tables
        if symbols is None:
            symbols = {
                RAW_DATA_TABLE: RAW_DATA_SYMBOLS,
                LIQUIDITY_INDEXES_TABLE: LIQUIDITY_INDEXES_SYMBOLS,
            }.get(table, [])

        # Ensure timestamp column is datetime
        if timestamp_col in df.columns:
            df = df.copy()
            df[timestamp_col] = pd.to_datetime(df[timestamp_col])

        try:
            with Sender.from_conf(f"tcp::addr={self.host}:{self.ilp_port};") as sender:  # type: ignore[attr-defined]
                sender.dataframe(
                    df, table_name=table, at=timestamp_col, symbols=symbols
                )

            rows = len(df)
            logger.info("Ingested %d rows to table '%s'", rows, table)
            return rows

        except Exception as e:
            logger.error("Failed to ingest data to %s: %s", table, e)
            raise QuestDBIngestionError(f"Ingestion failed: {e}") from e

    def get_latest(
        self, series_id: str, table: str = RAW_DATA_TABLE
    ) -> dict[str, Any] | None:
        """Get the latest data point for a series.

        Useful for freshness checks and incremental updates.

        Args:
            series_id: The series identifier to query.
            table: Table to query. Defaults to raw_data.

        Returns:
            Dict with latest data point, or None if not found.
        """
        sql = f"""
            SELECT * FROM {table}
            WHERE series_id = '{series_id}'
            ORDER BY timestamp DESC
            LIMIT 1
        """  # nosec B608 - table and series_id are internal enums, not user input
        result = self.query(sql)
        if result and len(result) > 0:
            return result[0]
        return None

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts.

        Args:
            sql: SQL query to execute.

        Returns:
            List of dictionaries, one per row.

        Raises:
            QuestDBStorageError: If query fails.
        """
        conn = self._get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = (
                    [desc[0] for desc in cur.description] if cur.description else []
                )
                rows = cur.fetchall()
                return [dict(zip(columns, row, strict=False)) for row in rows]
        except psycopg2.Error as e:
            logger.error("Query failed: %s", e)
            raise QuestDBStorageError(f"Query failed: {e}") from e
        finally:
            conn.close()

    def get_latest_timestamp(
        self, series_id: str, table: str = RAW_DATA_TABLE
    ) -> datetime | None:
        """Get the timestamp of the latest data point for a series.

        Args:
            series_id: The series identifier.
            table: Table to query.

        Returns:
            Latest timestamp as datetime, or None if no data.
        """
        latest = self.get_latest(series_id, table)
        if latest and "timestamp" in latest:
            ts = latest["timestamp"]
            return (
                ts if isinstance(ts, datetime) else pd.to_datetime(ts).to_pydatetime()
            )
        return None

    def health_check(self) -> bool:
        """Check if QuestDB is accessible and healthy.

        Returns:
            True if QuestDB is healthy, False otherwise.
        """
        try:
            result = self.query("SELECT 1 as health")
            return len(result) > 0 and result[0].get("health") == 1
        except Exception as e:
            logger.warning("QuestDB health check failed: %s", e)
            return False

    def __repr__(self) -> str:
        """Return string representation."""
        return f"QuestDBStorage(host={self.host!r}, ilp_port={self.ilp_port}, pg_port={self.pg_port})"
