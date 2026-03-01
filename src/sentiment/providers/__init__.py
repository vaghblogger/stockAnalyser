from src.sentiment.providers.base import SentimentProvider
from src.sentiment.providers.free_news_finbert import FreeNewsFinbertProvider
from src.sentiment.providers.registry import get_sentiment_provider, register_sentiment_provider

register_sentiment_provider("free_news_finbert", FreeNewsFinbertProvider)

__all__ = ["SentimentProvider", "get_sentiment_provider", "register_sentiment_provider", "FreeNewsFinbertProvider"]
