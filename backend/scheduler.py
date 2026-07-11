"""
Scheduled live polling (Phase 6).

A background APScheduler job that runs every POLL_INTERVAL_MINUTES and:

  1. Warms the in-memory caches (model signals + news) so the next user request
     and the next WebSocket tick are instant.
  2. If MySQL is configured (MYSQL_PASSWORD set), persists a fresh snapshot via
     store_data.store() — so the `signals` time series and `news`/`prices` tables
     fill in automatically over the day, no manual runs needed.

Exposes status() for the /api/scheduler endpoint and the UI's "last synced" badge.
Everything is defensive: a failed poll is logged into the status and the scheduler
keeps running.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import config
import db_config
import model as signal_model
import news_api

log = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None

_status: dict = {
    "enabled": config.SCHEDULER_ENABLED,
    "interval_minutes": config.POLL_INTERVAL_MINUTES,
    "runs": 0,
    "last_run": None,
    "last_status": None,
    "last_detail": None,
    "last_persisted": None,
    "next_run": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def poll() -> None:
    """One polling cycle: warm caches, and persist to MySQL when configured."""
    _status["runs"] += 1
    _status["last_run"] = _now_iso()
    try:
        # 1) Warm caches (also the fetch the WebSocket/API will reuse).
        signals = signal_model.watchlist_signals()
        news = news_api.fetch_news(limit=30)

        detail = f"warmed {len(signals)} signals, {len(news)} news"

        # 2) Persist a snapshot if MySQL is set up.
        if db_config.MYSQL_PASSWORD:
            try:
                import store_data

                counts = store_data.store()
                _status["last_persisted"] = _now_iso()
                detail += (f"; persisted prices={counts['prices']} "
                           f"signals={counts['signals']} news={counts['news']}")
            except Exception as exc:  # noqa: BLE001
                detail += f"; MySQL persist FAILED: {type(exc).__name__}: {exc}"
                _status["last_status"] = "partial"
                _status["last_detail"] = detail
                log.warning("poll persist failed: %s", exc)
                _refresh_next_run()
                return

        _status["last_status"] = "ok"
        _status["last_detail"] = detail
        log.info("poll ok: %s", detail)
    except Exception as exc:  # noqa: BLE001
        _status["last_status"] = "error"
        _status["last_detail"] = f"{type(exc).__name__}: {exc}"
        log.warning("poll error: %s", exc)
    finally:
        _refresh_next_run()


def _refresh_next_run() -> None:
    if _scheduler is not None:
        job = _scheduler.get_job("poll")
        _status["next_run"] = job.next_run_time.isoformat() if job and job.next_run_time else None


def start() -> None:
    global _scheduler
    if not config.SCHEDULER_ENABLED or _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        poll,
        trigger="interval",
        minutes=config.POLL_INTERVAL_MINUTES,
        id="poll",
        next_run_time=datetime.now(timezone.utc)
        + __import__("datetime").timedelta(seconds=config.POLL_INITIAL_DELAY),
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    _refresh_next_run()
    log.info("scheduler started: every %s min", config.POLL_INTERVAL_MINUTES)


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def status() -> dict:
    return dict(_status)
