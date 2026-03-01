"""
Configurable rule engine for backtest signals.

Rule format is inspired by TradingView Pine Script:
- Logical: and, or, not (see https://www.tradingview.com/pine-script-docs/language/operators/)
- Comparison: <, <=, >, >=, ==, !=

Available indicator keys (from compute_indicators): rsi, macd, macd_signal, macd_hist,
  sma_20, sma_50, sma_200, ema_12, ema_26, atr, bb_upper, bb_mid, bb_lower, obv.
  'close' is added by the backtest route from the latest Close price.

Available flags (from pattern_flags): rsi_oversold, rsi_overbought, macd_bullish, macd_bearish,
  above_sma200, below_sma200.
"""

from typing import Any, Optional

# Comparison operators: same set as Pine Script
_COMPARISONS = {
    "<": lambda a, b: a < b if _both_finite(a, b) else False,
    "<=": lambda a, b: a <= b if _both_finite(a, b) else False,
    ">": lambda a, b: a > b if _both_finite(a, b) else False,
    ">=": lambda a, b: a >= b if _both_finite(a, b) else False,
    "==": lambda a, b: a == b if _both_finite(a, b) else False,
    "!=": lambda a, b: a != b if _both_finite(a, b) else False,
}


def _both_finite(a: Any, b: Any) -> bool:
    try:
        fa = float(a)
        fb = float(b)
        return bool(fa == fa and fb == fb)  # reject nan
    except (TypeError, ValueError):
        return False


def _get_indicator_value(indicators: dict[str, float], key: str) -> Optional[float]:
    """Return numeric value for an indicator key; None if missing or non-finite."""
    v = indicators.get(key)
    if v is None:
        return None
    try:
        f = float(v)
        if f != f:  # nan
            return None
        return f
    except (TypeError, ValueError):
        return None


def _evaluate_condition(
    node: dict,
    indicators: dict[str, float],
    flags: list[str],
) -> bool:
    """Evaluate a single condition node. Returns False on invalid/missing data."""
    if not isinstance(node, dict):
        return False

    # Logical AND: all sub-rules must be true
    if "and" in node:
        children = node["and"]
        if not isinstance(children, list):
            return False
        return all(_evaluate_condition(c, indicators, flags) for c in children)

    # Logical OR: at least one sub-rule true
    if "or" in node:
        children = node["or"]
        if not isinstance(children, list):
            return False
        return any(_evaluate_condition(c, indicators, flags) for c in children)

    # Logical NOT
    if "not" in node:
        return not _evaluate_condition(node["not"], indicators, flags)

    # Flag condition: true if flag is present in flags list
    if "flag" in node:
        flag_name = node["flag"]
        if not isinstance(flag_name, str):
            return False
        return flag_name in flags

    # Indicator vs constant: { "indicator": "rsi", "op": "<", "value": 30 }
    if "indicator" in node and "op" in node and "value" in node:
        left = _get_indicator_value(indicators, node["indicator"])
        if left is None:
            return False
        op = node["op"]
        if op not in _COMPARISONS:
            return False
        try:
            right = float(node["value"])
        except (TypeError, ValueError):
            return False
        return _COMPARISONS[op](left, right)

    # Indicator vs indicator: { "left": "close", "op": ">", "right": "sma_200" }
    if "left" in node and "op" in node and "right" in node:
        left = _get_indicator_value(indicators, node["left"])
        right = _get_indicator_value(indicators, node["right"])
        if left is None or right is None:
            return False
        op = node["op"]
        if op not in _COMPARISONS:
            return False
        return _COMPARISONS[op](left, right)

    return False


def evaluate_rule(
    rule: Any,
    indicators: dict[str, float],
    flags: list[str],
) -> bool:
    """
    Evaluate a rule (condition or group) against current indicators and flags.

    Rule can be:
    - dict with "and" / "or" / "not" (logical)
    - dict with "indicator", "op", "value" (indicator vs number)
    - dict with "left", "op", "right" (indicator vs indicator)
    - dict with "flag" (flag name; true if present)

    Operators: <, <=, >, >=, ==, !=
    """
    if rule is None:
        return False
    return _evaluate_condition(rule, indicators, flags)


def rule_signal_from_rules(
    buy_rule: Any,
    sell_rule: Any,
    indicators: dict[str, float],
    flags: list[str],
) -> tuple[str, str]:
    """
    Return (action, reason) from optional buy_rule and sell_rule.
    BUY if buy_rule is true and sell_rule is not; SELL if sell_rule is true; else HOLD.
    """
    buy_triggered = evaluate_rule(buy_rule, indicators, flags) if buy_rule else False
    sell_triggered = evaluate_rule(sell_rule, indicators, flags) if sell_rule else False

    if buy_triggered and not sell_triggered:
        return "BUY", "Custom buy rule"
    if sell_triggered:
        return "SELL", "Custom sell rule"
    return "HOLD", ""
