"""GET /sentiment - fetch sentiment for symbol."""

import math
from typing import Any, Optional

from fastapi import APIRouter, Request

from src.state import SentimentResult

router = APIRouter()


def _sanitize_json(obj: Any) -> Any:
    """Make structure JSON-safe: replace nan/inf floats with None."""
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


@router.get("/sentiment")
def get_sentiment(
    request: Request,
    symbol: str,
    company_name: Optional[str] = None,
    lookback_days: int = 7,
) -> dict:
    """Return sentiment score, label, snippets, source."""
    provider = request.app.state.sentiment_provider
    result = provider.get_sentiment(symbol=symbol, company_name=company_name, lookback_days=lookback_days)
    return _sanitize_json(result.model_dump())
