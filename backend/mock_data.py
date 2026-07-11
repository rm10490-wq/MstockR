"""
Mock data source for the dashboard MVP.

Everything here is fake but shaped exactly like the real thing will be, so the
frontend never has to change when we swap these functions for live news + a real
model in later phases:

    Phase 2  -> replace generate_price_history() with yfinance
    Phase 3  -> replace article "sentiment" with FinBERT scores
    Phase 4  -> replace generate_signal() with the trained classifier
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

# NSE large-caps — kept in sync with market_data.WATCHLIST so mock news refers
# to the same Indian companies we show real prices for.
WATCHLIST = [
    {"ticker": "RELIANCE.NS", "name": "Reliance Industries"},
    {"ticker": "TCS.NS", "name": "Tata Consultancy Services"},
    {"ticker": "INFY.NS", "name": "Infosys"},
    {"ticker": "HDFCBANK.NS", "name": "HDFC Bank"},
    {"ticker": "ICICIBANK.NS", "name": "ICICI Bank"},
]

DIRECTIONS = ["up", "flat", "down"]

_EVENT_TYPES = ["earnings", "guidance", "analyst", "product", "m&a", "lawsuit", "macro"]

_HEADLINE_TEMPLATES = {
    "earnings": [
        "{name} beats Q{q} earnings estimates on strong demand",
        "{name} misses revenue forecast despite margin gains",
        "{name} posts record quarterly profit, shares in focus",
    ],
    "guidance": [
        "{name} raises full-year guidance above Wall Street view",
        "{name} cuts outlook, citing softer consumer spending",
    ],
    "analyst": [
        "Analysts upgrade {name} to Buy on improving fundamentals",
        "{name} downgraded as valuation concerns mount",
    ],
    "product": [
        "{name} unveils new product line to positive early reviews",
        "{name} delays flagship launch, raising near-term concerns",
    ],
    "m&a": [
        "{name} explores acquisition to expand market share",
        "Regulators scrutinize {name} over proposed deal",
    ],
    "lawsuit": [
        "{name} faces class-action suit over disclosures",
        "{name} settles regulatory probe, removing an overhang",
    ],
    "macro": [
        "Rate-cut hopes lift megacap tech including {name}",
        "Inflation surprise pressures growth names such as {name}",
    ],
}

_SOURCES = ["Reuters", "Bloomberg", "CNBC", "MarketWatch", "SEC 8-K", "Finnhub"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def name_for(ticker: str) -> str:
    """Company name if we know it, otherwise just echo the ticker."""
    for item in WATCHLIST:
        if item["ticker"] == ticker:
            return item["name"]
    return ticker


def generate_signal(ticker: str) -> dict:
    """A fake model prediction. Shape matches what the real classifier will emit."""
    direction = random.choices(DIRECTIONS, weights=[0.42, 0.2, 0.38])[0]
    confidence = round(random.uniform(0.51, 0.78), 3)
    change_pct = {
        "up": round(random.uniform(0.3, 2.4), 2),
        "flat": round(random.uniform(-0.25, 0.25), 2),
        "down": round(-random.uniform(0.3, 2.4), 2),
    }[direction]
    return {
        "ticker": ticker,
        "direction": direction,
        "confidence": confidence,
        "expected_change_pct": change_pct,
        # Per-horizon, per the plan's Diagram 02 (day = strongest signal).
        "horizon": random.choice(["1d", "1w", "1m"]),
        "news_score": round(random.uniform(-1, 1), 2),
        "updated_at": _now().isoformat(),
    }


def generate_signals() -> list[dict]:
    return [generate_signal(item["ticker"]) for item in WATCHLIST]


def rank_suggestions(signals: list[dict]) -> list[dict]:
    """Turn raw signals into a ranked 'ideas' list.

    Score favours confident UP calls and penalises DOWN calls. This is a
    heuristic ranking of MODEL OUTPUT, not investment advice — in the real
    system this is where risk-adjusted position logic would live.
    """
    def score(sig: dict) -> float:
        sign = {"up": 1.0, "flat": 0.0, "down": -1.0}[sig["direction"]]
        return round(sign * sig["confidence"], 4)

    ranked = sorted(signals, key=score, reverse=True)
    for rank, sig in enumerate(ranked, start=1):
        sig = sig  # signals are dicts; annotate in place
        sig["rank"] = rank
        sig["score"] = score(sig)
        sig["idea"] = (
            "watch — bullish signal" if sig["direction"] == "up"
            else "avoid / short candidate" if sig["direction"] == "down"
            else "no clear edge"
        )
    return ranked


def generate_news(limit: int = 12, ticker: str | None = None) -> list[dict]:
    """Fake news feed with per-article sentiment (FinBERT stand-in).

    If ``ticker`` is given, every article is about that ticker (used by the
    search / analyze endpoint); otherwise articles span the watchlist.
    """
    articles = []
    for i in range(limit):
        if ticker:
            stock = {"ticker": ticker, "name": name_for(ticker)}
        else:
            stock = random.choice(WATCHLIST)
        event = random.choice(_EVENT_TYPES)
        template = random.choice(_HEADLINE_TEMPLATES[event])
        headline = template.format(name=stock["name"], q=random.randint(1, 4))
        sentiment = round(random.uniform(-1, 1), 2)
        articles.append(
            {
                "id": f"news-{i}-{random.randint(1000, 9999)}",
                "ticker": stock["ticker"],
                "headline": headline,
                "source": random.choice(_SOURCES),
                "event_type": event,
                "sentiment": sentiment,
                "sentiment_label": (
                    "positive" if sentiment > 0.15
                    else "negative" if sentiment < -0.15
                    else "neutral"
                ),
                # "surprise" is the real edge (plan Phase 3): novel vs. rehashed news.
                "surprise": round(random.uniform(0, 1), 2),
                "published_at": (_now() - timedelta(minutes=random.randint(1, 600))).isoformat(),
            }
        )
    articles.sort(key=lambda a: a["published_at"], reverse=True)
    return articles


def generate_price_history(ticker: str, days: int = 60) -> list[dict]:
    """Fake OHLC-ish daily closes + the model's predicted next-day close."""
    base = 100 + (hash(ticker) % 300)
    price = float(base)
    history = []
    start = _now() - timedelta(days=days)
    for d in range(days):
        # gentle random walk with a mild trend + sine wobble
        drift = math.sin(d / 7) * 1.5
        price = max(5.0, price + random.uniform(-2.5, 2.6) + drift * 0.3)
        day = start + timedelta(days=d)
        history.append(
            {
                "date": day.date().isoformat(),
                "close": round(price, 2),
                # what the model *predicted* the close would be (for accuracy view)
                "predicted": round(price + random.uniform(-2, 2), 2),
            }
        )
    return history
