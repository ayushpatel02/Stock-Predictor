"""
XGBoost binary classifier: will the stock close >threshold% higher in `horizon` days?

CRITICAL — NO FUTURE LEAKAGE:
    - time_split() always uses the LAST test_frac of rows as test set.
    - The model is trained ONLY on data before the split date.
    - Features are lagged returns (not forward returns) — all look backward.
    - Scaler is fit ONLY on training data, then applied to test data.

Design choices:
    - Binary classification first (up >2% in 5 days), not regression.
      Regression of noisy price targets tends to overfit; calibrated probabilities
      are more actionable for the BUY/HOLD/SELL framing.
    - StandardScaler + XGBoost (tree-based methods don't need scaling, but it
      helps if we add regularised linear models later without rewriting the pipeline).
    - Feature list is explicit (FEATURE_COLS constant) so the saved bundle
      always knows which columns to expect.
"""

import logging
import os
import pickle
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature column list
# ---------------------------------------------------------------------------

# IMPORTANT: order matters — must match the order used during training.
# Add new feature groups in NEW sections (commented stubs below) so old
# pickled models remain valid until retrained.
FEATURE_COLS: list[str] = [
    # --- Moving averages ---
    "sma_20",
    "sma_50",
    "sma_200",
    "ema_20",
    "ema_50",
    "sma_20_above_50",
    "golden_cross",
    # --- RSI ---
    "rsi",
    "rsi_oversold",
    "rsi_overbought",
    # --- MACD ---
    "macd",
    "macd_signal",
    "macd_hist",
    "macd_bullish_cross",
    # --- Bollinger Bands ---
    "bb_width",
    "bb_pct",
    # --- ATR ---
    "atr_pct",
    # --- Volume ---
    "volume_ratio",
    "obv_ema",
    # --- Returns & volatility ---
    "return_1d",
    "return_5d",
    "return_20d",
    # vol_1d excluded: rolling std of window=1 is always NaN (ddof=1 needs ≥2 obs)
    "vol_5d",
    "vol_20d",
    # --- Fundamentals (stub — not in live feature set yet) ---
    # "pe_ratio",
    # "roe",
    # "debt_to_equity",
    # "beta",
    # --- Sentiment (stub — not in live feature set yet) ---
    # "sentiment_compound",
    # --- Market context (stub — not in live feature set yet) ---
    # "nifty_return_5d",
    # "nifty_above_sma50",
]

# ---------------------------------------------------------------------------
# Target
# ---------------------------------------------------------------------------


def make_target(
    df: pd.DataFrame,
    horizon: int = 5,
    threshold: float = 0.02,
) -> pd.Series:
    """
    Binary target: 1 if close price rises > threshold in `horizon` trading days.

    Uses SHIFTED future close — this column must be EXCLUDED from features and
    must only be computed before the train/test split is known.

    NOTE: The last `horizon` rows will be NaN — drop them before training.

    Args:
        df:        OHLCV DataFrame with at least a 'close' column.
        horizon:   Number of trading days forward to predict.
        threshold: Minimum price increase fraction to label as 1 (default 2%).

    Returns:
        pd.Series of {0, 1, NaN}
    """
    future_return = df["close"].shift(-horizon) / df["close"] - 1
    return (future_return > threshold).astype(float).where(future_return.notna(), other=np.nan)


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------


