"""
Fundamental feature extraction.
Currently normalises raw yfinance .info fields into model-ready scalars.
These features are not yet wired into the ML model (see FEATURE_COLS in ml_model.py)
but the extraction logic is ready for the next phase.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Reasonable bounds for winsorization — prevents extreme outliers from
# distorting scaling. Tune per sector in production.
_BOUNDS = {
    "pe_ratio": (0, 150),
    "debt_to_equity": (0, 500),
    "roe": (-1, 1),
    "revenue_growth": (-1, 2),
    "profit_margins": (-1, 1),
}


def extract_fundamental_features(info: dict[str, Any]) -> dict[str, float | None]:
    """
    Normalise raw fundamental dict (from fetchers.fetch_fundamentals) into
    model-ready float features. Missing values return None — fill with
    sector median before passing to the model.

    Returns:
        dict with keys suitable for merging into a feature DataFrame.
    """
    features: dict[str, float | None] = {}

    raw = {
        "pe_ratio": info.get("pe_ratio"),
        "debt_to_equity": info.get("debt_to_equity"),
        "roe": info.get("roe"),
        "revenue_growth": info.get("revenue_growth"),
        "profit_margins": info.get("profit_margins"),
        "beta": info.get("beta"),
        "price_to_book": info.get("price_to_book"),
    }

    for key, value in raw.items():
        if value is None or not np.isfinite(float(value)):
            features[key] = None
        else:
            v = float(value)
            if key in _BOUNDS:
                lo, hi = _BOUNDS[key]
                v = max(lo, min(hi, v))
            features[key] = v

    # Derived: distance from 52-week high/low as momentum signal
    high52 = info.get("week_52_high")
    low52 = info.get("week_52_low")
    market_cap = info.get("market_cap")  # noqa: F841  # used in future scoring

    features["dist_from_52w_high"] = None
    features["dist_from_52w_low"] = None

    if high52 and low52 and high52 > 0:
        # Assumes current price is embedded in info — use as proxy
        current = info.get("market_cap")  # placeholder until price is passed
        if current:
            features["dist_from_52w_high"] = None  # requires current price
            features["dist_from_52w_low"] = None   # requires current price

    return features
