"""POST /trend - trend and pattern flags from enriched OHLCV + indicators."""

from typing import Optional

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from src.analysis.trend import pattern_flags, trend_summary

router = APIRouter()


class TrendRequest(BaseModel):
    ohlcv: list[dict]
    indicators: Optional[dict[str, float]] = None


class TrendResponse(BaseModel):
    trend_summary: str
    pattern_flags: list[str]


def _records_to_df(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    return df


@router.post("/trend", response_model=TrendResponse)
def post_trend(body: TrendRequest):
    df = _records_to_df(body.ohlcv)
    trend_sum = trend_summary(df, body.indicators)
    flags = pattern_flags(df, body.indicators)
    return TrendResponse(trend_summary=trend_sum, pattern_flags=flags)
