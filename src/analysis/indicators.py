"""Technical indicators from OHLCV. Uses pandas for core indicators (no TA-Lib required)."""

from typing import Any, Optional

import numpy as np
import pandas as pd


def _ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure columns Open, High, Low, Close, Volume (case-insensitive)."""
    df = df.copy()
    col_map = {c.upper(): c for c in df.columns}
    for name in ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]:
        if name in col_map and name not in df.columns:
            df[name] = df[col_map[name]]
    if "Close" not in df.columns and "CLOSE" in df.columns:
        df["Close"] = df["CLOSE"]
    if "High" not in df.columns and "HIGH" in df.columns:
        df["High"] = df["HIGH"]
    if "Low" not in df.columns and "LOW" in df.columns:
        df["Low"] = df["LOW"]
    if "Open" not in df.columns and "OPEN" in df.columns:
        df["Open"] = df["OPEN"]
    if "Volume" not in df.columns and "VOLUME" in df.columns:
        df["Volume"] = df["VOLUME"]
    return df


def compute_sma(df: pd.DataFrame, period: int, column: str = "Close") -> pd.Series:
    return df[column].rolling(window=period, min_periods=1).mean()


def compute_ema(df: pd.DataFrame, period: int, column: str = "Close") -> pd.Series:
    return df[column].ewm(span=period, adjust=False).mean()


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def compute_bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = df["Close"].rolling(period, min_periods=period).mean()
    std_ser = df["Close"].rolling(period, min_periods=period).std()
    upper = mid + std * std_ser
    lower = mid - std * std_ser
    return upper, mid, lower


def compute_obv(df: pd.DataFrame) -> pd.Series:
    obv = (np.sign(df["Close"].diff()) * df["Volume"]).fillna(0).cumsum()
    return obv


def compute_indicators(
    df: pd.DataFrame,
    config: Optional[Any] = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """
    Add indicator columns to df and return (df, last_values_dict).
    config: optional IndicatorsConfig or dict with trend/momentum/volatility/volume params.
    """
    df = _ensure_ohlcv(df)
    if df.empty or "Close" not in df.columns:
        return df, {}

    cfg = config
    if cfg is None:
        sma_periods = [20, 50, 200]
        ema_periods = [12, 26]
        rsi_period = 14
        macd_fast, macd_slow, macd_signal = 12, 26, 9
        atr_period = 14
        bb_period, bb_std = 20, 2.0
    else:
        t = getattr(cfg, "trend", None) or cfg.get("trend", {})
        m = getattr(cfg, "momentum", None) or cfg.get("momentum", {})
        v = getattr(cfg, "volatility", None) or cfg.get("volatility", {})
        sma_periods = t.get("sma_periods", [20, 50, 200]) if isinstance(t, dict) else getattr(t, "sma_periods", [20, 50, 200])
        ema_periods = t.get("ema_periods", [12, 26]) if isinstance(t, dict) else getattr(t, "ema_periods", [12, 26])
        rsi_period = m.get("rsi_period", 14) if isinstance(m, dict) else getattr(m, "rsi_period", 14)
        macd_fast = m.get("macd_fast", 12) if isinstance(m, dict) else getattr(m, "macd_fast", 12)
        macd_slow = m.get("macd_slow", 26) if isinstance(m, dict) else getattr(m, "macd_slow", 26)
        macd_signal = m.get("macd_signal", 9) if isinstance(m, dict) else getattr(m, "macd_signal", 9)
        atr_period = v.get("atr_period", 14) if isinstance(v, dict) else getattr(v, "atr_period", 14)
        bb_period = v.get("bollinger_period", 20) if isinstance(v, dict) else getattr(v, "bollinger_period", 20)
        bb_std = v.get("bollinger_std", 2.0) if isinstance(v, dict) else getattr(v, "bollinger_std", 2.0)

    last: dict[str, float] = {}

    def _last_finite(series: pd.Series):
        """Last valid (non-nan) value, or nan if none."""
        if series.empty:
            return float("nan")
        dropped = series.dropna()
        return float(dropped.iloc[-1]) if len(dropped) > 0 else float("nan")

    for p in sma_periods:
        df[f"sma_{p}"] = compute_sma(df, p)
        if not df.empty:
            last[f"sma_{p}"] = _last_finite(df[f"sma_{p}"])
    for p in ema_periods:
        df[f"ema_{p}"] = compute_ema(df, p)
        if not df.empty:
            last[f"ema_{p}"] = _last_finite(df[f"ema_{p}"])

    df["rsi"] = compute_rsi(df, rsi_period)
    if not df.empty:
        last["rsi"] = _last_finite(df["rsi"])

    macd_line, signal_line, hist = compute_macd(df, macd_fast, macd_slow, macd_signal)
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = hist
    if not df.empty:
        last["macd"] = _last_finite(df["macd"])
        last["macd_signal"] = _last_finite(df["macd_signal"])
        last["macd_hist"] = _last_finite(df["macd_hist"])

    df["atr"] = compute_atr(df, atr_period)
    if not df.empty:
        last["atr"] = _last_finite(df["atr"])

    bb_upper, bb_mid, bb_lower = compute_bollinger(df, bb_period, bb_std)
    df["bb_upper"] = bb_upper
    df["bb_mid"] = bb_mid
    df["bb_lower"] = bb_lower
    if not df.empty:
        last["bb_upper"] = _last_finite(df["bb_upper"])
        last["bb_lower"] = _last_finite(df["bb_lower"])

    if "Volume" in df.columns:
        obv = (np.sign(df["Close"].diff()) * df["Volume"]).fillna(0).cumsum()
        df["obv"] = obv
        if not df.empty:
            last["obv"] = _last_finite(df["obv"])

    return df, last
