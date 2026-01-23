"""Data collectors for Global Liquidity Monitor.

This module provides the base collector pattern with resilience (retry + circuit breaker)
and a registry for collector discovery.
"""

from liquidity.collectors.base import (
    BaseCollector,
    CollectorCircuitOpenError,
    CollectorError,
    CollectorFetchError,
)
from liquidity.collectors.boc import SERIES_MAP as BOC_SERIES_MAP
from liquidity.collectors.boc import BOCCollector
from liquidity.collectors.boe import BOECollector
from liquidity.collectors.cofer import COFER_SERIES, COFERCollector
from liquidity.collectors.commodities import (
    COMMODITY_SYMBOLS,
    UNIT_MAP as COMMODITY_UNIT_MAP,
    CommodityCollector,
)
from liquidity.collectors.etf_flows import (
    ETF_TICKERS,
    ETF_UNDERLYING,
    ETFFlowCollector,
)
from liquidity.collectors.fed_custody import (
    CUSTODY_SERIES,
    FedCustodyCollector,
)
from liquidity.collectors.fred import SERIES_MAP, FredCollector
from liquidity.collectors.fx import FX_SYMBOLS, FXCollector
from liquidity.collectors.overnight_rates import (
    CORRACollector,
    ESTRCollector,
    SONIACollector,
    calculate_rate_differentials,
)
from liquidity.collectors.pboc import PBOCCollector
from liquidity.collectors.registry import CollectorRegistry, registry
from liquidity.collectors.risk_etfs import (
    RISK_ETF_TICKERS,
    RISK_ETF_TYPE,
    RiskETFCollector,
)
from liquidity.collectors.snb import SNBCollector
from liquidity.collectors.sofr import SOFRCollector
from liquidity.collectors.stress import (
    STRESS_THRESHOLDS,
    StressIndicatorCollector,
)
from liquidity.collectors.tic import (
    COUNTRY_CODES as TIC_COUNTRY_CODES,
    FRED_TIC_SERIES,
    TIC_URLS,
    TICCollector,
)
from liquidity.collectors.yahoo import SYMBOLS as YAHOO_SYMBOLS
from liquidity.collectors.yahoo import YahooCollector

__all__ = [
    # Base
    "BaseCollector",
    "CollectorError",
    "CollectorFetchError",
    "CollectorCircuitOpenError",
    # Registry
    "CollectorRegistry",
    "registry",
    # FRED
    "FredCollector",
    "SERIES_MAP",
    # Yahoo
    "YahooCollector",
    "YAHOO_SYMBOLS",
    # BoC
    "BOCCollector",
    "BOC_SERIES_MAP",
    # SNB
    "SNBCollector",
    # BoE
    "BOECollector",
    # PBoC
    "PBOCCollector",
    # SOFR (Phase 3)
    "SOFRCollector",
    # FX (Phase 3)
    "FXCollector",
    "FX_SYMBOLS",
    # Overnight Rates (Phase 3)
    "ESTRCollector",
    "SONIACollector",
    "CORRACollector",
    "calculate_rate_differentials",
    # Commodities (Phase 4)
    "CommodityCollector",
    "COMMODITY_SYMBOLS",
    "COMMODITY_UNIT_MAP",
    # ETF Flows (Phase 4)
    "ETFFlowCollector",
    "ETF_TICKERS",
    "ETF_UNDERLYING",
    # Risk ETFs (Phase 5)
    "RiskETFCollector",
    "RISK_ETF_TICKERS",
    "RISK_ETF_TYPE",
    # COFER (Phase 5)
    "COFERCollector",
    "COFER_SERIES",
    # Fed Custody (Phase 5)
    "FedCustodyCollector",
    "CUSTODY_SERIES",
    # Stress Indicators (Phase 5)
    "StressIndicatorCollector",
    "STRESS_THRESHOLDS",
    # TIC (Phase 5)
    "TICCollector",
    "TIC_URLS",
    "FRED_TIC_SERIES",
    "TIC_COUNTRY_CODES",
]
