"""News panel component for central bank communications.

Displays:
- Tabbed interface for filtering by central bank (Fed, ECB, BoJ, All)
- News items with title, source, sentiment indicator, and time ago
- Sentiment color coding (hawkish/dovish/neutral)
"""

from datetime import UTC, datetime, timedelta

import dash_bootstrap_components as dbc
from dash import html

from liquidity.news.schemas import FeedSource, NewsItem

# Sentiment classification enum-like constants
SENTIMENT_HAWKISH = "hawkish"
SENTIMENT_DOVISH = "dovish"
SENTIMENT_NEUTRAL = "neutral"

# Color palette for news panel
NEWS_COLORS = {
    "hawkish": "#ff6b6b",  # Red - hawkish/tightening
    "dovish": "#00ff88",  # Green - dovish/easing
    "neutral": "#adb5bd",  # Gray - neutral
}

# Sentiment indicator symbols
SENTIMENT_SYMBOLS = {
    "hawkish": "\u25b2",  # ▲ Up arrow
    "dovish": "\u25bc",  # ▼ Down arrow
    "neutral": "\u2500",  # ─ Horizontal line
}

# Map FeedSource to display labels
SOURCE_LABELS: dict[FeedSource, str] = {
    FeedSource.FED_PRESS: "Fed",
    FeedSource.FED_SPEECHES: "Fed",
    FeedSource.ECB_PRESS: "ECB",
    FeedSource.BOJ_NEWS: "BoJ",
    FeedSource.BOE_NEWS: "BoE",
    FeedSource.SNB_NEWS: "SNB",
    FeedSource.BOC_NEWS: "BoC",
    FeedSource.PBOC_NEWS: "PBoC",
}

# Filter options
FILTER_ALL = "all"
FILTER_OPTIONS = [FILTER_ALL, "fed", "ecb", "boj"]


