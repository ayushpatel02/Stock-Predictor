"""Market overview endpoints — indices and broad market data."""

import logging

from fastapi import APIRouter, HTTPException

from app.data import cache
from app.data.fetchers import fetch_market_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])


@router.get("/overview")
async def market_overview():
    """
    Return current values and day-change % for Nifty 50, Bank Nifty, VIX, and Sensex.
    Results are cached for 5 minutes (indices are delayed anyway).
    """
    cached = cache.get("market:overview")
    if cached:
        return cached

    try:
        data = fetch_market_context()
    except Exception as exc:
        logger.error("Market context fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail="Market data unavailable") from exc

    cache.set("market:overview", data, ttl_seconds=300)
    return data
