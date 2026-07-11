# Backend — Stock News Dashboard API

FastAPI service. Currently serves **mock data** so the whole app runs before any
real news/model is wired in.

## Run

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell
pip install -r requirements.txt
uvicorn main:app --reload
```

API runs at http://127.0.0.1:8000 — interactive docs at http://127.0.0.1:8000/docs

## What to replace in later phases

| Phase | File / function | Swap in |
|-------|-----------------|---------|
| 2 | `mock_data.generate_price_history` | `yfinance` live prices |
| 2 | `mock_data.generate_news` | Finnhub / NewsAPI feed |
| 3 | article `sentiment` | FinBERT scores |
| 4 | `mock_data.generate_signal` | trained XGBoost classifier |
| 6 | `/ws` loop | APScheduler-driven real refresh |
