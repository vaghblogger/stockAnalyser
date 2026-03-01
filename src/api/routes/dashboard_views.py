"""Dashboard views CRUD: persist and restore column config."""

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.db.app_db import (
    create_dashboard_view,
    delete_dashboard_view,
    get_dashboard_view,
    list_dashboard_views,
    update_dashboard_view,
)

router = APIRouter()


class DashboardViewCreate(BaseModel):
    name: str
    columns_config: list[dict[str, Any]] = []


class DashboardViewUpdate(BaseModel):
    name: Optional[str] = None
    columns_config: Optional[list[dict[str, Any]]] = None


@router.get("/views")
def list_views(request: Request, user_id: Optional[str] = None):
    """List all saved dashboard views (optionally filtered by user_id)."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    views = list_dashboard_views(config.cache_dir, user_id=user_id)
    return {"views": views, "count": len(views)}


@router.get("/views/{view_id}")
def get_view(request: Request, view_id: str):
    """Get a single dashboard view by id."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    view = get_dashboard_view(config.cache_dir, view_id)
    if not view:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="View not found")
    return view


@router.post("/views")
def create_view(request: Request, body: DashboardViewCreate):
    """Create a new dashboard view."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    view = create_dashboard_view(config.cache_dir, body.name, body.columns_config)
    return view


@router.put("/views/{view_id}")
def update_view(request: Request, view_id: str, body: DashboardViewUpdate):
    """Update an existing dashboard view."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    view = update_dashboard_view(
        config.cache_dir,
        view_id,
        name=body.name,
        columns_config=body.columns_config,
    )
    if not view:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="View not found")
    return view


@router.delete("/views/{view_id}")
def remove_view(request: Request, view_id: str):
    """Delete a dashboard view."""
    config = getattr(request.app.state, "config", None)
    if config is None:
        from src.config_loader import get_config
        config = get_config()
    deleted = delete_dashboard_view(config.cache_dir, view_id)
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="View not found")
    return {"ok": True}
