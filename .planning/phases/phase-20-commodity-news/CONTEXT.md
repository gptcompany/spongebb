# Phase 20: Commodity News - Context

## Goal

Oil-specific news intelligence: RSS feeds per oil news (OPEC, Reuters Energy, Platts), OPEC meeting calendar, weather/hurricane tracking (NOAA), e supply disruption alerts.

## Requirements (from ROADMAP)

| ID | Requirement |
|----|-------------|
| NEWS-10 | Oil RSS feeds (Reuters, Platts, Argus, OPEC) |
| NEWS-11 | OPEC meeting calendar integration |
| NEWS-12 | Weather/hurricane event tracking |

## Plans

| Plan | Description | Effort | Wave |
|------|-------------|--------|------|
| 20-01 | Oil RSS feeds (Reuters, Platts, Argus, OPEC) | M | 1 |
| 20-02 | OPEC meeting calendar integration | S | 1 |
| 20-03 | Hurricane/weather impact tracker (NOAA) | M | 2 |
| 20-04 | Supply disruption keyword alerts | M | 2 |

## Technical Approach

### Plan 20-01: Oil RSS Feeds

**Feed URLs to add:**
- OPEC News: `https://www.opec.org/opec_web/en/press_room.htm` (scrape or find RSS)
- Reuters Energy: `https://www.reuters.com/business/energy/` (RSS may not be available - check)
- S&P Global Platts: Check for public RSS
- Argus Media: Check for public RSS

**Alternative free sources:**
- OilPrice.com RSS: `https://oilprice.com/rss/main`
- EIA This Week in Petroleum: `https://www.eia.gov/petroleum/weekly/`
- OPEC Monthly Oil Market Report: Check release calendar

**Implementation:**
- Estendere `FeedSource` enum in `news/schemas.py`
- Aggiungere feed configs in `COMMODITY_FEEDS` dict
- Estendere `NewsPoller` per supportare commodity feeds

### Plan 20-02: OPEC Meeting Calendar

**Data source:**
- OPEC official calendar: `https://www.opec.org/opec_web/en/press_room/28.htm`
- OPEC+ meeting dates (announced in advance)

**Implementation:**
- Nuovo modulo `src/liquidity/calendar/opec.py`
- Scrape o API per meeting dates
- Integrazione con existing calendar system (`calendar/treasury.py` pattern)
- Alert pre-meeting (1 giorno prima)

### Plan 20-03: Hurricane/Weather Tracker

**Data sources:**
- NOAA National Hurricane Center: `https://www.nhc.noaa.gov/`
- NHC GIS Data: `https://www.nhc.noaa.gov/gis/`
- NOAA Active Storms RSS: `https://www.nhc.noaa.gov/index-at.xml`

**Impact areas:**
- Gulf of Mexico (GOM) oil production
- Refinery corridor (Texas/Louisiana coast)
- SPR release locations

**Implementation:**
- Nuovo modulo `src/liquidity/weather/noaa.py`
- Parse NHC advisories per storms
- Calcola proximity a oil infrastructure
- Alert se storm Cat 3+ near GOM

### Plan 20-04: Supply Disruption Alerts

**Keywords da monitorare:**
- Production cuts: "production cut", "output reduction", "quota"
- Sanctions: "sanctions", "embargo", "ban"
- Outages: "outage", "disruption", "force majeure", "pipeline"
- Geopolitical: "Iran", "Russia", "Libya", "Venezuela", "Nigeria"
- OPEC: "OPEC+", "JMMC", "ministerial meeting"

**Implementation:**
- Estendere `news/alerts.py` con keyword matching
- Priority scoring (high: sanctions/outage, medium: OPEC, low: general)
- Discord webhook per high-priority alerts

## Dependencies

- **Phase 14**: News Intelligence infrastructure (feeds.py, schemas.py, alerts.py)
- **Phase 16**: EIA oil data (per context)

## Files to Create/Modify

| Action | File |
|--------|------|
| MODIFY | `src/liquidity/news/schemas.py` (add OIL_* feed sources) |
| CREATE | `src/liquidity/news/oil_feeds.py` (commodity-specific feeds) |
| CREATE | `src/liquidity/calendar/opec.py` (OPEC meetings) |
| CREATE | `src/liquidity/weather/noaa.py` (hurricane tracking) |
| CREATE | `src/liquidity/weather/__init__.py` |
| MODIFY | `src/liquidity/news/alerts.py` (add oil keywords) |
| CREATE | `tests/unit/news/test_oil_feeds.py` |
| CREATE | `tests/unit/calendar/test_opec.py` |
| CREATE | `tests/unit/weather/test_noaa.py` |

## Validation Criteria

- [ ] Oil RSS feeds polling senza errori
- [ ] OPEC calendar contiene prossimi meeting
- [ ] NOAA tracker rileva active storms (when present)
- [ ] Keyword alerts trigger correttamente
- [ ] Test coverage > 80%
