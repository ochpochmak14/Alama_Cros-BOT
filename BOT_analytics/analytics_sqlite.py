"""
Analytics module for KBJU Telegram bot — SQLite intermediate storage.

Logs user events to a local SQLite database (non-blocking, bounded thread pool).
Later, migrate to Google Sheets using analytics_migrate.py.

Schema:
  events: id, user_id, event_name, timestamp, params (JSON), synced_to_sheets, synced_at
"""

import os
import json
import logging
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("kbju_bot.analytics")

# Local SQLite database — created automatically in bot directory
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analytics.db")

# Bounded pool: at most 4 concurrent database writes
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="analytics")

# Database connection thread safety
_db_lock = threading.Lock()

# Max length for free-text user fields (injection mitigation)
_MAX_PARAM_STR_LEN = 200


def _init_db():
    """Create the events table if it doesn't exist."""
    with _db_lock:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")  # Write-ahead logging for concurrent access
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    params TEXT NOT NULL,
                    synced_to_sheets INTEGER DEFAULT 0,
                    synced_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_synced_to_sheets
                ON events(synced_to_sheets)
            """)
            conn.commit()
        finally:
            conn.close()


def _sanitize_params(params: dict) -> dict:
    """Truncate long strings to prevent injection attacks."""
    clean = {}
    for k, v in params.items():
        if isinstance(v, str):
            v = v[:_MAX_PARAM_STR_LEN]
        clean[k] = v
    return clean


def _write_row(user_id: int, event_name: str, params: dict) -> None:
    """Write one event row to SQLite. Runs inside the thread pool."""
    try:
        with _db_lock:
            conn = sqlite3.connect(_DB_PATH, timeout=30)
            try:
                conn.execute(
                    """
                    INSERT INTO events (user_id, event_name, timestamp, params, synced_to_sheets)
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (
                        user_id,
                        event_name,
                        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        json.dumps(_sanitize_params(params), ensure_ascii=False),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        logger.exception("Failed to log event '%s' for user %s", event_name, user_id)


def log_event(user_id: int, event_name: str, params: dict = None) -> None:
    """
    Non-blocking analytics event logger.

    Submits the write task to a bounded thread pool (max 4 workers) so the
    bot handler returns immediately. If the pool queue is full, the event is
    dropped with a warning rather than blocking the bot.

    Args:
        user_id:    Telegram numeric user ID (never a username or phone number).
        event_name: Snake-case event identifier, e.g. 'bot_start', 'search_dish'.
        params:     Optional dict of event parameters (serialized as JSON).
    """
    _executor.submit(_write_row, user_id, event_name, params or {})


# Initialize database on module import
_init_db()
