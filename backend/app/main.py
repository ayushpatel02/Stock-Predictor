"""
FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import backtest, market, screener, stocks
from app.config import settings
from app.data.universe import all_symbols
from app.db.models import Base
from app.db.session import engine

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Create DB tables on startup (idempotent)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Nifty 50 Stock Predictor",
    description=(
        "Decision-support tool for Indian equities. "
        "NOT financial advice — predictions are probabilistic."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router)
app.include_router(backtest.router)
app.include_router(market.router)
app.include_router(screener.router)


@app.get("/", tags=["health"])
async def health_check():
    """API health check."""
    return {"status": "ok", "service": "stock-predictor", "version": "1.0.0"}


@app.get("/universe", tags=["health"])
async def get_universe():
    """Return the list of all supported stock symbols."""
    return {"symbols": all_symbols(), "count": len(all_symbols())}
