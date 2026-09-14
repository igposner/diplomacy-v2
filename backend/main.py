"""Diplomacy API. Thin: every rules decision belongs to engine.facade,
and nothing lives only in memory -- see storage.py."""
from __future__ import annotations

import uuid

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import storage
from bots.greedy_bot import GreedyBot
from engine.facade import POWERS, Facade, PhaseResult

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


class NewGame(BaseModel):
    power: str = "FRANCE"
    advance: int = 0          # play this many phases with scripted bots first


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
    storage.create_game(gid, power, f.game)
    return {"game_id": gid, "power": power, "phase": f.phase}


@app.get("/api/games/{game_id}/state")
async def state(game_id: str, power: str | None = None):
    f = get(game_id)
    out = f.state(power.upper() if power else None)
    loaded = storage.load_game(game_id)
    out["lastResult"] = loaded[2] if loaded else None
    return out


@app.post("/api/games/{game_id}/orders")
async def orders(game_id: str, body: Orders):
    f = get(game_id)
    power = body.power.upper()
    bad = f.validate(power, body.orders)
    if bad:
        raise HTTPException(400, {"message": "illegal orders", "orders": bad})
    f.submit(power, body.orders)
    storage.save_game(game_id, f.game)
    return {"accepted": body.orders}


@app.post("/api/games/{game_id}/process")
async def process(game_id: str):
    f = get(game_id)
    bots = {p: GreedyBot(p) for p in POWERS}
    for p in POWERS:
        if f.legal_orders(p) and not f.game.powers[p].orders:
            f.game.set_orders(p, await bots[p].decide_orders(f.game))
    r = f.process()
    payload = result_json(r)
    storage.save_game(game_id, f.game, payload)
    return {**payload, "next": f.phase}


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
