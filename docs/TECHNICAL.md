# Signal Desk — Technical Documentation

**Project:** News-driven NSE stock dashboard
**Version:** 0.6 (Phases 1–6 complete)
**Audience:** developers, maintainers, reviewers

---

## 1. Overview

Signal Desk is a full-stack web application that ingests **real Indian-market
data**, produces a **direction signal** per stock, and validates that signal with
a **walk-forward backtest**. It runs end-to-end on live data:

- **Prices** — real NSE/BSE daily data via Yahoo Finance (`yfinance`)
- **News** — real headlines via NewsAPI.org
- **Sentiment** — FinBERT (`ProsusAI/finbert`) per headline
- **Signal** — a trained XGBoost classifier, with a momentum baseline for comparison
- **Backtest** — walk-forward, no look-ahead, strategy vs buy-&-hold
- **Persistence** — snapshots written to MySQL for offline analysis
- **Automation** — a background scheduler refreshes and persists on an interval

> ⚠️ **Honesty note (carried throughout):** prices are real, but the model has
> **no proven predictive edge** (out-of-sample AUC ≈ 0.50). The system is an
> honest research scaffold, not a profitable trading product, and every layer
> surfaces that fact rather than hiding it.

---

## 2. Technology stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend framework | FastAPI | 0.115.6 |
| ASGI server | Uvicorn | 0.34.0 |
| Market data | yfinance | 1.5.1 |
| Numerics | pandas / numpy | 2.3.3 / 2.2.6 |
| News | NewsAPI.org (REST) | Developer plan |
| Sentiment model | transformers + torch (FinBERT) | 5.13.0 / 2.13.0 |
| Signal model | xgboost + scikit-learn | 3.2.0 / 1.7.2 |
| Scheduler | APScheduler | 3.11.3 |
| Database | MySQL + SQLAlchemy + PyMySQL | 8.x / 2.0.51 / 1.2.0 |
| Frontend | React + Vite + Recharts | 18 / 6 / 2.15 |
| Language runtimes | Python 3.10, Node 24 | — |

---

## 3. System architecture

```
                         ┌────────────────────────────────────────────┐
   Browser (React/Vite)  │  http://localhost:5173                      │
   ┌───────────────┐     │  SignalCard · PriceChart · NewsFeed ·       │
   │  App.jsx      │◄────┤  SearchBar (typeahead) · BacktestView       │
   │  state + WS   │     └───────────────┬─────────────────────────────┘
   └──────┬────────┘   Vite dev proxy    │  /api/*  and  /ws
          │  fetch + WebSocket           ▼
          │              ┌────────────────────────────────────────────┐
          └─────────────►│  FastAPI backend  http://127.0.0.1:8000     │
                         │  main.py  (routes + WebSocket + lifecycle)  │
                         └───┬───────┬───────┬────────┬────────┬───────┘
                             │       │       │        │        │
              market_data ◄──┘       │       │        │        └──► scheduler
              (yfinance)             │       │        │             (APScheduler)
                                     │       │        │                  │
              news_api ◄─────────────┘       │        │                  ▼
              (NewsAPI) ──► finbert           │        │            store_data
                            (FinBERT)         │        │            (MySQL upsert)
                                              │        │
              model ◄─── features ◄───────────┘        └──► backtest
              (XGBoost infer)  (shared FE)                  (walk-forward)
                    ▲                                              │
                    └──────────── models/signal_xgb.json ◄─────────┘
                                  (trained by train_model.py)

   External services: Yahoo Finance · NewsAPI.org · HuggingFace Hub · MySQL
```

**Two processes:** the FastAPI backend (`:8000`) and the Vite dev server
(`:5173`). Vite proxies `/api` and `/ws` to the backend, so the browser makes
same-origin calls with no CORS friction in development.

---

## 4. Backend modules

