"""GET /dashboard - list all stocks in cache with indicators and BUY/SELL/HOLD signal."""

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.analysis.indicators import compute_indicators
from src.data.cache import (
    get_cached_or_fetch,
    get_ohlcv_days_count,
    list_symbols_in_cache,
    read_ohlcv_cache_last_n,
    read_ohlcv_cache_partial,
)
from src.data.symbols import load_symbol_map
from src.db.app_db import list_universe_symbols

router = APIRouter()


def _derive_signal(indicators: dict[str, Any]) -> dict[str, str]:
    """Same logic as frontend: RSI and MACD hist -> BUY/SELL/HOLD."""
    rsi = indicators.get("rsi")
    macd_hist = indicators.get("macd_hist")
    if rsi is not None and rsi < 30 and (macd_hist is None or macd_hist > 0):
        return {"action": "BUY", "reason": "RSI oversold, MACD bullish"}
    if rsi is not None and rsi > 70:
        return {"action": "SELL", "reason": "RSI overbought"}
    if macd_hist is not None and macd_hist > 0:
        return {"action": "BUY", "reason": "MACD bullish"}
    if macd_hist is not None and macd_hist < 0:
        return {"action": "SELL", "reason": "MACD bearish"}
    return {"action": "HOLD", "reason": "No strong signal"}


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f if abs(f) < 1e100 else None
    except (TypeError, ValueError):
        return None


@router.get("/dashboard")
def get_dashboard(
    request: Request,
    lookback_days: int = 90,
):
    """
    Return all symbols in the OHLCV cache with latest indicators and signal.
    Always reads from the DB/cache (no response caching) so the dashboard stays in sync with
    stored data. Each stock: symbol, company_name, indicators, signal, data_duration_days
    (number of days of data in the cache for that symbol).
    """
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    cache_dir = config.cache_dir
    symbols_path = getattr(config, "symbols_path", "config/symbols.csv")
    ind_config = getattr(config, "analysis", None) and getattr(config.analysis, "indicators", None)
    data_provider = getattr(request.app.state, "data_provider", None)
    universe = list_universe_symbols(cache_dir)
    if universe:
        symbols = [s.get("yahoo_symbol") or s.get("symbol") for s in universe if s.get("yahoo_symbol") or s.get("symbol")]
    else:
        symbols = list_symbols_in_cache(cache_dir)
    universe_by_symbol = {s.get("yahoo_symbol") or s.get("symbol"): s for s in universe} if universe else {}
    if not symbols:
        return JSONResponse(
            content={"stocks": [], "count": 0},
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    # Resolve company names from symbols.csv (base symbol -> company_name)
    symbol_map = load_symbol_map(symbols_path)
    end_date = date.today()
    start_date = end_date - timedelta(days=max(1, lookback_days))

    def fetcher(sym: str, s: date, e: date):
        return data_provider.get_daily_ohlcv(sym, s, e) if data_provider else None

    stocks = []
    for symbol in symbols:
        try:
            df = None
            # 1) Prefer cache: last N rows (always show something if cache has data)
            df = read_ohlcv_cache_last_n(cache_dir, symbol, n=250)
            if df is None or df.empty or len(df) < 20:
                # 2) Try full date range from cache or fetch from provider
                if data_provider:
                    df = get_cached_or_fetch(cache_dir, symbol, start_date, end_date, fetcher, use_cache=True)
            if df is None or df.empty or len(df) < 20:
                df = read_ohlcv_cache_partial(cache_dir, symbol, start_date, end_date, min_rows=20)
            if df is None or df.empty or len(df) < 20:
                base = symbol.split(".")[0]
                u = universe_by_symbol.get(symbol, {})
                cn = u.get("company_name") or (symbol_map.get(base) or ("", ""))[1]
                duration_days = get_ohlcv_days_count(cache_dir, symbol)
                stocks.append({
                    "symbol": str(symbol),
                    "company_name": cn if cn else None,
                    "indicators": {},
                    "signal": {"action": "HOLD", "reason": "Insufficient data"},
                    "data_duration_days": duration_days,
                })
                continue
            df = df.sort_index()
            duration_days = max(len(df), get_ohlcv_days_count(cache_dir, symbol))
            df, last_ind = compute_indicators(df, ind_config)
            indicators = {}
            for k in ("close", "sma_20", "sma_50", "sma_200", "rsi", "macd", "macd_signal", "macd_hist", "atr", "bb_upper", "bb_lower", "obv"):
                if k == "close":
                    if "Close" in df.columns and not df.empty:
                        indicators["close"] = _safe_float(df["Close"].iloc[-1])
                else:
                    indicators[k] = _safe_float(last_ind.get(k))
            if indicators.get("close") is None and "Close" in df.columns and not df.empty:
                indicators["close"] = _safe_float(df["Close"].iloc[-1])
            signal = _derive_signal(indicators)
            base = symbol.split(".")[0]
            u = universe_by_symbol.get(symbol, {})
            company_name = u.get("company_name") or (symbol_map.get(base) or ("", ""))[1] or None
            # Ensure all indicator values are native Python for JSON
            indicators_clean = {}
            for k, v in indicators.items():
                if v is not None:
                    try:
                        indicators_clean[k] = float(v)
                    except (TypeError, ValueError):
                        pass
            stocks.append({
                "symbol": str(symbol),
                "company_name": company_name,
                "indicators": indicators_clean,
                "signal": {"action": signal["action"], "reason": signal["reason"]},
                "data_duration_days": duration_days,
            })
        except Exception:
            base = symbol.split(".")[0]
            u = universe_by_symbol.get(symbol, {})
            cn = u.get("company_name") or (symbol_map.get(base) or ("", ""))[1]
            duration_days = get_ohlcv_days_count(cache_dir, symbol)
            stocks.append({
                "symbol": str(symbol),
                "company_name": cn if cn else None,
                "indicators": {},
                "signal": {"action": "HOLD", "reason": "Error computing indicators"},
                "data_duration_days": duration_days,
            })
    payload = {"stocks": stocks, "count": len(stocks)}
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )
