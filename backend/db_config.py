"""
MySQL connection settings for the analysis store.

The password is read from the MYSQL_PASSWORD environment variable so it never has
to be written into source. Set it once per shell before running store_data.py:

    PowerShell:  $env:MYSQL_PASSWORD = "yourpassword"
    Git Bash:    export MYSQL_PASSWORD="yourpassword"

Everything else can be overridden via env vars too (MYSQL_HOST, MYSQL_PORT, ...).
"""

from __future__ import annotations

import os

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DB = os.environ.get("MYSQL_DB", "stockdash")


def server_url() -> str:
    """SQLAlchemy URL WITHOUT a database (used to CREATE the database)."""
    from urllib.parse import quote_plus

    pw = quote_plus(MYSQL_PASSWORD)
    return f"mysql+pymysql://{MYSQL_USER}:{pw}@{MYSQL_HOST}:{MYSQL_PORT}/?charset=utf8mb4"


def db_url() -> str:
    """SQLAlchemy URL for the stockdash database."""
    from urllib.parse import quote_plus

    pw = quote_plus(MYSQL_PASSWORD)
    return f"mysql+pymysql://{MYSQL_USER}:{pw}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
