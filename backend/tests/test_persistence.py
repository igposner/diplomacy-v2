"""A game must survive a restart. Proves it by dropping every in-memory handle
between writing and reading, exactly as a process restart would."""
import asyncio, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DIPLOMACY_DB"] = tempfile.mktemp(suffix=".sqlite3")

import main
from main import NewGame, Orders, Message


async def run() -> int:
    g = await main.new_game(NewGame(power="FRANCE", advance=4))
    gid = g["game_id"]
    before = await main.state(gid, "FRANCE")

    loc = before["orderable"][0]
    order = before["legalOrders"][loc][0]
    await main.orders(gid, Orders(power="FRANCE", orders=[order]))
    await main.send_message(gid, Message(sender="FRANCE", to="ENGLAND", text="Channel stays quiet."))

    # --- the restart: forget everything held in memory
    main.LIVE.clear()
    main.HUMAN.clear()

    after = await main.state(gid, "FRANCE")
    assert after["phase"] == before["phase"], "phase changed across restart"
    assert after["powers"] == before["powers"], "board changed across restart"
    eng = await main.read_messages(gid, "ENGLAND")
    assert [m["text"] for m in eng] == ["Channel stays quiet."], f"press lost: {eng}"
    ita = await main.read_messages(gid, "ITALY")
    assert ita == [], f"a private message leaked to Italy: {ita}"

    r = await main.process(gid)
    assert r["orders"], "no order results returned"
    assert any(o["outcomes"] for o in r["orders"]), "outcomes missing"

    main.LIVE.clear()
    main.HUMAN.clear()
    resumed = await main.state(gid, "FRANCE")
    assert resumed["phase"] == r["next"], "resolved phase did not persist"
    assert resumed["lastResult"]["phase"] == r["phase"], "result overlay did not persist"

    listed = await main.list_games()
    assert any(x["id"] == gid for x in listed), "game missing from the list"

    codes = sorted({c for o in r["orders"] for c in o["outcomes"]})
    print(f"ok: survived two restarts; {len(r['orders'])} order results; outcomes seen {codes}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(run()))
    finally:
        p = os.environ["DIPLOMACY_DB"]
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(p + suffix):
                os.unlink(p + suffix)
