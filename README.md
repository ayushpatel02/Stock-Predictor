# Nifty 50 Stock Predictor

A hybrid ML-powered decision-support tool for Indian equity markets. Combines technical indicators, fundamentals, and walk-forward backtesting to produce BUY/HOLD/SELL signals with calibrated probability scores and risk ratings.

**This is not financial advice.** Predictions are probabilistic. Past performance does not guarantee future results. Always do your own research before making investment decisions.

---

## What it does

- Fetches OHLCV data for all **Nifty 50** constituents via yfinance (15-min delayed)
- Computes 25+ technical indicators (RSI, MACD, Bollinger Bands, ATR, OBV, moving averages)
- Trains an **XGBoost binary classifier** per stock: "Will this stock rise >2% in 5 trading days?"
- Exposes predictions via a **FastAPI** REST API consumed by a **React** dashboard
- Includes honest **walk-forward backtesting** (no future leakage, no random CV splits on time series)
- Shows **risk scores** (1-10) from ATR%, beta, and debt-to-equity

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, XGBoost, scikit-learn, pandas |
| Data | yfinance (free, 15-min delayed) |
| Storage | SQLite (dev) / Postgres (prod) |
| Cache | In-memory / Redis (optional) |
| Frontend | React 18, Vite, Tailwind CSS, Recharts, Axios |
| Deployment | Railway/Render (backend), Vercel (frontend) |
| CI/CD | GitHub Actions |

---

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Train models for 5 stocks first (quick test)
python -m app.scripts.train_all --symbols RELIANCE TCS INFY HDFCBANK ICICIBANK

# Train all 50 (takes ~15-30 min with network)
python -m app.scripts.train_all

# Start API
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # set VITE_API_URL=http://localhost:8000
npm run dev
# Open http://localhost:5173
```

### Docker (both services)

```bash
docker-compose up --build
# API: http://localhost:8000
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/universe` | All supported symbols |
| GET | `/market/overview` | Nifty, BankNifty, VIX, Sensex |
| GET | `/stocks/{symbol}` | Fundamentals + 30d OHLCV |
| GET | `/stocks/{symbol}/predict` | BUY/HOLD/SELL signal + risk score |
| POST | `/backtest/{symbol}` | Walk-forward backtest on 5y data |

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

Tests use synthetic data — no network calls required.

---

## Deployment

### Backend → Railway / Render

1. Connect your GitHub repo
2. Set root directory to `backend/`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Set environment variable: `DATABASE_URL` (Postgres connection string)

### Frontend → Vercel

1. Import GitHub repo, set framework to Vite
2. Root directory: `frontend/`
3. Set env var: `VITE_API_URL=https://your-backend.railway.app`

---

## Roadmap

- [ ] **Sentiment**: Finnhub news + VADER (stub in `app/features/sentiment.py`)
- [ ] **Fundamental features in ML**: wire P/E, ROE, D/E into FEATURE_COLS
- [ ] **All NSE expansion**: swap `ACTIVE_UNIVERSE` in `universe.py`
- [ ] **Alerts**: email/webhook on signal change
- [ ] **Multi-class target**: BUY/HOLD/SELL instead of binary up/down
- [ ] **Sector analysis**: group signals by GICS sector
- [ ] **Portfolio optimizer**: Kelly criterion or mean-variance given multiple signals

---

## Known Limitations / Deliberate Stubs

| Area | Status | Notes |
|---|---|---|
| Sentiment | Stub (returns 0.0) | Ready to plug in VADER + Finnhub |
| Fundamentals in ML | Not in FEATURE_COLS | Extraction works; add to FEATURE_COLS when ready |
| Market context features | Not in FEATURE_COLS | Fetch logic in `market_context.py` |
| Short selling | Not implemented | Long-only backtest |
| Intraday data | Not used | Daily candles only (yfinance free tier) |
| Hyperparameter tuning | Sane defaults | Tune per-stock with TimeSeriesSplit CV |

---

## Disclaimer

This software is for educational and research purposes only. The authors are not registered financial advisors. Nothing in this application constitutes financial advice, investment recommendations, or solicitation to buy or sell securities. Use at your own risk.
