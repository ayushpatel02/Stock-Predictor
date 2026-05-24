"""
Tests for technical indicator calculations.
Uses synthetic OHLCV data — no network calls, deterministic results.
"""

import numpy as np
import pandas as pd
import pytest

from app.features.technical import (
    add_atr,
    add_bollinger,
    add_macd,
    add_moving_averages,
    add_rsi,
    add_returns,
    add_volume_features,
    build_features,
)


def make_ohlcv(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data with a mild upward trend."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    close = 1000 + np.cumsum(rng.normal(loc=0.5, scale=10, size=n))
    close = np.maximum(close, 100)  # Floor at 100
    high = close * (1 + rng.uniform(0, 0.02, n))
    low = close * (1 - rng.uniform(0, 0.02, n))
    open_ = close * (1 + rng.normal(0, 0.005, n))
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def ohlcv():
    return make_ohlcv()


class TestMovingAverages:
    def test_sma_columns_present(self, ohlcv):
        df = add_moving_averages(ohlcv)
        for w in [20, 50, 200]:
            assert f"sma_{w}" in df.columns
            assert f"ema_{w}" in df.columns

    def test_sma_values_reasonable(self, ohlcv):
        df = add_moving_averages(ohlcv)
        # SMA-20 should be close to recent close prices
        last_20_mean = ohlcv["close"].iloc[-20:].mean()
        sma20_last = df["sma_20"].iloc[-1]
        assert abs(sma20_last - last_20_mean) < 1.0

    def test_sma_above_50_binary(self, ohlcv):
        df = add_moving_averages(ohlcv)
        vals = df["sma_20_above_50"].dropna().unique()
        assert set(vals).issubset({0, 1})

    def test_golden_cross_binary(self, ohlcv):
        df = add_moving_averages(ohlcv)
        vals = df["golden_cross"].dropna().unique()
        assert set(vals).issubset({0, 1})


class TestRSI:
    def test_rsi_range(self, ohlcv):
        df = add_rsi(ohlcv)
        rsi = df["rsi"].dropna()
        assert rsi.min() >= 0, "RSI should not be negative"
        assert rsi.max() <= 100, "RSI should not exceed 100"

    def test_rsi_overbought_consistent(self, ohlcv):
        df = add_rsi(ohlcv)
        mask = df["rsi_overbought"] == 1
        # All flagged rows should have RSI > 70
        assert (df.loc[mask, "rsi"] > 70).all()

    def test_rsi_oversold_consistent(self, ohlcv):
        df = add_rsi(ohlcv)
        mask = df["rsi_oversold"] == 1
        assert (df.loc[mask, "rsi"] < 30).all()

    def test_trending_rsi_above_50(self):
        """In a strongly rising market RSI should tend to be above 50."""
        # Create 100 sessions of pure up-moves
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        c = np.arange(100, 200, dtype=float)
        df = pd.DataFrame(
            {"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": [1e6] * 100},
            index=dates,
        )
        df = add_rsi(df)
        # After burn-in period RSI should be high
        assert df["rsi"].iloc[-1] > 60


class TestMACD:
    def test_columns_present(self, ohlcv):
        df = add_macd(ohlcv)
        for col in ["macd", "macd_signal", "macd_hist", "macd_bullish_cross"]:
            assert col in df.columns

    def test_hist_is_diff(self, ohlcv):
        df = add_macd(ohlcv)
        diff = (df["macd"] - df["macd_signal"] - df["macd_hist"]).dropna().abs()
        assert diff.max() < 1e-10, "macd_hist should equal macd - signal"

    def test_bullish_cross_binary(self, ohlcv):
        df = add_macd(ohlcv)
        vals = df["macd_bullish_cross"].dropna().unique()
        assert set(vals).issubset({0, 1})


class TestBollinger:
    def test_price_within_bands(self, ohlcv):
        df = add_bollinger(ohlcv)
        valid = df[["close", "bb_upper", "bb_lower"]].dropna()
        # Price should rarely be outside 3-sigma bands (virtually never for 2-sigma in normal markets)
        within = (valid["close"] <= valid["bb_upper"] * 1.01) & (valid["close"] >= valid["bb_lower"] * 0.99)
        # At least 80% of rows should be within bands
        assert within.mean() > 0.80

    def test_bb_pct_around_50_on_sma_touch(self, ohlcv):
        df = add_bollinger(ohlcv)
        # When close == bb_middle, bb_pct should be ≈ 0.5
        at_middle = (df["close"] - df["bb_middle"]).abs() < 0.01
        if at_middle.any():
            pcts = df.loc[at_middle, "bb_pct"].dropna()
            assert (pcts - 0.5).abs().max() < 0.05

    def test_bb_width_positive(self, ohlcv):
        df = add_bollinger(ohlcv)
        assert (df["bb_width"].dropna() > 0).all()


class TestATR:
    def test_atr_positive(self, ohlcv):
        df = add_atr(ohlcv)
        assert (df["atr"].dropna() > 0).all()

    def test_atr_pct_in_range(self, ohlcv):
        df = add_atr(ohlcv)
        pct = df["atr_pct"].dropna()
        # Typical daily range for liquid large-caps: 0.5% – 5%
        assert pct.min() > 0
        assert pct.max() < 0.2


class TestVolumeFeatures:
    def test_columns_present(self, ohlcv):
        df = add_volume_features(ohlcv)
        for col in ["volume_ma20", "volume_ratio", "obv", "obv_ema"]:
            assert col in df.columns

    def test_volume_ratio_near_one_on_flat_volume(self):
        """If volume is constant, ratio should be 1.0."""
        dates = pd.date_range("2023-01-01", periods=50, freq="B")
        close = np.ones(50) * 1000
        volume = np.ones(50) * 1_000_000
        df = pd.DataFrame(
            {"open": close, "high": close, "low": close, "close": close, "volume": volume},
            index=dates,
        )
        df = add_volume_features(df)
        ratios = df["volume_ratio"].dropna()
        assert (ratios - 1.0).abs().max() < 1e-6


class TestReturns:
    def test_columns_present(self, ohlcv):
        df = add_returns(ohlcv)
        for p in [1, 5, 20]:
            assert f"return_{p}d" in df.columns
            assert f"vol_{p}d" in df.columns

    def test_1d_return_matches_pct_change(self, ohlcv):
        df = add_returns(ohlcv)
        expected = ohlcv["close"].pct_change(1)
        diff = (df["return_1d"] - expected).dropna().abs()
        assert diff.max() < 1e-12


class TestBuildFeatures:
    def test_pipeline_runs_without_error(self, ohlcv):
        df = build_features(ohlcv)
        assert not df.empty

    def test_all_feature_cols_present(self, ohlcv):
        from app.models.ml_model import FEATURE_COLS

        df = build_features(ohlcv)
        missing = [c for c in FEATURE_COLS if c not in df.columns]
        assert missing == [], f"Missing feature columns: {missing}"

    def test_enough_non_nan_rows(self, ohlcv):
        from app.models.ml_model import FEATURE_COLS

        df = build_features(ohlcv)
        valid = df.dropna(subset=FEATURE_COLS)
        # With 300 rows and SMA-200, should have at least 80 valid rows
        assert len(valid) >= 80
