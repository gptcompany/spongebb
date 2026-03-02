from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import psycopg2
import pytest

from liquidity.storage.questdb import (
    QuestDBConnectionError,
    QuestDBIngestionError,
    QuestDBStorage,
    QuestDBStorageError,
)
from liquidity.storage.schemas import RAW_DATA_TABLE


@pytest.fixture
def mock_settings():
    class MockSettings:
        questdb_host = "mock-host"
        questdb_port = 9009
    return MockSettings()


@pytest.fixture
def storage(mock_settings):
    return QuestDBStorage(settings=mock_settings)


def test_init_defaults(mock_settings):
    """Test storage initialization defaults."""
    storage = QuestDBStorage(settings=mock_settings)
    assert storage.host == "mock-host"
    assert storage.ilp_port == 9009
    assert storage.pg_port == 8812


def test_init_overrides(mock_settings):
    """Test storage initialization with explicit overrides."""
    storage = QuestDBStorage(host="explicit-host", ilp_port=1234, pg_port=5678, settings=mock_settings)
    assert storage.host == "explicit-host"
    assert storage.ilp_port == 1234
    assert storage.pg_port == 5678


@patch("liquidity.storage.questdb.psycopg2.connect")
def test_get_pg_connection_success(mock_connect, storage):
    """Test successful PG connection."""
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    conn = storage._get_pg_connection()
    assert conn == mock_conn
    mock_connect.assert_called_once_with(
        host="mock-host",
        port=8812,
        user="admin",
        password="quest",
        database="qdb"
    )


@patch("liquidity.storage.questdb.psycopg2.connect")
def test_get_pg_connection_failure(mock_connect, storage):
    """Test connection failure raises specific exception."""
    mock_connect.side_effect = psycopg2.Error("Connection refused")

    with pytest.raises(QuestDBConnectionError, match="Failed to connect to QuestDB: Connection refused"):
        storage._get_pg_connection()


@patch("liquidity.storage.questdb.QuestDBStorage._get_pg_connection")
def test_create_tables_success(mock_get_conn, storage):
    """Test table creation executes schemas successfully."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    storage.create_tables()

    assert mock_cursor.execute.call_count == 2
    assert mock_conn.commit.call_count == 2
    mock_conn.close.assert_called_once()


@patch("liquidity.storage.questdb.QuestDBStorage._get_pg_connection")
def test_create_tables_already_exists(mock_get_conn, storage):
    """Test table creation continues if schema execution fails (e.g. table exists)."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    mock_cursor.execute.side_effect = psycopg2.Error("Table already exists")

    storage.create_tables()

    assert mock_cursor.execute.call_count == 2
    assert mock_conn.rollback.call_count == 2
    mock_conn.close.assert_called_once()


@patch("liquidity.storage.questdb.Sender")
def test_ingest_dataframe_empty(mock_sender, storage):
    """Test ingestion skips empty dataframe."""
    df = pd.DataFrame()
    rows = storage.ingest_dataframe("raw_data", df)

    assert rows == 0
    mock_sender.from_conf.assert_not_called()


@patch("liquidity.storage.questdb.Sender")
def test_ingest_dataframe_success(mock_sender_cls, storage):
    """Test successful dataframe ingestion."""
    mock_sender = MagicMock()
    mock_sender_cls.from_conf.return_value.__enter__.return_value = mock_sender

    df = pd.DataFrame({
        "timestamp": [datetime.now()],
        "series_id": ["WALCL"],
        "value": [100.0]
    })

    rows = storage.ingest_dataframe(RAW_DATA_TABLE, df)

    assert rows == 1
    mock_sender_cls.from_conf.assert_called_once_with("tcp::addr=mock-host:9009;")
    mock_sender.dataframe.assert_called_once()

    # Assert timestamp was parsed and symbols provided correctly
    args, kwargs = mock_sender.dataframe.call_args
    assert kwargs["table_name"] == RAW_DATA_TABLE
    assert kwargs["at"] == "timestamp"
    assert "series_id" in kwargs["symbols"]


@patch("liquidity.storage.questdb.Sender")
def test_ingest_dataframe_failure(mock_sender_cls, storage):
    """Test dataframe ingestion failure."""
    mock_sender_cls.from_conf.side_effect = Exception("Sender connection failed")

    df = pd.DataFrame({
        "timestamp": [datetime.now()],
        "series_id": ["WALCL"],
        "value": [100.0]
    })

    with pytest.raises(QuestDBIngestionError, match="Ingestion failed: Sender connection failed"):
        storage.ingest_dataframe(RAW_DATA_TABLE, df)


@patch("liquidity.storage.questdb.QuestDBStorage.query")
def test_get_latest_found(mock_query, storage):
    """Test retrieving latest row."""
    mock_query.return_value = [{"timestamp": "2026-02-20T00:00:00Z", "series_id": "WALCL", "value": 100.0}]

    result = storage.get_latest("WALCL")

    assert result is not None
    assert result["value"] == 100.0
    mock_query.assert_called_once()
    sql = mock_query.call_args[0][0]
    assert "series_id = 'WALCL'" in sql


@patch("liquidity.storage.questdb.QuestDBStorage.query")
def test_get_latest_not_found(mock_query, storage):
    """Test retrieving latest row when no data."""
    mock_query.return_value = []

    result = storage.get_latest("WALCL")

    assert result is None


@patch("liquidity.storage.questdb.QuestDBStorage._get_pg_connection")
def test_query_success(mock_get_conn, storage):
    """Test executing a query and retrieving results."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    mock_cursor.description = [("timestamp",), ("value",)]
    mock_cursor.fetchall.return_value = [("2026-02-20", 100.0)]

    result = storage.query("SELECT * FROM test")

    assert len(result) == 1
    assert result[0] == {"timestamp": "2026-02-20", "value": 100.0}
    mock_cursor.execute.assert_called_once_with("SELECT * FROM test")


@patch("liquidity.storage.questdb.QuestDBStorage._get_pg_connection")
def test_query_failure(mock_get_conn, storage):
    """Test executing a query when an exception occurs."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_get_conn.return_value = mock_conn

    mock_cursor.execute.side_effect = psycopg2.Error("Bad syntax")

    with pytest.raises(QuestDBStorageError, match="Query failed: Bad syntax"):
        storage.query("SELECT * FROM test")


@patch("liquidity.storage.questdb.QuestDBStorage.get_latest")
def test_get_latest_timestamp(mock_get_latest, storage):
    """Test getting just the latest timestamp."""
    dt = datetime(2026, 2, 20)
    mock_get_latest.return_value = {"timestamp": dt, "value": 100.0}

    result = storage.get_latest_timestamp("WALCL")

    assert result == dt


@patch("liquidity.storage.questdb.QuestDBStorage.get_latest")
def test_get_latest_timestamp_none(mock_get_latest, storage):
    """Test getting latest timestamp when no data exists."""
    mock_get_latest.return_value = None

    result = storage.get_latest_timestamp("WALCL")

    assert result is None


@patch("liquidity.storage.questdb.QuestDBStorage.query")
def test_health_check_healthy(mock_query, storage):
    """Test health check when QuestDB is responsive."""
    mock_query.return_value = [{"health": 1}]
    assert storage.health_check() is True


@patch("liquidity.storage.questdb.QuestDBStorage.query")
def test_health_check_unhealthy(mock_query, storage):
    """Test health check when query fails."""
    mock_query.side_effect = QuestDBStorageError("Connection failed")
    assert storage.health_check() is False
