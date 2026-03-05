"""POST /backtest - run backtest; GET /metrics not needed if backtest returns metrics."""

import math
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.config_loader import get_config
from src.data.cache import get_cached_or_fetch
from src.data.symbols import resolve_symbol
from src.db.app_db import get_global_default_strategy, get_strategy, save_backtest_run, list_backtest_runs, get_backtest_run
from src.analysis.indicators import compute_indicators
from src.analysis.volume_structure import volume_summary, structure_summary
from src.analysis.trend import trend_summary, pattern_flags
from src.analysis.risk import risk_summary
from src.analysis.rule_engine import rule_signal_from_rules
from src.backtest.runner import run_backtest
from src.backtest.metrics import compute_metrics

router = APIRouter()


class MetricsRequest(BaseModel):
    rows: list[dict]  # each: date, signal/action, forward_return


# Fallback schema when config.backtest.rule_schema is not set (see docs/BACKTEST_RULES.md).
_DEFAULT_RULE_INDICATORS = [
    "rsi", "macd", "macd_signal", "macd_hist",
    "sma_20", "sma_50", "sma_200", "ema_12", "ema_26",
    "atr", "bb_upper", "bb_mid", "bb_lower", "obv", "close",
]
_DEFAULT_RULE_FLAGS = ["rsi_oversold", "rsi_overbought", "macd_bullish", "macd_bearish", "above_sma200", "below_sma200"]
_DEFAULT_RULE_OPERATORS = ["<", "<=", ">", ">=", "==", "!="]


@router.get("/api/backtest/rule-schema")
def get_backtest_rule_schema() -> dict:
    """Return available indicator keys, flags, and operators from config (or built-in defaults)."""
    config = get_config()
    schema = getattr(config.backtest, "rule_schema", None) if config.backtest else None
    indicators = _DEFAULT_RULE_INDICATORS
    flags = _DEFAULT_RULE_FLAGS
    operators = _DEFAULT_RULE_OPERATORS
    if schema and isinstance(schema, dict):
        ind = schema.get("indicators")
        if isinstance(ind, list) and len(ind) > 0:
            indicators = [str(x) for x in ind]
        fl = schema.get("flags")
        if isinstance(fl, list) and len(fl) > 0:
            flags = [str(x) for x in fl]
        op = schema.get("operators")
        if isinstance(op, list) and len(op) > 0:
            operators = [str(x) for x in op]
    return {
        "indicators": indicators,
        "flags": flags,
        "operators": operators,
        "docs": "See docs/BACKTEST_RULES.md for rule format (and/or/not, indicator vs value, indicator vs indicator, flag).",
    }


@router.post("/metrics")
def post_metrics(body: MetricsRequest) -> dict:
    """Compute backtest metrics from collected rows (for n8n Option B)."""
    return compute_metrics(body.rows, signal_key="signal", return_key="forward_return", action_key="action")


class BacktestRequest(BaseModel):
    symbol: Optional[str] = None
    symbols: Optional[list[str]] = None
    strategy_assignments: Optional[dict[str, str]] = None  # symbol -> strategy_id or "global_default"
    start: str
    end: str
    lookback_days: Optional[int] = None
    hold_days: Optional[int] = None
    step_days: Optional[int] = None
    strategy_id: Optional[str] = None
    params: Optional[dict[str, Any]] = None  # inline override: e.g. buy_rule, sell_rule (merged over strategy params)


def _rule_signal(indicators: dict, flags: list, params: dict) -> tuple[str, str]:
    """Rule-based signal: use custom buy_rule/sell_rule if present, else built-in rules."""
    buy_rule = params.get("buy_rule")
    sell_rule = params.get("sell_rule")
    if buy_rule is not None or sell_rule is not None:
        return rule_signal_from_rules(buy_rule, sell_rule, indicators, flags)

    # Built-in rules (backward compatible)
    rsi_buy = params.get("rsi_buy_below", 30)
    rsi_sell = params.get("rsi_sell_above", 70)
    rsi = indicators.get("rsi")
    macd_hist = indicators.get("macd_hist")
    action, reason = "HOLD", ""
    if rsi is not None and rsi < rsi_buy and (macd_hist is None or macd_hist > 0):
        action, reason = "BUY", "RSI oversold, MACD bullish"
    elif rsi is not None and rsi > rsi_sell:
        action, reason = "SELL", "RSI overbought"
    elif macd_hist is not None and macd_hist > 0 and "above_sma200" in flags:
        action, reason = "BUY", "Above SMA200, MACD bullish"
    elif macd_hist is not None and macd_hist < 0 and "below_sma200" in flags:
        action, reason = "SELL", "Below SMA200, MACD bearish"
    return action, reason


