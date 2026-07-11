"""
Real news feed via NewsAPI.org (Phase 3, news half).

Replaces mock_data.generate_news() with live articles about the watchlist
companies. NewsAPI does not provide sentiment or an "event type", so we add:

  * sentiment      -> a finance keyword-lexicon score in [-1, 1]  (HEURISTIC,
                      an honest stand-in for FinBERT, which is Phase 3's model half)
  * sentiment_label-> positive / neutral / negative
  * event_type     -> inferred from headline keywords (earnings, analyst, m&a, ...)
  * surprise       -> recency x event-strength novelty proxy in [0, 1]

The output shape is byte-for-byte what the frontend NewsFeed already expects, so
nothing in the UI changes. On ANY failure (rate limit, network, no key) we fall
back to mock_data.generate_news() so the dashboard never shows an empty feed.

Free "Developer" plan notes: ~100 requests/day, results may lag ~24h, localhost
only. We cache aggressively (config.NEWS_CACHE_TTL) to respect the quota.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import config
import finbert
import mock_data

_ENDPOINT = "https://newsapi.org/v2/everything"

# ticker -> query terms used to find articles about that company.
_COMPANY_QUERY = {
    "RELIANCE.NS": "Reliance Industries",
    "TCS.NS": "Tata Consultancy Services",
    "INFY.NS": "Infosys",
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
}

# ticker -> lowercase aliases as they actually appear in headlines. Order matters:
# longer / more specific names are checked first so "hdfc bank" wins over "hdfc".
_COMPANY_ALIASES = {
    "RELIANCE.NS": ("reliance industries", "reliance", "ril", "jio"),
    "TCS.NS": ("tata consultancy", "tcs"),
    "INFY.NS": ("infosys", "infy"),
    "HDFCBANK.NS": ("hdfc bank", "hdfcbank", "hdfc"),
    "ICICIBANK.NS": ("icici bank", "icicibank", "icici"),
}

# --- tiny finance sentiment lexicon (HEURISTIC, not a trained model) -----------
_POS_WORDS = {
    "beat", "beats", "surge", "surges", "jump", "jumps", "rally", "rallies",
    "gain", "gains", "rise", "rises", "record", "profit", "growth", "upgrade",
    "upgrades", "outperform", "strong", "boost", "boosts", "wins", "win",
    "raise", "raises", "raised", "bullish", "top", "tops", "soar", "soars",
    "recovery", "expands", "expansion", "approval", "approved", "dividend",
    "high", "higher", "optimistic", "positive", "buy", "rebound",
}
_NEG_WORDS = {
    "miss", "misses", "missed", "fall", "falls", "drop", "drops", "plunge",
    "plunges", "slump", "slumps", "decline", "declines", "loss", "losses",
    "downgrade", "downgrades", "weak", "cut", "cuts", "cutting", "lawsuit",
    "probe", "fraud", "fine", "fined", "warning", "warns", "bearish", "slide",
    "slides", "concern", "concerns", "crash", "crashes", "sell", "selloff",
    "layoff", "layoffs", "default", "risk", "risks", "low", "lower", "delay",
    "delays", "recall", "scandal", "sinks", "sink", "tumble", "tumbles",
}

_EVENT_KEYWORDS = {
    "earnings": ("earnings", "profit", "revenue", "quarter", "q1", "q2", "q3", "q4", "results"),
    "guidance": ("guidance", "outlook", "forecast", "estimate"),
    "analyst": ("upgrade", "downgrade", "analyst", "rating", "target price", "buy", "sell"),
    "m&a": ("acquire", "acquisition", "merger", "stake", "buyout", "deal"),
    "lawsuit": ("lawsuit", "probe", "regulator", "fine", "court", "sebi", "penalty"),
    "product": ("launch", "unveil", "product", "service", "expand"),
    "macro": ("inflation", "rate", "rbi", "economy", "gdp", "sensex", "nifty", "market"),
}

# Tiny in-memory cache: key -> (expiry_epoch, value)
_CACHE: dict[str, tuple[float, list[dict]]] = {}


def _cache_get(key: str):
    hit = _CACHE.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    return None


def _cache_put(key: str, value: list[dict]) -> None:
    _CACHE[key] = (time.time() + config.NEWS_CACHE_TTL, value)


def _score_sentiment(text: str) -> float:
    """Lexicon sentiment in [-1, 1]. HEURISTIC stand-in for FinBERT."""
    words = [w.strip(".,!?:;\"'()").lower() for w in text.split()]
    pos = sum(1 for w in words if w in _POS_WORDS)
    neg = sum(1 for w in words if w in _NEG_WORDS)
    if pos == 0 and neg == 0:
        return 0.0
    raw = (pos - neg) / (pos + neg)
    # Dampen so single-word headlines don't peg to +/-1.
    magnitude = min(1.0, (pos + neg) / 3.0)
    return round(raw * (0.5 + 0.5 * magnitude), 2)


def _label(sentiment: float) -> str:
    if sentiment > 0.15:
        return "positive"
    if sentiment < -0.15:
        return "negative"
    return "neutral"


def _analyze_sentiment(text: str) -> tuple[float, str, str]:
    """(sentiment, label, engine). FinBERT when available, else the lexicon."""
    try:
        sentiment, label = finbert.score(text)
        return sentiment, label, "FinBERT (ProsusAI/finbert)"
    except Exception:
        sentiment = _score_sentiment(text)
        return sentiment, _label(sentiment), "lexicon (heuristic fallback)"


def _event_type(text: str) -> str:
    low = text.lower()
    for event, keywords in _EVENT_KEYWORDS.items():
        if any(k in low for k in keywords):
            return event
    return "news"


def _surprise(published_at: str, event_type: str) -> float:
    """Novelty proxy in [0, 1]: fresher + event-driven news scores higher."""
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        age_h = 24.0
    recency = max(0.0, 1.0 - age_h / 48.0)          # 0 at >=48h old, 1 if brand new
    event_boost = 0.0 if event_type == "news" else 0.25
    return round(min(1.0, recency * 0.75 + event_boost), 2)


def _match_ticker(text: str, default: str | None) -> str:
    """Tag an article to whichever watchlist company it mentions (by alias)."""
    low = text.lower()
    for ticker, aliases in _COMPANY_ALIASES.items():
        if any(alias in low for alias in aliases):
            return ticker
    return default or "MARKET"


def _http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "signal-desk/0.3"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _map_articles(raw: list[dict], limit: int, default_ticker: str | None) -> list[dict]:
    out: list[dict] = []
    for i, art in enumerate(raw[:limit]):
        title = (art.get("title") or "").strip()
        desc = (art.get("description") or "").strip()
        if not title:
            continue
        blob = f"{title} {desc}"
        sentiment, sent_label, engine = _analyze_sentiment(blob)
        event = _event_type(blob)
        published = art.get("publishedAt") or datetime.now(timezone.utc).isoformat()
        src = (art.get("source") or {}).get("name") or "NewsAPI"
        out.append(
            {
                "id": f"news-{i}-{abs(hash(art.get('url') or title)) % 100000}",
                "ticker": _match_ticker(blob, default_ticker),
                "headline": title,
                "source": src,
                "event_type": event,
                "sentiment": sentiment,
                "sentiment_label": sent_label,
                "surprise": _surprise(published, event),
                "published_at": published,
                "url": art.get("url"),
                "basis": f"newsapi.org + {engine}",
            }
        )
    return out


def fetch_news(limit: int = 12, ticker: str | None = None) -> list[dict]:
    """Live news for the watchlist (or one ticker). Falls back to mock on failure."""
    if not config.NEWSAPI_KEY:
        return mock_data.generate_news(limit=limit, ticker=ticker)

    cache_key = f"news:{ticker or 'watchlist'}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if ticker:
        query = _COMPANY_QUERY.get(ticker, ticker.replace(".NS", "").replace(".BO", ""))
    else:
        # One combined query for the whole watchlist keeps us within the daily quota.
        query = "(" + " OR ".join(f'"{n}"' for n in _COMPANY_QUERY.values()) + ")"

    params = urllib.parse.urlencode(
        {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": max(limit, 20),
            "apiKey": config.NEWSAPI_KEY,
        }
    )
    try:
        data = _http_get(f"{_ENDPOINT}?{params}")
    except Exception:
        # network / rate-limit / bad key -> don't break the dashboard
        return mock_data.generate_news(limit=limit, ticker=ticker)

    if data.get("status") != "ok":
        return mock_data.generate_news(limit=limit, ticker=ticker)

    articles = _map_articles(data.get("articles", []), limit, ticker)
    if not articles:
        return mock_data.generate_news(limit=limit, ticker=ticker)

    _cache_put(cache_key, articles)
    return articles
