"""Calendar endpoints for liquidity-impacting events.

Provides:
- GET /calendar/events - Calendar events within a date range
- GET /calendar/next - Next N upcoming events
"""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from liquidity.api.deps import CalendarRegistryDep
from liquidity.api.schemas import (
    APIMetadata,
    CalendarEventData,
    CalendarEventsResponse,
)
from liquidity.calendar.base import EventType, ImpactLevel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get(
    "/events",
    response_model=CalendarEventsResponse,
    summary="Get Calendar Events",
    description="Returns liquidity-impacting events within a date range.",
    openapi_extra={
        "widget_config": {
            "name": "Macro Calendar",
            "description": "Upcoming liquidity-impacting events (auctions, Fed meetings, etc.)",
            "category": "Calendar",
            "type": "table",
            "refetchInterval": 3600000,
            "gridData": {"w": 20, "h": 8},
            "data": {
                "dataKey": "events",
                "table": {
                    "columnsDefs": [
                        {"field": "date", "headerName": "Date", "cellDataType": "dateString", "pinned": "left"},
                        {"field": "event_type", "headerName": "Type", "renderFn": "titleCase"},
                        {"field": "title", "headerName": "Event"},
                        {"field": "impact", "headerName": "Impact", "renderFn": "greenRed"},
                    ]
                },
            },
        }
    },
)
async def get_calendar_events(
    registry: CalendarRegistryDep,
    start: Annotated[
        date | None,
        Query(description="Start date (YYYY-MM-DD). Defaults to today."),
    ] = None,
    end: Annotated[
        date | None,
        Query(description="End date (YYYY-MM-DD). Defaults to 30 days from start."),
    ] = None,
    event_type: Annotated[
        str | None,
        Query(
            description="Filter by event type: treasury_auction, fed_meeting, ecb_meeting, "
            "boj_meeting, boe_meeting, tax_date, quarter_end, month_end, holiday"
        ),
    ] = None,
    impact: Annotated[
        str | None,
        Query(description="Filter by impact level: low, medium, high"),
    ] = None,
) -> CalendarEventsResponse:
    """Get calendar events affecting liquidity.

    Event types:
    - treasury_auction: US Treasury bill/note/bond auctions
    - fed_meeting: FOMC meetings
    - ecb_meeting: ECB governing council meetings
    - boj_meeting: BoJ policy meetings
    - tax_date: Corporate/estimated tax payment dates
    - quarter_end: Quarter-end window dressing
    - holiday: Market holidays (closed)

    Impact levels:
    - high: Major events (10Y/30Y auctions, FOMC decisions, quarter-end)
    - medium: Standard events (2Y auctions, other CB meetings)
    - low: Minor events (bill auctions, partial holidays)

    Args:
        registry: Injected CalendarRegistry.
        start: Start date (default today).
        end: End date (default 30 days from start).
        event_type: Filter by specific event type.
        impact: Filter by impact level.

    Returns:
        CalendarEventsResponse with filtered events.

    Raises:
        HTTPException: If date range invalid.
    """
    try:
        # Set default dates
        if start is None:
            start = date.today()
        if end is None:
            end = start + timedelta(days=30)

        if end < start:
            raise ValueError("End date must be after start date")

        # Get all events in range
        events = registry.get_events(start, end)

        # Filter by event type if specified
        if event_type:
            try:
                et = EventType(event_type)
                events = [e for e in events if e.event_type == et]
            except ValueError as err:
                raise ValueError(f"Invalid event_type: {event_type}") from err

        # Filter by impact if specified
        if impact:
            try:
                il = ImpactLevel(impact)
                events = [e for e in events if e.impact == il]
            except ValueError as err:
                raise ValueError(f"Invalid impact level: {impact}") from err

        # Convert to response format
        event_data = [
            CalendarEventData(
                date=e.event_date.isoformat(),
                event_type=e.event_type.value,
                title=e.title,
                description=e.description,
                settlement_date=e.settlement_date.isoformat() if e.settlement_date else None,
                impact=e.impact.value,
            )
            for e in events
        ]

        return CalendarEventsResponse(
            start=start.isoformat(),
            end=end.isoformat(),
            count=len(event_data),
            events=event_data,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except ValueError as e:
        logger.warning("Calendar events fetch failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Unexpected error in get_calendar_events")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e


@router.get(
    "/next",
    response_model=CalendarEventsResponse,
    summary="Get Next Events",
    description="Returns the next N upcoming high-impact events.",
    openapi_extra={
        "widget_config": {
            "name": "Next Liquidity Events",
            "description": "Upcoming high-impact liquidity events",
            "category": "Calendar",
            "type": "table",
            "refetchInterval": 3600000,
            "gridData": {"w": 20, "h": 6},
            "data": {"dataKey": "events"},
        }
    },
)
async def get_next_events(
    registry: CalendarRegistryDep,
    limit: Annotated[
        int,
        Query(ge=1, le=50, description="Number of events to return (1-50)"),
    ] = 5,
    high_impact_only: Annotated[
        bool,
        Query(description="Only return high-impact events"),
    ] = True,
) -> CalendarEventsResponse:
    """Get next upcoming liquidity events.

    Returns the next N events from today, optionally filtering
    to high-impact events only.

    Args:
        registry: Injected CalendarRegistry.
        limit: Maximum number of events to return.
        high_impact_only: If True, only return high-impact events.

    Returns:
        CalendarEventsResponse with upcoming events.

    Raises:
        HTTPException: If fetch fails.
    """
    try:
        start = date.today()
        # Search up to 1 year ahead
        end = date(start.year + 1, start.month, start.day)

        if high_impact_only:
            events = registry.get_high_impact_events(start, end)
        else:
            events = registry.get_events(start, end)

        # Limit results
        events = events[:limit]

        # Determine actual date range of results
        actual_end = max(e.event_date for e in events) if events else start

        # Convert to response format
        event_data = [
            CalendarEventData(
                date=e.event_date.isoformat(),
                event_type=e.event_type.value,
                title=e.title,
                description=e.description,
                settlement_date=e.settlement_date.isoformat() if e.settlement_date else None,
                impact=e.impact.value,
            )
            for e in events
        ]

        return CalendarEventsResponse(
            start=start.isoformat(),
            end=actual_end.isoformat(),
            count=len(event_data),
            events=event_data,
            metadata=APIMetadata(timestamp=datetime.now(UTC)),
        )
    except Exception as e:
        logger.exception("Unexpected error in get_next_events")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {e}",
        ) from e
