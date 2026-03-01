"""Data and universe: seed OHLCV, list/add/remove universe symbols."""

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.data.cache import get_cached_or_fetch, write_ohlcv_cache
from src.data.universe import pre_seed_ohlcv
from src.db.app_db import (
    add_universe_symbol,
    get_universe_symbol,
    get_universe_symbol_by_any,
    list_universe_symbols,
    remove_universe_symbol,
    update_universe_symbol,
)

router = APIRouter()


class SeedRequest(BaseModel):
    lookback_days: Optional[int] = 730


class AddSymbolRequest(BaseModel):
    symbol: str
    yahoo_symbol: Optional[str] = None
    company_name: Optional[str] = None
    lookback_days: Optional[int] = 3650  # default 10 years for new stocks


class UpdateSymbolRequest(BaseModel):
    symbol: Optional[str] = None  # new symbol (rename); if changed, data is refetched for new symbol
    yahoo_symbol: Optional[str] = None
    company_name: Optional[str] = None
    lookback_days: Optional[int] = 3650  # when refetching after symbol change


class UpdateSymbolBodyRequest(UpdateSymbolRequest):
    """Update symbol with current_symbol in body (avoids path-param 404 issues)."""
    current_symbol: str  # symbol being edited (path is always POST /universe/update)


@router.post("/universe/update")
def post_universe_update(request: Request, body: UpdateSymbolBodyRequest):
    """Update a symbol by current_symbol in body. Defined before /universe/{symbol} so path is matched correctly."""
    return put_universe_symbol(request, body.current_symbol.strip().upper(), body)


@router.get("/universe/item/{symbol}")
@router.get("/universe/{symbol}")
def get_universe_symbol_route(request: Request, symbol: str):
    """Get one symbol's details from the universe. Supports both /universe/{symbol} and /universe/item/{symbol}."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    s = get_universe_symbol_by_any(config.cache_dir, symbol)
    if not s:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Symbol not found")
    return s


@router.post("/seed")
def post_seed(request: Request, body: Optional[SeedRequest] = None):
    """
    Pre-seed OHLCV cache for all symbols in universe.
    Fetches last lookback_days (default 730) and writes to cache.
    """
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    provider = getattr(request.app.state, "data_provider", None)
    if not provider:
        return {"ok": False, "error": "Data provider not available", "success": 0, "failed": 0}
    lookback = (body and body.lookback_days) or 730
    cache_dir = config.cache_dir

    def fetcher(symbol: str, start, end):
        return provider.get_daily_ohlcv(symbol, start, end)

    success, failed = pre_seed_ohlcv(
        cache_dir,
        fetcher,
        lookback_days=lookback,
        write_cache=lambda _cd, sym, df: write_ohlcv_cache(_cd, sym, df),
    )
    return {"ok": True, "success": success, "failed": failed}


@router.get("/universe")
def get_universe(request: Request):
    """List all symbols in the universe (from app DB)."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    symbols = list_universe_symbols(config.cache_dir)
    return {"symbols": symbols, "count": len(symbols)}


def _normalize_yahoo_symbol(symbol: str, yahoo_symbol: Optional[str]) -> str:
    """Ensure we have an exchange suffix (.NS or .BO) for Yahoo Finance."""
    raw = (yahoo_symbol or symbol or "").strip()
    if not raw:
        return symbol.strip().upper() + ".NS"
    if raw.endswith(".NS") or raw.endswith(".BO"):
        return raw
    return raw + ".NS"


@router.post("/universe")
def post_universe_symbol(request: Request, body: AddSymbolRequest):
    """
    Add a symbol to the universe and fetch OHLCV using the same logic as the Analysis page
    (get_cached_or_fetch with provider). Default lookback 10 years so the stock is visible everywhere.
    """
    from datetime import date, timedelta

    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    provider = getattr(request.app.state, "data_provider", None)
    symbol_upper = body.symbol.strip().upper()
    yahoo = _normalize_yahoo_symbol(body.symbol, body.yahoo_symbol)

    add_universe_symbol(
        config.cache_dir,
        symbol_upper,
        yahoo_symbol=yahoo,
        company_name=body.company_name,
    )

    lookback = body.lookback_days if body.lookback_days is not None else 3650
    lookback = max(1, min(lookback, 3650 * 2))
    success = False
    error_message: Optional[str] = None
    used_yahoo = yahoo
    actual_lookback: Optional[int] = None

    if provider and lookback > 0:
        end_date = date.today()
        # Same fetcher pattern as GET /ohlcv and Analysis page
        def fetcher(sym: str, start: date, end: date):
            return provider.get_daily_ohlcv(sym, start, end)

        def fetch_for_days(sym: str, days: int):
            start_date = end_date - timedelta(days=days)
            return get_cached_or_fetch(
                config.cache_dir,
                sym,
                start_date,
                end_date,
                fetcher,
                use_cache=True,
            )

        try:
            df = fetch_for_days(yahoo, lookback)
            if df is not None and not getattr(df, "empty", True) and len(df) >= 1:
                success = True
                actual_lookback = lookback
            else:
                df_short = fetch_for_days(yahoo, 365)
                if df_short is not None and not getattr(df_short, "empty", True) and len(df_short) >= 1:
                    success = True
                    actual_lookback = 365
                    error_message = "Only 1 year of data (10-year returned no data). Use Data seed for more."
                elif yahoo.endswith(".NS"):
                    alt = symbol_upper + ".BO"
                    try:
                        df_bo = fetch_for_days(alt, lookback)
                        if df_bo is not None and not getattr(df_bo, "empty", True) and len(df_bo) >= 1:
                            add_universe_symbol(config.cache_dir, symbol_upper, yahoo_symbol=alt, company_name=body.company_name)
                            success = True
                            used_yahoo = alt
                            actual_lookback = lookback
                        else:
                            df_bo = fetch_for_days(alt, 365)
                            if df_bo is not None and not getattr(df_bo, "empty", True) and len(df_bo) >= 1:
                                add_universe_symbol(config.cache_dir, symbol_upper, yahoo_symbol=alt, company_name=body.company_name)
                                success = True
                                used_yahoo = alt
                                actual_lookback = 365
                                error_message = "BSE (.BO): 1 year fetched. Use Data seed for more."
                    except Exception:
                        pass
                if not success:
                    error_message = "No data returned for " + yahoo + ". Check symbol (e.g. .BO for BSE)."
        except Exception as e:
            error_message = str(e) or type(e).__name__
            try:
                df_short = fetch_for_days(yahoo, 365)
                if df_short is not None and not getattr(df_short, "empty", True) and len(df_short) >= 1:
                    success = True
                    actual_lookback = 365
                    error_message = "Fetched 1 year only (" + (error_message or "long range failed") + "). Use Data seed for more."
            except Exception:
                pass

    return {
        "ok": True,
        "symbol": symbol_upper,
        "yahoo_symbol": used_yahoo,
        "fetched": success,
        "lookback_days": actual_lookback or lookback,
        "error_message": error_message,
    }


