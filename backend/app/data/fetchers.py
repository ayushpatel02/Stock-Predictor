"""
Data fetching layer — wraps yfinance for OHLCV, fundamentals, and market context.

yfinance data is 15-minute delayed for most users. This module is intentionally
thin: validation and caching happen in callers, not here.

NOTE ON LEAKAGE: This module only fetches raw market data. All train/test
splitting must happen in ml_model.py using time-based splits.
"""
from __future__ import annotations

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


def fetch_analyst_data(
    symbol: str,
    exchange: Exchange = "NSE",
) -> dict[str, Any]:
    """
    Fetch analyst estimates, consensus recommendations, and revenue/EPS forecasts.

    Primary source: yfinance Ticker properties.
    Fallback: Financial Modeling Prep free tier (if FMP_API_KEY env var is set).

    Returns a dict with keys:
        consensus       — analyst buy/hold/sell counts
        revenue_actuals — list of {year, value}
        revenue_estimates — list of {year, value}
        eps_actuals     — list of {year, value}
        eps_estimates   — list of {year, value}
        target_prices   — {mean, high, low}
    """
    from app.config import settings

    ticker_str = yf_symbol(symbol, exchange)
    result: dict[str, Any] = {
        "consensus": None,
        "revenue_actuals": [],
        "revenue_estimates": [],
        "eps_actuals": [],
        "eps_estimates": [],
        "target_prices": None,
    }

    try:
        t = yf.Ticker(ticker_str)
        info = t.info

        # --- Consensus recommendations ---
        try:
            recs = t.recommendations
            if recs is not None and not recs.empty:
                # Modern yfinance format: columns period, strongBuy, buy, hold, sell, strongSell
                if hasattr(recs, "columns") and "strongBuy" in recs.columns:
                    latest = recs.iloc[-1]
                    result["consensus"] = {
                        "strong_buy": int(latest.get("strongBuy", 0)),
                        "buy": int(latest.get("buy", 0)),
                        "hold": int(latest.get("hold", 0)),
                        "sell": int(latest.get("sell", 0)),
                        "strong_sell": int(latest.get("strongSell", 0)),
                    }
        except Exception:
            pass

        # Fallback consensus from .info recommendationKey + numberOfAnalystOpinions
        if result["consensus"] is None:
            rec_key = info.get("recommendationKey", "").lower()
            n = int(info.get("numberOfAnalystOpinions") or 0)
            if n > 0 and rec_key:
                # Distribute analysts across buckets based on key
                dist: dict[str, int] = {"strong_buy": 0, "buy": 0, "hold": 0, "sell": 0, "strong_sell": 0}
                if "strong buy" in rec_key:
                    dist["strong_buy"] = n
                elif "buy" in rec_key:
                    dist["buy"] = int(n * 0.6)
                    dist["strong_buy"] = n - dist["buy"]
                elif "hold" in rec_key:
                    dist["hold"] = n
                elif "sell" in rec_key:
                    dist["sell"] = n
                result["consensus"] = dist

        # --- Target prices ---
        try:
            tgt = t.analyst_price_targets
            if tgt is not None and not tgt.empty:
                row = tgt.iloc[-1]
                result["target_prices"] = {
                    "mean": _safe_float(row.get("mean")),
                    "high": _safe_float(row.get("high")),
                    "low": _safe_float(row.get("low")),
                    "current": _safe_float(row.get("current")),
                }
        except Exception:
            pass

        if result["target_prices"] is None:
            mean = _safe_float(info.get("targetMeanPrice"))
            high = _safe_float(info.get("targetHighPrice"))
            low = _safe_float(info.get("targetLowPrice"))
            if mean:
                result["target_prices"] = {"mean": mean, "high": high, "low": low, "current": None}

        # --- Revenue and EPS — historical from financials ---
        try:
            fin = t.financials
            if fin is not None and not fin.empty:
                for col in fin.columns:
                    yr_label = str(col.year) if hasattr(col, "year") else str(col)[:4]
                    rev = _safe_float(fin.loc["Total Revenue", col] if "Total Revenue" in fin.index else None)
                    if rev:
                        result["revenue_actuals"].append({"year": yr_label, "value": rev})
                result["revenue_actuals"].sort(key=lambda x: x["year"])
        except Exception:
            pass

        try:
            earn = t.earnings
            if earn is not None and not earn.empty and "Earnings" in earn.columns:
                for idx, row in earn.iterrows():
                    result["eps_actuals"].append({"year": str(idx), "value": _safe_float(row.get("Earnings"))})
                result["eps_actuals"].sort(key=lambda x: x["year"])
        except Exception:
            pass

        # --- Forward estimates ---
        try:
            rev_est = t.revenue_estimate
            if rev_est is not None and not rev_est.empty:
                for idx, row in rev_est.iterrows():
                    yr = str(idx)
                    avg = _safe_float(row.get("avg") if "avg" in row else row.iloc[0] if len(row) else None)
                    if avg:
                        result["revenue_estimates"].append({"year": yr + "E", "value": avg})
        except Exception:
            pass

        try:
            eps_est = t.earnings_estimate
            if eps_est is not None and not eps_est.empty:
                for idx, row in eps_est.iterrows():
                    yr = str(idx)
                    avg = _safe_float(row.get("avg") if "avg" in row else row.iloc[0] if len(row) else None)
                    if avg:
                        result["eps_estimates"].append({"year": yr + "E", "value": avg})
        except Exception:
            pass

    except Exception as exc:
        logger.error("Error fetching analyst data for %s: %s", symbol, exc)

    # --- FMP fallback (if API key set and data is still sparse) ---
    if settings.fmp_api_key and not result["revenue_actuals"]:
        try:
            import urllib.request
            import json as _json
            fmp_sym = symbol.replace("&", "")
            url = (
                f"https://financialmodelingprep.com/api/v3/income-statement/{fmp_sym}"
                f"?limit=5&apikey={settings.fmp_api_key}"
            )
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = _json.loads(resp.read())
            for entry in reversed(data[:5]):
                yr = str(entry.get("calendarYear", ""))
                rev = _safe_float(entry.get("revenue"))
                eps = _safe_float(entry.get("eps"))
                if yr and rev:
                    result["revenue_actuals"].append({"year": yr, "value": rev})
                if yr and eps:
                    result["eps_actuals"].append({"year": yr, "value": eps})
        except Exception as exc:
            logger.debug("FMP income-statement fallback failed for %s: %s", symbol, exc)

    if settings.fmp_api_key and not result["consensus"]:
        try:
            import urllib.request
            import json as _json
            fmp_sym = symbol.replace("&", "")
            url = (
                f"https://financialmodelingprep.com/api/v3/analyst-estimates/{fmp_sym}"
                f"?limit=2&apikey={settings.fmp_api_key}"
            )
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = _json.loads(resp.read())
            # FMP analyst estimates don't directly give consensus counts; skip
        except Exception:
            pass

    return result


def _safe_float(v: Any) -> float | None:
    """Coerce to float; return None if missing, NaN, or infinite."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if (f == f and f not in (float("inf"), float("-inf"))) else None
    except (TypeError, ValueError):
        return None


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
