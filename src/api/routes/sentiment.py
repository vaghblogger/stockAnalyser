"""GET /sentiment - fetch sentiment for symbol."""

from typing import Optional

from fastapi import APIRouter, Request

from src.state import SentimentResult

router = APIRouter()


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
    return result.model_dump()
