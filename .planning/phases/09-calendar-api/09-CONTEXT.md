# Phase 9: Calendar & API - Context

## Phase Goal

Build the Calendar effects tracking system and FastAPI REST server for exposing liquidity data and regime classification to external systems (NautilusTrader, dashboards).

## User Preferences (from Discuss)

### Calendar Events Scope
- **Core (CAL-01 to CAL-05)**:
  - US Treasury auction calendar with settlement dates
  - Month-end/quarter-end liquidity windows
  - Tax payment dates (April 15, Sept 15, Dec 15)
  - Fed meeting dates and blackout periods
- **Extended (user requested)**:
  - ECB/BoJ/BoE meeting dates
  - US market holidays (impatto liquidità)

### API Architecture
- **Protocol**: REST only (no WebSocket, no gRPC)
- **Endpoints** (API-01 to API-09):
  - `GET /liquidity/net` - Net Liquidity Index
  - `GET /liquidity/global` - Global Liquidity Index
  - `GET /regime/current` - Current regime + intensity
  - `GET /metrics/stealth-qe` - Stealth QE Score
  - `GET /fx/dxy` - DXY data
  - `GET /stress/indicators` - Stress indicators
  - `GET /correlations` - Correlation matrix
  - `GET /calendar/events` - Calendar events

### Deployment
- **Target**: Docker container
- **Requirements**: Dockerfile + docker-compose.yml

## Technical Constraints

### Dependencies to Add
- `fastapi>=0.115.0` - Web framework
- `uvicorn>=0.30.0` - ASGI server
- `python-dateutil>=2.8.0` - Calendar date utilities
- `holidays>=0.40.0` - US market holidays

### Existing Components to Integrate
| Component | Location | API Usage |
|-----------|----------|-----------|
| NetLiquidityCalculator | `calculators/net_liquidity.py` | `/liquidity/net` |
| GlobalLiquidityCalculator | `calculators/global_liquidity.py` | `/liquidity/global` |
| StealthQECalculator | `calculators/stealth_qe.py` | `/metrics/stealth-qe` |
| RegimeClassifier | `analyzers/regime_classifier.py` | `/regime/current` |
| CorrelationEngine | `analyzers/correlation_engine.py` | `/correlations` |
| StressIndicatorCollector | `collectors/stress.py` | `/stress/indicators` |
| FXCollector | `collectors/fx.py` | `/fx/dxy` |
| QuestDB Storage | `storage/questdb.py` | Data fetching |

### Calendar Data Sources
| Event Type | Source | Update Frequency |
|------------|--------|------------------|
| US Treasury Auctions | treasurydirect.gov | Weekly |
| Fed Meetings | federalreserve.gov | Annual (known schedule) |
| ECB Meetings | ecb.europa.eu | Annual |
| BoJ Meetings | boj.or.jp | Annual |
| BoE Meetings | bankofengland.co.uk | Annual |
| Tax Dates | IRS | Fixed dates |
| US Holidays | `holidays` package | Static |

## Architecture Decisions

### Module Structure
```
src/liquidity/
├── calendar/
│   ├── __init__.py
│   ├── events.py          # CalendarEvent base + implementations
│   ├── treasury.py        # Treasury auction calendar
│   ├── central_banks.py   # Fed/ECB/BoJ/BoE meetings
│   └── holidays.py        # US market holidays
│
├── api/
│   ├── __init__.py
│   ├── server.py          # FastAPI app + routes
│   ├── deps.py            # Dependency injection
│   ├── schemas.py         # Pydantic response models
│   └── routers/
│       ├── liquidity.py   # /liquidity/* endpoints
│       ├── regime.py      # /regime/* endpoints
│       ├── metrics.py     # /metrics/* endpoints
│       ├── fx.py          # /fx/* endpoints
│       ├── stress.py      # /stress/* endpoints
│       ├── correlations.py # /correlations endpoint
│       └── calendar.py    # /calendar/* endpoints
```

### API Response Format
```json
{
  "data": {...},
  "metadata": {
    "timestamp": "2026-02-04T10:00:00Z",
    "source": "spongebb",
    "version": "1.0.0"
  }
}
```

### NautilusTrader Integration (API-05)
- Simple HTTP client to call `/regime/current`
- Returns: `{ "regime": "EXPANSION", "intensity": 75, "confidence": "HIGH" }`
- NautilusTrader macro filter queries this on strategy startup + periodically

## Out of Scope (Phase 9)
- WebSocket streaming (future enhancement)
- Authentication (internal use only, private network)
- Rate limiting (low volume, trusted clients)
- Dashboard overlay (CAL-05) - deferred to Phase 10

## Risk Assessment
- **Low**: FastAPI + Uvicorn are battle-tested
- **Low**: Calendar data is static/semi-static
- **Medium**: Treasury auction scraping may change format

## Success Criteria
- [ ] All API endpoints return valid JSON
- [ ] Calendar returns next 30 days of events
- [ ] Docker container starts and serves on port 8000
- [ ] 100% unit test coverage for API routes
- [ ] Integration test with QuestDB data fetch
