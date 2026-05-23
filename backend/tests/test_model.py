"""
Tests for the ML model pipeline.
Uses synthetic data — no network calls, no trained model files needed.
"""

import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from app.features.technical import build_features
from app.models.ml_model import (
    FEATURE_COLS,
    evaluate,
    load_model,
    make_target,
    prepare_training_data,
    predict,
    save_model,
    time_split,
    train_model,
)


def make_synthetic_df(n: int = 400, seed: int = 0) -> pd.DataFrame:
    """Synthetic OHLCV with an upward trend and enough rows for SMA-200."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2021-01-01", periods=n, freq="B")
    close = 1000 + np.cumsum(rng.normal(0.3, 8, n))
    close = np.maximum(close, 50)
    high = close * (1 + rng.uniform(0, 0.015, n))
    low = close * (1 - rng.uniform(0, 0.015, n))
    open_ = close + rng.normal(0, 3, n)
    volume = rng.integers(500_000, 3_000_000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def feature_df():
    raw = make_synthetic_df()
    df = build_features(raw)
    return df.dropna(subset=FEATURE_COLS)


@pytest.fixture
def xy(feature_df):
    return prepare_training_data(feature_df)


@pytest.fixture
def trained(xy):
    X, y = xy
    X_train, _, y_train, _ = time_split(X, y)
    return train_model(X_train, y_train)


class TestMakeTarget:
    def test_binary_values(self, feature_df):
        y = make_target(feature_df)
        unique = y.dropna().unique()
        assert set(unique).issubset({0.0, 1.0})

    def test_last_rows_nan(self, feature_df):
        y = make_target(feature_df, horizon=5)
        # Last 5 rows should be NaN (no future data)
        assert y.iloc[-5:].isna().all()

    def test_positive_rate_reasonable(self, feature_df):
        y = make_target(feature_df)
        rate = y.dropna().mean()
        # In a trending-up market, >5% positive rate is plausible
        assert 0.05 < rate < 0.95


class TestPrepareData:
    def test_no_nan_in_output(self, feature_df):
        X, y = prepare_training_data(feature_df)
        assert not X.isna().any().any()
        assert not y.isna().any()

    def test_correct_columns(self, feature_df):
        X, _ = prepare_training_data(feature_df)
        assert list(X.columns) == FEATURE_COLS

    def test_raises_on_missing_cols(self):
        df = pd.DataFrame({"close": [1, 2, 3]})
        with pytest.raises(ValueError, match="missing required columns"):
            prepare_training_data(df)


class TestTimeSplit:
    def test_chronological_order(self, xy):
        X, y = xy
        X_train, X_test, y_train, y_test = time_split(X, y)
        assert X_train.index[-1] < X_test.index[0]

    def test_sizes_correct(self, xy):
        X, y = xy
        X_train, X_test, y_train, y_test = time_split(X, y, test_frac=0.2)
        total = len(X)
        assert len(X_train) == int(total * 0.8)
        assert len(X_test) == total - int(total * 0.8)

    def test_raises_insufficient_data(self):
        X = pd.DataFrame({"a": [1, 2, 3]})
        y = pd.Series([0, 1, 0])
        with pytest.raises(ValueError, match="Not enough data"):
            time_split(X, y, test_frac=0.2)


class TestTrainModel:
    def test_returns_model_and_scaler(self, xy):
        X, y = xy
        X_train, _, y_train, _ = time_split(X, y)
        model, scaler = train_model(X_train, y_train)
        assert model is not None
        assert scaler is not None

    def test_model_can_predict_proba(self, xy, trained):
        X, y = xy
        model, scaler = trained
        _, X_test, _, _ = time_split(X, y)
        proba = model.predict_proba(scaler.transform(X_test))
        assert proba.shape == (len(X_test), 2)
        assert (proba >= 0).all() and (proba <= 1).all()


class TestEvaluate:
    def test_returns_expected_keys(self, xy, trained):
        X, y = xy
        model, scaler = trained
        _, X_test, _, y_test = time_split(X, y)
        metrics = evaluate(model, scaler, X_test, y_test)
        for key in ["accuracy", "auc", "classification_report", "feature_importance"]:
            assert key in metrics

    def test_accuracy_in_range(self, xy, trained):
        X, y = xy
        model, scaler = trained
        _, X_test, _, y_test = time_split(X, y)
        metrics = evaluate(model, scaler, X_test, y_test)
        assert 0 <= metrics["accuracy"] <= 1


class TestPredict:
    def test_signal_valid(self, feature_df, trained):
        model, scaler = trained
        result = predict(model, scaler, feature_df)
        assert result["signal"] in {"BUY", "HOLD", "SELL"}

    def test_probability_in_range(self, feature_df, trained):
        model, scaler = trained
        result = predict(model, scaler, feature_df)
        assert 0.0 <= result["probability_up"] <= 1.0

    def test_confidence_in_range(self, feature_df, trained):
        model, scaler = trained
        result = predict(model, scaler, feature_df)
        assert 0.0 <= result["confidence"] <= 1.0


class TestPersistence:
    def test_save_and_load(self, trained):
        model, scaler = trained
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.pkl")
            save_model(model, scaler, path)
            loaded_model, loaded_scaler = load_model(path)
            assert loaded_model is not None
            assert loaded_scaler is not None

    def test_load_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            load_model("/nonexistent/path/model.pkl")
