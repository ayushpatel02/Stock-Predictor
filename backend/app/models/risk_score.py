"""
Risk scoring: combines ATR%, beta, and debt-to-equity into a 1-10 risk score.
Higher = riskier. The score is computed from the latest available data,
not from predictions — it represents intrinsic stock risk, not directional risk.
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# Score boundaries for each factor before combining
_ATR_PCT_BUCKETS = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.065, 0.08]  # 9 thresholds → 10 bands
_BETA_BUCKETS = [0.3, 0.5, 0.7, 0.9, 1.0, 1.1, 1.3, 1.5, 1.8]
_DE_BUCKETS = [0, 10, 30, 60, 100, 150, 200, 300, 500]


def _bucket(value: float, thresholds: list[float]) -> int:
    """Map a value to an integer 1-10 using threshold buckets."""
    for i, t in enumerate(thresholds):
        if value <= t:
            return i + 1
    return 10


def compute_risk_score(
    atr_pct: float | None,
    beta: float | None,
    debt_to_equity: float | None,
) -> int:
    """
    Compute a 1-10 risk score from volatility and leverage metrics.

    Weights: ATR% 50%, beta 30%, D/E 20%.
    Any missing component is replaced by a neutral mid-range value (5).

    Args:
        atr_pct:        ATR / close price (e.g. 0.02 = 2% daily range)
        beta:           Market beta (1.0 = market neutral)
        debt_to_equity: Debt-to-equity ratio (e.g. 100 = 1x)

    Returns:
        int 1-10 where 10 is highest risk
    """
    atr_score = _bucket(atr_pct, _ATR_PCT_BUCKETS) if atr_pct is not None else 5
    beta_score = _bucket(beta, _BETA_BUCKETS) if beta is not None else 5
    de_score = _bucket(debt_to_equity, _DE_BUCKETS) if debt_to_equity is not None else 5

    weighted = 0.5 * atr_score + 0.3 * beta_score + 0.2 * de_score
    return max(1, min(10, round(weighted)))
