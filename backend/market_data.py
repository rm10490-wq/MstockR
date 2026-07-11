"""
Real Indian-market price data via yfinance (NSE / BSE).

This replaces the mock price generator for Phase 2. NSE symbols use a ``.NS``
suffix (RELIANCE.NS), BSE uses ``.BO``. Prices are in INR.

The "signal" here is an honest **momentum baseline** (10-day vs 20-day average +
recent return), NOT a trained model. It's the Phase-1 baseline the real model
must beat. News + sentiment remain mock until we add an Indian news feed.
"""

from __future__ import annotations

import time

import yfinance as yf

# NSE large-caps to start with (liquid, heavily covered).
WATCHLIST = [
    {"ticker": "RELIANCE.NS", "name": "Reliance Industries"},
    {"ticker": "TCS.NS", "name": "Tata Consultancy Services"},
    {"ticker": "INFY.NS", "name": "Infosys"},
    {"ticker": "HDFCBANK.NS", "name": "HDFC Bank"},
    {"ticker": "ICICIBANK.NS", "name": "ICICI Bank"},
]

CURRENCY = "INR"

# Tiny in-memory cache so we don't hammer Yahoo on every WebSocket tick.
_CACHE: dict[str, tuple[float, object]] = {}
_TTL = 60.0  # seconds


def _cache_get(key: str):
    hit = _CACHE.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    return None


def _cache_put(key: str, value, ttl: float = _TTL) -> None:
    _CACHE[key] = (time.time() + ttl, value)


# Indian market indices (Yahoo symbols). These carry a "^" prefix and must NOT
# get a ".NS" suffix appended.
INDICES = [
    {"ticker": "^NSEI", "name": "NIFTY 50"},
    {"ticker": "^NSEBANK", "name": "NIFTY BANK"},
    {"ticker": "^BSESN", "name": "SENSEX"},
    {"ticker": "^CNXFIN", "name": "NIFTY FIN SERVICE"},
]

# Broader liquid-stock universe ranked for the "top suggested stocks" list.
STOCK_UNIVERSE = [
    {"ticker": "RELIANCE.NS", "name": "Reliance Industries"},
    {"ticker": "TCS.NS", "name": "Tata Consultancy Services"},
    {"ticker": "INFY.NS", "name": "Infosys"},
    {"ticker": "HDFCBANK.NS", "name": "HDFC Bank"},
    {"ticker": "ICICIBANK.NS", "name": "ICICI Bank"},
    {"ticker": "SBIN.NS", "name": "State Bank of India"},
    {"ticker": "LT.NS", "name": "Larsen & Toubro"},
    {"ticker": "ITC.NS", "name": "ITC"},
    {"ticker": "HINDUNILVR.NS", "name": "Hindustan Unilever"},
    {"ticker": "BHARTIARTL.NS", "name": "Bharti Airtel"},
]

_NAMES = {i["ticker"]: i["name"] for i in (WATCHLIST + INDICES + STOCK_UNIVERSE)}


def is_index(symbol: str) -> bool:
    return symbol.strip().startswith("^")


def normalize_symbol(symbol: str) -> str:
    """User types 'TCS' -> 'TCS.NS'. Leaves suffixes (.NS/.BO) and ^indices alone."""
    s = symbol.upper().strip()
    if not s:
        return s
    if s.startswith("^"):   # index symbol, e.g. ^NSEI — never append .NS
        return s
    if "." in s:
        return s
    return f"{s}.NS"


def name_for(symbol: str) -> str:
    symbol = normalize_symbol(symbol)
    return _NAMES.get(symbol, symbol)


def fetch_history(symbol: str, period: str = "6mo") -> list[dict]:
    """Real daily closes + a trailing 5-day average. Empty list on failure."""
    symbol = normalize_symbol(symbol)
    key = f"hist:{symbol}:{period}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    try:
        df = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=True)
    except Exception:
        return []

    if df is None or df.empty or "Close" not in df:
        return []
    df = df.dropna(subset=["Close"])

    points: list[dict] = []
    window: list[float] = []
    for ts, row in df.iterrows():
        close = float(row["Close"])
        window.append(close)
        if len(window) > 5:
            window.pop(0)
        sma = sum(window) / len(window)
        points.append(
            {
                "date": ts.date().isoformat(),
                "close": round(close, 2),
                "sma": round(sma, 2),
            }
        )
    _cache_put(key, points)
    return points


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def momentum_signal(symbol: str, points: list[dict] | None = None) -> dict:
    """Honest momentum baseline over REAL prices. Not a trained model."""
    symbol = normalize_symbol(symbol)
    pts = points if points is not None else fetch_history(symbol)
    closes = [p["close"] for p in pts]

    if len(closes) < 15:
        return {
            "ticker": symbol,
            "name": name_for(symbol),
            "direction": "flat",
            "confidence": 0.5,
            "expected_change_pct": 0.0,
            "horizon": "1w",
            "last_price": closes[-1] if closes else None,
            "currency": CURRENCY,
            "basis": "insufficient-data",
        }

    last = closes[-1]
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else ma10
    ret5 = (last - closes[-6]) / closes[-6] * 100.0  # % over last 5 sessions
    spread = (ma10 - ma20) / ma20 * 100.0            # short vs longer trend

    strength = spread + ret5 * 0.3
    if strength > 0.4:
        direction = "up"
    elif strength < -0.4:
        direction = "down"
    else:
        direction = "flat"

    confidence = round(_clamp(0.5 + abs(strength) / 10.0, 0.5, 0.75), 3)
    # Projection derived from the SAME strength that sets direction, so the sign
    # of the expected move always agrees with the arrow shown.
    expected = round(_clamp(strength * 0.4, -3.0, 3.0), 2)

    return {
        "ticker": symbol,
        "name": name_for(symbol),
        "direction": direction,
        "confidence": confidence,
        "expected_change_pct": expected,
        "horizon": "1w",
        "last_price": round(last, 2),
        "currency": CURRENCY,
        "basis": "momentum-baseline: MA10 vs MA20 + 5-day return",
    }


def watchlist_signals() -> list[dict]:
    key = "signals:watchlist"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    signals = [momentum_signal(item["ticker"]) for item in WATCHLIST]
    _cache_put(key, signals, ttl=45.0)
    return signals
