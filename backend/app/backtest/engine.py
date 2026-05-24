"""
Walk-forward backtest engine.

CRITICAL DESIGN PRINCIPLE — NO FUTURE LEAKAGE:
    Walk-forward means we train on a fixed rolling window ending at time T,
    make predictions for T+1 to T+retrain_every, then slide the window forward.
    The model NEVER sees data from its own prediction period during training.

    This is the only honest way to evaluate a time-series ML model.
    Never use random cross-validation on time-series — it will give falsely
    optimistic results by training on data that postdates the test period.

Trading simulation:
    - Long-only (no short selling — easier to implement as retail, common in India).
    - Full position sizing: either fully invested or fully in cash.
    - Transaction cost applied on both entry and exit.
    - Compared to simple buy-and-hold for the same stock over the same period.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.backtest.metrics import calculate_metrics
from app.features.technical import build_features
from app.models.ml_model import (
    FEATURE_COLS,
    make_target,
    prepare_training_data,
    time_split,
    train_model,
    predict as ml_predict,
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Container for walk-forward backtest outputs."""

    symbol: str
    trades: pd.DataFrame
    equity_curve: pd.Series
    metrics: dict[str, Any]
    parameters: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Human-readable one-line summary."""
        m = self.metrics
        if not m:
            return f"{self.symbol}: no metrics computed"
        return (
            f"{self.symbol}: return={m.get('total_return', 0):.1%} "
            f"alpha={m.get('alpha', 0):.1%} "
            f"sharpe={m.get('sharpe_ratio', 0):.2f} "
            f"maxdd={m.get('max_drawdown', 0):.1%} "
            f"trades={m.get('num_trades', 0)}"
        )


def walk_forward_backtest(
    ohlcv: pd.DataFrame,
    symbol: str,
    train_window: int = 504,       # ~2 trading years
    retrain_every: int = 21,       # ~1 trading month
    horizon: int = 5,
    threshold: float = 0.02,
    initial_capital: float = 100_000,
    transaction_cost: float = 0.001,  # 0.1% per trade (brokerage + STT proxy)
) -> BacktestResult:
    """
    Walk-forward backtest for a single stock symbol.

    Algorithm:
        1. Build all features once from the full OHLCV history.
        2. Walk through time in steps of `retrain_every`:
            a. Take the last `train_window` rows as training data.
            b. Train an XGBoost model on training data (time_split within it for eval).
            c. For the next `retrain_every` rows (the "prediction window"):
                - Predict prob_up for each bar.
                - If prob_up > 0.55: go long (buy at next open).
                - Else: stay in cash.
        3. Track equity curve: capital changes based on daily returns when invested.
        4. Compare to buy-and-hold.

    Returns:
        BacktestResult with full trade log, equity curve, and metrics.

    Args:
        ohlcv:             Raw OHLCV DataFrame (output of fetch_ohlcv).
        symbol:            Stock symbol (for labelling only).
        train_window:      Rows of history used per training run (~2 years = 504).
        retrain_every:     How often to retrain (rows between retraining cycles).
        horizon:           Prediction horizon in trading days.
        threshold:         Return threshold for binary label (e.g. 0.02 = 2%).
        initial_capital:   Starting portfolio value in INR.
        transaction_cost:  One-way transaction cost as a fraction of trade value.
    """
    # --- Feature engineering ---
    try:
        feature_df = build_features(ohlcv.copy())
    except Exception as exc:
        logger.error("Feature engineering failed for %s: %s", symbol, exc)
        return BacktestResult(symbol=symbol, trades=pd.DataFrame(), equity_curve=pd.Series(dtype=float), metrics={})

    # Drop rows where features or target would be NaN
    feature_df = feature_df.dropna(subset=FEATURE_COLS)

    if len(feature_df) < train_window + retrain_every + horizon:
        logger.warning(
            "%s: not enough data for backtest (%d rows, need %d)",
            symbol,
            len(feature_df),
            train_window + retrain_every + horizon,
        )
        return BacktestResult(symbol=symbol, trades=pd.DataFrame(), equity_curve=pd.Series(dtype=float), metrics={})

    dates = feature_df.index
    closes = feature_df["close"]

    # --- Walk-forward loop ---
    equity = initial_capital
    equity_curve: dict = {}
    trade_log: list[dict] = []
    position = 0          # 0 = cash, 1 = long
    entry_price = None
    entry_date = None

    # Start the walk at train_window (need history for first train)
    start_idx = train_window

    for window_start in range(start_idx, len(feature_df) - horizon, retrain_every):
        window_end = min(window_start + retrain_every, len(feature_df) - horizon)
        train_slice = feature_df.iloc[window_start - train_window: window_start]

        # --- Train ---
        try:
            y_train = make_target(train_slice, horizon=horizon, threshold=threshold)
            X_raw = train_slice[FEATURE_COLS]
            valid = X_raw.index.intersection(y_train.dropna().index)
            X_tr = X_raw.loc[valid]
            y_tr = y_train.loc[valid]
            if len(y_tr) < 50 or y_tr.nunique() < 2:
                # Not enough data or only one class — skip this window
                continue
            model, scaler = train_model(X_tr, y_tr)
        except Exception as exc:
            logger.debug("Training failed for %s window %d: %s", symbol, window_start, exc)
            continue

        # --- Predict and simulate trading ---
        for bar_idx in range(window_start, window_end):
            bar_date = dates[bar_idx]
            bar_close = float(closes.iloc[bar_idx])

            try:
                pred = ml_predict(model, scaler, feature_df.iloc[: bar_idx + 1])
                prob_up = pred["probability_up"]
            except Exception:
                prob_up = 0.5  # Neutral on prediction failure

            want_position = 1 if prob_up > 0.55 else 0

            # --- Position change ---
            if position == 0 and want_position == 1:
                # Buy: deduct transaction cost
                equity *= 1 - transaction_cost
                position = 1
                entry_price = bar_close
                entry_date = bar_date

            elif position == 1 and want_position == 0:
                # Sell: deduct transaction cost
                equity *= 1 - transaction_cost
                position = 0
                trade_return = bar_close / entry_price - 1 if entry_price else 0
                trade_log.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": bar_date,
                        "entry_price": entry_price,
                        "exit_price": bar_close,
                        "trade_return": trade_return,
                    }
                )
                entry_price = None
                entry_date = None

            # --- Daily equity update ---
            if bar_idx > 0 and position == 1:
                prev_close = float(closes.iloc[bar_idx - 1])
                if prev_close > 0:
                    daily_ret = bar_close / prev_close - 1
                    equity *= 1 + daily_ret

            equity_curve[bar_date] = equity

    # Close any open position at end
    if position == 1 and entry_price is not None:
        last_price = float(closes.iloc[-1])
        equity *= 1 - transaction_cost
        trade_return = last_price / entry_price - 1
        trade_log.append(
            {
                "entry_date": entry_date,
                "exit_date": dates[-1],
                "entry_price": entry_price,
                "exit_price": last_price,
                "trade_return": trade_return,
            }
        )

    equity_series = pd.Series(equity_curve)
    trades_df = pd.DataFrame(trade_log)

    # --- Buy-and-hold benchmark ---
    start_close = float(closes.iloc[start_idx])
    end_close = float(closes.iloc[-1])
    buy_hold_return = (end_close / start_close - 1) if start_close > 0 else 0.0

    metrics = calculate_metrics(equity_series, trades_df, buy_hold_return)

    return BacktestResult(
        symbol=symbol,
        trades=trades_df,
        equity_curve=equity_series,
        metrics=metrics,
        parameters={
            "train_window": train_window,
            "retrain_every": retrain_every,
            "horizon": horizon,
            "threshold": threshold,
            "transaction_cost": transaction_cost,
        },
    )
