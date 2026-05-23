from __future__ import annotations
import sqlite3
import os
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.db')


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.execute('''
            CREATE TABLE IF NOT EXISTS shortenings (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user      TEXT NOT NULL,
                orig_url  TEXT,
                short_url TEXT,
                ts        TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
            )
        ''')


def log_shortening(user: str, orig_url: str, short_url: str):
    with _conn() as c:
        c.execute(
            'INSERT INTO shortenings (user, orig_url, short_url) VALUES (?,?,?)',
            (user, orig_url, short_url),
        )


def today_count(user: str) -> int:
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(DISTINCT orig_url) FROM shortenings WHERE user=? AND date(ts)=?",
            (user, date.today().isoformat()),
        ).fetchone()[0]


def weekly_total(user: str) -> int:
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(DISTINCT orig_url) FROM shortenings "
            "WHERE user=? AND date(ts) >= date('now','-6 days')",
            (user,),
        ).fetchone()[0]


def all_time_total(user: str) -> int:
    with _conn() as c:
        return c.execute(
            'SELECT COUNT(DISTINCT orig_url) FROM shortenings WHERE user=?', (user,)
        ).fetchone()[0]


def best_day(user: str) -> dict:
    with _conn() as c:
        r = c.execute(
            'SELECT date(ts) as day, COUNT(DISTINCT orig_url) as cnt FROM shortenings '
            'WHERE user=? GROUP BY day ORDER BY cnt DESC LIMIT 1',
            (user,),
        ).fetchone()
    return {'day': r['day'], 'cnt': r['cnt']} if r else {'day': '—', 'cnt': 0}


def count_for_date(user: str, date_str: str) -> int:
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(DISTINCT orig_url) FROM shortenings WHERE user=? AND date(ts)=?",
            (user, date_str),
        ).fetchone()[0]


def session_counts_for_date(user: str, date_str: str) -> dict:
    """S1: 00:00-13:59 UTC, S2: 14:00-16:59 UTC, S3: 17:00-23:59 UTC"""
    with _conn() as c:
        rows = c.execute("""
            SELECT
                CASE
                    WHEN CAST(strftime('%H', ts) AS INTEGER) < 14 THEN '1'
                    WHEN CAST(strftime('%H', ts) AS INTEGER) < 17 THEN '2'
                    ELSE '3'
                END as snum,
                COUNT(DISTINCT orig_url) as cnt
            FROM shortenings
            WHERE user=? AND date(ts)=?
            GROUP BY snum
        """, (user, date_str)).fetchall()
    counts = {'1': 0, '2': 0, '3': 0}
    for r in rows:
        counts[r['snum']] = r['cnt']
    return counts


def daily_stats(user: str, days: int = 30) -> list[dict]:
    """One entry per calendar day for the last `days` days; zero-fills gaps."""
    end   = date.today()
    start = end - timedelta(days=days - 1)
    with _conn() as c:
        rows = c.execute(
            'SELECT date(ts) as day, COUNT(DISTINCT orig_url) as cnt FROM shortenings '
            'WHERE user=? AND date(ts)>=? GROUP BY day ORDER BY day',
            (user, start.isoformat()),
        ).fetchall()
    db = {r['day']: r['cnt'] for r in rows}
    result, cur = [], start
    while cur <= end:
        ds = cur.isoformat()
        result.append({'day': ds, 'cnt': db.get(ds, 0)})
        cur += timedelta(days=1)
    return result
