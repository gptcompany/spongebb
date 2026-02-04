"""Unit tests for Fed Custody Holdings collector (no API key required).

Run with: uv run pytest tests/unit/test_fed_custody.py -v
"""


from liquidity.collectors.fed_custody import (
    CUSTODY_SERIES,
    CUSTODY_UNIT_MAP,
    FedCustodyCollector,
)


class TestCustodySeries:
    """Tests for CUSTODY_SERIES constant."""

    def test_series_mapping_complete(self) -> None:
        """Test that CUSTODY_SERIES has all expected mappings."""
        assert "fed_custody_total" in CUSTODY_SERIES
        assert "fed_custody_treasuries" in CUSTODY_SERIES
        assert "fed_custody_agencies" in CUSTODY_SERIES

        # Verify FRED series IDs
        assert CUSTODY_SERIES["fed_custody_total"] == "WSEFINTL1"
        assert CUSTODY_SERIES["fed_custody_treasuries"] == "WMTSECL1"
        assert CUSTODY_SERIES["fed_custody_agencies"] == "WFASECL1"

    def test_series_count(self) -> None:
        """Test that CUSTODY_SERIES has exactly 3 series."""
        assert len(CUSTODY_SERIES) == 3

    def test_unit_map_complete(self) -> None:
        """Test that all FRED series have unit mappings."""
        for _internal_name, fred_id in CUSTODY_SERIES.items():
            assert fred_id in CUSTODY_UNIT_MAP, f"Missing unit for {fred_id}"
            assert CUSTODY_UNIT_MAP[fred_id] == "millions_usd"


class TestFedCustodyCollectorInit:
    """Tests for FedCustodyCollector initialization (no API calls)."""

    def test_collector_name_default(self) -> None:
        """Test default collector name."""
        collector = FedCustodyCollector()
        assert collector.name == "fed_custody"

    def test_collector_name_custom(self) -> None:
        """Test custom collector name."""
        collector = FedCustodyCollector(name="custom_custody")
        assert collector.name == "custom_custody"

    def test_collector_has_series_map(self) -> None:
        """Test collector exposes CUSTODY_SERIES."""
        assert FedCustodyCollector.CUSTODY_SERIES == CUSTODY_SERIES

    def test_collector_repr(self) -> None:
        """Test collector string representation."""
        collector = FedCustodyCollector()
        assert "FedCustodyCollector" in repr(collector)
        assert "fed_custody" in repr(collector)


class TestRegistryIntegration:
    """Test registry integration (no API calls)."""

    def test_collector_registered(self) -> None:
        """Test that fed_custody is registered in the registry."""
        from liquidity.collectors import registry

        assert "fed_custody" in registry.list_collectors()

    def test_get_collector_class(self) -> None:
        """Test getting collector class from registry."""
        from liquidity.collectors import registry

        collector_cls = registry.get("fed_custody")
        assert collector_cls is FedCustodyCollector

    def test_instantiate_from_registry(self) -> None:
        """Test instantiating collector from registry."""
        from liquidity.collectors import registry

        collector_cls = registry.get("fed_custody")
        collector = collector_cls()
        assert isinstance(collector, FedCustodyCollector)
        assert collector.name == "fed_custody"
