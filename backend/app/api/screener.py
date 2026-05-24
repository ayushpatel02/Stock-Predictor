"""
Screener endpoint — returns enriched data for all symbols in the universe.

This is the data source for both the heatmap dashboard and the screener table.
Heavy operation (50 yfinance calls + 50 model loads); aggressively cached.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import settings
from app.data import cache
from app.data.fetchers import fetch_fundamentals, fetch_ohlcv
from app.data.universe import all_symbols
from app.features.technical import build_features
from app.models.dvm import compute_dvm
from app.models.ml_model import FEATURE_COLS, load_model, predict as ml_predict
from app.models.risk_score import compute_risk_score

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/screener", tags=["screener"])


def _enrich_symbol(symbol: str) -> dict | None:
    """Build a screener row for one symbol. Returns None on data failure."""
    try:
        ohlcv = fetch_ohlcv(symbol, period="1y")
        if ohlcv.empty or len(ohlcv) < 220:
            return None

        feature_df = build_features(ohlcv).dropna(subset=FEATURE_COLS)
        if feature_df.empty:
            return None

        latest = feature_df.iloc[-1]
        fundamentals = fetch_fundamentals(symbol)

        # Day return from last two closes
        prev_close = float(ohlcv["close"].iloc[-2])
        current_close = float(ohlcv["close"].iloc[-1])
        day_return = ((current_close - prev_close) / prev_close) if prev_close > 0 else 0.0

        # ML prediction — only if model exists
        signal = None
        probability_up = None
        confidence = None
        model_path = os.path.join(settings.models_dir, f"{symbol}.pkl")
        if os.path.exists(model_path):
            try:
                model, scaler = load_model(model_path)
                pred = ml_predict(model, scaler, feature_df)
                signal = pred["signal"]
                probability_up = pred["probability_up"]
                confidence = pred["confidence"]
            except Exception as exc:
                logger.debug("Prediction failed for %s: %s", symbol, exc)

        # DVM scores
        dvm = compute_dvm(
            fundamentals=fundamentals,
            features=latest.to_dict(),
            atr_pct=float(latest.get("atr_pct", 0)) or None,
        )

        # Risk
        risk = compute_risk_score(
            atr_pct=float(latest.get("atr_pct", 0)) or None,
            beta=fundamentals.get("beta"),
            debt_to_equity=fundamentals.get("debt_to_equity"),
        )

        return {
            "symbol": symbol,
            "price": round(current_close, 2),
            "day_return": round(day_return, 4),
            "signal": signal,
            "probability_up": probability_up,
            "confidence": confidence,
            "risk_score": risk,
            "durability": dvm["durability"],
            "valuation": dvm["valuation"],
            "momentum": dvm["momentum"],
            "rsi": round(float(latest["rsi"]), 1) if "rsi" in latest else None,
            "pe_ratio": fundamentals.get("pe_ratio"),
            "market_cap": fundamentals.get("market_cap"),
            "sector": fundamentals.get("sector"),  # may be None — yfinance limitation
        }
    except Exception as exc:
        logger.error("Enrich failed for %s: %s", symbol, exc)
        return None


@router.get("/all")
async def screener_all():
    """
    Return enriched data for all symbols in the universe.

    Cached for 10 minutes — this triggers ~50 yfinance calls in parallel.
    """
    cached = cache.get("screener:all")
    if cached:
        return cached

    symbols = all_symbols()
    rows: list[dict] = []

    # Parallel fetch across symbols — IO-bound, threads work fine
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_enrich_symbol, sym): sym for sym in symbols}
        for fut in as_completed(futures):
            row = fut.result()
            if row:
                rows.append(row)

    rows.sort(key=lambda r: r["symbol"])
    response = {
        "rows": rows,
        "count": len(rows),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
    cache.set("screener:all", response, ttl_seconds=600)
    return response
