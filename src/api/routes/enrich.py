"""POST /enrich - add technical indicators and volume/structure summaries."""

import json
import math
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.analysis.indicators import compute_indicators
from src.analysis.volume_structure import structure_summary, volume_summary

router = APIRouter()


def _ensure_no_bad_floats(obj: Any) -> Any:
    """Recursively replace any non-finite float with None; coerce numbers to native Python."""
    if isinstance(obj, dict):
        return {k: _ensure_no_bad_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_ensure_no_bad_floats(v) for v in obj]
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return None
        return float(obj)
    if isinstance(obj, (int,)) and not isinstance(obj, bool):
        return int(obj)
    if obj is None or isinstance(obj, bool) or isinstance(obj, str):
        return obj
    # number-like (numpy scalar, etc.)
    try:
        if hasattr(obj, "__float__"):
            f = float(obj)
            return None if not math.isfinite(f) else float(f)
    except (TypeError, ValueError):
        pass
    return obj


class EnrichRequest(BaseModel):
    ohlcv: list[dict]
    symbol: Optional[str] = None


class EnrichResponse(BaseModel):
    ohlcv_with_indicators: list[dict]
    indicators: dict[str, Optional[float]]
    volume_summary: str
    structure_summary: str


def _pick(d: dict, *keys: str):
    """First key that exists in d (case-insensitive)."""
    d_upper = {k.upper() if isinstance(k, str) else k: k for k in d}
    for want in keys:
        if want.upper() in d_upper:
            return d.get(d_upper[want.upper()])
    return None


