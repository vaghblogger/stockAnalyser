"""Paper trading: portfolios, positions, run simulation."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.db.app_db import (
    add_paper_position,
    append_paper_snapshot,
    create_paper_portfolio,
    delete_paper_portfolio,
    get_paper_portfolio,
    get_paper_snapshots,
    list_paper_portfolios,
    list_paper_positions,
    remove_paper_position,
    update_paper_portfolio,
)
from src.paper.engine import run_paper_day

router = APIRouter()


class PaperPortfolioCreate(BaseModel):
    name: str
    initial_capital: float
    currency: str = "INR"


class PaperPortfolioUpdate(BaseModel):
    name: Optional[str] = None
    initial_capital: Optional[float] = None


class PositionAdd(BaseModel):
    symbol: str
    strategy_ids: list[str] = []


class RunPaperRequest(BaseModel):
    up_to_date: Optional[str] = None  # YYYY-MM-DD; if not set, run one day from last snapshot


def _config(request: Request):
    c = getattr(request.app.state, "config", None)
    if c is None:
        from src.config_loader import get_config
        c = get_config()
    return c


@router.get("/portfolios")
def list_portfolios(request: Request):
    config = _config(request)
    return {"portfolios": list_paper_portfolios(config.cache_dir), "count": len(list_paper_portfolios(config.cache_dir))}


@router.get("/portfolios/{portfolio_id}")
def get_portfolio(request: Request, portfolio_id: str):
    config = _config(request)
    p = get_paper_portfolio(config.cache_dir, portfolio_id)
    if not p:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Portfolio not found")
    positions = list_paper_positions(config.cache_dir, portfolio_id)
    return {"portfolio": p, "positions": positions}


@router.post("/portfolios")
def create_portfolio(request: Request, body: PaperPortfolioCreate):
    config = _config(request)
    return create_paper_portfolio(config.cache_dir, body.name, body.initial_capital, body.currency)


@router.put("/portfolios/{portfolio_id}")
def update_portfolio(request: Request, portfolio_id: str, body: PaperPortfolioUpdate):
    config = _config(request)
    p = update_paper_portfolio(config.cache_dir, portfolio_id, name=body.name, initial_capital=body.initial_capital)
    if not p:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return p


@router.delete("/portfolios/{portfolio_id}")
def delete_portfolio(request: Request, portfolio_id: str):
    config = _config(request)
    ok = delete_paper_portfolio(config.cache_dir, portfolio_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"ok": True}


@router.get("/portfolios/{portfolio_id}/positions")
def get_positions(request: Request, portfolio_id: str):
    config = _config(request)
    return {"positions": list_paper_positions(config.cache_dir, portfolio_id)}


@router.post("/portfolios/{portfolio_id}/positions")
def add_position(request: Request, portfolio_id: str, body: PositionAdd):
    config = _config(request)
    return add_paper_position(config.cache_dir, portfolio_id, body.symbol.strip().upper(), body.strategy_ids)


@router.delete("/portfolios/{portfolio_id}/positions/{symbol}")
def remove_position(request: Request, portfolio_id: str, symbol: str):
    config = _config(request)
    ok = remove_paper_position(config.cache_dir, portfolio_id, symbol)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Position not found")
    return {"ok": True}


@router.post("/portfolios/{portfolio_id}/run")
def run_simulation(request: Request, portfolio_id: str, body: Optional[RunPaperRequest] = None):
    """Run paper trading: one day or up to up_to_date."""
    config = _config(request)
    provider = getattr(request.app.state, "data_provider", None)
    if not provider:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Data provider not available")
    up_to = body.up_to_date if body and body.up_to_date else None
    result = run_paper_day(
        cache_dir=config.cache_dir,
        portfolio_id=portfolio_id,
        get_ohlcv=lambda sym, start, end: provider.get_daily_ohlcv(sym, start, end),
        up_to_date=up_to,
    )
    return result


@router.get("/portfolios/{portfolio_id}/snapshots")
def get_snapshots(request: Request, portfolio_id: str, from_date: Optional[str] = None, to_date: Optional[str] = None):
    config = _config(request)
    snapshots = get_paper_snapshots(config.cache_dir, portfolio_id, from_date=from_date, to_date=to_date)
    return {"snapshots": snapshots, "count": len(snapshots)}
