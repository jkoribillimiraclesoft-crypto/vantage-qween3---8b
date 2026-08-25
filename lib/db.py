"""Persistent storage for enriched updates. SQLite keeps this deployable
with zero external infrastructure; swap this module for Postgres later
without touching pipeline.py or app.py."""

import json
import os
import sqlite3
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vantage.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            source_url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            date TEXT NOT NULL,
            tier INTEGER NOT NULL,
            category TEXT,
            is_gcp INTEGER,
            is_de INTEGER,
            summary TEXT,
            whats_new TEXT,
            why_matters TEXT,
            why_learn TEXT,
            what_to_learn TEXT,
            gcp_use TEXT,
            gcp_use_case TEXT,
            scores TEXT,
            fetched_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS refresh_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ran_at TEXT,
            new_items INTEGER,
            status_json TEXT
        )
    """)
    conn.commit()
    conn.close()


def upsert_updates(items):
    conn = _connect()
    now = datetime.datetime.utcnow().isoformat()
    for it in items:
        conn.execute("""
            INSERT INTO updates (source_url, title, source, date, tier, category, is_gcp, is_de,
                summary, whats_new, why_matters, why_learn, what_to_learn, gcp_use, gcp_use_case,
                scores, fetched_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_url) DO UPDATE SET
                title=excluded.title, tier=excluded.tier, category=excluded.category,
                is_gcp=excluded.is_gcp, is_de=excluded.is_de, summary=excluded.summary,
                whats_new=excluded.whats_new, why_matters=excluded.why_matters,
                why_learn=excluded.why_learn, what_to_learn=excluded.what_to_learn,
                gcp_use=excluded.gcp_use, gcp_use_case=excluded.gcp_use_case,
                scores=excluded.scores, fetched_at=excluded.fetched_at
        """, (
            it["source_url"], it["title"], it["source"], it["date"], it["tier"], it["category"],
            int(it["is_gcp"]), int(it["is_de"]), it["summary"], it["whats_new"], it["why_matters"],
            it["why_learn"], json.dumps(it["what_to_learn"]), it["gcp_use"], it["gcp_use_case"],
            json.dumps(it["scores"]), now,
        ))
    conn.commit()
    conn.close()


def log_refresh(new_items, status):
    conn = _connect()
    conn.execute("INSERT INTO refresh_log (ran_at, new_items, status_json) VALUES (?,?,?)",
                 (datetime.datetime.utcnow().isoformat(), new_items, json.dumps(status)))
    conn.commit()
    conn.close()


def get_last_refresh():
    conn = _connect()
    row = conn.execute("SELECT * FROM refresh_log ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return None
    return dict(ran_at=row["ran_at"], new_items=row["new_items"], status=json.loads(row["status_json"]))


def get_all_updates():
    conn = _connect()
    rows = conn.execute("SELECT * FROM updates ORDER BY date DESC").fetchall()
    conn.close()
    items = []
    for r in rows:
        items.append(dict(
            title=r["title"], source=r["source"], source_url=r["source_url"], date=r["date"],
            tier=r["tier"], category=r["category"], is_gcp=bool(r["is_gcp"]), is_de=bool(r["is_de"]),
            summary=r["summary"], whats_new=r["whats_new"], why_matters=r["why_matters"],
            why_learn=r["why_learn"], what_to_learn=json.loads(r["what_to_learn"] or "[]"),
            gcp_use=r["gcp_use"], gcp_use_case=r["gcp_use_case"],
            scores=json.loads(r["scores"] or "{}"),
        ))
    return items


def get_existing_urls_and_titles():
    conn = _connect()
    rows = conn.execute("SELECT source_url, title FROM updates").fetchall()
    conn.close()
    return [r["source_url"] for r in rows], [r["title"] for r in rows]


def count():
    conn = _connect()
    n = conn.execute("SELECT COUNT(*) c FROM updates").fetchone()["c"]
    conn.close()
    return n
