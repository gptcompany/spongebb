"""FOMC Statement schemas using Pydantic.

Defines the data model for FOMC statements with validation and serialization.
"""

from datetime import date as DateType
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field


class FOMCStatement(BaseModel):
    """FOMC monetary policy statement.

    Represents a Federal Reserve FOMC statement with metadata and content.

    Attributes:
        date: Publication date of the statement.
        meeting_date: FOMC meeting date (may differ from publication).
        raw_text: Full text of the statement (cleaned, no HTML).
        source: Data source tier (fed, fedtools, github).
        url: Source URL where statement was fetched from.
        fetched_at: Timestamp when data was fetched.
        cached_at: Timestamp when data was cached (None if not cached).
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
    )

    date: DateType = Field(
        description="Publication date of the FOMC statement",
    )
    meeting_date: DateType = Field(
        description="FOMC meeting date (may differ from publication date)",
    )
    raw_text: str = Field(
        min_length=100,
        description="Full text of the statement (cleaned, no HTML tags)",
    )
    source: Literal["fed", "fedtools", "github"] = Field(
        description="Data source tier: fed (official), fedtools (library), github (archive)",
    )
    url: HttpUrl = Field(
        description="Source URL where the statement was fetched from",
    )
    fetched_at: datetime = Field(
        description="Timestamp when the data was fetched",
    )
    cached_at: datetime | None = Field(
        default=None,
        description="Timestamp when the data was cached locally (None if fresh fetch)",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def word_count(self) -> int:
        """Count words in the statement text.

        Returns:
            Number of words in raw_text.
        """
        return len(self.raw_text.split())

    def to_cache_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for JSON caching.

        Handles datetime serialization for JSON storage.

        Returns:
            Dictionary with JSON-serializable values.
        """
        return {
            "date": self.date.isoformat(),
            "meeting_date": self.meeting_date.isoformat(),
            "raw_text": self.raw_text,
            "source": self.source,
            "url": str(self.url),
            "fetched_at": self.fetched_at.isoformat(),
            "cached_at": datetime.utcnow().isoformat(),
            "word_count": self.word_count,
        }

    @classmethod
    def from_cache_dict(cls, data: dict[str, Any]) -> "FOMCStatement":
        """Create instance from cached dictionary.

        Args:
            data: Dictionary loaded from JSON cache.

        Returns:
            FOMCStatement instance.
        """
        return cls(
            date=DateType.fromisoformat(data["date"]),
            meeting_date=DateType.fromisoformat(data["meeting_date"]),
            raw_text=data["raw_text"],
            source=data["source"],
            url=data["url"],
            fetched_at=datetime.fromisoformat(data["fetched_at"]),
            cached_at=(
                datetime.fromisoformat(data["cached_at"])
                if data.get("cached_at")
                else None
            ),
        )


class FOMCStatementCollection(BaseModel):
    """Collection of FOMC statements.

    Useful for batch operations and analysis.
    """

    model_config = ConfigDict(frozen=True)

    statements: list[FOMCStatement] = Field(
        default_factory=list,
        description="List of FOMC statements ordered by date",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def count(self) -> int:
        """Number of statements in collection."""
        return len(self.statements)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def date_range(self) -> tuple[DateType, DateType] | None:
        """Date range of statements in collection.

        Returns:
            Tuple of (earliest_date, latest_date) or None if empty.
        """
        if not self.statements:
            return None
        dates = [s.date for s in self.statements]
        return (min(dates), max(dates))

    def get_by_date(self, target_date: DateType) -> FOMCStatement | None:
        """Get statement by exact date.

        Args:
            target_date: Date to search for.

        Returns:
            FOMCStatement if found, None otherwise.
        """
        for statement in self.statements:
            if statement.date == target_date:
                return statement
        return None
