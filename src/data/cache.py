"""OHLCV cache by (symbol, date range). Local Parquet; optional Redis later."""

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd


def _cache_path(cache_dir: str, symbol: str, start: date, end: date) -> Path:
    safe = symbol.replace(".", "_")
    return Path(cache_dir) / f"{safe}_{start}_{end}.parquet"


def read_ohlcv_cache(
    cache_dir: str,
    symbol: str,
    start: date,
    end: date,
) -> Optional[pd.DataFrame]:
    """Return cached DataFrame if file exists and is valid."""
    path = _cache_path(cache_dir, symbol, start, end)
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return None


def write_ohlcv_cache(
    cache_dir: str,
    symbol: str,
    start: date,
    end: date,
    df: pd.DataFrame,
) -> None:
    """Write DataFrame to cache."""
    path = _cache_path(cache_dir, symbol, start, end)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=True)


def get_cached_or_fetch(
    cache_dir: str,
    symbol: str,
    start: date,
    end: date,
    fetcher: callable,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Return cached OHLCV or call fetcher(symbol, start, end) and cache result."""
    if use_cache:
        cached = read_ohlcv_cache(cache_dir, symbol, start, end)
        if cached is not None and not cached.empty:
            return cached
    df = fetcher(symbol, start, end)
    if use_cache and not df.empty:
        write_ohlcv_cache(cache_dir, symbol, start, end, df)
    return df