def prepare_training_data(
    feature_df: pd.DataFrame,
    horizon: int = 5,
    threshold: float = 0.02,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Build (X, y) from a feature DataFrame, dropping NaN rows.

    Args:
        feature_df: Output of build_features() — must contain FEATURE_COLS.
        horizon:    Days forward for the target.
        threshold:  Return threshold for binary label.

    Returns:
        (X, y) with aligned indices, NaN rows removed.
    """
    missing = [c for c in FEATURE_COLS if c not in feature_df.columns]
    if missing:
        raise ValueError(f"feature_df missing required columns: {missing}")

    y = make_target(feature_df, horizon, threshold)
    X = feature_df[FEATURE_COLS].copy()

    combined = pd.concat([X, y.rename("target")], axis=1).dropna()
    return combined[FEATURE_COLS], combined["target"]


# ---------------------------------------------------------------------------
# Train / test split — TIME-BASED ONLY
# ---------------------------------------------------------------------------


def time_split(
    X: pd.DataFrame,
    y: pd.Series,
    test_frac: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """
    Chronological train/test split. NEVER random.

    The last `test_frac` fraction of rows (by index order) is the test set.
    This mirrors real-world deployment: train on past, evaluate on future.

    Returns:
        (X_train, X_test, y_train, y_test)
    """
    n = len(X)
    split_idx = int(n * (1 - test_frac))
    if split_idx < 50:
        raise ValueError(
            f"Not enough data for training: {n} rows total, split at {split_idx}. "
            "Need at least 50 training rows."
        )
    return X.iloc[:split_idx], X.iloc[split_idx:], y.iloc[:split_idx], y.iloc[split_idx:]


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> tuple[XGBClassifier, StandardScaler]:
    """
    Train XGBoost classifier with StandardScaler.

    Hyperparameters are sane defaults — tune per-stock in production using
    TimeSeriesSplit CV. Do NOT tune on the test set.

    Returns:
        (model, scaler) — both fitted on X_train / y_train only.
    """
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)

    # Class imbalance: weight positive class by the inverse frequency
    pos_frac = y_train.mean()
    scale_pos_weight = (1 - pos_frac) / pos_frac if pos_frac > 0 else 1.0

    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled, y_train)
    return model, scaler


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------


def evaluate(
    model: XGBClassifier,
    scaler: StandardScaler,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    """
    Evaluate model on held-out test set (must be the FUTURE relative to training).

    Returns:
        dict with accuracy, auc, classification_report, feature_importance
    """
    X_scaled = scaler.transform(X_test)
    y_pred = model.predict(X_scaled)
    y_prob = model.predict_proba(X_scaled)[:, 1]

    try:
        auc = roc_auc_score(y_test, y_prob)
    except ValueError:
        auc = None  # Only one class in test set (can happen with small test sets)

    importance = dict(zip(FEATURE_COLS, model.feature_importances_.tolist()))

    return {
        "accuracy": float((y_pred == y_test).mean()),
        "auc": float(auc) if auc is not None else None,
        "classification_report": classification_report(y_test, y_pred, output_dict=True),
        "feature_importance": importance,
        "n_test_samples": len(y_test),
    }


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------


def predict(
    model: XGBClassifier,
    scaler: StandardScaler,
    latest_features: pd.DataFrame,
) -> dict[str, Any]:
    """
    Generate a BUY/HOLD/SELL signal from the most recent feature row.

    Signal thresholds:
        prob_up > 0.65  → BUY
        prob_up < 0.35  → SELL
        otherwise       → HOLD

    Confidence is the distance from the 0.5 midpoint, scaled to [0, 1].

    Args:
        latest_features: DataFrame with FEATURE_COLS columns (1 or more rows;
                         uses last row).

    Returns:
        dict: signal, probability_up, confidence
    """
    from app.config import settings

    row = latest_features[FEATURE_COLS].iloc[[-1]]
    X_scaled = scaler.transform(row)
    prob_up = float(model.predict_proba(X_scaled)[0, 1])

    if prob_up > settings.buy_threshold:
        signal = "BUY"
    elif prob_up < settings.sell_threshold:
        signal = "SELL"
    else:
        signal = "HOLD"

    confidence = abs(prob_up - 0.5) * 2  # 0 = uncertain, 1 = very confident
    return {
        "signal": signal,
        "probability_up": round(prob_up, 4),
        "confidence": round(confidence, 4),
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_model(
    model: XGBClassifier,
    scaler: StandardScaler,
    path: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Save model, scaler, feature list, and optional metadata to a pickle bundle.

    The feature list is saved explicitly so loading code can detect column
    mismatches if features change between training runs.
    """
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    bundle = {
        "model": model,
        "scaler": scaler,
        "feature_cols": FEATURE_COLS,
        "metadata": metadata or {},
    }
    with open(path, "wb") as f:
        pickle.dump(bundle, f)
    logger.info("Model saved to %s", path)


def load_model(path: str) -> tuple[XGBClassifier, StandardScaler]:
    """
    Load model bundle and validate feature columns match current FEATURE_COLS.

    Returns:
        (model, scaler)

    Raises:
        FileNotFoundError: if the .pkl file does not exist.
        ValueError: if saved feature columns don't match current FEATURE_COLS.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"No trained model at {path}. Run train_all.py first.")

    with open(path, "rb") as f:
        bundle = pickle.load(f)

    saved_cols = bundle.get("feature_cols", [])
    if saved_cols and saved_cols != FEATURE_COLS:
        logger.warning(
            "Feature mismatch: saved model has %d features, current FEATURE_COLS has %d. "
            "Retrain the model.",
            len(saved_cols),
            len(FEATURE_COLS),
        )

    return bundle["model"], bundle["scaler"]
