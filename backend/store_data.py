"""
Persist the dashboard's data into MySQL for offline analysis.

Creates the `stockdash` database (if missing) and three tables, then pulls the
current data straight from the app's own modules and writes it:

    prices   -- real yfinance daily closes + 5-day SMA, one row per (ticker, date)
    signals  -- momentum-baseline signal snapshots, a time series you can trend
    news     -- real NewsAPI headlines + heuristic sentiment, deduped by (ticker, url)

Re-runnable and idempotent: prices/news use INSERT ... ON DUPLICATE KEY UPDATE so
repeat runs refresh rather than duplicate; signals are append-only so you can see
how the signal evolves over time.

Usage:
    set MYSQL_PASSWORD first (see db_config.py), then:
        python store_data.py
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

import db_config
import market_data
import news_api

DDL = {
    "prices": """
        CREATE TABLE IF NOT EXISTS prices (
            ticker   VARCHAR(20)  NOT NULL,
            date     DATE         NOT NULL,
            close    DECIMAL(14,2) NOT NULL,
            sma      DECIMAL(14,2),
            currency VARCHAR(8)   NOT NULL DEFAULT 'INR',
            PRIMARY KEY (ticker, date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "signals": """
        CREATE TABLE IF NOT EXISTS signals (
            id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
            ticker              VARCHAR(20) NOT NULL,
            captured_at         DATETIME    NOT NULL,
            direction           VARCHAR(8)  NOT NULL,
            confidence          DECIMAL(5,3),
            expected_change_pct DECIMAL(6,2),
            last_price          DECIMAL(14,2),
            currency            VARCHAR(8)  NOT NULL DEFAULT 'INR',
            basis               VARCHAR(120),
            KEY ix_signals_ticker_time (ticker, captured_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    "news": """
        CREATE TABLE IF NOT EXISTS news (
            id              BIGINT AUTO_INCREMENT PRIMARY KEY,
            ticker          VARCHAR(20)  NOT NULL,
            headline        VARCHAR(512) NOT NULL,
            source          VARCHAR(120),
            event_type      VARCHAR(20),
            sentiment       DECIMAL(4,2),
            sentiment_label VARCHAR(10),
            surprise        DECIMAL(4,2),
            published_at    DATETIME,
            url             VARCHAR(512),
            url_hash        CHAR(40) NOT NULL,
            UNIQUE KEY uq_news (ticker, url_hash)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
}


def _parse_dt(iso: str | None):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def ensure_database() -> None:
    """Create the stockdash database if it doesn't exist yet."""
    engine = create_engine(db_config.server_url())
    with engine.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_config.MYSQL_DB} "
                          "CHARACTER SET utf8mb4"))
    engine.dispose()


def store() -> dict:
    ensure_database()
    engine = create_engine(db_config.db_url())
    counts = {"prices": 0, "signals": 0, "news": 0}
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with engine.begin() as conn:
        for ddl in DDL.values():
            conn.execute(text(ddl))

        for item in market_data.WATCHLIST:
            ticker = item["ticker"]

            # --- prices (real yfinance history) ---
            for p in market_data.fetch_history(ticker):
                conn.execute(text("""
                    INSERT INTO prices (ticker, date, close, sma, currency)
                    VALUES (:t, :d, :c, :s, :cur)
                    ON DUPLICATE KEY UPDATE close=VALUES(close), sma=VALUES(sma)
                """), {"t": ticker, "d": p["date"], "c": p["close"],
                       "s": p["sma"], "cur": market_data.CURRENCY})
                counts["prices"] += 1

            # --- signal snapshot (append-only time series) ---
            sig = market_data.momentum_signal(ticker)
            conn.execute(text("""
                INSERT INTO signals (ticker, captured_at, direction, confidence,
                                     expected_change_pct, last_price, currency, basis)
                VALUES (:t, :ts, :dir, :conf, :exp, :lp, :cur, :basis)
            """), {"t": ticker, "ts": now, "dir": sig["direction"],
                   "conf": sig["confidence"], "exp": sig["expected_change_pct"],
                   "lp": sig["last_price"], "cur": sig["currency"], "basis": sig["basis"]})
            counts["signals"] += 1

        # --- news (real NewsAPI + heuristic sentiment) ---
        for a in news_api.fetch_news(limit=30):
            url = a.get("url") or a["headline"]
            # Stable across runs — built-in hash() is per-process salted, which
            # would break the (ticker, url_hash) dedup key and insert duplicates.
            url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()
            conn.execute(text("""
                INSERT INTO news (ticker, headline, source, event_type, sentiment,
                                  sentiment_label, surprise, published_at, url, url_hash)
                VALUES (:t, :h, :src, :ev, :sent, :lbl, :sur, :pub, :url, :uh)
                ON DUPLICATE KEY UPDATE sentiment=VALUES(sentiment),
                    sentiment_label=VALUES(sentiment_label), surprise=VALUES(surprise)
            """), {"t": a["ticker"], "h": a["headline"], "src": a.get("source"),
                   "ev": a.get("event_type"), "sent": a.get("sentiment"),
                   "lbl": a.get("sentiment_label"), "sur": a.get("surprise"),
                   "pub": _parse_dt(a.get("published_at")), "url": a.get("url"),
                   "uh": url_hash})
            counts["news"] += 1

    engine.dispose()
    return counts


if __name__ == "__main__":
    if not db_config.MYSQL_PASSWORD:
        print("ERROR: set MYSQL_PASSWORD first (see db_config.py).", file=sys.stderr)
        sys.exit(1)
    try:
        result = store()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Stored -> prices: {result['prices']} rows, "
          f"signals: {result['signals']} rows, news: {result['news']} rows "
          f"into MySQL database '{db_config.MYSQL_DB}'.")
