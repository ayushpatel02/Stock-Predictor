"""
Layer 1: Rule-based signal generator.
Produces a pre-ML signal from classic technical rules.
Used as a sanity check and as an additional feature input to the ML model.
Not intended to be the sole decision signal — use ml_model.py for final signals.
"""

import pandas as pd


def rule_based_signal(df: pd.DataFrame) -> dict[str, object]:
    """
    Compute a rule-based BUY/HOLD/SELL signal from the latest feature row.

    Scoring rubric (each rule adds to a bull_score 0-6):
        +1  RSI < 40 (not overbought)
        +1  MACD > MACD signal (momentum positive)
        +1  Close > SMA-50 (above medium-term trend)
        +1  Close > SMA-200 (above long-term trend)
        +1  BB%  < 0.8 (not at upper band extreme)
        +1  Volume ratio > 1.0 (above-average volume = conviction)

    Signal mapping: bull_score >= 4 → BUY, <= 2 → SELL, else HOLD.

    Args:
        df: Feature DataFrame produced by build_features(); uses the last row.

    Returns:
        dict with keys: signal, bull_score, reasons
    """
    if df.empty:
        return {"signal": "HOLD", "bull_score": 3, "reasons": ["no data"]}

    row = df.iloc[-1]
    score = 0
    reasons: list[str] = []

    def _safe(col: str, default=None):
        v = row.get(col, default)
        if v is None or (hasattr(v, "__float__") and not __import__("math").isfinite(float(v))):
            return default
        return v

    rsi = _safe("rsi")
    if rsi is not None and rsi < 40:
        score += 1
        reasons.append(f"RSI={rsi:.1f} not overbought")

    macd = _safe("macd")
    macd_sig = _safe("macd_signal")
    if macd is not None and macd_sig is not None and macd > macd_sig:
        score += 1
        reasons.append("MACD above signal")

    close = _safe("close", row.get("close"))
    sma50 = _safe("sma_50")
    if close and sma50 and close > sma50:
        score += 1
        reasons.append("Price above SMA-50")

    sma200 = _safe("sma_200")
    if close and sma200 and close > sma200:
        score += 1
        reasons.append("Price above SMA-200")

    bb_pct = _safe("bb_pct")
    if bb_pct is not None and bb_pct < 0.8:
        score += 1
        reasons.append(f"BB%={bb_pct:.2f} not at upper extreme")

    vol_ratio = _safe("volume_ratio")
    if vol_ratio is not None and vol_ratio > 1.0:
        score += 1
        reasons.append(f"Volume ratio={vol_ratio:.2f} above average")

    if score >= 4:
        signal = "BUY"
    elif score <= 2:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {"signal": signal, "bull_score": score, "reasons": reasons}
