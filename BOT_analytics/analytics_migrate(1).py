"""
Migrate analytics data from SQLite to Google Sheets.

Run this script periodically (weekly, monthly) to batch-upload events
from the local analytics.db to your Google Sheets analytics spreadsheet.

Usage:
    python analytics_migrate.py [--keep-local]

Flags:
    --keep-local    Don't delete synced events from SQLite (default: deletes after sync)

Required env vars:
    ANALYTICS_SHEET_ID
    GOOGLE_CREDS_JSON  (or credentials.json file)
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime, timezone

try:
    import gspread
except ImportError:
    gspread = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analytics.db")
SHEET_HEADER = ["user_id", "event_name", "timestamp", "params"]


def _get_client():
    """Return an authenticated gspread Client."""
    if gspread is None:
        raise EnvironmentError(
            "gspread not installed. Run: pip install gspread"
        )

    creds_json = os.getenv("GOOGLE_CREDS_JSON")
    if creds_json:
        creds_data = json.loads(creds_json)
        return gspread.service_account_from_dict(creds_data)

    creds_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
    if os.path.exists(creds_file):
        return gspread.service_account(filename=creds_file)

    raise EnvironmentError(
        "Google credentials not found. "
        "Set GOOGLE_CREDS_JSON env var or place credentials.json in the bot directory."
    )


def _get_worksheet():
    """Return the 'events' worksheet, creating it with a header if needed."""
    sheet_id = os.getenv("ANALYTICS_SHEET_ID")
    if not sheet_id:
        raise EnvironmentError("ANALYTICS_SHEET_ID env var is required.")

    client = _get_client()
    spreadsheet = client.open_by_key(sheet_id)

    try:
        ws = spreadsheet.worksheet("events")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="events", rows=50000, cols=4)
        ws.append_row(SHEET_HEADER, value_input_option="USER_ENTERED")

    return ws


def _fetch_unsynced_events(limit: int = 5000) -> list:
    """Fetch unsynced events from SQLite (limited to prevent API quota exhaustion).

    Returns list of dicts including 'id' so we can mark exactly these rows as synced.
    """
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT id, user_id, event_name, timestamp, params FROM events WHERE synced_to_sheets = 0 ORDER BY id LIMIT ?",
                (limit,),
            )
            events = [dict(row) for row in cursor.fetchall()]
            return events
        finally:
            conn.close()
    except sqlite3.OperationalError as e:
        logger.error("Failed to read from SQLite: %s", e)
        return []


def _mark_synced(event_ids: list) -> None:
    """Mark events as synced in SQLite."""
    if not event_ids:
        return

    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        try:
            placeholders = ", ".join("?" * len(event_ids))
            conn.execute(
                f"""
                UPDATE events
                SET synced_to_sheets = 1, synced_at = ?
                WHERE id IN ({placeholders})
                """,
                (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), *event_ids),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.OperationalError as e:
        logger.error("Failed to update SQLite: %s", e)


def _delete_synced(event_ids: list) -> None:
    """Delete synced events from SQLite (optional cleanup)."""
    if not event_ids:
        return

    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        try:
            placeholders = ", ".join("?" * len(event_ids))
            conn.execute(f"DELETE FROM events WHERE id IN ({placeholders})", event_ids)
            conn.commit()
            logger.info("Deleted %d synced events from SQLite", len(event_ids))
        finally:
            conn.close()
    except sqlite3.OperationalError as e:
        logger.error("Failed to delete from SQLite: %s", e)


def migrate(keep_local: bool = False) -> None:
    """
    Migrate unsynced events from SQLite to Google Sheets.

    Args:
        keep_local: If True, don't delete synced events from SQLite
    """
    logger.info("Fetching unsynced events from SQLite…")
    events = _fetch_unsynced_events()
    if not events:
        logger.info("No unsynced events. Done.")
        return

    logger.info("Found %d unsynced events", len(events))

    # Prepare rows for batch upload
    rows = [[e["user_id"], e["event_name"], e["timestamp"], e["params"]] for e in events]

    try:
        logger.info("Uploading to Google Sheets…")
        ws = _get_worksheet()
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        logger.info("✓ Uploaded %d events to Google Sheets", len(events))

        # Use IDs captured at fetch time — safe even if new events arrived during upload
        event_ids = [e["id"] for e in events]

        _mark_synced(event_ids)
        logger.info("✓ Marked %d events as synced", len(event_ids))

        # Optionally clean up local storage
        if not keep_local and event_ids:
            _delete_synced(event_ids)

    except Exception as e:
        logger.error("Migration failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    keep_local = "--keep-local" in sys.argv
    migrate(keep_local=keep_local)