def create_news_panel() -> dbc.Card:
    """Create the central bank news panel.

    Contains:
    - Filter buttons for central bank selection
    - Scrollable news items list
    - Sentiment indicators per item

    Returns:
        Bootstrap Card with news components.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.Span("Central Bank News"),
                    html.Small(" (CB Communications)", className="text-muted ms-2"),
                ]
            ),
            dbc.CardBody(
                [
                    # Filter buttons
                    dbc.ButtonGroup(
                        [
                            dbc.Button(
                                "All",
                                id="news-filter-all",
                                color="secondary",
                                outline=True,
                                size="sm",
                                active=True,
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "Fed",
                                id="news-filter-fed",
                                color="secondary",
                                outline=True,
                                size="sm",
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "ECB",
                                id="news-filter-ecb",
                                color="secondary",
                                outline=True,
                                size="sm",
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "BoJ",
                                id="news-filter-boj",
                                color="secondary",
                                outline=True,
                                size="sm",
                                n_clicks=0,
                            ),
                        ],
                        className="mb-3 w-100",
                    ),
                    # News items container
                    html.Div(
                        id="news-items-container",
                        style={
                            "maxHeight": "300px",
                            "overflowY": "auto",
                        },
                        children=_create_placeholder_items(),
                    ),
                ]
            ),
        ]
    )


def _create_placeholder_items() -> list[html.Div]:
    """Create placeholder news items for initial load.

    Returns:
        List of placeholder Div elements.
    """
    return [
        html.Div(
            [
                html.Small("Loading news...", className="text-muted"),
            ],
            className="text-center py-3",
        )
    ]


def create_news_item(
    title: str,
    source: str,
    sentiment: str,
    time_ago: str,
    link: str | None = None,
) -> html.Div:
    """Create a single news item display.

    Args:
        title: News item title.
        source: Source label (e.g., "Fed", "ECB").
        sentiment: Sentiment classification ("hawkish", "dovish", "neutral").
        time_ago: Human-readable time ago string.
        link: Optional URL to original content.

    Returns:
        Div containing the formatted news item.
    """
    sentiment_color = NEWS_COLORS.get(sentiment, NEWS_COLORS["neutral"])
    sentiment_symbol = SENTIMENT_SYMBOLS.get(sentiment, SENTIMENT_SYMBOLS["neutral"])
    sentiment_label = sentiment.capitalize()

    # Title element (with optional link)
    if link:
        title_element = html.A(
            title,
            href=link,
            target="_blank",
            className="text-decoration-none",
            style={"color": "#e9ecef"},
        )
    else:
        title_element = html.Span(title)

    return html.Div(
        [
            # Source badge and title
            html.Div(
                [
                    dbc.Badge(
                        source,
                        color="dark",
                        className="me-2",
                        style={"fontSize": "0.7rem"},
                    ),
                    title_element,
                ],
                className="mb-1",
            ),
            # Sentiment and time
            html.Div(
                [
                    html.Span(
                        f"{sentiment_symbol} {sentiment_label}",
                        style={
                            "color": sentiment_color,
                            "fontSize": "0.75rem",
                            "fontWeight": "500",
                        },
                    ),
                    html.Span(
                        f" | {time_ago}",
                        className="text-muted",
                        style={"fontSize": "0.75rem"},
                    ),
                ],
            ),
        ],
        className="news-item mb-3 pb-2 border-bottom border-secondary",
    )


def create_news_items_list(
    items: list[dict],
    filter_source: str = FILTER_ALL,
) -> html.Div:
    """Create the news items list from data.

    Args:
        items: List of news item dictionaries with keys:
            - title: str
            - source: str (FeedSource value or display label)
            - sentiment: str ("hawkish", "dovish", "neutral")
            - published: datetime or ISO string
            - link: str (optional)
        filter_source: Filter by source ("all", "fed", "ecb", "boj").

    Returns:
        Div containing all filtered news items.
    """
    if not items:
        return html.Div(
            html.Small("No news available", className="text-muted"),
            className="text-center py-3",
        )

    # Filter items by source
    filtered_items = _filter_items_by_source(items, filter_source)

    if not filtered_items:
        return html.Div(
            html.Small(
                f"No {filter_source.upper()} news available",
                className="text-muted",
            ),
            className="text-center py-3",
        )

    # Create news item components
    item_components = []
    for item in filtered_items:
        source_label = _get_source_label(item.get("source", ""))
        time_ago = format_time_ago(item.get("published"))

        item_components.append(
            create_news_item(
                title=item.get("title", "Untitled"),
                source=source_label,
                sentiment=item.get("sentiment", SENTIMENT_NEUTRAL),
                time_ago=time_ago,
                link=item.get("link"),
            )
        )

    return html.Div(item_components)


def _filter_items_by_source(items: list[dict], filter_source: str) -> list[dict]:
    """Filter news items by source.

    Args:
        items: List of news item dictionaries.
        filter_source: Filter value ("all", "fed", "ecb", "boj").

    Returns:
        Filtered list of items.
    """
    if filter_source == FILTER_ALL:
        return items

    filter_map = {
        "fed": [FeedSource.FED_PRESS.value, FeedSource.FED_SPEECHES.value, "Fed"],
        "ecb": [FeedSource.ECB_PRESS.value, "ECB"],
        "boj": [FeedSource.BOJ_NEWS.value, "BoJ"],
    }

    allowed_sources = filter_map.get(filter_source.lower(), [])
    return [
        item
        for item in items
        if item.get("source") in allowed_sources
        or _get_source_label(item.get("source", "")).lower() == filter_source.lower()
    ]


def _get_source_label(source: str) -> str:
    """Get display label for a source.

    Args:
        source: Source identifier (FeedSource value or existing label).

    Returns:
        Human-readable source label.
    """
    # Check if it's already a label
    if source in ["Fed", "ECB", "BoJ", "BoE", "SNB", "BoC", "PBoC"]:
        return source

    # Try to map from FeedSource value
    try:
        feed_source = FeedSource(source)
        return SOURCE_LABELS.get(feed_source, source)
    except ValueError:
        # Not a valid FeedSource, return as-is or extract meaningful part
        if "fed" in source.lower():
            return "Fed"
        elif "ecb" in source.lower():
            return "ECB"
        elif "boj" in source.lower():
            return "BoJ"
        elif "boe" in source.lower():
            return "BoE"
        elif "snb" in source.lower():
            return "SNB"
        elif "boc" in source.lower():
            return "BoC"
        elif "pboc" in source.lower():
            return "PBoC"
        return source


def format_time_ago(published: datetime | str | None) -> str:
    """Format a datetime as a human-readable 'time ago' string.

    Args:
        published: Publication datetime or ISO string.

    Returns:
        Human-readable time ago string (e.g., "2h ago", "3d ago").
    """
    if published is None:
        return "Unknown"

    # Parse if string
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            return "Unknown"

    # Ensure timezone aware
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)

    now = datetime.now(UTC)
    delta = now - published

    if delta < timedelta(minutes=1):
        return "Just now"
    elif delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() // 60)
        return f"{minutes}m ago"
    elif delta < timedelta(days=1):
        hours = int(delta.total_seconds() // 3600)
        return f"{hours}h ago"
    elif delta < timedelta(days=7):
        days = delta.days
        return f"{days}d ago"
    elif delta < timedelta(days=30):
        weeks = delta.days // 7
        return f"{weeks}w ago"
    else:
        return published.strftime("%b %d")


def news_items_from_newsitem_objects(
    items: list[NewsItem],
    sentiment_map: dict[str, str] | None = None,
) -> list[dict]:
    """Convert NewsItem objects to dictionary format for display.

    Args:
        items: List of NewsItem objects from the news module.
        sentiment_map: Optional mapping of item IDs to sentiment classifications.
            If not provided, defaults to neutral for all items.

    Returns:
        List of dictionaries suitable for create_news_items_list.
    """
    sentiment_map = sentiment_map or {}

    result = []
    for item in items:
        result.append({
            "title": item.title,
            "source": item.source.value,
            "sentiment": sentiment_map.get(item.id, SENTIMENT_NEUTRAL),
            "published": item.published,
            "link": str(item.link),
        })

    return result


def get_mock_news_items() -> list[dict]:
    """Get mock news items for testing/demo.

    Returns:
        List of sample news items.
    """
    now = datetime.now(UTC)
    return [
        {
            "title": "FOMC Minutes: Committee members discussed pace of rate cuts",
            "source": "Fed",
            "sentiment": SENTIMENT_HAWKISH,
            "published": now - timedelta(hours=2),
            "link": "https://federalreserve.gov/fomc",
        },
        {
            "title": "ECB Governing Council announces rate decision",
            "source": "ECB",
            "sentiment": SENTIMENT_DOVISH,
            "published": now - timedelta(hours=4),
            "link": "https://ecb.europa.eu/press",
        },
        {
            "title": "Bank of Japan maintains yield curve control policy",
            "source": "BoJ",
            "sentiment": SENTIMENT_NEUTRAL,
            "published": now - timedelta(hours=6),
            "link": "https://boj.or.jp/en",
        },
        {
            "title": "Fed Chair Powell speech on economic outlook",
            "source": "Fed",
            "sentiment": SENTIMENT_HAWKISH,
            "published": now - timedelta(days=1),
            "link": "https://federalreserve.gov/speeches",
        },
        {
            "title": "ECB Executive Board member comments on inflation",
            "source": "ECB",
            "sentiment": SENTIMENT_DOVISH,
            "published": now - timedelta(days=2),
            "link": "https://ecb.europa.eu/speeches",
        },
    ]
