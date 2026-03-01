"""FastAPI app: /ohlcv, /enrich, /sentiment, /trend, /risk, /backtest, /metrics."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config_loader import load_config
from src.data.providers import get_data_provider
from src.data.symbols import resolve_symbol
from src.sentiment.providers import get_sentiment_provider

# Import routes to register
from src.api.routes import backtest, enrich, ohlcv, risk, sentiment, trend

# Ensure data/sentiment providers are registered
import src.data.providers  # noqa: F401
import src.sentiment.providers  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    app.state.config = cfg
    app.state.data_provider = get_data_provider(
        cfg.providers.data_provider,
        **cfg.providers.yfinance,
    )
    app.state.sentiment_provider = get_sentiment_provider(cfg.providers.sentiment_provider)
    yield
    # cleanup if any


app = FastAPI(title="Stock Analysis API", version="0.1.0", lifespan=lifespan)
cfg = load_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ohlcv.router, prefix="", tags=["ohlcv"])
app.include_router(enrich.router, prefix="", tags=["enrich"])
app.include_router(sentiment.router, prefix="", tags=["sentiment"])
app.include_router(trend.router, prefix="", tags=["trend"])
app.include_router(risk.router, prefix="", tags=["risk"])
app.include_router(backtest.router, prefix="", tags=["backtest"])


@app.get("/health")
def health():
    return {"status": "ok"}
