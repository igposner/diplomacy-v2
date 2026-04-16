from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from importlib.metadata import version as pkg_version
from pydantic import TypeAdapter, ValidationError

from connection_manager import ConnectionManager
from game_manager import create_game, get_game
from schemas import (
    CreateGameRequest,
    ClientMessage,
    StateMessage,
    ErrorMessage,
    GameOverMessage,
)

app = FastAPI(title="Diplomacy API")
ws_manager = ConnectionManager()

_VALID_POWERS = {'AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY'}
_client_msg_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


@app.get("/api/health")
async def health():
    try:
        diplomacy_version = pkg_version("diplomacy")
    except Exception:
        diplomacy_version = "unknown"
    return {"status": "ok", "diplomacy_version": diplomacy_version}


@app.post("/api/games", response_model=dict)
async def create_game_endpoint(body: CreateGameRequest):
    power = body.human_power.upper()
    if power not in _VALID_POWERS:
        raise HTTPException(status_code=400, detail=f"Invalid power name: {body.human_power!r}")
    game_id = create_game(power)
    return {"game_id": game_id}


def _get_winners(game) -> list[str]:
    try:
        outcome = game.outcome
        if outcome:
            return list(outcome)
    except AttributeError:
        pass
    max_centers = max((len(p.centers) for p in game.powers.values()), default=0)
    return [name for name, p in game.powers.items() if len(p.centers) == max_centers]


@app.websocket("/api/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    gm = get_game(game_id)
    if gm is None:
        await websocket.close(code=4004)
        return

    await ws_manager.connect(websocket, game_id)
    await ws_manager.send_to(websocket, StateMessage(data=gm.state_for_frontend()).model_dump())

    try:
        while True:
            raw = await websocket.receive_json()

            try:
                msg = _client_msg_adapter.validate_python(raw)
            except ValidationError as exc:
                await ws_manager.send_to(
                    websocket,
                    ErrorMessage(message=f"Invalid message: {exc.error_count()} error(s)").model_dump(),
                )
                continue

            if msg.type == "get_state":
                await ws_manager.send_to(
                    websocket, StateMessage(data=gm.state_for_frontend()).model_dump()
                )

            elif msg.type == "submit_orders":
                orderable_locs = gm.game.get_orderable_locations(gm.human_power)
                all_possible = gm.game.get_all_possible_orders()
                valid_set = {o for loc in orderable_locs for o in all_possible.get(loc, [])}
                invalid = [o for o in msg.orders if o not in valid_set]
                if invalid:
                    await ws_manager.send_to(
                        websocket,
                        ErrorMessage(message=f"Invalid orders rejected: {invalid}").model_dump(),
                    )
                else:
                    gm.submit_human_orders(msg.orders)
                    await ws_manager.send_to(
                        websocket, StateMessage(data=gm.state_for_frontend()).model_dump()
                    )

            elif msg.type == "advance_phase":
                gm.advance_phase()
                await ws_manager.send_to(
                    websocket, StateMessage(data=gm.state_for_frontend()).model_dump()
                )
                if gm.game.is_game_done:
                    await ws_manager.send_to(
                        websocket,
                        GameOverMessage(winners=_get_winners(gm.game)).model_dump(),
                    )

    except WebSocketDisconnect:
        ws_manager.disconnect(game_id)
