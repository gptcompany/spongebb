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
from liquidity.collectors.bis import (
    BIS_COLUMN_MAPPING,
    LBS_DIMENSION_CODES,
    BISCollector,
)
from liquidity.collectors.boc import SERIES_MAP as BOC_SERIES_MAP
from liquidity.collectors.boc import BOCCollector
from liquidity.collectors.boe import BOECollector
from liquidity.collectors.cftc_cot import (
    COMMODITY_MAP as CFTC_COMMODITY_MAP,
)
from liquidity.collectors.cftc_cot import (
    POSITION_FIELDS as CFTC_POSITION_FIELDS,
)
from liquidity.collectors.cftc_cot import (
    CFTCCOTCollector,
)
from liquidity.collectors.china_rates import (
    SHIBOR_TENORS,
    ChinaRatesCollector,
)
from liquidity.collectors.cofer import COFER_SERIES, COFERCollector
from liquidity.collectors.commodities import (
    COMMODITY_SYMBOLS,
    CommodityCollector,
)
from liquidity.collectors.commodities import (
    UNIT_MAP as COMMODITY_UNIT_MAP,
)
from liquidity.collectors.consumer_credit import (
    ALL_CONSUMER_SERIES,
    CONSUMER_SERIES,
    WEEKLY_HF_SERIES,
    ConsumerCreditCollector,
)
from liquidity.collectors.consumer_credit_risk import (
    CREDIT_RISK_SERIES_MAP,
    DEFAULT_SENSITIVE_STOCKS,
    MARKET_PAIR_SYMBOLS,
    ConsumerCreditRiskCollector,
)
from liquidity.collectors.credit import (
    CP_SERIES,
    LENDING_THRESHOLDS,
    SLOOS_SERIES,
    CreditCollector,
)
from liquidity.collectors.eia import (
    CUSHING_CAPACITY_KB as EIA_CUSHING_CAPACITY_KB,
)
from liquidity.collectors.eia import (
    ROUTE_MAP as EIA_ROUTE_MAP,
)
from liquidity.collectors.eia import (
    SERIES_MAP as EIA_SERIES_MAP,
)
from liquidity.collectors.eia import (
    UNIT_MAP as EIA_UNIT_MAP,
)
from liquidity.collectors.eia import (
    UTILIZATION_THRESHOLDS as EIA_UTILIZATION_THRESHOLDS,
)
from liquidity.collectors.eia import (
    EIACollector,
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
from liquidity.collectors.nyfed import NYFedCollector
from liquidity.collectors.oil_term_structure import (
    SERIES_MAP as OIL_TS_SERIES_MAP,
)
from liquidity.collectors.oil_term_structure import (
    UNIT_MAP as OIL_TS_UNIT_MAP,
)
from liquidity.collectors.oil_term_structure import (
    OilTermStructureCollector,
)
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
from liquidity.collectors.stablecoins import TOP_STABLECOINS, StablecoinCollector
from liquidity.collectors.stress import (
    STRESS_THRESHOLDS,
    StressIndicatorCollector,
)
from liquidity.collectors.swap_lines import SWAP_PARTNERS, SwapLinesCollector
from liquidity.collectors.tga_daily import TGADailyCollector
from liquidity.collectors.tic import (
    COUNTRY_CODES as TIC_COUNTRY_CODES,
)
from liquidity.collectors.tic import (
    FRED_TIC_SERIES,
    TIC_URLS,
    TICCollector,
)
from liquidity.collectors.xccy_basis import (
    STRESS_THRESHOLDS as XCCY_STRESS_THRESHOLDS,
)
from liquidity.collectors.xccy_basis import (
    XCcyBasisCollector,
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
    # Credit Market (Phase 6)
    "CreditCollector",
    "SLOOS_SERIES",
    "CP_SERIES",
    "LENDING_THRESHOLDS",
    # BIS International Banking (Phase 6)
    "BISCollector",
    "LBS_DIMENSION_CODES",
    "BIS_COLUMN_MAPPING",
    # TIC (Phase 5)
    "TICCollector",
    "TIC_URLS",
    "FRED_TIC_SERIES",
    "TIC_COUNTRY_CODES",
    # NY Fed (Phase 11)
    "NYFedCollector",
    "SwapLinesCollector",
    "SWAP_PARTNERS",
    # China Rates (Phase 11)
    "ChinaRatesCollector",
    "SHIBOR_TENORS",
    # Stablecoins (Phase 11)
    "StablecoinCollector",
    "TOP_STABLECOINS",
    # Consumer Credit (Phase 11)
    "ConsumerCreditCollector",
    "CONSUMER_SERIES",
    "ALL_CONSUMER_SERIES",
    "WEEKLY_HF_SERIES",
    # Consumer Credit Risk (Phase 20)
    "ConsumerCreditRiskCollector",
    "CREDIT_RISK_SERIES_MAP",
    "MARKET_PAIR_SYMBOLS",
    "DEFAULT_SENSITIVE_STOCKS",
    # Cross-Currency Basis (Phase 11)
    "XCcyBasisCollector",
    "XCCY_STRESS_THRESHOLDS",
    # TGA Daily (Phase 11)
    "TGADailyCollector",
    # EIA Petroleum (Phase 16)
    "EIACollector",
    "EIA_SERIES_MAP",
    "EIA_UNIT_MAP",
    "EIA_ROUTE_MAP",
    "EIA_CUSHING_CAPACITY_KB",
    "EIA_UTILIZATION_THRESHOLDS",
    # CFTC COT (Phase 17)
    "CFTCCOTCollector",
    "CFTC_COMMODITY_MAP",
    "CFTC_POSITION_FIELDS",
    # Oil Term Structure (Phase 18)
    "OilTermStructureCollector",
    "OIL_TS_SERIES_MAP",
    "OIL_TS_UNIT_MAP",
]
