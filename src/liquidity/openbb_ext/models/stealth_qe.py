"""OpenBB Fetcher for Stealth QE detection score."""

from datetime import UTC, datetime, timedelta
from datetime import date as dateType
from typing import Any

from openbb_core.provider.abstract.annotated_result import AnnotatedResult
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field


class LiquidityStealthQEQueryParams(QueryParams):
    """Stealth QE query parameters."""

    start_date: dateType | None = Field(
        default=None, description="Start date (default: 2 years ago)."
    )
    end_date: dateType | None = Field(
        default=None, description="End date (default: today)."
    )


class LiquidityStealthQEData(Data):
    """Stealth QE time-series data point."""

    date: dateType = Field(description="Observation date.")
    score_daily: float | None = Field(
        default=None, description="Daily smoothed Stealth QE score (0-100)."
    )
    rrp_level: float | None = Field(
        default=None, description="Reverse Repo level in billions USD."
    )
    tga_level: float | None = Field(
        default=None, description="TGA level in billions USD."
    )
    fed_total: float | None = Field(
        default=None, description="Fed total assets in billions USD."
    )
    comp_rrp: float | None = Field(
        default=None, description="RRP component score (0-100)."
    )
    comp_tga: float | None = Field(
        default=None, description="TGA component score (0-100)."
    )
    comp_fed: float | None = Field(
        default=None, description="Fed component score (0-100)."
    )
    status: str | None = Field(
        default=None, description="Activity classification (VERY_ACTIVE to MINIMAL)."
    )


class LiquidityStealthQEFetcher(
    Fetcher[LiquidityStealthQEQueryParams, list[LiquidityStealthQEData]]
):
    """Fetcher for Stealth QE data."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> LiquidityStealthQEQueryParams:
        """Set default date range if not provided."""
        transformed = params.copy()
        if transformed.get("start_date") is None:
            transformed["start_date"] = dateType.today() - timedelta(days=730)
        if transformed.get("end_date") is None:
            transformed["end_date"] = dateType.today()
        return LiquidityStealthQEQueryParams(**transformed)

    @staticmethod
    async def aextract_data(
        query: LiquidityStealthQEQueryParams,
        credentials: dict[str, str] | None,  # noqa: ARG004
        **kwargs: Any,  # noqa: ARG004
    ) -> list[dict]:
        """Extract Stealth QE data from calculator."""
        # Lazy import: avoids circular dependency with openbb import chain
        from liquidity.calculators.stealth_qe import StealthQECalculator

        calc = StealthQECalculator()
        assert query.start_date is not None  # noqa: S101
        assert query.end_date is not None  # noqa: S101
        start_dt = datetime(
            query.start_date.year, query.start_date.month, query.start_date.day, tzinfo=UTC
        )
        end_dt = datetime(
            query.end_date.year, query.end_date.month, query.end_date.day, tzinfo=UTC
        )
        df = await calc.calculate_daily(start_date=start_dt, end_date=end_dt)
        df = df.reset_index()
        if "timestamp" in df.columns:
            df = df.rename(columns={"timestamp": "date"})
        return df.to_dict("records")  # type: ignore[return-value]

    @staticmethod
    def transform_data(
        query: LiquidityStealthQEQueryParams,  # noqa: ARG004
        data: list[dict],
        **kwargs: Any,  # noqa: ARG004
    ) -> AnnotatedResult[list[LiquidityStealthQEData]]:
        """Validate and wrap data in AnnotatedResult."""
        return AnnotatedResult(
            result=[LiquidityStealthQEData.model_validate(d) for d in data]
        )
