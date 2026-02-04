# Phase 14: News Intelligence

## Overview

Implement news and central bank communication monitoring for early warning signals. This phase addresses the gap of being purely reactive (waiting for data releases) vs proactive (monitoring communications that precede policy changes).

## Goals

1. **RSS Aggregation**: Collect CB announcements, speeches, and news
2. **NLP Translation**: Translate Chinese PBoC communications to English
3. **Sentiment Analysis**: Classify CB speech sentiment (hawkish/dovish)
4. **Breaking Alerts**: Keyword-triggered notifications
5. **Dashboard Panel**: News timeline with sentiment indicators

## Dependencies

- Phase 11 (High-Frequency Data Layer) - For integration with HF data

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NEWS-01 | RSS feed aggregation from major CBs | HIGH |
| NEWS-02 | Chinese→English translation pipeline | HIGH |
| NEWS-03 | finBERT sentiment analysis for CB text | MEDIUM |
| NEWS-04 | Keyword-based breaking news alerts | MEDIUM |
| NEWS-05 | News panel in dashboard | MEDIUM |

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
├── translator.py        # Translation pipeline
├── sentiment.py         # finBERT analysis
├── alerts.py            # Keyword alerts
├── processors/
│   ├── __init__.py
│   ├── pboc.py          # PBoC-specific processing
│   ├── fed.py           # Fed-specific processing
│   └── base.py          # Base processor class
└── models/
    └── news_item.py     # News data model
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

## References

- finBERT: https://github.com/ProsusAI/finBERT
- Helsinki NLP: https://huggingface.co/Helsinki-NLP
- feedparser: https://feedparser.readthedocs.io/
- awesome-financial-nlp: https://github.com/icoxfog417/awesome-financial-nlp
- Loughran-McDonald Dictionary: https://sraf.nd.edu/loughranmcdonald-master-dictionary/
