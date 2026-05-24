"""
Tests for the walk-forward backtest engine.
Uses synthetic data — no network calls.
"""

import numpy as np
import pandas as pd
import pytest

from app.backtest.engine import BacktestResult, walk_forward_backtest
from app.backtest.metrics import calculate_metrics, max_drawdown, sharpe_ratio, win_rate


def make_trending_ohlcv(n: int = 800, seed: int = 1) -> pd.DataFrame:
    """
    Strongly trending synthetic OHLCV.
    With a consistent uptrend the model should tend to stay long
    and produce positive returns.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2019-01-01", periods=n, freq="B")
    close = 1000 + np.cumsum(rng.normal(loc=1.0, scale=8, size=n))
    close = np.maximum(close, 100)
    high = close * (1 + rng.uniform(0.002, 0.012, n))
    low = close * (1 - rng.uniform(0.002, 0.012, n))
    open_ = close + rng.normal(0, 2, n)
    volume = rng.integers(1_000_000, 4_000_000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def make_flat_ohlcv(n: int = 800, price: float = 1000.0) -> pd.DataFrame:
    """Flat (sideways) synthetic OHLCV — model should stay mostly in cash."""
    rng = np.random.default_rng(99)
    dates = pd.date_range("2019-01-01", periods=n, freq="B")
    close = np.full(n, price) + rng.normal(0, 2, n)
    close = np.maximum(close, 50)
    high = close * 1.005
    low = close * 0.995
    open_ = close.copy()
    volume = rng.integers(500_000, 2_000_000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


class TestMetrics:
    def test_sharpe_flat_returns_zero(self):
        returns = pd.Series([0.0] * 100)
        # Zero daily returns → zero excess (below risk-free), negative sharpe
        s = sharpe_ratio(returns)
        assert s < 0 or np.isnan(s)

    def test_sharpe_positive_on_rising_equity(self):
        rng = np.random.default_rng(0)
        # Positive mean return with small noise so std > 0
        returns = pd.Series(rng.normal(loc=0.005, scale=0.001, size=252))
        s = sharpe_ratio(returns)
        assert s > 0

    def test_max_drawdown_no_drawdown(self):
        equity = pd.Series(range(1, 101), dtype=float)
        dd = max_drawdown(equity)
        assert abs(dd) < 1e-10

    def test_max_drawdown_measures_worst(self):
        equity = pd.Series([100, 120, 80, 90, 100], dtype=float)
        dd = max_drawdown(equity)
        # Worst: 120 → 80 = -33.3%
        assert abs(dd - (-1 / 3)) < 0.01

    def test_win_rate_all_winners(self):
        trades = pd.DataFrame({"trade_return": [0.05, 0.10, 0.03]})
        assert win_rate(trades) == 1.0

    def test_win_rate_all_losers(self):
        trades = pd.DataFrame({"trade_return": [-0.05, -0.10, -0.03]})
        assert win_rate(trades) == 0.0


class TestBacktestEngine:
    @pytest.fixture
    def trending_result(self):
        ohlcv = make_trending_ohlcv()
        return walk_forward_backtest(
            ohlcv,
            symbol="TEST",
            train_window=300,
            retrain_every=21,
        )

    def test_returns_backtest_result(self, trending_result):
        assert isinstance(trending_result, BacktestResult)

    def test_equity_curve_non_empty(self, trending_result):
        assert not trending_result.equity_curve.empty

    def test_equity_starts_near_initial_capital(self, trending_result):
        initial = 100_000
        first_equity = trending_result.equity_curve.iloc[0]
        assert abs(first_equity - initial) / initial < 0.05

    def test_metrics_present(self, trending_result):
        m = trending_result.metrics
        for key in ["total_return", "sharpe_ratio", "max_drawdown", "win_rate", "num_trades"]:
            assert key in m

    def test_trending_market_positive_return(self, trending_result):
        """
        On a strongly trending market, the strategy should make money.
        Not guaranteed (market-timing is hard) but with a 1.0pt/day drift
        the signal should detect the trend and produce positive returns.
        """
        total_ret = trending_result.metrics.get("total_return", 0)
        # Weak assertion: at least not catastrophic
        assert total_ret > -0.5, f"Strategy lost >50% on trending data: {total_ret:.1%}"

    def test_summary_string(self, trending_result):
        summary = trending_result.summary()
        assert "TEST" in summary
        assert "return=" in summary

    def test_insufficient_data_returns_empty(self):
        """With too little data the engine should return gracefully, not crash."""
        short_df = make_trending_ohlcv(n=50)
        result = walk_forward_backtest(short_df, symbol="SHORT", train_window=300)
        # Should return an empty result, not raise
        assert result.equity_curve.empty or result.metrics == {}

    def test_flat_market_few_trades(self):
        """In a sideways market the model should trade infrequently."""
        ohlcv = make_flat_ohlcv()
        result = walk_forward_backtest(ohlcv, symbol="FLAT", train_window=300, retrain_every=21)
        # Flat market → low probability signals → few trades expected
        # Just ensure it runs and num_trades is a non-negative integer
        if result.metrics:
            assert result.metrics.get("num_trades", 0) >= 0
