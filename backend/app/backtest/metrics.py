"""
Backtest performance metrics.
All metrics are computed from an equity curve (daily portfolio values).
"""

import numpy as np
import pandas as pd


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.065) -> float:
    """
    Annualised Sharpe ratio.

    Uses Indian risk-free rate (~6.5% 10Y gilt) as default.
    Annualised by √252 (trading days per year).

    Returns NaN if returns have zero standard deviation.
    """
    if returns.std() == 0 or len(returns) < 2:
        return float("nan")
    excess = returns - risk_free_rate / 252
    return float(excess.mean() / excess.std() * np.sqrt(252))


def max_drawdown(equity: pd.Series) -> float:
    """
    Maximum peak-to-trough drawdown as a fraction (e.g. -0.25 = -25%).
    """
    if equity.empty:
        return float("nan")
    rolling_max = equity.cummax()
    drawdown = equity / rolling_max - 1
    return float(drawdown.min())


def win_rate(trades: pd.DataFrame) -> float:
    """
    Fraction of closed trades with positive return.
    Expects trades DataFrame with column 'trade_return'.
    """
    if trades.empty or "trade_return" not in trades.columns:
        return float("nan")
    winning = (trades["trade_return"] > 0).sum()
    return float(winning / len(trades))


def calculate_metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    buy_hold_return: float,
) -> dict[str, float]:
    """
    Compute all standard backtest metrics.

    Args:
        equity:           Equity curve (indexed by date, values = portfolio value).
        trades:           Trade log with columns: entry_date, exit_date, trade_return.
        buy_hold_return:  Total return of buy-and-hold strategy over the same period.

    Returns:
        dict of metric name → float
    """
    if equity.empty or len(equity) < 2:
        return {
            "total_return": float("nan"),
            "sharpe_ratio": float("nan"),
            "max_drawdown": float("nan"),
            "win_rate": float("nan"),
            "num_trades": 0,
            "buy_hold_return": buy_hold_return,
            "alpha": float("nan"),
        }

    daily_returns = equity.pct_change().dropna()
    total_ret = float(equity.iloc[-1] / equity.iloc[0] - 1)

    return {
        "total_return": round(total_ret, 4),
        "sharpe_ratio": round(sharpe_ratio(daily_returns), 4),
        "max_drawdown": round(max_drawdown(equity), 4),
        "win_rate": round(win_rate(trades), 4),
        "num_trades": len(trades),
        "buy_hold_return": round(buy_hold_return, 4),
        "alpha": round(total_ret - buy_hold_return, 4),
    }
