"""GET /ohlcv - fetch daily OHLCV with cache and symbol resolution."""

import math
from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.config_loader import get_config
from src.data.cache import get_cached_or_fetch
from src.data.symbols import resolve_symbol

router = APIRouter()


def _safe_float(v: Any) -> float:
    """Return a JSON-safe float (no nan/inf). Use 0.0 for invalid."""
    if v is None:
        return 0.0
    try:
        f = float(v)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return 0.0


def _safe_int(v: Any) -> int:
    """Return a JSON-safe int. Use 0 for invalid/nan."""
    if v is None:
        return 0
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return 0
        return int(f)
    except (TypeError, ValueError):
        return 0


class OHLCVResponse(BaseModel):
    ohlcv: list[dict]
    symbol: str
    company_name: Optional[str] = None
    raw_fetch_metadata: dict


@router.get("/ohlcv", response_model=OHLCVResponse)
def get_ohlcv(
    request: Request,
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    days: Optional[int] = 90,
    use_cache: bool = True,
):
    """Fetch daily OHLCV. Symbol can be RELIANCE or RELIANCE.NS. start/end as YYYY-MM-DD; or use days from today."""
    config = get_config()
    # Coerce days to int (query params can arrive as str)
    req_days = int(days) if days is not None else 90
    if config.max_lookback_days and req_days > config.max_lookback_days:
        req_days = config.max_lookback_days
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else (end_date - timedelta(days=req_days))
    suffix = ".BO" if config.default_exchange == "BSE" else ".NS"
    yahoo_symbol, company_name = resolve_symbol(symbol, config.symbols_path, suffix)

    provider = request.app.state.data_provider

    def fetcher(sym: str, s: date, e: date):
        return provider.get_daily_ohlcv(sym, s, e)

    df = get_cached_or_fetch(config.cache_dir, yahoo_symbol, start_date, end_date, fetcher, use_cache=use_cache)
    if df.empty:
        return OHLCVResponse(
            ohlcv=[],
            symbol=yahoo_symbol,
            company_name=company_name,
            raw_fetch_metadata={"cached": False, "data_start_date": None, "data_end_date": None},
        )
    df = df.sort_index()
    records = []
    for idx, row in df.iterrows():
        ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
        records.append({
            "date": ts[:10],
            "Open": _safe_float(row.get("Open")),
            "High": _safe_float(row.get("High")),
            "Low": _safe_float(row.get("Low")),
            "Close": _safe_float(row.get("Close")),
            "Volume": _safe_int(row.get("Volume")),
        })
    metadata = {
        "cached": use_cache,
        "rows": len(records),
        "data_start_date": records[0]["date"],
        "data_end_date": records[-1]["date"],
    }
    return OHLCVResponse(
        ohlcv=records,
        symbol=yahoo_symbol,
        company_name=company_name,
        raw_fetch_metadata=metadata,
    )
