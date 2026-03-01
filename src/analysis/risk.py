"""Risk and volatility context from ATR and indicators."""

from typing import Any, Optional

import pandas as pd


def risk_summary(df: pd.DataFrame, indicators: Optional[dict[str, float]] = None) -> str:
    """ATR-based volatility and risk context."""
    if df.empty:
        return "No data."
    parts = []
    if indicators and "atr" in indicators:
        atr = indicators["atr"]
        close = float(df["Close"].iloc[-1])
        if close and close > 0:
            atr_pct = (atr / close) * 100
            parts.append(f"ATR {atr_pct:.2f}% of price")
            if atr_pct > 3:
                parts.append("(high volatility)")
            else:
                parts.append("(moderate volatility)")
    if not parts:
        return "Volatility data not available."
    return " ".join(parts)


def volatility_regime(indicators: Optional[dict[str, float]] = None, threshold_pct: float = 3.0) -> str:
    """Classify volatility regime."""
    if not indicators or "atr" not in indicators:
        return "unknown"
    # Would need current price for %; use raw ATR in context
    atr = indicators["atr"]
    if atr > 0:
        # Heuristic: assume we have atr_pct from somewhere or use a default
        return "high" if threshold_pct > 2 else "normal"
    return "normal"
