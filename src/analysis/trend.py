"""Trend and pattern summary from OHLCV and indicators."""

from typing import Any, Optional

import pandas as pd


def trend_summary(df: pd.DataFrame, indicators: Optional[dict[str, float]] = None) -> str:
    """Text summary of trend from SMA/EMA and price position."""
    if df.empty:
        return "No data."
    close = float(df["Close"].iloc[-1])
    parts = []
    for col in ["sma_20", "sma_50", "sma_200"]:
        if col in df.columns:
            val = df[col].dropna().iloc[-1]
            if close > val:
                parts.append(f"Price above {col}")
            else:
                parts.append(f"Price below {col}")
    if indicators:
        rsi = indicators.get("rsi")
        if rsi is not None:
            if rsi > 70:
                parts.append("RSI overbought")
            elif rsi < 30:
                parts.append("RSI oversold")
            else:
                parts.append(f"RSI neutral ({rsi:.0f})")
        macd_hist = indicators.get("macd_hist")
        if macd_hist is not None:
            if macd_hist > 0:
                parts.append("MACD bullish")
            else:
                parts.append("MACD bearish")
    return "; ".join(parts) if parts else "Insufficient indicators."


def pattern_flags(df: pd.DataFrame, indicators: Optional[dict[str, float]] = None) -> list[str]:
    """Simple pattern flags for rules."""
    flags = []
    if df.empty:
        return flags
    if indicators:
        rsi = indicators.get("rsi")
        if rsi is not None and rsi < 30:
            flags.append("rsi_oversold")
        if rsi is not None and rsi > 70:
            flags.append("rsi_overbought")
        macd_hist = indicators.get("macd_hist")
        if macd_hist is not None and macd_hist > 0:
            flags.append("macd_bullish")
        if macd_hist is not None and macd_hist < 0:
            flags.append("macd_bearish")
    if "sma_200" in df.columns and not df["sma_200"].isna().all():
        if float(df["Close"].iloc[-1]) > float(df["sma_200"].iloc[-1]):
            flags.append("above_sma200")
        else:
            flags.append("below_sma200")
    return flags
