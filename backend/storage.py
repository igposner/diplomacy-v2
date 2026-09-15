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
    opponents    TEXT NOT NULL DEFAULT 'bots',   -- bots | agents
    model        TEXT,                           -- the agents' model, when agents
    deadline     REAL,                           -- unix time the current phase closes, agent games
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
    at        TEXT NOT NULL,
    kind      TEXT NOT NULL DEFAULT 'text'   -- text | commitment
);
CREATE INDEX IF NOT EXISTS messages_by_game ON messages(game_id, id);

-- Research. None of this is ever served to a player during a game.
CREATE TABLE IF NOT EXISTS charts (          -- what an agent handed in beside its orders
    game_id     TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    power       TEXT NOT NULL,
    phase       TEXT NOT NULL,
    commitments TEXT NOT NULL,               -- JSON list, may be empty
    rejected    TEXT NOT NULL,               -- JSON list: what could not be scored, and why
    at          TEXT NOT NULL,
    PRIMARY KEY (game_id, power, phase)
);
CREATE TABLE IF NOT EXISTS turns (           -- one row per power with units to order, per phase
    game_id  TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    phase    TEXT NOT NULL,
    power    TEXT NOT NULL,
    spoke    INTEGER NOT NULL,               -- 0 = said nothing to anyone: silence
    PRIMARY KEY (game_id, phase, power)
);
CREATE TABLE IF NOT EXISTS verdicts (        -- every promise, scored against the orders given
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id    TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    phase      TEXT NOT NULL,
    commitment TEXT NOT NULL,                -- JSON
    verdict    TEXT NOT NULL,                -- KEPT | BROKEN | VOID
    reason     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_calls (     -- every model call, in full, with its cost
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    power       TEXT NOT NULL,
    phase       TEXT NOT NULL,
    step        TEXT NOT NULL,               -- press:N | reply | orders | repair
    model       TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    response    TEXT,
    error       TEXT,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd    REAL NOT NULL DEFAULT 0,
    latency_ms  INTEGER NOT NULL DEFAULT 0,
    at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_actions (   -- every input an agent tried, accepted or not
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id  TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    power    TEXT NOT NULL,
    phase    TEXT NOT NULL,
    kind     TEXT NOT NULL,     -- response | message | order | commitment | submission | deadline
    payload  TEXT NOT NULL,     -- exactly what it sent, as JSON
    ok       INTEGER NOT NULL,  -- 0 = faulty
    error    TEXT,              -- why it was refused
    at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS actions_by_game ON agent_actions(game_id, power, ok);
CREATE TABLE IF NOT EXISTS submissions (     -- who has handed in orders this phase
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    phase   TEXT NOT NULL,
    power   TEXT NOT NULL,
    at      TEXT NOT NULL,
    PRIMARY KEY (game_id, phase, power)
);
CREATE TABLE IF NOT EXISTS notes (           -- an agent's private notebook, carried turn to turn
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    power   TEXT NOT NULL,
    phase   TEXT NOT NULL,
    text    TEXT NOT NULL,
    at      TEXT NOT NULL
);
"""

# Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS never
# alters an existing table, so an old database would silently lack them.
_ADDED = [("messages", "kind", "TEXT NOT NULL DEFAULT 'text'"),
          ("games", "opponents", "TEXT NOT NULL DEFAULT 'bots'"),
          ("games", "model", "TEXT"),
          ("games", "deadline", "REAL")]

_local = threading.local()


def _migrate(c: sqlite3.Connection) -> None:
    # Private plans, press rounds and intent were measured once and then dropped.
    # Those tables only ever held test data, so an old shape is rebuilt, not migrated.
    stale = {"charts": {"plan", "round"}, "verdicts": {"intent"}}
    for table, cols in stale.items():
        if cols & {r[1] for r in c.execute(f"PRAGMA table_info({table})")}:
            c.execute(f"DROP TABLE {table}")
    c.executescript(_SCHEMA)
    c.commit()


def _conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        _migrate_first(c)
        _local.conn = c
    return c


def _migrate_first(c: sqlite3.Connection) -> None:
    # Old tables must gain their columns before the schema's indexes refer to them.
    exists = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if exists:
        for table, col, decl in _ADDED:
            if table in exists and col not in {r[1] for r in c.execute(f"PRAGMA table_info({table})")}:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    c.executescript(_SCHEMA)
    _migrate(c)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- games
def create_game(game_id: str, human_power: str, game: diplomacy.Game,
                opponents: str = "bots", model: str | None = None) -> None:
    c = _conn()
    now = _now()
    c.execute(
        "INSERT OR REPLACE INTO games (id, human_power, saved, last_result, opponents, model,"
        " created_at, updated_at) VALUES (?,?,?,NULL,?,?,?,?)",
        (game_id, human_power, json.dumps(to_saved_game_format(game)), opponents, model, now, now),
    )
    c.commit()


def seating(game_id: str) -> dict | None:
    """Who sits where: the human's power, and whether the rest are bots or agents."""
    r = _conn().execute("SELECT human_power, opponents, model FROM games WHERE id=?", (game_id,)).fetchone()
    return None if r is None else {"human": r["human_power"], "opponents": r["opponents"], "model": r["model"]}


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


def last_result(game_id: str) -> dict | None:
    r = _conn().execute("SELECT last_result FROM games WHERE id=?", (game_id,)).fetchone()
    return json.loads(r["last_result"]) if r and r["last_result"] else None


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
def add_message(game_id: str, sender: str, recipient: str, text: str, phase: str,
                kind: str = "text") -> dict:
    c = _conn()
    m = {"sender": sender, "to": recipient, "text": text, "phase": phase, "at": _now(), "kind": kind}
    c.execute("INSERT INTO messages (game_id, sender, recipient, text, phase, at, kind)"
              " VALUES (?,?,?,?,?,?,?)",
              (game_id, sender, recipient, text, phase, m["at"], kind))
    c.commit()
    return m


def messages_for(game_id: str, power: str) -> list[dict]:
    """Only what this power can see. Enforced here, not in the browser."""
    rows = _conn().execute(
        "SELECT id, sender, recipient, text, phase, at, kind FROM messages"
        " WHERE game_id=? AND (recipient='GLOBAL' OR sender=? OR recipient=?)"
        " ORDER BY id", (game_id, power, power)).fetchall()
    return [{"id": r["id"], "sender": r["sender"], "to": r["recipient"], "text": r["text"],
             "phase": r["phase"], "at": r["at"], "kind": r["kind"]} for r in rows]


# ---------------------------------------------------------------- research
def save_chart(game_id: str, chart) -> None:
    """A player's final commitment sheet for the phase, written as it submits."""
    from dataclasses import asdict
    c = _conn()
    c.execute("INSERT OR REPLACE INTO charts (game_id, power, phase, commitments, rejected, at)"
              " VALUES (?,?,?,?,?,?)",
              (game_id, chart.power, chart.phase,
               json.dumps([asdict(x) for x in chart.commitments]),
               json.dumps(chart.rejected), _now()))
    c.commit()


def charts_in_phase(game_id: str, phase: str) -> list[dict]:
    rows = _conn().execute("SELECT * FROM charts WHERE game_id=? AND phase=?", (game_id, phase)).fetchall()
    return [{"power": r["power"], "commitments": json.loads(r["commitments"]),
             "rejected": json.loads(r["rejected"])} for r in rows]


def senders_in_phase(game_id: str, phase: str) -> set[str]:
    rows = _conn().execute("SELECT DISTINCT sender FROM messages WHERE game_id=? AND phase=?",
                           (game_id, phase)).fetchall()
    return {r["sender"] for r in rows}


def record_turn(game_id: str, phase: str, spoke: dict[str, bool], verdicts: list[dict]) -> None:
    """Written once, as the phase resolves. Idempotent for the same phase."""
    c = _conn()
    c.execute("DELETE FROM turns WHERE game_id=? AND phase=?", (game_id, phase))
    c.execute("DELETE FROM verdicts WHERE game_id=? AND phase=?", (game_id, phase))
    c.executemany("INSERT INTO turns (game_id, phase, power, spoke) VALUES (?,?,?,?)",
                  [(game_id, phase, p, int(v)) for p, v in spoke.items()])
    c.executemany("INSERT INTO verdicts (game_id, phase, commitment, verdict, reason)"
                  " VALUES (?,?,?,?,?)",
                  [(game_id, phase, json.dumps(v["commitment"]), v["verdict"], v["reason"])
                   for v in verdicts])
    c.commit()


def turns_for(game_id: str) -> list[dict]:
    return [dict(r) for r in _conn().execute(
        "SELECT phase, power, spoke FROM turns WHERE game_id=? ORDER BY rowid", (game_id,)).fetchall()]


def verdicts_for(game_id: str) -> list[dict]:
    return [{"phase": r["phase"], "commitment": json.loads(r["commitment"]), "verdict": r["verdict"],
             "reason": r["reason"]}
            for r in _conn().execute("SELECT * FROM verdicts WHERE game_id=? ORDER BY id", (game_id,))]


# ---------------------------------------------------------------- agents
def log_call(game_id: str, power: str, phase: str, step: str, model: str, prompt: str,
             response: str | None, error: str | None, usage: dict) -> None:
    c = _conn()
    c.execute("INSERT INTO agent_calls (game_id, power, phase, step, model, prompt, response, error,"
              " input_tokens, cached_tokens, output_tokens, cost_usd, latency_ms, at)"
              " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (game_id, power, phase, step, model, prompt, response, error,
               usage.get("input_tokens", 0), usage.get("cached_tokens", 0), usage.get("output_tokens", 0),
               usage.get("cost_usd", 0.0), usage.get("latency_ms", 0), _now()))
    c.commit()


def calls_for(game_id: str) -> list[dict]:
    return [dict(r) for r in _conn().execute(
        "SELECT * FROM agent_calls WHERE game_id=? ORDER BY id", (game_id,)).fetchall()]


def game_cost(game_id: str) -> float:
    r = _conn().execute("SELECT COALESCE(SUM(cost_usd),0) FROM agent_calls WHERE game_id=?", (game_id,)).fetchone()
    return float(r[0])


def add_note(game_id: str, power: str, phase: str, text: str) -> None:
    c = _conn()
    c.execute("INSERT INTO notes (game_id, power, phase, text, at) VALUES (?,?,?,?,?)",
              (game_id, power, phase, text, _now()))
    c.commit()


def notes_for(game_id: str, power: str, limit: int = 6) -> list[dict]:
    rows = _conn().execute("SELECT phase, text FROM notes WHERE game_id=? AND power=?"
                           " ORDER BY rowid DESC LIMIT ?", (game_id, power, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def log_action(game_id: str, power: str, phase: str, kind: str, payload, ok: bool,
               error: str | None = None) -> None:
    c = _conn()
    c.execute("INSERT INTO agent_actions (game_id, power, phase, kind, payload, ok, error, at)"
              " VALUES (?,?,?,?,?,?,?,?)",
              (game_id, power, phase, kind, json.dumps(payload), int(ok), error, _now()))
    c.commit()


def actions_for(game_id: str, faulty_only: bool = False) -> list[dict]:
    q = "SELECT * FROM agent_actions WHERE game_id=?" + (" AND ok=0" if faulty_only else "") + " ORDER BY id"
    return [{**dict(r), "payload": json.loads(r["payload"])} for r in _conn().execute(q, (game_id,))]


def fault_counts(game_id: str) -> dict[str, dict]:
    """power -> {attempts, faulty, by_kind: {kind: faulty}}"""
    out: dict[str, dict] = {}
    for r in _conn().execute("SELECT power, kind, COUNT(*) n, SUM(ok=0) bad FROM agent_actions"
                             " WHERE game_id=? GROUP BY power, kind", (game_id,)):
        row = out.setdefault(r["power"], {"attempts": 0, "faulty": 0, "byKind": {}})
        row["attempts"] += r["n"]
        row["faulty"] += r["bad"]
        if r["bad"]:
            row["byKind"][r["kind"]] = r["bad"]
    return out


def mark_submitted(game_id: str, phase: str, power: str) -> None:
    c = _conn()
    c.execute("INSERT OR IGNORE INTO submissions (game_id, phase, power, at) VALUES (?,?,?,?)",
              (game_id, phase, power, _now()))
    c.commit()


def submitted(game_id: str, phase: str) -> set[str]:
    return {r["power"] for r in _conn().execute(
        "SELECT power FROM submissions WHERE game_id=? AND phase=?", (game_id, phase))}


def set_deadline(game_id: str, deadline: float | None) -> None:
    c = _conn()
    c.execute("UPDATE games SET deadline=? WHERE id=?", (deadline, game_id))
    c.commit()


def deadline(game_id: str) -> float | None:
    r = _conn().execute("SELECT deadline FROM games WHERE id=?", (game_id,)).fetchone()
    return r["deadline"] if r else None
