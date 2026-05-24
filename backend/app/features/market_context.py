"""
Market-context features derived from index data (Nifty 50, VIX, etc.).
These features capture the macro regime and are appended to per-stock feature rows.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.data.fetchers import fetch_ohlcv

logger = logging.getLogger(__name__)


def fetch_nifty_features(period: str = "2y") -> pd.DataFrame:
    """
    Fetch Nifty 50 index OHLCV and compute context features used in the ML model.

    Returns a DataFrame indexed by date with columns:
        nifty_return_1d, nifty_return_5d, nifty_above_sma50, nifty_above_sma200

    Merging this on date into per-stock features adds market regime context.
    """
    df = fetch_ohlcv("^NSEI", period=period, exchange="NSE")
    if df.empty:
        # Try without the suffix (special index symbol)
        import yfinance as yf

        try:
            raw = yf.download("^NSEI", period=period, auto_adjust=True, progress=False)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw.columns = [c.lower() for c in raw.columns]
            df = raw[raw["close"].notna()]
        except Exception as exc:
            logger.error("Could not fetch Nifty context: %s", exc)
            return pd.DataFrame()

    ctx = pd.DataFrame(index=df.index)
    ctx["nifty_return_1d"] = df["close"].pct_change(1)
    ctx["nifty_return_5d"] = df["close"].pct_change(5)
    sma50 = df["close"].rolling(50, min_periods=50).mean()
    sma200 = df["close"].rolling(200, min_periods=200).mean()
    ctx["nifty_above_sma50"] = (df["close"] > sma50).astype(int)
    ctx["nifty_above_sma200"] = (df["close"] > sma200).astype(int)
    return ctx


def add_market_context(stock_df: pd.DataFrame, context_df: pd.DataFrame) -> pd.DataFrame:
    """
    Left-join market context features into per-stock feature DataFrame.

    Uses date index alignment; forward-fills gaps (e.g. stock holiday != index holiday).
    """
    if context_df.empty:
        return stock_df
    merged = stock_df.join(context_df, how="left")
    # Forward-fill at most 5 days to handle short non-overlapping periods
    fill_cols = context_df.columns.tolist()
    merged[fill_cols] = merged[fill_cols].ffill(limit=5)
    return merged
