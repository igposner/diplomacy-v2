"""
End-to-end WebSocket test for Step 2.
Requires: uvicorn main:app --port 8000 running in another terminal from backend/
"""
import asyncio
import json
import sys

import httpx
import websockets

BASE_HTTP = "http://localhost:8000"
BASE_WS = "ws://localhost:8000"
TARGET_PHASES = 5


async def recv_json(ws):
    return json.loads(await ws.recv())


async def main():
    # Create game via REST
    async with httpx.AsyncClient() as http:
        resp = await http.post(f"{BASE_HTTP}/api/games", json={"human_power": "FRANCE"})
        resp.raise_for_status()
        game_id = resp.json()["game_id"]
    print(f"Created game: {game_id}")

    async with websockets.connect(f"{BASE_WS}/api/ws/{game_id}") as ws:
        msg = await recv_json(ws)
        assert msg["type"] == "state", f"Expected initial state, got: {msg}"
        print(f"Connected. Initial phase: {msg['data']['phase']}")

        completed = 0

        while completed < TARGET_PHASES:
            state = msg["data"]
            orderable = state.get("orderable", [])
            possible = state.get("possible_orders", {})

            if orderable:
                orders = [possible[loc][0] for loc in orderable if possible.get(loc)]
                print(f"  Submitting {len(orders)} order(s) for {state['phase']}")
                await ws.send(json.dumps({"type": "submit_orders", "orders": orders}))
                msg = await recv_json(ws)
                assert msg["type"] == "state", f"Expected state after submit_orders, got: {msg}"

            else:
                print(f"  No orders this phase ({state['phase']}), advancing directly")

            await ws.send(json.dumps({"type": "advance_phase"}))
            msg = await recv_json(ws)

            # advance_phase sends state; if done it follows with game_over
            if msg["type"] == "game_over":
                print(f"\nGame over (early)! Winners: {msg['winners']}")
                sys.exit(0)

            assert msg["type"] == "state", f"Expected state after advance_phase, got: {msg}"
            completed += 1
            print(f"  Phase {completed}/{TARGET_PHASES} done → {msg['data']['phase']}")

            if msg["data"]["done"]:
                game_over = await recv_json(ws)
                assert game_over["type"] == "game_over", f"Expected game_over, got: {game_over}"
                print(f"\nGame over! Winners: {game_over['winners']}")
                sys.exit(0)

    print(f"\nCompleted {completed}/{TARGET_PHASES} phase(s). Disconnected cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
