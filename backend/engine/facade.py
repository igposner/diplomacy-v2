"""The only module that touches diplomacy.Game.

Everything the UI, the agents and the log need comes through here in one shape,
so a change in the engine's surface is a change in exactly one file.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import diplomacy

from .orders import describe

POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]


@dataclass
class OrderResult:
    power: str
    order: str
    english: str
    outcomes: list[str] = field(default_factory=list)   # OK / BOUNCE / CUT / VOID / DISLODGED ...

    @property
    def ok(self) -> bool:
        return not self.outcomes or self.outcomes == ["OK"]


@dataclass
class PhaseResult:
    phase: str
    orders: list[OrderResult]
    dislodged: dict[str, list[str]]     # power -> units needing a retreat
    center_changes: dict[str, str]      # province -> new owner


class Facade:
    def __init__(self, game: diplomacy.Game | None = None):
        self.game = game or diplomacy.Game()

    # -- reading ------------------------------------------------------------
    @property
    def phase(self) -> str:
        return str(self.game.phase)

    @property
    def phase_type(self) -> str:
        p = self.phase.upper()
        return "ADJUSTMENT" if "ADJUST" in p else "RETREAT" if "RETREAT" in p else "MOVEMENT"

    @property
    def done(self) -> bool:
        return bool(self.game.is_game_done)

    def legal_orders(self, power: str) -> dict[str, list[str]]:
        locs = self.game.get_orderable_locations(power)
        every = self.game.get_all_possible_orders()
        return {loc: sorted(every.get(loc, [])) for loc in locs if every.get(loc)}

    def state(self, viewer: str | None = None) -> dict:
        powers = {
            name: {
                "units": sorted(p.units),
                "centers": sorted(p.centers),
                "homes": sorted(self.game.map.homes.get(name, [])),
            }
            for name, p in self.game.powers.items()
        }
        owner = {c: name for name, p in self.game.powers.items() for c in p.centers}
        out = {
            "phase": self.phase,
            "phaseType": self.phase_type,
            "done": self.done,
            "powers": powers,
            "centerOwners": owner,
            "viewer": viewer,
        }
        if viewer:
            out["legalOrders"] = self.legal_orders(viewer)
            out["orderable"] = sorted(self.legal_orders(viewer))
        return out

    # -- writing ------------------------------------------------------------
    def validate(self, power: str, orders: list[str]) -> list[str]:
        """Return the orders the engine would reject. Empty list means all legal."""
        legal = {o for opts in self.legal_orders(power).values() for o in opts}
        return [o for o in orders if o not in legal]

    def submit(self, power: str, orders: list[str]) -> None:
        bad = self.validate(power, orders)
        if bad:
            raise ValueError(f"illegal orders for {power}: {bad}")
        self.game.set_orders(power, orders)

    def process(self) -> PhaseResult:
        phase = self.phase
        before = {c: n for n, p in self.game.powers.items() for c in p.centers}
        # power.orders is {unit: rest-of-order}, e.g. {"A PAR": "- BUR"}.
        # result_history is keyed by that same unit string; an empty list means success.
        submitted = {
            n: [(unit, f"{unit} {rest}".strip()) for unit, rest in p.orders.items() if rest]
            for n, p in self.game.powers.items()
        }
        self.game.process()
        try:
            raw_results = self.game.result_history.last_value() or {}
        except Exception:
            raw_results = {}

        results = []
        for power, pairs in submitted.items():
            for unit, order in pairs:
                codes = [str(r).upper() for r in raw_results.get(unit, []) if str(r)]
                results.append(OrderResult(power, order, describe(order), codes or ["OK"]))

        after = {c: n for n, p in self.game.powers.items() for c in p.centers}
        changes = {c: n for c, n in after.items() if before.get(c) != n}
        dislodged = {
            n: sorted(self.game.get_orderable_locations(n))
            for n in self.game.powers
            if self.phase_type == "RETREAT" and self.game.get_orderable_locations(n)
        }
        return PhaseResult(phase, results, dislodged, changes)
