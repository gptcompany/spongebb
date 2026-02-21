"""OpenBB Fetcher for Global Liquidity (Fed + ECB + BoJ + PBoC in USD)."""

from datetime import UTC, datetime, timedelta
from datetime import date as dateType
from typing import Any

from openbb_core.provider.abstract.annotated_result import AnnotatedResult
from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from pydantic import Field


class LiquidityGlobalLiquidityQueryParams(QueryParams):
    """Global Liquidity query parameters."""

    start_date: dateType | None = Field(
        default=None, description="Start date (default: 2 years ago)."
    )
    end_date: dateType | None = Field(
        default=None, description="End date (default: today)."
    )
    tier: int = Field(
        default=1,
        description="CB tier: 1 = Fed+ECB+BoJ+PBoC, 2 = includes BoE+SNB+BoC.",
    )


class LiquidityGlobalLiquidityData(Data):
    """Global Liquidity time-series data point."""

    date: dateType = Field(description="Observation date.")
    global_liquidity: float | None = Field(
        default=None, description="Total global liquidity in billions USD."
    )
    fed_usd: float | None = Field(
        default=None, description="Fed contribution in billions USD."
    )
    ecb_usd: float | None = Field(
        default=None, description="ECB contribution in billions USD."
    )
    boj_usd: float | None = Field(
        default=None, description="BoJ contribution in billions USD."
    )
    pboc_usd: float | None = Field(
        default=None, description="PBoC contribution in billions USD."
    )
    boe_usd: float | None = Field(
        default=None, description="BoE contribution in billions USD (Tier 2 only)."
    )
    snb_usd: float | None = Field(
        default=None, description="SNB contribution in billions USD (Tier 2 only)."
    )
    boc_usd: float | None = Field(
        default=None, description="BoC contribution in billions USD (Tier 2 only)."
    )


class LiquidityGlobalLiquidityFetcher(
    Fetcher[LiquidityGlobalLiquidityQueryParams, list[LiquidityGlobalLiquidityData]]
):
    """Fetcher for Global Liquidity data."""

    @staticmethod
    def transform_query(params: dict[str, Any]) -> LiquidityGlobalLiquidityQueryParams:
        """Set default date range if not provided."""
        transformed = params.copy()
        if transformed.get("start_date") is None:
            transformed["start_date"] = dateType.today() - timedelta(days=730)
        if transformed.get("end_date") is None:
            transformed["end_date"] = dateType.today()
        return LiquidityGlobalLiquidityQueryParams(**transformed)

    @staticmethod
    async def aextract_data(
        query: LiquidityGlobalLiquidityQueryParams,
        credentials: dict[str, str] | None,  # noqa: ARG004
        **kwargs: Any,  # noqa: ARG004
    ) -> list[dict]:
        """Extract global liquidity data from calculator."""
        # Lazy import: avoids circular dependency with openbb import chain
        from liquidity.calculators.global_liquidity import GlobalLiquidityCalculator

        calc = GlobalLiquidityCalculator()
        assert query.start_date is not None  # noqa: S101
        assert query.end_date is not None  # noqa: S101
        start_dt = datetime(
            query.start_date.year, query.start_date.month, query.start_date.day, tzinfo=UTC
        )
        end_dt = datetime(
            query.end_date.year, query.end_date.month, query.end_date.day, tzinfo=UTC
        )
        df = await calc.calculate(start_date=start_dt, end_date=end_dt, tier=query.tier)
        df = df.reset_index()
        if "timestamp" in df.columns:
            df = df.rename(columns={"timestamp": "date"})
        return df.to_dict("records")  # type: ignore[return-value]

    @staticmethod
    def transform_data(
        query: LiquidityGlobalLiquidityQueryParams,  # noqa: ARG004
        data: list[dict],
        **kwargs: Any,  # noqa: ARG004
    ) -> AnnotatedResult[list[LiquidityGlobalLiquidityData]]:
        """Validate and wrap data in AnnotatedResult."""
        return AnnotatedResult(
            result=[LiquidityGlobalLiquidityData.model_validate(d) for d in data]
        )
