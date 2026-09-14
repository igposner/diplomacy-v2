"""A solo ends the game. Eighteen of the thirty-four centres, and no further
phase is played."""
import asyncio, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DIPLOMACY_DB"] = tempfile.mktemp(suffix=".sqlite3")

import main, storage
from engine.facade import Facade, VICTORY_CENTERS
from main import NewGame, Orders


async def run() -> int:
    g = await main.new_game(NewGame(power="FRANCE", advance=0))
    gid = g["game_id"]
    f = main.LIVE[gid]
    scs = sorted(f.game.map.scs)

    # one short of a solo: the game runs on
    f.game.clear_units(); f.game.clear_centers()
    f.game.set_centers("FRANCE", scs[:VICTORY_CENTERS - 1]); f.game.set_units("FRANCE", ["A PAR"])
    f.game.set_centers("GERMANY", scs[VICTORY_CENTERS - 1:VICTORY_CENTERS + 3])
    f.game.set_units("GERMANY", ["A BER"])
    storage.save_game(gid, f.game)
    s = await main.state(gid, "FRANCE")
    assert not s["done"] and s["outcome"] is None, "ended a game one centre early"

    # the eighteenth centre ends it
    f.game.set_centers("FRANCE", scs[:VICTORY_CENTERS])
    storage.save_game(gid, f.game)
    s = await main.state(gid, "FRANCE")
    o = s["outcome"]
    assert s["done"] and o and o["kind"] == "solo", f"no solo at {VICTORY_CENTERS} centres: {o}"
    assert o["winner"] == "FRANCE" and o["centers"] == VICTORY_CENTERS
    assert o["standings"][0]["power"] == "FRANCE", "standings not ordered by centres"

    # and nothing further is played
    before = s["powers"]["FRANCE"]["units"]
    r = await main.submit(gid, Orders(power="FRANCE", orders=[]))
    assert r["orders"] == [] and r["outcome"]["kind"] == "solo", "a finished game processed a phase"
    after = (await main.state(gid, "FRANCE"))["powers"]["FRANCE"]["units"]
    assert before == after, "the board moved after the game ended"

    # a defeat is the same outcome seen from another seat
    s2 = await main.state(gid, "TURKEY")
    assert s2["outcome"]["winner"] == "FRANCE", "the winner should be the same for everyone"

    print(f"ok: solo at {VICTORY_CENTERS} centres ends the game; no phase plays after it")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(run()))
    finally:
        p = os.environ["DIPLOMACY_DB"]
        for suf in ("", "-wal", "-shm"):
            if os.path.exists(p + suf):
                os.unlink(p + suf)
