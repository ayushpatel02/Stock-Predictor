"""
CLI script: train XGBoost models for all symbols in the active universe.

Usage:
    # From backend/ directory with venv activated:
    python -m app.scripts.train_all

    # Train only a subset (useful for quick validation):
    python -m app.scripts.train_all --symbols RELIANCE TCS INFY HDFCBANK ICICIBANK

Outputs:
    models/{SYMBOL}.pkl for each successfully trained symbol.
    Summary table printed to stdout.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

# Ensure project root is importable when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import settings
from app.data.fetchers import fetch_ohlcv
from app.data.universe import all_symbols
from app.features.technical import build_features
from app.models.ml_model import (
    FEATURE_COLS,
    evaluate,
    prepare_training_data,
    save_model,
    time_split,
    train_model,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("train_all")


def train_symbol(symbol: str) -> dict | None:
    """
    Train and save a model for a single symbol.
    Returns a metrics dict on success, None on failure.
    """
    logger.info("[%s] Fetching 5 years of data...", symbol)
    df = fetch_ohlcv(symbol, period="5y")
    if df.empty or len(df) < 300:
        logger.warning("[%s] Insufficient data (%d rows) — skipping", symbol, len(df))
        return None

    logger.info("[%s] Building features...", symbol)
    try:
        feature_df = build_features(df)
    except Exception as exc:
        logger.error("[%s] Feature engineering failed: %s", symbol, exc)
        return None

    try:
        X, y = prepare_training_data(feature_df)
    except Exception as exc:
        logger.error("[%s] Data preparation failed: %s", symbol, exc)
        return None

    if len(X) < 100 or y.nunique() < 2:
        logger.warning("[%s] Not enough usable rows or single class — skipping", symbol)
        return None

    try:
        X_train, X_test, y_train, y_test = time_split(X, y, test_frac=0.2)
        model, scaler = train_model(X_train, y_train)
        metrics = evaluate(model, scaler, X_test, y_test)
    except Exception as exc:
        logger.error("[%s] Training/evaluation failed: %s", symbol, exc)
        return None

    model_path = os.path.join(settings.models_dir, f"{symbol}.pkl")
    try:
        save_model(model, scaler, model_path, metadata={"symbol": symbol, **metrics})
    except Exception as exc:
        logger.error("[%s] Save failed: %s", symbol, exc)
        return None

    logger.info(
        "[%s] Trained — accuracy=%.3f AUC=%.3f (n_test=%d)",
        symbol,
        metrics.get("accuracy", 0),
        metrics.get("auc") or 0,
        metrics.get("n_test_samples", 0),
    )
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Train stock prediction models")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Symbols to train (default: all universe symbols)",
    )
    args = parser.parse_args()

    symbols = [s.upper() for s in args.symbols] if args.symbols else all_symbols()
    logger.info("Training %d symbols: %s", len(symbols), symbols)

    os.makedirs(settings.models_dir, exist_ok=True)

    results = {}
    t0 = time.time()
    for symbol in symbols:
        results[symbol] = train_symbol(symbol)

    # Print summary
    success = {s: r for s, r in results.items() if r is not None}
    failed = [s for s, r in results.items() if r is None]

    print("\n" + "=" * 60)
    print(f"Training complete in {time.time() - t0:.0f}s")
    print(f"Success: {len(success)}/{len(symbols)}")
    if failed:
        print(f"Failed:  {failed}")
    print("-" * 60)

    if success:
        accs = [r["accuracy"] for r in success.values() if r.get("accuracy") is not None]
        aucs = [r["auc"] for r in success.values() if r.get("auc") is not None]
        print(f"Avg accuracy: {sum(accs)/len(accs):.3f}" if accs else "")
        print(f"Avg AUC:      {sum(aucs)/len(aucs):.3f}" if aucs else "")

    print("=" * 60)


if __name__ == "__main__":
    main()
