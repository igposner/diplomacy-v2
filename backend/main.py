"""Diplomacy API. Thin: every rules decision belongs to engine.facade,
and nothing lives only in memory -- see storage.py."""
from __future__ import annotations

import uuid
from typing import Literal

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import storage
from bots.greedy_bot import GreedyBot
from agents.models import MissingKey, make_model
from agents.table import Table
from engine.facade import POWERS, Facade, PhaseResult
from research.record import game_summary, record_phase

app = FastAPI(title="Diplomacy API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# A cache in front of SQLite, not the source of truth.
LIVE: dict[str, Facade] = {}
HUMAN: dict[str, str] = {}
TABLES: dict[str, Table] = {}   # agent games only; rebuilt from storage after a restart
MODELS = make_model             # tests swap this for an offline model
TABLE_OPTIONS: dict = {}        # and shorten the clock through this


class NewGame(BaseModel):
    power: str = "FRANCE"
    advance: int = 0          # play this many phases with scripted bots first
    opponents: Literal["bots", "agents"] = "bots"
    model: str = "deepseek-flash"


class Orders(BaseModel):
    power: str
    orders: list[str]


class Message(BaseModel):
    sender: str
    to: str
    text: str


def get(game_id: str) -> Facade:
    f = LIVE.get(game_id)
    if f is not None:
        return f
    loaded = storage.load_game(game_id)
    if loaded is None:
        raise HTTPException(404, f"no game {game_id}")
    game, human, _ = loaded
    f = Facade(game)
    LIVE[game_id] = f
    HUMAN[game_id] = human
    return f


def result_json(r: PhaseResult) -> dict:
    return {
        "phase": r.phase,
        "centerChanges": r.center_changes,
        "dislodged": r.dislodged,
        "orders": [{"power": o.power, "order": o.order, "english": o.english,
                    "outcomes": o.outcomes, "ok": o.ok} for o in r.orders],
    }


def resolve_phase(game_id: str, f: Facade) -> dict:
    """Every order is in: score the promises while the position still exists, then play it."""
    record_phase(game_id, f)
    payload = result_json(f.process())
    storage.save_game(game_id, f.game, payload)
    return payload


def table(game_id: str) -> Table | None:
    """The agents at this game, or None if the other seats are scripted bots.
    Building one starts its clock, so a restart picks the game up where it was."""
    if game_id in TABLES:
        return TABLES[game_id]
    seat = storage.seating(game_id)
    if not seat or seat["opponents"] != "agents":
        return None
    f = get(game_id)
    model = MODELS(seat["model"])
    t = _seat(game_id, f, model, seat["human"])
    return t


def _seat(game_id: str, f: Facade, model, human: str) -> Table:
    async def resolve():
        resolve_phase(game_id, f)
    t = Table(game_id, f, {p: model for p in POWERS if p != human}, resolve=resolve, human=human,
              **TABLE_OPTIONS)
    TABLES[game_id] = t
    if not f.done:
        t.start()
    return t


@app.get("/api/health")
async def health():
    return {"status": "ok", "live": len(LIVE), "stored": len(storage.list_games(1000))}


@app.get("/api/games")
async def list_games():
    return storage.list_games()


@app.post("/api/games")
async def new_game(body: NewGame):
    power = body.power.upper()
    if power not in POWERS:
        raise HTTPException(400, f"invalid power {body.power!r}")
    model = None
    if body.opponents == "agents":
        try:
            model = MODELS(body.model)
        except (MissingKey, ValueError) as e:
            raise HTTPException(400, str(e))
    f = Facade()
    bots = {p: GreedyBot(p) for p in POWERS}
    for _ in range(max(0, body.advance)):
        if f.done:
            break
        for p in POWERS:
            if f.legal_orders(p):
                f.game.set_orders(p, await bots[p].decide_orders(f.game))
        f.process()
    gid = uuid.uuid4().hex[:8]
    LIVE[gid] = f
    HUMAN[gid] = power
    storage.create_game(gid, power, f.game, body.opponents, body.model if model else None)
    if model is not None:
        _seat(gid, f, model, power)
    return {"game_id": gid, "power": power, "phase": f.phase, "opponents": body.opponents}


@app.get("/api/games/{game_id}/state")
async def state(game_id: str, power: str | None = None):
    f = get(game_id)
    loaded = storage.load_game(game_id)
    human = loaded[1] if loaded else HUMAN.get(game_id)
    # The seat is a property of the game, not of the query, so the browser does
    # not have to remember which power it picked.
    out = f.state((power or human or "").upper() or None)
    out["humanPower"] = human
    out["lastResult"] = loaded[2] if loaded else None
    t = table(game_id)
    out["opponents"] = "agents" if t else "bots"
    if t:
        done = storage.submitted(game_id, f.phase)
        out["clock"] = {"secondsLeft": round(t.seconds_left(), 1),
                        "submitted": sorted(done & t.must_submit()),
                        "waitingOn": sorted(t.waiting_on()),
                        "youSubmitted": human in done}
        out["myOrders"] = f.game.get_orders(human) if human else []
    return out


@app.get("/api/games/{game_id}/history")
async def history(game_id: str):
    """Every phase already played, oldest first. Orders are public once resolved."""
    return get(game_id).history()


@app.post("/api/games/{game_id}/orders")
async def orders(game_id: str, body: Orders):
    """Save orders without handing them in. In a timed game this is what stands
    if the clock runs out before you submit, and it may be changed after
    submitting too: the phase plays whatever stands when it closes."""
    f = get(game_id)
    if f.done:
        return _finished(f)
    power = body.power.upper()
    bad = f.validate(power, body.orders)
    if bad:
        raise HTTPException(400, {"message": "illegal orders", "orders": bad})
    f.submit(power, body.orders)
    storage.save_game(game_id, f.game)
    return {"accepted": body.orders}


def _finished(f: Facade) -> dict:
    return {"phase": f.phase, "next": f.phase, "centerChanges": {}, "dislodged": {},
            "orders": [], "outcome": f.outcome}


async def _resolve(game_id: str, f: Facade, human: str | None) -> dict:
    """Bot games only: fill in the other powers and process. NEVER the human's
    seat: their unordered units hold, which is the rule."""
    if f.done:
        return _finished(f)
    bots = {p: GreedyBot(p) for p in POWERS if p != human}
    for p, bot in bots.items():
        if f.legal_orders(p) and not f.game.powers[p].orders:
            f.game.set_orders(p, await bot.decide_orders(f.game))
    payload = resolve_phase(game_id, f)
    return {**payload, "next": f.phase, "outcome": f.outcome}


@app.post("/api/games/{game_id}/submit")
async def submit(game_id: str, body: Orders):
    """Hand in your orders. Against bots the turn resolves at once. At a timed
    table it resolves when everyone has submitted or the clock runs out."""
    f = get(game_id)
    if f.done:
        return _finished(f)
    power = body.power.upper()
    bad = f.validate(power, body.orders)
    if bad:
        raise HTTPException(400, {"message": "illegal orders", "orders": bad})
    t = table(game_id)
    if t:
        # Not final: submit again to change them until the phase closes.
        phase = f.phase
        f.submit(power, body.orders)
        storage.save_game(game_id, f.game)
        t.submitted(power)
        return {"submitted": True, "phase": phase, "waitingOn": sorted(t.waiting_on()),
                "secondsLeft": round(t.seconds_left(), 1)}
    if body.orders:
        f.submit(power, body.orders)
    loaded = storage.load_game(game_id)
    human = loaded[1] if loaded else HUMAN.get(game_id)
    return await _resolve(game_id, f, human)


@app.post("/api/games/{game_id}/process")
async def process(game_id: str):
    f = get(game_id)
    if table(game_id):
        raise HTTPException(409, "a timed game resolves on its own clock")
    loaded = storage.load_game(game_id)
    return await _resolve(game_id, f, loaded[1] if loaded else HUMAN.get(game_id))


@app.get("/api/games/{game_id}/research")
async def research(game_id: str):
    """Promise-keeping and faulty inputs per power. Closed until the game ends:
    mid-game it would tell a player who has been lying to them."""
    f = get(game_id)
    if not f.done:
        raise HTTPException(403, "research data is available once the game is over")
    loaded = storage.load_game(game_id)
    humans = {loaded[1]} if loaded and loaded[1] else set()
    return {"summary": {p: s.to_dict() for p, s in game_summary(game_id, humans).items()},
            "verdicts": storage.verdicts_for(game_id),
            "faults": storage.fault_counts(game_id)}


@app.get("/api/games/{game_id}/messages")
async def read_messages(game_id: str, power: str):
    get(game_id)
    return storage.messages_for(game_id, power.upper())


@app.post("/api/games/{game_id}/messages")
async def send_message(game_id: str, body: Message):
    f = get(game_id)
    sender, to = body.sender.upper(), body.to.upper()
    if sender not in POWERS:
        raise HTTPException(400, f"invalid sender {body.sender!r}")
    if to != "GLOBAL" and to not in POWERS:
        raise HTTPException(400, f"invalid recipient {body.to!r}")
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "empty message")
    return storage.add_message(game_id, sender, to, text[:2000], f.phase)
