"""POST /risk - risk and volatility summary from OHLCV + indicators."""

from typing import Optional

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from src.analysis.risk import risk_summary, volatility_regime

router = APIRouter()


class RiskRequest(BaseModel):
    ohlcv: list[dict]
    indicators: Optional[dict[str, float]] = None


class RiskResponse(BaseModel):
    risk_summary: str
    volatility_regime: str


def _records_to_df(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    return df


@router.post("/risk", response_model=RiskResponse)
def post_risk(body: RiskRequest):
    df = _records_to_df(body.ohlcv)
    risk_sum = risk_summary(df, body.indicators)
    regime = volatility_regime(body.indicators)
    return RiskResponse(risk_summary=risk_sum, volatility_regime=regime)
