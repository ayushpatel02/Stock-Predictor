"""SQLAlchemy ORM models for caching prediction results and backtest metrics."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from app.db.session import Base


class PredictionLog(Base):
    """Log of every prediction made — useful for tracking model drift."""

    __tablename__ = "prediction_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    signal = Column(String(10), nullable=False)
    probability_up = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    risk_score = Column(Integer, nullable=False)
    as_of = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class BacktestCache(Base):
    """Cache backtest results to avoid re-running expensive computations."""

    __tablename__ = "backtest_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True)
    total_return = Column(Float)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    win_rate = Column(Float)
    num_trades = Column(Integer)
    buy_hold_return = Column(Float)
    alpha = Column(Float)
    raw_json = Column(Text)  # Full result as JSON for API response
    run_at = Column(DateTime, server_default=func.now())
