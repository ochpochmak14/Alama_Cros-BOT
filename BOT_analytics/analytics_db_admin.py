#!/usr/bin/env python3
"""
SQLite database administration utility for analytics.db.

Usage:
    python analytics_db_admin.py stats          # Show database statistics
    python analytics_db_admin.py clean          # Delete all synced events (after backup!)
    python analytics_db_admin.py backup         # Create a backup copy
    python analytics_db_admin.py vacuum         # Optimize database file size
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime

_DB_PATH = "analytics.db"


def _connect():
    """Connect to the database."""
    if not os.path.exists(_DB_PATH):
        print(f"❌ Database not found: {_DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(_DB_PATH, timeout=30)


def stats():
    """Show database statistics."""
    conn = _connect()
    try:
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM events")
        total = cursor.fetchone()[0]

        # Unsynced events
        cursor.execute("SELECT COUNT(*) FROM events WHERE synced_to_sheets = 0")
        unsynced = cursor.fetchone()[0]

        # Synced events
        synced = total - unsynced

        # Date range
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM events")
        date_range = cursor.fetchone()
        min_date = date_range[0] if date_range[0] else "N/A"
        max_date = date_range[1] if date_range[1] else "N/A"

        # Unique users
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM events")
        unique_users = cursor.fetchone()[0]

        # File size
        file_size = os.path.getsize(_DB_PATH)
        file_size_mb = file_size / (1024 * 1024)
    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("📊 Analytics Database Statistics")
    print("=" * 60)
    print(f"Total events             : {total:,}")
    print(f"  ├─ Unsynced (pending)  : {unsynced:,}")
    print(f"  └─ Synced to Sheets    : {synced:,}")
    print(f"\nUnique users             : {unique_users:,}")
    print(f"Date range               : {min_date} → {max_date}")
    print(f"Database file size       : {file_size_mb:.2f} MB")
    print("=" * 60 + "\n")


def clean():
    """Delete all synced events (warning: irreversible)."""
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events WHERE synced_to_sheets = 1")
        synced_count = cursor.fetchone()[0]

        if synced_count == 0:
            print("\n✓ No synced events to clean.")
            return

        print(f"\n⚠️  Will delete {synced_count:,} synced events from the database.")
        confirm = input("Type 'DELETE' to confirm: ").strip()

        if confirm == "DELETE":
            cursor.execute("DELETE FROM events WHERE synced_to_sheets = 1")
            conn.commit()
            print(f"✓ Deleted {synced_count:,} events.")
        else:
            print("✗ Cancelled.")
    finally:
        conn.close()


def backup():
    """Create a backup of the database."""
    if not os.path.exists(_DB_PATH):
        print(f"❌ Database not found: {_DB_PATH}")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{_DB_PATH}.backup_{timestamp}"

    shutil.copy2(_DB_PATH, backup_path)
    backup_size = os.path.getsize(backup_path) / (1024 * 1024)
    print(f"\n✓ Backup created: {backup_path} ({backup_size:.2f} MB)")


def vacuum():
    """Optimize database file size (WAL cleanup)."""
    conn = _connect()
    try:
        # VACUUM reclaims unused space
        conn.execute("VACUUM")
        conn.close()

        file_size = os.path.getsize(_DB_PATH) / (1024 * 1024)
        print(f"\n✓ Database optimized. Current size: {file_size:.2f} MB")
    except sqlite3.OperationalError as e:
        print(f"\n❌ Optimization failed: {e}")
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "stats":
        stats()
    elif command == "clean":
        clean()
    elif command == "backup":
        backup()
    elif command == "vacuum":
        vacuum()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)
