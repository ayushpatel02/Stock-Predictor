"""
Daily data refresh script — run after market close (4:30 PM IST weekdays).

Fetches latest OHLCV for all symbols and optionally retrains models.
Designed to be called from the GitHub Actions daily-refresh.yml workflow.

Usage:
    python -m app.scripts.refresh_data [--retrain]
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.data.fetchers import fetch_ohlcv
from app.data.universe import all_symbols

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("refresh_data")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrain", action="store_true", help="Retrain models after refresh")
    args = parser.parse_args()

    symbols = all_symbols()
    logger.info("Refreshing data for %d symbols", len(symbols))

    success, fail = 0, 0
    for symbol in symbols:
        df = fetch_ohlcv(symbol, period="5y")
        if df.empty:
            logger.warning("[%s] No data fetched", symbol)
            fail += 1
        else:
            logger.info("[%s] %d rows fetched (latest: %s)", symbol, len(df), df.index[-1])
            success += 1

    logger.info("Refresh done: %d success, %d failed", success, fail)

    if args.retrain:
        logger.info("Retraining models...")
        from app.scripts.train_all import main as train_main  # noqa: F401
        train_main()


if __name__ == "__main__":
    main()
