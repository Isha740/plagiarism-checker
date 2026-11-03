"""Tiny SQLite store. Every browser gets a private workspace id (cookie), so users never see each other's files."""
import os
import sqlite3
import time

import config


def _conn():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    c = sqlite3.connect(config.DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wid TEXT NOT NULL,
            mode TEXT NOT NULL,          -- 'compare' | 'reference'
            kind TEXT NOT NULL,          -- 'doc' | 'ref'
            name TEXT NOT NULL,
            text TEXT NOT NULL,
            words INTEGER NOT NULL,
            created REAL NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_docs ON documents (wid, mode, kind)")
    purge_old()


def purge_old():
    cutoff = time.time() - config.PURGE_AFTER_HOURS * 3600
    with _conn() as c:
        c.execute("DELETE FROM documents WHERE created < ?", (cutoff,))


def add_doc(wid, mode, kind, name, text, words):
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO documents (wid, mode, kind, name, text, words, created) VALUES (?,?,?,?,?,?,?)",
            (wid, mode, kind, name, text, words, time.time()))
        return cur.lastrowid


def list_docs(wid, mode, kind, with_text=False):
    cols = "id, name, words, created" + (", text" if with_text else "")
    with _conn() as c:
        rows = c.execute(
            f"SELECT {cols} FROM documents WHERE wid=? AND mode=? AND kind=? ORDER BY id",
            (wid, mode, kind)).fetchall()
    return [dict(r) for r in rows]


def count_docs(wid, mode, kind):
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM documents WHERE wid=? AND mode=? AND kind=?",
                         (wid, mode, kind)).fetchone()[0]


def delete_doc(wid, doc_id):
    with _conn() as c:
        cur = c.execute("DELETE FROM documents WHERE wid=? AND id=?", (wid, doc_id))
        return cur.rowcount > 0


def delete_kind(wid, mode, kind):
    with _conn() as c:
        c.execute("DELETE FROM documents WHERE wid=? AND mode=? AND kind=?", (wid, mode, kind))