def _run_analysis_for_date(
    symbol: str,
    start: date,
    end: date,
    provider: Any,
    cache_dir: str,
    config: Any,
    sentiment_provider: Any,
    strategy_params: Optional[dict] = None,
) -> dict:
    """Run analysis for one date window: OHLCV -> enrich -> trend/risk -> rule-based signal."""
    suffix = ".BO" if config.default_exchange == "BSE" else ".NS"
    yahoo_symbol, _ = resolve_symbol(symbol, config.symbols_path, suffix)

    def fetcher(sym: str, s: date, e: date):
        return provider.get_daily_ohlcv(sym, s, e)

    df = get_cached_or_fetch(cache_dir, yahoo_symbol, start, end, fetcher, use_cache=True)
    if df.empty or len(df) < 20:
        return {"signal": {"action": "HOLD", "confidence": 0.0, "reason": "Insufficient data"}}
    df, indicators = compute_indicators(df, config.analysis.indicators)
    if not df.empty and "Close" in df.columns:
        indicators = {**indicators, "close": float(df["Close"].iloc[-1])}
    trend_sum = trend_summary(df, indicators)
    flags = pattern_flags(df, indicators)
    params = strategy_params or {}
    action, reason = _rule_signal(indicators, flags, params)
    return {
        "signal": {"action": action, "confidence": 0.7, "reason": reason or trend_sum},
        "indicators": indicators,
    }


def _resolve_strategy_params(cache_dir: str, strategy_id: Optional[str], assignments: Optional[dict], symbol: str) -> tuple[dict, dict]:
    """Return (params, strategy_info) for a symbol from strategy_assignments or strategy_id or global default."""
    sid = None
    if assignments and symbol in assignments:
        sid = assignments.get(symbol)
        if sid == "global_default":
            sid = None
    if sid is None and strategy_id:
        sid = strategy_id
    record = get_strategy(cache_dir, sid) if sid else get_global_default_strategy(cache_dir)
    params = record.get("params", {}) if record else {}
    info = {
        "name": (record.get("name") or "Rule-based") if record else "Rule-based",
        "description": (record.get("description") or "") if record else "",
    }
    return params, info


