"""
Data fetching layer — wraps yfinance for OHLCV, fundamentals, and market context.

yfinance data is 15-minute delayed for most users. This module is intentionally
thin: validation and caching happen in callers, not here.

NOTE ON LEAKAGE: This module only fetches raw market data. All train/test
splitting must happen in ml_model.py using time-based splits.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from app.data.universe import Exchange

logger = logging.getLogger(__name__)

# Re-export for convenience
from app.data.universe import NIFTY_50, all_symbols, is_valid_symbol  # noqa: F401

# Index tickers used for market context
_INDEX_TICKERS = {
    "nifty50": "^NSEI",
    "banknifty": "^NSEBANK",
    "vix": "^INDIAVIX",
    "sensex": "^BSESN",
}


def yf_symbol(symbol: str, exchange: Exchange = "NSE") -> str:
    """
    Convert a plain NSE/BSE symbol to yfinance format.

    yfinance uses '.NS' for NSE and '.BO' for BSE.
    Handles edge cases like M&M (becomes MM.NS on yfinance).
    """
    symbol = symbol.upper().strip()
    # yfinance doesn't accept '&' — M&M is listed as 'MM.NS'
    if symbol == "M&M":
        symbol = "MM"
    suffix = ".NS" if exchange == "NSE" else ".BO"
    return f"{symbol}{suffix}"


def fetch_ohlcv(
    symbol: str,
    period: str = "2y",
    interval: str = "1d",
    exchange: Exchange = "NSE",
) -> pd.DataFrame:
    """
    Fetch OHLCV data for a single symbol from yfinance.

    Returns a DataFrame with lowercase columns: open, high, low, close, volume.
    Returns an empty DataFrame on failure — callers must check `df.empty`.

    Args:
        symbol:   Plain NSE symbol, e.g. 'RELIANCE'
        period:   yfinance period string, e.g. '1y', '2y', '5y'
        interval: yfinance interval string, e.g. '1d', '1wk'
        exchange: 'NSE' or 'BSE'
    """
    ticker = yf_symbol(symbol, exchange)
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
            show_errors=False,
        )
        if df.empty:
            logger.warning("No data returned for %s", ticker)
            return pd.DataFrame()

        # Flatten multi-level columns that yfinance sometimes returns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.columns = [c.lower() for c in df.columns]
        df.index.name = "date"

        # Drop rows where close is NaN or zero
        df = df[df["close"].notna() & (df["close"] > 0)]
        return df

    except Exception as exc:
        logger.error("Error fetching OHLCV for %s: %s", ticker, exc)
        return pd.DataFrame()


def fetch_fundamentals(
    symbol: str,
    exchange: Exchange = "NSE",
) -> dict[str, Any]:
    """
    Fetch fundamental data for a symbol via yfinance Ticker.info.

    Returns a dict with standardised keys. Missing fields are None.
    yfinance .info availability varies — never crash on missing keys.
    """
    ticker = yf_symbol(symbol, exchange)
    result: dict[str, Any] = {
        "symbol": symbol,
        "pe_ratio": None,
        "eps": None,
        "roe": None,
        "debt_to_equity": None,
        "market_cap": None,
        "beta": None,
        "week_52_high": None,
        "week_52_low": None,
        "dividend_yield": None,
        "revenue_growth": None,
        "profit_margins": None,
        "book_value": None,
        "price_to_book": None,
    }
    try:
        info = yf.Ticker(ticker).info
        result.update(
            {
                "pe_ratio": info.get("trailingPE"),
                "eps": info.get("trailingEps"),
                "roe": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "market_cap": info.get("marketCap"),
                "beta": info.get("beta"),
                "week_52_high": info.get("fiftyTwoWeekHigh"),
                "week_52_low": info.get("fiftyTwoWeekLow"),
                "dividend_yield": info.get("dividendYield"),
                "revenue_growth": info.get("revenueGrowth"),
                "profit_margins": info.get("profitMargins"),
                "book_value": info.get("bookValue"),
                "price_to_book": info.get("priceToBook"),
            }
        )
    except Exception as exc:
        logger.error("Error fetching fundamentals for %s: %s", ticker, exc)

    return result


def fetch_market_context() -> dict[str, Any]:
    """
    Fetch current values and day-change % for key Indian market indices.

    Returns dict with keys: nifty50, banknifty, vix, sensex.
    Each value is {'price': float, 'change_pct': float} or None on failure.
    """
    context: dict[str, Any] = {}
    for name, ticker in _INDEX_TICKERS.items():
        try:
            df = yf.download(
                ticker,
                period="5d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                show_errors=False,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [c.lower() for c in df.columns]
            df = df[df["close"].notna()]
            if len(df) < 2:
                context[name] = None
                continue
            price = float(df["close"].iloc[-1])
            prev_price = float(df["close"].iloc[-2])
            change_pct = ((price - prev_price) / prev_price) * 100
            context[name] = {"price": price, "change_pct": round(change_pct, 2)}
        except Exception as exc:
            logger.error("Error fetching market context for %s: %s", ticker, exc)
            context[name] = None

    return context


def fetch_batch_ohlcv(
    symbols: list[str],
    period: str = "2y",
    exchange: Exchange = "NSE",
) -> dict[str, pd.DataFrame]:
    """
    Efficiently fetch OHLCV for multiple symbols in one yfinance call.

    Returns a dict mapping plain symbol -> DataFrame.
    Missing/failed symbols return empty DataFrames.
    """
    tickers = [yf_symbol(s, exchange) for s in symbols]
    result: dict[str, pd.DataFrame] = {}

    try:
        raw = yf.download(
            tickers,
            period=period,
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            progress=False,
            show_errors=False,
        )
    except Exception as exc:
        logger.error("Batch OHLCV download failed: %s", exc)
        return {s: pd.DataFrame() for s in symbols}

    for symbol, ticker in zip(symbols, tickers):
        try:
            if ticker in raw.columns.get_level_values(0):
                df = raw[ticker].copy()
                df.columns = [c.lower() for c in df.columns]
                df.index.name = "date"
                df = df[df["close"].notna() & (df["close"] > 0)]
                result[symbol] = df
            else:
                result[symbol] = pd.DataFrame()
        except Exception as exc:
            logger.error("Error extracting %s from batch result: %s", symbol, exc)
            result[symbol] = pd.DataFrame()

    return result
