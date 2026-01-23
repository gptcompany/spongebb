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
from liquidity.collectors.fred import SERIES_MAP, FredCollector
from liquidity.collectors.fx import FX_SYMBOLS, FXCollector
from liquidity.collectors.pboc import PBOCCollector
from liquidity.collectors.registry import CollectorRegistry, registry
from liquidity.collectors.snb import SNBCollector
from liquidity.collectors.sofr import SOFRCollector
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
]
