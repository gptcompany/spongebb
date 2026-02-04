# NautilusTrader Integration Guide

This guide explains how to integrate the Global Liquidity Monitor API with NautilusTrader for macro-filtered trading strategies.

## Overview

The API provides real-time liquidity regime classification that can be used as a macro filter in trading systems. The key endpoint for trading decisions is `/regime/current`, which returns the current liquidity environment classification.

## API Endpoints

### Regime Classification (Primary)

```
GET /regime/current
```

Response:
```json
{
  "regime": "EXPANSION",
  "intensity": 72.5,
  "confidence": "HIGH",
  "components": "Net: +40% | Global: +35% | StealthQE: +25%",
  "as_of_date": "2026-02-04T10:30:00Z",
  "metadata": {...}
}
```

### Supporting Endpoints

| Endpoint | Purpose | Use Case |
|----------|---------|----------|
| `/liquidity/net` | Net Liquidity Index | Component analysis |
| `/liquidity/global` | Global CB Liquidity | Global context |
| `/stress/indicators` | Funding stress | Risk management |
| `/correlations` | Asset-liquidity correlations | Position sizing |
| `/calendar/next` | Upcoming events | Event risk |

## Python Client Implementation

### Basic Macro Filter

```python
"""NautilusTrader Liquidity Macro Filter."""

import httpx
from dataclasses import dataclass
from enum import Enum


class TradingPermission(Enum):
    ALLOWED = "allowed"
    REDUCED = "reduced"
    BLOCKED = "blocked"


@dataclass
class MacroState:
    """Current macro liquidity state."""
    regime: str
    intensity: float
    confidence: str
    permission: TradingPermission
    reason: str


class LiquidityMacroFilter:
    """Macro filter based on liquidity regime.

    Integrates with Global Liquidity Monitor API to make
    trading permission decisions based on macro conditions.

    Args:
        api_url: Base URL of the Liquidity Monitor API.
        expansion_only: If True, only allow trading in EXPANSION regime.
        min_confidence: Minimum confidence level for full trading (HIGH/MEDIUM/LOW).
        min_intensity: Minimum intensity score for full trading (0-100).
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        expansion_only: bool = True,
        min_confidence: str = "MEDIUM",
        min_intensity: float = 40.0,
    ):
        self.api_url = api_url
        self.expansion_only = expansion_only
        self.min_confidence = min_confidence
        self.min_intensity = min_intensity
        self._confidence_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    async def get_macro_state(self) -> MacroState:
        """Fetch current macro state from API.

        Returns:
            MacroState with current regime and trading permission.

        Raises:
            httpx.HTTPError: If API request fails.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.api_url}/regime/current")
            resp.raise_for_status()
            data = resp.json()

        regime = data["regime"]
        intensity = data["intensity"]
        confidence = data["confidence"]

        # Determine trading permission
        permission, reason = self._evaluate_permission(regime, intensity, confidence)

        return MacroState(
            regime=regime,
            intensity=intensity,
            confidence=confidence,
            permission=permission,
            reason=reason,
        )

    def _evaluate_permission(
        self,
        regime: str,
        intensity: float,
        confidence: str,
    ) -> tuple[TradingPermission, str]:
        """Evaluate trading permission based on regime state."""

        # Block trading in CONTRACTION if expansion_only
        if self.expansion_only and regime == "CONTRACTION":
            return TradingPermission.BLOCKED, "CONTRACTION regime - no new positions"

        # Check confidence level
        current_conf = self._confidence_order.get(confidence, 0)
        min_conf = self._confidence_order.get(self.min_confidence, 2)

        if current_conf < min_conf:
            return TradingPermission.REDUCED, f"Low confidence ({confidence})"

        # Check intensity
        if intensity < self.min_intensity:
            return TradingPermission.REDUCED, f"Low intensity ({intensity:.1f})"

        return TradingPermission.ALLOWED, "Favorable macro conditions"

    async def should_trade(self) -> bool:
        """Simple boolean check for trading permission.

        Returns:
            True if trading is allowed, False otherwise.
        """
        state = await self.get_macro_state()
        return state.permission == TradingPermission.ALLOWED


# Example usage in NautilusTrader strategy
"""
from nautilus_trader.trading.strategy import Strategy

class LiquidityFilteredStrategy(Strategy):
    def __init__(self, config):
        super().__init__(config)
        self.macro_filter = LiquidityMacroFilter(
            api_url="http://liquidity-monitor:8000",
            expansion_only=True,
            min_confidence="MEDIUM",
            min_intensity=40.0,
        )

    async def on_signal(self, signal):
        # Check macro conditions before entering
        macro_state = await self.macro_filter.get_macro_state()

        if macro_state.permission == TradingPermission.BLOCKED:
            self.log.warning(f"Trade blocked: {macro_state.reason}")
            return

        if macro_state.permission == TradingPermission.REDUCED:
            # Reduce position size
            signal.quantity *= 0.5
            self.log.info(f"Position reduced: {macro_state.reason}")

        # Execute trade
        await self.execute_signal(signal)
"""
```

