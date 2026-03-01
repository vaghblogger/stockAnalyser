"""Yahoo Finance data provider for NSE/BSE (yfinance)."""

from datetime import date, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from src.data.providers.base import DataProvider


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
        """Download daily OHLCV; ensure columns Open, High, Low, Close, Volume."""
        # yfinance expects datetime or string
        start_str = start.isoformat()
        end_str = end.isoformat()
        df = yf.download(
            symbol,
            start=start_str,
            end=end_str,
            progress=False,
            auto_adjust=self.auto_adjust,
            threads=False,
        )
        if df.empty:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        # MultiIndex columns: take first level if (Close, symbol) style
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        required = ["Open", "High", "Low", "Close", "Volume"]
        for c in required:
            if c not in df.columns:
                df[c] = float("nan")
        df = df[required].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.sort_index()
        return df
