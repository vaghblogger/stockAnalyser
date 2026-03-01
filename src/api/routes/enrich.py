"""POST /enrich - add technical indicators and volume/structure summaries."""

import math
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
    indicators: dict[str, Optional[float]]
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


@router.post("/enrich")
def post_enrich(request: Request, body: EnrichRequest):
    """Compute indicators and volume/structure from OHLCV."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    ind_config = config.analysis.indicators if config else None
    def _sanitize(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: _sanitize(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_sanitize(v) for v in o]
        if isinstance(o, float):
            return None if (math.isnan(o) or math.isinf(o)) else o
        if isinstance(o, (int,)):
            return o
        if pd.isna(o):
            return None
        try:
            import numpy as np
            if isinstance(o, (np.floating, np.integer)):
                v = float(o) if isinstance(o, np.floating) else int(o)
                return None if (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else v
        except Exception:
            pass
        if hasattr(o, "item"):
            try:
                v = o.item()
                return None if (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else v
            except Exception:
                return None
        # Catch-all: any number-like value (e.g. numpy scalar, decimal)
        try:
            if hasattr(o, "__float__") and not isinstance(o, (bool, str)):
                f = float(o)
                return None if (math.isnan(f) or math.isinf(f)) else f
        except (TypeError, ValueError):
            pass
        return o

    df = _records_to_df(body.ohlcv)
    if df.empty:
        return _sanitize({
            "ohlcv_with_indicators": [],
            "indicators": {},
            "volume_summary": "No data.",
            "structure_summary": "No data.",
        })
    df, last_indicators = compute_indicators(df, ind_config)
    vol_sum = volume_summary(df)
    struct_sum = structure_summary(df)
    # Serialize back to list of dicts (include indicator columns)
    def _safe_float(v: Any) -> Optional[float]:
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return None
        try:
            f = float(v)
            return None if (math.isnan(f) or math.isinf(f)) else f
        except (TypeError, ValueError):
            return None

    def _safe_int(v: Any) -> int:
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            return 0
        try:
            f = float(v)
            return 0 if (math.isnan(f) or math.isinf(f)) else int(f)
        except (TypeError, ValueError):
            return 0

    out_records = []
    for idx, row in df.iterrows():
        ts = idx.isoformat()[:10] if hasattr(idx, "isoformat") else str(idx)[:10]
        rec = {
            "date": ts,
            "Open": _safe_float(row["Open"]) or 0.0,
            "High": _safe_float(row["High"]) or 0.0,
            "Low": _safe_float(row["Low"]) or 0.0,
            "Close": _safe_float(row["Close"]) or 0.0,
            "Volume": _safe_int(row.get("Volume", 0)),
        }
        for col in df.columns:
            if col not in ("Open", "High", "Low", "Close", "Volume"):
                val = _safe_float(row[col])
                if val is not None:
                    rec[col] = val
        out_records.append(rec)

    safe_indicators = {k: _safe_float(v) for k, v in last_indicators.items()}

    # Build response dict manually (no Pydantic model_dump) so no nan/numpy slips through
    out = {
        "ohlcv_with_indicators": out_records,
        "indicators": safe_indicators,
        "volume_summary": vol_sum or "",
        "structure_summary": struct_sum or "",
    }
    return _sanitize(out)
