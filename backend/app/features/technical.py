"""
Pure-Python technical indicator calculations using pandas/numpy only.
No TA-Lib or C-extension dependencies — runs on any cloud platform.

Convention: every `add_*` function takes an OHLCV DataFrame and returns it
with new columns appended in-place (copy returned). Input columns expected:
open, high, low, close, volume (lowercase).

NOTE ON LEAKAGE: All indicators use only past data (no lookahead).
Rolling/EMA windows only look backward. This is enforced by pandas default
(min_periods respected, no center=True).
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _validate(df: pd.DataFrame, required: list[str] = None) -> pd.DataFrame:
    """Return a copy of df; raise ValueError if required columns are missing."""
    required = required or ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")
    return df.copy()


# ---------------------------------------------------------------------------
# Moving averages
# ---------------------------------------------------------------------------


def add_moving_averages(df: pd.DataFrame, windows: list[int] = None) -> pd.DataFrame:
    """
    Add SMA and EMA for each window, plus two binary signals.

    Columns added:
        sma_{w}, ema_{w}  for each w in windows
        sma_20_above_50   1 if SMA-20 > SMA-50 (short-term bullish structure)
        golden_cross      1 if SMA-50 > SMA-200 (long-term trend signal)
    """
    windows = windows or [20, 50, 200]
    df = _validate(df)

    for w in windows:
        df[f"sma_{w}"] = df["close"].rolling(window=w, min_periods=w).mean()
        df[f"ema_{w}"] = df["close"].ewm(span=w, adjust=False, min_periods=w).mean()

    if 20 in windows and 50 in windows:
        df["sma_20_above_50"] = (df["sma_20"] > df["sma_50"]).astype(int)

    if 50 in windows and 200 in windows:
        df["golden_cross"] = (df["sma_50"] > df["sma_200"]).astype(int)

    return df


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI formula.
    Uses Exponential Moving Average (Wilder's smoothing = 1/period alpha).
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder smoothing: equivalent to EWM with alpha=1/period, adjust=False
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    # Replace 0 with tiny epsilon: avg_loss=0 means all-up moves → RS→∞ → RSI=100.
    # Using a tiny divisor instead of NaN preserves correct RSI=100 for pure bull runs
    # while still propagating NaN from the min_periods warm-up period.
    safe_loss = avg_loss.where(avg_loss != 0, other=1e-10)
    rs = avg_gain / safe_loss
    rsi = 100 - (100 / (1 + rs))
    # Re-mask rows that were NaN before (min_periods not yet met)
    rsi = rsi.where(avg_gain.notna())
    return rsi


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add RSI and overbought/oversold flags.

    Columns added:
        rsi             14-period Wilder's RSI
        rsi_oversold    1 if RSI < 30
        rsi_overbought  1 if RSI > 70
    """
    df = _validate(df, ["close"])
    df["rsi"] = _rsi(df["close"], period)
    df["rsi_oversold"] = (df["rsi"] < 30).astype(int)
    df["rsi_overbought"] = (df["rsi"] > 70).astype(int)
    return df


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """
    Add MACD line, signal line, histogram, and bullish crossover flag.

    Columns added:
        macd              fast EMA − slow EMA
        macd_signal       9-period EMA of MACD line
        macd_hist         MACD − signal (momentum)
        macd_bullish_cross  1 when MACD crosses above signal (current bar only)
    """
    df = _validate(df, ["close"])
    ema_fast = df["close"].ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False, min_periods=slow).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False, min_periods=signal).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Cross: MACD was below signal yesterday, above today
    macd_above = df["macd"] > df["macd_signal"]
    prev_above = macd_above.shift(1).infer_objects(copy=False).fillna(False)
    df["macd_bullish_cross"] = (macd_above & ~prev_above).astype(int)
    return df


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------


def add_bollinger(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
) -> pd.DataFrame:
    """
    Add Bollinger Bands.

    Columns added:
        bb_middle    SMA-20
        bb_upper     SMA + 2*std
        bb_lower     SMA − 2*std
        bb_width     (upper − lower) / middle  → volatility proxy
        bb_pct       (close − lower) / (upper − lower) → position in band [0,1]
    """
    df = _validate(df, ["close"])
    sma = df["close"].rolling(window=period, min_periods=period).mean()
    std = df["close"].rolling(window=period, min_periods=period).std()
    df["bb_middle"] = sma
    df["bb_upper"] = sma + std_dev * std
    df["bb_lower"] = sma - std_dev * std
    band_width = df["bb_upper"] - df["bb_lower"]
    df["bb_width"] = band_width / sma.replace(0, np.nan)
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / band_width.replace(0, np.nan)
    return df


# ---------------------------------------------------------------------------
# ATR (Average True Range)
# ---------------------------------------------------------------------------


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add ATR and ATR as a percentage of close price.

    ATR = Wilder-smoothed average of True Range.
    atr_pct makes ATR comparable across stocks of different price levels.

    Columns added:
        atr      average true range
        atr_pct  atr / close
    """
    df = _validate(df, ["high", "low", "close"])
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    df["atr"] = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    df["atr_pct"] = df["atr"] / df["close"].replace(0, np.nan)
    return df


# ---------------------------------------------------------------------------
# Volume features
# ---------------------------------------------------------------------------


def add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add volume-based indicators.

    Columns added:
        volume_ma20    20-day volume moving average
        volume_ratio   close-volume / 20d MA (>1 = above-average activity)
        obv            on-balance volume (running sum gated by price direction)
        obv_ema        21-day EMA of OBV (trend in volume flow)
    """
    df = _validate(df, ["close", "volume"])
    df["volume_ma20"] = df["volume"].rolling(window=20, min_periods=20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma20"].replace(0, np.nan)

    # OBV: cumulative volume with sign flipped by price direction
    direction = np.sign(df["close"].diff()).fillna(0)
    df["obv"] = (direction * df["volume"]).cumsum()
    df["obv_ema"] = df["obv"].ewm(span=21, adjust=False, min_periods=21).mean()
    return df


# ---------------------------------------------------------------------------
# Return and volatility features
# ---------------------------------------------------------------------------


def add_returns(df: pd.DataFrame, periods: list[int] = None) -> pd.DataFrame:
    """
    Add past log-returns and rolling volatility.

    Columns added (for each p in periods):
        return_{p}d   log return over last p trading days
        vol_{p}d      rolling std of daily log returns over p days (annualised)
    """
    periods = periods or [1, 5, 20]
    df = _validate(df, ["close"])
    log_ret = np.log(df["close"] / df["close"].shift(1))

    for p in periods:
        df[f"return_{p}d"] = df["close"].pct_change(p)
        df[f"vol_{p}d"] = log_ret.rolling(window=p, min_periods=p).std() * np.sqrt(252)

    return df


# ---------------------------------------------------------------------------
# Composite pipeline
# ---------------------------------------------------------------------------


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    One-shot pipeline: apply all technical indicators to a raw OHLCV DataFrame.

    Returns DataFrame with all feature columns added.
    Rows at the beginning will have NaN for long-window indicators (e.g. SMA-200);
    callers should dropna() before training.
    """
    df = add_moving_averages(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger(df)
    df = add_atr(df)
    df = add_volume_features(df)
    df = add_returns(df)
    return df
