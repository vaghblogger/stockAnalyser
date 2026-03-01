"""Strategies CRUD and global default."""

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.db.app_db import (
    create_strategy,
    delete_strategy,
    get_global_default_strategy,
    get_strategy,
    list_strategies,
    set_global_default_strategy,
    update_strategy,
)

router = APIRouter()


class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    strategy_type: str = "rule_based"
    params: dict[str, Any] = {}
    is_global_default: bool = False


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    params: Optional[dict[str, Any]] = None


@router.get("")
def list_all(request: Request):
    """List all strategies (global default first)."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    strategies = list_strategies(config.cache_dir)
    return {"strategies": strategies, "count": len(strategies)}


@router.get("/default")
def get_default(request: Request):
    """Get the global default strategy."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    s = get_global_default_strategy(config.cache_dir)
    if not s:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No global default strategy set")
    return s


@router.get("/{strategy_id}")
def get_one(request: Request, strategy_id: str):
    """Get a strategy by id."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    s = get_strategy(config.cache_dir, strategy_id)
    if not s:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Strategy not found")
    return s


@router.post("")
def create_one(request: Request, body: StrategyCreate):
    """Create a new strategy. Only one can be global default."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    s = create_strategy(
        config.cache_dir,
        name=body.name,
        strategy_type=body.strategy_type,
        params=body.params,
        description=body.description,
        is_global_default=body.is_global_default,
    )
    return s


@router.put("/{strategy_id}")
def update_one(request: Request, strategy_id: str, body: StrategyUpdate):
    """Update a strategy."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    s = update_strategy(
        config.cache_dir,
        strategy_id,
        name=body.name,
        description=body.description,
        params=body.params,
    )
    if not s:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Strategy not found")
    return s


@router.post("/{strategy_id}/set-default")
def set_default(request: Request, strategy_id: str):
    """Set this strategy as the global default."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    s = set_global_default_strategy(config.cache_dir, strategy_id)
    if not s:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Strategy not found")
    return s


@router.delete("/{strategy_id}")
def delete_one(request: Request, strategy_id: str):
    """Delete a strategy."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    deleted = delete_strategy(config.cache_dir, strategy_id)
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"ok": True}
