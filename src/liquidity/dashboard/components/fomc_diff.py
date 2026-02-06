"""FOMC Statement Diff Panel component.

Bloomberg-style side-by-side diff view for comparing FOMC statements.
Shows hawkish/dovish changes with red/green highlighting.

Panel Layout:
+------------------------------------------------+
| FOMC Statement Comparison                      |
+------------------------------------------------+
| Date 1: [Dec 2024]  Date 2: [Jan 2025]         |
+------------------------------------------------+
| Change: HAWKISH (+0.35)                        |
| Key shifts: +vigilant, -patient, +tight        |
+------------------------------------------------+
| [Side-by-side diff view with colored text]     |
| The Committee -patient- +vigilant+ about...    |
+------------------------------------------------+
"""

from datetime import date

import dash_bootstrap_components as dbc
from dash import dcc, html

from liquidity.news.fomc.diff import ChangeScore, PhraseShift, StatementDiff


# =============================================================================
# Color Constants (Bloomberg-style)
# =============================================================================

HAWKISH_COLOR = "#ff4444"  # Red for hawkish/tightening
DOVISH_COLOR = "#00ff88"   # Green for dovish/easing
NEUTRAL_COLOR = "#888888"  # Gray for neutral


# =============================================================================
# Panel Components
# =============================================================================


def create_fomc_diff_panel() -> dbc.Card:
    """Create the FOMC statement diff panel.

    Returns:
        Bootstrap Card with date selectors, change summary, and diff view.
    """
    return dbc.Card(
        [
            dbc.CardHeader(
                [
                    html.I(className="bi bi-file-diff me-2"),
                    "FOMC Statement Comparison",
                ],
                className="d-flex align-items-center",
            ),
            dbc.CardBody(
                [
                    # Date selector row
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Label(
                                        "Previous Statement",
                                        html_for="fomc-date-1",
                                        className="text-muted small",
                                    ),
                                    dcc.Dropdown(
                                        id="fomc-date-1",
                                        placeholder="Select date...",
                                        className="mb-2",
                                        style={"backgroundColor": "#2a2a3e"},
                                    ),
                                ],
                                width=6,
                            ),
                            dbc.Col(
                                [
                                    dbc.Label(
                                        "Current Statement",
                                        html_for="fomc-date-2",
                                        className="text-muted small",
                                    ),
                                    dcc.Dropdown(
                                        id="fomc-date-2",
                                        placeholder="Select date...",
                                        className="mb-2",
                                        style={"backgroundColor": "#2a2a3e"},
                                    ),
                                ],
                                width=6,
                            ),
                        ],
                        className="mb-3",
                    ),
                    # Compare button
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    [
                                        html.I(className="bi bi-arrow-left-right me-2"),
                                        "Compare Statements",
                                    ],
                                    id="fomc-compare-btn",
                                    color="primary",
                                    outline=True,
                                    size="sm",
                                    className="w-100",
                                ),
                                width={"size": 6, "offset": 3},
                            ),
                        ],
                        className="mb-3",
                    ),
                    # Change summary (dynamically populated)
                    html.Div(id="fomc-change-summary", className="mb-3"),
                    # Separator
                    html.Hr(className="my-2"),
                    # Diff view (dynamically populated)
                    html.Div(
                        id="fomc-diff-view",
                        className="fomc-diff-container",
                        style={
                            "maxHeight": "400px",
                            "overflowY": "auto",
                            "backgroundColor": "#1a1a2e",
                            "padding": "15px",
                            "borderRadius": "8px",
                        },
                    ),
                ]
            ),
        ],
        className="h-100",
    )