| File | Responsibility |
|------|----------------|
| `main.py` | FastAPI app, all HTTP routes, the `/ws` WebSocket, startup/shutdown hooks |
| `market_data.py` | Real prices + history via yfinance; the **momentum baseline** signal; 45–60 s caches |
| `news_api.py` | Real news via NewsAPI; maps to article shape; routes sentiment to FinBERT/lexicon; 30-min cache; mock fallback |
| `finbert.py` | Lazy-loaded FinBERT model; `score(text) -> (sentiment, label)` |
| `features.py` | **Shared** technical feature engineering (13 features) + label/forward-return helpers |
| `train_model.py` | Fetches 5y × 15 tickers, trains XGBoost, chronological hold-out, saves to `models/` |
| `model.py` | Loads the trained model; serves signals in the API shape; carries the baseline alongside; 60 s cache |
| `backtest.py` | Walk-forward backtest per ticker (no look-ahead); equity curve + stats; 30-min cache |
| `search.py` | Keyword → matching NSE/BSE stocks via Yahoo search; 15-min cache |
| `scheduler.py` | APScheduler job: warm caches + persist to MySQL every N minutes; status tracking |
| `store_data.py` | Create schema + upsert prices/signals/news into MySQL |
| `config.py` | NewsAPI key, cache TTL, scheduler settings (all env-overridable) |
| `db_config.py` | MySQL connection settings + SQLAlchemy URL builders (env-driven) |
| `mock_data.py` | Deterministic fake data used as a fallback when a live source is down |

**Design principle — never break the dashboard:** every live integration
degrades gracefully. FinBERT unavailable → lexicon sentiment. NewsAPI down →
mock news. Model missing → momentum baseline. MySQL unset → scheduler still warms
caches. Failures are logged/surfaced, never fatal to a request.

---

## 5. API reference

