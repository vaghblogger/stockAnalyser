"""POST /backtest - run backtest; GET /metrics not needed if backtest returns metrics."""

from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.config_loader import get_config
from src.data.cache import get_cached_or_fetch
from src.data.symbols import resolve_symbol
from src.analysis.indicators import compute_indicators
from src.analysis.volume_structure import volume_summary, structure_summary
from src.analysis.trend import trend_summary, pattern_flags
from src.analysis.risk import risk_summary
from src.backtest.runner import run_backtest
from src.backtest.metrics import compute_metrics

router = APIRouter()


class MetricsRequest(BaseModel):
    rows: list[dict]  # each: date, signal/action, forward_return


@router.post("/metrics")
def post_metrics(body: MetricsRequest) -> dict:
    """Compute backtest metrics from collected rows (for n8n Option B)."""
    return compute_metrics(body.rows, signal_key="signal", return_key="forward_return", action_key="action")


class BacktestRequest(BaseModel):
    symbol: str
    start: str
    end: str
    lookback_days: Optional[int] = None
    hold_days: Optional[int] = None
    step_days: Optional[int] = None


def _run_analysis_for_date(
    symbol: str,
    start: date,
    end: date,
    provider: Any,
    cache_dir: str,
    config: Any,
    sentiment_provider: Any,
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
    vol_sum = volume_summary(df)
    struct_sum = structure_summary(df)
    trend_sum = trend_summary(df, indicators)
    risk_sum = risk_summary(df, indicators)
    flags = pattern_flags(df, indicators)
    # Simple rule-based signal for backtest (no LLM)
    action = "HOLD"
    reason = ""
    rsi = indicators.get("rsi")
    macd_hist = indicators.get("macd_hist")
    if rsi is not None and rsi < 30 and (macd_hist is None or macd_hist > 0):
        action = "BUY"
        reason = "RSI oversold, MACD bullish"
    elif rsi is not None and rsi > 70:
        action = "SELL"
        reason = "RSI overbought"
    elif macd_hist is not None and macd_hist > 0 and "above_sma200" in flags:
        action = "BUY"
        reason = "Above SMA200, MACD bullish"
    elif macd_hist is not None and macd_hist < 0 and "below_sma200" in flags:
        action = "SELL"
        reason = "Below SMA200, MACD bearish"
    return {
        "signal": {"action": action, "confidence": 0.7, "reason": reason or trend_sum},
        "indicators": indicators,
    }


@router.post("/backtest")
def post_backtest(request: Request, body: BacktestRequest) -> dict:
    """Run backtest: rolling windows, rule-based signal, forward returns, metrics."""
    config = get_config()
    start_date = date.fromisoformat(body.start)
    end_date = date.fromisoformat(body.end)
    lookback_days = body.lookback_days or config.backtest.default_lookback_days
    hold_days = body.hold_days or config.backtest.default_hold_days
    step_days = body.step_days or config.backtest.default_step_days
    max_dates = config.max_backtest_dates
    provider = request.app.state.data_provider
    cache_dir = config.cache_dir

    def run_analysis(sym: str, s: date, e: date):
        return _run_analysis_for_date(sym, s, e, provider, cache_dir, config, request.app.state.sentiment_provider)

    def get_forward_return(sym: str, from_date: date, hold: int) -> Optional[float]:
        suffix = ".BO" if config.default_exchange == "BSE" else ".NS"
        yahoo_symbol, _ = resolve_symbol(sym, config.symbols_path, suffix)
        end_fwd = from_date + timedelta(days=hold + 30)
        df = get_cached_or_fetch(
            cache_dir, yahoo_symbol, from_date, end_fwd,
            lambda s, start, end: provider.get_daily_ohlcv(yahoo_symbol, start, end),
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
            # Get date hold_days trading days later (simplified: use calendar days)
            future_dates = df.index[df.index > from_ts]
            if len(future_dates) < hold:
                return None
            end_ts = future_dates[min(hold - 1, len(future_dates) - 1)]
            end_price = float(df.loc[end_ts, "Close"])
            return (end_price - start_price) / start_price
        except Exception:
            return None

    result = run_backtest(
        symbol=body.symbol,
        start=start_date,
        end=end_date,
        lookback_days=lookback_days,
        hold_days=hold_days,
        step_days=step_days,
        run_analysis=run_analysis,
        get_forward_return=get_forward_return,
        max_dates=max_dates,
    )
    return result