def create_change_summary(change_score: ChangeScore, phrase_shifts: list[PhraseShift]) -> html.Div:
    """Create the change score summary display.

    Args:
        change_score: ChangeScore with direction, magnitude, and key changes.
        phrase_shifts: List of detected policy phrase shifts.

    Returns:
        Div with styled change summary.
    """
    # Determine color and arrow based on direction
    if change_score.direction == "hawkish":
        color = HAWKISH_COLOR
        arrow = "\u25b2"  # Up arrow
        direction_text = "HAWKISH"
    elif change_score.direction == "dovish":
        color = DOVISH_COLOR
        arrow = "\u25bc"  # Down arrow
        direction_text = "DOVISH"
    else:
        color = NEUTRAL_COLOR
        arrow = "\u25cf"  # Circle
        direction_text = "NEUTRAL"

    # Format magnitude
    mag_sign = "+" if change_score.magnitude >= 0 else ""
    magnitude_text = f"({mag_sign}{change_score.magnitude:.2f})"

    # Build phrase shifts summary
    shift_badges = []
    for shift in phrase_shifts[:6]:  # Limit to 6 phrases
        if shift.change == "added":
            badge_color = (
                HAWKISH_COLOR if shift.policy_signal == "hawkish" else DOVISH_COLOR
            )
            prefix = "+"
        else:
            badge_color = (
                HAWKISH_COLOR if shift.policy_signal == "hawkish" else DOVISH_COLOR
            )
            prefix = "-"

        shift_badges.append(
            dbc.Badge(
                f"{prefix}{shift.phrase}",
                style={
                    "backgroundColor": badge_color,
                    "color": "#fff" if badge_color == HAWKISH_COLOR else "#000",
                    "marginRight": "5px",
                    "marginBottom": "5px",
                },
            )
        )

    return html.Div(
        [
            # Main change indicator
            html.Div(
                [
                    html.Span(
                        f"{arrow} {direction_text}",
                        style={
                            "color": color,
                            "fontSize": "1.2rem",
                            "fontWeight": "bold",
                            "marginRight": "10px",
                        },
                    ),
                    html.Span(
                        magnitude_text,
                        style={"color": color, "fontSize": "1rem"},
                    ),
                ],
                className="mb-2",
            ),
            # Key phrase shifts
            html.Div(
                [
                    html.Small("Key policy shifts: ", className="text-muted"),
                    html.Div(shift_badges, className="d-inline"),
                ]
            )
            if shift_badges
            else None,
        ]
    )


def create_diff_view(diff: StatementDiff) -> html.Div:
    """Create the diff view from StatementDiff HTML.

    Uses the pre-rendered HTML from the diff engine with inline styles.

    Args:
        diff: StatementDiff with rendered HTML.

    Returns:
        Div containing the diff HTML.
    """
    # The diff.html already contains <style> and styled spans
    # We wrap it in an Iframe component or use dangerously_set_inner_html
    return html.Div(
        [
            # Date header
            html.Div(
                [
                    html.Small(
                        f"Comparing: {diff.old_date.strftime('%b %d, %Y')} "
                        f"\u2192 {diff.new_date.strftime('%b %d, %Y')}",
                        className="text-muted",
                    ),
                    html.Small(
                        f" | Unchanged: {diff.unchanged_ratio:.0%}",
                        className="text-muted ms-2",
                    ),
                ],
                className="mb-2",
            ),
            # Diff content (using Dash's html.Iframe for isolated styles)
            html.Iframe(
                srcDoc=diff.html,
                style={
                    "width": "100%",
                    "height": "350px",
                    "border": "none",
                    "backgroundColor": "#1a1a2e",
                },
            ),
        ]
    )


def create_empty_diff_view(message: str = "Select two statement dates to compare") -> html.Div:
    """Create placeholder when no diff is available.

    Args:
        message: Message to display.

    Returns:
        Div with placeholder message.
    """
    return html.Div(
        [
            html.I(
                className="bi bi-file-earmark-text",
                style={"fontSize": "3rem", "color": "#444"},
            ),
            html.P(
                message,
                className="text-muted mt-3",
            ),
        ],
        className="text-center py-5",
    )


def create_loading_diff_view() -> html.Div:
    """Create loading state for diff view.

    Returns:
        Div with loading spinner.
    """
    return html.Div(
        [
            dbc.Spinner(color="primary", type="border", size="lg"),
            html.P("Loading statements...", className="text-muted mt-3"),
        ],
        className="text-center py-5",
    )


def create_error_diff_view(error_message: str) -> html.Div:
    """Create error state for diff view.

    Args:
        error_message: Error message to display.

    Returns:
        Div with error message.
    """
    return html.Div(
        [
            html.I(
                className="bi bi-exclamation-triangle",
                style={"fontSize": "3rem", "color": HAWKISH_COLOR},
            ),
            html.P(
                error_message,
                className="text-danger mt-3",
            ),
        ],
        className="text-center py-5",
    )


# =============================================================================
# Helper Functions for Callbacks
# =============================================================================


def format_date_option(statement_date: date) -> dict:
    """Format a date for dropdown option.

    Args:
        statement_date: Date to format.

    Returns:
        Dropdown option dict with label and value.
    """
    return {
        "label": statement_date.strftime("%b %d, %Y"),
        "value": statement_date.isoformat(),
    }


def get_available_dates_options(dates: list[date]) -> list[dict]:
    """Convert list of dates to dropdown options.

    Args:
        dates: List of available statement dates.

    Returns:
        List of dropdown option dicts.
    """
    # Sort descending (most recent first)
    sorted_dates = sorted(dates, reverse=True)
    return [format_date_option(d) for d in sorted_dates]


def parse_date_value(value: str | None) -> date | None:
    """Parse date value from dropdown.

    Args:
        value: ISO format date string or None.

    Returns:
        date object or None.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
