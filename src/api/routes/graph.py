"""LangGraph API: POST /api/graph/analyze and POST /api/graph/backtest."""

from typing import Any, Optional

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel

from src.graph import GraphContext, build_analysis_graph, build_backtest_graph
from src.api.routes.backtest import BacktestRequest

router = APIRouter()


class AnalyzeGraphRequest(BaseModel):
    symbol: str = "RELIANCE"
    days: Optional[int] = 90


def _context_from_request(request: Request) -> GraphContext:
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    return GraphContext(
        config=config,
        cache_dir=config.cache_dir,
        data_provider=request.app.state.data_provider,
        sentiment_provider=request.app.state.sentiment_provider,
    )


@router.post("/api/graph/analyze")
def post_graph_analyze(
    request: Request,
    body: Optional[AnalyzeGraphRequest] = Body(None),
) -> dict[str, Any]:
    """Run the analysis graph: OHLCV -> enrich + sentiment (parallel) -> merge and signal."""
    ctx = _context_from_request(request)
    graph = build_analysis_graph(ctx)
    req = body or AnalyzeGraphRequest()
    initial: dict[str, Any] = {"symbol": req.symbol, "days": req.days or 90}
    result = graph.invoke(initial)
    return {
        "symbol": result.get("symbol"),
        "company_name": result.get("company_name"),
        "ohlcv_count": len(result.get("ohlcv") or []),
        "enrich_result": result.get("enrich_result"),
        "sentiment_result": result.get("sentiment_result"),
        "signal": result.get("signal", "HOLD"),
        "reason": result.get("reason", ""),
        "error": result.get("error"),
    }


@router.post("/api/graph/backtest")
def post_graph_backtest(request: Request, body: BacktestRequest) -> dict:
    """Run the backtest graph (same response shape as POST /api/backtest)."""
    ctx = _context_from_request(request)
    graph = build_backtest_graph(ctx)
    initial = {
        "symbol": body.symbol,
        "symbols": body.symbols,
        "strategy_assignments": body.strategy_assignments,
        "start": body.start,
        "end": body.end,
        "lookback_days": body.lookback_days,
        "hold_days": body.hold_days,
        "step_days": body.step_days,
        "strategy_id": body.strategy_id,
        "params": body.params,
    }
    result = graph.invoke(initial)
    if result.get("error"):
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=result["error"])
    return {
        "metrics": result.get("metrics"),
        "rows": result.get("rows"),
        "strategy": result.get("strategy"),
        "by_symbol": result.get("by_symbol"),
        "run_id": result.get("run_id"),
    }
