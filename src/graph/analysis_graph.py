"""Analysis graph: fetch OHLCV -> enrich -> fetch sentiment -> merge and signal."""

import math
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd

from langgraph.graph import END, START, StateGraph

from src.analysis.indicators import compute_indicators
from src.analysis.rule_engine import rule_signal_from_rules
from src.analysis.trend import pattern_flags
from src.analysis.volume_structure import structure_summary, volume_summary
from src.data.cache import get_cached_or_fetch
from src.data.symbols import resolve_symbol

from src.graph.state import AnalysisState, GraphContext


def _records_to_df(records: list[dict]) -> pd.DataFrame:
    """Build DataFrame from OHLCV records (same logic as enrich route)."""
    if not records:
        return pd.DataFrame()
    rows = []
    for r in records:
        if not isinstance(r, dict):
            continue
        date_val = r.get("date") or r.get("Date")
        close_val = r.get("Close") or r.get("close")
        if date_val is None or close_val is None:
            continue
        try:
            close_f = float(close_val)
        except (TypeError, ValueError):
            continue
        open_f = _to_float(r.get("Open") or r.get("open")) or close_f
        high_f = _to_float(r.get("High") or r.get("high")) or close_f
        low_f = _to_float(r.get("Low") or r.get("low")) or close_f
        vol = r.get("Volume") or r.get("volume") or 0
        vol_f = float(vol) if isinstance(vol, (int, float)) else 0.0
        rows.append({
            "date": date_val,
            "Open": open_f,
            "High": high_f,
            "Low": low_f,
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
    df = df.sort_index()
    return df


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        f = float(v)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return 0.0


def _rule_signal(indicators: dict, flags: list, params: dict) -> tuple[str, str]:
    """Rule-based signal (same logic as backtest route)."""
    buy_rule = params.get("buy_rule")
    sell_rule = params.get("sell_rule")
    if buy_rule is not None or sell_rule is not None:
        return rule_signal_from_rules(buy_rule, sell_rule, indicators, flags)
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


def build_analysis_graph(ctx: GraphContext):
    """Build the compiled analysis graph (OHLCV -> enrich -> sentiment -> signal)."""

    def fetch_ohlcv(state: AnalysisState) -> AnalysisState:
        symbol = state.get("symbol") or "RELIANCE"
        days = state.get("days") or 90
        config = ctx.config
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        suffix = ".BO" if config.default_exchange == "BSE" else ".NS"
        yahoo_symbol, company_name = resolve_symbol(symbol, config.symbols_path, suffix)
        provider = ctx.data_provider

        def fetcher(sym: str, s: date, e: date):
            return provider.get_daily_ohlcv(sym, s, e)

        df = get_cached_or_fetch(
            ctx.cache_dir, yahoo_symbol, start_date, end_date, fetcher, use_cache=True
        )
        if df.empty:
            return {"symbol": yahoo_symbol, "company_name": company_name, "ohlcv": [], "error": "No OHLCV data"}
        df = df.sort_index()
        records = []
        for idx, row in df.iterrows():
            ts = idx.isoformat()[:10] if hasattr(idx, "isoformat") else str(idx)[:10]
            records.append({
                "date": ts,
                "Open": _safe_float(row.get("Open")),
                "High": _safe_float(row.get("High")),
                "Low": _safe_float(row.get("Low")),
                "Close": _safe_float(row.get("Close")),
                "Volume": int(_safe_float(row.get("Volume"))),
            })
        return {
            "symbol": yahoo_symbol,
            "company_name": company_name,
            "ohlcv": records,
        }

    def enrich(state: AnalysisState) -> AnalysisState:
        ohlcv = state.get("ohlcv") or []
        symbol = state.get("symbol") or ""
        if not ohlcv:
            return {"enrich_result": None, "error": "No OHLCV to enrich"}
        config = ctx.config
        ind_config = config.analysis.indicators if config else None
        df = _records_to_df(ohlcv)
        if df.empty or len(df) < 10:
            return {"enrich_result": None, "error": "Insufficient OHLCV for indicators"}
        df, last_indicators = compute_indicators(df, ind_config)
        vol_sum = volume_summary(df)
        struct_sum = structure_summary(df)
        flags = pattern_flags(df, last_indicators)
        if not df.empty and "Close" in df.columns:
            last_indicators = {**last_indicators, "close": float(df["Close"].iloc[-1])}
        out_indicators = {k: (float(v) if v is not None and math.isfinite(v) else None) for k, v in last_indicators.items()}
        return {
            "enrich_result": {
                "indicators": out_indicators,
                "volume_summary": vol_sum,
                "structure_summary": struct_sum,
                "flags": flags,
            }
        }

    def fetch_sentiment(state: AnalysisState) -> AnalysisState:
        symbol = state.get("symbol") or ""
        company_name = state.get("company_name") or ""
        provider = ctx.sentiment_provider
        result = provider.get_sentiment(symbol=symbol, company_name=company_name, lookback_days=7)
        return {
            "sentiment_result": {
                "label": result.label,
                "score": result.score,
                "snippets": result.snippets,
                "source": result.source,
            }
        }

    def merge_and_signal(state: AnalysisState) -> AnalysisState:
        enrich_result = state.get("enrich_result")
        sentiment_result = state.get("sentiment_result")
        if not enrich_result:
            return {"signal": "HOLD", "reason": "No enrich result"}
        if not sentiment_result:
            return {}
        indicators = enrich_result.get("indicators") or {}
        flags = enrich_result.get("flags") or []
        config = ctx.config
        params = getattr(config.backtest, "default_params", None) or {}
        action, reason = _rule_signal(indicators, flags, params)
        sentiment_note = ""
        if sentiment_result:
            sentiment_note = f" Sentiment: {sentiment_result.get('label', '')} ({sentiment_result.get('score', 0):.2f})."
        return {"signal": action, "reason": (reason or "Rule-based.") + sentiment_note}

    graph = StateGraph(AnalysisState)
    graph.add_node("fetch_ohlcv", fetch_ohlcv)
    graph.add_node("enrich", enrich)
    graph.add_node("fetch_sentiment", fetch_sentiment)
    graph.add_node("merge_and_signal", merge_and_signal)

    graph.add_edge(START, "fetch_ohlcv")
    graph.add_edge("fetch_ohlcv", "enrich")
    graph.add_edge("fetch_ohlcv", "fetch_sentiment")
    graph.add_edge("enrich", "merge_and_signal")
    graph.add_edge("fetch_sentiment", "merge_and_signal")
    graph.add_edge("merge_and_signal", END)

    return graph.compile()
