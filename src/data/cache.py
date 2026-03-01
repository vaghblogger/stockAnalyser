"""OHLCV cache using SQLite. One DB file, one row per (symbol, date)."""

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd


def _db_path(cache_dir: str) -> Path:
    path = Path(cache_dir) / "ohlcv.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.commit()


def read_ohlcv_cache(
    cache_dir: str,
    symbol: str,
    start: date,
    end: date,
) -> Optional[pd.DataFrame]:
    """
    Return cached DataFrame if we have full coverage for [start, end].
    One row per (symbol, date) in SQLite.
    """
    import sqlite3
    db = _db_path(cache_dir)
    if not db.exists():
        return None
    start_str = start.isoformat()
    end_str = end.isoformat()
    try:
        conn = sqlite3.connect(str(db))
        _ensure_table(conn)
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume FROM ohlcv WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date",
            conn,
            params=(symbol, start_str, end_str),
        )
        conn.close()
        if df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df.columns = ["Open", "High", "Low", "Close", "Volume"]
        tmin, tmax = df.index.min(), df.index.max()
        min_date = tmin.date() if hasattr(tmin, "date") else pd.Timestamp(tmin).date()
        max_date = tmax.date() if hasattr(tmax, "date") else pd.Timestamp(tmax).date()
        if min_date <= start and max_date >= end:
            return df
        return None
    except Exception:
        return None


def read_ohlcv_cache_partial(
    cache_dir: str,
    symbol: str,
    start: date,
    end: date,
    min_rows: int = 20,
) -> Optional[pd.DataFrame]:
    """
    Return cached DataFrame for symbol in [start, end] if we have at least min_rows.
    Does not require full date coverage (use for dashboard when partial data is OK).
    """
    import sqlite3
    db = _db_path(cache_dir)
    if not db.exists():
        return None
    start_str = start.isoformat()
    end_str = end.isoformat()
    try:
        conn = sqlite3.connect(str(db))
        _ensure_table(conn)
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume FROM ohlcv WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date",
            conn,
            params=(symbol, start_str, end_str),
        )
        conn.close()
        if df.empty or len(df) < min_rows:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df.columns = ["Open", "High", "Low", "Close", "Volume"]
        return df.sort_index()
    except Exception:
        return None


def read_ohlcv_cache_last_n(
    cache_dir: str,
    symbol: str,
    n: int = 250,
) -> Optional[pd.DataFrame]:
    """
    Return the last n cached rows for symbol (most recent dates). Use when date range has no data.
    """
    import sqlite3
    db = _db_path(cache_dir)
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(str(db))
        _ensure_table(conn)
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume FROM ohlcv WHERE symbol = ? ORDER BY date DESC LIMIT ?",
            conn,
            params=(symbol, n),
        )
        conn.close()
        if df.empty or len(df) < 20:
            return None
        df = df.iloc[::-1].reset_index(drop=True)  # oldest first
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        df.columns = ["Open", "High", "Low", "Close", "Volume"]
        return df.sort_index()
    except Exception:
        return None


def write_ohlcv_cache(
    cache_dir: str,
    symbol: str,
    df: pd.DataFrame,
) -> None:
    """Write OHLCV rows to SQLite (INSERT OR REPLACE per symbol, date)."""
    import sqlite3
    if df.empty:
        return
    db = _db_path(cache_dir)
    conn = sqlite3.connect(str(db))
    _ensure_table(conn)
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    for idx, row in df.iterrows():
        d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        o = float(row.get("Open", row.get("open", 0)))
        h = float(row.get("High", row.get("high", 0)))
        lo = float(row.get("Low", row.get("low", 0)))
        c = float(row.get("Close", row.get("close", 0)))
        v = float(row.get("Volume", row.get("volume", 0)))
        conn.execute(
            "INSERT OR REPLACE INTO ohlcv (symbol, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (symbol, d, o, h, lo, c, v),
        )
    conn.commit()
    conn.close()


def init_cache_db(cache_dir: str) -> None:
    """Ensure the cache DB and ohlcv table exist. Call once at startup or first use."""
    import sqlite3
    db = _db_path(cache_dir)
    conn = sqlite3.connect(str(db))
    _ensure_table(conn)
    conn.close()


def list_symbols_in_cache(cache_dir: str) -> list[str]:
    """Return distinct symbols in the OHLCV cache, sorted. Updates as new data is written."""
    import sqlite3
    db = _db_path(cache_dir)
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(str(db))
        _ensure_table(conn)
        cur = conn.execute("SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol")
        symbols = [row[0] for row in cur.fetchall()]
        conn.close()
        return symbols
    except Exception:
        return []


def get_cached_or_fetch(
    cache_dir: str,
    symbol: str,
    start: date,
    end: date,
    fetcher: callable,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Return cached OHLCV if we have full coverage, else fetch and cache."""
    if use_cache:
        init_cache_db(cache_dir)
    if use_cache:
        cached = read_ohlcv_cache(cache_dir, symbol, start, end)
        if cached is not None and not cached.empty:
            return cached
    df = fetcher(symbol, start, end)
    if not df.empty:
        write_ohlcv_cache(cache_dir, symbol, df)
    return df
