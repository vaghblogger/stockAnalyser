"""GET /ohlcv - fetch daily OHLCV with cache and symbol resolution."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.config_loader import get_config
from src.data.cache import get_cached_or_fetch
from src.data.symbols import resolve_symbol

router = APIRouter()


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
    if config.max_lookback_days and days and days > config.max_lookback_days:
        days = config.max_lookback_days
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else (end_date - timedelta(days=days or 90))
    suffix = ".BO" if config.default_exchange == "BSE" else ".NS"
    yahoo_symbol, company_name = resolve_symbol(symbol, config.symbols_path, suffix)

    provider = request.app.state.data_provider

    def fetcher(sym: str, s: date, e: date):
        return provider.get_daily_ohlcv(sym, s, e)

    df = get_cached_or_fetch(config.cache_dir, yahoo_symbol, start_date, end_date, fetcher, use_cache=use_cache)
    if df.empty:
        return OHLCVResponse(ohlcv=[], symbol=yahoo_symbol, company_name=company_name, raw_fetch_metadata={"cached": False})
    df = df.sort_index()
    records = []
    for idx, row in df.iterrows():
        ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
        records.append({
            "date": ts[:10],
            "Open": float(row["Open"]),
            "High": float(row["High"]),
            "Low": float(row["Low"]),
            "Close": float(row["Close"]),
            "Volume": int(row["Volume"]) if "Volume" in row else 0,
        })
    return OHLCVResponse(
        ohlcv=records,
        symbol=yahoo_symbol,
        company_name=company_name,
        raw_fetch_metadata={"cached": use_cache, "rows": len(records)},
    )
