"""Registry for sentiment providers."""

from typing import Type

from src.sentiment.providers.base import SentimentProvider

_registry: dict[str, type[SentimentProvider]] = {}


def register_sentiment_provider(name: str, provider_class: Type[SentimentProvider]) -> None:
    _registry[name] = provider_class


def get_sentiment_provider(name: str, **kwargs: object) -> SentimentProvider:
    if name not in _registry:
        raise ValueError(f"Unknown sentiment provider: {name}. Registered: {list(_registry)}")
    return _registry[name](**kwargs)
