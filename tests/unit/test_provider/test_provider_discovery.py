"""Tests for OpenBB Provider registration and discovery."""

from liquidity.openbb_ext.provider import liquidity_provider


class TestProviderRegistration:
    """Tests for liquidity_provider object."""

    def test_provider_name(self):
        """Provider name is 'liquidity'."""
        assert liquidity_provider.name == "liquidity"

    def test_provider_has_all_fetchers(self):
        """Provider registers all 3 fetcher commands."""
        expected = {
            "LiquidityNetLiquidity",
            "LiquidityGlobalLiquidity",
            "LiquidityStealthQE",
        }
        assert set(liquidity_provider.fetcher_dict.keys()) == expected

    def test_provider_no_credentials(self):
        """Provider requires no API keys."""
        assert liquidity_provider.credentials == []

    def test_provider_has_description(self):
        """Provider has a non-empty description."""
        assert liquidity_provider.description
        assert len(liquidity_provider.description) > 10


class TestProviderDiscovery:
    """Tests for OpenBB entry point discovery."""

    def test_entry_point_registered(self):
        """liquidity provider is discoverable via entry points."""
        from openbb_core.app.extension_loader import ExtensionLoader

        el = ExtensionLoader()
        providers = el.provider_objects
        assert "liquidity" in providers, (
            f"liquidity not in providers: {list(providers.keys())}"
        )

    def test_discovered_provider_matches(self):
        """Discovered provider matches our registered object."""
        from openbb_core.app.extension_loader import ExtensionLoader

        el = ExtensionLoader()
        discovered = el.provider_objects["liquidity"]
        assert discovered.name == "liquidity"
        assert set(discovered.fetcher_dict.keys()) == set(liquidity_provider.fetcher_dict.keys())
