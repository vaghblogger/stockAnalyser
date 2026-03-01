"""Registry for data providers: register by name, get by config."""

from typing import Type

from src.data.providers.base import DataProvider

_registry: dict[str, type[DataProvider]] = {}


def register_data_provider(name: str, provider_class: Type[DataProvider]) -> None:
    _registry[name] = provider_class


def get_data_provider(name: str, **kwargs: object) -> DataProvider:
    if name not in _registry:
        raise ValueError(f"Unknown data provider: {name}. Registered: {list(_registry)}")
    return _registry[name](**kwargs)
