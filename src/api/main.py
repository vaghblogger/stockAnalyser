"""FastAPI app: /ohlcv, /enrich, /sentiment, /trend, /risk, /backtest, /metrics."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.config_loader import load_config
from src.data.cache import init_cache_db
from src.data.providers import get_data_provider
from src.sentiment.providers import get_sentiment_provider

# Import routes to register
from src.api.routes import backtest, enrich, ohlcv, risk, sentiment, trend

# Ensure data/sentiment providers are registered
import src.data.providers  # noqa: F401
import src.sentiment.providers  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    init_cache_db(cfg.cache_dir)
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

# Web app: static files and /app route
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/app", include_in_schema=False)
    def app_index():
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/app/", include_in_schema=False)
    def app_index_slash():
        return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
