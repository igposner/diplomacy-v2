"""SQLite persistence. A game survives a restart; nothing lives only in memory.

The engine already serialises a whole game, pending orders included, so a game
row is that blob plus the little we add on top (who the human is, what the last
phase resolved to). Press is its own table because it is queried per power.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

import diplomacy
from diplomacy.utils.export import from_saved_game_format, to_saved_game_format

DB_PATH = os.environ.get("DIPLOMACY_DB", os.path.join(os.path.dirname(__file__), "diplomacy.sqlite3"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id           TEXT PRIMARY KEY,
    human_power  TEXT NOT NULL,
    saved        TEXT NOT NULL,          -- to_saved_game_format(game)
    last_result  TEXT,                   -- the phase that just resolved, or NULL
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id   TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    sender    TEXT NOT NULL,
    recipient TEXT NOT NULL,             -- a power, or GLOBAL
    text      TEXT NOT NULL,
    phase     TEXT NOT NULL,
    at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_by_game ON messages(game_id, id);
"""

_local = threading.local()


def _conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.executescript(_SCHEMA)
        _local.conn = c
    return c


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- games
def create_game(game_id: str, human_power: str, game: diplomacy.Game) -> None:
    c = _conn()
    now = _now()
    c.execute(
        "INSERT OR REPLACE INTO games (id, human_power, saved, last_result, created_at, updated_at)"
        " VALUES (?,?,?,NULL,?,?)",
        (game_id, human_power, json.dumps(to_saved_game_format(game)), now, now),
    )
    c.commit()


def save_game(game_id: str, game: diplomacy.Game, last_result: dict | None = None) -> None:
    c = _conn()
    if last_result is None:
        c.execute("UPDATE games SET saved=?, updated_at=? WHERE id=?",
                  (json.dumps(to_saved_game_format(game)), _now(), game_id))
    else:
        c.execute("UPDATE games SET saved=?, last_result=?, updated_at=? WHERE id=?",
                  (json.dumps(to_saved_game_format(game)), json.dumps(last_result), _now(), game_id))
    c.commit()


def load_game(game_id: str) -> tuple[diplomacy.Game, str, dict | None] | None:
    row = _conn().execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
    if row is None:
        return None
    game = from_saved_game_format(json.loads(row["saved"]))
    result = json.loads(row["last_result"]) if row["last_result"] else None
    return game, row["human_power"], result


def list_games(limit: int = 50) -> list[dict]:
    rows = _conn().execute(
        "SELECT id, human_power, created_at, updated_at FROM games"
        " ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def delete_game(game_id: str) -> None:
    c = _conn()
    c.execute("DELETE FROM games WHERE id=?", (game_id,))
    c.commit()


# ---------------------------------------------------------------- press
def add_message(game_id: str, sender: str, recipient: str, text: str, phase: str) -> dict:
    c = _conn()
    m = {"sender": sender, "to": recipient, "text": text, "phase": phase, "at": _now()}
    c.execute("INSERT INTO messages (game_id, sender, recipient, text, phase, at)"
              " VALUES (?,?,?,?,?,?)",
              (game_id, sender, recipient, text, phase, m["at"]))
    c.commit()
    return m


def messages_for(game_id: str, power: str) -> list[dict]:
    """Only what this power can see. Enforced here, not in the browser."""
    rows = _conn().execute(
        "SELECT sender, recipient, text, phase, at FROM messages"
        " WHERE game_id=? AND (recipient='GLOBAL' OR sender=? OR recipient=?)"
        " ORDER BY id", (game_id, power, power)).fetchall()
    return [{"sender": r["sender"], "to": r["recipient"], "text": r["text"],
             "phase": r["phase"], "at": r["at"]} for r in rows]
