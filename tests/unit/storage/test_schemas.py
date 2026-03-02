import pytest

from liquidity.storage.schemas import (
    ALL_SCHEMAS,
    LIQUIDITY_INDEXES_SCHEMA,
    LIQUIDITY_INDEXES_SYMBOLS,
    LIQUIDITY_INDEXES_TABLE,
    RAW_DATA_SCHEMA,
    RAW_DATA_SYMBOLS,
    RAW_DATA_TABLE,
)


def test_table_constants():
    """Test that table name constants are correct."""
    assert RAW_DATA_TABLE == "raw_data"
    assert LIQUIDITY_INDEXES_TABLE == "liquidity_indexes"


def test_schemas_validity():
    """Test that schemas have the correct structural definitions."""
    # Check RAW_DATA schema structure
    assert "CREATE TABLE IF NOT EXISTS raw_data" in RAW_DATA_SCHEMA
    assert "PARTITION BY MONTH" in RAW_DATA_SCHEMA
    assert "WAL" in RAW_DATA_SCHEMA
    assert "DEDUP UPSERT KEYS(timestamp, series_id)" in RAW_DATA_SCHEMA

    # Check LIQUIDITY_INDEXES schema structure
    assert "CREATE TABLE IF NOT EXISTS liquidity_indexes" in LIQUIDITY_INDEXES_SCHEMA
    assert "PARTITION BY MONTH" in LIQUIDITY_INDEXES_SCHEMA
    assert "WAL" in LIQUIDITY_INDEXES_SCHEMA
    assert "DEDUP UPSERT KEYS(timestamp, index_name)" in LIQUIDITY_INDEXES_SCHEMA


def test_all_schemas_list():
    """Test that ALL_SCHEMAS contains all required schemas."""
    assert len(ALL_SCHEMAS) == 2
    assert RAW_DATA_SCHEMA in ALL_SCHEMAS
    assert LIQUIDITY_INDEXES_SCHEMA in ALL_SCHEMAS


def test_symbol_definitions():
    """Test that symbol definitions align with expected dictionary-encoded columns."""
    assert "series_id" in RAW_DATA_SYMBOLS
    assert "source" in RAW_DATA_SYMBOLS
    assert "unit" in RAW_DATA_SYMBOLS

    assert "index_name" in LIQUIDITY_INDEXES_SYMBOLS
    assert "regime" in LIQUIDITY_INDEXES_SYMBOLS
