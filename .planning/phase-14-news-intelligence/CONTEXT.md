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

## Gate Feedback Mitigations (v2)

Issues identificati dal confidence gate (72%) e relative mitigazioni:

| # | Issue | Mitigation |
|---|-------|------------|
| 1 | Helsinki-NLP zh-en debole per financial docs | Fallback: testi PBoC processati direttamente in cinese via Qwen3-1.5B (lightweight); zh-en solo per titoli brevi |
| 2 | FinBERT solo inglese, perde accuratezza su tradotto | Aggiungere confidence decay 0.85x per testi tradotti; keyword boost più alto (40% vs 30%) |
| 3 | GitHub FOMC fallback non ufficiale | Primario: Fed website scraping; Fallback 1: FedTools API; Fallback 2: GitHub archive; Cache locale 30 giorni |
| 4 | Latenza <60s richiede caching/warming | Model pre-load a startup (`warm_models()` in app init); risultati RSS cached 60s |
| 5 | PBoC scraping fragile | Retry 3x con exponential backoff; charset detection (`chardet`); fallback Trading Economics se parsing fails |
| 6 | Rate limiting mancante su RSS | Per-feed rate limit: 60s minimum; exponential backoff su 429; jitter ±10s |
| 7 | Nessuna deduplicazione news | Content hash (SHA256 of title+date) in Redis/dict; skip if seen in 24h |
| 8 | GPU/CPU switching non specificato | Runtime detection a startup: `torch.cuda.is_available()`; log choice; no dynamic switch |
| 9 | Error cascading non gestito | Fallback chain: translate→fail→use original+flag; sentiment→fail→keyword-only; discord→fail→queue |
| 10 | Word-level diff insufficiente | Semantic diff layer: detect key phrases ("patient", "data-dependent", "gradual"); highlight policy shifts separately |

## Updated Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | Full 9-plan implementation | Complete news intelligence layer |
| GPU Strategy | Runtime detection at startup | `torch.cuda.is_available()`, no dynamic switch |
| PBoC Data | Web scraping + Trading Economics fallback | Robust with retry logic and charset detection |
| Translation | Helsinki-NLP for EU langs, Qwen3-1.5B for Chinese | Language-appropriate models |
| Sentiment | FinBERT + boosted keywords (40%) for translated text | Compensate translation accuracy loss |
| FOMC Archive | Fed website → FedTools → GitHub (3-tier fallback) | Redundancy for reliability |
| Diff Algorithm | difflib + semantic phrase detection | Catch policy-relevant changes |
| Deduplication | Content hash (SHA256) with 24h TTL | Prevent duplicate alerts |
| Rate Limiting | 60s per-feed minimum + exponential backoff | Avoid bans |
| Model Loading | Pre-load at startup (warm_models) | Meet <60s latency target |
| Discord | discord-webhook (async) with queue on failure | Graceful degradation |

## Integration Points

- **Alerts:** Extend src/liquidity/alerts/ for news notifications
- **Dashboard:** New component in src/liquidity/dashboard/components/news.py
- **API:** New router /news endpoint
- **Storage:** QuestDB for sentiment time series
- **Cache:** Redis or in-memory dict for deduplication
