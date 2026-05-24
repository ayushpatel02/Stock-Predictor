"""
Stock data and prediction endpoints.

/stocks/{symbol}            — fundamentals + recent OHLCV
/stocks/{symbol}/predict    — BUY/HOLD/SELL signal with probability + risk score
/stocks/{symbol}/dvm        — Trendlyne-style Durability/Valuation/Momentum scores
/stocks/{symbol}/news       — Recent news headlines + sentiment
/stocks/{symbol}/peers      — Peer comparison (other large-caps from universe)
"""
from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.data import cache
from app.data.fetchers import fetch_analyst_data, fetch_fundamentals, fetch_ohlcv
from app.data.news import aggregate_sentiment, fetch_news
from app.data.universe import all_symbols, is_valid_symbol
from app.features.technical import build_features
from app.models.dvm import compute_dvm
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


@router.get("/{symbol}/dvm")
async def get_dvm(symbol: str):
    """
    Return DVM (Durability/Valuation/Momentum) scores for a symbol.

    Each score is 0-100 (higher = better). Includes a breakdown of the
    sub-scores so users can see *why* a stock scores the way it does.
    """
    sym = _symbol_or_404(symbol)
    cache_key = f"dvm:{sym}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ohlcv = fetch_ohlcv(sym, period="1y")
    if ohlcv.empty or len(ohlcv) < 220:
        raise HTTPException(status_code=503, detail=f"Insufficient data for {sym}")

    feature_df = build_features(ohlcv).dropna(subset=FEATURE_COLS)
    if feature_df.empty:
        raise HTTPException(status_code=503, detail=f"Could not build features for {sym}")

    latest = feature_df.iloc[-1].to_dict()
    fundamentals = fetch_fundamentals(sym)
    dvm = compute_dvm(
        fundamentals=fundamentals,
        features=latest,
        atr_pct=float(feature_df["atr_pct"].iloc[-1]) if "atr_pct" in feature_df.columns else None,
    )

    result = {"symbol": sym, **dvm, "as_of": datetime.now(timezone.utc).isoformat()}
    cache.set(cache_key, result, ttl_seconds=900)
    return result


