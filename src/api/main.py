"""FastAPI app: /ohlcv, /enrich, /sentiment, /trend, /risk, /backtest, /metrics."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.config_loader import load_config
from src.data.cache import init_cache_db
from src.data.providers import get_data_provider
from src.data.universe import ensure_universe_from_csv
from src.db.app_db import init_app_db
from src.scheduler import start_scheduler, stop_scheduler
from src.sentiment.providers import get_sentiment_provider

# Import routes to register
from src.api.routes import backtest, dashboard, dashboard_views, data, enrich, ohlcv, paper, risk, sentiment, strategies, trend

# Ensure data/sentiment providers are registered
import src.data.providers  # noqa: F401
import src.sentiment.providers  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    init_cache_db(cfg.cache_dir)
    init_app_db(cfg.cache_dir)
    ensure_universe_from_csv(cfg.cache_dir)
    app.state.config = cfg
    app.state.data_provider = get_data_provider(
        cfg.providers.data_provider,
        **cfg.providers.yfinance,
    )
    app.state.sentiment_provider = get_sentiment_provider(cfg.providers.sentiment_provider)
    refresh_cfg = getattr(cfg, "refresh", None)
    if refresh_cfg and getattr(refresh_cfg, "refresh_enabled", True):
        def get_fetcher():
            p = getattr(app.state, "data_provider", None)
            return p.get_daily_ohlcv if p else None
        start_scheduler(
            cfg.cache_dir,
            get_fetcher,
            interval_minutes=getattr(refresh_cfg, "refresh_interval_minutes", 360),
            lookback_days=getattr(refresh_cfg, "refresh_lookback_days", 5),
            enabled=getattr(refresh_cfg, "refresh_enabled", True),
        )
    yield
    stop_scheduler()


app = FastAPI(title="Stock Analysis API", version="0.1.0", lifespan=lifespan)
cfg = load_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Set no-cache headers for /static and /app so browser always loads fresh assets."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.scope.get("path") or ""
        if path.startswith("/static/") or path in ("/app", "/app/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(NoCacheStaticMiddleware)

app.include_router(ohlcv.router, prefix="", tags=["ohlcv"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(enrich.router, prefix="", tags=["enrich"])
app.include_router(sentiment.router, prefix="", tags=["sentiment"])
app.include_router(trend.router, prefix="", tags=["trend"])
app.include_router(risk.router, prefix="", tags=["risk"])
app.include_router(backtest.router, prefix="", tags=["backtest"])
app.include_router(dashboard.router, prefix="", tags=["dashboard"])
app.include_router(dashboard_views.router, prefix="/api/dashboard", tags=["dashboard_views"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(paper.router, prefix="/api/paper", tags=["paper"])


@app.get("/dashboard", tags=["dashboard"])
def dashboard_route(request: Request, lookback_days: int = 90):
    """All stocks in cache with indicators and signal. Delegates to dashboard module."""
    return dashboard.get_dashboard(request, lookback_days=lookback_days)

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
