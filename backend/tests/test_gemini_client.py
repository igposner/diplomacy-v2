"""
End-to-end Gemini integration test (Step 3).

Requires:
  - uvicorn main:app --port 8000 running in another terminal from backend/
  - GEMINI_API_KEY set in backend/.env
"""
import asyncio
import json
import sys

import httpx
import websockets

BASE_HTTP = "http://localhost:8000"
BASE_WS = "ws://localhost:8000"

CHAT_MESSAGES = [
    "Hello Germany, would you be interested in a non-aggression pact for Spring 1901?",
    "How are you finding the early game so far? Are you worried about Russia?",
    "I'm considering moving toward Belgium — I hope we won't find ourselves in conflict.",
]


async def recv_json(ws):
    return json.loads(await ws.recv())


async def main():
    # --- Create game ---
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{BASE_HTTP}/api/games",
            json={"human_power": "FRANCE", "ai_power": "GERMANY"},
        )
        resp.raise_for_status()
        game_id = resp.json()["game_id"]
    print(f"Game {game_id}: FRANCE (you) vs GERMANY (Gemini) + 5 GreedyBots\n")

    chat_replies: list[str] = []
    germany_snapshots: list[dict] = []

    async with websockets.connect(f"{BASE_WS}/api/ws/{game_id}") as ws:
        msg = await recv_json(ws)
        assert msg["type"] == "state", f"Expected initial state, got: {msg}"
        print(f"Initial phase: {msg['data']['phase']}\n")

        for phase_num in range(3):
            state = msg["data"]
            current_phase = state["phase"]
            print(f"{'='*60}")
            print(f"Phase {phase_num + 1}/3 — {current_phase}")

            # Chat with Germany
            chat_text = CHAT_MESSAGES[phase_num]
            print(f"\n[FRANCE → GERMANY] {chat_text}")
            await ws.send(json.dumps({"type": "send_message", "text": chat_text}))
            reply_msg = await recv_json(ws)
            assert reply_msg["type"] == "message", f"Expected message, got: {reply_msg}"
            reply = reply_msg["text"]
            chat_replies.append(reply)
            print(f"[GERMANY → FRANCE] {reply}")

            # Submit France's orders (pick first legal order per location)
            orderable = state.get("orderable", [])
            possible = state.get("possible_orders", {})
            if orderable:
                orders = [possible[loc][0] for loc in orderable if possible.get(loc)]
                print(f"\n[FRANCE orders] {orders}")
                await ws.send(json.dumps({"type": "submit_orders", "orders": orders}))
                msg = await recv_json(ws)
                assert msg["type"] == "state", f"Expected state after submit, got: {msg}"
            else:
                print("\n[FRANCE] No orders this phase.")

            # Advance phase (Gemini decides Germany's orders, GreedyBots decide the rest)
            print("[Advancing phase — waiting for Gemini...]")
            await ws.send(json.dumps({"type": "advance_phase"}))
            msg = await recv_json(ws)

            if msg["type"] == "game_over":
                print(f"\nGame over! Winners: {msg['winners']}")
                break

            assert msg["type"] == "state", f"Expected state after advance, got: {msg}"
            new_state = msg["data"]
            germany = new_state["powers"].get("GERMANY", {})
            germany_snapshots.append(
                {
                    "after_phase": current_phase,
                    "units": sorted(germany.get("units", [])),
                    "centers": sorted(germany.get("centers", [])),
                }
            )
            print(f"[GERMANY after phase] units={germany_snapshots[-1]['units']}")
            print(f"                     centers={germany_snapshots[-1]['centers']}")

            if new_state["done"]:
                game_over = await recv_json(ws)
                assert game_over["type"] == "game_over"
                print(f"\nGame over! Winners: {game_over['winners']}")
                break

    # --- Summary ---
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"\nGermany's chat replies ({len(chat_replies)}):")
    for i, reply in enumerate(chat_replies, 1):
        print(f"\n  [{i}] {reply}")

    print(f"\nGermany's positions after each phase:")
    for snap in germany_snapshots:
        print(f"  After {snap['after_phase']}:")
        print(f"    units  : {snap['units']}")
        print(f"    centers: {snap['centers']}")

    print("\nTest complete — no errors.")


if __name__ == "__main__":
    asyncio.run(main())
