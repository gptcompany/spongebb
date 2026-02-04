"""Tests for alert scheduler."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from liquidity.alerts.config import AlertConfig
from liquidity.alerts.handlers import AlertHandlers
from liquidity.alerts.scheduler import AlertScheduler, FullAlertScheduler


@pytest.fixture
def mock_handlers() -> MagicMock:
    """Create mock alert handlers."""
    return MagicMock(spec=AlertHandlers)


@pytest.fixture
def alert_config() -> AlertConfig:
    """Create test alert configuration."""
    return AlertConfig(
        enabled=True,
        check_interval_seconds=1,  # Short interval for tests
    )


@pytest.fixture
def scheduler(mock_handlers: MagicMock, alert_config: AlertConfig) -> AlertScheduler:
    """Create alert scheduler with mock handlers."""
    return AlertScheduler(mock_handlers, alert_config)


class TestAlertSchedulerInit:
    """Tests for AlertScheduler initialization."""

    def test_init_default_interval(
        self, mock_handlers: MagicMock, alert_config: AlertConfig
    ) -> None:
        """Test initialization with default interval."""
        scheduler = AlertScheduler(mock_handlers, alert_config)

        assert scheduler._interval == 1
        assert scheduler.is_running is False
        assert scheduler.last_check is None
        assert scheduler.check_count == 0

    def test_init_custom_interval(
        self, mock_handlers: MagicMock, alert_config: AlertConfig
    ) -> None:
        """Test initialization with custom interval."""
        scheduler = AlertScheduler(
            mock_handlers, alert_config, check_interval_seconds=10
        )

        assert scheduler._interval == 10


class TestAlertSchedulerProperties:
    """Tests for AlertScheduler properties."""

    def test_is_running(self, scheduler: AlertScheduler) -> None:
        """Test is_running property."""
        assert scheduler.is_running is False

        scheduler._running = True
        assert scheduler.is_running is True

    def test_last_check(self, scheduler: AlertScheduler) -> None:
        """Test last_check property."""
        assert scheduler.last_check is None

    def test_check_count(self, scheduler: AlertScheduler) -> None:
        """Test check_count property."""
        assert scheduler.check_count == 0


class TestAlertSchedulerCallbacks:
    """Tests for callback registration."""

    def test_register_check(self, scheduler: AlertScheduler) -> None:
        """Test registering a check callback."""
        async def custom_check() -> None:
            pass

        scheduler.register_check(custom_check)

        assert len(scheduler._check_callbacks) == 1

    def test_multiple_callbacks(self, scheduler: AlertScheduler) -> None:
        """Test registering multiple callbacks."""
        async def check1() -> None:
            pass

        async def check2() -> None:
            pass

        scheduler.register_check(check1)
        scheduler.register_check(check2)

        assert len(scheduler._check_callbacks) == 2


class TestAlertSchedulerRunOnce:
    """Tests for run_once method."""

    @pytest.mark.asyncio
    async def test_run_once(self, scheduler: AlertScheduler) -> None:
        """Test running checks once."""
        await scheduler.run_once()

        assert scheduler.last_check is not None
        assert scheduler.check_count == 1

    @pytest.mark.asyncio
    async def test_run_once_calls_callbacks(self, scheduler: AlertScheduler) -> None:
        """Test that run_once calls registered callbacks."""
        callback_called = False

        async def custom_check() -> None:
            nonlocal callback_called
            callback_called = True

        scheduler.register_check(custom_check)
        await scheduler.run_once()

        assert callback_called is True

    @pytest.mark.asyncio
    async def test_run_once_handles_callback_errors(
        self, scheduler: AlertScheduler
    ) -> None:
        """Test that run_once handles callback errors gracefully."""
        async def failing_check() -> None:
            raise ValueError("Test error")

        scheduler.register_check(failing_check)

        # Should not raise
        await scheduler.run_once()
        assert scheduler.check_count == 1


class TestAlertSchedulerStop:
    """Tests for stop method."""

    def test_stop(self, scheduler: AlertScheduler) -> None:
        """Test stopping the scheduler."""
        scheduler._running = True
        scheduler.stop()

        assert scheduler.is_running is False

    def test_stop_when_not_running(self, scheduler: AlertScheduler) -> None:
        """Test stopping when not running."""
        scheduler.stop()  # Should not raise
        assert scheduler.is_running is False


class TestAlertSchedulerStart:
    """Tests for start method."""

    @pytest.mark.asyncio
    async def test_start_and_stop(
        self, mock_handlers: MagicMock, alert_config: AlertConfig
    ) -> None:
        """Test starting and stopping the scheduler."""
        scheduler = AlertScheduler(
            mock_handlers, alert_config, check_interval_seconds=60
        )

        # Start in background
        task = asyncio.create_task(scheduler.start())

        # Let it run briefly
        await asyncio.sleep(0.1)
        assert scheduler.is_running is True

        # Stop it
        scheduler.stop()
        await asyncio.sleep(0.1)

        # Task should complete
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_start_already_running(self, scheduler: AlertScheduler) -> None:
        """Test starting when already running."""
        scheduler._running = True

        # Should return immediately
        await scheduler.start()


class TestAlertSchedulerRepr:
    """Tests for string representation."""

    def test_repr_stopped(self, scheduler: AlertScheduler) -> None:
        """Test repr when stopped."""
        repr_str = repr(scheduler)

        assert "AlertScheduler" in repr_str
        assert "stopped" in repr_str
        assert "interval=1s" in repr_str

    def test_repr_running(self, scheduler: AlertScheduler) -> None:
        """Test repr when running."""
        scheduler._running = True
        repr_str = repr(scheduler)

        assert "running" in repr_str


class TestFullAlertScheduler:
    """Tests for FullAlertScheduler."""

    def test_init_with_components(
        self, mock_handlers: MagicMock, alert_config: AlertConfig
    ) -> None:
        """Test initialization with collector components."""
        mock_classifier = MagicMock()
        mock_fx_collector = MagicMock()
        mock_stress_collector = MagicMock()
        mock_corr_engine = MagicMock()

        scheduler = FullAlertScheduler(
            handlers=mock_handlers,
            config=alert_config,
            regime_classifier=mock_classifier,
            fx_collector=mock_fx_collector,
            stress_collector=mock_stress_collector,
            correlation_engine=mock_corr_engine,
        )

        assert scheduler._regime_classifier == mock_classifier
        assert scheduler._fx_collector == mock_fx_collector
        assert scheduler._stress_collector == mock_stress_collector
        assert scheduler._correlation_engine == mock_corr_engine

    def test_repr_with_components(
        self, mock_handlers: MagicMock, alert_config: AlertConfig
    ) -> None:
        """Test repr shows enabled components."""
        scheduler = FullAlertScheduler(
            handlers=mock_handlers,
            config=alert_config,
            regime_classifier=MagicMock(),
            fx_collector=MagicMock(),
        )

        repr_str = repr(scheduler)

        assert "FullAlertScheduler" in repr_str
        assert "regime" in repr_str
        assert "dxy" in repr_str

    @pytest.mark.asyncio
    async def test_check_regime_called(
        self, mock_handlers: MagicMock, alert_config: AlertConfig
    ) -> None:
        """Test that regime check is called."""
        mock_classifier = MagicMock()
        mock_result = MagicMock()
        mock_result.direction.value = "EXPANSION"
        mock_result.intensity = 72
        mock_result.confidence = "HIGH"
        mock_classifier.classify = AsyncMock(return_value=mock_result)

        mock_handlers.check_regime_change_async = AsyncMock(return_value=False)

        scheduler = FullAlertScheduler(
            handlers=mock_handlers,
            config=alert_config,
            regime_classifier=mock_classifier,
        )

        await scheduler.run_once()

        mock_classifier.classify.assert_called_once()
        mock_handlers.check_regime_change_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_dxy_called(
        self, mock_handlers: MagicMock, alert_config: AlertConfig
    ) -> None:
        """Test that DXY check is called."""
        mock_fx_collector = MagicMock()
        mock_fx_collector.get_current_dxy = AsyncMock(return_value=104.5)

        mock_handlers.check_dxy_move_async = AsyncMock(return_value=False)

        scheduler = FullAlertScheduler(
            handlers=mock_handlers,
            config=alert_config,
            fx_collector=mock_fx_collector,
        )

        await scheduler.run_once()

        mock_fx_collector.get_current_dxy.assert_called_once()
        mock_handlers.check_dxy_move_async.assert_called_once_with(104.5)

    @pytest.mark.asyncio
    async def test_check_handles_errors(
        self, mock_handlers: MagicMock, alert_config: AlertConfig
    ) -> None:
        """Test that checks handle errors gracefully."""
        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(side_effect=ValueError("Test error"))

        scheduler = FullAlertScheduler(
            handlers=mock_handlers,
            config=alert_config,
            regime_classifier=mock_classifier,
        )

        # Should not raise
        await scheduler.run_once()
        assert scheduler.check_count == 1