@router.put("/universe/{symbol}")
@router.post("/universe/{symbol}/update")
def put_universe_symbol(request: Request, symbol: str, body: UpdateSymbolRequest):
    """
    Update a symbol's name (company_name), yahoo_symbol, or rename (symbol).
    If symbol or yahoo_symbol is changed, refetches OHLCV data for the new symbol.
    PUT /universe/{symbol} or POST /universe/{symbol}/update (for clients that block PUT).
    """
    from datetime import date, timedelta

    try:
        config = getattr(request.app.state, "config", None)
        if config is None:
            from src.config_loader import get_config
            config = get_config()
        provider = getattr(request.app.state, "data_provider", None)
        current_symbol = (symbol or "").strip().upper()
        if not current_symbol:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Symbol is required")
        existing = get_universe_symbol_by_any(config.cache_dir, current_symbol)
        new_symbol = (body.symbol or "").strip().upper() if body.symbol else current_symbol
        new_symbol = new_symbol or current_symbol
        if body.yahoo_symbol is not None and str(body.yahoo_symbol).strip():
            new_yahoo = _normalize_yahoo_symbol(body.yahoo_symbol, body.yahoo_symbol)
        elif existing:
            new_yahoo = (existing.get("yahoo_symbol") or "") or _normalize_yahoo_symbol(new_symbol, None)
        else:
            new_yahoo = _normalize_yahoo_symbol(new_symbol, body.yahoo_symbol)
        new_company = body.company_name if body.company_name is not None else (existing.get("company_name") if existing else "") or ""
        lookback = body.lookback_days if body.lookback_days is not None else 3650
        lookback = max(1, min(lookback, 3650 * 2))
        fetched = False
        error_message = None

        existing_key = (existing.get("symbol") or current_symbol).strip().upper() if existing else None
        if not existing:
            add_universe_symbol(config.cache_dir, new_symbol, yahoo_symbol=new_yahoo, company_name=new_company or "")
            refetch_symbol = None
        elif new_symbol != existing_key:
            remove_universe_symbol(config.cache_dir, existing_key)
            add_universe_symbol(config.cache_dir, new_symbol, yahoo_symbol=new_yahoo, company_name=new_company or "")
            refetch_symbol = new_yahoo
        else:
            update_universe_symbol(config.cache_dir, existing_key, company_name=new_company, yahoo_symbol=new_yahoo)
            refetch_symbol = new_yahoo if (body.yahoo_symbol is not None and new_yahoo != (existing.get("yahoo_symbol") or "")) else None

        if provider and refetch_symbol:
            end_date = date.today()
            def fetcher(sym: str, start: date, end: date):
                return provider.get_daily_ohlcv(sym, start, end)
            def fetch_for_days(sym: str, days: int):
                start_date = end_date - timedelta(days=days)
                return get_cached_or_fetch(config.cache_dir, sym, start_date, end_date, fetcher, use_cache=True)
            try:
                df = fetch_for_days(refetch_symbol, lookback)
                if df is not None and not getattr(df, "empty", True) and len(df) >= 1:
                    fetched = True
                else:
                    df_short = fetch_for_days(refetch_symbol, 365)
                    if df_short is not None and not getattr(df_short, "empty", True) and len(df_short) >= 1:
                        fetched = True
                        error_message = "Refetched 1 year only. Use Data seed for more."
            except Exception as e:
                error_message = str(e) or type(e).__name__

        out = get_universe_symbol(config.cache_dir, new_symbol) or {"symbol": new_symbol, "yahoo_symbol": new_yahoo, "company_name": new_company or ""}
        out["fetched"] = fetched
        out["error_message"] = error_message
        return out
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            raise
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or type(e).__name__)


@router.delete("/universe/{symbol}")
def delete_universe_symbol(request: Request, symbol: str):
    """Remove a symbol from the universe (does not delete from OHLCV cache)."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    removed = remove_universe_symbol(config.cache_dir, symbol)
    return {"ok": True, "removed": removed}
