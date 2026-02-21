"""Workspace-specific response schemas for OpenBB Workspace widgets.

These schemas produce the flat shapes required by Workspace:
- WorkspaceMetric: Simple KPI card (value + label + delta)
"""

from pydantic import BaseModel, Field


class WorkspaceMetric(BaseModel):
    """Response model for metric widgets in OpenBB Workspace.

    Returns a single KPI value with label, delta, and optional metadata.
    """

    value: float = Field(description="Primary metric value")
    label: str = Field(description="Display label for the metric")
    delta: float | None = Field(default=None, description="Change vs previous period")
    unit: str | None = Field(default=None, description="Unit of measurement (e.g. 'B USD')")
    sentiment: str | None = Field(
        default=None, description="Sentiment indicator (e.g. BULLISH, EXPANSION)"
    )