### Advanced Filter with Multiple Signals

```python
"""Advanced macro filter combining multiple signals."""

import httpx
from dataclasses import dataclass
from typing import Optional


@dataclass
class ComprehensiveMacroState:
    """Full macro state with all indicators."""
    regime: str
    intensity: float
    confidence: str
    net_liquidity_sentiment: str
    stress_level: str
    next_high_impact_days: int
    trading_score: float  # 0-100


class AdvancedLiquidityFilter:
    """Advanced filter combining regime, stress, and calendar signals."""

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url

    async def get_comprehensive_state(self) -> ComprehensiveMacroState:
        """Fetch all relevant macro data."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Parallel requests for speed
            regime_task = client.get(f"{self.api_url}/regime/current")
            net_task = client.get(f"{self.api_url}/liquidity/net")
            stress_task = client.get(f"{self.api_url}/stress/indicators")
            calendar_task = client.get(f"{self.api_url}/calendar/next?limit=1")

            regime_resp = await regime_task
            net_resp = await net_task
            stress_resp = await stress_task
            calendar_resp = await calendar_task

        regime_data = regime_resp.json()
        net_data = net_resp.json()
        stress_data = stress_resp.json()
        calendar_data = calendar_resp.json()

        # Calculate days until next high-impact event
        next_event_days = 999
        if calendar_data["events"]:
            from datetime import date
            event_date = date.fromisoformat(calendar_data["events"][0]["date"])
            next_event_days = (event_date - date.today()).days

        # Calculate composite trading score
        trading_score = self._calculate_score(
            regime_data, net_data, stress_data, next_event_days
        )

        return ComprehensiveMacroState(
            regime=regime_data["regime"],
            intensity=regime_data["intensity"],
            confidence=regime_data["confidence"],
            net_liquidity_sentiment=net_data["sentiment"],
            stress_level=stress_data["overall_stress"],
            next_high_impact_days=next_event_days,
            trading_score=trading_score,
        )

    def _calculate_score(
        self,
        regime_data: dict,
        net_data: dict,
        stress_data: dict,
        event_days: int,
    ) -> float:
        """Calculate composite trading score (0-100)."""
        score = 0.0

        # Regime contribution (40 points max)
        if regime_data["regime"] == "EXPANSION":
            score += 20 + (regime_data["intensity"] / 100 * 20)

        # Net liquidity sentiment (20 points max)
        sentiment_scores = {"BULLISH": 20, "NEUTRAL": 10, "BEARISH": 0}
        score += sentiment_scores.get(net_data["sentiment"], 10)

        # Stress level (20 points max)
        stress_scores = {"normal": 20, "elevated": 10, "critical": 0}
        score += stress_scores.get(stress_data["overall_stress"], 10)

        # Event proximity (20 points max)
        if event_days > 7:
            score += 20
        elif event_days > 3:
            score += 10
        elif event_days > 1:
            score += 5
        # 0 points if event is tomorrow or today

        return min(100.0, max(0.0, score))

    async def get_position_multiplier(self) -> float:
        """Get position size multiplier based on macro conditions.

        Returns:
            Multiplier between 0.0 (no trading) and 1.0 (full size).
        """
        state = await self.get_comprehensive_state()

        if state.stress_level == "critical":
            return 0.0  # No trading during stress

        if state.regime == "CONTRACTION" and state.confidence == "HIGH":
            return 0.0  # Definite contraction

        # Scale position by trading score
        return state.trading_score / 100.0
```

