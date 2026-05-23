"""
Backtest endpoints.
POST /backtest/{symbol} — runs walk-forward backtest on 5 years of data.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.backtest.engine import walk_forward_backtest
from app.data import cache
from app.data.fetchers import fetch_ohlcv
from app.data.universe import is_valid_symbol

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/{symbol}")
async def run_backtest(symbol: str):
    """
    Run a walk-forward backtest for a symbol on 5 years of daily OHLCV data.

    This is computationally expensive (several seconds per symbol).
    Results are cached for 24 hours to avoid redundant re-runs.

    Returns:
        metrics dict + per-trade summary + equity curve (sampled monthly for payload size).
    """
    sym = symbol.upper()
    if not is_valid_symbol(sym):
        raise HTTPException(status_code=404, detail=f"{sym} is not in the supported universe")

    cache_key = f"backtest:{sym}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ohlcv_df = fetch_ohlcv(sym, period="5y")
    if ohlcv_df.empty or len(ohlcv_df) < 600:
        raise HTTPException(
            status_code=503,
            detail=f"Insufficient data for {sym} — need at least 600 trading days",
        )

    try:
        result = walk_forward_backtest(ohlcv_df, sym)
    except Exception as exc:
        logger.error("Backtest failed for %s: %s", sym, exc)
        raise HTTPException(status_code=500, detail=f"Backtest error: {exc}") from exc

    # Sample equity curve monthly to keep payload manageable
    equity_sampled = {}
    if not result.equity_curve.empty:
        monthly = result.equity_curve.resample("ME").last()
        equity_sampled = {str(k.date()): round(float(v), 2) for k, v in monthly.items()}

    trades_summary = []
    if not result.trades.empty:
        for _, row in result.trades.iterrows():
            trades_summary.append(
                {
                    "entry_date": str(row.get("entry_date", "")),
                    "exit_date": str(row.get("exit_date", "")),
                    "trade_return": round(float(row.get("trade_return", 0)), 4),
                }
            )

    response = {
        "symbol": sym,
        "summary": result.summary(),
        "metrics": result.metrics,
        "equity_curve": equity_sampled,
        "trades": trades_summary,
        "parameters": result.parameters,
        "disclaimer": "Past performance does not guarantee future results.",
    }
    cache.set(cache_key, response, ttl_seconds=86400)  # 24h cache
    return response
