"""
FastAPI backend for the news-driven stock dashboard.

Prices & signals: REAL Indian-market data via yfinance (see market_data.py).
News & sentiment: still mock (mock_data.py) until an Indian news feed is added.

Run:
    pip install -r requirements.txt
    uvicorn main:app --reload

Endpoints:
    GET  /api/health          -> liveness check
    GET  /api/watchlist       -> tracked NSE tickers
    GET  /api/signals         -> momentum-baseline signals over real prices
    GET  /api/news            -> latest scored news (mock)
    GET  /api/history/{tkr}   -> real daily closes + 5-day average (INR)
    GET  /api/suggestions     -> ranked ideas (heuristic, not advice)
    GET  /api/analyze/{tkr}   -> full snapshot for any NSE/BSE symbol
    WS   /ws                  -> pushes refreshed signals every few seconds
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import backtest
import forecast as price_forecast
import market_data
import mock_data
import model as signal_model
import news_api
import scheduler
import search as symbol_search

app = FastAPI(title="Stock News Dashboard API", version="0.2.0")

# Vite dev server runs on 5173; allow it (and localhost variants) to call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DISCLAIMER = "Educational prototype. Prices are real; the signal is a momentum baseline, not advice."


@app.on_event("startup")
def _start_scheduler() -> None:
    scheduler.start()


@app.on_event("shutdown")
def _stop_scheduler() -> None:
    scheduler.shutdown()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "market": "NSE/BSE (India)", "currency": "INR"}


@app.get("/api/watchlist")
def watchlist() -> list[dict]:
    return market_data.WATCHLIST


@app.get("/api/signals")
def signals() -> list[dict]:
    # Trained model when available; falls back to the momentum baseline internally.
    if signal_model.is_available():
        return signal_model.watchlist_signals()
    return market_data.watchlist_signals()


def _signals_for(items: list[dict]) -> list[dict]:
    """Model signals (or momentum fallback) for a list of {ticker, name} items."""
    if signal_model.is_available():
        return [signal_model.predict_signal(it["ticker"]) for it in items]
    return [market_data.momentum_signal(it["ticker"]) for it in items]


def _index_signals() -> list[dict]:
    return _signals_for(market_data.INDICES)


@app.get("/api/indices")
def indices() -> list[dict]:
    """Signals for the tracked market indices (NIFTY 50, BANK NIFTY, SENSEX, FIN NIFTY)."""
    return _index_signals()


@app.get("/api/top-stocks")
def top_stocks(limit: int = 10) -> list[dict]:
    """Ranked stock ideas from the broader universe — strongest signals first."""
    sigs = _signals_for(market_data.STOCK_UNIVERSE)

    def score(s: dict) -> float:
        sign = {"up": 1.0, "flat": 0.0, "down": -1.0}.get(s.get("direction"), 0.0)
        return sign * (s.get("confidence") or 0.5)

    return sorted(sigs, key=score, reverse=True)[:limit]


@app.get("/api/model")
def model_info() -> dict:
    """Metadata about the trained signal model (empty if not trained yet)."""
    return {"available": signal_model.is_available(), **signal_model.meta()}


@app.get("/api/backtest/{ticker}")
def backtest_ticker(ticker: str) -> dict:
    """Walk-forward backtest of the model on one ticker (strategy vs buy-&-hold)."""
    return backtest.run(ticker)


@app.get("/api/forecast/{ticker}")
def forecast_ticker(ticker: str) -> dict:
    """Forward price projection: predicted path + target + confidence cone."""
    return price_forecast.forecast(ticker)


@app.get("/api/scheduler")
def scheduler_status() -> dict:
    """Status of the background polling scheduler (Phase 6)."""
    return scheduler.status()


@app.get("/api/news")
def news(limit: int = 12) -> list[dict]:
    return news_api.fetch_news(limit=limit)


@app.get("/api/history/{ticker}")
def history(ticker: str, period: str = "6mo") -> dict:
    symbol = market_data.normalize_symbol(ticker)
    return {
        "ticker": symbol,
        "currency": market_data.CURRENCY,
        "points": market_data.fetch_history(symbol, period=period),
    }


@app.get("/api/search")
def search(q: str = "") -> list[dict]:
    """Keyword typeahead -> matching NSE/BSE stocks to pick from."""
    return symbol_search.search(q)


@app.get("/api/suggestions")
def suggestions() -> dict:
    """Ranked ideas from momentum signals over real prices. NOT advice."""
    ranked = mock_data.rank_suggestions(market_data.watchlist_signals())
    return {"disclaimer": DISCLAIMER, "ideas": ranked}


@app.get("/api/analyze/{ticker}")
def analyze(ticker: str, period: str = "6mo") -> dict:
    """Full predictive snapshot for ANY NSE/BSE symbol the user searches."""
    symbol = market_data.normalize_symbol(ticker)
    points = market_data.fetch_history(symbol, period=period)
    return {
        "ticker": symbol,
        "name": market_data.name_for(symbol),
        "currency": market_data.CURRENCY,
        "found": bool(points),
        "signal": (signal_model.predict_signal(symbol)
                   if signal_model.is_available()
                   else market_data.momentum_signal(symbol, points=points)),
        "history": points,
        "news": news_api.fetch_news(limit=8, ticker=symbol),
        "disclaimer": DISCLAIMER,
    }


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    """Push a fresh batch of signals every 5s so the UI feels live.

    Signals are cached (~45s TTL) in market_data, so this loop is cheap and does
    not hammer Yahoo — most ticks return the cached batch.
    """
    await websocket.accept()
    try:
        while True:
            data = await asyncio.to_thread(_index_signals)
            await websocket.send_json({"type": "signals", "data": data})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    except Exception:
        with contextlib.suppress(Exception):
            await websocket.close()
