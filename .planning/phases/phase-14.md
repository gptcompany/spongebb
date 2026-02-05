# Phase 14: News Intelligence

## Overview

Implement news and central bank communication monitoring for early warning signals. This phase addresses the gap of being purely reactive (waiting for data releases) vs proactive (monitoring communications that precede policy changes).

## Goals

1. **RSS Aggregation**: Collect CB announcements, speeches, and news
2. **NLP Translation**: Translate Chinese/German/Japanese/French CB communications to English
3. **Sentiment Analysis**: Classify CB speech sentiment (hawkish/dovish) via finBERT + Qwen3
4. **Breaking Alerts**: Keyword-triggered notifications
5. **Dashboard Panel**: News timeline with sentiment indicators
6. **FOMC Statement Scraping**: Fetch and store FOMC statements from Fed website
7. **Statement Diff Analysis**: Word-level diff with hawkish/dovish scoring (Bloomberg-style)
8. **Statement Diff UI**: Side-by-side comparison with inline highlighting
9. **Real-time Statement Webhook**: Immediate alert on new statement publication

## Dependencies

- Phase 11 (High-Frequency Data Layer) - For integration with HF data

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NEWS-01 | RSS feed aggregation from major CBs | HIGH |
| NEWS-02 | Multi-language translation (CN+DE+JP+FR→EN) | HIGH |
| NEWS-03 | finBERT + Qwen3 sentiment analysis for CB text | MEDIUM |
| NEWS-04 | Keyword-based breaking news alerts | MEDIUM |
| NEWS-05 | News panel in dashboard | MEDIUM |
| NEWS-06 | FOMC statement scraper (Fed website + GitHub) | HIGH |
| NEWS-07 | Statement diff engine (word-level, hawkish/dovish) | HIGH |
| NEWS-08 | Statement diff UI (Bloomberg-style side-by-side) | MEDIUM |
| NEWS-09 | Real-time statement webhook (<60s latency) | MEDIUM |

## Research Topics

1. **finBERT for Financial Sentiment**
   - GitHub: https://github.com/ProsusAI/finBERT (1,984 stars)
   - Pre-trained on financial text
   - Sentiment: Positive/Negative/Neutral
   - Install: `pip install transformers`
   - Model: `ProsusAI/finbert`

2. **Central Bank NLP Research**
   - awesome-financial-nlp: https://github.com/icoxfog417/awesome-financial-nlp
   - Loughran-McDonald financial dictionary
   - Fed communication analysis papers

3. **Translation APIs**
   - DeepL API (highest quality): `pip install deepl`
   - Google Translate: `pip install google-cloud-translate`
   - Helsinki NLP (free, HuggingFace): `Helsinki-NLP/opus-mt-zh-en`

4. **RSS Parsing**
   - feedparser: `pip install feedparser`
   - atoma: `pip install atoma`

## CB Feed Sources

| Central Bank | Feed URL | Language |
|--------------|----------|----------|
| Fed | https://www.federalreserve.gov/feeds/press_all.xml | EN |
| ECB | https://www.ecb.europa.eu/rss/press.html | EN |
| BoJ | https://www.boj.or.jp/en/rss.xml | EN |
| PBoC | http://www.pbc.gov.cn/rss/ | CN |
| BoE | https://www.bankofengland.co.uk/rss/news | EN |
| SNB | https://www.snb.ch/en/service/rss | EN |
| BoC | https://www.bankofcanada.ca/rss/ | EN |

## Plans

### Plan 14-01: RSS Feed Aggregator
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Build RSS feed aggregator for central bank communications.

**Deliverables**:
- `src/liquidity/news/rss_aggregator.py`
- `src/liquidity/news/feeds.py` (feed configurations)
- Database storage for news items
- Tests in `tests/unit/test_news/`

**Acceptance Criteria**:
- [ ] Polls 7 CB feeds every 15 minutes
- [ ] Deduplicates entries by GUID
- [ ] Stores to QuestDB news table
- [ ] Handles feed failures gracefully

### Plan 14-02: NLP Translation Pipeline
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Implement Chinese to English translation for PBoC communications.

**Methodology**:
```python
from transformers import pipeline

# Option 1: Helsinki NLP (free)
translator = pipeline("translation", model="Helsinki-NLP/opus-mt-zh-en")

# Option 2: DeepL API (better quality)
import deepl
translator = deepl.Translator(auth_key)
result = translator.translate_text(text, target_lang="EN-US")
```

**Deliverables**:
- `src/liquidity/news/translator.py`
- `src/liquidity/news/processors/pboc.py`
- Tests in `tests/unit/test_news/`

**Acceptance Criteria**:
- [ ] Translates PBoC announcements to English
- [ ] Preserves numerical values correctly
- [ ] Handles financial terminology
- [ ] Caches translations to reduce API calls

