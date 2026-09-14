"""Smoke test: seven scripted bots play a full game through the facade.

Deliberately does not assert on strategy -- it asserts the loop terminates, the
engine accepts every order the facade offers, and results come back attached to
the right orders. Run with: python tests/test_smoke.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots.greedy_bot import GreedyBot
from engine.facade import POWERS, Facade


async def main() -> int:
    f = Facade()
    bots = {p: GreedyBot(p) for p in POWERS}
    phases = 0
    results_seen = 0

    while not f.done and phases < 60:
        for p in POWERS:
            if f.legal_orders(p):
                orders = await bots[p].decide_orders(f.game)
                bad = f.validate(p, orders)
                assert not bad, f"bot produced orders the facade rejects: {bad}"
                f.submit(p, orders)
        r = f.process()
        results_seen += len(r.orders)
        for o in r.orders:
            assert o.outcomes, f"no outcome recorded for {o.order}"
            assert o.english and o.english != o.order or " " in o.english
        phases += 1
        if int(f.phase.split()[1]) >= 1912:
            break

    counts = {p: len(f.game.powers[p].centers) for p in POWERS}
    owned = [c for p in POWERS for c in f.game.powers[p].centers]
    # Centres left neutral are normal, so owned <= 34; what must never happen is
    # the same centre being owned twice.
    assert len(owned) <= 34, f"more owned centres than exist: {counts}"
    assert len(owned) == len(set(owned)), "a centre is owned by two powers"
    print(f"ok: {phases} phases, {results_seen} order results, "
          f"{len(owned)}/34 centres owned, {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
