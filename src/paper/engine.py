"""Paper trading engine: run one day or up to date, apply signals, snapshot equity."""

from datetime import date, timedelta
from typing import Callable, Optional

from src.analysis.indicators import compute_indicators
from src.analysis.trend import pattern_flags
from src.config_loader import get_config
from src.data.cache import read_ohlcv_cache_last_n, write_ohlcv_cache
from src.data.symbols import resolve_symbol
from src.db.app_db import (
    append_paper_snapshot,
    get_paper_portfolio,
    get_paper_snapshots,
    get_strategy,
    get_global_default_strategy,
    list_paper_positions,
)


def _rule_signal(indicators: dict, flags: list, params: dict) -> str:
    rsi_buy = params.get("rsi_buy_below", 30)
    rsi_sell = params.get("rsi_sell_above", 70)
    rsi = indicators.get("rsi")
    macd_hist = indicators.get("macd_hist")
    if rsi is not None and rsi < rsi_buy and (macd_hist is None or macd_hist > 0):
        return "BUY"
    if rsi is not None and rsi > rsi_sell:
        return "SELL"
    if macd_hist is not None and macd_hist > 0 and "above_sma200" in flags:
        return "BUY"
    if macd_hist is not None and macd_hist < 0 and "below_sma200" in flags:
        return "SELL"
    return "HOLD"


def run_paper_day(
    cache_dir: str,
    portfolio_id: str,
    get_ohlcv: Callable[[str, date, date], object],
    up_to_date: Optional[str] = None,
    lookback_days: int = 90,
    trade_amount_pct: float = 0.1,
) -> dict:
    """
    Run paper trading for one day (or from last snapshot to up_to_date).
    Returns { snapshot, equity, cash, positions, trades }.
    """
    config = get_config()
    portfolio = get_paper_portfolio(cache_dir, portfolio_id)
    if not portfolio:
        return {"ok": False, "error": "Portfolio not found"}
    positions_config = list_paper_positions(cache_dir, portfolio_id)
    if not positions_config:
        return {"ok": False, "error": "No positions in portfolio"}

    snapshots = get_paper_snapshots(cache_dir, portfolio_id)
    if snapshots:
        last = snapshots[-1]
        cash = float(last["cash"])
        positions = last.get("positions") or {}
        if isinstance(positions, list):
            positions = {}
        last_date = date.fromisoformat(last["date"])
    else:
        cash = float(portfolio["initial_capital"])
        positions = {}
        last_date = date.fromisoformat(portfolio["created_at"][:10]) if portfolio.get("created_at") else date.today() - timedelta(days=365)

    suffix = ".BO" if config.default_exchange == "BSE" else ".NS"
    eval_date = last_date + timedelta(days=1)
    if up_to_date:
        end_date = date.fromisoformat(up_to_date)
        if eval_date > end_date:
            return {"ok": True, "message": "Already up to date", "snapshots_added": 0}
    else:
        end_date = min(eval_date, date.today())

    trades = []
    start_date = eval_date - timedelta(days=lookback_days)
    ind_config = getattr(config, "analysis", None) and getattr(config.analysis, "indicators", None)

    for pos in positions_config:
        symbol = pos.get("symbol") or ""
        yahoo_symbol, _ = resolve_symbol(symbol, config.symbols_path, suffix)
        strategy_ids = pos.get("strategy_ids") or []
        params = {}
        if strategy_ids:
            s = get_strategy(cache_dir, strategy_ids[0])
            if s:
                params = s.get("params") or {}
        if not params:
            g = get_global_default_strategy(cache_dir)
            if g:
                params = g.get("params") or {}

        df = read_ohlcv_cache_last_n(cache_dir, yahoo_symbol, n=lookback_days + 10)
        if df is None or df.empty:
            try:
                df = get_ohlcv(yahoo_symbol, start_date, eval_date + timedelta(days=5))
                if df is not None and not getattr(df, "empty", True):
                    write_ohlcv_cache(cache_dir, yahoo_symbol, df)
            except Exception:
                pass
        if df is None or getattr(df, "empty", True) or len(df) < 20:
            continue
        df = df.sort_index()
        df = df[df.index <= str(eval_date)]
        if df.empty or len(df) < 20:
            continue
        df, last_ind = compute_indicators(df, ind_config)
        flags = pattern_flags(df, last_ind)
        action = _rule_signal(last_ind, flags, params)
        try:
            close_price = float(df["Close"].iloc[-1])
        except Exception:
            continue
        qty = positions.get(yahoo_symbol, 0) or positions.get(symbol, 0)
        if isinstance(qty, dict):
            qty = 0
        qty = float(qty)

        trade_cash = float(portfolio["initial_capital"]) * trade_amount_pct if action == "BUY" else 0
        if trade_cash <= 0:
            trade_cash = cash * 0.1

        if action == "BUY" and cash >= trade_cash and trade_cash > 0:
            add_qty = trade_cash / close_price
            positions[yahoo_symbol] = qty + add_qty
            cash -= trade_cash
            trades.append({"date": str(eval_date), "symbol": yahoo_symbol, "action": "BUY", "quantity": add_qty, "price": close_price})
        elif action == "SELL" and qty > 0:
            cash += qty * close_price
            if yahoo_symbol in positions:
                del positions[yahoo_symbol]
            if symbol in positions:
                del positions[symbol]
            trades.append({"date": str(eval_date), "symbol": yahoo_symbol, "action": "SELL", "quantity": qty, "price": close_price})

    equity = cash
    for sym, q in list(positions.items()):
        qf = float(q) if not isinstance(q, dict) else 0
        if qf > 0:
            try:
                d = read_ohlcv_cache_last_n(cache_dir, sym, n=5)
                if d is not None and not d.empty:
                    equity += qf * float(d["Close"].iloc[-1])
            except Exception:
                pass
    append_paper_snapshot(cache_dir, portfolio_id, str(eval_date), equity, cash, positions)
    return {
        "ok": True,
        "snapshot": {"date": str(eval_date), "equity": equity, "cash": cash, "positions": positions},
        "equity": equity,
        "cash": cash,
        "positions": positions,
        "trades": trades,
        "snapshots_added": 1,
    }