### Plan 14-03: CB Speech Sentiment Analyzer
**Wave**: 2 | **Effort**: L | **Priority**: MEDIUM

Implement finBERT-based sentiment analysis for CB communications.

**Methodology**:
```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Load finBERT
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")

def analyze_sentiment(text: str) -> dict:
    """
    Returns: {
        "sentiment": "positive" | "negative" | "neutral",
        "confidence": 0.0-1.0,
        "hawkish_score": -1.0 to 1.0
    }
    """
    inputs = tokenizer(text, return_tensors="pt", truncation=True)
    outputs = model(**inputs)
    # Process outputs...
```

**Deliverables**:
- `src/liquidity/news/sentiment.py`
- Historical sentiment tracker
- Tests in `tests/unit/test_news/`

**Acceptance Criteria**:
- [ ] Classifies as Hawkish/Dovish/Neutral
- [ ] Confidence score for each classification
- [ ] Tracks sentiment changes over time
- [ ] Validates against known hawkish/dovish speeches

### Plan 14-04: Breaking News Alerts
**Wave**: 2 | **Effort**: M | **Priority**: MEDIUM

Implement keyword-triggered alert system.

**Keyword Categories**:
```python
ALERT_KEYWORDS = {
    "critical": [
        "emergency", "crisis", "intervention", "bailout",
        "swap line", "liquidity facility", "rate cut", "rate hike"
    ],
    "high": [
        "balance sheet", "QE", "QT", "taper",
        "inflation target", "employment mandate"
    ],
    "medium": [
        "policy statement", "minutes", "testimony",
        "economic outlook", "financial stability"
    ]
}
```

**Deliverables**:
- `src/liquidity/news/alerts.py`
- Discord webhook integration
- Tests in `tests/unit/test_news/`

**Acceptance Criteria**:
- [ ] Triggers on critical keywords immediately
- [ ] Batches non-critical alerts (hourly digest)
- [ ] Rate limits to prevent spam
- [ ] Priority-based alert formatting

### Plan 14-05: News Dashboard Panel
**Wave**: 3 | **Effort**: M | **Priority**: MEDIUM

Add news timeline panel to dashboard.

**Deliverables**:
- `src/liquidity/dashboard/components/news.py`
- Integration with main layout
- Tests in `tests/unit/test_dashboard/`

**UI Components**:
- News timeline (scrollable, last 24h)
- Sentiment indicator per item (color-coded)
- CB source filter
- Keyword search
- Sentiment trend chart

**Acceptance Criteria**:
- [ ] Shows last 24h of CB news
- [ ] Color-coded sentiment (green/yellow/red)
- [ ] Filterable by source
- [ ] Links to original source

### Plan 14-06: FOMC Statement Scraper
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Fetch FOMC statements from Fed website with GitHub fallback.

**Sources**:
- Primary: https://www.federalreserve.gov/monetarypolicy/fomc.htm
- Fallback: https://github.com/fomc/statements (raw text files)

**Deliverables**:
- `src/liquidity/collectors/fomc_statements.py`
- Tests in `tests/unit/collectors/test_fomc_statements.py`
- Integration tests in `tests/integration/collectors/`

**Schema**:
```python
columns = ["timestamp", "meeting_date", "series_id", "source", "text", "url", "word_count"]
```

**Acceptance Criteria**:
- [ ] Fetches current and historical statements (2020+)
- [ ] Falls back to GitHub if Fed website unavailable
- [ ] Follows BaseCollector pattern with retry/circuit breaker
- [ ] Registered in collector registry

### Plan 14-07: Statement Diff Engine
**Wave**: 1 | **Effort**: M | **Priority**: HIGH

Word-level diff between consecutive FOMC statements with hawkish/dovish scoring.

**Methodology**:
```python
from difflib import SequenceMatcher

# Hawkish keywords (tightening)
HAWKISH = {"inflation": 0.3, "restrictive": 0.5, "tightening": 0.5, "elevated": 0.2}

# Dovish keywords (easing)
DOVISH = {"patient": -0.3, "accommodative": -0.5, "data-dependent": -0.2, "gradual": -0.3}
```

**Deliverables**:
- `src/liquidity/analyzers/statement_diff.py`
- Tests in `tests/unit/analyzers/test_statement_diff.py`

**Output**:
```python
@dataclass
class StatementDiff:
    previous_date: date
    current_date: date
    added_words: list[str]
    removed_words: list[str]
    word_count_delta: int
    hawkish_score_delta: float  # -1 (dovish) to +1 (hawkish)
    summary: str
```

**Acceptance Criteria**:
- [ ] Computes word-level diff with ChangeType enum
- [ ] Calculates hawkish/dovish score delta
- [ ] Generates human-readable summary
- [ ] Handles edge cases (identical statements, empty text)

### Plan 14-08: Statement Diff UI (Bloomberg-style)
**Wave**: 2 | **Effort**: M | **Priority**: MEDIUM

