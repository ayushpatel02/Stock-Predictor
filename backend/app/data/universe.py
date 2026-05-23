"""
Symbol universe management.
Currently hardcoded to Nifty 50; designed to expand to all NSE without structural changes.
"""

from typing import Literal

# All 50 current Nifty 50 constituents (plain NSE symbols, no suffix).
# Update this list when index reconstitution happens.
NIFTY_50: list[str] = [
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "BHARTIARTL",
    "ICICIBANK",
    "INFY",
    "SBIN",
    "LT",
    "HINDUNILVR",
    "ITC",
    "BAJFINANCE",
    "HCLTECH",
    "KOTAKBANK",
    "SUNPHARMA",
    "MARUTI",
    "M&M",
    "AXISBANK",
    "NTPC",
    "ULTRACEMCO",
    "ONGC",
    "ADANIENT",
    "TITAN",
    "POWERGRID",
    "WIPRO",
    "BAJAJFINSV",
    "ASIANPAINT",
    "ADANIPORTS",
    "JSWSTEEL",
    "COALINDIA",
    "NESTLEIND",
    "BAJAJ-AUTO",
    "TATAMOTORS",
    "TATASTEEL",
    "GRASIM",
    "TRENT",
    "BEL",
    "HINDALCO",
    "SHRIRAMFIN",
    "EICHERMOT",
    "SBILIFE",
    "TECHM",
    "CIPLA",
    "DRREDDY",
    "APOLLOHOSP",
    "HDFCLIFE",
    "HEROMOTOCO",
    "TATACONSUM",
    "INDUSINDBK",
    "BPCL",
    "BRITANNIA",
]

# Active universe — swap this to expand to all NSE later
ACTIVE_UNIVERSE: list[str] = NIFTY_50

Exchange = Literal["NSE", "BSE"]


def is_valid_symbol(symbol: str) -> bool:
    """Return True if symbol is in the active universe."""
    return symbol.upper() in ACTIVE_UNIVERSE


def all_symbols() -> list[str]:
    """Return the full active symbol universe."""
    return list(ACTIVE_UNIVERSE)
