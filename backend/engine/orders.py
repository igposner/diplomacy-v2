"""The one place that knows Diplomacy order syntax.

The UI builds Order objects, agents return JSON that parses into Order objects,
and only this module turns them into the strings the engine accepts. Nothing
else in the codebase should ever concatenate an order string.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

UnitKind = Literal["A", "F"]


@dataclass(frozen=True)
class Hold:
    kind: UnitKind
    loc: str
    def to_engine(self) -> str: return f"{self.kind} {self.loc} H"


@dataclass(frozen=True)
class Move:
    kind: UnitKind
    loc: str
    dest: str
    via_convoy: bool = False
    def to_engine(self) -> str:
        return f"{self.kind} {self.loc} - {self.dest}" + (" VIA" if self.via_convoy else "")


@dataclass(frozen=True)
class SupportHold:
    kind: UnitKind
    loc: str
    target_kind: UnitKind
    target: str
    def to_engine(self) -> str:
        return f"{self.kind} {self.loc} S {self.target_kind} {self.target}"


@dataclass(frozen=True)
class SupportMove:
    kind: UnitKind
    loc: str
    target_kind: UnitKind
    target: str
    dest: str
    def to_engine(self) -> str:
        return f"{self.kind} {self.loc} S {self.target_kind} {self.target} - {self.dest}"


@dataclass(frozen=True)
class Convoy:
    loc: str
    target: str
    dest: str
    def to_engine(self) -> str: return f"F {self.loc} C A {self.target} - {self.dest}"


@dataclass(frozen=True)
class Retreat:
    kind: UnitKind
    loc: str
    dest: str
    def to_engine(self) -> str: return f"{self.kind} {self.loc} R {self.dest}"


@dataclass(frozen=True)
class Disband:
    kind: UnitKind
    loc: str
    def to_engine(self) -> str: return f"{self.kind} {self.loc} D"


@dataclass(frozen=True)
class Build:
    kind: UnitKind
    loc: str
    def to_engine(self) -> str: return f"{self.kind} {self.loc} B"


@dataclass(frozen=True)
class Waive:
    def to_engine(self) -> str: return "WAIVE"


Order = Union[Hold, Move, SupportHold, SupportMove, Convoy, Retreat, Disband, Build, Waive]

_U = r"([AF])"
_P = r"([A-Z]{3}(?:/[A-Z]{2})?)"


def parse(s: str) -> Order:
    """Inverse of to_engine(). Raises ValueError on anything it does not recognise."""
    import re
    t = " ".join(s.strip().upper().split())
    if t == "WAIVE":
        return Waive()
    for pattern, build in (
        (rf"^{_U} {_P} H$", lambda m: Hold(m[1], m[2])),
        (rf"^{_U} {_P} - {_P}( VIA)?$", lambda m: Move(m[1], m[2], m[3], bool(m[4]))),
        (rf"^{_U} {_P} S {_U} {_P} - {_P}$", lambda m: SupportMove(m[1], m[2], m[3], m[4], m[5])),
        (rf"^{_U} {_P} S {_U} {_P}$", lambda m: SupportHold(m[1], m[2], m[3], m[4])),
        (rf"^F {_P} C A {_P} - {_P}$", lambda m: Convoy(m[1], m[2], m[3])),
        (rf"^{_U} {_P} R {_P}$", lambda m: Retreat(m[1], m[2], m[3])),
        (rf"^{_U} {_P} D$", lambda m: Disband(m[1], m[2])),
        (rf"^{_U} {_P} B$", lambda m: Build(m[1], m[2])),
    ):
        m = re.match(pattern, t)
        if m:
            return build(m)
    raise ValueError(f"unrecognised order: {s!r}")


def describe(s: str) -> str:
    """Plain English for the order list. Falls back to the raw string."""
    try:
        o = parse(s)
    except ValueError:
        return s
    unit = {"A": "Army", "F": "Fleet"}
    if isinstance(o, Hold):        return f"{unit[o.kind]} {o.loc} holds"
    if isinstance(o, Move):        return f"{unit[o.kind]} {o.loc} to {o.dest}" + (" by convoy" if o.via_convoy else "")
    if isinstance(o, SupportHold): return f"{unit[o.kind]} {o.loc} supports {o.target}"
    if isinstance(o, SupportMove): return f"{unit[o.kind]} {o.loc} supports {o.target} into {o.dest}"
    if isinstance(o, Convoy):      return f"Fleet {o.loc} convoys {o.target} to {o.dest}"
    if isinstance(o, Retreat):     return f"{unit[o.kind]} {o.loc} retreats to {o.dest}"
    if isinstance(o, Disband):     return f"Disband the {unit[o.kind].lower()} in {o.loc}"
    if isinstance(o, Build):       return f"Build {'an army' if o.kind == 'A' else 'a fleet'} in {o.loc}"
    return "Waive a build"
