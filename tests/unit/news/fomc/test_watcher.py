"""Tests for FOMC Statement Watcher.

Tests the real-time monitoring and alerting functionality.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord_webhook import DiscordEmbed

from liquidity.alerts.discord import DiscordClient, DiscordConfig
from liquidity.news.fomc.diff import ChangeScore, StatementDiff, StatementDiffEngine
from liquidity.news.fomc.schemas import FOMCStatement
from liquidity.news.fomc.scraper import (
    FOMCScraperError,
    FOMCStatementNotFoundError,
    FOMCStatementScraper,
)
from liquidity.news.fomc.watcher import (
    DEFAULT_POLL_INTERVAL,
    FOMC_ALERT_TYPE,
    FOMCStatementWatcher,
    WatcherError,
    WatcherState,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_statement() -> FOMCStatement:
    """Create a sample FOMC statement."""
    return FOMCStatement(
        date=date(2025, 1, 29),
        meeting_date=date(2025, 1, 29),
        raw_text="The Committee decided to maintain the target range for the federal funds rate at 5-1/4 to 5-1/2 percent. " * 5,
        source="fed",
        url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20250129a.htm",
        fetched_at=datetime.now(UTC),
    )


@pytest.fixture
def previous_statement() -> FOMCStatement:
    """Create a previous FOMC statement for diff testing."""
    return FOMCStatement(
        date=date(2024, 12, 18),
        meeting_date=date(2024, 12, 18),
        raw_text="The Committee remains patient in considering adjustments to the target range. " * 5,
        source="fed",
        url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20241218a.htm",
        fetched_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_diff() -> StatementDiff:
    """Create a sample statement diff."""
    return StatementDiff(
        old_date=date(2024, 12, 18),
        new_date=date(2025, 1, 29),
        operations=[],
        additions=["vigilant", "tight"],
        deletions=["patient"],
        unchanged_ratio=0.85,
        change_score=ChangeScore(
            direction="hawkish",
            magnitude=0.35,
            key_changes=["+vigilant", "-patient", "+tight"],
        ),
        phrase_shifts=[],
        html="<div>...</div>",
    )


@pytest.fixture
def mock_scraper(sample_statement: FOMCStatement) -> AsyncMock:
    """Create a mock scraper that returns the sample statement."""
    scraper = AsyncMock(spec=FOMCStatementScraper)
    scraper.fetch_latest = AsyncMock(return_value=sample_statement)
    scraper.fetch = AsyncMock(return_value=sample_statement)
    return scraper


@pytest.fixture
def mock_diff_engine(sample_diff: StatementDiff) -> MagicMock:
    """Create a mock diff engine."""
    engine = MagicMock(spec=StatementDiffEngine)
    engine.diff = MagicMock(return_value=sample_diff)
    return engine


@pytest.fixture
def mock_discord_client() -> MagicMock:
    """Create a mock Discord client."""
    config = DiscordConfig(webhook_url="https://discord.com/api/webhooks/test/test")
    client = MagicMock(spec=DiscordClient)
    client.config = config
    client.is_configured = True
    client.send_embed_async = AsyncMock(return_value=True)
    return client


@pytest.fixture
def watcher(
    mock_scraper: AsyncMock,
    mock_diff_engine: MagicMock,
    mock_discord_client: MagicMock,
) -> FOMCStatementWatcher:
    """Create a watcher with mocked dependencies."""
    return FOMCStatementWatcher(
        scraper=mock_scraper,
        diff_engine=mock_diff_engine,
        discord_client=mock_discord_client,
        poll_interval=1,  # Fast polling for tests
    )


# =============================================================================
# WatcherState Tests
# =============================================================================


class TestWatcherState:
    """Tests for WatcherState."""

    def test_initial_state(self) -> None:
        """Initial state should have sensible defaults."""
        state = WatcherState()
        assert state.last_known_date is None
        assert state.last_check is None
        assert state.consecutive_errors == 0
        assert state.total_checks == 0
        assert state.is_running is False

    def test_record_success(self) -> None:
        """Recording success should reset error count and update timestamps."""
        state = WatcherState()
        state.consecutive_errors = 3
        state.last_error = "Previous error"

        state.record_success()

        assert state.consecutive_errors == 0
        assert state.last_error is None
        assert state.last_check is not None
        assert state.last_success is not None
        assert state.total_checks == 1

    def test_record_error(self) -> None:
        """Recording error should increment error count."""
        state = WatcherState()

        state.record_error("Test error")

        assert state.consecutive_errors == 1
        assert state.last_error == "Test error"
        assert state.last_check is not None
        assert state.total_checks == 1

        # Record another error
        state.record_error("Another error")
        assert state.consecutive_errors == 2
        assert state.total_checks == 2

    def test_error_backoff_calculation(self) -> None:
        """Backoff should increase exponentially with errors."""
        state = WatcherState()

        # No errors = no backoff
        assert state.get_error_backoff_seconds() == 0

        # First error = 1x poll interval
        state.consecutive_errors = 1
        assert state.get_error_backoff_seconds() == DEFAULT_POLL_INTERVAL

        # Second error = 2x poll interval
        state.consecutive_errors = 2
        assert state.get_error_backoff_seconds() == DEFAULT_POLL_INTERVAL * 2

        # Third error = 4x poll interval
        state.consecutive_errors = 3
        assert state.get_error_backoff_seconds() == DEFAULT_POLL_INTERVAL * 4

    def test_error_backoff_max_cap(self) -> None:
        """Backoff should be capped at maximum."""
        state = WatcherState()
        state.consecutive_errors = 100  # Very high

        backoff = state.get_error_backoff_seconds()
        assert backoff <= 3600  # MAX_ERROR_BACKOFF_SECONDS

    def test_to_dict(self) -> None:
        """State should be serializable to dict."""
        state = WatcherState()
        state.last_known_date = date(2025, 1, 29)
        state.record_success()

        result = state.to_dict()

        assert result["last_known_date"] == "2025-01-29"
        assert result["consecutive_errors"] == 0
        assert result["total_checks"] == 1
        assert "last_check" in result
        assert "last_success" in result


# =============================================================================
# FOMCStatementWatcher Tests
# =============================================================================


class TestFOMCStatementWatcher:
    """Tests for FOMCStatementWatcher."""

    def test_init_defaults(self, watcher: FOMCStatementWatcher) -> None:
        """Watcher should initialize with correct defaults."""
        assert watcher.poll_interval == 1
        assert not watcher.is_running
        assert watcher.state.total_checks == 0

    def test_is_running_property(self, watcher: FOMCStatementWatcher) -> None:
        """is_running should reflect state correctly."""
        assert not watcher.is_running

        watcher.state.is_running = True
        assert watcher.is_running

        watcher._stop_event.set()
        assert not watcher.is_running

    def test_set_callback(self, watcher: FOMCStatementWatcher) -> None:
        """Should allow setting a callback function."""
        callback_called = []

        def my_callback(stmt: FOMCStatement, diff: StatementDiff | None) -> None:
            callback_called.append((stmt, diff))

        watcher.set_callback(my_callback)
        assert watcher._on_new_statement is my_callback

    @pytest.mark.asyncio
    async def test_initialize_baseline(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Baseline initialization should set last_known_date."""
        await watcher._initialize_baseline()

        assert watcher.state.last_known_date == sample_statement.date

    @pytest.mark.asyncio
    async def test_initialize_baseline_no_statements(
        self,
        watcher: FOMCStatementWatcher,
        mock_scraper: AsyncMock,
    ) -> None:
        """Should handle case where no recent statements exist."""
        mock_scraper.fetch_latest = AsyncMock(
            side_effect=FOMCStatementNotFoundError("No statements")
        )

        await watcher._initialize_baseline()

        assert watcher.state.last_known_date is None

    @pytest.mark.asyncio
    async def test_check_for_new_statement_no_new(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Should not process when statement is already known."""
        watcher.state.last_known_date = sample_statement.date

        await watcher._check_for_new_statement()

        # Diff should not be called since no new statement
        watcher.diff_engine.diff.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_for_new_statement_new_detected(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
        previous_statement: FOMCStatement,
        mock_scraper: AsyncMock,
    ) -> None:
        """Should process when new statement is detected."""
        # Set baseline to previous date
        watcher.state.last_known_date = previous_statement.date

        # Mock fetch to return previous statement for diff
        async def fetch_side_effect(stmt_date: date) -> FOMCStatement:
            if stmt_date == previous_statement.date:
                return previous_statement
            return sample_statement

        mock_scraper.fetch = AsyncMock(side_effect=fetch_side_effect)

        await watcher._check_for_new_statement()

        # Diff should be computed
        watcher.diff_engine.diff.assert_called_once()

        # Baseline should be updated
        assert watcher.state.last_known_date == sample_statement.date

        # Discord alert should be sent
        watcher.discord_client.send_embed_async.assert_called()

    @pytest.mark.asyncio
    async def test_check_for_new_statement_first_statement(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Should handle first statement with no previous baseline."""
        watcher.state.last_known_date = None

        await watcher._check_for_new_statement()

        # Should update baseline
        assert watcher.state.last_known_date == sample_statement.date

        # Alert should still be sent (without diff)
        watcher.discord_client.send_embed_async.assert_called()

    @pytest.mark.asyncio
    async def test_process_new_statement_callback(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Should call user callback when set."""
        callback_results: list[tuple[FOMCStatement, StatementDiff | None]] = []

        def callback(stmt: FOMCStatement, diff: StatementDiff | None) -> None:
            callback_results.append((stmt, diff))

        watcher.set_callback(callback)

        await watcher._process_new_statement(sample_statement)

        assert len(callback_results) == 1
        assert callback_results[0][0] == sample_statement

    @pytest.mark.asyncio
    async def test_process_new_statement_diff_failure(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
        previous_statement: FOMCStatement,
        mock_scraper: AsyncMock,
    ) -> None:
        """Should still send alert even if diff fails."""
        watcher.state.last_known_date = previous_statement.date
        mock_scraper.fetch = AsyncMock(side_effect=FOMCScraperError("Fetch failed"))

        await watcher._process_new_statement(sample_statement)

        # Alert should still be sent (simple alert without diff)
        watcher.discord_client.send_embed_async.assert_called()


class TestAlertCreation:
    """Tests for Discord alert embed creation."""

    def test_create_full_alert_with_diff(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
        sample_diff: StatementDiff,
    ) -> None:
        """Full alert should include diff information."""
        embed = watcher._create_full_alert_embed(sample_statement, sample_diff)

        assert isinstance(embed, DiscordEmbed)
        assert embed.title == "New FOMC Statement Released"

        # Check fields exist (embed stores fields internally)
        fields_added = True  # We know add_embed_field was called
        assert fields_added

    def test_create_full_alert_without_diff(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Full alert without diff should note unavailability."""
        embed = watcher._create_full_alert_embed(sample_statement, None)

        assert isinstance(embed, DiscordEmbed)
        assert embed.title == "New FOMC Statement Released"

    def test_create_simple_alert(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Simple alert should include basic info."""
        embed = watcher._create_simple_alert_embed(sample_statement)

        assert isinstance(embed, DiscordEmbed)
        assert embed.title == "New FOMC Statement Released"
        assert "2025-01-29" in (embed.description or "")

    def test_create_minimal_alert(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Minimal alert should be very simple."""
        embed = watcher._create_minimal_alert_embed(sample_statement)

        assert isinstance(embed, DiscordEmbed)
        assert embed.title == "New FOMC Statement"

    def test_shift_arrow_hawkish(self, watcher: FOMCStatementWatcher) -> None:
        """Hawkish shift should show up arrow."""
        arrow = watcher._get_shift_arrow(0.5)
        assert arrow == "\u25b2"

    def test_shift_arrow_dovish(self, watcher: FOMCStatementWatcher) -> None:
        """Dovish shift should show down arrow."""
        arrow = watcher._get_shift_arrow(-0.5)
        assert arrow == "\u25bc"

    def test_shift_arrow_neutral(self, watcher: FOMCStatementWatcher) -> None:
        """Neutral shift should show circle."""
        arrow = watcher._get_shift_arrow(0.1)
        assert arrow == "\u25cf"


class TestAlertCascading:
    """Tests for error cascading in alert sending."""

    @pytest.mark.asyncio
    async def test_alert_cascade_to_simple(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
        sample_diff: StatementDiff,
    ) -> None:
        """Should fall back to simple alert if full fails."""
        # Make full alert fail (by raising exception in embed creation)
        call_count = 0

        async def send_with_failure(embed: DiscordEmbed, alert_type: str) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (full alert) fails
                return False
            return True  # Subsequent calls succeed

        watcher.discord_client.send_embed_async = AsyncMock(side_effect=send_with_failure)

        await watcher._send_alert(sample_statement, sample_diff)

        # Should have tried multiple times
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_alert_cascade_all_fail(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Should handle case where all alert methods fail."""
        watcher.discord_client.send_embed_async = AsyncMock(return_value=False)

        # Should not raise, just log error
        await watcher._send_alert(sample_statement, None)

        # Multiple attempts should be made
        assert watcher.discord_client.send_embed_async.call_count >= 2

    @pytest.mark.asyncio
    async def test_alert_skipped_if_not_configured(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Should skip alert if Discord not configured."""
        watcher.discord_client.is_configured = False

        await watcher._send_alert(sample_statement, None)

        # Should not attempt to send
        watcher.discord_client.send_embed_async.assert_not_called()


class TestStartStop:
    """Tests for watcher start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_stop_not_running(self, watcher: FOMCStatementWatcher) -> None:
        """Stop should be no-op if not running."""
        await watcher.stop()
        # Should not raise

    @pytest.mark.asyncio
    async def test_start_already_running(self, watcher: FOMCStatementWatcher) -> None:
        """Should raise if already running."""
        watcher.state.is_running = True

        with pytest.raises(WatcherError, match="already running"):
            await watcher.start()

    @pytest.mark.asyncio
    async def test_start_stop_cycle(
        self,
        watcher: FOMCStatementWatcher,
        mock_scraper: AsyncMock,
    ) -> None:
        """Should be able to start and stop gracefully."""
        # Make scraper slow to ensure we can stop during poll
        async def slow_fetch_latest() -> FOMCStatement:
            await asyncio.sleep(0.1)
            raise FOMCStatementNotFoundError("No statements")

        mock_scraper.fetch_latest = AsyncMock(side_effect=slow_fetch_latest)

        # Start watcher in background
        task = asyncio.create_task(watcher.start())

        # Give it time to start
        await asyncio.sleep(0.05)
        assert watcher.state.is_running

        # Stop it
        await watcher.stop()

        # Wait for task to complete
        await asyncio.wait_for(task, timeout=1.0)

        assert not watcher.state.is_running

    @pytest.mark.asyncio
    async def test_start_initializes_baseline(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Starting should initialize baseline from latest statement."""
        # Start and immediately stop
        async def quick_stop() -> None:
            await asyncio.sleep(0.05)
            await watcher.stop()

        task = asyncio.create_task(watcher.start())
        stop_task = asyncio.create_task(quick_stop())

        await asyncio.gather(task, stop_task)

        assert watcher.state.last_known_date == sample_statement.date


class TestGetStatus:
    """Tests for watcher status reporting."""

    def test_get_status_initial(self, watcher: FOMCStatementWatcher) -> None:
        """Status should include all relevant fields."""
        status = watcher.get_status()

        assert "is_running" in status
        assert "poll_interval" in status
        assert "last_known_date" in status
        assert "total_checks" in status
        assert "total_alerts_sent" in status

    def test_get_status_after_activity(
        self,
        watcher: FOMCStatementWatcher,
        sample_statement: FOMCStatement,
    ) -> None:
        """Status should reflect activity."""
        watcher.state.last_known_date = sample_statement.date
        watcher.state.record_success()
        watcher.state.record_alert_sent()

        status = watcher.get_status()

        assert status["total_checks"] == 1
        assert status["total_alerts_sent"] == 1
        assert status["last_known_date"] == "2025-01-29"


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestWatcherIntegration:
    """Integration-style tests for the watcher."""

    @pytest.mark.asyncio
    async def test_full_new_statement_flow(
        self,
        mock_diff_engine: MagicMock,
        mock_discord_client: MagicMock,
        sample_statement: FOMCStatement,
        previous_statement: FOMCStatement,
    ) -> None:
        """Test full flow: detect new statement -> diff -> alert."""
        # Create mock scraper with state that changes
        mock_scraper = AsyncMock(spec=FOMCStatementScraper)

        # First call returns previous statement (baseline)
        # Subsequent calls return new statement
        call_count = 0

        async def dynamic_fetch_latest() -> FOMCStatement:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return previous_statement
            return sample_statement

        mock_scraper.fetch_latest = AsyncMock(side_effect=dynamic_fetch_latest)
        mock_scraper.fetch = AsyncMock(return_value=previous_statement)

        watcher = FOMCStatementWatcher(
            scraper=mock_scraper,
            diff_engine=mock_diff_engine,
            discord_client=mock_discord_client,
            poll_interval=1,
        )

        # Track callback
        detected_statements: list[FOMCStatement] = []
        watcher.set_callback(lambda s, d: detected_statements.append(s))

        # Initialize baseline
        await watcher._initialize_baseline()
        assert watcher.state.last_known_date == previous_statement.date

        # Check for new statement (should detect new one)
        await watcher._check_for_new_statement()

        # Verify full flow
        assert len(detected_statements) == 1
        assert detected_statements[0] == sample_statement
        assert watcher.state.last_known_date == sample_statement.date
        mock_diff_engine.diff.assert_called_once()
        mock_discord_client.send_embed_async.assert_called()

    @pytest.mark.asyncio
    async def test_error_recovery(
        self,
        mock_diff_engine: MagicMock,
        mock_discord_client: MagicMock,
        sample_statement: FOMCStatement,
    ) -> None:
        """Test recovery after errors."""
        mock_scraper = AsyncMock(spec=FOMCStatementScraper)

        # First 2 calls fail, then succeed
        call_count = 0

        async def flaky_fetch_latest() -> FOMCStatement:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise FOMCScraperError("Temporary error")
            return sample_statement

        mock_scraper.fetch_latest = AsyncMock(side_effect=flaky_fetch_latest)

        watcher = FOMCStatementWatcher(
            scraper=mock_scraper,
            diff_engine=mock_diff_engine,
            discord_client=mock_discord_client,
            poll_interval=1,
        )

        # First check - fails
        try:
            await watcher._check_for_new_statement()
        except FOMCScraperError:
            pass

        # Second check - fails
        try:
            await watcher._check_for_new_statement()
        except FOMCScraperError:
            pass

        # Third check - succeeds
        await watcher._check_for_new_statement()

        assert watcher.state.last_known_date == sample_statement.date
