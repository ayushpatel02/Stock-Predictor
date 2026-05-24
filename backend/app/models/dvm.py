"""
DVM Score: Durability, Valuation, Momentum — Trendlyne-inspired stock scoring.

Each score is 0-100, where higher is better. The three scores together give
a quick view of stock quality without needing the user to read raw metrics.

Scoring is intentionally simple and transparent — every input feature maps
to a sub-score via fixed thresholds, then weighted-averaged. Tune the weights
or thresholds per sector in production (current thresholds suit large-caps).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _bucket_score(value: float, thresholds: list[float], invert: bool = False) -> float:
    """
    Map a value to a 0-100 score using threshold buckets.

    `thresholds` defines 10 equal bands from worst to best.
    If `invert=True`, lower values are better (e.g. P/E, D/E).
    """
    n = len(thresholds)
    score = 100.0
    for i, t in enumerate(thresholds):
        if invert:
            if value > t:
                score = 100.0 * (n - i - 1) / n
                break
        else:
            if value < t:
                score = 100.0 * i / n
                break
    return max(0.0, min(100.0, score))


# Threshold tables — derived from Nifty 50 typical ranges.
# Format: 10 cutoff values from "worst" to "best" so 11 bands of 10 points each.

# Durability inputs (all "higher is better" except where noted)
_DE_THRESHOLDS = [10, 30, 50, 80, 100, 150, 200, 300, 500, 1000]  # invert=True
_PROFIT_MARGIN_THRESHOLDS = [-0.1, 0, 0.03, 0.06, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
_ROE_THRESHOLDS = [-0.05, 0, 0.05, 0.08, 0.12, 0.15, 0.18, 0.22, 0.28, 0.35]
_ATR_PCT_THRESHOLDS = [0.008, 0.012, 0.016, 0.020, 0.025, 0.030, 0.040, 0.050, 0.065, 0.080]  # invert

# Valuation inputs
_PE_THRESHOLDS = [10, 15, 20, 25, 30, 40, 50, 70, 100, 150]   # invert=True
_PB_THRESHOLDS = [1, 2, 3, 4, 5, 7, 10, 15, 20, 30]            # invert=True
_DIV_YIELD_THRESHOLDS = [0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.07]

# Momentum inputs
_RETURN_THRESHOLDS = [-0.10, -0.05, -0.02, 0, 0.02, 0.05, 0.08, 0.12, 0.18, 0.25]


def _safe(value: object) -> float | None:
    """Coerce value to float if finite, else None."""
    if value is None:
        return None
    try:
        v = float(value)
        if v != v or v in (float("inf"), float("-inf")):  # NaN/inf check
            return None
        return v
    except (TypeError, ValueError):
        return None


def durability_score(fundamentals: dict, atr_pct: float | None) -> tuple[float, dict]:
    """
    Durability: how stable / financially sound is the business.

    Inputs (weights):
        Debt/Equity   30% (lower = better)
        Profit margin 25%
        ROE           25%
        ATR%          20% (lower volatility = more durable)
    """
    de = _safe(fundamentals.get("debt_to_equity"))
    pm = _safe(fundamentals.get("profit_margins"))
    roe = _safe(fundamentals.get("roe"))
    atr = _safe(atr_pct)

    parts = {
        "debt_to_equity": _bucket_score(de, _DE_THRESHOLDS, invert=True) if de is not None else 50,
        "profit_margin": _bucket_score(pm, _PROFIT_MARGIN_THRESHOLDS) if pm is not None else 50,
        "roe": _bucket_score(roe, _ROE_THRESHOLDS) if roe is not None else 50,
        "atr_pct": _bucket_score(atr, _ATR_PCT_THRESHOLDS, invert=True) if atr is not None else 50,
    }
    weighted = 0.30 * parts["debt_to_equity"] + 0.25 * parts["profit_margin"] + \
               0.25 * parts["roe"] + 0.20 * parts["atr_pct"]
    return round(weighted, 1), parts


def valuation_score(fundamentals: dict) -> tuple[float, dict]:
    """
    Valuation: is the stock cheap, fair, or expensive on classic metrics.

    Inputs (weights):
        P/E ratio        40% (lower = better)
        P/B ratio        30% (lower = better)
        Dividend yield   30% (higher = better)
    """
    pe = _safe(fundamentals.get("pe_ratio"))
    pb = _safe(fundamentals.get("price_to_book"))
    dy = _safe(fundamentals.get("dividend_yield"))

    parts = {
        "pe_ratio": _bucket_score(pe, _PE_THRESHOLDS, invert=True) if pe is not None else 50,
        "price_to_book": _bucket_score(pb, _PB_THRESHOLDS, invert=True) if pb is not None else 50,
        "dividend_yield": _bucket_score(dy, _DIV_YIELD_THRESHOLDS) if dy is not None else 50,
    }
    weighted = 0.40 * parts["pe_ratio"] + 0.30 * parts["price_to_book"] + \
               0.30 * parts["dividend_yield"]
    return round(weighted, 1), parts


def momentum_score(features: dict) -> tuple[float, dict]:
    """
    Momentum: is the stock trending up with conviction.

    Inputs (weights):
        20-day return   30%
        5-day return    15%
        RSI sweet-spot  20% (60-70 = strong, but >80 punished)
        MACD bullish    15%
        Volume ratio    10%
        Above SMA-50    10%
    """
    ret_20 = _safe(features.get("return_20d"))
    ret_5 = _safe(features.get("return_5d"))
    rsi = _safe(features.get("rsi"))
    macd_hist = _safe(features.get("macd_hist"))
    vol_ratio = _safe(features.get("volume_ratio"))
    above_sma50 = _safe(features.get("sma_20_above_50"))

    # RSI sweet spot: 60-70 = 100, 50 = 70, 30 = 40, 80+ = 50 (overbought punished)
    def _rsi_score(r: float | None) -> float:
        if r is None:
            return 50
        if r > 80:
            return 50
        if r >= 60:
            return 100
        if r >= 50:
            return 70 + (r - 50) * 3
        if r >= 30:
            return 40 + (r - 30) * 1.5
        return max(10, r * 1.3)

    parts = {
        "return_20d": _bucket_score(ret_20, _RETURN_THRESHOLDS) if ret_20 is not None else 50,
        "return_5d": _bucket_score(ret_5, _RETURN_THRESHOLDS) if ret_5 is not None else 50,
        "rsi": _rsi_score(rsi),
        "macd_hist": (100 if macd_hist is not None and macd_hist > 0 else
                      0 if macd_hist is not None else 50),
        "volume_ratio": (min(100, max(0, (vol_ratio - 0.5) * 100)) if vol_ratio is not None else 50),
        "above_sma50": 100 if above_sma50 == 1 else 0 if above_sma50 == 0 else 50,
    }
    weighted = (0.30 * parts["return_20d"] + 0.15 * parts["return_5d"] +
                0.20 * parts["rsi"] + 0.15 * parts["macd_hist"] +
                0.10 * parts["volume_ratio"] + 0.10 * parts["above_sma50"])
    return round(weighted, 1), parts


def compute_dvm(fundamentals: dict, features: dict, atr_pct: float | None) -> dict:
    """
    Compute all three DVM scores in one call.

    Returns:
        {durability, valuation, momentum, dvm_breakdown}
        Each main score is a float 0-100; breakdown is the sub-score map.
    """
    d, d_parts = durability_score(fundamentals, atr_pct)
    v, v_parts = valuation_score(fundamentals)
    m, m_parts = momentum_score(features)
    return {
        "durability": d,
        "valuation": v,
        "momentum": m,
        "dvm_breakdown": {
            "durability": d_parts,
            "valuation": v_parts,
            "momentum": m_parts,
        },
    }
