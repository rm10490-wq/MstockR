"""
Local configuration / secrets for the dashboard backend.

NewsAPI key powers the real news feed (Phase 3). It is read from the
NEWSAPI_KEY environment variable if set, otherwise it falls back to the value
below so the app works out of the box on this machine.

⚠️ Keep this file private — do NOT commit the key to a public repo. If you ever
push this project, move the key into an env var and replace the fallback with "".
"""

from __future__ import annotations

import os

# newsapi.org developer key. Env var wins so you can override without editing code.
NEWSAPI_KEY: str = os.environ.get("NEWSAPI_KEY", "864ebb8c549f4332a42621ce7975cc8c")

# How long to cache NewsAPI responses (seconds). The free "Developer" plan allows
# ~100 requests/day, so cache generously to stay well under the limit.
NEWS_CACHE_TTL: float = 1800.0  # 30 minutes

# --- Phase 6: scheduled live polling ----------------------------------------
# Master switch and cadence for the background scheduler (scheduler.py). It warms
# the signal/news caches and, when MySQL is configured, persists a fresh snapshot.
SCHEDULER_ENABLED: bool = os.environ.get("SCHEDULER_ENABLED", "1") not in ("0", "false", "False")
# Full poll (fetch + persist to MySQL) cadence, in minutes.
POLL_INTERVAL_MINUTES: int = int(os.environ.get("POLL_INTERVAL_MINUTES", "30"))
# Seconds after startup before the first poll fires (let the server settle).
POLL_INITIAL_DELAY: int = int(os.environ.get("POLL_INITIAL_DELAY", "20"))
