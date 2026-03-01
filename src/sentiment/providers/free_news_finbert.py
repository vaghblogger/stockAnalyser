"""Free sentiment: RSS/news snippets + FinBERT (transformers) scoring. Fallback neutral if no news."""

from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup

from src.state import SentimentResult
from src.sentiment.providers.base import SentimentProvider


def _fetch_rss_snippets(company_name: str, symbol: str, lookback_days: int, max_items: int = 10) -> list[str]:
    """Fetch recent headlines/snippets from RSS or simple web. Returns list of text snippets."""
    snippets: list[str] = []
    # MoneyControl RSS (example - may need to adjust URL)
    urls = [
        "https://www.moneycontrol.com/rss/latestnews.xml",
        "https://www.moneycontrol.com/rss/marketoutlook.xml",
    ]
    query = f"{company_name or symbol} stock"
    for url in urls:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "StockAnalysis/1.0"})
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:max_items]:
                title = entry.get("title") or ""
                summary = entry.get("summary") or entry.get("description") or ""
                if query.lower() in (title + summary).lower() or company_name or symbol:
                    text = (title + " " + summary).strip()
                    if text and len(text) > 20:
                        snippets.append(text[:500])
        except Exception:
            continue
        if len(snippets) >= max_items:
            break
    # If no filtered results, take generic market headlines for fallback context
    if not snippets and urls:
        try:
            resp = requests.get(urls[0], timeout=10, headers={"User-Agent": "StockAnalysis/1.0"})
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:3]:
                title = entry.get("title") or ""
                if title:
                    snippets.append(title[:300])
        except Exception:
            pass
    return snippets[:max_items]


def _score_with_finbert(snippets: list[str]) -> tuple[float, str]:
    """Aggregate sentiment from snippets using FinBERT. Returns (score -1..1, label)."""
    if not snippets:
        return 0.0, "neutral"
    try:
        from transformers import pipeline
        pipe = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            top_k=None,
            truncation=True,
            max_length=512,
        )
    except Exception:
        # Fallback: simple keyword-based if model not available
        return _keyword_score(snippets)
    scores_positive = []
    scores_negative = []
    for text in snippets:
        try:
            out = pipe(text[:512])
            if isinstance(out, list) and len(out) > 0:
                first = out[0]
            else:
                first = out
            if isinstance(first, list):
                by_label = {str(x.get("label", "")).lower(): float(x.get("score", 0)) for x in first}
            else:
                by_label = {str(first.get("label", "")).lower(): float(first.get("score", 0))}
            pos = by_label.get("positive", 0.0)
            neg = by_label.get("negative", 0.0)
            neu = by_label.get("neutral", 0.0)
            if pos + neg + neu > 0:
                scores_positive.append(pos)
                scores_negative.append(neg)
        except Exception:
            continue
    if not scores_positive:
        return 0.0, "neutral"
    avg_pos = sum(scores_positive) / len(scores_positive)
    avg_neg = sum(scores_negative) / len(scores_negative)
    score = avg_pos - avg_neg  # roughly in [-1, 1]
    if score > 0.2:
        label = "positive"
    elif score < -0.2:
        label = "negative"
    else:
        label = "neutral"
    return max(-1.0, min(1.0, score)), label


def _keyword_score(snippets: list[str]) -> tuple[float, str]:
    """Simple keyword fallback when FinBERT not available."""
    positive = ("surge", "gain", "rise", "growth", "beat", "profit", "up", "bullish", "upgrade")
    negative = ("fall", "drop", "loss", "decline", "miss", "down", "bearish", "downgrade", "cut")
    total = 0.0
    n = 0
    for s in snippets:
        low = s.lower()
        p = sum(1 for w in positive if w in low)
        neg = sum(1 for w in negative if w in low)
        if p + neg > 0:
            total += (p - neg) / max(p + neg, 1)
            n += 1
    if n == 0:
        return 0.0, "neutral"
    score = total / n
    if score > 0.2:
        label = "positive"
    elif score < -0.2:
        label = "negative"
    else:
        label = "neutral"
    return max(-1.0, min(1.0, score)), label


class FreeNewsFinbertProvider(SentimentProvider):
    """Free sentiment: RSS headlines + FinBERT (or keyword fallback)."""

    @property
    def name(self) -> str:
        return "free_news_finbert"

    def get_sentiment(
        self,
        symbol: str,
        company_name: Optional[str] = None,
        lookback_days: int = 7,
        **kwargs: object,
    ) -> SentimentResult:
        snippets = _fetch_rss_snippets(company_name or symbol, symbol, lookback_days)
        score, label = _score_with_finbert(snippets)
        return SentimentResult(
            score=score,
            label=label,
            snippets=snippets[:5],
            source=self.name,
        )
