# Signal Desk — News-Driven Stock Dashboard

A live web dashboard that reads market news, scores it, and shows a predicted
direction signal per stock. This is the **MVP scaffold**: it runs end-to-end on
**mock data** so you can see the whole app working before wiring in real feeds.

```
stock-news-dashboard/
├── backend/            FastAPI API + WebSocket
│   ├── main.py           routes: signals, news, history, analyze, model, backtest, /ws
│   ├── market_data.py    real NSE prices + momentum baseline (yfinance)
│   ├── news_api.py       real news feed (NewsAPI) + sentiment routing
│   ├── finbert.py        FinBERT sentiment (ProsusAI/finbert)
│   ├── features.py       technical feature engineering (shared)
│   ├── train_model.py    train + save the XGBoost model -> models/
│   ├── model.py          trained-model inference (serves /api/signals)
│   ├── backtest.py       walk-forward backtest (serves /api/backtest)
│   ├── store_data.py     persist prices/signals/news to MySQL
│   ├── config.py         NewsAPI key (env-overridable)
│   ├── db_config.py      MySQL connection (env-overridable)
│   ├── mock_data.py      fallbacks when a live source is unavailable
│   └── requirements.txt
└── frontend/           React + Vite + Recharts
    ├── package.json
    └── src/
        ├── App.jsx
        ├── api.js
        └── components/  SignalCard · NewsFeed · PriceChart · BacktestView · …
```

## Run it

### One-click (Windows)

Double-click **`start.bat`** in the project root. It opens the backend and
frontend in two terminal windows and launches the dashboard in your browser.
**`stop.bat`** shuts them down. (Edit the `MYSQL_PASSWORD` line in `start.bat`
if your MySQL root password differs; leave it blank to skip DB writes.)

> The dev servers only run while those two windows are open. If the page shows
> `ERR_CONNECTION_REFUSED`, the servers aren't running — just run `start.bat`.

### Manually (two terminals)

**Terminal 1 — backend**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
uvicorn main:app --reload      # http://127.0.0.1:8000
```

**Terminal 2 — frontend**
```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

Open **http://localhost:5173**. Signals update live over WebSocket; click a
signal card to filter the news feed and load that ticker's chart.

## Roadmap (from the plan)

| Phase | What changes | Status |
|-------|--------------|--------|
| 1 | Define direction signal + universe | ✅ shape locked |
| 1b | UI scaffold on mock data | ✅ done |
| 2 | Real NSE prices (yfinance) + momentum baseline | ✅ done |
| 3 | Indian news feed (NewsAPI) + FinBERT sentiment | ✅ done |
| 4 | Trained XGBoost signal model | ✅ done* |
| 5 | Walk-forward backtest view | ✅ done |
| **6** | **Scheduled live polling (APScheduler)** | ✅ done |
| — | MySQL analysis store (prices/signals/news) | ✅ bonus |

All six roadmap phases are complete. The scheduler (`scheduler.py`) polls every
`POLL_INTERVAL_MINUTES` (default 30): it warms the signal/news caches and, when
MySQL is configured, persists a fresh snapshot — so the `signals` time series
grows automatically. Status is at `GET /api/scheduler` and in the header badge.

\* The model pipeline is complete and deployed (features → train → serve →
backtest), but its **out-of-sample AUC is ≈0.50 — no reliable edge over the
momentum baseline**. That is the honest, expected result for predicting short-term
direction from technical features alone, and it is exactly what the Phase 5
backtest is built to reveal. The deliverable is the *validated pipeline*, not a
profitable model.

## Data status

- **Prices** — REAL, from NSE via Yahoo Finance (`yfinance`), in INR. Search any
  NSE symbol (RELIANCE, TCS, WIPRO, SBIN…); `.NS` is added automatically.
- **Signal** — a trained **XGBoost** classifier (5-day direction) over technical
  features, with the **momentum baseline** carried alongside for comparison.
  Reality check: out-of-sample it does **not** beat the baseline (AUC ≈0.50) —
  see the walk-forward backtest panel per ticker.
- **Forecast** — a forward 5-day **price projection** (`forecast.py`,
  `/api/forecast/{ticker}`) drawn on the chart: the signal's expected move sets
  the target, and a ±1σ volatility cone shows rising uncertainty. Quant-only
  (no LLM); a projection, not advice.
- **News** — REAL, live from [NewsAPI.org](https://newsapi.org) (`news_api.py`),
  tagged to the watchlist ticker it mentions. Falls back to mock if the API is
  unreachable. Free plan: ~100 req/day, cached 30 min.
- **Sentiment** — REAL **FinBERT** (`ProsusAI/finbert`, `finbert.py`) per headline,
  with an automatic keyword-lexicon fallback if the model can't load.

> ⚠️ Prices are real; predictions are a heuristic baseline. Not financial advice.
