"""
Sentiment feature stub — wired for Finnhub news + VADER analysis.
Returns neutral scores (0.0) until implemented.

Implementation plan (Phase 2):
    1. Fetch news headlines from Finnhub for the symbol.
    2. Run VADER SentimentIntensityAnalyzer on each headline.
    3. Aggregate: 5-day rolling mean compound score.
    4. Add to FEATURE_COLS in ml_model.py.

Dependencies to add to requirements.txt when activating:
    finnhub-python==2.4.19
    vaderSentiment==3.3.2
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_sentiment_score(symbol: str, days_back: int = 5) -> dict[str, float]:
    """
    Return sentiment scores for a symbol over the past N days.

    Currently returns neutral stub values (0.0). Replace this function body
    to activate sentiment features — the rest of the pipeline is already wired.

    Returns:
        dict with keys: sentiment_compound, sentiment_positive, sentiment_negative
    """
    logger.debug("Sentiment stub called for %s — returning neutral scores", symbol)
    return {
        "sentiment_compound": 0.0,
        "sentiment_positive": 0.0,
        "sentiment_negative": 0.0,
    }
