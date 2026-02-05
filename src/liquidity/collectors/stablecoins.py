"""Stablecoin supply collector using DefiLlama API.

Tracks major stablecoins as crypto liquidity proxy.
Stablecoins (~$200B+ market cap) represent a significant pool of USD-denominated
liquidity outside traditional banking.

API Docs: https://defillama.com/docs/api
Base URL: https://stablecoins.llama.fi
No authentication required.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd

from liquidity.collectors.base import BaseCollector, CollectorFetchError
from liquidity.collectors.registry import registry
from liquidity.config import Settings, get_settings

logger = logging.getLogger(__name__)

DEFILLAMA_BASE = "https://stablecoins.llama.fi"

# Top stablecoins to track (by DefiLlama ID slug)
TOP_STABLECOINS = [
    "tether",           # USDT - largest, fiat-backed
    "usd-coin",         # USDC - second largest, fiat-backed
    "dai",              # DAI - crypto-backed (MakerDAO)
    "first-digital-usd",  # FDUSD - Binance ecosystem
    "ethena-usde",      # USDe - algorithmic/derivative
]


class StablecoinCollector(BaseCollector[pd.DataFrame]):
    """Collector for stablecoin supply data from DefiLlama.

    Provides:
    - Total stablecoin market cap
    - Individual stablecoin supply (USDT, USDC, DAI, etc.)
    - Supply by chain (Ethereum, Tron, Solana)
    - Historical market cap

    API Endpoints:
    - All stablecoins: /stablecoins
    - Historical: /stablecoincharts/all

    Example:
        collector = StablecoinCollector()
        try:
            df = await collector.collect()
            print(df)
        finally:
            await collector.close()
    """

    def __init__(
        self,
        name: str = "stablecoins",
        settings: Settings | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize stablecoin collector.

        Args:
            name: Collector name for circuit breaker.
            settings: Optional settings override.
            **kwargs: Additional arguments passed to BaseCollector.
        """
        super().__init__(name=name, settings=settings, **kwargs)
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def collect(
        self,
        include_chain_breakdown: bool = True,
    ) -> pd.DataFrame:
        """Collect current stablecoin supply data.

        Args:
            include_chain_breakdown: Whether to include per-chain supply
                for major stablecoins. Only chains with >$1B supply
                are included to keep data manageable.

        Returns:
            DataFrame with columns: timestamp, series_id, source, value, unit
            - series_id format: STABLECOIN_{symbol} or STABLECOIN_{symbol}_{CHAIN}
            - value in billions USD

        Raises:
            CollectorFetchError: If API request fails after retries.
        """

        async def _fetch() -> pd.DataFrame:
            return await self._fetch_stablecoins(include_chain_breakdown)

        try:
            return await self.fetch_with_retry(_fetch)
        except Exception as e:
            logger.error("Stablecoin fetch failed: %s", e)
            raise CollectorFetchError(f"Stablecoin fetch failed: {e}") from e

    async def _fetch_stablecoins(
        self,
        include_chain_breakdown: bool = True,
    ) -> pd.DataFrame:
        """Fetch stablecoin data from DefiLlama API.

        Args:
            include_chain_breakdown: Include per-chain supply breakdown.

        Returns:
            DataFrame with stablecoin supply data.
        """
        client = await self._get_client()

        url = f"{DEFILLAMA_BASE}/stablecoins"
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()
        pegged_assets = data.get("peggedAssets", [])

        if not pegged_assets:
            logger.warning("No stablecoin data returned from DefiLlama")
            return self._empty_df()

        now = datetime.now(UTC)
        rows = []

        # Calculate total USD-pegged stablecoin market cap
        total_mcap = sum(
            asset.get("circulating", {}).get("peggedUSD", 0)
            for asset in pegged_assets
            if asset.get("pegType") == "peggedUSD"
        )

        rows.append({
            "timestamp": now,
            "series_id": "STABLECOIN_TOTAL_MCAP",
            "source": "defillama",
            "value": total_mcap / 1e9,  # Convert to billions USD
            "unit": "billions_usd",
        })

        # Individual stablecoins from our TOP_STABLECOINS list
        for asset in pegged_assets:
            asset_id = asset.get("id", "").lower()

            # Match by id (DefiLlama uses id field as slug)
            if asset_id not in TOP_STABLECOINS:
                continue

            symbol = asset.get("symbol", "UNKNOWN")
            circulating = asset.get("circulating", {}).get("peggedUSD", 0)

            rows.append({
                "timestamp": now,
                "series_id": f"STABLECOIN_{symbol}",
                "source": "defillama",
                "value": circulating / 1e9,  # billions USD
                "unit": "billions_usd",
            })

            # Chain breakdown for tracked stablecoins (only large chains)
            if include_chain_breakdown:
                chain_data = asset.get("chainCirculating", {})
                for chain, chain_info in chain_data.items():
                    chain_supply = chain_info.get("current", {}).get("peggedUSD", 0)
                    # Only chains with >$1B supply
                    if chain_supply > 1e9:
                        rows.append({
                            "timestamp": now,
                            "series_id": f"STABLECOIN_{symbol}_{chain.upper()}",
                            "source": "defillama",
                            "value": chain_supply / 1e9,
                            "unit": "billions_usd",
                        })

        df = pd.DataFrame(rows)
        logger.info("Fetched %d stablecoin data points from DefiLlama", len(df))
        return df

    async def collect_historical(
        self,
        days: int = 365,
    ) -> pd.DataFrame:
        """Collect historical total stablecoin market cap.

        Args:
            days: Number of days of history to return (from most recent).

        Returns:
            DataFrame with historical market cap data.
            Columns: timestamp, series_id, source, value, unit

        Raises:
            CollectorFetchError: If API request fails after retries.
        """

        async def _fetch() -> pd.DataFrame:
            return await self._fetch_historical(days)

        try:
            return await self.fetch_with_retry(_fetch, breaker_name="stablecoins_hist")
        except Exception as e:
            logger.error("Historical stablecoin fetch failed: %s", e)
            raise CollectorFetchError(f"Historical fetch failed: {e}") from e

    async def _fetch_historical(
        self,
        days: int,
    ) -> pd.DataFrame:
        """Fetch historical stablecoin market cap from DefiLlama.

        Uses the /stablecoincharts/all endpoint which returns
        daily total stablecoin market cap over time.

        Args:
            days: Number of days to return.

        Returns:
            DataFrame with historical data.
        """
        client = await self._get_client()

        url = f"{DEFILLAMA_BASE}/stablecoincharts/all"
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()

        if not data:
            logger.warning("No historical stablecoin data returned")
            return self._empty_df()

        rows = []
        # API returns data sorted by date, take last N days
        for point in data[-days:]:
            date_ts = point.get("date", 0)
            if date_ts == 0:
                continue

            date = datetime.fromtimestamp(date_ts, tz=UTC)
            total_usd = point.get("totalCirculatingUSD", {}).get("peggedUSD", 0)

            rows.append({
                "timestamp": date,
                "series_id": "STABLECOIN_TOTAL_MCAP",
                "source": "defillama",
                "value": total_usd / 1e9,  # billions USD
                "unit": "billions_usd",
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info("Fetched %d historical stablecoin records", len(df))
        return df

    async def collect_market_summary(self) -> dict[str, Any]:
        """Get summary statistics for stablecoin market.

        Convenience method that fetches current data and computes
        key market metrics.

        Returns:
            Dictionary with market summary:
            - total_market_cap_billions: Total stablecoin market cap
            - usdt_billions: USDT supply
            - usdc_billions: USDC supply
            - usdt_dominance: USDT % of total market
            - timestamp: ISO format timestamp
        """
        df = await self.collect(include_chain_breakdown=False)

        # Extract values safely
        total_rows = df[df["series_id"] == "STABLECOIN_TOTAL_MCAP"]
        total = total_rows["value"].iloc[0] if len(total_rows) > 0 else 0.0

        usdt_rows = df[df["series_id"] == "STABLECOIN_USDT"]
        usdt = usdt_rows["value"].iloc[0] if len(usdt_rows) > 0 else 0.0

        usdc_rows = df[df["series_id"] == "STABLECOIN_USDC"]
        usdc = usdc_rows["value"].iloc[0] if len(usdc_rows) > 0 else 0.0

        return {
            "total_market_cap_billions": total,
            "usdt_billions": usdt,
            "usdc_billions": usdc,
            "usdt_dominance": (usdt / total * 100) if total > 0 else 0.0,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def _empty_df(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(
            columns=["timestamp", "series_id", "source", "value", "unit"]
        )

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Register collector
registry.register("stablecoins", StablecoinCollector)
