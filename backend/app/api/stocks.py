"""
Stock data and prediction endpoints.

/stocks/{symbol}           — fundamentals + recent OHLCV
/stocks/{symbol}/predict   — BUY/HOLD/SELL signal with probability + risk score
"""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.data import cache
from app.data.fetchers import fetch_fundamentals, fetch_ohlcv
from app.data.universe import is_valid_symbol
from app.features.technical import build_features
from app.models.ml_model import FEATURE_COLS, load_model, predict as ml_predict
from app.models.risk_score import compute_risk_score

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stocks", tags=["stocks"])


def _symbol_or_404(symbol: str) -> str:
    sym = symbol.upper()
    if not is_valid_symbol(sym):
        raise HTTPException(status_code=404, detail=f"{sym} is not in the supported universe")
    return sym


@router.get("/{symbol}")
async def get_stock(symbol: str):
    """
    Return fundamentals and the last 30 days of OHLCV for a symbol.
    OHLCV is returned as a list of {date, open, high, low, close, volume} dicts.
    """
    sym = _symbol_or_404(symbol)
    cache_key = f"stock:{sym}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    fundamentals = fetch_fundamentals(sym)
    ohlcv_df = fetch_ohlcv(sym, period="1mo")
    if ohlcv_df.empty:
        ohlcv = []
    else:
        ohlcv = [
            {
                "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]),
            }
            for idx, row in ohlcv_df.iterrows()
        ]

    result = {"symbol": sym, "fundamentals": fundamentals, "ohlcv": ohlcv}
    cache.set(cache_key, result, ttl_seconds=900)  # 15 min cache
    return result


@router.get("/{symbol}/predict")
async def predict_stock(symbol: str):
    """
    Return a BUY/HOLD/SELL prediction for a symbol.

    Loads the pre-trained model from disk, fetches recent OHLCV, builds
    features, and runs inference. Returns:
        signal, probability_up, confidence, risk_score (1-10), as_of timestamp.

    Returns 404 if:
        - Symbol not in the supported universe.
        - No trained model exists for this symbol (run train_all.py first).
    """
    sym = _symbol_or_404(symbol)
    cache_key = f"predict:{sym}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    model_path = os.path.join(settings.models_dir, f"{sym}.pkl")
    try:
        model, scaler = load_model(model_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No trained model for {sym}. Run `python -m app.scripts.train_all` first.",
        )

    # Fetch 1 year of data to ensure long-window indicators (SMA-200) can compute
    ohlcv_df = fetch_ohlcv(sym, period="1y")
    if ohlcv_df.empty or len(ohlcv_df) < 220:
        raise HTTPException(status_code=503, detail=f"Insufficient data for {sym}")

    try:
        feature_df = build_features(ohlcv_df)
        feature_df = feature_df.dropna(subset=FEATURE_COLS)
        if feature_df.empty:
            raise ValueError("All feature rows contain NaN after build_features")
        prediction = ml_predict(model, scaler, feature_df)
    except Exception as exc:
        logger.error("Prediction failed for %s: %s", sym, exc)
        raise HTTPException(status_code=500, detail=f"Prediction error: {exc}") from exc

    # Risk score from latest ATR%, beta, and D/E
    fundamentals = fetch_fundamentals(sym)
    latest_atr_pct = float(feature_df["atr_pct"].iloc[-1]) if "atr_pct" in feature_df.columns else None
    risk_score = compute_risk_score(
        atr_pct=latest_atr_pct,
        beta=fundamentals.get("beta"),
        debt_to_equity=fundamentals.get("debt_to_equity"),
    )

    result = {
        "symbol": sym,
        **prediction,
        "risk_score": risk_score,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "This is not financial advice. Predictions are probabilistic.",
    }
    cache.set(cache_key, result, ttl_seconds=900)
    return result
