"""POST /enrich - add technical indicators and volume/structure summaries."""

from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.analysis.indicators import compute_indicators
from src.analysis.volume_structure import structure_summary, volume_summary

router = APIRouter()


class EnrichRequest(BaseModel):
    ohlcv: list[dict]
    symbol: Optional[str] = None


class EnrichResponse(BaseModel):
    ohlcv_with_indicators: list[dict]
    indicators: dict[str, float]
    volume_summary: str
    structure_summary: str


def _records_to_df(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    return df


@router.post("/enrich", response_model=EnrichResponse)
def post_enrich(request: Request, body: EnrichRequest):
    """Compute indicators and volume/structure from OHLCV."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    ind_config = config.analysis.indicators if config else None
    df = _records_to_df(body.ohlcv)
    if df.empty:
        return EnrichResponse(
            ohlcv_with_indicators=[],
            indicators={},
            volume_summary="No data.",
            structure_summary="No data.",
        )
    df, last_indicators = compute_indicators(df, ind_config)
    vol_sum = volume_summary(df)
    struct_sum = structure_summary(df)
    # Serialize back to list of dicts (include indicator columns)
    out_records = []
    for idx, row in df.iterrows():
        ts = idx.isoformat()[:10] if hasattr(idx, "isoformat") else str(idx)[:10]
        rec = {"date": ts, "Open": float(row["Open"]), "High": float(row["High"]), "Low": float(row["Low"]), "Close": float(row["Close"]), "Volume": int(row.get("Volume", 0))}
        for col in df.columns:
            if col not in ("Open", "High", "Low", "Close", "Volume"):
                val = row[col]
                if pd.notna(val):
                    rec[col] = float(val)
        out_records.append(rec)
    return EnrichResponse(
        ohlcv_with_indicators=out_records,
        indicators=last_indicators,
        volume_summary=vol_sum,
        structure_summary=struct_sum,
    )
