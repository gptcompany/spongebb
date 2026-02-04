"""Dependency injection for the Liquidity API.

Provides dependency factories for storage and calculator instances.
Uses lru_cache for singleton behavior where appropriate.
"""

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from liquidity.analyzers import RegimeClassifier
from liquidity.analyzers.correlation_engine import CorrelationEngine
from liquidity.calculators import (
    GlobalLiquidityCalculator,
    NetLiquidityCalculator,
    StealthQECalculator,
)
from liquidity.calendar.registry import CalendarRegistry
from liquidity.collectors.fx import FXCollector
from liquidity.collectors.stress import StressIndicatorCollector
from liquidity.config import Settings, get_settings
from liquidity.storage.questdb import QuestDBStorage

logger = logging.getLogger(__name__)


@lru_cache
def get_settings_cached() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings instance (singleton via lru_cache).
    """
    return get_settings()


@lru_cache
def get_storage() -> QuestDBStorage:
    """Get QuestDB storage instance.

    Returns:
        QuestDBStorage instance (singleton via lru_cache).

    Note:
        Connection is lazily established on first query.
    """
    settings = get_settings_cached()
    logger.debug("Creating QuestDBStorage instance")
    return QuestDBStorage(settings=settings)


def get_net_liquidity_calculator(
    settings: Annotated[Settings, Depends(get_settings_cached)],
) -> NetLiquidityCalculator:
    """Get Net Liquidity calculator instance.

    Args:
        settings: Injected settings.

    Returns:
        NetLiquidityCalculator configured with settings.
    """
    return NetLiquidityCalculator(settings=settings)


def get_global_liquidity_calculator(
    settings: Annotated[Settings, Depends(get_settings_cached)],
) -> GlobalLiquidityCalculator:
    """Get Global Liquidity calculator instance.

    Args:
        settings: Injected settings.

    Returns:
        GlobalLiquidityCalculator configured with settings.
    """
    return GlobalLiquidityCalculator(settings=settings)


def get_stealth_qe_calculator(
    settings: Annotated[Settings, Depends(get_settings_cached)],
) -> StealthQECalculator:
    """Get Stealth QE calculator instance.

    Args:
        settings: Injected settings.

    Returns:
        StealthQECalculator configured with settings.
    """
    return StealthQECalculator(settings=settings)


def get_regime_classifier(
    settings: Annotated[Settings, Depends(get_settings_cached)],
) -> RegimeClassifier:
    """Get Regime Classifier instance.

    Args:
        settings: Injected settings.

    Returns:
        RegimeClassifier configured with settings.
    """
    return RegimeClassifier(settings=settings)


def get_fx_collector(
    settings: Annotated[Settings, Depends(get_settings_cached)],
) -> FXCollector:
    """Get FX Collector instance.

    Args:
        settings: Injected settings.

    Returns:
        FXCollector configured with settings.
    """
    return FXCollector(settings=settings)


def get_stress_collector(
    settings: Annotated[Settings, Depends(get_settings_cached)],
) -> StressIndicatorCollector:
    """Get Stress Indicator Collector instance.

    Args:
        settings: Injected settings.

    Returns:
        StressIndicatorCollector configured with settings.
    """
    return StressIndicatorCollector(settings=settings)


def get_correlation_engine(
    settings: Annotated[Settings, Depends(get_settings_cached)],
) -> CorrelationEngine:
    """Get Correlation Engine instance.

    Args:
        settings: Injected settings.

    Returns:
        CorrelationEngine configured with settings.
    """
    return CorrelationEngine(settings=settings)


@lru_cache
def get_calendar_registry() -> CalendarRegistry:
    """Get Calendar Registry instance.

    Returns:
        CalendarRegistry singleton instance.
    """
    return CalendarRegistry()


# Type aliases for dependency injection
StorageDep = Annotated[QuestDBStorage, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_settings_cached)]
NetLiquidityCalcDep = Annotated[NetLiquidityCalculator, Depends(get_net_liquidity_calculator)]
GlobalLiquidityCalcDep = Annotated[
    GlobalLiquidityCalculator, Depends(get_global_liquidity_calculator)
]
StealthQECalcDep = Annotated[StealthQECalculator, Depends(get_stealth_qe_calculator)]
RegimeClassifierDep = Annotated[RegimeClassifier, Depends(get_regime_classifier)]
FXCollectorDep = Annotated[FXCollector, Depends(get_fx_collector)]
StressCollectorDep = Annotated[StressIndicatorCollector, Depends(get_stress_collector)]
CorrelationEngineDep = Annotated[CorrelationEngine, Depends(get_correlation_engine)]
CalendarRegistryDep = Annotated[CalendarRegistry, Depends(get_calendar_registry)]
