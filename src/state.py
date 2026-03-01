"""Shared state schema and Pydantic models for request/response JSON."""

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SentimentResult(BaseModel):
    """Output of sentiment provider."""

    score: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score -1 to 1")
    label: str = Field(..., description="positive | neutral | negative")
    snippets: list[str] = Field(default_factory=list)
    source: str = Field(default="", description="Provider or source name")


class Signal(BaseModel):
    """Final buy/sell/hold signal."""

    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


# --- Config schema (Pydantic) ---


class IndicatorTrendConfig(BaseModel):
    sma_periods: list[int] = [20, 50, 200]
    ema_periods: list[int] = [12, 26]
    adx_period: int = 14
    ichimoku: bool = True
    parabolic_sar: bool = True


class IndicatorMomentumConfig(BaseModel):
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    stochastic_k: int = 14
    stochastic_d: int = 3
    cci_period: int = 20
    roc_period: int = 10


class IndicatorVolatilityConfig(BaseModel):
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    atr_period: int = 14
    keltner_period: int = 20


class IndicatorVolumeConfig(BaseModel):
    obv: bool = True
    mfi_period: int = 14
    chaikin_period: int = 20


class IndicatorSupportResistanceConfig(BaseModel):
    pivot: bool = True
    swing_days: int = 30


class IndicatorsConfig(BaseModel):
    trend: IndicatorTrendConfig = Field(default_factory=IndicatorTrendConfig)
    momentum: IndicatorMomentumConfig = Field(default_factory=IndicatorMomentumConfig)
    volatility: IndicatorVolatilityConfig = Field(default_factory=IndicatorVolatilityConfig)
    volume: IndicatorVolumeConfig = Field(default_factory=IndicatorVolumeConfig)
    support_resistance: IndicatorSupportResistanceConfig = Field(
        default_factory=IndicatorSupportResistanceConfig
    )


class AnalysisConfig(BaseModel):
    indicators: IndicatorsConfig = Field(default_factory=IndicatorsConfig)
    trend_thresholds: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=lambda: {"atr_multiplier_stop": 2.0})


class LLMConfig(BaseModel):
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 500


class DecisionConfig(BaseModel):
    mode: Literal["rule", "ml", "hybrid"] = "hybrid"
    rule_overlay: dict[str, Any] = Field(
        default_factory=lambda: {"rsi_no_buy_above": 80, "rsi_no_sell_below": 20}
    )


class BacktestConfig(BaseModel):
    default_lookback_days: int = 90
    default_hold_days: int = 5
    default_step_days: int = 5


class APIConfig(BaseModel):
    port: int = 8000
    workers: int = 1
    request_timeout_seconds: int = 60
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class ProvidersConfig(BaseModel):
    data_provider: str = "yfinance"
    sentiment_provider: str = "free_news_finbert"
    yfinance: dict[str, Any] = Field(default_factory=lambda: {"cache_ttl_days": 1, "auto_adjust": True})


class AppConfig(BaseModel):
    """Validated application config (from YAML + env overrides)."""

    default_exchange: str = "NSE"
    symbol_suffix: str = ".NS"
    symbols_path: str = "config/symbols.csv"
    cache_dir: str = "data/cache"
    cache_ttl_days: int = 1
    max_lookback_days: int = 3650
    max_backtest_dates: int = 1000
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    decision: DecisionConfig = Field(default_factory=DecisionConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    api: APIConfig = Field(default_factory=APIConfig)
