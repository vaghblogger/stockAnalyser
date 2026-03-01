"""Yahoo Finance data provider for NSE/BSE (yfinance)."""

import os
import sys
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from src.data.providers.base import DataProvider

# Single-request range; beyond this we chunk (yfinance often returns only ~1y per call for NSE)
_CHUNK_DAYS = 300


@contextmanager
def _quiet_stderr():
    """Temporarily suppress stderr to avoid yfinance 'possibly delisted' / 'Failed download' spam."""
    old_stderr = sys.stderr
    try:
        sys.stderr = open(os.devnull, "w")
        yield
    finally:
        if sys.stderr is not old_stderr:
            try:
                sys.stderr.close()
            except Exception:
                pass
        sys.stderr = old_stderr


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has required OHLCV columns and clean index."""
    if df.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close", "Volume"]
    for c in required:
        if c not in df.columns:
            df[c] = float("nan")
    df = df[required].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.sort_index()


def _download_one(
    symbol: str,
    start: date,
    end: date,
    auto_adjust: bool,
) -> pd.DataFrame:
    """One yf.download call for [start, end). Suppresses yfinance stderr to avoid console spam."""
    try:
        with _quiet_stderr():
            df = yf.download(
                symbol,
                start=start.isoformat(),
                end=end.isoformat(),
                interval="1d",
                progress=False,
                auto_adjust=auto_adjust,
                threads=False,
            )
        return _normalize_ohlcv(df)
    except Exception:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


class YahooDataProvider(DataProvider):
    """Free OHLCV via yfinance. Symbols: SYMBOL.NS (NSE), SYMBOL.BO (BSE)."""

    def __init__(self, cache_ttl_days: int = 1, auto_adjust: bool = True, **kwargs: Any) -> None:
        self.cache_ttl_days = cache_ttl_days
        self.auto_adjust = auto_adjust

    @property
    def name(self) -> str:
        return "yfinance"

    def get_daily_ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Download daily OHLCV. For >_CHUNK_DAYS we fetch in chunks and merge (avoids 1y cap)."""
        span_days = (end - start).days
        if span_days <= _CHUNK_DAYS:
            df = _download_one(symbol, start, end, self.auto_adjust)
            return df

        chunks = []
        current = start
        while current < end:
            chunk_end = min(current + timedelta(days=_CHUNK_DAYS), end)
            part = _download_one(symbol, current, chunk_end, self.auto_adjust)
            if not part.empty:
                chunks.append(part)
            current = chunk_end

        if not chunks:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        df = pd.concat(chunks)
        if df.index.duplicated().any():
            df = df.loc[~df.index.duplicated(keep="first")]
        df = df.sort_index()
        # Clip to requested range (yfinance end is exclusive; avoid any extra rows)
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        df = df.loc[(df.index >= start_ts) & (df.index <= end_ts)]
        return df
