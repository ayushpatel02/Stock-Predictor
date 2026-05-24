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
    windows = windows or [10, 20, 30, 50, 100, 200]
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


# ---------------------------------------------------------------------------
# Stochastic Oscillator
# ---------------------------------------------------------------------------


def add_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """
    Add Stochastic %K and %D.

    Columns added:
        stoch_k   raw stochastic: (close - low_k) / (high_k - low_k) * 100
        stoch_d   signal line: SMA(d_period) of %K
    """
    df = _validate(df, ["high", "low", "close"])
    low_k = df["low"].rolling(window=k_period, min_periods=k_period).min()
    high_k = df["high"].rolling(window=k_period, min_periods=k_period).max()
    band = (high_k - low_k).replace(0, np.nan)
    df["stoch_k"] = (df["close"] - low_k) / band * 100
    df["stoch_d"] = df["stoch_k"].rolling(window=d_period, min_periods=d_period).mean()
    return df


# ---------------------------------------------------------------------------
# CCI (Commodity Channel Index)
# ---------------------------------------------------------------------------


def add_cci(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Add CCI.

    Columns added:
        cci   (typical_price - SMA_tp) / (0.015 * mean_deviation)
    """
    df = _validate(df, ["high", "low", "close"])
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(window=period, min_periods=period).mean()
    mean_dev = tp.rolling(window=period, min_periods=period).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    df["cci"] = (tp - sma_tp) / (0.015 * mean_dev.replace(0, np.nan))
    return df


# ---------------------------------------------------------------------------
# ADX (Average Directional Index)
# ---------------------------------------------------------------------------


def add_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add ADX, +DI, and -DI.

    Columns added:
        plus_di    positive directional indicator
        minus_di   negative directional indicator
        adx        average directional index (trend strength, 0-100)
    """
    df = _validate(df, ["high", "low", "close"])
    prev_high = df["high"].shift(1)
    prev_low = df["low"].shift(1)
    prev_close = df["close"].shift(1)

    plus_dm = (df["high"] - prev_high).clip(lower=0)
    minus_dm = (prev_low - df["low"]).clip(lower=0)
    # If both DMs positive, keep only the larger; zero the other
    both_pos = (plus_dm > 0) & (minus_dm > 0)
    plus_dm = plus_dm.where(~both_pos | (plus_dm >= minus_dm), other=0)
    minus_dm = minus_dm.where(~both_pos | (minus_dm > plus_dm), other=0)

    tr = pd.concat(
        [df["high"] - df["low"],
         (df["high"] - prev_close).abs(),
         (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    smooth_plus = plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    smooth_minus = minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    safe_atr = atr.replace(0, np.nan)
    df["plus_di"] = smooth_plus / safe_atr * 100
    df["minus_di"] = smooth_minus / safe_atr * 100

    di_sum = (df["plus_di"] + df["minus_di"]).replace(0, np.nan)
    dx = ((df["plus_di"] - df["minus_di"]).abs() / di_sum * 100)
    df["adx"] = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return df


# ---------------------------------------------------------------------------
# Awesome Oscillator
# ---------------------------------------------------------------------------


def add_awesome_oscillator(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add Awesome Oscillator.

    AO = SMA(5, median_price) − SMA(34, median_price)

    Columns added:
        ao   awesome oscillator
    """
    df = _validate(df, ["high", "low"])
    mp = (df["high"] + df["low"]) / 2
    df["ao"] = mp.rolling(window=5, min_periods=5).mean() - mp.rolling(window=34, min_periods=34).mean()
    return df


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------


def add_momentum(df: pd.DataFrame, period: int = 10) -> pd.DataFrame:
    """
    Add price momentum.

    Columns added:
        momentum   close - close[period] (positive = bullish)
    """
    df = _validate(df, ["close"])
    df["momentum"] = df["close"] - df["close"].shift(period)
    return df


# ---------------------------------------------------------------------------
# Stochastic RSI
# ---------------------------------------------------------------------------


def add_stochastic_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add Stochastic RSI: apply stochastic formula to RSI values.

    Requires rsi column (add_rsi must run first).

    Columns added:
        stoch_rsi   0-100
    """
    df = _validate(df, ["close"])
    if "rsi" not in df.columns:
        df = add_rsi(df, period)
    rsi = df["rsi"]
    low_rsi = rsi.rolling(window=period, min_periods=period).min()
    high_rsi = rsi.rolling(window=period, min_periods=period).max()
    band = (high_rsi - low_rsi).replace(0, np.nan)
    df["stoch_rsi"] = (rsi - low_rsi) / band * 100
    return df


# ---------------------------------------------------------------------------
# Williams %R
# ---------------------------------------------------------------------------


def add_williams_r(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add Williams %R.

    %R = (highest_high - close) / (highest_high - lowest_low) * -100
    Range: -100 to 0. <-80 = oversold (BUY signal), >-20 = overbought (SELL signal).

    Columns added:
        williams_r
    """
    df = _validate(df, ["high", "low", "close"])
    hh = df["high"].rolling(window=period, min_periods=period).max()
    ll = df["low"].rolling(window=period, min_periods=period).min()
    band = (hh - ll).replace(0, np.nan)
    df["williams_r"] = (hh - df["close"]) / band * -100
    return df


# ---------------------------------------------------------------------------
# Bull Bear Power
# ---------------------------------------------------------------------------


def add_bull_bear_power(df: pd.DataFrame, period: int = 13) -> pd.DataFrame:
    """
    Add Bull Power and Bear Power (Elder's force index variant).

    Bull Power = high - EMA(period)
    Bear Power = low - EMA(period)
    Combined: bull_power + bear_power = total market power

    Columns added:
        bull_power
        bear_power
    """
    df = _validate(df, ["high", "low", "close"])
    ema = df["close"].ewm(span=period, adjust=False, min_periods=period).mean()
    df["bull_power"] = df["high"] - ema
    df["bear_power"] = df["low"] - ema
    return df


# ---------------------------------------------------------------------------
# Ultimate Oscillator
# ---------------------------------------------------------------------------


def add_ultimate_oscillator(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add Ultimate Oscillator (Williams, periods 7/14/28).

    UO = 100 * (4*BP7/TR7 + 2*BP14/TR14 + BP28/TR28) / (4+2+1)

    Columns added:
        ultimate_osc
    """
    df = _validate(df, ["high", "low", "close"])
    prev_close = df["close"].shift(1)
    bp = df["close"] - pd.concat([df["low"], prev_close], axis=1).min(axis=1)
    tr = pd.concat(
        [df["high"] - df["low"],
         (df["high"] - prev_close).abs(),
         (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    def _avg(window):
        bp_sum = bp.rolling(window=window, min_periods=window).sum()
        tr_sum = tr.rolling(window=window, min_periods=window).sum()
        return bp_sum / tr_sum.replace(0, np.nan)

    df["ultimate_osc"] = 100 * (4 * _avg(7) + 2 * _avg(14) + _avg(28)) / 7
    return df


# ---------------------------------------------------------------------------
# Ichimoku Base Line
# ---------------------------------------------------------------------------


def add_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add Ichimoku Base Line (Kijun-sen).

    Base Line = (highest_high(26) + lowest_low(26)) / 2

    Columns added:
        ichimoku_base
    """
    df = _validate(df, ["high", "low"])
    df["ichimoku_base"] = (
        df["high"].rolling(window=26, min_periods=26).max() +
        df["low"].rolling(window=26, min_periods=26).min()
    ) / 2
    return df


# ---------------------------------------------------------------------------
# VWMA (Volume-Weighted Moving Average)
# ---------------------------------------------------------------------------


def add_vwma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Add Volume-Weighted Moving Average.

    VWMA = sum(close * volume, period) / sum(volume, period)

    Columns added:
        vwma_20
    """
    df = _validate(df, ["close", "volume"])
    cv = df["close"] * df["volume"]
    vol_sum = df["volume"].rolling(window=period, min_periods=period).sum()
    df[f"vwma_{period}"] = cv.rolling(window=period, min_periods=period).sum() / vol_sum.replace(0, np.nan)
    return df


# ---------------------------------------------------------------------------
# Hull Moving Average
# ---------------------------------------------------------------------------


def add_hull_ma(df: pd.DataFrame, period: int = 9) -> pd.DataFrame:
    """
    Add Hull Moving Average.

    HMA(n) = WMA(2*WMA(n/2) - WMA(n), sqrt(n))

    WMA approximated with EMA (close enough for signal generation).

    Columns added:
        hull_ma_9
    """
    df = _validate(df, ["close"])
    half = max(1, period // 2)
    sqrt_p = max(1, int(period ** 0.5))
    wma_half = df["close"].ewm(span=half, adjust=False, min_periods=half).mean()
    wma_full = df["close"].ewm(span=period, adjust=False, min_periods=period).mean()
    raw = 2 * wma_half - wma_full
    df[f"hull_ma_{period}"] = raw.ewm(span=sqrt_p, adjust=False, min_periods=sqrt_p).mean()
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
    # Extended indicators (used for technicals display, not ML features)
    df = add_stochastic(df)
    df = add_cci(df)
    df = add_adx(df)
    df = add_awesome_oscillator(df)
    df = add_momentum(df)
    df = add_stochastic_rsi(df)
    df = add_williams_r(df)
    df = add_bull_bear_power(df)
    df = add_ultimate_oscillator(df)
    df = add_ichimoku(df)
    df = add_vwma(df)
    df = add_hull_ma(df)
    return df
