"""Volume and price structure summaries from OHLCV."""

import pandas as pd


def volume_summary(df: pd.DataFrame, window: int = 20) -> str:
    """Describe volume vs average and recent trend."""
    if df.empty or "Volume" not in df.columns:
        return "No volume data."
    vol = df["Volume"]
    avg_vol = vol.rolling(window, min_periods=1).mean().iloc[-1] if len(vol) >= 1 else vol.iloc[-1]
    last_vol = vol.iloc[-1]
    if avg_vol and avg_vol > 0:
        pct = (last_vol / avg_vol - 1) * 100
        return f"Latest volume {last_vol:,.0f} vs {window}d avg {avg_vol:,.0f} ({pct:+.1f}%)."
    return f"Latest volume {last_vol:,.0f}."


def structure_summary(df: pd.DataFrame, short: int = 5, long: int = 20) -> str:
    """Higher highs / higher lows style structure."""
    if df.empty or len(df) < long:
        return "Insufficient data for structure."
    close = df["Close"]
    recent = close.iloc[-long:]
    highs = recent.rolling(short, min_periods=1).max()
    lows = recent.rolling(short, min_periods=1).min()
    last_high = highs.iloc[-1]
    last_low = lows.iloc[-1]
    prev_high = highs.iloc[-short - 1] if len(highs) > short else last_high
    prev_low = lows.iloc[-short - 1] if len(lows) > short else last_low
    hh = last_high > prev_high
    hl = last_low > prev_low
    if hh and hl:
        return "Higher highs and higher lows (uptrend structure)."
    if not hh and not hl:
        return "Lower highs and lower lows (downtrend structure)."
    return "Mixed structure (sideways or transition)."
