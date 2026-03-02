"""OpenBB Provider registration for liquidity data.

Exposes:
    obb.liquidity.net_liquidity()     - Fed Net Liquidity (Hayes formula)
    obb.liquidity.global_liquidity()  - Global CB aggregate in USD
    obb.liquidity.stealth_qe()        - Hidden liquidity injection score
"""

from openbb_core.provider.abstract.provider import Provider

from liquidity.openbb_ext.models.global_liquidity import LiquidityGlobalLiquidityFetcher
from liquidity.openbb_ext.models.net_liquidity import LiquidityNetLiquidityFetcher
from liquidity.openbb_ext.models.stealth_qe import LiquidityStealthQEFetcher

liquidity_provider = Provider(
    name="liquidity",
    website="https://github.com/gptcompany/spongebb",
    description="Global liquidity monitoring: Fed Net Liquidity (Hayes), "
    "Global CB aggregate, Stealth QE detection.",
    credentials=[],
    fetcher_dict={
        "LiquidityNetLiquidity": LiquidityNetLiquidityFetcher,
        "LiquidityGlobalLiquidity": LiquidityGlobalLiquidityFetcher,
        "LiquidityStealthQE": LiquidityStealthQEFetcher,
    },
)
