#!/usr/bin/env python3
"""
Quick test script to verify analytics is working.
Logs sample events to SQLite and displays them.
"""

import sqlite3
import json
from analytics_sqlite import log_event
from datetime import datetime

_DB_PATH = "analytics.db"


def test_logging():
    """Log some sample events."""
    print("📝 Logging sample events…")

    # Test bot_start
    log_event(user_id=12345, event_name="bot_start", params={
        "is_new": True,
        "source": "instagram"
    })
    print("  ✓ bot_start")

    # Test search_dish
    log_event(user_id=12345, event_name="search_dish", params={
        "restaurant": "mcdonalds",
        "query": "chicken"
    })
    print("  ✓ search_dish")

    # Test cart_add
    log_event(user_id=12345, event_name="cart_add", params={
        "dish_name": "McChicken",
        "restaurant": "mcdonalds"
    })
    print("  ✓ cart_add")

    # Test zero_results
    log_event(user_id=12345, event_name="zero_results", params={
        "restaurant": "bella_ciao",
        "query": "pizza margherita with pineapple"
    })
    print("  ✓ zero_results")

    # Give thread pool time to write
    import time
    time.sleep(1)


def display_events():
    """Display logged events from SQLite."""
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 10")
        events = cursor.fetchall()
        conn.close()

        print(f"\n📊 Last {len(events)} events in database:\n")
        print(f"{'ID':>3} {'User':>6} {'Event':<20} {'Timestamp':<20} {'Synced':<7}")
        print("─" * 75)

        for e in events:
            synced = "✓" if e['synced_to_sheets'] else "○"
            print(f"{e['id']:>3} {e['user_id']:>6} {e['event_name']:<20} {e['timestamp']:<20} {synced:<7}")

        # Show one event in detail
        if events:
            e = events[0]
            print(f"\n📋 Latest event details:")
            print(f"  ID: {e['id']}")
            print(f"  User: {e['user_id']}")
            print(f"  Event: {e['event_name']}")
            print(f"  Timestamp: {e['timestamp']}")
            print(f"  Params: {e['params']}")

    except sqlite3.OperationalError as err:
        print(f"❌ Database error: {err}")


def check_database():
    """Check database stats."""
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        cursor = conn.execute("SELECT COUNT(*) FROM events")
        total = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM events WHERE synced_to_sheets = 0")
        unsynced = cursor.fetchone()[0]

        conn.close()

        print(f"\n📈 Database stats:")
        print(f"  Total events: {total}")
        print(f"  Unsynced (pending migration): {unsynced}")
        print(f"  Synced to Sheets: {total - unsynced}")

    except sqlite3.OperationalError as err:
        print(f"❌ Database error: {err}")


if __name__ == "__main__":
    print("=" * 75)
    print("KBJU Bot Analytics Test")
    print("=" * 75)

    test_logging()
    display_events()
    check_database()

    print("\n✅ Test complete!")
    print("\nNext steps:")
    print("  • python dashboard_weekly_sqlite.py  — View weekly report")
    print("  • python analytics_migrate.py         — Migrate to Google Sheets")
