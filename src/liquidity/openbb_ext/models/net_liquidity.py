"""OpenBB Fetcher for Net Liquidity (Hayes formula: WALCL - TGA - RRP)."""

from datetime import UTC, datetime, timedelta
from datetime import date as dateType
from typing import Any

from openbb_core.provider.abstract.annotated_result import AnnotatedResult
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field


class LiquidityNetLiquidityQueryParams(QueryParams):
    """Net Liquidity query parameters."""

    start_date: dateType | None = Field(
        default=None, description="Start date (default: 2 years ago)."
    )
    end_date: dateType | None = Field(
        default=None, description="End date (default: today)."
    )


class LiquidityNetLiquidityData(Data):
    """Net Liquidity time-series data point."""

    date: dateType = Field(description="Observation date.")
    net_liquidity: float | None = Field(
        default=None, description="Net Liquidity in billions USD."
    )
    walcl: float | None = Field(
        default=None, description="Fed Total Assets (WALCL) in billions USD."
    )
    tga: float | None = Field(
        default=None, description="Treasury General Account in billions USD."
    )
    rrp: float | None = Field(
        default=None, description="Reverse Repo in billions USD."
    )


class LiquidityNetLiquidityFetcher(
    Fetcher[LiquidityNetLiquidityQueryParams, list[LiquidityNetLiquidityData]]
):
    """Fetcher for Net Liquidity data."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> LiquidityNetLiquidityQueryParams:
        """Set default date range if not provided."""
        transformed = params.copy()
        if transformed.get("start_date") is None:
            transformed["start_date"] = dateType.today() - timedelta(days=730)
        if transformed.get("end_date") is None:
            transformed["end_date"] = dateType.today()
        return LiquidityNetLiquidityQueryParams(**transformed)

    @staticmethod
    async def aextract_data(
        query: LiquidityNetLiquidityQueryParams,
        credentials: dict[str, str] | None,  # noqa: ARG004
        **kwargs: Any,  # noqa: ARG004
    ) -> list[dict]:
        """Extract net liquidity data from calculator."""
        # Lazy import: avoids circular dependency with openbb import chain
        from liquidity.calculators.net_liquidity import NetLiquidityCalculator

        calc = NetLiquidityCalculator()
        assert query.start_date is not None  # noqa: S101
        assert query.end_date is not None  # noqa: S101
        start_dt = datetime(
            query.start_date.year, query.start_date.month, query.start_date.day, tzinfo=UTC
        )
        end_dt = datetime(
            query.end_date.year, query.end_date.month, query.end_date.day, tzinfo=UTC
        )
        df = await calc.calculate(start_date=start_dt, end_date=end_dt)
        df = df.reset_index()
        if "timestamp" in df.columns:
            df = df.rename(columns={"timestamp": "date"})
        return df.to_dict("records")  # type: ignore[return-value]

    @staticmethod
    def transform_data(
        query: LiquidityNetLiquidityQueryParams,  # noqa: ARG004
        data: list[dict],
        **kwargs: Any,  # noqa: ARG004
    ) -> AnnotatedResult[list[LiquidityNetLiquidityData]]:
        """Validate and wrap data in AnnotatedResult."""
        return AnnotatedResult(
            result=[LiquidityNetLiquidityData.model_validate(d) for d in data]
        )