Base URL: `http://127.0.0.1:8000` (or via the Vite proxy at `:5173`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness + market/currency info |
| GET | `/api/watchlist` | Tracked NSE tickers |
| GET | `/api/signals` | Model signals for the watchlist (baseline carried alongside) |
| GET | `/api/model` | Trained-model metadata + out-of-sample metrics |
| GET | `/api/backtest/{ticker}` | Walk-forward backtest: equity curve + stats |
| GET | `/api/scheduler` | Background scheduler status (last run, next run, detail) |
| GET | `/api/search?q=` | Keyword typeahead → matching NSE/BSE stocks |
| GET | `/api/suggestions` | Ranked "ideas" derived from signals (not advice) |
| GET | `/api/news?limit=` | Live news feed with sentiment |
| GET | `/api/history/{ticker}?period=` | Real daily closes + 5-day SMA |
| GET | `/api/analyze/{ticker}?period=` | Full snapshot: signal + history + news for any symbol |
| WS | `/ws` | Pushes a fresh signal batch every 5 s |

### Representative payloads

**`GET /api/signals`** (one element):
```json
{
  "ticker": "RELIANCE.NS", "name": "Reliance Industries",
  "direction": "flat", "confidence": 0.518, "expected_change_pct": 0.11,
  "horizon": "1w", "last_price": 1307.8, "currency": "INR",
  "prob_up": 0.518, "basis": "XGBoost classifier (trained, 5d horizon)",
  "model": "xgboost", "baseline_direction": "down"
}
```

**`GET /api/backtest/{ticker}`**:
```json
{
  "ticker": "RELIANCE.NS", "found": true,
  "points": [{"date": "2022-09-26", "strategy": 0.9967, "buyhold": 0.9967}, ...],
  "stats": {"accuracy": 0.5294, "n_predictions": 187, "trades": 115,
            "strategy_return_pct": 49.34, "buyhold_return_pct": 18.11,
            "horizon_days": 5, "retrains": 47, "start": "...", "end": "..."},
  "basis": "walk-forward, non-overlapping, periodic retrain, no look-ahead"
}
```

---

## 6. The signal model (Phase 4)

### 6.1 Features (`features.py`)
Thirteen scale-free technical features, so one pooled model works across tickers
of any price level:

`ret_1, ret_5, ret_10, ret_20` (returns) · `close_ma5, close_ma10, close_ma20,
ma5_ma20` (moving-average ratios) · `vol_10, vol_20` (volatility) · `rsi_14`
(RSI/100) · `mom_10` (momentum) · `vol_chg_5` (volume change).

The **same** `build_features()` is used for training, live inference, and
backtesting — eliminating train/serve skew.

### 6.2 Label
Binary: `1` if the close **5 trading days ahead** is higher than today, else `0`.

### 6.3 Training (`train_model.py`)
- **Data:** 5 years × 15 liquid NSE tickers (~18k rows)
- **Split:** per-ticker **chronological** hold-out (earliest 80% train, latest
  20% test). No shuffling — shuffling would leak the future.
- **Model:** `XGBClassifier` (250 trees, depth 4, lr 0.05, subsample/colsample
  0.85, L2 = 1.5).
- **Artifacts:** `models/signal_xgb.json` + `models/model_meta.json` (features,
  horizon, metrics, feature importances).

### 6.4 Measured result (honest)
```
OUT-OF-SAMPLE  accuracy: 0.496   AUC: 0.495   (majority-class baseline: 0.516)
```
The model is **at chance / below the majority baseline**. This is the expected,
well-documented reality of predicting short-horizon direction from technicals
alone. The numbers were **not** tuned to look better; the deliverable is a
correct, leakage-free pipeline that tells the truth.

### 6.5 Inference (`model.py`)
Fetches recent OHLCV → `build_features()` → `predict_proba` on the latest row →
`P(up)`. Mapped to the UI's three states with a deadband: `≥0.55 up`, `≤0.45
down`, else `flat`. Confidence = distance from 0.5. The momentum baseline is
computed alongside as `baseline_direction`. Results cached 60 s so the 5 s
WebSocket push doesn't hammer yfinance.

---

## 7. Walk-forward backtest (Phase 5)

`backtest.py` evaluates the model on **one ticker** without look-ahead:

1. Build features + 5-day forward label over ~5y.
2. Step forward in **non-overlapping 5-day chunks**.
3. At each chunk, (re)train on **only rows whose label is already realized**
   (`index ≤ t − horizon`) — this is the anti-leakage guarantee. Retrain every 4
   chunks (~monthly) for speed.
4. Simulate a **long/flat** strategy (long when the model says "up", else cash),
   compounding realized chunk returns; compare to buy-&-hold.
5. Return an equity curve + stats (directional accuracy, strategy vs buy-&-hold
   return, trades). Cached 30 min. Typical response ~6 s.

**Interpretation caveat (also shown in the UI):** a long/flat strategy can beat
buy-&-hold simply by sitting out drawdowns, even at ~50% accuracy. That is **not**
evidence of edge. No transaction costs are modelled. Single-ticker results are
noisy (RELIANCE looked great, INFY lost money) — consistent with a model whose
pooled AUC ≈ 0.50.

---

## 8. Data integrations

### 8.1 Prices — yfinance
`market_data.fetch_history()` pulls `period="6mo"` daily bars (auto-adjusted, INR)
and computes a trailing 5-day SMA. `normalize_symbol()` appends `.NS` when no
suffix is given. 60 s cache.

### 8.2 News — NewsAPI + sentiment
`news_api.fetch_news()` issues **one** combined watchlist query (to respect the
~100 req/day free quota), tags each article to the mentioned company via alias
matching, and scores sentiment. Sentiment routing (`_analyze_sentiment`):
**FinBERT if loaded, else the keyword lexicon** — every article records which
engine scored it in `basis`. 30-min cache; mock fallback on any failure.

### 8.3 Sentiment — FinBERT
`finbert.py` lazy-loads `ProsusAI/finbert` (~420 MB, downloaded once from
HuggingFace, then offline). `score()` softmaxes the logits and returns
`P(positive) − P(negative)` plus the arg-max label. Thread-safe singleton; the
backend still starts instantly (first news request pays the load).

### 8.4 Search — Yahoo Finance
`search.py` calls Yahoo's public `finance/search`, keeps `EQUITY` quotes on
NSE/BSE, dedupes by base symbol preferring the `.NS` listing. 15-min cache.

---

## 9. Database (MySQL analysis store)

Created automatically by `store_data.py` (database `stockdash`).

**`prices`** — real daily closes
| column | type | notes |
|--------|------|-------|
| ticker | VARCHAR(20) | PK part |
| date | DATE | PK part |
| close, sma | DECIMAL(14,2) | |
| currency | VARCHAR(8) | default INR |

**`signals`** — append-only signal time series
| column | type | notes |
|--------|------|-------|
| id | BIGINT AI | PK |
| ticker, captured_at | | indexed together |
| direction, confidence, expected_change_pct, last_price, currency, basis | | |

**`news`** — deduped headlines + sentiment
| column | type | notes |
|--------|------|-------|
| id | BIGINT AI | PK |
| ticker, url_hash | | `UNIQUE(ticker, url_hash)` |
| headline, source, event_type, sentiment, sentiment_label, surprise, published_at, url | | |

**Idempotency:** `prices`/`news` use `INSERT … ON DUPLICATE KEY UPDATE`;
`signals` is append-only (so you can trend the signal over time). `url_hash` is a
**SHA-1** of the URL (not Python's per-process-salted `hash()`, which previously
caused duplicate rows — fixed).

---

## 10. Scheduler (Phase 6)

`scheduler.py` runs an APScheduler `BackgroundScheduler` started in the FastAPI
`startup` hook. Every `POLL_INTERVAL_MINUTES` (default 30) it:
1. Warms the model-signal + news caches.
2. If `MYSQL_PASSWORD` is set, persists a fresh snapshot via `store_data.store()`.

Status (runs, last_run, last_status, last_detail, next_run) is exposed at
`/api/scheduler` and shown in the header "synced Xm ago" badge. Jobs are
`coalesce=True, max_instances=1`; failures are recorded and non-fatal.

---

## 11. Caching summary

| Data | TTL | Where |
|------|-----|-------|
| Price history | 60 s | `market_data._CACHE` |
| Watchlist momentum signals | 45 s | `market_data` |
| Model signals | 60 s | `model._SIG_CACHE` |
| News (per query) | 30 min | `news_api._CACHE` |
| Backtest (per ticker) | 30 min | `backtest._CACHE` |
| Symbol search (per query) | 15 min | `search._CACHE` |

Caching protects the free NewsAPI quota, keeps the 5 s WebSocket cheap, and makes
the ~6 s backtest feel instant on repeat views.

---

## 12. Configuration (environment variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEWSAPI_KEY` | (bundled dev key) | NewsAPI authentication |
| `SCHEDULER_ENABLED` | `1` | Master switch for polling |
| `POLL_INTERVAL_MINUTES` | `30` | Poll cadence |
| `POLL_INITIAL_DELAY` | `20` | Seconds before first poll |
| `MYSQL_HOST/PORT/USER/PASSWORD/DB` | `127.0.0.1/3306/root/""/stockdash` | DB connection |
| `HF_HUB_DISABLE_SYMLINKS_WARNING` | — | Quiet a Windows HF cache warning |

Secrets are read from the environment; nothing sensitive is hard-committed except
a bundled NewsAPI **dev** key (documented as replaceable).

---

## 13. Frontend architecture

- **`App.jsx`** — owns all state (watchlist, signals, news, selected ticker,
  history, model info, scheduler status). Loads initial data, opens the `/ws`
  WebSocket for live signals, polls news (15 s) and scheduler (30 s).
- **Components** — `SignalCard`, `TopPick`, `PriceChart` (Recharts), `NewsFeed`,
  `SearchBar` (debounced typeahead with keyboard nav), `BacktestView` (equity
  curve + stat tiles).
- **`api.js`** — thin fetch layer; all calls go through the Vite proxy.
- **Styling** — a single `index.css` with CSS custom properties (dark theme).

---

## 14. Setup & run

```bash
# Backend
cd backend
pip install -r requirements.txt          # full dependency set (Phases 1–6)
python train_model.py                     # one-time: fetch data + train the model
# with auto-persistence + scheduler:
setx-equivalent: $env:MYSQL_PASSWORD="…"  # PowerShell; or export in bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

**Environment note:** on some sandboxed shells, outbound network for background
commands is blocked — installs and any network calls must run with the sandbox
disabled. The app itself uses the system Python 3.10 which already carries the
dependencies.

---

## 15. Known limitations

1. **No predictive edge** — the model does not beat the baseline out-of-sample
   (AUC ≈ 0.50). By design the app proves this rather than hiding it.
2. **Sentiment not yet a model feature** — FinBERT scores are displayed but not
   fed into the signal model. This is the most promising next experiment.
3. **NewsAPI free tier** — ~100 req/day, up to ~24 h article lag, localhost only;
   a freshly-searched small-cap may show market-wide news rather than
   company-specific.
4. **Backtest costs** — no transaction costs / slippage / risk-free rate on cash.
5. **In-process scheduler** — resets on server restart; not a distributed cron.
6. **Single-node dev setup** — no auth, no HTTPS, no production hardening.

---

## 16. Suggested next steps

- Add FinBERT sentiment (and its trend) as model features; re-measure AUC.
- Model transaction costs in the backtest; add Sharpe/max-drawdown.
- Persist model signals (with `prob_up`) to MySQL, not just the baseline.
- Cross-validate across market regimes; add per-ticker vs pooled comparison.
- Production: containerize, add auth, move secrets to a vault, schedule via cron.
```
