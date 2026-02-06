# Phase 14: News Intelligence - Context

**Created:** 2026-02-05
**Phase:** 14 of 15
**Depends on:** Phase 11 (High-Frequency Data Layer)

## Goals

Early warning via CB communications, FOMC statement analysis, and news monitoring.

## Requirements Covered

- NEWS-01: RSS aggregator (PBoC, ECB, Fed, BoJ)
- NEWS-02: NLP translation pipeline (CN+DE+JP+FR via Helsinki-NLP)
- NEWS-03: CB speech sentiment analyzer (finBERT + Qwen3)
- NEWS-04: Breaking news keyword alerts
- NEWS-05: News dashboard panel
- NEWS-06: FOMC Statement Scraper (Fed website + GitHub fallback)
- NEWS-07: Statement Diff Engine (word-level, hawkish/dovish scoring)
- NEWS-08: Statement Diff UI (Bloomberg-style side-by-side)
- NEWS-09: Real-time Statement Webhook (RSS→diff→Discord, <60s latency)

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | Full 9-plan implementation | Complete news intelligence layer |
| GPU Strategy | Hybrid (GPU primary, CPU fallback) | Best effort with graceful degradation |
| PBoC Data | Web scraping (pandas.read_html) | No official RSS, parse HTM files directly |
| Translation | Helsinki-NLP OPUS-MT | Free, fast, trained on EU/UN financial docs |
| Sentiment | FinBERT + keyword augmentation | 70% model + 30% hawkish/dovish keywords |
| FOMC Archive | github.com/fomc/statements + FedTools | Reliable community-maintained sources |
| Diff Algorithm | Python difflib | Industry standard, word-level |
| Discord | discord-webhook (async) | Lightweight, no bot auth required |

## Research Summary

### RSS Feeds (Verified)

| Central Bank | Feed URL | Notes |
|-------------|----------|-------|
| Fed | federalreserve.gov/feeds/ | FOMC + press releases |
| ECB | ecb.europa.eu RSS | Press + supervision |
| BoJ | boj.or.jp/en/rss/whatsnew.xml | Daily news |
| PBoC | N/A - web scrape | pbc.gov.cn HTML tables |

### NLP Stack

- **Translation:** Helsinki-NLP/opus-mt-{zh,ja,de,fr}-en (50-300MB each)
- **Sentiment:** ProsusAI/finbert (440MB)
- **Inference:** transformers.pipeline() with device detection
- **Fallback:** CPU inference if GPU unavailable

### Performance Targets

- RSS poll interval: 30 seconds
- End-to-end latency: <60 seconds (fetch → translate → sentiment → Discord)
- Sentiment accuracy: >90% on CB statements

## Constraints

- No paid APIs (use open-source models only)
- Must integrate with existing alerting system (src/liquidity/alerts/)
- Must add dashboard panel (src/liquidity/dashboard/components/)
- PBoC monthly lag accepted (same as existing collectors)

## Integration Points

- **Alerts:** Extend src/liquidity/alerts/ for news notifications
- **Dashboard:** New component in src/liquidity/dashboard/components/news.py
- **API:** New router /news endpoint
- **Storage:** QuestDB for sentiment time series
