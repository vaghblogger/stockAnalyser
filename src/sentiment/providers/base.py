"""Sentiment provider protocol."""

from abc import ABC, abstractmethod
from typing import Optional

from src.state import SentimentResult


class SentimentProvider(ABC):
    """Interface for fetching and scoring sentiment. Implementations register by name."""

    @abstractmethod
    def get_sentiment(
        self,
        symbol: str,
        company_name: Optional[str] = None,
        lookback_days: int = 7,
        **kwargs: object,
    ) -> SentimentResult:
        """Return aggregated sentiment for the symbol over the lookback period."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for registry."""
        ...
