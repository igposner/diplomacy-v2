"""Where the instrument meets the game: score a phase at the moment it resolves.

It has to be then. Rule 3 (a promise you could not have broken is void) needs
the legal orders of that exact position, which are gone once the phase moves on.
"""
from __future__ import annotations

from dataclasses import asdict

import storage
from engine.facade import POWERS, Facade
from research.commitments import Commitment, Condition, Scored, Summary, score_phase, summarize


def _commitment(d: dict) -> Commitment:
    cond = d.get("condition")
    return Commitment(**{**d, "condition": Condition(**cond) if cond else None})


def record_phase(game_id: str, f: Facade) -> list[Scored]:
    """Call after every power's orders are set and before f.process()."""
    phase = f.phase
    legal = {p: f.legal_orders(p) for p in POWERS}
    active = [p for p in POWERS if legal[p]]
    orders = {p: f.game.get_orders(p) for p in POWERS}
    orderable = {p: set(legal[p]) for p in POWERS}

    charts = storage.charts_in_phase(game_id, phase)
    promises = [_commitment(c) for ch in charts for c in ch["commitments"]]
    plans = {ch["power"]: ch["plan"] for ch in charts}
    scored = score_phase(promises, orders, orderable, plans, legal)

    # Silence means no word to anyone: no message and no promise.
    talked = storage.senders_in_phase(game_id, phase) | {c.speaker for c in promises}
    storage.record_turn(game_id, phase, {p: p in talked for p in active},
                        [{"commitment": asdict(s.commitment), "verdict": s.verdict,
                          "intent": s.intent, "reason": s.reason} for s in scored])
    return scored


def game_summary(game_id: str, humans: set[str]) -> dict[str, Summary]:
    by_phase: dict[str, dict] = {}
    for t in storage.turns_for(game_id):
        row = by_phase.setdefault(t["phase"], {"scored": [], "active": set(), "spoke": set()})
        row["active"].add(t["power"])
        if t["spoke"]:
            row["spoke"].add(t["power"])
    for v in storage.verdicts_for(game_id):
        by_phase.setdefault(v["phase"], {"scored": [], "active": set(), "spoke": set()})["scored"].append(
            Scored(_commitment(v["commitment"]), v["verdict"], v["intent"], v["reason"]))
    return summarize([(ph, r["scored"], r["active"], r["spoke"]) for ph, r in by_phase.items()], humans)
