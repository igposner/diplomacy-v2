"""A headless game: seven agents, no human, on the same clock as a human game.

    ./venv/bin/python scripts/play_agents.py --model dummy --fast       # free, offline, seconds
    ./venv/bin/python scripts/play_agents.py --model deepseek-flash --phases 2 --cap 0.50

Prints cost, every kind of faulty input, and promise-keeping.
"""
from __future__ import annotations

import argparse, asyncio, os, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import storage
from agents.models import make_model
from agents.table import Table
from engine.facade import POWERS, Facade
from research.record import game_summary


async def play(a) -> str:
    from main import resolve_phase
    f = Facade()
    gid = "headless-" + uuid.uuid4().hex[:6]
    storage.create_game(gid, "", f.game, "agents", a.model)
    model = make_model(a.model)
    if a.seed is not None and hasattr(model, "rng"):
        model.rng.seed(a.seed)
    played = 0

    async def resolve():
        nonlocal played
        resolve_phase(gid, f)
        played += 1
        print(f"  {f.phase:<26} ${storage.game_cost(gid):.4f}", flush=True)

    timing = dict(phase_seconds=3, min_interval=0.02, idle_after=0.05, final_call=1) if a.fast else \
        dict(phase_seconds=a.phase_seconds)
    t = Table(gid, f, {p: model for p in POWERS}, resolve=resolve, cost_cap_usd=a.cap, **timing)
    while not f.done and played < a.phases:
        await t.play_phase()
    return gid


def report(gid: str) -> None:
    calls = storage.calls_for(gid)
    print(f"\ngame {gid}: {len(calls)} calls, ${storage.game_cost(gid):.4f}, "
          f"{sum(c['input_tokens'] for c in calls)} in / {sum(c['output_tokens'] for c in calls)} out tokens")
    for p, c in sorted(storage.fault_counts(gid).items()):
        kinds = ", ".join(f"{k} {n}" for k, n in sorted(c["byKind"].items())) or "none"
        print(f"  {p:<8} inputs {c['attempts']:>4}  faulty {c['faulty']:>3}  ({kinds})")
    for p, s in sorted(game_summary(gid, set()).items()):
        d = s.to_dict()
        fmt = lambda v: "-" if v is None else f"{v:.2f}"
        print(f"  {p:<8} promises {d['made']:>3}  kept {d['kept']:>3}  broken {d['broken']:>3}  "
              f"void {d['void']:>2}  honesty {fmt(d['honesty'])}  silence {fmt(d['silence'])}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dummy")
    ap.add_argument("--phases", type=int, default=1000)
    ap.add_argument("--phase-seconds", type=float, default=120)
    ap.add_argument("--fast", action="store_true", help="offline testing: a 3 s clock, no pacing")
    ap.add_argument("--cap", type=float, default=5.0, help="stop spending at this many dollars")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    report(asyncio.run(play(a)))
