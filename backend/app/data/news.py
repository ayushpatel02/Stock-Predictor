"""
News fetching for Indian stocks.

Primary source: yfinance Ticker.news (free, no key needed).
Secondary source: Finnhub (free tier, 60 calls/min — needs FINNHUB_API_KEY).

Returns headlines with source, timestamp, and simple sentiment polarity
derived from headline keywords (placeholder until VADER is wired in).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import yfinance as yf

from app.config import settings
from app.data.fetchers import yf_symbol

logger = logging.getLogger(__name__)

# Lightweight keyword-based sentiment until VADER/FinBERT is enabled
_POSITIVE_KEYWORDS = {
    "surge", "soar", "jump", "gain", "rally", "rise", "beat", "outperform",
    "upgrade", "buy", "strong", "growth", "profit", "record", "high", "bullish",
    "expand", "approve", "launch", "win", "boost",
}
_NEGATIVE_KEYWORDS = {
    "fall", "drop", "plunge", "crash", "decline", "loss", "miss", "weak",
    "downgrade", "sell", "cut", "concern", "risk", "warning", "low", "bearish",
    "delay", "fine", "probe", "scandal", "fraud",
}


def _headline_sentiment(title: str) -> str:
    """Return 'positive', 'negative', or 'neutral' from headline keyword match."""
    if not title:
        return "neutral"
    t = title.lower()
    pos = sum(1 for w in _POSITIVE_KEYWORDS if w in t)
    neg = sum(1 for w in _NEGATIVE_KEYWORDS if w in t)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _format_ts(ts: int | float | None) -> str | None:
    """Convert unix timestamp to ISO string."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return None


def _from_yfinance(symbol: str, limit: int) -> list[dict[str, Any]]:
    """Fetch news from yfinance — free, returns Yahoo Finance items."""
    try:
        ticker = yf.Ticker(yf_symbol(symbol, "NSE"))
        items = ticker.news or []
    except Exception as exc:
        logger.warning("yfinance news failed for %s: %s", symbol, exc)
        return []

    out: list[dict[str, Any]] = []
    for item in items[:limit]:
        # yfinance returns a mix of legacy and new schemas; handle both.
        title = item.get("title") or item.get("content", {}).get("title")
        publisher = (
            item.get("publisher")
            or item.get("content", {}).get("provider", {}).get("displayName")
            or "Yahoo Finance"
        )
        link = item.get("link") or item.get("content", {}).get("canonicalUrl", {}).get("url")
        ts = item.get("providerPublishTime") or item.get("content", {}).get("pubDate")

        if isinstance(ts, str):
            published = ts
        else:
            published = _format_ts(ts)

        if title:
            out.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "published": published,
                "sentiment": _headline_sentiment(title),
                "source": "yfinance",
            })
    return out


def _from_finnhub(symbol: str, limit: int) -> list[dict[str, Any]]:
    """Fetch news from Finnhub free tier — needs FINNHUB_API_KEY in env."""
    if not settings.finnhub_api_key:
        return []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_ago = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() - 7 * 86400, tz=timezone.utc
    ).strftime("%Y-%m-%d")

    # Finnhub uses '.NS' for NSE symbols (same as yfinance)
    ticker = yf_symbol(symbol, "NSE")
    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": ticker,
        "from": week_ago,
        "to": today,
        "token": settings.finnhub_api_key,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            items = r.json() or []
    except Exception as exc:
        logger.warning("Finnhub news failed for %s: %s", symbol, exc)
        return []

    return [
        {
            "title": item.get("headline"),
            "publisher": item.get("source"),
            "link": item.get("url"),
            "published": _format_ts(item.get("datetime")),
            "sentiment": _headline_sentiment(item.get("headline", "")),
            "source": "finnhub",
        }
        for item in items[:limit]
        if item.get("headline")
    ]


def fetch_news(symbol: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Fetch latest news for a symbol — yfinance first, Finnhub as fallback.

    Returns a list of news items sorted by recency. Each item:
        {title, publisher, link, published, sentiment, source}
    """
    items = _from_yfinance(symbol, limit)
    if not items:
        items = _from_finnhub(symbol, limit)

    # Sort newest first
    def _sort_key(item: dict[str, Any]) -> str:
        return item.get("published") or ""

    items.sort(key=_sort_key, reverse=True)
    return items[:limit]


def aggregate_sentiment(news_items: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Aggregate news sentiment into a single score.
    Returns {bullish_count, bearish_count, neutral_count, sentiment_score}
    where sentiment_score is in [-1, 1].
    """
    pos = sum(1 for n in news_items if n.get("sentiment") == "positive")
    neg = sum(1 for n in news_items if n.get("sentiment") == "negative")
    neu = sum(1 for n in news_items if n.get("sentiment") == "neutral")
    total = pos + neg + neu
    score = (pos - neg) / total if total > 0 else 0.0
    return {
        "bullish_count": pos,
        "bearish_count": neg,
        "neutral_count": neu,
        "sentiment_score": round(score, 3),
    }