Dashboard panel with side-by-side statement comparison.

**Deliverables**:
- `src/liquidity/dashboard/components/statement_diff.py`
- Integration with layout.py and callbacks.py
- Tests in `tests/unit/test_dashboard/`

**UI Components**:
- Meeting date selector dropdown
- Hawkish/Dovish sentiment meter (gauge)
- Side-by-side statement text with inline highlighting
- Key changes summary table

**Color Scheme**:
```python
DIFF_COLORS = {
    "added": "#00ff88",      # Green
    "removed": "#ff4444",    # Red
    "modified": "#ffaa00",   # Yellow
    "unchanged": "#888888",  # Gray
}
```

**Acceptance Criteria**:
- [ ] Side-by-side comparison with inline highlights
- [ ] Sentiment meter showing hawkish/dovish shift
- [ ] Meeting selector with all available dates
- [ ] Follows existing dashboard dark theme

### Plan 14-09: Real-time Statement Webhook
**Wave**: 3 | **Effort**: L | **Priority**: MEDIUM

Monitor for new FOMC statements and trigger immediate alert pipeline.

**Pipeline**:
```
RSS Monitor → Detect New Statement → Fetch Full Text → Compute Diff → Analyze Sentiment → Discord Alert
```

**Deliverables**:
- `src/liquidity/alerts/statement_monitor.py`
- Additions to `alerts/formatter.py` (fomc_statement method)
- Tests in `tests/unit/test_alerts/`

**Configuration**:
```python
CHECK_INTERVAL_SECONDS = 30   # During FOMC meeting days
IDLE_INTERVAL_SECONDS = 3600  # Non-meeting days (uses CBMeetingCalendar)
```

**Acceptance Criteria**:
- [ ] Monitors Fed RSS feed for new statements
- [ ] Triggers full pipeline on detection
- [ ] Sends Discord alert with diff summary
- [ ] Target latency: <60s from publication
- [ ] Integrates with calendar for smart polling

## Technical Notes

### New Dependencies

```toml
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "transformers>=4.35.0",  # finBERT, translation
    "feedparser>=6.0.0",    # RSS parsing
    "deepl>=1.0.0",         # Translation API (optional)
]
```

### Module Structure

```
src/liquidity/news/
├── __init__.py
├── rss_aggregator.py    # Feed polling
├── feeds.py             # Feed configurations
├── translator.py        # Multi-language translation (CN/DE/JP/FR)
├── sentiment.py         # finBERT + Qwen3 analysis
├── alerts.py            # Keyword alerts
├── processors/
│   ├── __init__.py
│   ├── pboc.py          # PBoC-specific processing
│   ├── fed.py           # Fed-specific processing
│   └── base.py          # Base processor class
└── models/
    └── news_item.py     # News data model

src/liquidity/collectors/
└── fomc_statements.py   # NEW: FOMC statement scraper

src/liquidity/analyzers/
└── statement_diff.py    # NEW: Statement diff engine

src/liquidity/dashboard/components/
└── statement_diff.py    # NEW: Statement diff UI panel

src/liquidity/alerts/
└── statement_monitor.py # NEW: Real-time statement monitor
```

### Database Schema

```sql
CREATE TABLE cb_news (
    timestamp TIMESTAMP,
    source STRING,
    title STRING,
    content STRING,
    url STRING,
    language STRING,
    translated_content STRING,
    sentiment STRING,
    sentiment_score DOUBLE,
    keywords STRING,
    processed BOOLEAN
) TIMESTAMP(timestamp) PARTITION BY DAY;
```

## Success Metrics

| Metric | Target |
|--------|--------|
| Feed coverage | 7/7 major CBs |
| Translation quality | >90% accuracy |
| Sentiment accuracy | >75% vs human labels |
| Alert latency | <5 min from publication |
| Statement fetch success | >95% (with fallback) |
| Diff accuracy | 100% word-level |
| Hawkish/dovish scoring | Validated against known speeches |
| Real-time webhook latency | <60s from publication |

## References

- finBERT: https://github.com/ProsusAI/finBERT
- FinGPT: https://github.com/AI4Finance-Foundation/FinGPT
- Helsinki NLP: https://huggingface.co/Helsinki-NLP
- feedparser: https://feedparser.readthedocs.io/
- awesome-financial-nlp: https://github.com/icoxfog417/awesome-financial-nlp
- Loughran-McDonald Dictionary: https://sraf.nd.edu/loughranmcdonald-master-dictionary/
- FOMC Statements GitHub: https://github.com/fomc/statements
- FedTools: https://github.com/David-Woroniuk/FedTools
- centralbank_analysis: https://github.com/yukit-k/centralbank_analysis
- LLM Open Finance (Qwen3-based): https://huggingface.co/blog/DragonLLM/llm-open-finance-models
- Qwen3 on Ollama: https://ollama.com/library/qwen3
