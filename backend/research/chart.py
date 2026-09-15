"""The commitment sheet: the promises a player hands in with its orders.

    "commitments": [{"to": "ENGLAND", "kind": "support_move",
                     "unit": "A MUN", "target": "A PAR", "dest": "BUR"},
                    {"to": "RUSSIA", "kind": "no_enter", "province": "SIL",
                     "if": {"power": "RUSSIA", "order": "A WAR H"}}]

It is written at the moment of submission and lists each promise about this
phase's orders in the final form the player gave it: one withdrawn in a later
message is left off, one revised is written as revised. An empty sheet is valid;
nobody owes anyone a word. The sheet is never shown to other players.

Known gap: the sheet is self-reported. A promise left off it is not scored, so
a player who omits the ones it breaks looks honest. Every message is stored in
full so the sheet can be audited against what was actually said.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine.facade import POWERS
from research.commitments import Commitment, Condition


@dataclass
class Chart:
    power: str
    phase: str
    commitments: list[Commitment] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)   # what could not be scored, and why


def parse_chart(power: str, phase: str, data: dict, legal: dict[str, list[str]] | None = None) -> Chart:
    """Turn a sheet into scoreable commitments. Nothing is silently dropped:
    everything refused is listed in `rejected` with the reason."""
    power = power.upper()
    chart = Chart(power, phase)
    others = set(POWERS) - {power}
    for raw in data.get("commitments") or []:
        if not isinstance(raw, dict):
            chart.rejected.append(f"{raw!r} is not a commitment object")
            continue
        to = str(raw.get("to", "")).upper()
        if to not in others:
            chart.rejected.append(f"commitment to {to!r}, who is not another power")
            continue
        cond = raw.get("if")
        try:
            chart.commitments.append(Commitment(
                speaker=power, recipient=to, phase=phase, kind=raw.get("kind"),
                unit=raw.get("unit"), target=raw.get("target"), dest=raw.get("dest"),
                province=raw.get("province"),
                condition=Condition(str(cond["power"]).upper(), str(cond["order"])) if cond else None,
            ))
        except (ValueError, KeyError, TypeError) as e:
            chart.rejected.append(f"unscoreable commitment {raw}: {e}")
    return chart