def run_backtest_core(
    *,
    config: Any,
    cache_dir: str,
    data_provider: Any,
    sentiment_provider: Any,
    body: BacktestRequest,
) -> dict:
    """Core backtest logic (used by POST /api/backtest and LangGraph backtest node)."""
    start_date = date.fromisoformat(body.start)
    end_date = date.fromisoformat(body.end)
    lookback_days = body.lookback_days or config.backtest.default_lookback_days
    hold_days = body.hold_days or config.backtest.default_hold_days
    step_days = body.step_days or config.backtest.default_step_days
    max_dates = config.max_backtest_dates
    provider = data_provider
    symbols = body.symbols if body.symbols else ([body.symbol] if body.symbol else ["RELIANCE"])
    assignments = body.strategy_assignments or {}

    all_rows = []
    strategy_info = {"name": "Rule-based", "description": ""}
    by_symbol: dict[str, dict] = {}

    for sym in symbols:
        strategy_params, info = _resolve_strategy_params(cache_dir, body.strategy_id, assignments, sym)
        if body.params:
            strategy_params = {**strategy_params, **body.params}
        strategy_info = info

        def run_analysis(sym: str, s: date, e: date, params: dict = strategy_params):
            return _run_analysis_for_date(sym, s, e, provider, cache_dir, config, sentiment_provider, strategy_params=params)

        def get_forward_return(s: str, from_date: date, hold: int) -> Optional[float]:
            suffix = ".BO" if config.default_exchange == "BSE" else ".NS"
            yahoo_symbol, _ = resolve_symbol(s, config.symbols_path, suffix)
            end_fwd = from_date + timedelta(days=hold + 30)
            df = get_cached_or_fetch(
                cache_dir, yahoo_symbol, from_date, end_fwd,
                lambda _s, start, end: provider.get_daily_ohlcv(yahoo_symbol, start, end),
                use_cache=True,
            )
            if df.empty or len(df) < 2:
                return None
            df = df.sort_index()
            try:
                from_ts = pd.Timestamp(from_date)
                after = df.index[df.index >= from_ts]
                if len(after) == 0:
                    return None
                start_price = float(df.loc[after[0], "Close"])
                future_dates = df.index[df.index > from_ts]
                if len(future_dates) < hold:
                    return None
                end_ts = future_dates[min(hold - 1, len(future_dates) - 1)]
                end_price = float(df.loc[end_ts, "Close"])
                return (end_price - start_price) / start_price
            except Exception:
                return None

        result = run_backtest(
            symbol=sym,
            start=start_date,
            end=end_date,
            lookback_days=lookback_days,
            hold_days=hold_days,
            step_days=step_days,
            run_analysis=lambda s, start, end: run_analysis(s, start, end),
            get_forward_return=get_forward_return,
            max_dates=max_dates,
        )
        rows = result.get("rows") or []
        for r in rows:
            r["symbol"] = sym
        all_rows.extend(rows)
        by_symbol[sym] = {"metrics": result.get("metrics"), "rows_count": len(rows)}

    all_rows.sort(key=lambda r: (r["date"], r.get("symbol", "")))
    metrics = compute_metrics(all_rows, signal_key="signal", return_key="forward_return", action_key="action")
    result = {"metrics": metrics, "rows": all_rows, "strategy": strategy_info, "by_symbol": by_symbol}

    def _sanitize_json(obj: Any) -> Any:
        """Replace nan/inf and convert numpy-like scalars so JSON serialization does not fail."""
        if isinstance(obj, dict):
            return {k: _sanitize_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize_json(v) for v in obj]
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, (int, bool)) or obj is None:
            return obj
        try:
            if hasattr(obj, "__float__") and not isinstance(obj, bool):
                f = float(obj)
                if math.isnan(f) or math.isinf(f):
                    return None
                return f
        except (TypeError, ValueError):
            pass
        return obj

    run_params = {
        "lookback_days": lookback_days,
        "hold_days": hold_days,
        "step_days": step_days,
    }
    if body.params:
        run_params.update(body.params)
    try:
        saved = save_backtest_run(
            cache_dir,
            strategy_id=body.strategy_id,
            strategy_name=strategy_info.get("name", "Rule-based"),
            strategy_description=strategy_info.get("description", ""),
            symbols=symbols,
            start_date=body.start,
            end_date=body.end,
            params=run_params,
            metrics=_sanitize_json(metrics),
            rows=_sanitize_json(all_rows),
        )
        result["run_id"] = saved["id"]
    except Exception:
        result["run_id"] = None

    return _sanitize_json(result)


@router.post("/api/backtest")
def post_backtest(request: Request, body: BacktestRequest) -> dict:
    """Run backtest: single or multi-symbol; optional strategy per symbol."""
    config = get_config()
    return run_backtest_core(
        config=config,
        cache_dir=config.cache_dir,
        data_provider=request.app.state.data_provider,
        sentiment_provider=request.app.state.sentiment_provider,
        body=body,
    )


@router.get("/api/backtest/runs")
def get_backtest_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    symbol: Optional[str] = Query(None),
    strategy_id: Optional[str] = Query(None),
) -> dict:
    """List saved backtest runs (newest first). Optional filters: symbol, strategy_id."""
    config = get_config()
    runs = list_backtest_runs(config.cache_dir, limit=limit, offset=offset, symbol=symbol, strategy_id=strategy_id)
    return {"runs": runs, "count": len(runs)}


@router.get("/api/backtest/runs/{run_id}")
def get_backtest_run_by_id(run_id: str) -> dict:
    """Retrieve a single backtest run by id. Response shape matches POST /backtest for UI compatibility."""
    config = get_config()
    run = get_backtest_run(config.cache_dir, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    rows = run.get("rows") or []
    by_symbol: dict[str, dict] = {}
    for r in rows:
        sym = r.get("symbol", "")
        if sym and sym not in by_symbol:
            by_symbol[sym] = {"metrics": None, "rows_count": sum(1 for x in rows if x.get("symbol") == sym)}
    out = {
        "run_id": run["id"],
        "metrics": run.get("metrics", {}),
        "rows": rows,
        "strategy": run.get("strategy", {"name": run.get("strategy_name", "Rule-based"), "description": run.get("strategy_description", "")}),
        "by_symbol": by_symbol,
        "created_at": run.get("created_at"),
        "start_date": run.get("start_date"),
        "end_date": run.get("end_date"),
        "symbols": run.get("symbols", []),
    }
    return out
