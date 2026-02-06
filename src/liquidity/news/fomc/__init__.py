"""FOMC-specific news and analysis modules.

This module provides tools for:
- Scraping FOMC statements with 3-tier fallback and caching
- Semantic diff analysis of statement changes
- Real-time statement monitoring with Discord alerts

Example:
    from liquidity.news.fomc import FOMCStatementScraper, FOMCStatement
    from datetime import date

    async with FOMCStatementScraper() as scraper:
        statement = await scraper.fetch(date(2024, 1, 31))
        print(f"Source: {statement.source}, Words: {statement.word_count}")

    # Real-time monitoring
    from liquidity.news.fomc import FOMCStatementWatcher
    watcher = FOMCStatementWatcher(scraper, diff_engine, discord_client)
    await watcher.start()
"""

from liquidity.news.fomc.diff import (
    ChangeScore,
    DiffOp,
    PhraseShift,
    PolicySignal,
    SemanticDiffLayer,
    StatementDiff,
    StatementDiffEngine,
    diff_statements,
)
from liquidity.news.fomc.schemas import FOMCStatement, FOMCStatementCollection
from liquidity.news.fomc.scraper import (
    FOMCScraperError,
    FOMCStatementNotFoundError,
    FOMCStatementScraper,
)
from liquidity.news.fomc.watcher import (
    FOMCStatementWatcher,
    WatcherError,
    WatcherNotRunningError,
    WatcherState,
    create_and_run_watcher,
)

__all__ = [
    # Schemas
    "FOMCStatement",
    "FOMCStatementCollection",
    # Scraper
    "FOMCStatementScraper",
    # Exceptions
    "FOMCScraperError",
    "FOMCStatementNotFoundError",
    # Diff analysis
    "ChangeScore",
    "DiffOp",
    "PhraseShift",
    "PolicySignal",
    "SemanticDiffLayer",
    "StatementDiff",
    "StatementDiffEngine",
    "diff_statements",
    # Watcher (real-time monitoring)
    "FOMCStatementWatcher",
    "WatcherError",
    "WatcherNotRunningError",
    "WatcherState",
    "create_and_run_watcher",
]
