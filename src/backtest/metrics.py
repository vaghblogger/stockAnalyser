"""Backtest metrics from (date, signal, forward_return) rows."""

import math
from typing import Literal

import numpy as np


def _finite_float(x: float) -> float:
    """Return x if finite, else 0.0 (for JSON-safe metrics)."""
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return 0.0
    return float(x)


def win_rate(returns: list[float]) -> float:
    """Fraction of returns > 0."""
    if not returns:
        return 0.0
    return sum(1 for r in returns if r > 0) / len(returns)


def average_return(returns: list[float]) -> float:
    if not returns:
        return 0.0
    return sum(returns) / len(returns)


def sharpe_ratio(returns: list[float], risk_free: float = 0.0) -> float:
    if not returns or len(returns) < 2:
        return 0.0
    arr = np.array(returns)
    excess = arr - risk_free
    if excess.std() == 0:
        return 0.0
    return float(np.mean(excess) / np.std(excess) * np.sqrt(252))  # annualized


def max_drawdown(cumulative_returns: list[float]) -> float:
    """Max drawdown from cumulative return series (e.g. 1, 1.02, 0.98, ...)."""
    if not cumulative_returns:
        return 0.0
    arr = np.array(cumulative_returns)
    peak = np.maximum.accumulate(arr)
    dd = (arr - peak) / np.where(peak != 0, peak, 1)
    return float(np.min(dd))


def compute_metrics(
    rows: list[dict],
    signal_key: str = "signal",
    return_key: str = "forward_return",
    action_key: str = "action",
) -> dict:
    """
    rows: list of {date, signal (e.g. BUY/SELL/HOLD), forward_return (float)}.
    Returns dict with by-signal stats and portfolio-style metrics.
    """
    by_action: dict[str, list[float]] = {"BUY": [], "SELL": [], "HOLD": []}
    for r in rows:
        sig = r.get(signal_key) or r.get(action_key)
        ret = r.get(return_key)
        if sig in by_action and ret is not None:
            try:
                v = float(ret)
                if math.isfinite(v):
                    by_action[sig].append(v)
            except (TypeError, ValueError):
                pass

    result = {
        "by_signal": {
            "BUY": {
                "count": len(by_action["BUY"]),
                "win_rate": _finite_float(win_rate(by_action["BUY"])),
                "avg_return": _finite_float(average_return(by_action["BUY"])),
            },
            "SELL": {
                "count": len(by_action["SELL"]),
                "win_rate": _finite_float(win_rate(by_action["SELL"])),
                "avg_return": _finite_float(average_return(by_action["SELL"])),
            },
            "HOLD": {"count": len(by_action["HOLD"])},
        },
    }
    # Portfolio: treat BUY as long return, SELL as -return (short), HOLD as 0
    all_returns = []
    for ret in by_action["BUY"]:
        all_returns.append(ret)
    for ret in by_action["SELL"]:
        all_returns.append(-ret)
    if all_returns:
        result["portfolio"] = {
            "trade_count": len(all_returns),
            "win_rate": _finite_float(win_rate(all_returns)),
            "avg_return": _finite_float(average_return(all_returns)),
            "sharpe": _finite_float(sharpe_ratio(all_returns)),
        }
        cum = np.cumprod([1 + r for r in all_returns])
        result["portfolio"]["max_drawdown"] = _finite_float(max_drawdown(cum.tolist()))
    else:
        result["portfolio"] = {"trade_count": 0, "win_rate": 0, "avg_return": 0, "sharpe": 0, "max_drawdown": 0}
    return result