## Error Handling

```python
"""Robust error handling for production use."""

import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ResilientMacroFilter:
    """Macro filter with fallback behavior on errors."""

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        fallback_permission: str = "REDUCED",
        retry_attempts: int = 3,
    ):
        self.api_url = api_url
        self.fallback_permission = fallback_permission
        self.retry_attempts = retry_attempts
        self._last_known_state: Optional[dict] = None

    async def get_regime_with_fallback(self) -> dict:
        """Fetch regime with retry and fallback logic."""
        for attempt in range(self.retry_attempts):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{self.api_url}/regime/current")
                    resp.raise_for_status()
                    data = resp.json()
                    self._last_known_state = data
                    return data
            except httpx.HTTPError as e:
                logger.warning(f"API request failed (attempt {attempt + 1}): {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(1.0 * (attempt + 1))

        # All retries failed - use fallback
        if self._last_known_state:
            logger.warning("Using last known state as fallback")
            return self._last_known_state

        # No last known state - return conservative default
        logger.error("No regime data available, returning conservative default")
        return {
            "regime": "CONTRACTION",
            "intensity": 0,
            "confidence": "LOW",
            "components": "FALLBACK - API unavailable",
        }
```

## Health Monitoring

```python
"""Health check for API connectivity."""

async def check_api_health(api_url: str = "http://localhost:8000") -> dict:
    """Check API health and connectivity.

    Returns:
        Dict with health status and latency.
    """
    import time

    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{api_url}/health")
            latency_ms = (time.monotonic() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": "healthy",
                    "latency_ms": round(latency_ms, 2),
                    "questdb_connected": data.get("questdb_connected", False),
                }
            else:
                return {
                    "status": "degraded",
                    "latency_ms": round(latency_ms, 2),
                    "error": f"HTTP {resp.status_code}",
                }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
```

## Configuration

### Environment Variables

```bash
# API Configuration
LIQUIDITY_API_URL=http://localhost:8000

# Filter Settings
MACRO_FILTER_EXPANSION_ONLY=true
MACRO_FILTER_MIN_CONFIDENCE=MEDIUM
MACRO_FILTER_MIN_INTENSITY=40.0
```

### Docker Compose Example

```yaml
services:
  liquidity-monitor:
    image: liquidity-monitor:latest
    ports:
      - "8000:8000"
    environment:
      - FRED_API_KEY=${FRED_API_KEY}
      - QUESTDB_HOST=questdb
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nautilus-trader:
    image: nautilus-trader:latest
    environment:
      - LIQUIDITY_API_URL=http://liquidity-monitor:8000
    depends_on:
      liquidity-monitor:
        condition: service_healthy
```

## Best Practices

1. **Cache responses**: Regime doesn't change frequently; cache for 1-5 minutes
2. **Use async**: All API calls should be async to avoid blocking
3. **Handle failures gracefully**: Always have fallback behavior
4. **Log decisions**: Track why trades were allowed/blocked for analysis
5. **Monitor latency**: Alert if API latency exceeds thresholds
6. **Test in paper trading**: Validate filter logic before live trading
