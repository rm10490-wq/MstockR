"""
Symbol search / typeahead (keyword -> matching NSE/BSE stocks).

Backs the search box so a user can type a company keyword ("tata", "reliance",
"infosys") and pick from matched stocks, instead of having to know the exact NSE
ticker. Uses Yahoo Finance's public search endpoint, filtered to Indian equities.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

_ENDPOINT = "https://query1.finance.yahoo.com/v1/finance/search"

# Yahoo exchange codes for Indian equities: NSI = NSE, BSE = BSE.
_INDIA_EXCHANGES = {"NSI", "BSE"}

_CACHE: dict[str, tuple[float, list[dict]]] = {}
_TTL = 900.0  # 15 min


def _cache_get(key: str):
    hit = _CACHE.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    return None


def search(query: str, limit: int = 8) -> list[dict]:
    """Return matched Indian stocks: [{symbol, name, exchange}]. NSE preferred."""
    q = (query or "").strip()
    if len(q) < 2:
        return []

    key = q.lower()
    cached = _cache_get(key)
    if cached is not None:
        return cached[:limit]

    params = urllib.parse.urlencode({"q": q, "quotesCount": 20, "newsCount": 0})
    try:
        req = urllib.request.Request(
            f"{_ENDPOINT}?{params}", headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    seen: dict[str, dict] = {}  # base symbol -> best match (prefer .NS)
    for qt in data.get("quotes", []):
        if qt.get("quoteType") != "EQUITY":
            continue
        symbol = qt.get("symbol") or ""
        exch = qt.get("exchange") or ""
        if exch not in _INDIA_EXCHANGES and not symbol.endswith((".NS", ".BO")):
            continue
        name = qt.get("shortname") or qt.get("longname") or symbol
        base = symbol.split(".")[0]
        item = {"symbol": symbol, "name": name, "exchange": exch}
        # Prefer the NSE (.NS) listing when the same company appears on both.
        if base not in seen or (symbol.endswith(".NS") and not seen[base]["symbol"].endswith(".NS")):
            seen[base] = item

    results = list(seen.values())
    _CACHE[key] = (time.time() + _TTL, results)
    return results[:limit]
