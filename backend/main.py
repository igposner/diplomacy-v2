"""Diplomacy API. Thin: every rules decision belongs to engine.facade."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bots.greedy_bot import GreedyBot
from engine.facade import POWERS, Facade

app = FastAPI(title="Diplomacy API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GAMES: dict[str, Facade] = {}
# Press, per game. Kept in memory for now; it moves to SQLite with persistence.
MESSAGES: dict[str, list[dict]] = {}


class NewGame(BaseModel):
    power: str = "FRANCE"
    advance: int = 0          # play this many phases with scripted bots first


class Orders(BaseModel):
    power: str
    orders: list[str]


class Message(BaseModel):
    sender: str
    to: str          # a power name, or GLOBAL
    text: str


def get(game_id: str) -> Facade:
    f = GAMES.get(game_id)
    if f is None:
        raise HTTPException(404, f"no game {game_id}")
    return f


@app.get("/api/health")
async def health():
    return {"status": "ok", "games": len(GAMES)}


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
            locs = f.legal_orders(p)
            if locs:
                f.game.set_orders(p, await bots[p].decide_orders(f.game))
        f.process()
    gid = uuid.uuid4().hex[:8]
    GAMES[gid] = f
    return {"game_id": gid, "power": power, "phase": f.phase}


@app.get("/api/games/{game_id}/state")
async def state(game_id: str, power: str | None = None):
    return get(game_id).state(power.upper() if power else None)


@app.post("/api/games/{game_id}/orders")
async def orders(game_id: str, body: Orders):
    f = get(game_id)
    bad = f.validate(body.power.upper(), body.orders)
    if bad:
        raise HTTPException(400, {"message": "illegal orders", "orders": bad})
    f.submit(body.power.upper(), body.orders)
    return {"accepted": body.orders}


@app.get("/api/games/{game_id}/messages")
async def read_messages(game_id: str, power: str):
    """Only what this power can see: its own channels and anything global."""
    get(game_id)
    me = power.upper()
    return [
        m for m in MESSAGES.get(game_id, [])
        if m["to"] == "GLOBAL" or m["sender"] == me or m["to"] == me
    ]


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
    m = {"sender": sender, "to": to, "text": text[:2000], "phase": f.phase,
         "at": datetime.now(timezone.utc).isoformat()}
    MESSAGES.setdefault(game_id, []).append(m)
    return m


@app.post("/api/games/{game_id}/process")
async def process(game_id: str):
    f = get(game_id)
    bots = {p: GreedyBot(p) for p in POWERS}
    for p in POWERS:
        if f.legal_orders(p) and not f.game.powers[p].orders:
            f.game.set_orders(p, await bots[p].decide_orders(f.game))
    r = f.process()
    return {
        "phase": r.phase,
        "next": f.phase,
        "centerChanges": r.center_changes,
        "orders": [{"power": o.power, "order": o.order, "english": o.english,
                    "outcomes": o.outcomes, "ok": o.ok} for o in r.orders],
    }