@router.get("/{symbol}/news")
async def get_news(symbol: str, limit: int = 10):
    """
    Return latest news headlines for a symbol with simple keyword sentiment.

    Primary source: yfinance (free). Fallback: Finnhub (if FINNHUB_API_KEY set).
    """
    sym = _symbol_or_404(symbol)
    cache_key = f"news:{sym}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    items = fetch_news(sym, limit=limit)
    aggregate = aggregate_sentiment(items)

    result = {
        "symbol": sym,
        "items": items,
        "aggregate": aggregate,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
    cache.set(cache_key, result, ttl_seconds=600)  # 10 min — news is fresh
    return result


@router.get("/{symbol}/peers")
async def get_peers(symbol: str, n: int = 5):
    """
    Return a list of peer symbols (other Nifty 50 stocks) for comparison.

    Peer selection logic: same sector if known, else top-N by similar market cap.
    Since yfinance .info doesn't reliably return sector for Indian stocks, we
    use market-cap proximity as the primary signal here. Tune for production.
    """
    sym = _symbol_or_404(symbol)
    cache_key = f"peers:{sym}:{n}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    target = fetch_fundamentals(sym)
    target_cap = target.get("market_cap") or 0
    universe = [s for s in all_symbols() if s != sym]

    candidates: list[tuple[str, float]] = []
    for peer in universe:
        try:
            peer_fund = fetch_fundamentals(peer)
            peer_cap = peer_fund.get("market_cap") or 0
            if peer_cap > 0 and target_cap > 0:
                # Smaller log-ratio = more similar in market cap
                log_diff = abs((peer_cap / target_cap) - 1)
                candidates.append((peer, log_diff))
        except Exception:
            continue

    candidates.sort(key=lambda x: x[1])
    chosen = [c[0] for c in candidates[:n]] if candidates else random.sample(universe, n)

    # Return rich peer rows
    peers_data = []
    for peer in chosen:
        peer_ohlcv = fetch_ohlcv(peer, period="3mo")
        if peer_ohlcv.empty:
            continue
        peer_fund = fetch_fundamentals(peer)
        last_price = float(peer_ohlcv["close"].iloc[-1])
        prev_price = float(peer_ohlcv["close"].iloc[-2]) if len(peer_ohlcv) > 1 else last_price
        peers_data.append({
            "symbol": peer,
            "price": round(last_price, 2),
            "day_return": round((last_price - prev_price) / prev_price, 4) if prev_price else 0,
            "pe_ratio": peer_fund.get("pe_ratio"),
            "market_cap": peer_fund.get("market_cap"),
        })

    result = {"symbol": sym, "peers": peers_data, "as_of": datetime.now(timezone.utc).isoformat()}
    cache.set(cache_key, result, ttl_seconds=1800)  # 30 min
    return result


# ---------------------------------------------------------------------------
# Signal classification helpers for the technicals endpoint
# ---------------------------------------------------------------------------

def _osc_signal(name: str, latest: dict) -> dict:
    """Return {name, value, action} for a single oscillator."""
    def _v(col: str):
        v = latest.get(col)
        if v is None or (isinstance(v, float) and (v != v)):
            return None
        return float(v)

    if name == "RSI(14)":
        v = _v("rsi")
        action = "BUY" if v is not None and v < 30 else "SELL" if v is not None and v > 70 else "NEUTRAL"
        return {"name": name, "value": round(v, 2) if v is not None else None, "action": action}

    if name == "Stochastic %K(14,3,3)":
        v = _v("stoch_k")
        action = "BUY" if v is not None and v < 20 else "SELL" if v is not None and v > 80 else "NEUTRAL"
        return {"name": name, "value": round(v, 2) if v is not None else None, "action": action}

    if name == "CCI(20)":
        v = _v("cci")
        action = "BUY" if v is not None and v < -100 else "SELL" if v is not None and v > 100 else "NEUTRAL"
        return {"name": name, "value": round(v, 2) if v is not None else None, "action": action}

    if name == "ADX(14)":
        adx = _v("adx")
        pdi = _v("plus_di")
        mdi = _v("minus_di")
        if adx is not None and adx > 25:
            action = "BUY" if pdi is not None and mdi is not None and pdi > mdi else "SELL"
        else:
            action = "NEUTRAL"
        return {"name": name, "value": round(adx, 2) if adx is not None else None, "action": action}

    if name == "Awesome Oscillator":
        v = _v("ao")
        action = "BUY" if v is not None and v > 0 else "SELL" if v is not None and v < 0 else "NEUTRAL"
        return {"name": name, "value": round(v, 2) if v is not None else None, "action": action}

    if name == "Momentum(10)":
        v = _v("momentum")
        action = "BUY" if v is not None and v > 0 else "SELL" if v is not None and v < 0 else "NEUTRAL"
        return {"name": name, "value": round(v, 2) if v is not None else None, "action": action}

    if name == "MACD(12,26)":
        macd = _v("macd")
        sig = _v("macd_signal")
        if macd is not None and sig is not None:
            action = "BUY" if macd > sig else "SELL"
        else:
            action = "NEUTRAL"
        return {"name": name, "value": round(macd, 4) if macd is not None else None, "action": action}

    if name == "Stochastic RSI(14)":
        v = _v("stoch_rsi")
        action = "BUY" if v is not None and v < 20 else "SELL" if v is not None and v > 80 else "NEUTRAL"
        return {"name": name, "value": round(v, 2) if v is not None else None, "action": action}

    if name == "Williams %R(14)":
        v = _v("williams_r")
        action = "BUY" if v is not None and v < -80 else "SELL" if v is not None and v > -20 else "NEUTRAL"
        return {"name": name, "value": round(v, 2) if v is not None else None, "action": action}

    if name == "Bull Bear Power":
        bull = _v("bull_power")
        bear = _v("bear_power")
        combined = (bull or 0) + (bear or 0) if (bull is not None and bear is not None) else None
        action = "BUY" if combined is not None and combined > 0 else "SELL" if combined is not None and combined < 0 else "NEUTRAL"
        return {"name": name, "value": round(combined, 2) if combined is not None else None, "action": action}

    if name == "Ultimate Oscillator(7,14,28)":
        v = _v("ultimate_osc")
        action = "BUY" if v is not None and v < 30 else "SELL" if v is not None and v > 70 else "NEUTRAL"
        return {"name": name, "value": round(v, 2) if v is not None else None, "action": action}

    return {"name": name, "value": None, "action": "NEUTRAL"}


def _ma_signal(ma_name: str, ma_col: str, close: float, latest: dict) -> dict:
    v = latest.get(ma_col)
    if v is None or (isinstance(v, float) and v != v):
        return {"name": ma_name, "value": None, "action": "NEUTRAL"}
    v = float(v)
    action = "BUY" if close > v else "SELL"
    return {"name": ma_name, "value": round(v, 2), "action": action}


def _summary_rec(buy: int, sell: int, total: int) -> str:
    if total == 0:
        return "NEUTRAL"
    buy_pct = buy / total
    sell_pct = sell / total
    if buy_pct >= 0.67:
        return "STRONG BUY"
    if sell_pct >= 0.67:
        return "STRONG SELL"
    if buy > sell + total * 0.10:
        return "BUY"
    if sell > buy + total * 0.10:
        return "SELL"
    return "NEUTRAL"


@router.get("/{symbol}/technicals")
async def get_technicals(symbol: str):
    """
    Return TradingView-style technical analysis: oscillators + moving averages + summary.

    All values computed from OHLCV data using pure-Python indicators.
    """
    sym = _symbol_or_404(symbol)
    cache_key = f"technicals:{sym}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ohlcv_df = fetch_ohlcv(sym, period="1y")
    if ohlcv_df.empty or len(ohlcv_df) < 50:
        raise HTTPException(status_code=503, detail=f"Insufficient data for {sym}")

    feature_df = build_features(ohlcv_df)
    latest = feature_df.iloc[-1].to_dict()
    close = float(ohlcv_df["close"].iloc[-1])

    # Oscillators
    osc_names = [
        "RSI(14)", "Stochastic %K(14,3,3)", "CCI(20)", "ADX(14)",
        "Awesome Oscillator", "Momentum(10)", "MACD(12,26)",
        "Stochastic RSI(14)", "Williams %R(14)", "Bull Bear Power",
        "Ultimate Oscillator(7,14,28)",
    ]
    oscillators = [_osc_signal(n, latest) for n in osc_names]
    osc_buy = sum(1 for o in oscillators if o["action"] == "BUY")
    osc_sell = sum(1 for o in oscillators if o["action"] == "SELL")
    osc_neutral = sum(1 for o in oscillators if o["action"] == "NEUTRAL")

    # Moving averages
    ma_defs = [
        ("SMA(10)", "sma_10"), ("EMA(10)", "ema_10"),
        ("SMA(20)", "sma_20"), ("EMA(20)", "ema_20"),
        ("SMA(30)", "sma_30"), ("EMA(30)", "ema_30"),
        ("SMA(50)", "sma_50"), ("EMA(50)", "ema_50"),
        ("SMA(100)", "sma_100"), ("EMA(100)", "ema_100"),
        ("SMA(200)", "sma_200"), ("EMA(200)", "ema_200"),
        ("Ichimoku Base(26)", "ichimoku_base"),
        ("VWMA(20)", "vwma_20"),
        ("Hull MA(9)", "hull_ma_9"),
    ]
    moving_averages = [_ma_signal(name, col, close, latest) for name, col in ma_defs]
    ma_buy = sum(1 for m in moving_averages if m["action"] == "BUY")
    ma_sell = sum(1 for m in moving_averages if m["action"] == "SELL")
    ma_neutral = sum(1 for m in moving_averages if m["action"] == "NEUTRAL")

    total_buy = osc_buy + ma_buy
    total_sell = osc_sell + ma_sell
    total_neutral = osc_neutral + ma_neutral
    total = total_buy + total_sell + total_neutral

    result = {
        "symbol": sym,
        "oscillators": {
            "summary": {
                "buy": osc_buy, "sell": osc_sell, "neutral": osc_neutral,
                "recommendation": _summary_rec(osc_buy, osc_sell, len(oscillators)),
            },
            "indicators": oscillators,
        },
        "moving_averages": {
            "summary": {
                "buy": ma_buy, "sell": ma_sell, "neutral": ma_neutral,
                "recommendation": _summary_rec(ma_buy, ma_sell, len(moving_averages)),
            },
            "indicators": moving_averages,
        },
        "summary": {
            "buy": total_buy, "sell": total_sell, "neutral": total_neutral,
            "total": total,
            "recommendation": _summary_rec(total_buy, total_sell, total),
        },
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
    cache.set(cache_key, result, ttl_seconds=900)
    return result


@router.get("/{symbol}/overview")
async def get_overview(symbol: str):
    """
    Return Trendlyne-style company overview: price analysis, PE history,
    revenue/EPS forecasts, and analyst consensus recommendations.
    """
    sym = _symbol_or_404(symbol)
    cache_key = f"overview:{sym}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    fundamentals = fetch_fundamentals(sym)
    ohlcv_df = fetch_ohlcv(sym, period="1y")
    analyst = fetch_analyst_data(sym)

    # Price analysis
    price_analysis = None
    if not ohlcv_df.empty:
        last_close = float(ohlcv_df["close"].iloc[-1])
        prev_close = float(ohlcv_df["close"].iloc[-2]) if len(ohlcv_df) > 1 else last_close
        day_change = last_close - prev_close
        day_change_pct = day_change / prev_close if prev_close else 0
        price_analysis = {
            "current_price": round(last_close, 2),
            "day_change": round(day_change, 2),
            "day_change_pct": round(day_change_pct, 4),
            "week_52_high": fundamentals.get("week_52_high"),
            "week_52_low": fundamentals.get("week_52_low"),
            "market_cap": fundamentals.get("market_cap"),
            "pe_ratio": fundamentals.get("pe_ratio"),
            "eps": fundamentals.get("eps"),
            "book_value": fundamentals.get("book_value"),
            "dividend_yield": fundamentals.get("dividend_yield"),
            "beta": fundamentals.get("beta"),
            "price_to_book": fundamentals.get("price_to_book"),
            "profit_margins": fundamentals.get("profit_margins"),
            "revenue_growth": fundamentals.get("revenue_growth"),
            "roe": fundamentals.get("roe"),
        }

    # PE history: approximate daily PE from OHLCV + trailing EPS
    pe_history = []
    eps = fundamentals.get("eps")
    if not ohlcv_df.empty and eps and eps > 0:
        for idx, row in ohlcv_df.iterrows():
            date_str = str(idx.date()) if hasattr(idx, "date") else str(idx)
            pe_val = round(float(row["close"]) / eps, 2)
            pe_history.append({"date": date_str, "close": round(float(row["close"]), 2), "pe": pe_val})

    # Consensus — add total + recommendation label
    consensus = analyst.get("consensus")
    if consensus:
        total_analysts = sum(consensus.values())
        consensus["total"] = total_analysts
        # Determine text recommendation
        sb = consensus.get("strong_buy", 0)
        b = consensus.get("buy", 0)
        h = consensus.get("hold", 0)
        s = consensus.get("sell", 0)
        ss = consensus.get("strong_sell", 0)
        if total_analysts:
            buy_pct = (sb + b) / total_analysts
            sell_pct = (s + ss) / total_analysts
            if sb / max(total_analysts, 1) >= 0.5:
                rec_label = "Strong Buy"
            elif buy_pct >= 0.6:
                rec_label = "Buy"
            elif sell_pct >= 0.6:
                rec_label = "Sell"
            elif (h / max(total_analysts, 1)) >= 0.5:
                rec_label = "Hold"
            else:
                rec_label = "Neutral"
            consensus["recommendation"] = rec_label
        if analyst.get("target_prices"):
            consensus.update(analyst["target_prices"])

    result = {
        "symbol": sym,
        "price_analysis": price_analysis,
        "pe_history": pe_history,
        "revenue_forecast": {
            "actuals": analyst.get("revenue_actuals", []),
            "estimates": analyst.get("revenue_estimates", []),
        },
        "eps_forecast": {
            "actuals": analyst.get("eps_actuals", []),
            "estimates": analyst.get("eps_estimates", []),
        },
        "consensus": consensus,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
    cache.set(cache_key, result, ttl_seconds=1800)
    return result
