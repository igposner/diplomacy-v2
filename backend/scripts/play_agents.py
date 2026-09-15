"""A headless game: seven agents, no human. Prints cost, failures and promise-keeping.

    ./venv/bin/python scripts/play_agents.py --model dummy            # free, offline
    ./venv/bin/python scripts/play_agents.py --model deepseek-flash --phases 4 --cap 1.00
"""
from __future__ import annotations

import argparse, asyncio, os, sys, uuid
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import storage
from agents.models import make_model
from agents.table import Table
from engine.facade import POWERS, Facade
from research.record import game_summary, record_phase


async def play(model_name: str, phases: int, rounds: int, cap: float, seed: int | None) -> str:
    f = Facade()
    gid = "headless-" + uuid.uuid4().hex[:6]
    storage.create_game(gid, "", f.game, "agents", model_name)
    model = make_model(model_name)
    if seed is not None and hasattr(model, "rng"):
        model.rng.seed(seed)
    t = Table(gid, f, {p: model for p in POWERS}, rounds=rounds, cost_cap_usd=cap)
    for _ in range(phases):
        if f.done:
            break
        await t.play_phase()
        record_phase(gid, f)
        from main import result_json
        storage.save_game(gid, f.game, result_json(f.process()))
        print(f"  {f.phase:<26} ${storage.game_cost(gid):.4f}", flush=True)
    return gid


def report(gid: str) -> None:
    calls = storage.calls_for(gid)
    errors = Counter(c["step"].split(":")[0] + (": " + c["error"].split(":")[0] if c["error"] else "")
                     for c in calls if c["error"])
    print(f"\ngame {gid}: {len(calls)} calls, ${storage.game_cost(gid):.4f}, "
          f"{sum(c['input_tokens'] for c in calls)} in / {sum(c['output_tokens'] for c in calls)} out tokens")
    for k, n in errors.most_common():
        print(f"  failure  {n:>3}  {k}")
    for p, s in sorted(game_summary(gid, set()).items()):
        d = s.to_dict()
        print(f"  {p:<8} promises {d['made']:>3}  kept {d['kept']:>3}  broken {d['broken']:>3}  "
              f"void {d['void']:>2}  honesty {d['honesty'] if d['honesty'] is None else round(d['honesty'], 2)}  "
              f"silence {d['silence'] if d['silence'] is None else round(d['silence'], 2)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dummy")
    ap.add_argument("--phases", type=int, default=200)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--cap", type=float, default=3.0, help="stop spending at this many dollars")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    report(asyncio.run(play(a.model, a.phases, a.rounds, a.cap, a.seed)))
