"""State schemas and context for LangGraph workflows."""

from typing import Any, Optional, TypedDict


class AnalysisState(TypedDict, total=False):
    """State for the analysis graph: symbol -> OHLCV -> enrich + sentiment -> signal."""

    symbol: str
    days: int
    company_name: Optional[str]
    ohlcv: list
    enrich_result: Optional[dict]
    sentiment_result: Optional[dict]
    signal: str
    reason: str
    error: Optional[str]


class BacktestState(TypedDict, total=False):
    """State for the backtest graph: params -> run_backtest -> metrics, rows, strategy."""

    symbol: Optional[str]
    symbols: Optional[list[str]]
    strategy_assignments: Optional[dict[str, str]]
    start: str
    end: str
    lookback_days: Optional[int]
    hold_days: Optional[int]
    step_days: Optional[int]
    strategy_id: Optional[str]
    params: Optional[dict[str, Any]]
    metrics: Optional[dict]
    rows: Optional[list]
    strategy: Optional[dict]
    by_symbol: Optional[dict]
    run_id: Optional[str]
    error: Optional[str]


class GraphContext:
    """Context passed into graph nodes (config, providers, cache_dir). Not serialized."""

    __slots__ = ("config", "cache_dir", "data_provider", "sentiment_provider")

    def __init__(
        self,
        *,
        config: Any,
        cache_dir: str,
        data_provider: Any,
        sentiment_provider: Any,
    ):
        self.config = config
        self.cache_dir = cache_dir
        self.data_provider = data_provider
        self.sentiment_provider = sentiment_provider
