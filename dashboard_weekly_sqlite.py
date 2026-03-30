"""
Weekly analytics dashboard for KBJU Telegram bot — reads from SQLite.

Computes key metrics from local analytics.db and prints a report.
Run manually or schedule weekly (e.g., every Monday morning).

Usage:
    python dashboard_weekly_sqlite.py
"""

import os
import json
import sqlite3
import logging
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analytics.db")


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _parse_ts(ts_str):
    """Parse ISO timestamp string to aware datetime (UTC)."""
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_params(params_str):
    try:
        return json.loads(params_str) if params_str else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _week_boundaries(weeks_ago=0):
    """Return (start, end) UTC datetimes for a calendar week."""
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday(), weeks=weeks_ago)
    start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start, end


def _load_events(max_rows: int = 200_000):
    """Fetch events from SQLite."""
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                """
                SELECT user_id, event_name, timestamp, params
                FROM events
                ORDER BY timestamp
                LIMIT ?
                """,
                (max_rows,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    except sqlite3.OperationalError as e:
        logger.error("Failed to read from SQLite: %s", e)
        return []


# ─── METRICS ──────────────────────────────────────────────────────────────────

def compute_metrics(events, period_start, period_end):
    """Compute all dashboard metrics for the given time window."""

    # Filter to window
    window = [
        e for e in events
        if (ts := _parse_ts(e.get("timestamp", ""))) and period_start <= ts < period_end
    ]

    # All-time for retention calculation
    all_starts = [e for e in events if e.get("event_name") == "bot_start"]

    # ── New users this week ────────────────────────────────────────────────────
    new_users_this_week = {
        e["user_id"]
        for e in window
        if e.get("event_name") == "bot_start" and _parse_params(e.get("params")).get("is_new")
    }

    # ── MAU (last 30 days from period_end) ────────────────────────────────────
    mau_start = period_end - timedelta(days=30)
    mau = {e["user_id"] for e in events if (ts := _parse_ts(e.get("timestamp", ""))) and mau_start <= ts < period_end}

    # ── DAU (yesterday relative to period_end) ────────────────────────────────
    yesterday_start = (period_end - timedelta(days=1)).replace(hour=0, minute=0, second=0)
    yesterday_end = yesterday_start + timedelta(days=1)
    dau = {e["user_id"] for e in events if (ts := _parse_ts(e.get("timestamp", ""))) and yesterday_start <= ts < yesterday_end}

    # ── D7 Retention ──────────────────────────────────────────────────────────
    cohort_end = period_end - timedelta(days=7)
    cohort_start = cohort_end - timedelta(days=7)
    cohort_users = {
        e["user_id"]
        for e in all_starts
        if (ts := _parse_ts(e.get("timestamp", ""))) and cohort_start <= ts < cohort_end
    }
    returned_users = {
        e["user_id"]
        for e in events
        if (ts := _parse_ts(e.get("timestamp", "")))
        and period_end - timedelta(days=7) <= ts < period_end
        and e["user_id"] in cohort_users
    }
    d7_retention = (
        round(len(returned_users) / len(cohort_users) * 100, 1)
        if cohort_users else None
    )

    # ── Top restaurants by search volume ──────────────────────────────────────
    restaurant_searches = Counter()
    for e in window:
        if e.get("event_name") == "search_dish":
            params = _parse_params(e.get("params"))
            rest = params.get("restaurant", "unknown")
            restaurant_searches[rest] += 1

    # ── Top zero-result queries ────────────────────────────────────────────────
    zero_result_queries = Counter()
    for e in window:
        if e.get("event_name") == "zero_results":
            params = _parse_params(e.get("params"))
            q = params.get("query", "").strip().lower()
            if q:
                zero_result_queries[q] += 1

    # ── Traffic sources ────────────────────────────────────────────────────────
    source_counts = Counter()
    for e in window:
        if e.get("event_name") == "bot_start":
            params = _parse_params(e.get("params"))
            source = params.get("source", "unknown")
            source_counts[source] += 1

    # ── Cart adoption (% of active users who added to cart) ───────────────────
    active_users = {e["user_id"] for e in window}
    cart_users = {e["user_id"] for e in window if e.get("event_name") == "cart_add"}
    cart_pct = round(len(cart_users) / len(active_users) * 100, 1) if active_users else 0

    # ── Goal feature adoption ─────────────────────────────────────────────────
    goal_users = {e["user_id"] for e in window if e.get("event_name") == "goal_search"}
    goal_pct = round(len(goal_users) / len(active_users) * 100, 1) if active_users else 0

    # ── Peak hours ────────────────────────────────────────────────────────────
    hour_counts = Counter()
    for e in window:
        ts = _parse_ts(e.get("timestamp", ""))
        if ts:
            hour_counts[ts.hour] += 1
    peak_hours = hour_counts.most_common(3)

    return {
        "period_start": period_start,
        "period_end": period_end,
        "new_users": len(new_users_this_week),
        "mau": len(mau),
        "dau": len(dau),
        "d7_retention_pct": d7_retention,
        "cohort_size": len(cohort_users),
        "top_restaurants": restaurant_searches.most_common(10),
        "top_zero_result_queries": zero_result_queries.most_common(10),
        "source_counts": dict(source_counts.most_common()),
        "cart_adoption_pct": cart_pct,
        "goal_adoption_pct": goal_pct,
        "peak_hours": peak_hours,
        "total_events_in_period": len(window),
        "active_users": len(active_users),
    }


# ─── REPORT ───────────────────────────────────────────────────────────────────

def print_report(m):
    sep = "─" * 52
    w_start = m["period_start"].strftime("%d.%m.%Y")
    w_end = (m["period_end"] - timedelta(seconds=1)).strftime("%d.%m.%Y")

    print(f"\n{'═' * 52}")
    print(f"  КБЖУ-бот — еженедельный отчёт  {w_start} – {w_end}")
    print(f"{'═' * 52}")

    print(f"\n📊 АУДИТОРИЯ")
    print(sep)
    print(f"  Новые пользователи за неделю : {m['new_users']}")
    print(f"  MAU  (последние 30 дней)     : {m['mau']}")
    print(f"  DAU  (вчера)                 : {m['dau']}")
    if m["d7_retention_pct"] is not None:
        print(f"  Retention D7                 : {m['d7_retention_pct']}%  (когорта {m['cohort_size']} чел.)")
    else:
        print(f"  Retention D7                 : нет данных (когорта пуста)")

    print(f"\n🍽️  АКТИВНОСТЬ")
    print(sep)
    print(f"  Активных пользователей       : {m['active_users']}")
    print(f"  Всего событий за период      : {m['total_events_in_period']}")
    print(f"  Используют корзину           : {m['cart_adoption_pct']}% активных")
    print(f"  Используют подбор по цели    : {m['goal_adoption_pct']}% активных")

    print(f"\n🏆 ТОП-10 РЕСТОРАНОВ ПО ПОИСКАМ")
    print(sep)
    if m["top_restaurants"]:
        for i, (rest, cnt) in enumerate(m["top_restaurants"], 1):
            print(f"  {i:2}. {rest:<25} {cnt} запросов")
    else:
        print("  Нет данных")

    print(f"\n❌ ТОП-10 ЗАПРОСОВ С НУЛЕВЫМ РЕЗУЛЬТАТОМ")
    print(sep)
    if m["top_zero_result_queries"]:
        for i, (q, cnt) in enumerate(m["top_zero_result_queries"], 1):
            print(f"  {i:2}. {q:<30} {cnt}×")
    else:
        print("  Нет нулевых результатов — отлично!")

    print(f"\n📣 ИСТОЧНИКИ ТРАФИКА")
    print(sep)
    total_src = sum(m["source_counts"].values()) or 1
    for src, cnt in sorted(m["source_counts"].items(), key=lambda x: -x[1]):
        bar = "█" * int(cnt / total_src * 20)
        print(f"  {src:<12} {cnt:4}  {bar} {cnt/total_src*100:.0f}%")

    print(f"\n⏰ ПИКОВЫЕ ЧАСЫ (UTC)")
    print(sep)
    for hour, cnt in m["peak_hours"]:
        print(f"  {hour:02d}:00–{hour+1:02d}:00   {cnt} событий")

    print(f"\n{'═' * 52}\n")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Загружаю события из SQLite…")
    events = _load_events()
    print(f"Загружено {len(events)} событий.")

    # Отчёт за прошлую неделю
    start, end = _week_boundaries(weeks_ago=1)
    metrics = compute_metrics(events, start, end)
    print_report(metrics)