def _to_float(x: Any) -> Optional[float]:
    """Coerce to float; handle strings (including comma decimals), None, int."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(x) else None
    if isinstance(x, str):
        s = x.strip().replace(",", "")
        if not s:
            return None
        try:
            f = float(s)
            return f if math.isfinite(f) else None
        except ValueError:
            return None
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _records_to_df(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    # Build rows with canonical keys so indicators always see Open, High, Low, Close, Volume
    rows = []
    for r in records:
        if not isinstance(r, dict):
            continue
        date_val = _pick(r, "date", "Date", "DATE")
        close_val = _pick(r, "Close", "close", "CLOSE")
        if date_val is None:
            continue
        close_f = _to_float(close_val) if close_val is not None else None
        if close_f is None:
            continue
        open_f = _to_float(_pick(r, "Open", "open", "OPEN"))
        high_f = _to_float(_pick(r, "High", "high", "HIGH"))
        low_f = _to_float(_pick(r, "Low", "low", "LOW"))
        vol = _pick(r, "Volume", "volume", "VOLUME")
        vol_f = _to_float(vol) if vol is not None else (int(vol) if isinstance(vol, int) else 0.0)
        if vol_f is None:
            vol_f = 0.0
        rows.append({
            "date": date_val,
            "Open": open_f if open_f is not None else close_f,
            "High": high_f if high_f is not None else close_f,
            "Low": low_f if low_f is not None else close_f,
            "Close": close_f,
            "Volume": vol_f,
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    if df.empty:
        return pd.DataFrame()
    df = df.set_index("date")
    for col in ("Open", "High", "Low", "Close", "Volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Fill any remaining NaN in OHLC with forward/backward fill so indicators can compute
    ohlc = ["Open", "High", "Low", "Close"]
    for c in ohlc:
        if c in df.columns and df[c].isna().any():
            df[c] = df[c].ffill().bfill()
    if df["Close"].isna().all():
        return pd.DataFrame()
    return df.sort_index()


@router.post("/enrich")
def post_enrich(request: Request, body: EnrichRequest, debug: bool = Query(False)):
    """Compute indicators and volume/structure from OHLCV."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    ind_config = config.analysis.indicators if config else None
    def _sanitize(o: Any) -> Any:
        """Return only JSON-serializable types; convert nan/inf to None and numpy to native Python."""
        if isinstance(o, dict):
            return {k: _sanitize(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_sanitize(v) for v in o]
        if isinstance(o, bool) or o is None:
            return o
        if isinstance(o, (int,)) and not isinstance(o, bool):
            return int(o)
        if isinstance(o, float):
            if math.isnan(o) or math.isinf(o):
                return None
            return float(o)  # ensure native Python float
        if pd.isna(o):
            return None
        try:
            import numpy as np
            if isinstance(o, (np.floating, np.integer)):
                v = float(o) if isinstance(o, np.floating) else int(o)
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    return None
                return v if isinstance(v, int) else float(v)
        except Exception:
            pass
        if hasattr(o, "item"):
            try:
                v = o.item()
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    return None
                return float(v) if isinstance(v, (int, float)) else v
            except Exception:
                return None
        try:
            if hasattr(o, "__float__") and not isinstance(o, (bool, str)):
                f = float(o)
                if math.isnan(f) or math.isinf(f):
                    return None
                return float(f)
        except (TypeError, ValueError):
            pass
        return o

    df = _records_to_df(body.ohlcv)
    if df.empty:
        data = _ensure_no_bad_floats(_sanitize({
            "ohlcv_with_indicators": [],
            "indicators": {},
            "volume_summary": "No data.",
            "structure_summary": "No data.",
        }))
        return JSONResponse(content=data)
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

    def _finite_float(v: Any, default: float = 0.0) -> float:
        x = _safe_float(v) or default
        return default if not math.isfinite(x) else float(x)

    # Known indicator keys for the summary panel (order matches frontend)
    INDICATOR_KEYS = (
        "sma_20", "sma_50", "sma_200", "ema_12", "ema_26", "rsi",
        "macd", "macd_signal", "macd_hist", "atr", "bb_upper", "bb_lower", "obv", "close",
    )
    out_records = []
    for idx, row in df.iterrows():
        ts = idx.isoformat()[:10] if hasattr(idx, "isoformat") else str(idx)[:10]
        rec = {
            "date": ts,
            "Open": _finite_float(row["Open"]),
            "High": _finite_float(row["High"]),
            "Low": _finite_float(row["Low"]),
            "Close": _finite_float(row["Close"]),
            "Volume": int(_safe_int(row.get("Volume", 0))),
        }
        for col in df.columns:
            if col not in ("Open", "High", "Low", "Close", "Volume"):
                val = _safe_float(row[col])
                if val is not None and math.isfinite(val):
                    rec[col] = float(val)
        out_records.append(rec)

    # Build indicators: use last_indicators (last finite value in series), fallback to last row
    safe_indicators = {}
    # Include last close from dataframe so frontend has one source for price
    if not df.empty and "Close" in df.columns:
        last_close = _safe_float(df["Close"].iloc[-1])
        if last_close is not None and math.isfinite(last_close):
            safe_indicators["close"] = float(last_close)
    for k in INDICATOR_KEYS:
        if k == "close" and safe_indicators.get("close") is not None:
            continue
        v = last_indicators.get(k)
        try:
            x = float(v) if v is not None else None
            safe_indicators[k] = x if (x is not None and math.isfinite(x)) else None
        except (TypeError, ValueError):
            safe_indicators[k] = None
    if out_records:
        last_rec = out_records[-1]
        for k in INDICATOR_KEYS:
            if safe_indicators.get(k) is not None:
                continue
            v = last_rec.get(k)
            if v is not None and isinstance(v, (int, float)) and math.isfinite(v):
                safe_indicators[k] = float(v)
        if safe_indicators.get("close") is None:
            c = last_rec.get("Close")
            if c is not None and isinstance(c, (int, float)) and math.isfinite(c):
                safe_indicators["close"] = float(c)
        for k, v in last_rec.items():
            if k in ("date", "Open", "High", "Low", "Close", "Volume") or k in INDICATOR_KEYS:
                continue
            if v is not None and isinstance(v, (int, float)) and math.isfinite(v):
                safe_indicators[k] = float(v)

    # Sanitize only the list of records (nested floats); leave indicators/summaries as-is
    safe_records = _ensure_no_bad_floats(_sanitize(out_records))
    data = {
        "ohlcv_with_indicators": safe_records,
        "indicators": safe_indicators,
        "volume_summary": vol_sum or "",
        "structure_summary": struct_sum or "",
    }
    if debug:
        def _debug_val(v):
            if v is None or (isinstance(v, float) and math.isfinite(v)):
                return v
            if isinstance(v, float):
                return None
            try:
                f = float(v)
                return f if math.isfinite(f) else None
            except (TypeError, ValueError):
                return v
        close_list = df["Close"].head(3).tolist() if "Close" in df.columns and not df.empty else []
        data["_debug"] = {
            "request_rows": len(body.ohlcv),
            "first_record_keys": list(body.ohlcv[0].keys()) if body.ohlcv else [],
            "df_rows": len(df),
            "df_columns": list(df.columns),
            "close_sample": [_debug_val(x) for x in close_list],
            "last_indicators_keys": list(last_indicators.keys()),
            "last_indicators_sample": {k: _debug_val(v) for k, v in list(last_indicators.items())[:5]},
        }
    # Pass dict so JSONResponse serializes once; pre-dumping would double-encode and break the web app indicators.
    data = _ensure_no_bad_floats(data)
    return JSONResponse(content=data)
