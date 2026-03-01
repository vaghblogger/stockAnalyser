from src.data.providers.base import DataProvider
from src.data.providers.registry import get_data_provider, register_data_provider
from src.data.providers.yahoo import YahooDataProvider

register_data_provider("yfinance", YahooDataProvider)

__all__ = ["DataProvider", "get_data_provider", "register_data_provider", "YahooDataProvider"]
