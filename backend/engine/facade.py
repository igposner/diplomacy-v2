"""The only module that touches diplomacy.Game.

Everything the UI, the agents and the log need comes through here in one shape,
so a change in the engine's surface is a change in exactly one file.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import diplomacy

from .orders import describe

POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]

# A solo is eighteen of the thirty-four centres. The engine carries the number
# (game.victory == [18]) but only ends a game through its own internal path, so
# the rule is stated here where the rest of the game-level rules live.
VICTORY_CENTERS = 18


def long_phase(short: str) -> str:
    """S1901M -> SPRING 1901 MOVEMENT, the form the rest of the code uses."""
    season = {"S": "SPRING", "F": "FALL", "W": "WINTER"}[short[0]]
    kind = {"M": "MOVEMENT", "R": "RETREATS", "A": "ADJUSTMENTS"}[short[-1]]
    return f"{season} {short[1:5]} {kind}"
# Without a cap a stalemate runs forever; at the cap the game is scored on
# centres held, as agreed in docs/PLAN.md.
FINAL_YEAR = 1920


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
    def year(self) -> int:
        try:
            return int(str(self.game.phase).split()[1])
        except (IndexError, ValueError):
            return 0

    @property
    def winner(self) -> str | None:
        """The power holding a solo, if any."""
        for name, p in self.game.powers.items():
            if len(p.centers) >= VICTORY_CENTERS:
                return name
        return None

    @property
    def standings(self) -> list[dict]:
        rows = [{"power": n, "centers": len(p.centers), "units": len(p.units)}
                for n, p in self.game.powers.items()]
        rows.sort(key=lambda r: (-r["centers"], r["power"]))
        return rows

    @property
    def done(self) -> bool:
        return bool(self.game.is_game_done) or self.winner is not None or self.year > FINAL_YEAR

    @property
    def outcome(self) -> dict | None:
        """How the game ended, or None while it is still running."""
        if not self.done:
            return None
        w = self.winner
        rows = self.standings
        if w:
            return {"kind": "solo", "winner": w, "centers": len(self.game.powers[w].centers),
                    "year": self.year, "standings": rows}
        top = rows[0]["centers"]
        return {"kind": "draw", "winner": None, "year": self.year, "standings": rows,
                "leaders": [r["power"] for r in rows if r["centers"] == top]}

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
            "outcome": self.outcome,
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
        """Replace this power's orders for the phase. An empty list clears them."""
        bad = self.validate(power, orders)
        if bad:
            raise ValueError(f"illegal orders for {power}: {bad}")
        self.game.clear_orders(power)
        if orders:
            self.game.set_orders(power, orders)

    def history(self) -> list[dict]:
        """Every phase already played: the board as it stood, the orders given, what happened."""
        out = []
        for d in self.game.get_phase_history():
            st = d.state
            powers = {n: {"units": sorted(st["units"].get(n, [])), "centers": sorted(st["centers"].get(n, [])),
                          "homes": sorted(st["homes"].get(n, []))} for n in self.game.powers}
            results = {u: [str(r).upper() for r in rs if str(r)] for u, rs in (d.results or {}).items()}
            orders = []
            for n, os_ in (d.orders or {}).items():
                for o in os_ or []:
                    unit = " ".join(o.split()[:2])
                    codes = results.get(unit, [])
                    orders.append({"power": n, "order": o, "english": describe(o),
                                   "outcomes": codes or ["OK"], "ok": not codes})
            out.append({"phase": long_phase(d.name), "short": d.name, "powers": powers,
                        "centerOwners": {c: n for n, p in powers.items() for c in p["centers"]},
                        "orders": orders})
        return out

    def process(self) -> PhaseResult:
        if self.done:
            raise ValueError("the game is over")
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
