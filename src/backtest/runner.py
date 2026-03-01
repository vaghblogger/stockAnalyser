"""Backtest runner: rolling dates, run analysis, forward returns, aggregate metrics."""

from datetime import date, timedelta
from typing import Any, Callable, Optional

from src.backtest.metrics import compute_metrics


def generate_eval_dates(start: date, end: date, step_days: int = 5) -> list[date]:
    """Generate evaluation dates from start to end, every step_days."""
    out = []
    d = start
    while d <= end:
        out.append(d)
        d += timedelta(days=step_days)
    return out


def run_backtest(
    symbol: str,
    start: date,
    end: date,
    lookback_days: int,
    hold_days: int,
    step_days: int,
    run_analysis: Callable[[str, date, date], dict],
    get_forward_return: Callable[[str, date, int], Optional[float]],
    max_dates: Optional[int] = None,
) -> dict[str, Any]:
    """
    run_analysis(symbol, end_date, start_date) -> { "signal": { "action": "BUY"|"SELL"|"HOLD", ... }, ... }
    get_forward_return(symbol, from_date, hold_days) -> float or None
    """
    eval_dates = generate_eval_dates(start, end, step_days)
    if max_dates:
        eval_dates = eval_dates[:max_dates]
    rows = []
    for eval_date in eval_dates:
        window_start = eval_date - timedelta(days=lookback_days)
        try:
            state = run_analysis(symbol, window_start, eval_date)
        except Exception:
            continue
        signal = state.get("signal") or {}
        action = signal.get("action", "HOLD")
        forward_ret = get_forward_return(symbol, eval_date, hold_days)
        if forward_ret is None:
            forward_ret = 0.0
        rows.append({
            "date": eval_date.isoformat(),
            "action": action,
            "signal": action,
            "forward_return": forward_ret,
        })
    metrics = compute_metrics(rows, signal_key="signal", return_key="forward_return", action_key="action")
    return {"metrics": metrics, "rows": rows}
