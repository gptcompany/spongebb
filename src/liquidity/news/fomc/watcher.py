"""FOMC Statement Watcher with real-time monitoring.

Monitors Fed RSS feed for new FOMC statements and triggers an alert pipeline:
RSS Monitor -> Detect New Statement -> Fetch Full Text -> Compute Diff -> Discord Alert

Target latency: <60s from statement publication.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable

from discord_webhook import DiscordEmbed

from liquidity.alerts.discord import DiscordClient
from liquidity.news.fomc.diff import StatementDiff, StatementDiffEngine
from liquidity.news.fomc.schemas import FOMCStatement
from liquidity.news.fomc.scraper import (
    FOMCScraperError,
    FOMCStatementNotFoundError,
    FOMCStatementScraper,
)

logger = logging.getLogger(__name__)

# Alert type for rate limiting
FOMC_ALERT_TYPE = "fomc_statement"

# Default poll interval
DEFAULT_POLL_INTERVAL = 60  # seconds

# Error backoff settings
MAX_CONSECUTIVE_ERRORS = 5
ERROR_BACKOFF_MULTIPLIER = 2
MAX_ERROR_BACKOFF_SECONDS = 3600  # 1 hour max backoff


class WatcherError(Exception):
    """Base exception for watcher errors."""

    pass


class WatcherNotRunningError(WatcherError):
    """Watcher is not running."""

    pass


@dataclass
class WatcherState:
    """Runtime state for the FOMC statement watcher.

    Tracks the last known statement date, error counts, and monitoring status.
    """

    last_known_date: date | None = None
    last_check: datetime | None = None
    last_success: datetime | None = None
    consecutive_errors: int = 0
    total_checks: int = 0
    total_alerts_sent: int = 0
    is_running: bool = False
    last_error: str | None = None

    def record_success(self) -> None:
        """Record a successful check."""
        now = datetime.now(UTC)
        self.last_check = now
        self.last_success = now
        self.consecutive_errors = 0
        self.total_checks += 1
        self.last_error = None

    def record_error(self, error: str) -> None:
        """Record a failed check."""
        self.last_check = datetime.now(UTC)
        self.consecutive_errors += 1
        self.total_checks += 1
        self.last_error = error

    def record_alert_sent(self) -> None:
        """Record an alert being sent."""
        self.total_alerts_sent += 1

    def get_error_backoff_seconds(self) -> int:
        """Calculate backoff seconds based on consecutive errors."""
        if self.consecutive_errors == 0:
            return 0
        backoff = DEFAULT_POLL_INTERVAL * (ERROR_BACKOFF_MULTIPLIER ** (self.consecutive_errors - 1))
        return int(min(backoff, MAX_ERROR_BACKOFF_SECONDS))

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "last_known_date": self.last_known_date.isoformat() if self.last_known_date else None,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "consecutive_errors": self.consecutive_errors,
            "total_checks": self.total_checks,
            "total_alerts_sent": self.total_alerts_sent,
            "is_running": self.is_running,
            "last_error": self.last_error,
        }


@dataclass
class FOMCStatementWatcher:
    """Real-time FOMC statement watcher with Discord alerting.

    Monitors the Federal Reserve for new FOMC statements, computes diffs
    against the previous statement, and sends Discord alerts with sentiment analysis.

    Features:
    - Configurable poll interval (default: 60s)
    - Automatic diff computation on new statements
    - Discord alerts with hawkish/dovish shift indicator
    - Error cascading with fallbacks to simpler alerts
    - Exponential backoff on consecutive errors
    - Graceful start/stop lifecycle

    Example:
        async with FOMCStatementScraper() as scraper:
            diff_engine = StatementDiffEngine()
            discord_client = create_discord_client()

            watcher = FOMCStatementWatcher(
                scraper=scraper,
                diff_engine=diff_engine,
                discord_client=discord_client,
            )

            await watcher.start()  # Blocks until stop() is called

    Attributes:
        scraper: FOMCStatementScraper instance for fetching statements.
        diff_engine: StatementDiffEngine for computing diffs.
        discord_client: DiscordClient for sending alerts.
        poll_interval: Seconds between RSS checks (default: 60).
        state: WatcherState tracking runtime metrics.
    """

    scraper: FOMCStatementScraper
    diff_engine: StatementDiffEngine
    discord_client: DiscordClient
    poll_interval: int = DEFAULT_POLL_INTERVAL
    state: WatcherState = field(default_factory=WatcherState)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    _task: asyncio.Task[None] | None = field(default=None, repr=False)
    _on_new_statement: Callable[[FOMCStatement, StatementDiff | None], None] | None = field(
        default=None, repr=False
    )

    def __post_init__(self) -> None:
        """Initialize after dataclass creation."""
        # Ensure stop event is created
        if self._stop_event is None:
            self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        """Check if watcher is currently running."""
        return self.state.is_running and not self._stop_event.is_set()

    def set_callback(
        self, callback: Callable[[FOMCStatement, StatementDiff | None], None]
    ) -> None:
        """Set callback function called when new statement is detected.

        Args:
            callback: Function called with (statement, diff) arguments.
                     diff may be None if this is the first statement.
        """
        self._on_new_statement = callback

    async def start(self) -> None:
        """Start continuous monitoring loop.

        This method blocks until stop() is called. It polls the Fed RSS
        feed at the configured interval and processes any new statements.

        Raises:
            WatcherError: If watcher is already running.
        """
        if self.state.is_running:
            raise WatcherError("Watcher is already running")

        self._stop_event.clear()
        self.state.is_running = True

        logger.info(
            "FOMC Statement Watcher started (poll_interval=%ds)",
            self.poll_interval,
        )

        try:
            # Initialize with the most recent known statement
            await self._initialize_baseline()

            # Main monitoring loop
            while not self._stop_event.is_set():
                try:
                    await self._check_for_new_statement()
                    self.state.record_success()
                except FOMCScraperError as e:
                    self.state.record_error(str(e))
                    logger.warning(
                        "Check failed (attempt %d): %s",
                        self.state.consecutive_errors,
                        e,
                    )
                    # Check if we should give up after too many errors
                    if self.state.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(
                            "Max consecutive errors (%d) reached, continuing with backoff",
                            MAX_CONSECUTIVE_ERRORS,
                        )
                except Exception as e:
                    self.state.record_error(f"Unexpected: {type(e).__name__}: {e}")
                    logger.exception("Unexpected error during check: %s", e)

                # Calculate next poll time (with error backoff if needed)
                wait_time = self.poll_interval + self.state.get_error_backoff_seconds()

                # Wait for next poll or stop signal
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=wait_time,
                    )
                    # Stop event was set
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue polling
                    pass

        finally:
            self.state.is_running = False
            logger.info(
                "FOMC Statement Watcher stopped (total_checks=%d, total_alerts=%d)",
                self.state.total_checks,
                self.state.total_alerts_sent,
            )

    async def stop(self) -> None:
        """Stop monitoring gracefully.

        Signals the monitoring loop to exit on its next iteration.
        This method returns immediately; the loop will stop shortly after.
        """
        if not self.state.is_running:
            logger.debug("Watcher not running, nothing to stop")
            return

        logger.info("Stopping FOMC Statement Watcher...")
        self._stop_event.set()

    async def _initialize_baseline(self) -> None:
        """Initialize baseline with most recent statement.

        Fetches the latest known statement to establish a baseline
        for diff comparisons. Does not send alerts for the baseline.
        """
        try:
            latest = await self.scraper.fetch_latest()
            self.state.last_known_date = latest.date
            logger.info(
                "Baseline established: most recent statement from %s",
                latest.date,
            )
        except FOMCStatementNotFoundError:
            logger.warning(
                "No recent statements found for baseline, will alert on first detection"
            )
            self.state.last_known_date = None

    async def _check_for_new_statement(self) -> None:
        """Check for new statement and process if found.

        Fetches the latest statement and compares against baseline.
        If a new statement is detected, triggers the full processing pipeline.
        """
        try:
            latest = await self.scraper.fetch_latest()
        except FOMCStatementNotFoundError:
            # No statement found - not an error, just nothing new
            logger.debug("No recent statements found")
            return

        # Check if this is a new statement
        if self.state.last_known_date is None:
            # First statement since watcher started
            logger.info("First statement detected: %s", latest.date)
            await self._process_new_statement(latest)
        elif latest.date > self.state.last_known_date:
            # New statement!
            logger.info(
                "New FOMC statement detected: %s (previous: %s)",
                latest.date,
                self.state.last_known_date,
            )
            await self._process_new_statement(latest)
        else:
            logger.debug(
                "No new statement (latest: %s, known: %s)",
                latest.date,
                self.state.last_known_date,
            )

    async def _process_new_statement(self, new_statement: FOMCStatement) -> None:
        """Process new statement: diff, analyze, and alert.

        Implements error cascading with fallbacks:
        1. Full alert: diff + sentiment shift
        2. Simple alert: just the statement info (if diff fails)
        3. Minimal alert: basic notification (if everything fails)

        Args:
            new_statement: The newly detected FOMCStatement.
        """
        previous_date = self.state.last_known_date
        diff: StatementDiff | None = None

        # Try to compute diff against previous statement
        if previous_date is not None:
            try:
                previous = await self.scraper.fetch(previous_date)
                diff = self.diff_engine.diff(
                    old_text=previous.raw_text,
                    new_text=new_statement.raw_text,
                    old_date=previous.date,
                    new_date=new_statement.date,
                )
                logger.info(
                    "Diff computed: %s shift (%.2f), unchanged: %.1f%%",
                    diff.change_score.direction,
                    diff.change_score.magnitude,
                    diff.unchanged_ratio * 100,
                )
            except Exception as e:
                logger.warning("Failed to compute diff: %s", e)
                # Continue without diff

        # Update baseline
        self.state.last_known_date = new_statement.date

        # Call user callback if set
        if self._on_new_statement is not None:
            try:
                self._on_new_statement(new_statement, diff)
            except Exception as e:
                logger.warning("Callback error: %s", e)

        # Send Discord alert with error cascading
        await self._send_alert(new_statement, diff)

    async def _send_alert(
        self,
        statement: FOMCStatement,
        diff: StatementDiff | None,
    ) -> None:
        """Send Discord alert with error cascading.

        Attempts to send a rich alert with diff info, falling back to
        simpler formats if components fail.

        Args:
            statement: The new FOMCStatement.
            diff: Optional StatementDiff (may be None if diff failed).
        """
        if not self.discord_client.is_configured:
            logger.warning("Discord not configured, skipping alert")
            return

        # Try full alert first
        try:
            embed = self._create_full_alert_embed(statement, diff)
            success = await self.discord_client.send_embed_async(embed, FOMC_ALERT_TYPE)
            if success:
                self.state.record_alert_sent()
                logger.info("Full alert sent for statement %s", statement.date)
                return
        except Exception as e:
            logger.warning("Full alert failed: %s, trying simple alert", e)

        # Fallback to simple alert
        try:
            embed = self._create_simple_alert_embed(statement)
            success = await self.discord_client.send_embed_async(embed, FOMC_ALERT_TYPE)
            if success:
                self.state.record_alert_sent()
                logger.info("Simple alert sent for statement %s", statement.date)
                return
        except Exception as e:
            logger.warning("Simple alert failed: %s, trying minimal alert", e)

        # Final fallback: minimal alert
        try:
            embed = self._create_minimal_alert_embed(statement)
            success = await self.discord_client.send_embed_async(embed, FOMC_ALERT_TYPE)
            if success:
                self.state.record_alert_sent()
                logger.info("Minimal alert sent for statement %s", statement.date)
        except Exception as e:
            logger.error("All alert methods failed: %s", e)

    def _create_full_alert_embed(
        self,
        statement: FOMCStatement,
        diff: StatementDiff | None,
    ) -> DiscordEmbed:
        """Create full alert embed with diff information.

        Format:
        Title: New FOMC Statement Released
        Date: 2025-01-29
        Shift: HAWKISH (+0.35) or DOVISH (-0.20) or NEUTRAL (0.00)
        Key Changes: +vigilant, -patient, +tight
        Unchanged: 85%
        [View Statement](url)

        Args:
            statement: The FOMCStatement.
            diff: The StatementDiff (may be None).

        Returns:
            DiscordEmbed for the full alert.
        """
        embed = DiscordEmbed(
            title="New FOMC Statement Released",
            color="1a73e8",  # Fed blue
        )

        # Date field
        embed.add_embed_field(
            name="Date",
            value=statement.date.strftime("%Y-%m-%d"),
            inline=True,
        )

        # Sentiment shift (if diff available)
        if diff is not None:
            direction = diff.change_score.direction.upper()
            magnitude = diff.change_score.magnitude
            arrow = self._get_shift_arrow(magnitude)
            shift_str = f"{arrow} {direction} ({magnitude:+.2f})"
            embed.add_embed_field(
                name="Shift",
                value=shift_str,
                inline=True,
            )

            # Key changes
            if diff.change_score.key_changes:
                changes = ", ".join(diff.change_score.key_changes[:5])
                embed.add_embed_field(
                    name="Key Changes",
                    value=changes,
                    inline=False,
                )

            # Unchanged ratio
            unchanged_pct = diff.unchanged_ratio * 100
            embed.add_embed_field(
                name="Unchanged",
                value=f"{unchanged_pct:.0f}%",
                inline=True,
            )
        else:
            embed.add_embed_field(
                name="Note",
                value="Diff analysis unavailable",
                inline=True,
            )

        # Link to statement
        embed.add_embed_field(
            name="Link",
            value=f"[View Statement]({statement.url})",
            inline=False,
        )

        # Word count
        embed.set_footer(text=f"Word count: {statement.word_count}")

        return embed

    def _create_simple_alert_embed(self, statement: FOMCStatement) -> DiscordEmbed:
        """Create simple alert embed without diff information.

        Args:
            statement: The FOMCStatement.

        Returns:
            DiscordEmbed for the simple alert.
        """
        embed = DiscordEmbed(
            title="New FOMC Statement Released",
            description=f"Date: {statement.date.strftime('%Y-%m-%d')}",
            color="1a73e8",
        )

        embed.add_embed_field(
            name="Source",
            value=statement.source,
            inline=True,
        )

        embed.add_embed_field(
            name="Word Count",
            value=str(statement.word_count),
            inline=True,
        )

        embed.add_embed_field(
            name="Link",
            value=f"[View Statement]({statement.url})",
            inline=False,
        )

        return embed

    def _create_minimal_alert_embed(self, statement: FOMCStatement) -> DiscordEmbed:
        """Create minimal alert embed as last resort.

        Args:
            statement: The FOMCStatement.

        Returns:
            DiscordEmbed for the minimal alert.
        """
        return DiscordEmbed(
            title="New FOMC Statement",
            description=f"Date: {statement.date}\nURL: {statement.url}",
            color="1a73e8",
        )

    @staticmethod
    def _get_shift_arrow(magnitude: float) -> str:
        """Get directional arrow based on magnitude.

        Args:
            magnitude: Score magnitude (-1 to +1).

        Returns:
            Arrow string.
        """
        if magnitude > 0.2:
            return "\u25b2"  # Up arrow (hawkish)
        elif magnitude < -0.2:
            return "\u25bc"  # Down arrow (dovish)
        else:
            return "\u25cf"  # Circle (neutral)

    def get_status(self) -> dict[str, Any]:
        """Get current watcher status.

        Returns:
            Dictionary with watcher status and metrics.
        """
        return {
            "is_running": self.is_running,
            "poll_interval": self.poll_interval,
            **self.state.to_dict(),
        }


async def create_and_run_watcher(
    discord_webhook_url: str | None = None,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
) -> FOMCStatementWatcher:
    """Factory function to create and start watcher.

    Convenience function for creating a fully configured watcher
    with default components.

    Args:
        discord_webhook_url: Discord webhook URL. If None, reads from env.
        poll_interval: Seconds between polls.

    Returns:
        Configured and started FOMCStatementWatcher.
    """
    from liquidity.alerts.discord import create_discord_client

    async with FOMCStatementScraper() as scraper:
        discord_client = create_discord_client(webhook_url=discord_webhook_url)

        watcher = FOMCStatementWatcher(
            scraper=scraper,
            diff_engine=StatementDiffEngine(),
            discord_client=discord_client,
            poll_interval=poll_interval,
        )

        await watcher.start()
        return watcher
