"""Data provider protocol for daily OHLCV."""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import pandas as pd


class DataProvider(ABC):
    """Interface for fetching daily OHLCV. Implementations register by name."""

    @abstractmethod
    def get_daily_ohlcv(
        self,
        symbol: str,
        start: date,
        end: date,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Return daily OHLCV with DatetimeIndex.
        Columns: Open, High, Low, Close, Volume (optional Adj Close).
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for registry."""
        ...
